'''
this generates the slit mask with the greatest total priority
if stars are selected as must have then they must be there
'''

PLATE_SCALE = 0.7272 #(mm/arcsecond) on the sky
CSU_HEIGHT = PLATE_SCALE*60*10 #height of csu in mm (height is 10 arcmin)
CSU_WIDTH = PLATE_SCALE*60*5 #width of the csu in mm (widgth is 5 arcmin)
TOTAL_BAR_PAIRS = 72



class SlitMask:
    def __init__(self,stars):
        self.stars = stars

    def calc_y_pos(self):
        #this will calculate the bar and x of every star and remove any that do not fit in position
        for obj in self.stars:
            y = obj["y_mm"]
            y_step = CSU_HEIGHT/TOTAL_BAR_PAIRS

            if y <= 0:
                bar_id = TOTAL_BAR_PAIRS/2+round(abs(y/y_step))
            elif y > 0: 
                bar_id = TOTAL_BAR_PAIRS/2 -round(abs(y/y_step))

            obj["bar id"] = int(bar_id)


        return self.stars
    
    # def check_if_within(x,y):
    #     if y > CSU_HEIGHT/2:
    #         return "delete"
    #     elif x > CSU_WIDTH/2:
    #         return "delete"
    #     return "save"
        #the delete and save is a temporary string that would tell another function to delete a star if it returned delete
        #and save the star if it returned save
        #this is just to make sure that all the stars that are given in the starlist are withing the boundaries
        #I am going to change this to do it when calculating the y_pos (will check if within all PA)
    
    def generate_pa(self):
        pass

    def optimize(self):
        #optimizes list of stars with total highest priority. 
        pass
    
    def make_mask(self):
        #will return a list that will be used by the csu to configure the slits 
        #this could also be used by the interactive slit mask
        pass