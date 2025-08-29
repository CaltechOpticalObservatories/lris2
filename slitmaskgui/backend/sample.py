from astroquery.gaia import Gaia
from astropy.coordinates import SkyCoord
import astropy.units as u
import random
import numpy as np


def query_gaia_starlist_rect(ra_center, dec_center, width_arcmin=5, height_arcmin=10, n_stars=100, output_file='gaia_starlist.txt'):
    # Convert center to SkyCoord
    center = SkyCoord(ra_center, dec_center, unit=(u.hourangle, u.deg), frame='icrs')



    radius = height_arcmin
    job = Gaia.cone_search_async(center, radius=radius*u.arcmin)
    results = job.get_results()

    # Write starlist
    with open(output_file, 'w') as f:
        f.write(f"# Starlist centered at RA={center.ra.to_string(u.hour, sep=':')}, Dec={center.dec.to_string(sep=':')}\n")
        for i, row in enumerate(results):
            name = f"Gaia_{i+1:03d}"
            coord = SkyCoord(ra=row['ra']*u.deg, dec=row['dec']*u.deg)
            ra_h, ra_m, ra_s = coord.ra.hms
            sign, dec_d, dec_m, dec_s = coord.dec.signed_dms
            dec_d = sign * dec_d

            parallax = row['parallax']  # in mas
            app_mag = row['phot_g_mean_mag']

            if parallax > 0:
                distance_pc = 1000.0 / parallax
                abs_mag = app_mag - 5 * (np.log10(distance_pc) - 1)
            else:
                abs_mag = float(0)

            line = f"{name:<15} {int(ra_h):02d} {int(ra_m):02d} {ra_s:05.2f} {int(dec_d):+03d} {int(dec_m):02d} {abs(dec_s):04.1f} 2000.0 vmag={row['phot_g_mean_mag']:.2f} priority={abs_mag:.2f}\n"
            f.write(line)
    # Output center info
    print("Starlist Generated")


# Example call — replace RA/Dec with your actual center
run = False  
if run:
    ra = "10 20 10.00"
    dec = "-10 04 00.10"
    query_gaia_starlist_rect(
        ra_center=ra,              # RA in degrees
        dec_center=dec,               # Dec in degrees
        width_arcmin=5,
        height_arcmin=10,
        n_stars=104,
        output_file='gaia_starlist.txt'
    )