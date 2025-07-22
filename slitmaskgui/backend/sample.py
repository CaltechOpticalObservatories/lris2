from astroquery.gaia import Gaia
from astropy.coordinates import SkyCoord
import astropy.units as u
import random

def query_gaia_starlist_rect(ra_center, dec_center, width_arcmin=5, height_arcmin=10, n_stars=100, output_file='gaia_starlist.txt'):
    # Convert center to SkyCoord
    center = SkyCoord(ra_center, dec_center, unit=(u.deg, u.deg), frame='icrs')


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

            line = f"{name:<15} {int(ra_h):02d} {int(ra_m):02d} {ra_s:05.2f} {int(dec_d):+03d} {int(dec_m):02d} {abs(dec_s):04.1f} 2000.0 vmag={row['phot_g_mean_mag']:.2f} priority={random.randint(1,2000)}\n"
            f.write(line)

    # Output center info
    print("✅ Starlist generated!")
    print(f"RA center  = {center.ra.to_string(u.hour, sep=':')}")
    print(f"Dec center = {center.dec.to_string(sep=':')}")
    print(f"Saved to   = {output_file}")

# Example call — replace RA/Dec with your actual center