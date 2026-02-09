import numpy as np
from astropy.coordinates import SkyCoord
import astropy.units as u
from numba import jit

@jit
def transform_coordinates(x, y, center_x, center_y, pa, extra_x=0, extra_y=0):
    """
    Transform coordinates (x, y) by rotating around the center (center_x, center_y) by position angle pa.
    :param x: x-coordinate of the point.
    :param y: y-coordinate of the point.
    :param center_x: x-coordinate of the center.
    :param center_y: y-coordinate of the center.
    :param pa: position angle in degrees.
    :return: transformed x and y coordinates.
    """
    theta = np.radians(pa)  # Convert PA from degrees to radians
    cos_pa = np.cos(theta)
    sin_pa = np.sin(theta)
    x_old = x - center_x
    y_old = y - center_y
    new_x = x_old * cos_pa - y_old * sin_pa + extra_x
    new_y = x_old * sin_pa + y_old * cos_pa + extra_y
    return new_x, new_y

@jit
def inCircle(x, y, center_x, center_y, radius):
    """
    Check if a point (x, y) is inside a circle defined by center (center_x, center_y) and radius.
    :param x: x-coordinate of the point.
    :param y: y-coordinate of the point.
    :param center_x: x-coordinate of the circle center.
    :param center_y: y-coordinate of the circle center.
    :param radius: radius of the circle.
    :return: True if the point is inside the circle, False otherwise.
    """
    return np.sqrt(np.power(np.abs(x - center_x),2) + np.power(np.abs(y - center_y),2)) < radius

class Coordinate:
    def __init__(self, ra, dec):
        if isinstance(ra, str) and isinstance(dec, str) and ':' in ra and ':' in dec:
            self.coord = SkyCoord(ra=ra, dec=dec, unit=(u.hourangle, u.deg))
            self.ra = self.coord.ra.deg
            self.dec = self.coord.dec.deg
        else:
            self.ra = ra
            self.dec = dec
            self.coord = SkyCoord(ra=ra, dec=dec, unit=(u.deg, u.deg))
        self.to_xy(reference_dec=None)

    def to_radec(self):
        # Convert the x and y coordinates in arcseconds back to RA/Dec coordinates.
        self.dec = self.y / 3600.  # Convert arcseconds to degrees
        dec_rad = np.radians(self.dec)  # Convert degrees to radians
        self.ra = self.x / (3600. * np.cos(dec_rad))  # Convert arcseconds to degrees (15 degrees per hour)

    def to_xy(self, reference_dec=None):
        self.y = self.dec * 3600.  # Convert declination to arcseconds
        if reference_dec is None:
            reference_dec = self.dec
        dec_rad = np.radians(reference_dec)  # Convert declination to radians
        self.x = np.cos(dec_rad) * (self.ra * 3600.)

    def do_ra_coord_wrap(self):
        hms = self.coord.ra.hms
        if hms.h == 0:
            hms.h = 12
        elif hms.h == 23:
            hms.h = 11
        self.coord = SkyCoord(ra=f"{hms.h}:{hms.m}:{hms.s}", dec=self.coord.dec.deg, unit=(u.hourangle, u.deg))
        self.ra = self.coord.ra.deg
        self.dec = self.coord.dec.deg
        self.to_xy(reference_dec=None)

class fieldCenter(Coordinate):
    def __init__(self, ra, dec):
        super().__init__(ra, dec)