import pandas as pd
import numpy as np
import math

class Slit:
    def __init__(self, slit_number=-1, slit_width=-1, slit_length=-1, slit_obj_name="blank",
                 slit_obj_priority=0, slit_obj_x=-1, slit_obj_y=-1):
        self.slit_number = slit_number
        self.slit_width = slit_width
        self.slit_length = slit_length
        self.slit_x = -1
        self.slit_y = -1
        self.slit_obj_name = slit_obj_name
        self.slit_obj_priority = slit_obj_priority
        self.obj_mag = None
        self.ra = None # degrees
        self.dec = None # degrees
        self.epoch = None
        self.equinox = None
        self.wcs_x = None
        self.wcs_y = None
        self.slit_obj_x = slit_obj_x
        self.slit_obj_y = slit_obj_y
        self.slit_obj_wcs_x = None
        self.slit_obj_wcs_y = None
        self.obj_ra = None
        self.obj_dec = None
        self.slit_mul = -1
        self.target_location = None

    def print_slit(self):
        print(f"{self.slit_number}\t{self.ra_hour}\t{self.ra_min}\t{self.ra_sec:.2f}\t"
              f"{self.dec_deg}\t{self.dec_min}\t{self.dec_sec:.2f}\t{self.slit_width:.2f}\t"
              f"{self.slit_length:.2f}\t{self.slit_obj_name}\t{self.slit_obj_priority:.2f}\t"
              f"{self.target_location:.2f}\t{self.obj_ra_hour}\t{self.obj_ra_min}\t"
              f"{self.obj_ra_sec:.2f}\t{self.obj_dec_deg}\t{self.obj_dec_min}\t{self.obj_dec_sec:.2f}")

    def print_slit_short(self):
        print(f"{self.slit_obj_x} {self.slit_y} {self.slit_width} {self.slit_length}")

    def is_not_blank(self):
        return self.slit_obj_name != "blank"

    def is_blank(self):
        return self.slit_obj_name == "blank"

# Clean up all the Slit Multiple Length numbers and Priorities.
def clean_up_slit_mul_pri(array):
    for i in range(len(array)):
        if array.loc[i,'slit_obj_priority'] > 0:
            for j in range(len(array)):
                if array.loc[j,'slit_obj_name'] == array.loc[i,'slit_obj_name']:
                    array.loc[j, 'slit_mul'] = array.loc[i, 'slit_mul']
                    array.loc[j, 'slit_obj_priority'] = array.loc[i, 'slit_obj_priority']
    return array
# def clean_up_slit_mul_pri(array):
#     """
#     Propagate 'slit_mul' and 'slit_obj_priority' values across rows with the same 'slit_obj_name'.
#     Args:
#         array (pd.DataFrame): DataFrame containing 'slit_obj_name', 'slit_mul', and 'slit_obj_priority' columns.
#     Returns:
#         pd.DataFrame: Updated DataFrame with consistent 'slit_mul' and 'slit_obj_priority' values.
#     """
#     # Group by 'slit_obj_name' and propagate the maximum 'slit_mul' and 'slit_obj_priority' within each group
#     array[['slit_mul', 'slit_obj_priority']] = array.groupby('slit_obj_name')[['slit_mul', 'slit_obj_priority']].transform('max')
#     return array

# Expand slit1 into slit2 and copy everything over.
def expand_slit(slit_array, s1, s2, slit_width):
    if slit_array.loc[s1,'slit_obj_name'] != "blank":
        slit_array.loc[s2,'slit_obj_name'] = slit_array.loc[s1,'slit_obj_name']
        slit_array.loc[s2,'slit_width'] = slit_width
        slit_array.loc[s2,'slit_obj_x'] = slit_array.loc[s1,'slit_obj_x']
        slit_array.loc[s2,'slit_obj_y'] = slit_array.loc[s1,'slit_obj_y']
        slit_array.loc[s1,'slit_mul'] = slit_array.loc[s1,'slit_mul'] + 1
    return slit_array

def slit_xy_to_radec(slit_array, field_center):
    # Convert the wcs x and y coordinates of the input slit dataframe into Ra/Dec coordinates.
    slit_array['dec'] = slit_array['wcs_y'] / 3600  # Convert arcseconds to degrees
    dec_rad = field_center.y * math.pi / 180 / 3600 # Convert degrees to radians
    slit_array['ra'] = slit_array['wcs_x'] / (3600 * math.cos(dec_rad))  # Convert arcseconds to degrees (15 degrees per hour)
    return slit_array

def slit_objxy_to_radec(slit_array, field_center):
    # Convert the obj x and y coordinates of the input slit dataframe into Ra/Dec coordinates.
    slit_array['obj_dec'] = slit_array['slit_obj_wcs_y'] / 3600  # Convert arcseconds to degrees
    dec_rad = field_center.y * math.pi / 180 / 3600  # Convert degrees to radians
    slit_array['obj_ra'] = slit_array['slit_obj_wcs_x'] / (3600 * math.cos(dec_rad))  # Convert arcseconds to degrees (15 degrees per hour)
    return slit_array

def slit_configuration_generator(optimum_astro_obj_array, config, csu_params, final_field_center, final_pa, bar_position_list):
    """
    Generate the slit configuration from a given input array of AstroObjs.
    Args:
        optimum_astro_obj_array (list): Optimized AstroObj array.
        config (dict): Configuration parameters for the CSU
        csu_params (dict): CSU parameters including slit width and overlap.
        final_field_center (object): Final field center coordinates.
        final_pa (float): Final position angle.
        bar_position_list (str): Path to the output file for bar positions.
    Returns:
        list: Array of Slit objects.
    """
        # /** The rest of the program simply takes the data from hPArray2Short and
        #  * maps it to a slit configuration. The empty bars are filled
        #  * by expanding original "singles" into "doubles" or "triples" when
        #  * possible and by expanding original "doubles" (which were created to
        #  * include a high-priority object in an overlap region) into "triples"
        #  * when possible. After this first pass expansion is complete, any
        #  * remaining empty slits are filled by expanding the nearest slit with
        #  * the higher-priority object. The slit expansion is conducted so as to
        #  * give more vertical space to the objects that are more likely to need
        #  * it and then to objects with higher priority. **/

    # Initialize the slit array with empty Slit objects
    slit_array = pd.DataFrame([Slit(slit_number=i+1).__dict__ for i in range(config['num_rows'])])
    # Copy the Overlap region objects into their proper slit assignment
    # pair. Object in OverlapRegion# is given slits numbered # and # - 1.
    # Also copy the Row region objects into their corresponding slit
    # assignments.
    for i in range(len(optimum_astro_obj_array)):
        OR = int(optimum_astro_obj_array.iloc[i]['obj_or'])
        if OR>=0:
            slit_array.loc[OR-1,['slit_obj_name','slit_obj_priority','slit_obj_x','slit_obj_y']] \
                = optimum_astro_obj_array.iloc[i][['target', 'priority', 'obj_x', 'obj_y']].tolist()
            slit_array.loc[OR-1, 'slit_width'] = csu_params['slitwidth']
            slit_array.loc[OR-1, 'slit_mul'] = 2
            slit_array.loc[OR,['slit_obj_name','slit_obj_x','slit_obj_y']] \
                = optimum_astro_obj_array.iloc[i][['target', 'obj_x', 'obj_y']].tolist()
            slit_array.loc[OR, 'slit_width'] = csu_params['slitwidth']
        RR = int(optimum_astro_obj_array.iloc[i]['obj_rr'])
        if RR>=0:
            slit_array.loc[RR,['slit_obj_name','slit_obj_priority','slit_obj_x','slit_obj_y']] \
                = optimum_astro_obj_array.iloc[i][['target', 'priority', 'obj_x', 'obj_y']].tolist()
            slit_array.loc[RR, 'slit_width'] = csu_params['slitwidth']
            slit_array.loc[RR, 'slit_mul'] = 1
    # Clean up slit_mul and slit_obj_priority
    slit_array = clean_up_slit_mul_pri(slit_array)

    # print(slit_array[['slit_number', 'slit_obj_name', 'slit_obj_priority', 'slit_mul']])

    # Extend slits in length to expand singles into double, doubles into
    # triples, etc.
    # First expand slit 1 into slit 2 and slit 44 into slit 43 if the
    # first slits are originally singles and if 44 and 43 are unoccupied
    # and if slit 1's object has higher priority than slit 3's (and if
    # slit 44's object has higher priority than slit 42's).
    # Then, lengthen occupied slits 2 and 45 into 1 and 46, respectively,
    # if slits 1 and 46 are unoccupied. There is no need to compare
    # priorities since there can be no objects in slits 0 or 47 (there are
    # no such slits).
    if (slit_array.loc[1,'slit_mul'] == 1 and slit_array.loc[2,'slit_mul'] == -1 and slit_array.loc[1,'slit_obj_priority'] > slit_array.loc[3,'slit_obj_priority']):
        slit_array = expand_slit(slit_array, 1, 2, csu_params['slitwidth'])

    if (slit_array.loc[44,'slit_mul'] == 1 and slit_array.loc[43,'slit_mul'] == -1 and slit_array.loc[44,'slit_obj_priority'] > slit_array.loc[42,'slit_obj_priority']):
        slit_array = expand_slit(slit_array, 44, 43, csu_params['slitwidth'])

    if (slit_array.loc[1,'slit_mul'] == 1 and slit_array.loc[0,'slit_mul'] == -1):
        slit_array.loc[0,'slit_obj_name'] = slit_array.loc[1,'slit_obj_name']
        slit_array = expand_slit(slit_array, 1, 0, csu_params['slitwidth'])

    if (slit_array.loc[44,'slit_mul'] == 1 and slit_array.loc[45,'slit_mul'] == -1):
        slit_array.loc[45,'slit_obj_name'] = slit_array.loc[44,'slit_obj_name']
        slit_array = expand_slit(slit_array, 44, 45, csu_params['slitwidth'])
    slit_array = clean_up_slit_mul_pri(slit_array)
    # Then extend all "singles" into "doubles" (or "triples") when possible
    # and so that, if there is a conflict, the slit which is extended is
    # the one that contains the higher-priority object. Note that we at
    # first ignore the first set of doubles that were created in order to
    # surround objects in overlap regions. This makes sense since those
    # original doubles are guaranteed to have their target objects near
    # their vertical slit center (within the middle overlap region).
    for i in range(len(slit_array)):
        if slit_array.loc[i,'slit_mul'] == 1:
            if i < 44:
                if slit_array.loc[i + 1,'slit_mul'] == -1:
                    if (slit_array.loc[i,'slit_obj_priority'] > slit_array.loc[i + 2,'slit_obj_priority']) or (slit_array.loc[i + 2,'slit_mul'] == 2):
                        slit_array = expand_slit(slit_array, i, i + 1, csu_params['slitwidth'])
                        slit_array.loc[i + 1,'slit_mul'] = slit_array.loc[i,'slit_mul']
            if i > 1:
                if slit_array.loc[i - 1,'slit_mul'] == -1:
                    if (slit_array.loc[i,'slit_obj_priority'] > slit_array.loc[i - 2,'slit_obj_priority']) or (slit_array.loc[i - 2,'slit_mul'] == 2):
                        slit_array = expand_slit(slit_array, i, i - 1, csu_params['slitwidth'])
                        slit_array.loc[i - 1,'slit_mul'] = slit_array.loc[i,'slit_mul']

    # Clean up all the Slit Multiple Length numbers and Priorities
    slit_array = clean_up_slit_mul_pri(slit_array)

    # Extend all slits to envelope blanks. After this, every row should be occupied by a slit.
    for j in range(config['num_rows']):
        for i in range(1, len(slit_array) - 1):
            if (slit_array.loc[i,'slit_mul'] == -1 and slit_array.loc[i - 1,'slit_mul'] > 0 and
                    slit_array.loc[i - 1,'slit_obj_priority'] > slit_array.loc[i + 1,'slit_obj_priority']):
                slit_array = expand_slit(slit_array, i-1, i, csu_params['slitwidth'])
                slit_array = clean_up_slit_mul_pri(slit_array)

            if (slit_array.loc[i,'slit_mul'] == -1 and slit_array.loc[i + 1,'slit_mul'] > 0 and
                    slit_array.loc[i + 1,'slit_obj_priority'] > slit_array.loc[i - 1,'slit_obj_priority']):
                slit_array = expand_slit(slit_array, i + 1, i, csu_params['slitwidth'])
                slit_array = clean_up_slit_mul_pri(slit_array)

            if slit_array.loc[i, 'slit_mul'] == -1 and slit_array.loc[i + 1, 'slit_obj_priority'] == slit_array.loc[i - 1, 'slit_obj_priority']:
                if (slit_array.loc[i + 1, 'slit_obj_y'] - csu_params['dead_space'] - (i + 1) * config['single_slit_height'] - 2 * i * csu_params['dead_space']) < 0:
                    slit_array = expand_slit(slit_array, i + 1, i, csu_params['slitwidth'])
                else:
                    slit_array = expand_slit(slit_array, i - 1, i, csu_params['slitwidth'])
                slit_array = clean_up_slit_mul_pri(slit_array)

        slit_array = clean_up_slit_mul_pri(slit_array)

    if slit_array.loc[45,'slit_mul'] == -1 and slit_array.loc[44,'slit_mul'] > 0:
        slit_array = expand_slit(slit_array, 44, 45, csu_params['slitwidth'])
        slit_array = clean_up_slit_mul_pri(slit_array)
    if slit_array.loc[0,'slit_mul'] == -1 and slit_array.loc[1,'slit_mul'] > 0:
        slit_array = expand_slit(slit_array, 1, 0, csu_params['slitwidth'])
        slit_array = clean_up_slit_mul_pri(slit_array)

    # correct the slitnum value for each slit
    for i in range(len(slit_array)):
        multiple = 0
        for j in range(len(slit_array)):
            if slit_array.loc[j,'slit_obj_name'] == slit_array.loc[i,'slit_obj_name']:
                multiple += 1
        slit_array.loc[i, 'slit_mul'] = multiple
    slit_array = clean_up_slit_mul_pri(slit_array)

    # Calculate the length, y-coordinate, and x-coordinate of each slit.
    for i in range(len(slit_array)):
        if slit_array.loc[i, 'slit_mul'] > 0:
            slit_array.loc[i, 'slit_length'] = slit_array.loc[i, 'slit_mul'] * config['single_slit_height'] + (slit_array.loc[i, 'slit_mul'] - 1) * config['overlap_as']
            slit_array.loc[i, 'slit_y'] = (2*csu_params['dead_space'] + csu_params['row_region_height'])*(i + 1/2) - config['csu_height']/2
            slit_array.loc[i, 'slit_x'] = slit_array.loc[i, 'slit_obj_x'] - final_field_center.x   ## TODO: Check this line later

    # Fill in the barPositionArray with the correct values and write it out to the user-specified file.
    bar_position_array = [0]*config['num_rows']*2
    for i in range(len(slit_array)):
        bar_position_array[2*i] = -slit_array.loc[config['num_rows']-1-i,'slit_obj_x'] - math.tan(config['bar_tilt']*math.pi/180)*(slit_array.loc[i,'slit_obj_y'] - slit_array.loc[i,'slit_y']) - csu_params['slitwidth']/2
        bar_position_array[2*i+1] = -slit_array.loc[config['num_rows']-1-i,'slit_obj_x'] - math.tan(config['bar_tilt']*math.pi/180)*(slit_array.loc[i,'slit_obj_y'] - slit_array.loc[i,'slit_y']) + csu_params['slitwidth']/2
    # Write the bar position list to a file
    with open(bar_position_list, 'w') as file:
        for i in range(len(bar_position_array)):
            file.write(f"{bar_position_array[i]}\n")

    # Create a new slit_array2, which is a copy of slit_array, but with no empty slits. Then renumber the slits
    slit_array2 = slit_array[slit_array['slit_mul'] > 0].reset_index(drop=True)  # Filter out empty slits
    slit_array2['slit_number'] = -1
    renumber = 0
    newslitnum = 1
    while renumber < len(slit_array2):
        slit_array2.loc[renumber, 'slit_number'] = newslitnum
        renumber = renumber + slit_array2.loc[renumber, 'slit_mul']
        newslitnum += 1

    # Make slit_array3, which is simply the slit information. Each slit
    # is only listed once, not in multiples. The slit length reflects
    # if the slit is a single, double, triple, etc.
    slit_array3 = slit_array2[slit_array2['slit_number'] > 0].reset_index(drop=True)

    # Give slitArray3 correct slitY values and "close" slitX values. Later,
    # the slitX will be modified to account for bar tilt so that the object
    # is placed in the horizontal center of the slit, regardless of its
    # vertical displacement from center.
    slit_array3['slit_y'] += (slit_array3['slit_mul'] - 1) * (csu_params['dead_space']+csu_params['row_region_height'] / 2)
    slit_array3['slit_x'] = slit_array3['slit_obj_x']

    # Rotate the slits in the CSU plane backwards by the Position Angle.
    theta = -final_pa * math.pi / 180
    x_old = slit_array3['slit_x']
    y_old = slit_array3['slit_y']
    slit_array3['slit_x'] = x_old * math.cos(theta) - y_old * math.sin(theta)
    slit_array3['slit_y'] = x_old * math.sin(theta) + y_old * math.cos(theta)

    x_obj_old = slit_array3['slit_obj_x']
    y_obj_old = slit_array3['slit_obj_y']
    slit_array3['slit_obj_x'] = x_obj_old * math.cos(theta) - y_obj_old * math.sin(theta)
    slit_array3['slit_obj_y'] = x_obj_old * math.sin(theta) + y_obj_old * math.cos(theta)

    slit_array3['wcs_x'] = slit_array3['slit_x'] + final_field_center.x - math.tan(config['bar_tilt'] * math.pi / 180)*(slit_array3['slit_obj_y'] - slit_array3['slit_y'])
    slit_array3['wcs_y'] = slit_array3['slit_y'] + final_field_center.y

    slit_array3 = slit_xy_to_radec(slit_array3, final_field_center)
    slit_array3['target_location'] = slit_array3['slit_obj_y'] - slit_array3['slit_y']
    slit_array3['slit_obj_wcs_x'] = slit_array3['slit_obj_x'] + final_field_center.x
    slit_array3['slit_obj_wcs_y'] = slit_array3['slit_obj_y'] + final_field_center.y
    slit_array3 = slit_objxy_to_radec(slit_array3, final_field_center)
    slit_array3['slit_number'] = len(slit_array3) - slit_array3['slit_number'] + 1  # Reverse the numbering to match the original slit numbering

    return slit_array3


def write_out_slit_list(output_slit_file, slit_array, slit_width):
    """
    Write the slit list to a file.
    """
    with open(output_slit_file, 'w') as file:
        for i in range(len(slit_array)):
            slit = slit_array.loc[len(slit_array) - i - 1]
            ra_hms = slit.ra_hms.split(':')
            dec_hms = slit.dec_dms.split(':')
            obj_ra_hms = slit.obj_ra_hms.split(':')
            obj_dec_hms = slit.obj_dec_dms.split(':')
            file.write(f"{slit.slit_number}\t{ra_hms[0]}\t{ra_hms[1]}\t{float(ra_hms[2]):.2f}\t{dec_hms[0]}\t{dec_hms[1]}\t{float(dec_hms[2]):.2f}\t"
                       f"{slit_width:.2f}\t{slit.slit_length:.2f}\t{slit.slit_obj_name}\t{slit.slit_obj_priority:.2f}\t{slit.target_location:.2f}\t"
                       f"{obj_ra_hms[0]}\t{obj_ra_hms[1]}\t{float(obj_ra_hms[2]):.2f}\t{obj_dec_hms[0]}\t{obj_dec_hms[1]}\t{float(obj_dec_hms[2]):.2f}\n")


def print_regions_from_slit_array(slit_array, config, csu_params, field_center, fieldcenterra, fieldcenterdec, position_angle, output_reg_file):
    from decimal import Decimal

    old_red_box_x = field_center.x + csu_params['xcenter']
    old_red_box_y = field_center.y
    red_box_csu_x = old_red_box_x - field_center.x
    red_box_csu_y = old_red_box_y - field_center.y
    theta = -position_angle * math.pi / 180
    red_box_csu_x_rotated = red_box_csu_x * math.cos(theta) - red_box_csu_y * math.sin(theta)
    red_box_csu_y_rotated = red_box_csu_x * math.sin(theta) + red_box_csu_y * math.cos(theta)
    red_box_wcs_x_rotated = red_box_csu_x_rotated + field_center.x
    red_box_wcs_y_rotated = red_box_csu_y_rotated + field_center.y

    try:
        with open(output_reg_file, 'w') as file:
            file.write("global color=green font=\"helvetica 10 normal\" "
                       "select=1 highlite=0 edit=0 move=0 delete=1 "
                       "include=1 fixed=0 source \nfk5\n")
            file.write(f"circle({fieldcenterra},{fieldcenterdec},{config['csu_fp_radius']}\")\t"
                       "# color=yellow font=\"helvetica 18 normal\" text={Keck Focal Plane}\n")
            file.write(f"box({(field_center.x / math.cos(field_center.y * math.pi / 180 / 3600) / 3600):.5f},"
                       f"{(field_center.y / 3600):.5f},"
                       f"{(config['csu_width']):.5f}\","
                       f"{(config['csu_height']):.5f}\","
                       f"{(position_angle):.3f})\t"
                       "# color=magenta font=\"helvetica 18 normal\" text={CSU Plane}\n")
            file.write(f"box({(red_box_wcs_x_rotated / math.cos(field_center.y * math.pi / 180 / 3600) / 3600):.5f},"
                       f"{(red_box_wcs_y_rotated / 3600):.5f},"
                       f"{(csu_params['xrange']):.5f}\","
                       f"{(config['csu_height']):.5f}\","
                       f"{(position_angle):.3f})\t# color=red\n")

            for i in range(len(slit_array)):
                slit = slit_array.loc[i]
                file.write(f"circle({(slit['slit_obj_wcs_x'] / math.cos(field_center.y * math.pi / 180 / 3600) / 3600):.5f},"
                           f"{(slit['slit_obj_wcs_y'] / 3600):.5f},0.5\")\t"
                           f"# text={{ {slit['slit_obj_name']} }}\n")
                file.write(f"box({(slit['wcs_x'] / math.cos(field_center.y * math.pi / 180 / 3600) / 3600):.5f},"
                           f"{(slit['wcs_y'] / 3600):.5f},"
                           f"{(csu_params['slitwidth']):.5f}\","
                           f"{(slit['slit_length']):.5f}\","
                           f"{(config['bar_tilt'] + position_angle):.3f})\t"
                           f"# text={{Slit# {slit['slit_number']} }}\n")
    except Exception as error:
        print("Error writing to file:", error)

    print(f"The corresponding SAOImage Ds9 region file is: {output_reg_file}")







