
from slitmaskgui.mask_widgets.mask_objects import *
from itertools import groupby
import logging
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal, QSize
from PyQt6.QtGui import QPen, QColor, QFont
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QWidget,
    QGraphicsScene,
    QGraphicsRectItem,
    QGraphicsTextItem,
    QHBoxLayout,
    QLabel
)

#will have another thing that will dispaly all the stars in the sky at the time
PLATE_SCALE = 0.7272 #(mm/arcsecond) on the sky
CSU_HEIGHT = PLATE_SCALE*60*10 #height of csu in mm (height is 10 arcmin)
CSU_WIDTH = PLATE_SCALE*60*5 #width of the csu in mm (widgth is 5 arcmin)
MM_TO_PIXEL = 1 #this is a mm to pixel ratio, it is currently just made up

logger = logging.getLogger(__name__)




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

        self.waveband_title = QLabel()
        
        self.slit_positions = [(xcenter_of_image,self.bar_height*x, "NONE") for x in range(72)]
        self.initialize_scene(0,angstrom_range=(3100,5500)) # Angstrom range currently a temp variable

        #-------------------connections-----------------------
        logger.info("wave view: establishing connections")
        self.scene.selectionChanged.connect(self.send_row)

        #------------------------layout-----------------------
        logger.info("wave view: defining layout")

        main_layout = QVBoxLayout()
        top_layout = QHBoxLayout()

        self.waveband_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        top_layout.addWidget(self.waveband_title)

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
        # IMPORTANT: if there is only one bar, total_height_of_bars will = 0
        return new_bar_list
    
    def make_line_between_text_and_bar(self, bar_positions, name_positions,edge_of_name) -> list:
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

    def update_angstrom_text(self,angstrom_range):
        # Make text item
        text = f"Waveband Range: {angstrom_range[0]} angstroms {chr(0x2013)} {angstrom_range[1]} angstroms"
        self.waveband_title.setText(text)


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

            # Add lines and brackets to point from star name to bar
            all_bar_objects = [bar for bar in new_scene.items() if isinstance(bar, interactiveBars)]
            edge_of_bar_list = self.find_edge_of_bar(all_bar_objects)
            bracket_list = self.make_line_between_text_and_bar(edge_of_bar_list,name_positions,scene_width)
            [new_scene.addItem(item) for item in bracket_list]

            # Update waveband text
            self.update_angstrom_text(angstrom_range)

            # Add scene to dict
            self.cached_scene_dict[self.mask_name][index]=new_scene
            self.cached_scene_dict[self.mask_name][index].setSceneRect(self.scene.itemsBoundingRect())
        
        # Changes the current scene to the scene at specified index
        self.view = CustomGraphicsView(self.cached_scene_dict[self.mask_name][index])
        self.view.setContentsMargins(0,0,0,0) 
    
    pyqtSlot(list)
    def update_mask_name(self,info):
        self.mask_name = info[0]
        print(self.mask_name)
        