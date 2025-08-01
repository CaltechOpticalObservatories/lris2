'''
this generates the slit mask with the greatest total priority
if stars are selected as must have then they must be there
'''

PLATE_SCALE = 0.7272 #(mm/arcsecond) on the sky
CSU_HEIGHT = PLATE_SCALE*60*10 #height of csu in mm (height is 10 arcmin)
CSU_WIDTH = PLATE_SCALE*60*5 #width of the csu in mm (widgth is 5 arcmin)
TOTAL_BAR_PAIRS = 72

from itertools import groupby
import json
from astropy.coordinates import SkyCoord
import astropy.units as u
import numpy as np


#for some reason I am splitting up everything into their own for s©tatements
#should be able to put this all into one for statement but I don't wanna think about that rnß
class SlitMask:
    def __init__(self,stars,center,slit_width=0,pa=0,max_slit_length=3):
        self.stars = stars
        self.center = center
        self.slit_width = slit_width
        self.pa = pa
        self.calc_y_pos()
        self.calc_bar_id()
        self.optimize()
        self.lengthen_slits(max_slit_length)

    def calc_y_pos(self):
        for obj in self.stars:
            star = SkyCoord(obj["ra"],obj["dec"], unit=(u.hourangle, u.deg), frame='icrs')
            separation = self.center.separation(star)  # returns an angle
            obj["center distance"] = float(separation.to(u.arcmin).value)

            delta_ra = (star.ra - self.center.ra).to(u.deg) #from center
            delta_dec = (star.dec - self.center.dec).to(u.arcsec) #from center

            if delta_ra.value > 180:  # If RA difference exceeds 180 degrees, wrap it
                delta_ra -= 360 * u.deg
            elif delta_ra.value < -180:
                delta_ra += 360 * u.deg

            delta_ra = delta_ra.to(u.arcsec)
            delta_ra_proj = delta_ra * np.cos(self.center.dec.radian) # Correct for spherical distortion
                # Convert to mm
            x_mm = float(delta_ra_proj.value * PLATE_SCALE)
            y_mm = float(delta_dec.value * PLATE_SCALE)

            obj["x_mm"] = x_mm
            obj["y_mm"] = y_mm

    def calc_bar_id(self):
        #this will calculate the bar and x of every star and remove any that do not fit in position
        for obj in self.stars:
            y, x = obj["y_mm"], obj["x_mm"]
            y_step = CSU_HEIGHT/TOTAL_BAR_PAIRS

            bar_id = TOTAL_BAR_PAIRS/2+round(abs(y/y_step)) if y<=0 else TOTAL_BAR_PAIRS/2 -round(abs(y/y_step))

            if self.check_if_within(x,y):
                obj["bar_id"] = int(bar_id)
            else:
                self.stars.remove(obj)

    
    def check_if_within(self,x,y):
        return abs(x) <= CSU_WIDTH / 2 and abs(y) <= CSU_HEIGHT / 2
    
    def find_center_of_priority(self):
        """              ∑ coordinates *priority
        CoP coordinate = ------------------------
                                ∑ priority
        """
        pass
    
    def generate_pa(self):
        pass

    def optimize(self):
        #optimizes list of stars with total highest priority. 
        #I could probably do some recursive function right here
        #rows is a list with all the dictionaries

        sorted_stars = sorted(
            [x for x in self.stars if "bar_id" in x],
            key=lambda x:(x["bar_id"],x["priority"])
            )
        highest_priority_stars = []
        for _, group in groupby(sorted_stars, key=lambda x: x["bar_id"]):
            highest_priority_star = max(group, key=lambda x: x["priority"])
            highest_priority_stars.append(highest_priority_star)
        self.stars = highest_priority_stars
    
    def lengthen_slits(self,max_length=3):
        index = 0
        while index < len(self.stars):
            current_bar_id = self.stars[index]["bar_id"]
            try:
                slit_diff = self.stars[index+1]["bar_id"] - current_bar_id
            except IndexError:
                slit_diff = 72 - current_bar_id
            slit_diff = slit_diff if slit_diff < max_length else max_length

            if slit_diff > 1:
                long_slit_list = [{**self.stars[index],"bar_id":current_bar_id+x} for x in range(slit_diff)]
                self.stars[index+1:index+1] = long_slit_list
                index += slit_diff
            index += 1
            
        
    def return_mask(self):
        return json.dumps(self.stars)
    
    def make_mask(self):
        #will return a list that will be used by the csu to configure the slits 
        #this could also be used by the interactive slit mask
        pass

