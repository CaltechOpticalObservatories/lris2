'''
this generates the slit mask with the greatest total priority
if stars are selected as must have then they must be there
'''

PLATE_SCALE = 0.7272 #(mm/arcsecond) on the sky
CSU_HEIGHT = PLATE_SCALE*60*10 #height of csu in mm (height is 10 arcmin)
CSU_WIDTH = PLATE_SCALE*60*5 #width of the csu in mm (widgth is 5 arcmin)
TOTAL_BAR_PAIRS = 72
print(CSU_HEIGHT/TOTAL_BAR_PAIRS)

class SlitMask:
    def __init__(self,stars):
        self.stars = stars

    def calc_y_pos(self):
        #this will calculate the bar and x of every star and remove any that do not fit in position
        for i in self.stars:
            y = i["y_mm"]
            y_step = CSU_HEIGHT/TOTAL_BAR_PAIRS

            bar_id = round(y/y_step)

            i["bar id"] = bar_id

        return self.stars

    def optimize(self):
        #optimizes list of stars with total highest priority. 
        pass
    
    def make_mask(self):
        #will return a list that will be used by the csu to configure the slits 
        #this could also be used by the interactive slit mask
        pass