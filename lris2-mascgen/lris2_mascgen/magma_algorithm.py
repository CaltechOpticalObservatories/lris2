import os.path

import numpy as np
import pandas as pd
from astropy.coordinates import SkyCoord
import astropy.units as u
import math, sys, argparse
import yaml, logging

from utils import transform_coordinates, inCircle, fieldCenter

'''
This script is the Python implementation of MascgenCore.java
'''

from functools import wraps
import time

def timeit(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        print(f"Function '{func.__name__}' executed in {end_time - start_time:.4f} seconds.")
        return result
    return wrapper

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TargetList:
    def __init__(self, df, type='targets'):
        self.data = df
        self.type = type

    def target_radec_to_xy(self, field_center):
        """
        Convert RA/Dec coordinates of targets to x/y coordinates relative to the field center.
        :param targets: pd.DataFrame containing targets with 'ra' and 'dec' columns.
        :param field_center: XYCoord object representing the field center in x/y coordinates.
        :return: pd.DataFrame with updated 'x' and 'y' columns.
        """
        self.data['y'] = self.data['dec'] * 3600
        self.data['x'] = math.cos(field_center.y * np.pi / 180. / 3600.) * self.data['ra'] * 3600

    def set_row(self, buffer, csuparams):
        """
        Calculate the row number for each target based on its y coordinate and a buffer.
        :param targets: pd.DataFrame containing targets with 'y' column.
        :param buffer: float representing the buffer in arcseconds.
        :return: pd.DataFrame with an additional 'row' column.
        """
        fac1 = (csuparams.single_slit_height - 2.0 * buffer) / csuparams.csu_row_height
        fac2 = (buffer + csuparams.overlap / 2.0) / csuparams.csu_row_height
        try:
            ydivrow = self.data['y_transformed'] / csuparams.csu_row_height
        except KeyError:
            raise KeyError("Error: y_transformed column not found in targets DataFrame. Make sure to call transform_coordinates first.")

        ydivrow_floor = np.floor(ydivrow)
        sel = (ydivrow >= 0) & (ydivrow_floor < csuparams.num_bar_pairs) & (ydivrow > ydivrow_floor + fac2) & (ydivrow < ydivrow_floor + fac1 + fac2)
        self.data.loc[sel, 'obj_rr'] = ydivrow_floor[sel].astype(int)

    # def set_overlap_row(self, buffer, csuparams):
    #     """
    #     Calculate the overlap region number for each target based on its y coordinate and a buffer.
    #     :param targets: pd.DataFrame containing targets with 'y' column.
    #     :param buffer: float representing the buffer in arcseconds.
    #     :return: pd.DataFrame with an additional 'overlap_region' column.
    #     """
    #     fac1 = (csuparams.single_slit_height - 2.0 * buffer) / csuparams.csu_row_height
    #     fac2 = (buffer + csuparams.overlap / 2.0) / csuparams.csu_row_height
    #     try:
    #         ydivrow = self.data['y_transformed'] / csuparams.csu_row_height - fac1 - fac2
    #     except KeyError:
    #         raise KeyError("Error: y_transformed column not found in targets DataFrame. Make sure to call transform_coordinates first.")
    #     ydivrow_floor = np.floor(ydivrow)
    #     sel = (ydivrow >= 0) & (ydivrow_floor < csuparams.num_bar_pairs - 1) & (ydivrow < ydivrow_floor + 2.0 * fac2)
    #     self.data.loc[sel, 'obj_or'] = ydivrow_floor[sel].astype(int) + 1
    #
    # def update_dither_rows(self, factor, csuparams):
    #     y1 = self.data['obj_y'] + factor * np.cos(csuparams.csu_slit_tilt_angle_rad)
    #     y2 = self.data['obj_y'] - factor * np.cos(csuparams.csu_slit_tilt_angle_rad)
    #     self.data['min_row'] = np.floor((y2 + csuparams.csu_height / 2 - csuparams.overlap) / csuparams.csu_row_height).astype(int)
    #     self.data['max_row'] = np.floor((y1 + csuparams.csu_height / 2 + csuparams.overlap) / csuparams.csu_row_height).astype(int)

# Create Node class similar to Java
class Node:
    def __init__(self, obj=None):
        # obj is expected to be a dict or pandas Series representing a DataFrame row
        self.next_node = None
        self.obj = obj if obj is not None else {}
        self.score = self.obj['priority'] if self.obj else 0.0

    def set_next_node(self, next_node):
        self.next_node = next_node

    def get_next_node(self):
        return self.next_node

    def set_obj(self, obj):
        self.obj = obj

    def get_obj(self):
        return self.obj

    def set_score(self, score):
        self.score = score

    def get_score(self):
        return self.score

    def total_score(self):
        # Recursively sum scores along the linked list
        if self.next_node:
            return self.score + self.next_node.total_score()
        return self.score

    def create_object_dataframe_from_top_node(self):
        data = []
        local_node = self
        while local_node is not None:
            if local_node.obj:
                local_node.obj['inValidSlit'] = True
                data.append(local_node.obj)
            local_node = local_node.next_node
        return pd.DataFrame(data)

    def __str__(self):
        if not self.next_node:
            return str(self.obj)
        return f"{self.obj} -> {self.next_node.obj}"

def get_next_factor(current):
    if current > 0:
        return -1 * current
    else:
        return -1 * current + 1

class MascgenCore:
    def __init__(self, args):
        # Validate command line arguments and load CSU parameters
        self.csuparams = CSUParameters(args.configfile)
        self.validate_args(args)
        self.args = args

        # Load target list
        self.science_targets, self.alignment_stars, self.ra_coord_wrap = self.load_target_list(args.targetlist)

        # if center coordinates are not provided in args or COP is true run COP estimation
        self.field_center = self.get_center_position(args.centerra, args.centerdec, args.runcop)
        self.bestNodes = [None] * self.csuparams.num_bar_pairs
        self.allNodes = [[] for _ in range(self.csuparams.num_bar_pairs)]
        self.optimal_run_num = 0
        self.final_pa = 0
        self.final_field_center = fieldCenter(0, 0)
        self.total_priority = 0
        self.final_alignment_stars = None
        self.optimum_target_list = None

    def validate_args(self, args):
        try:
            if args.xsteps < 0 or args.ysteps < 0 or args.pasteps < 0:
                raise ValueError("xsteps, ysteps, and pasteps must be positive integers.")
            if not (0 < args.xrange <= self.csuparams.csu_width / 60.0):
                raise ValueError(
                    f"Error: x range must be > 0 and <= CSU width ({self.csuparams.csu_width:.3f} arc min).")  # Substituting default x range = {config['default_xrange']}.")
            if not (-self.csuparams.csu_width / 120.0 < args.xcenter < self.csuparams.csu_width / 120.0):
                raise ValueError(
                    f"Error: x center must be between {-self.csuparams.csu_width / 120.0:.3f} and {self.csuparams.csu_width / 120.0:.3f} arc min.")
            if not (0 < args.slitwidth <= self.csuparams.csu_width):
                raise ValueError(f"Error: slit width must be > 0 and <= CSU width ({self.csuparams.csu_width:.3f} arc sec).")
            if not (0 <= args.ditherspace <= self.csuparams.single_slit_height / 2):
                raise ValueError(
                    f"Error: dither space must be >= 0 and <= {self.csuparams.single_slit_height / 2:.3f} arc sec.")
        except ValueError as e:
            logger.error(f"Error: {e} Exiting ...")
            sys.exit(1)

        self.csuparams.min_legal_x = 60. * (args.xcenter - args.xrange / 2.)
        self.csuparams.max_legal_x = 60. * (args.xcenter + args.xrange / 2.)
        self.csuparams.star_edge_buffer = args.star_edge_buffer
        self.csuparams.min_alignment_stars = args.min_alignment_stars
        self.csuparams.dither_space = args.ditherspace
        self.csuparams.xcenter = args.xcenter

    def load_target_list(self, input_file):
        """
        Load target list from a space separated text file
        Args:
            input_file (str): Path to the input file containing target data.
        Returns:
            pd.DataFrame: DataFrame containing the target list.
        """
        # Read the input file into a DataFrame (subject to changes in the file format)
        try:
            targets = pd.read_csv(input_file, sep='\s+', header=None,
                                  names=['target', 'priority', 'magnitude', 'ra_h', 'ra_m', 'ra_s', 'dec_d', 'dec_m',
                                         'dec_s', 'epoch1', 'epoch2', 'unk1', 'unk2'],
                                  dtype={'target': str, 'priority': float, 'magnitude': float, 'ra_h': int, 'ra_m': int,
                                         'ra_s': float, 'dec_d': str, 'dec_m': int,
                                         'dec_s': float})
        except Exception as e:
            raise ValueError(f"Error reading target list file (make sure it is in the required format): {e}")

        # Validate target data
        high_obj_ra_hour = targets['ra_h'].max()
        low_obj_ra_hour = targets['ra_h'].min()
        high_obj_dec_deg = float(targets['dec_d'].max())
        low_obj_dec_deg = float(targets['dec_d'].min())

        if (high_obj_ra_hour - low_obj_ra_hour > 1) and (high_obj_ra_hour != 23 or low_obj_ra_hour != 0):
            raise ValueError(
                "Error: object list spans more than one hour in Right Ascension. Shorten the list. Exiting ...")

        if high_obj_dec_deg - low_obj_dec_deg > 1:
            raise ValueError(
                "Error: object list spans more than one degree in Declination. Shorten the list. Exiting ...")

        # Check if RA coordinates wrap around 0h
        ra_coord_wrap = high_obj_ra_hour == 23 and low_obj_ra_hour == 0
        if ra_coord_wrap:
            targets.loc[targets['ra_h'] == 0, 'ra_h'] = 12
            targets.loc[targets['ra_h'] == 23, 'ra_h'] = 11

        # Convert RA and Dec to arcseconds (not using SkyCoord because it is slower for large lists)
        targets['ra'] = (targets['ra_h'] + targets['ra_m'] / 60.0 + targets['ra_s'] / 3600.0) * 15.
        targets['dec_sign'] = [-1 if d.startswith('-') else 1 for d in targets['dec_d']]
        targets['dec'] = (np.abs(targets['dec_d'].astype(float)) + targets['dec_m'] / 60.0 + targets[
            'dec_s'] / 3600.0) * targets['dec_sign']

        targets['obj_rr'] = -1  # row number for single slits
        targets['obj_or'] = -1  # overlap region number for double slits

        # Drop unnecessary columns
        targets = targets.drop(columns=['ra_h', 'ra_m', 'ra_s', 'dec_d', 'dec_m', 'dec_s',
                                        'epoch1', 'epoch2', 'unk1', 'unk2'])
        # Split by negative and positive priority and put into TargetList class
        science_targets = TargetList(targets[targets['priority'] > 0].reset_index(drop=True))
        alignment_stars = TargetList(targets[targets['priority'] < 0].reset_index(drop=True))
        return science_targets, alignment_stars, ra_coord_wrap

    def get_center_position(self, centerra, centerdec, runcop):
        """
        Calculate the center position based on the target list and arguments.
        If center coordinates are not provided in args or runcop is true, it runs COP estimation.
        :param targets: DataFrame containing target data.
        :param args: Parsed command line arguments.
        :param ra_coord_wrap: Boolean indicating if RA coordinates wrap around.
        :return: Modified args in place
        """
        targets = self.science_targets.data
        if centerra is None or centerdec is None or runcop:
            centerdec = (targets['dec'] * targets['priority']).sum() / targets['priority'].sum()
            centerra = (targets['ra'] * targets['priority']).sum() / targets['priority'].sum()
        else:
            center_coords = SkyCoord(ra=centerra, dec=centerdec, unit=(u.hourangle, u.deg))
            centerra = center_coords.ra.deg  # in degrees
            centerdec = center_coords.dec.deg  # in degrees

        # print the center coordinates
        logger.info(f"Center coordinates: RA={centerra:.6f} Dec={centerdec:.6f} degrees")
        field_center = fieldCenter(centerra, centerdec)
        if self.ra_coord_wrap:
            field_center.do_ra_coord_wrap()
        return field_center

    @timeit
    def optimize(self, field_center, pa):
        # reset nodes
        self.bestNodes = [None] * self.csuparams.num_bar_pairs
        self.allNodes = [[] for _ in range(self.csuparams.num_bar_pairs)]

        # Deep copy target list
        objects = self.science_targets.data.copy()

        # Transform coordinates similar to Java version
        obj_x, obj_y = transform_coordinates(objects['x'].to_numpy(), objects['y'].to_numpy(), field_center.x,
                                             field_center.y, pa)
        objects['obj_x'] = obj_x
        objects['obj_y'] = obj_y
        obj_x_lower = obj_x - self.csuparams.dither_space * np.sin(self.csuparams.csu_slit_tilt_angle_rad)
        obj_y_lower = obj_y - self.csuparams.dither_space * np.cos(self.csuparams.csu_slit_tilt_angle_rad)
        obj_x_upper = obj_x + self.csuparams.dither_space * np.sin(self.csuparams.csu_slit_tilt_angle_rad)
        obj_y_upper = obj_y + self.csuparams.dither_space * np.cos(self.csuparams.csu_slit_tilt_angle_rad)

        # Check what is within focal plane
        in_circle = (inCircle(obj_x_lower, obj_y_lower, 0, 0, self.csuparams.csu_fp_radius) &
                     inCircle(obj_x_upper, obj_y_upper, 0, 0, self.csuparams.csu_fp_radius))
        # Check legal x bounds
        inLegalx = ((obj_x_lower >= self.csuparams.min_legal_x) & (obj_x_upper <= self.csuparams.max_legal_x)
                    & (obj_x_lower > -self.csuparams.csu_width / 2.) & (obj_x_upper < self.csuparams.csu_width / 2.)
                    & (obj_y_lower > -self.csuparams.csu_height / 2.) & (obj_y_upper < self.csuparams.csu_height / 2.))

        objects['min_row'] = np.floor(
            (obj_y_lower + self.csuparams.csu_height / 2. - self.csuparams.overlap) / self.csuparams.csu_row_height).astype(int)
        objects['max_row'] = np.floor(
            (obj_y_upper + self.csuparams.csu_height / 2. + self.csuparams.overlap) / self.csuparams.csu_row_height).astype(int)

        # filter valid objects
        mask_valid = in_circle & inLegalx & (objects.min_row >= 0) & (objects.max_row < self.csuparams.num_bar_pairs)
        valid_objects = objects[mask_valid].reset_index(drop=True)

        if valid_objects.empty:
            return pd.DataFrame()

        for i, n in enumerate(valid_objects.max_row):
            self.allNodes[n].append(Node(valid_objects.loc[i].to_dict()))

        best_score = 0
        best_node = Node()

        for i in range(self.csuparams.num_bar_pairs):
            current_best = Node()
            if i > 0:
                current_best.next_node = self.bestNodes[i - 1]

            # Try each object that can fit in this row
            for node in self.allNodes[i]:
                obj_data = node.obj

                if node.score == 0:
                    node.score = obj_data['priority']
                # Find valid previous row connection
                span = obj_data['max_row'] - obj_data['min_row']
                prev_row = i - span - 1

                if prev_row >= 0:
                    node.next_node = self.bestNodes[prev_row]

                # Compare total scores
                node_total = node.total_score()
                current_total = current_best.total_score()

                if node_total > current_total:
                    current_best = node
                elif node_total == current_total:
                    # Tie-breaker: prefer object closer to x_center
                    obj_x = obj_data['obj_x']
                    n = i
                    tempnode = current_best
                    while n >= obj_data['min_row']:
                        localobj = tempnode.obj
                        if localobj != {} and abs(obj_x - self.csuparams.xcenter * 60.0) < abs(
                                localobj['obj_x'] - self.csuparams.xcenter * 60.0):
                            current_best = node
                            break
                        tempnode = tempnode.get_next_node()
                        if tempnode is None or tempnode.obj == {}:
                            break
                        n = tempnode.obj['max_row']

            # Check for conflicts with multi-row slits
            current_obj = current_best.obj
            if current_obj and 'min_row' in current_obj:
                span = current_obj['max_row'] - current_obj['min_row']
                for j in range(i - 1, i - span - 1, -1):
                    if j < 0:
                        break
                    # If there is a best node in the conflicting row, compare scores
                    prev_total = self.bestNodes[j].total_score()
                    curr_total = current_best.total_score()
                    if prev_total > curr_total:
                        current_best = Node()
                        current_best.next_node = self.bestNodes[j]

            self.bestNodes[i] = current_best

            # Track overall best solution
            total_score = current_best.total_score()
            if total_score > best_score:
                best_score = total_score
                best_node = current_best

        return best_node

    def find_legal_stars(self, field_center, pa):

        new_x, new_y = transform_coordinates(self.alignment_stars.data['x'].to_numpy(), self.alignment_stars.data['y'].to_numpy(),
                                             field_center.x, field_center.y, pa,
                                             self.csuparams.csu_width / 2., self.csuparams.csu_height / 2.)
        self.alignment_stars.data['x_transformed'] = new_x
        self.alignment_stars.data['y_transformed'] = new_y
        validstars = (
                inCircle(new_x, new_y, self.csuparams.csu_width / 2, self.csuparams.csu_height / 2, self.csuparams.csu_fp_radius) &
                (new_x > self.csuparams.star_edge_distance) & (new_x < self.csuparams.csu_width - self.csuparams.star_edge_distance) &
                (new_y > self.csuparams.star_edge_distance) & (new_y < self.csuparams.csu_height - self.csuparams.star_edge_distance))
        self.alignment_stars.data = self.alignment_stars.data[validstars].reset_index(drop=True)
        self.alignment_stars.set_row(self.csuparams.star_edge_buffer)
        return self.alignment_stars.data[self.alignment_stars.data['obj_rr'] != -1].reset_index(drop=True)

    def run(self):
        # Run the three-level loop over position angle, field center y-coordinate, and field center x-coordinate.
        # Initialize variables to track the best solution
        run_num = 0

        # print starting message with number of iterations
        total_runs = (self.args.xsteps * 2 + 1) * (self.args.ysteps * 2 + 1) * (self.args.pasteps * 2 + 1)
        logger.info(
            f"Total iterations: {total_runs}, xsteps: {self.args.xsteps * 2 + 1}, ysteps: {self.args.ysteps * 2 + 1}, pasteps: {self.args.pasteps * 2 + 1}")

        # Initialising xfactor, yfactor, pafactor, because instead of linearly iterating, we want to iterate closest to center first.
        # The get_next_factor function helps with that.
        xfactor, yfactor, pafactor = 0, 0, 0

        # Initialize other variables
        temp_field_center = fieldCenter(0, 0)

        # Start of the three-level loop
        logger.info("*** STARTING OPTIMIZATION ***")
        success = False
        for _ in range(-self.args.xsteps, self.args.xsteps + 1):
            temp_field_center.x = self.field_center.x - xfactor * self.args.xstepsize
            xfactor = get_next_factor(xfactor)
            yfactor = 0

            for _ in range(-self.args.ysteps, self.args.ysteps + 1):
                temp_field_center.y = self.field_center.y - yfactor * self.args.ystepsize
                yfactor = get_next_factor(yfactor)
                pafactor = 0
                # Once we have the perturbated field center, we need to convert the target list to x,y coordinates relative to that field center.
                self.science_targets.target_radec_to_xy(temp_field_center)
                self.alignment_stars.target_radec_to_xy(temp_field_center)

                for _ in range(-self.args.pasteps, self.args.pasteps + 1):
                    temp_pa = self.args.centerpa + pafactor * self.args.pastepsize
                    pafactor = get_next_factor(pafactor)

                    # Check if alignment stars are required, if yes, find valid stars
                    if self.args.min_alignment_stars > 0:
                        starlist = self.find_legal_stars(temp_field_center, temp_pa)
                        starsfound = len(starlist['obj_rr'].unique())
                    else:
                        starlist = pd.DataFrame()
                        starsfound = 0
                    logger.debug(
                        f"Alignment stars required: {self.args.min_alignment_stars}, Legal stars found: {starsfound}")
                    run_num += 1
                    if starsfound >= self.args.min_alignment_stars:
                        # Run the optimization
                        best_node = self.optimize(temp_field_center, temp_pa)
                        best_score = best_node.total_score()
                        if best_score >= self.total_priority:
                            success = True
                            self.total_priority = best_score
                            self.optimal_run_num = run_num
                            logger.info(
                                f"New optimal found at run {self.optimal_run_num}, best score so far is {best_score}")
                            # Store the best solution details
                            temp_field_center.to_radec()
                            if self.ra_coord_wrap:
                                temp_field_center.do_ra_coord_wrap()
                            self.final_field_center = fieldCenter(temp_field_center.ra, temp_field_center.dec)
                            self.final_pa = temp_pa
                            self.final_alignment_stars = starlist
                            self.optimum_target_list = best_node.create_object_dataframe_from_top_node()
                        elif best_score == self.total_priority:
                            logger.info(
                                f"Configuration with same score {best_score} found at run {run_num}. Not updating optimal solution.")
                            if len(self.optimum_target_list) == 0:
                                temp_field_center.to_radec()
                                if self.ra_coord_wrap:
                                    temp_field_center.do_ra_coord_wrap()
                                self.final_field_center = fieldCenter(temp_field_center.ra, temp_field_center.dec)
                                self.final_pa = temp_pa
                                self.final_alignment_stars = starlist
                    elif len(self.optimum_target_list) == 0 and starsfound > self.args.min_alignment_stars:
                        temp_field_center.to_radec()
                        if self.ra_coord_wrap:
                            temp_field_center.do_ra_coord_wrap()
                        self.final_field_center = fieldCenter(temp_field_center.ra, temp_field_center.dec)
                        self.final_pa = temp_pa
                        self.final_alignment_stars = starlist
        logger.info(f"*** OPTIMIZATION COMPLETE ***")
        if success:
            logger.info(f"Optimal solution found at run {self.optimal_run_num} with total priority {self.total_priority}.")
            logger.info(
                f"Final Center: RA={self.final_field_center.ra:.6f}, Dec={self.final_field_center.dec:.6f}, PA={self.final_pa:.2f}")
            logger.info(f"Number of legal alignment stars: {len(self.final_alignment_stars)}")
            logger.info(f"Number of targets in optimal solution: {len(self.optimum_target_list)}")

class CSUParameters:
    def __init__(self, config_path="config.yaml"):
        self.config = self.load_csu_config(config_path)
        for key, value in self.config.items():
            setattr(self, key, value)
        self.single_slit_height = self.single_slit_height_mm * self.arcsec_per_mm
        self.overlap = self.overlap_mm * self.arcsec_per_mm
        self.csu_row_height = self.single_slit_height + self.overlap
        self.csu_row_height_mm = self.single_slit_height_mm + self.overlap_mm
        self.csu_height = self.num_bar_pairs * self.csu_row_height
        self.csu_height_mm = self.num_bar_pairs * self.csu_row_height_mm
        self.csu_width = self.csu_height
        self.csu_width_mm = self.csu_height_mm
        self.csu_fp_radius_mm = self.csu_fp_radius / self.arcsec_per_mm
        self.csu_slit_tilt_angle_rad = np.radians(self.csu_slit_tilt_angle)
        self.min_legal_x = None  # To be set from validate_args
        self.max_legal_x = None  # To be set from validate_args
        self.star_edge_buffer = None
        self.min_alignment_stars = None
        self.dither_space = None
        self.xcenter = None

    def load_csu_config(self, config_path="config.yaml"):
        """
        Load the CSU configuration from a YAML file.
        Returns:
            dict: Configuration dictionary.
        """
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        return config

def get_args():
    """
    Parse command line arguments.
    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description="CSU Optimization Script")
    parser.add_argument('targetlist', type=str, help='Path to the input target list file')
    parser.add_argument('--configfile', type=str, default=f'{os.path.dirname(os.path.abspath(__file__))}/../config.yaml', help='Path to the configuration YAML file')
    parser.add_argument("--xrange", type=float, default=3.0, help="Width of legal x coordinate range (arcmin)")
    parser.add_argument("--xcenter", type=float, default=0.0, help="Center of legal x coordinate range (arcmin)")
    parser.add_argument("--slitwidth", type=float, default=0.7, help="Global slit width (arcsec)")
    parser.add_argument("--ditherspace", type=float, default=2.5, help="Minimum distance from slit edge (arcsec)")
    parser.add_argument("--centerra", type=str, help="Center RA in HH:MM:SS format")
    parser.add_argument("--centerdec", type=str, help="Center Dec in DD:MM:SS format")
    parser.add_argument("--centerpa", type=float, default=0, help="Center position angle (deg)")
    parser.add_argument("--xsteps", type=int, default=0, help="Number of x iterations (int, must be positive)")
    parser.add_argument("--xstepsize", type=float, default=1, help="Size of each x step (arcsec)")
    parser.add_argument("--ysteps", type=int, default=0, help="Number of y iterations (int)")
    parser.add_argument("--ystepsize", type=float, default=1, help="Size of each y step (arcsec)")
    parser.add_argument("--pasteps", type=int, default=0, help="Number of PA iterations (int)")
    parser.add_argument("--pastepsize", type=float, default=1, help="Size of each PA step (deg)")
    parser.add_argument("--min_alignment_stars", type=int, default=3, help="Minimum number of alignment stars")
    parser.add_argument("--star-edge-buffer", type=float, default=2.0, help="Minimum distance ???")
    parser.add_argument("--slitlist", type=str, default='slitsolution.txt', help="Output file for slit list")
    parser.add_argument("--slitregionfile", type=str, default='slitsolution.reg', help="Output file for region file")
    parser.add_argument("--barpositionlist", type=str, default='barposition.txt', help="Output file for bar positions")
    parser.add_argument("--runcop", action='store_true',
                        help="Run COP estimation for priority weighted center position", default=False)
    parser.add_argument("--debug", action='store_true', help="Enable debug mode", default=False)

    return parser.parse_args()



    # # Generate slit configurations
    # slit_configurations = slit_configuration_generator(optimum_astro_obj_array, config, csu_params, final_field_center, final_pa, args.barpositionlist)
    # slit_configurations['coord'] = [SkyCoord(ra=ra, dec=dec, unit=(u.deg, u.deg)) for ra, dec in zip(slit_configurations['ra'], slit_configurations['dec'])]
    # slit_configurations['ra_hms'] = [coord.ra.to_string(unit=u.hour, sep=':') for coord in slit_configurations['coord']]
    # slit_configurations['dec_dms'] = [coord.dec.to_string(unit=u.deg, sep=':') for coord in slit_configurations['coord']]
    #
    # slit_configurations['coord_obj'] = [SkyCoord(ra=ra, dec=dec, unit=(u.deg, u.deg)) for ra, dec in zip(slit_configurations['obj_ra'], slit_configurations['obj_dec'])]
    # slit_configurations['obj_ra_hms'] = [coord.ra.to_string(unit=u.hour, sep=':') for coord in slit_configurations['coord_obj']]
    # slit_configurations['obj_dec_dms'] = [coord.dec.to_string(unit=u.deg, sep=':') for coord in slit_configurations['coord_obj']]


    # if ra_coord_wrap:
    #     slit_configurations.loc[[int(ra_hms.split(':')[0])==12 for ra_hms in slit_configurations['ra_hms']], 'ra_hms'] = [f"00:{ra_hms.split(':')[1]}:{ra_hms.split(':')[2]}" for ra_hms in slit_configurations['ra_hms']]
    #     slit_configurations.loc[[int(ra_hms.split(':')[0])==11 for ra_hms in slit_configurations['ra_hms']], 'ra_hms'] = [f"23:{ra_hms.split(':')[1]}:{ra_hms.split(':')[2]}" for ra_hms in slit_configurations['ra_hms']]
    #     # same for final field center ra dec
    #     if finalcenter_coords.ra.hour == 12:
    #         finalcenterra = finalcenterra.replace('12', '00')
    #     elif finalcenter_coords.ra.hour == 11:
    #         finalcenterra = finalcenterra.replace('11', '23')

    # # The final step is to print the slit configuration.
    # print(f"The optimized slit configuration has been found after {run_num} runs."
    #       f"\n\tTotal Priority = {total_priority}"
    #       f"\n\tNumber of Slits = {len(slit_configurations)}"
    #       f"\n\tCSU Center Position = RA: {finalcenterra} Dec: {finalcenterdec}"
    #       f"\n\t Position Angle = {final_pa:.1f}°\n")
    #
    # # Write the slit list out.
    # write_out_slit_list(args.slitlist, slit_configurations, csu_params['slitwidth'])
    # print(f"The slit list file is: {args.slitlist}")
    #
    # # Write out the region file.
    # print_regions_from_slit_array(slit_configurations, config, csu_params, final_field_center, finalcenterra, finalcenterdec, final_pa, args.slitregionfile)
    # print(f"The corresponding bar position list is: {args.barpositionlist}")

## Run mascgen, track the time it takes to run the script
if __name__ == "__main__":
    start_time = time.time()

    args = get_args()
    if args.debug:
        logger.setLevel(logging.DEBUG)
    mascgen = MascgenCore(args)
    mascgen.run()

    end_time = time.time()
    print(f"Script executed in {end_time - start_time:.2f} seconds.")



