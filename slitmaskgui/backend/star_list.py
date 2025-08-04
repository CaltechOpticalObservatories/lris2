"""
This will convert the Apparent RA and Dec to milimeters and give a position in milimeters for the blah blah blah
"""


PLATE_SCALE = 0.7272 #(mm/arcsecond) on the sky
CSU_HEIGHT = PLATE_SCALE*60*10 #height of csu in mm (height is 10 arcmin)
CSU_WIDTH = PLATE_SCALE*60*5 #width of the csu in mm (widgth is 5 arcmin)


from astropy.coordinates import SkyCoord, Angle
import astropy.units as u
import pandas as pd
import numpy as np
from slitmaskgui.input_targets import TargetList
from slitmaskgui.backend.mask_gen import SlitMask
import json
import os


#Ra and Dec --> angle Degrees



#dimensions are 213.76 mm x 427.51 mm I think but have no clue

#I think the height, width = 10', 5' both in arcminutes
#formula for it in arcseconds: 1/PLATE_SCALE*height

#right ascension is counterclockwise relative to the north pole
#declination is up

#I will go through a json payload and send back something that 
#the slit row display, target list display, the slit mask display, and the CSU can use

#the input_targets function will give us a json payload
"""
I currently don't factor in PA because I don't know how to
I also assume that RA and DEC are aligned with the x and y axis
while that probably isn't right i'll just get something down for now
"""

class StarList:
    #with auto run you can select if the json is complete or not already
    #this means that if you have a complete list of all the stars as if it rand thorough this class, then you can select auto run as false
    #then you can use the send functions without doing a bunch of computation
    def __init__(self,payload,ra,dec,slit_width=0,pa=0,auto_run=True,use_center_of_priority=False): 
        self.payload = json.loads(payload)
        ra_coord,dec_coord = ra, dec
        if use_center_of_priority:
            ra_coord, dec_coord =self.find_center_of_priority()
        self.center = SkyCoord(ra=ra_coord,dec=dec_coord,unit=(u.hourangle,u.deg))

        self.slit_width = slit_width
        self.pa = pa

        if auto_run:
            #self.calc_mask()
            self.payload = self.calc_mask(self.payload)
    
    def calc_mask(self,all_stars): 
        slit_mask = SlitMask(all_stars,center=self.center, slit_width= self.slit_width, pa= self.pa)
            
        return json.loads(slit_mask.return_mask())

    def export_mask_config(self,file_path):
        # file_path = f'{os.getcwd()}/{mask_name}.json'
        with open(file_path,'w') as f:
            json.dump(self.payload,f,indent=4)
        # return file_path
    def send_mask(self, mask_name="untitled"):
        return self.payload
    

    def send_target_list(self):
        return [[x["name"],x["priority"],x["vmag"],x["ra"],x["dec"],x["center distance"]] for x in self.payload]


    def send_interactive_slit_list(self):
        #have to convert it to dict {bar_num:(position,star_name)}
        #imma just act rn like all the stars are in sequential order
        #I am going to have an optimize function that actually gets the right amount of stars with good positions
        #its going to also order them by bar
        total_pixels = 252 
        
        slit_dict = {
            i: (240 + (obj["x_mm"] / CSU_WIDTH) * total_pixels, obj["bar_id"], obj["name"]) 
            for i, obj in enumerate(self.payload[:72])
            if "bar_id" in obj
            }

        return slit_dict
    def send_list_for_wavelength(self):
        old_ra_dec_list = [[x["bar_id"],x["ra"],x["dec"]]for x in self.payload]
        ra_dec_list =[]
        [ra_dec_list.append(x) for x in old_ra_dec_list if x not in ra_dec_list]
        return ra_dec_list
    
    def send_row_widget_list(self):
        #the reason why the bar id is plus 1 is to transl
        sorted_row_list = sorted(
            ([obj["bar_id"]+1, obj["x_mm"], self.slit_width] 
            for obj in self.payload[:72] if "bar_id" in obj),
            key=lambda x: x[0]
            )
        return sorted_row_list
    def find_center_of_priority(self):
        """              ∑ coordinates * priority
        CoP coordinate = ------------------------
                                ∑ priority
        """
        star_list = [[SkyCoord(obj["ra"],obj["dec"], unit=(u.hourangle, u.deg), frame='icrs'),obj["priority"]] for obj in self.payload]
        ra_numerator, dec_numerator = 0,0
        for x in star_list:
            ra = float(Angle(x[0].ra).wrap_at(180 * u.deg).deg)
            dec = float(np.float64(x[0].dec.deg))
            priority = float(x[1])
            ra_numerator += priority*ra
            dec_numerator += priority*dec
        
        denominator_list = [float(star_list[x][1]) for x in range(len(star_list))]
        sum_denominator = sum(denominator_list)
        ra = Angle((ra_numerator/sum_denominator)*u.deg).to_string(unit=u.hourangle, sep=' ', precision=2, pad=True)
        dec = Angle((dec_numerator/sum_denominator)*u.deg).to_string(unit=u.deg, sep=' ', precision=2, pad=True,alwayssign=True)

        return ra, dec
    
    def generate_skyview(self):
        return "temp"
        
        


