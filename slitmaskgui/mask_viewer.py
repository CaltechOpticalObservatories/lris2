"""
This is the interactive slit mask feature. It will interact with the bar table on the left.
when you click the bar on the left then the image will display which row that is
additionally It will also interact with the target list
it will display where the slit is place and what stars will be shown
"""


import matplotlib.pyplot as plt
import logging
import numpy as np
from astroquery.gaia import Gaia
from astropy.coordinates import SkyCoord
import astropy.units as u
import matplotlib.pyplot as plt
from astropy.wcs import WCS
from astropy.io import fits
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal, QSize
from PyQt6.QtGui import QBrush, QPen, QPainter, QColor, QFont, QTransform
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsRectItem,
    QGraphicsLineItem,
    QGraphicsTextItem,
    QGraphicsItemGroup,
    QSizePolicy,
    QSizeGrip,
    QTabWidget,
    QComboBox


)

#will have another thing that will dispaly all the stars in the sky at the time
PLATE_SCALE = 0.7272 #(mm/arcsecond) on the sky
CSU_HEIGHT = PLATE_SCALE*60*10 #height of csu in mm (height is 10 arcmin)
CSU_WIDTH = PLATE_SCALE*60*5 #width of the csu in mm (widgth is 5 arcmin)
MM_TO_PIXEL = 1 #this is a mm to pixel ratio, it is currently just made up

logger = logging.getLogger(__name__)

class interactiveBars(QGraphicsRectItem):
    
    def __init__(self,x,y,bar_length,bar_width,this_id):
        super().__init__()
        #creates a rectangle that can cha
        self.length = bar_length
        self.width = bar_width
        self.y_pos = y
        self.setRect(x,self.y_pos, self.length,self.width)
        self.id = this_id
        self.setBrush = QBrush(Qt.GlobalColor.white)
        self.setPen = QPen(Qt.GlobalColor.black).setWidth(1)
        self.setFlags(self.GraphicsItemFlag.ItemIsSelectable)


    def check_id(self):
        return self.id
    
    def paint(self, painter: QPainter, option, widget = None):
        if self.isSelected():
            #self.setBrush = QBrush(Qt.GlobalColor.blue)
            painter.setBrush(QBrush(Qt.GlobalColor.cyan))
            painter.setPen(QPen(QColor("black"), 1))
        else:
            painter.setBrush(QBrush(Qt.GlobalColor.white))
            painter.setPen(QPen(QColor("black"), 1))
        painter.drawRect(self.rect())
    
    def send_size(self):
        return (self.length,self.width)

class FieldOfView(QGraphicsRectItem):
    def __init__(self,height=CSU_HEIGHT*MM_TO_PIXEL,width=CSU_WIDTH*MM_TO_PIXEL,x=0,y=0):
        super().__init__()

        self.height = height
        self.width = width #ratio of height to width 

        self.setRect(x,y,self.width,self.height)

        self.setPen(QPen(Qt.GlobalColor.darkGreen,4))
        self.setFlags(self.flags() & ~self.GraphicsItemFlag.ItemIsSelectable)

        self.setOpacity(0.35)
    def change_height(self):
        pass
    

class interactiveSlits(QGraphicsItemGroup):
    
    def __init__(self,x,y,name="NONE"):
        super().__init__()
        #line length will be dependent on the amount of slits
        #line position will depend on the slit position of the slits (need to check slit width and postion)
        #will have default lines down the middle
        #default NONE next to lines that don't have a star
        self.x_pos = x
        self.y_pos = y
        self.line = QGraphicsLineItem(self.x_pos,self.y_pos,self.x_pos,self.y_pos+7)
        #self.line = QLineF(x,y,x,y+7)
        self.line.setPen(QPen(Qt.GlobalColor.red, 2))

        self.star_name = name
        self.star = QGraphicsTextItem(self.star_name)
        self.star.setDefaultTextColor(Qt.GlobalColor.red)
        self.star.setFont(QFont("Arial",6))
        self.star.setPos(x+5,y-4)
        self.setFlags(self.flags() & ~self.GraphicsItemFlag.ItemIsSelectable)


        self.addToGroup(self.line)
        self.addToGroup(self.star)
    def get_y_value(self):
        return self.y_pos
    def get_bar_id(self):
        return self.y_pos/7
    def get_star_name(self):
        return self.star_name

class CustomGraphicsView(QGraphicsView):
    def __init__(self,scene):
        super().__init__(scene)
        # self.scene() == scene
        self.previous_height = self.height()
        self.previous_width = self.width()

        self.scale_x = 1.8
        self.scale_y = 1.8 #0.9
    
        self.scale(self.scale_x, self.scale_y)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.setViewportMargins(0,0,0,0)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def sizePolicy(self):
        return super().sizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    def renderHints(self):
        return super().renderHints(QPainter.RenderHint.Antialiasing)

class interactiveSlitMask(QWidget):
    row_selected = pyqtSignal(int,name="row selected")
    select_star = pyqtSignal(str)
    
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
        
        initial_bar_width = 7
        bar_length = self.scene_width
        self.bar_height = scene_height/72#PLATE_SCALE*7.6
        padding = 7

        for i in range(72):
            temp_rect = interactiveBars(0,i*self.bar_height+padding,this_id=i,bar_width=initial_bar_width,bar_length=bar_length)
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
    def connect_on(self,answer:bool):
        #---------------reconnect connections---------------
        if answer:
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
        # self.connect_on(False)
        if 0 <= row <len(all_bars):
            self.row_num = row
            all_bars[self.row_num].setSelected(True)
        # self.connect_on(True)

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
            if all_stars[i].star_name == name:
                bar_id = int(all_stars[i].get_bar_id())
                self.connect_on(False)
                all_bars[bar_id-1].setSelected(True)
                self.connect_on(True)
                
    def get_star_name_from_row(self):
        row_list = [x.check_id() for x in self.scene.selectedItems()]
        selected_star = [
            item.get_star_name() for item in reversed(self.scene.items())
            if isinstance(item, QGraphicsItemGroup) and item.get_bar_id()-1 in row_list
        ]
        if selected_star != []:
            logger.info(f"slit_view: method get_star_name_from_row called, selected star: {selected_star[0]}")
            self.select_star.emit(selected_star[0])

    def row_is_selected(self):
        if self.scene.selectedItems() != []:
            row_num = self.scene.selectedItems()[0].check_id()
            logger.info(f"slit_view: method row_is_selected called, row_num: {row_num}")
            self.row_selected.emit(row_num)

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
                
                new_item = interactiveSlits(x_center+x_pos, bar_id*self.bar_height+7, name) #7 is the margin at the top 
                new_items.append(new_item)
            except:
                continue
        #item_list.reverse()
        for item in new_items:
            self.scene.addItem(item)
        self.view = QGraphicsScene(self.scene)
    @pyqtSlot(np.ndarray, name="update labels")
    def update_name_center_pa(self,info):
        mask_name, center, pa = info[0], info[1], info[2] #the format of info is [mask_name,center,pa]
        if type(center) is tuple():
            center = str(center[0])+str(center[1])
        self.mask_name_title.setText(f'MASK NAME: {mask_name}')
        self.center_title.setText(f'CENTER: {center}')
        self.pa_title.setText(f'PA: {pa}')


"""
all the connections will be handled through the main widget
The tab widget will emit a signal on whether wavelengthview is in view or not (or which one is in view)
depending of in the wavelengthview is in view or now will change if the slitmask view will send information to it
all signals to outside will be handled through the slitmaskview
"""



class WavelengthView(QWidget):
    row_selected = pyqtSignal(int,name="row selected")
    
    def __init__(self):
        super().__init__()
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self.setMinimumSize(1,1)

        #--------------------definitions-----------------------
        logger.info("wavelength_view: doing definitions")
        scene_width = CSU_WIDTH * MM_TO_PIXEL
        scene_height = CSU_HEIGHT * MM_TO_PIXEL
        self.scene = QGraphicsScene(0,0,scene_width,scene_height)

        xcenter_of_image = self.scene.width()/2

        self.mask_name_title = QLabel(f'MASK NAME: None')
        self.center_title = QLabel(f'CENTER: None')
        self.pa_title = QLabel(f'PA: None')
        
        initial_bar_width = 7
        bar_length = scene_width
        self.bar_height = PLATE_SCALE*7.6
        padding = 7

        for i in range(72):
            temp_rect = interactiveBars(0,i*self.bar_height+padding,this_id=i,bar_width=initial_bar_width,bar_length=bar_length)
            temp_slit = interactiveSlits(scene_width/2,self.bar_height*i+padding)
            self.scene.addItem(temp_rect)
            self.scene.addItem(temp_slit)

        fov = FieldOfView(x=xcenter_of_image/2,y=padding)
        self.scene.addItem(fov)

        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        self.view = CustomGraphicsView(self.scene)
        #-------------------connections-----------------------
        logger.info("wavelength_view: establishing connections")

        self.scene.selectionChanged.connect(self.send_row)
        # self.combobox.currentIndexChanged.connect(self.re_initialize_scene)

        #------------------------layout-----------------------
        logger.info("wavelength_view: defining layout")
        top_layout = QHBoxLayout()
        main_layout = QVBoxLayout()

        top_layout.addWidget(self.mask_name_title,alignment=Qt.AlignmentFlag.AlignHCenter)
        top_layout.addWidget(self.center_title,alignment=Qt.AlignmentFlag.AlignHCenter)
        top_layout.addWidget(self.pa_title,alignment=Qt.AlignmentFlag.AlignHCenter)
        top_layout.setContentsMargins(0,0,0,0)
        top_layout.setSpacing(0)
        main_layout.addLayout(top_layout)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.addWidget(self.view)

        self.setLayout(main_layout)
        #-------------------------------------------
    def sizeHint(self):
        return QSize(650,620)
    
    def connect_on(self,answer:bool):
        #---------------reconnect connections---------------
        if answer:
            self.scene.selectionChanged.connect(self.send_row)
        else:
            self.scene.selectionChanged.disconnect(self.send_row)

    @pyqtSlot(int,name="row selected")
    def select_corresponding_row(self,row):
        all_bars = [
            item for item in reversed(self.scene.items())
            if isinstance(item, QGraphicsRectItem)
        ]
        self.connect_on(False)
        self.scene.clearSelection()
        # 
        if 0 <= row <len(all_bars):
            self.row_num = row
            all_bars[self.row_num].setSelected(True)
        self.connect_on(True)

    def send_row(self):
        if len(self.scene.selectedItems()) >0:
            row_num = self.scene.selectedItems()[0].check_id()
            self.row_selected.emit(row_num)

    @pyqtSlot(list,name="wavelength data")
    def get_spectra_of_star(self,ra_dec_list): #[bar_id,ra,dec]
        self.spectra_dict = {}
        for x in ra_dec_list:
            bar_id = x[0]
            ra = x[1]
            dec = x[2] 
            coord = SkyCoord(ra, dec, unit=(u.hourangle, u.deg), frame='icrs')
            #Currently not available
            
        self.re_initialize_scene(0)
        #gets the flux of each
    pyqtSlot(int,name="re-initializing scene")
    def re_initialize_scene(self,index):
        slit_spacing = 7
        
        try:
            new_items = [
                interactiveSlits(x=240, y=bar_id * slit_spacing + 7, name=str(np.float32(value[index])))
                for bar_id, value in self.spectra_dict.items()
            ]
            [self.scene.removeItem(item) for item in reversed(self.scene.items()) if isinstance(item, QGraphicsItemGroup)]

        except:
            return
        
        for item in new_items:
            self.scene.addItem(item)

        self.view.setScene(self.scene)
    

    @pyqtSlot(np.ndarray, name="update labels")
    def update_name_center_pa(self,info):
        mask_name, center, pa = info[0], info[1], info[2] #the format of info is [mask_name,center,pa]
        self.mask_name_title.setText(f'MASK NAME: {mask_name}')
        self.center_title.setText(f'CENTER: {center}')
        self.pa_title.setText(f'PA: {pa}')



# Define the coordinates (RA, Dec) - replace with your values

