"""
This is the interactive slit mask feature. It will interact with the bar table on the left.
when you click the bar on the left then the image will display which row that is
additionally It will also interact with the target list
it will display where the slit is place and what stars will be shown
"""

from slitmaskgui.mask_widgets.mask_objects import *
from itertools import groupby
import logging
import numpy as np
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QGraphicsScene,
    QGraphicsRectItem,
    QGraphicsItemGroup,
)

#will have another thing that will dispaly all the stars in the sky at the time
PLATE_SCALE = 0.7272 #(mm/arcsecond) on the sky
CSU_HEIGHT = PLATE_SCALE*60*10 #height of csu in mm (height is 10 arcmin)
CSU_WIDTH = PLATE_SCALE*60*5 #width of the csu in mm (widgth is 5 arcmin)
MM_TO_PIXEL = 1 #this is a mm to pixel ratio, it is currently just made up

logger = logging.getLogger(__name__)


class interactiveSlitMask(QWidget):
    row_selected = pyqtSignal(int,name="row selected")
    select_star = pyqtSignal(str)
    new_slit_positions = pyqtSignal(list)
    
    def __init__(self):
        super().__init__()

        #--------------------definitions-----------------------
        logger.info("slit_view: doing definitions")
        self.scene_width = (CSU_WIDTH+CSU_WIDTH/1.25) * MM_TO_PIXEL
        scene_height = CSU_HEIGHT * MM_TO_PIXEL
        self.scene = QGraphicsScene(0,0,self.scene_width,scene_height)

        xcenter_of_image = self.scene.sceneRect().center().x()

        self.mask_name_title = QLabel(f'MASK NAME: None')
        self.center_title = QLabel(f'CENTER: None')
        self.pa_title = QLabel(f'PA: None')
        
        bar_length = self.scene_width
        self.bar_height = CSU_HEIGHT/72#PLATE_SCALE*8.6
        padding = 0

        for i in range(72):
            temp_rect = interactiveBars(0,i*self.bar_height+padding,this_id=i,bar_width=self.bar_height,bar_length=bar_length)
            temp_slit = interactiveSlits(self.scene_width/2,self.bar_height*i+padding)
            self.scene.addItem(temp_rect)
            self.scene.addItem(temp_slit)

        fov = FieldOfView(x=xcenter_of_image/2,y=padding)
        new_center = fov.boundingRect().center().x()
        new_x = xcenter_of_image-new_center
        fov.setPos(new_x,0)
        self.scene.addItem(fov)

        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        self.view = CustomGraphicsView(self.scene)
        self.view.setContentsMargins(0,0,0,0)

        #-------------------connections-----------------------
        logger.info("slit_view: establishing connections")
        self.scene.selectionChanged.connect(self.row_is_selected)
        self.scene.selectionChanged.connect(self.get_star_name_from_row)


        #------------------------layout-----------------------
        logger.info("slit_view: defining layout")
        top_layout = QHBoxLayout()
        main_layout = QVBoxLayout()
        

        top_layout.addWidget(self.mask_name_title,alignment=Qt.AlignmentFlag.AlignHCenter)
        top_layout.addWidget(self.center_title,alignment=Qt.AlignmentFlag.AlignHCenter)
        top_layout.addWidget(self.pa_title,alignment=Qt.AlignmentFlag.AlignHCenter)
        main_layout.addLayout(top_layout)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.addWidget(self.view)

        self.setLayout(main_layout)
        #-------------------------------------------
    def sizeHint(self):
        return QSize(550,620)
    def toggle_connection(self,connect:bool):
        #---------------reconnect connections---------------
        if connect:
            self.scene.selectionChanged.connect(self.row_is_selected)
            self.scene.selectionChanged.connect(self.get_star_name_from_row)
        else:
            self.scene.selectionChanged.disconnect(self.row_is_selected)
            self.scene.selectionChanged.disconnect(self.get_star_name_from_row)


    @pyqtSlot(int,name="row selected")
    def select_corresponding_row(self,row):
        logger.info("slit_view: method select_correspond_row called")
        
        all_bars = [
            item for item in reversed(self.scene.items())
            if isinstance(item, QGraphicsRectItem)
        ]
        
        self.scene.clearSelection()
        # self.toggle_connection(False)
        if 0 <= row <len(all_bars):
            self.row_num = row
            all_bars[self.row_num].setSelected(True)
        # self.toggle_connection(True)

    @pyqtSlot(str)
    def get_row_from_star_name(self,name):
        logger.info("slit_view: method get_row_from_star_name called")
        all_stars = [
            item for item in reversed(self.scene.items())
            if isinstance(item, QGraphicsItemGroup)
        ]
        all_bars = [
            item for item in reversed(self.scene.items())
            if isinstance(item, interactiveBars)
        ]
        
        self.scene.clearSelection()
        for i in range(len(all_stars)):
            if all_stars[i].get_star_name() == name:
                bar_id = int(all_stars[i].get_bar_id())
                self.toggle_connection(False)
                all_bars[bar_id].setSelected(True)
                self.toggle_connection(True)
                
    def get_star_name_from_row(self):
        try:
            row_selected = [x.check_id() for x in self.scene.selectedItems()] 
            selected_star = [
                item.get_star_name() for item in reversed(self.scene.items())
                if isinstance(item, interactiveSlits)and item.get_bar_id() in row_selected
            ]
            if selected_star:
                logger.info(f"slit_view: method get_star_name_from_row called, selected star: {selected_star[0]}")
                self.select_star.emit(selected_star[0])
        except:
            pass
            

    def row_is_selected(self):
        try:
            row_num = self.scene.selectedItems()[0].check_id()
            logger.info(f"slit_view: method row_is_selected called, row_num: {row_num}")
            self.row_selected.emit(row_num)
        except:
            pass

    @pyqtSlot(dict,name="targets converted")
    def change_slit_and_star(self,pos):
        logger.info("slit_view: method change_slit_and_star called")
        #will get it in the form of {1:(position,star_names),...}
        self.position = list(pos.values())
        new_items = []
        x_center = self.scene.itemsBoundingRect().center().x()
        slits_to_replace = [
            item for item in reversed(self.scene.items())
            if isinstance(item, QGraphicsItemGroup)
        ]
        for num, item in enumerate(slits_to_replace):
            try:
                self.scene.removeItem(item)

                x_pos, bar_id, name = self.position[num]
                
                new_item = interactiveSlits(x_center+x_pos, bar_id*self.bar_height, name) #7 is the margin at the top 
                new_items.append(new_item)
            except:
                continue
        #item_list.reverse()
        for item in new_items:
            self.scene.addItem(item)
        self.emit_slit_positions(new_items,x_center)
        self.view = QGraphicsScene(self.scene)
    @pyqtSlot(np.ndarray, name="update labels")
    def update_name_center_pa(self,info):
        mask_name, center, pa = info[0], info[1], info[2] #the format of info is [mask_name,center,pa]
        if type(center) is tuple():
            center = str(center[0])+str(center[1])
        self.mask_name_title.setText(f'MASK NAME: {mask_name}')
        self.center_title.setText(f'CENTER: {center}')
        self.pa_title.setText(f'PA: {pa}')
    
    def emit_slit_positions(self,slits,x_center):
        slit_positions = [(x.x_pos,x.y_pos,x.star_name) for x in slits] #-(x_center-x.xpos) gets distance from center where left is negative
        self.new_slit_positions.emit(slit_positions)





# Define the coordinates (RA, Dec) - replace with your values

