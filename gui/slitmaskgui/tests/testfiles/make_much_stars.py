import numpy as np
from astropy.coordinates import SkyCoord
import astropy.units as u

def generate_random_center():

    ra_random = np.random.uniform(0, 360)  # RA in degrees
    dec_random = np.random.uniform(-90, 90)  # Dec in degrees

    random_coord = SkyCoord(ra=ra_random, dec=dec_random, unit='deg', frame='icrs')

    ra_ = random_coord.ra.to_string(unit='hour', sep=' ', precision=2)
    dec_ = random_coord.dec.to_string(unit='deg', sep=' ', precision=2)
    center = f"{ra_} {dec_}"
    print(center)
    center_coord = SkyCoord(ra=ra_, dec=dec_, unit=(u.hourangle,u.deg), frame='icrs')
    return center_coord

center = generate_random_center()


def make_bunch_o_stars(center, radius, num_stars):
    star_list = []
    center_ra = center.ra.deg
    center_dec = center.dec.deg


    for _ in range(num_stars):
        # Generate a random offset within a circle (uniform in area)

        rand_radius = radius * np.sqrt(np.random.uniform(0, 1))  # sqrt for uniform density
        rand_angle = np.random.uniform(0, 2 * np.pi)

        # Offset in RA/Dec (approximation valid for small radius)
        delta_ra = (rand_radius * np.cos(rand_angle)) / np.cos(np.deg2rad(center_dec))
        delta_dec = rand_radius * np.sin(rand_angle)

        # Calculate new coordinates
        new_ra = center_ra + delta_ra
        new_dec = center_dec + delta_dec

        # Wrap RA to [0, 360) and clamp Dec to [-90, 90]
        new_ra = new_ra % 360
        new_dec = max(min(new_dec, 90), -90)

        star_coord = SkyCoord(ra=new_ra * u.deg, dec=new_dec * u.deg, frame='icrs')

        ra_str = star_coord.ra.to_string(unit='hour', sep=' ', precision=2, pad=True)
        dec_str = star_coord.dec.to_string(unit='deg', sep=' ', precision=2, alwayssign=True)

        priority = int(np.random.uniform(1,2000))
        star_list.append({"ra":ra_str, "dec": dec_str,"priority":priority})
    return star_list
    
stars = make_bunch_o_stars(center,radius=10/60,num_stars=100)