"""
This is the interactive slit mask feature. It will interact with the bar table on the left.
when you click the bar on the left then the image will display which row that is
additionally It will also interact with the target list
it will display where the slit is place and what stars will be shown
"""

from itertools import groupby
import logging
import numpy as np
from astroquery.gaia import Gaia
from astropy.coordinates import SkyCoord
import astropy.units as u
import matplotlib.pyplot as plt
from astropy.wcs import WCS
from astropy.io import fits
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal, QSize, QPointF, QRectF
from PyQt6.QtGui import QBrush, QPen, QPainter, QColor, QFont, QLinearGradient, QTransform
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


)

#will have another thing that will dispaly all the stars in the sky at the time
PLATE_SCALE = 0.7272 #(mm/arcsecond) on the sky
CSU_HEIGHT = PLATE_SCALE*60*10 #height of csu in mm (height is 10 arcmin)
CSU_WIDTH = PLATE_SCALE*60*5 #width of the csu in mm (widgth is 5 arcmin)
MM_TO_PIXEL = 1 #this is a mm to pixel ratio, it is currently just made up

logger = logging.getLogger(__name__)



#got to add a "if dark mode then these are the colors"

class interactiveBars(QGraphicsRectItem):
    
    def __init__(self,x,y,bar_length,bar_width,this_id,has_gradient=False):
        super().__init__()
        #creates a rectangle that can cha
        self.length = bar_length
        self.width = bar_width
        self.y_pos = y
        self.x_pos = x
        self.has_gradient = has_gradient
        self.setRect(self.x_pos,self.y_pos, self.length,self.width)
        self.id = this_id
        self.setFlags(self.GraphicsItemFlag.ItemIsSelectable)


    def check_id(self):
        return self.id
    
    def paint(self, painter: QPainter, option, widget = None):

        if self.has_gradient:
            gradient = self.draw_with_gradient()
            painter.setBrush(QBrush(gradient))
            if self.isSelected():
                painter.setPen(QPen(QColor.fromString("#89b4fa"), 1))
            else:
                painter.setPen(QPen(QColor.fromString("#1e1e2e"), 0))
        elif self.isSelected():
            painter.setBrush(QBrush(QColor.fromString("#89b4fa")))
            painter.setPen(QPen(QColor.fromString("#1e1e2e"), 0))
        else:
            painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            painter.setPen(QPen(QColor.fromString("#6c7086"), 0))
        
        painter.drawRect(self.rect())
    
    def draw_with_gradient(self):
        start_point = QPointF(self.x_pos, self.y_pos)
        end_point = QPointF(self.x_pos+self.length, self.y_pos +self.width)

        gradient = QLinearGradient(start_point, end_point)
        gradient.setColorAt(0.0, QColor("#6c7086"))
        gradient.setColorAt(1.0, QColor("#9399b2"))
        return gradient
    
    def send_size(self):
        return (self.length,self.width)

class FieldOfView(QGraphicsRectItem):
    def __init__(self,height=CSU_HEIGHT*MM_TO_PIXEL,width=CSU_WIDTH*MM_TO_PIXEL,x=0,y=0):
        super().__init__()

        self.height = height
        self.width = width #ratio of height to width 

        self.setRect(x,y,self.width,self.height)

        self.setPen(QPen(QColor.fromString("#a6e3a1"),4))
        self.setFlags(self.flags() & ~self.GraphicsItemFlag.ItemIsSelectable)

        self.setOpacity(0.5)
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
        self.bar_height = round(CSU_HEIGHT/72*MM_TO_PIXEL) #without round it = 6.06 which causes some errors
        self.line = QGraphicsLineItem(self.x_pos,self.y_pos,self.x_pos,self.y_pos+self.bar_height)
        #self.line = QLineF(x,y,x,y+7)
        self.line.setPen(QPen(QColor.fromString("#eba0ac"), 2))

        self.star_name = name
        self.star = QGraphicsTextItem(self.star_name)
        self.star.setDefaultTextColor(QColor.fromString("#eba0ac"))
        self.star.setFont(QFont("Arial",6))
        self.star.setPos(x+5,y-4)
        self.setFlags(self.flags() & ~self.GraphicsItemFlag.ItemIsSelectable)


        self.addToGroup(self.line)
        self.addToGroup(self.star)
    def get_y_value(self):
        return self.y_pos
    def get_bar_id(self):
        return int(self.y_pos/self.bar_height)
    def get_star_name(self):
        return self.star_name
    
class BracketLineObject(QGraphicsItemGroup):
    
    def __init__(self, x_pos_of_edge_of_bar, total_height_of_bars, x_pos_of_edge_of_name, y_position_of_name,bar_height):
        super().__init__()

        self.bar_pos = x_pos_of_edge_of_bar
        self.height = total_height_of_bars
        self.x_name_pos = x_pos_of_edge_of_name
        self.y_name_pos = y_position_of_name + bar_height/2

        
        
        self.bracket_width = 7
        self.padding = 3
        self.pen = QPen(QColor("white"))
        self.pen.setWidth(0)
        # self.pen.setStyle(Qt.PenStyle.DashLine)
        multiplier = 2
        self.pen.setDashPattern([2*multiplier,1*multiplier])

        if self.height:
            self.make_bracket_and_line()
        else:
            self.make_line()

    
    def make_bracket_and_line(self):
        top_edge = QGraphicsLineItem(
            self.bar_pos + self.padding,
            self.y_name_pos - self.height/2,
            self.bar_pos + self.padding + self.bracket_width,
            self.y_name_pos - self.height/2,
            )
        bottom_edge = QGraphicsLineItem(
            self.bar_pos + self.padding,
            self.y_name_pos + self.height/2,
            self.bar_pos + self.padding + self.bracket_width,
            self.y_name_pos + self.height/2,
            )
        bracket_edge = QGraphicsLineItem(
            self.bar_pos + self.padding + self.bracket_width,
            self.y_name_pos - self.height/2,
            self.bar_pos + self.padding + self.bracket_width,
            self.y_name_pos + self.height/2,
            )
        main_line = QGraphicsLineItem(
            self.bar_pos + self.padding + self.bracket_width,
            self.y_name_pos,
            self.x_name_pos, #maybe add padding
            self.y_name_pos,
            )
        
        item_list = [top_edge,bottom_edge,bracket_edge,main_line]

        [item.setPen(self.pen) for item in item_list]
        [self.addToGroup(item) for item in item_list]

    def make_line(self):
        main_line = QGraphicsLineItem(
            self.bar_pos + self.padding,
            self.y_name_pos,
            self.x_name_pos,
            self.y_name_pos,
            )
        
        main_line.setPen(self.pen)
        self.addToGroup(main_line)

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
            if all_stars[i].get_star_name() == name:
                bar_id = int(all_stars[i].get_bar_id())
                self.connect_on(False)
                all_bars[bar_id].setSelected(True)
                self.connect_on(True)
                
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

"""
red and blue and 3 grisms for each

currently have the center of the bar move to the place where the slit is, and 
"""
class WavelengthView(QWidget):
    row_selected = pyqtSignal(int,name="row selected")
    
    def __init__(self):
        super().__init__()
        
        #--------------------definitions-----------------------
        logger.info("wave view: doing definitions")
        self.scene_width = (CSU_WIDTH+CSU_WIDTH/1.25) * MM_TO_PIXEL #this is the scene width of the slit display
        self.scene_height = CSU_HEIGHT * MM_TO_PIXEL #this is the scene height of the slit display
        self.scene = QGraphicsScene(0,0,self.scene_width,self.scene_height) 

        xcenter_of_image = self.scene.sceneRect().center().x()
        self.mask_name = None
        self.bar_height = CSU_HEIGHT/72#PLATE_SCALE*8.6

        # Initializing the cached dict
        self.cached_scene_dict = {}

        self.slit_positions = [(xcenter_of_image,self.bar_height*x, "NONE") for x in range(72)]
        self.initialize_scene(0,angstrom_range=(3100,5500)) # Angstrom range currently a temp variable

        #-------------------connections-----------------------
        logger.info("wave view: establishing connections")
        self.scene.selectionChanged.connect(self.send_row)

        #------------------------layout-----------------------
        logger.info("wave view: defining layout")

        main_layout = QVBoxLayout()

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
        try:
            row_num = self.scene.selectedItems()[0].check_id()
            self.row_selected.emit(row_num)
        except:
            pass

    def get_slit_positions(self,slit_positions,index,angstrom_range): #[(x_pos,y_pos)]
        #I think this is being called twice and I don't know why
        self.slit_positions = slit_positions
        self.initialize_scene(index,angstrom_range=(3100,5500))

    
    def make_new_bar(self, x_pos, y_pos, star_name, length = 100) -> QGraphicsRectItem:

        # Define the fov_width (fov_width subject to change from new data)
        fov_width = CSU_WIDTH*MM_TO_PIXEL

        # Calculate the x position of the edge of the bar
        x_position = x_pos-(self.scene_width-fov_width)/2
        x_position -= length/2 # map x to the left edge of the bar

        # Define the bar
        new_bar = interactiveBars(x_position,y_pos,this_id=star_name,bar_width=self.bar_height,bar_length=length,has_gradient=True)

        return new_bar
    
    def concatenate_stars(self, slit_positions):
        star_name_positions = [sublist[1:] for sublist in slit_positions]
        star_name_positions.sort(key=lambda x:x[1])
        name_positions = []
        for name, group in groupby(star_name_positions, key=lambda x: x[1]):
            group = list(group)
            max_y_pos = max(group, key=lambda x: x[0])[0]
            min_y_pos = min(group, key=lambda x: x[0])[0]
            average_y_pos = (max_y_pos+min_y_pos)/2
            name_positions.append((average_y_pos,name))

        return name_positions


    def make_star_text(self,x_pos, y_pos, text):

        text_item = QGraphicsTextItem(text)
        text_item.setPos(x_pos,y_pos - self.bar_height+1)
        text_item.setFont(QFont("Arial",6))

        return text_item
    
    def find_edge_of_bar(self,bar_items)-> list:

        new_list = sorted(
            [[bar.x_pos + bar.length, bar.y_pos, bar.id] for bar in bar_items],
            key=lambda x: x[2]
            )

        new_bar_list = []
        for name, group in groupby(new_list, key=lambda x: x[2]):
            group = [sublist[:-1] for sublist in list(group)]
            max_y_pos = max(group, key=lambda x: x[1])[1]
            min_y_pos = min(group, key=lambda x: x[1])[1]
            total_height_of_bars = max_y_pos-min_y_pos
            new_bar_list.append((group[0][0],total_height_of_bars,name))

        # it goes (right edge of bar, height, name of star)
        return new_bar_list
    
    def make_line_between_text_and_bar(self, bar_positions, name_positions,edge_of_name) -> list:
        #draw a dotted line between the bar and the star name so you can better see what corresponds to what
        #if its a group of bars draw a dotted bracket

        # bar_postions = [(x_bar,height,star_name),...]
        # name_positions = [(y_pos,name),...]
        # they have the same length
        bars, names, name_edge = bar_positions, name_positions, edge_of_name
        sorted_merged_list = sorted(bars + names, key=lambda x: x[-1])

        information_list = []
        object_list = []

        for name, group in groupby(sorted_merged_list,key=lambda x: x[-1]):
            group = [sublist[:-1] for sublist in list(group)]
            # group = [(x_bar,height),(name_y_pos,)]
            information_list.append([group[0][0],group[0][1],name_edge,group[1][0]])
        [object_list.append(BracketLineObject(a,b,c,d,bar_height=self.bar_height)) for a,b,c,d in information_list]
        return object_list

    def initialize_scene(self, index: int, **kwargs): 
        """
        initializes scene of selected grism of not stored in cache
        assumes index corresponds to Red low, red high blue, red high red, blue low, blue high blue, blue high red

        Args:
            index: the index of what box was selected (corresponds with the grism)
        Kwargs:    
        which_grism: name of the grism 
        angstrom_range: wavelength range that will be covered
        returns: 
            None
        """
        if self.mask_name not in self.cached_scene_dict.keys():
            self.cached_scene_dict[self.mask_name] = {}
        if index not in self.cached_scene_dict[self.mask_name]:
            new_scene = self.scene
            [new_scene.removeItem(item) for item in new_scene.items()] #removes all items

            angstrom_range = kwargs['angstrom_range']
            bar_length = 50#(angstrom_range[1]-angstrom_range[0])/10

            # ADD all the bars with slits
            [new_scene.addItem(self.make_new_bar(x,y,name)) for x,y,name in self.slit_positions] 

            # Add a rectangle representing the CCD camera FOV (is currently not accurate)
            camera_border = QGraphicsRectItem(0,0,CSU_WIDTH*MM_TO_PIXEL,CSU_HEIGHT*MM_TO_PIXEL)
            camera_border.setPen(QPen(QColor.fromString("#a6e3a1"),4))
            camera_border.setOpacity(0.5)
            new_scene.addItem(camera_border)

            # Add all the names of the stars on the side
            scene_width = new_scene.itemsBoundingRect().width()
            name_positions = self.concatenate_stars(self.slit_positions)
            [new_scene.addItem(self.make_star_text(scene_width,y,text)) for y,text in name_positions]

            # Prettify
            all_bar_objects = [bar for bar in new_scene.items() if isinstance(bar, interactiveBars)]
            edge_of_bar_list = self.find_edge_of_bar(all_bar_objects) #if the distance is 0 that means its one bar
            bracket_list = self.make_line_between_text_and_bar(edge_of_bar_list,name_positions,scene_width)
            [new_scene.addItem(item) for item in bracket_list]

            self.cached_scene_dict[self.mask_name][index]=new_scene
            self.cached_scene_dict[self.mask_name][index].setSceneRect(self.scene.itemsBoundingRect())
        
        # Changes the current scene to the scene at specified index
        self.view = CustomGraphicsView(self.cached_scene_dict[self.mask_name][index])
        self.view.setContentsMargins(0,0,0,0) 
        



# Define the coordinates (RA, Dec) - replace with your values

