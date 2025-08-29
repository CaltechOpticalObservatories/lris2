PLATE_SCALE = 0.7272 #(mm/arcsecond) on the sky
CSU_HEIGHT = PLATE_SCALE*60*10 #height of csu in mm (height is 10 arcmin)
CSU_WIDTH = PLATE_SCALE*60*5 #width of the csu in mm (widgth is 5 arcmin)
MM_TO_PIXEL = 1

print(PLATE_SCALE)
print(CSU_HEIGHT)
print(CSU_WIDTH)

thing = PLATE_SCALE*7.6
print(thing)

scene_width = (CSU_WIDTH+CSU_WIDTH/1.25) * MM_TO_PIXEL
scene_height = CSU_HEIGHT * MM_TO_PIXEL

print(scene_width,scene_height,scene_width/scene_height)
print("scene height:",scene_height/PLATE_SCALE/60)
print("scene width:",scene_width/PLATE_SCALE/60)
