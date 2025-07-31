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



#for some reason I am splitting up everything into their own for statements
#should be able to put this all into one for statement but I don't wanna think about that rnß
class SlitMask:
    def __init__(self,stars):
        self.stars = stars
        self.calc_y_pos()
        self.optimize()

    def calc_y_pos(self):
        #this will calculate the bar and x of every star and remove any that do not fit in position
        initial_len = len(self.stars)
        for obj in self.stars:
            y = obj["y_mm"]
            x = obj["x_mm"]
            y_step = CSU_HEIGHT/TOTAL_BAR_PAIRS

            if y <= 0:
                bar_id = TOTAL_BAR_PAIRS/2+round(abs(y/y_step))
            elif y > 0: 
                bar_id = TOTAL_BAR_PAIRS/2 -round(abs(y/y_step))
            if self.check_if_within(x,y):
                obj["bar_id"] = int(bar_id)
            else:
                self.stars.remove(obj)


    
    def check_if_within(self,x,y):
        return abs(x) <= CSU_WIDTH / 2 and abs(y) <= CSU_HEIGHT / 2
        #the delete and save is a temporary string that would tell another function to delete a star if it returned delete
        #and save the star if it returned save
        #this is just to make sure that all the stars that are given in the starlist are withing the boundaries
        #I am going to change this to do it when calculating the y_pos (will check if within all PA)
    
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
    # Get the star with the highest priority in this group
            highest_priority_star = max(group, key=lambda x: x["priority"])
            highest_priority_stars.append(highest_priority_star)
        self.stars = highest_priority_stars
        
            
    

    def return_mask(self):
        return json.dumps(self.stars)

    
    def make_mask(self):
        #will return a list that will be used by the csu to configure the slits 
        #this could also be used by the interactive slit mask
        pass

