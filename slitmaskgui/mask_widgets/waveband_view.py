
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
    QLabel,
    QGraphicsSceneResizeEvent
)

#will have another thing that will dispaly all the stars in the sky at the time
PLATE_SCALE = 0.7272 #(mm/arcsecond) on the sky
CSU_HEIGHT = PLATE_SCALE*60*10 #height of csu in mm (height is 10 arcmin)
CSU_WIDTH = PLATE_SCALE*60*5 #width of the csu in mm (widgth is 5 arcmin)
MM_TO_PIXEL = 1 #this is a mm to pixel ratio, it is currently just made up
MAGNIFICATION_FACTOR = 7.35
CCD_HEIGHT = 61.2 #in mm
CCD_WIDTH = 61.2 #in mm


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
        self.scene_width = CCD_WIDTH* MM_TO_PIXEL
        self.scene_height = CCD_HEIGHT * MM_TO_PIXEL
        
        self.scene = QGraphicsScene(0,0,self.scene_width,self.scene_height) 

        #since this is being fed information from CSU, it automatically adjusts from CSU positions
        #so initialize as CSU and it will change it 
        #this is mostly for testing
        self.CSU_dimensions = (CSU_HEIGHT,CSU_WIDTH)
        xcenter_of_image = self.scene.sceneRect().center().x()

        self.mask_name = None
        self.bar_height = CCD_HEIGHT/72#PLATE_SCALE*8.6 #this could be wrong maybe use magnification factor

        # Initializing the cached dict
        self.cached_scene_dict = {}

        self.waveband_title = QLabel()
        
        self.slit_positions = [(xcenter_of_image,self.bar_height*x, "NONE") for x in range(72)]
        self.initialize_scene(passband=(310,550),which_grism='blue_low_res') # passband currently a temp variable
        self.view = CustomGraphicsView(self.scene)

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
    
    def toggle_connection(self,connect:bool):
        #---------------reconnect connections---------------
        if connect:
            self.scene.selectionChanged.connect(self.send_row)
        else:
            self.scene.selectionChanged.disconnect(self.send_row)

    @pyqtSlot(int,name="row selected")
    def select_corresponding_row(self,row):
        all_bars = [
            item for item in reversed(self.scene.items())
            if isinstance(item, QGraphicsRectItem)
        ]
        self.toggle_connection(False)
        self.scene.clearSelection()
        # 
        if 0 <= row <len(all_bars):
            self.row_num = row
            all_bars[self.row_num].setSelected(True)
        self.toggle_connection(True)

    def send_row(self):
        try:
            row_num = self.scene.selectedItems()[0].check_id()
            self.row_selected.emit(row_num)
        except:
            pass

    def get_slit_positions(self,slit_positions): #[(x_pos,y_pos)]
        #I think this is being called twice and I don't know why
        self.slit_positions = self.redefine_slit_positions(slit_positions)

    
    def make_new_bar(self, x_pos, y_pos, star_name, length = 100) -> QGraphicsRectItem:
        
        x_position = x_pos - length/2
        new_bar = interactiveBars(x_position,y_pos,this_id=star_name,bar_width=self.bar_height,bar_length=length,has_gradient=True)

        return new_bar
    
    def concatenate_stars(self, slit_positions) -> list:
        """
        Concatenates the positions of the star_name text

        Args:
            slit_positions: the positions of the slits on the slitmask (also contains the name of the star)
        Returns:
            List of all the names that will be displayed and the y_position of those names
        """
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
        """ Makes a text item given an x_position, y_position, and the text to be displayed """

        text_item = SimpleTextItem(text)
        offset = (text_item.boundingRect().width()/2,text_item.boundingRect().height()/2)
        text_item.setPos(x_pos-offset[0]/2,y_pos-offset[1]+self.bar_height)
        return text_item
    
    def find_edge_of_bar(self,bar_items)-> list:
        """
        groups bars of same length and x position into a list containing info on
        which star the bars correspond to, the right edge of the bar, and the total height of the bars

        Args:
            bar_items: list of all the bars
        Returns:
            list of information formatted like [(right edge of bar, height, name of star),...]
            IMPORTANT: if there is only one bar, total_height_of_bars will = 0
        """

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

        return new_bar_list
    
    def make_line_between_text_and_bar(self, bar_positions, name_positions,edge_of_name) -> list:
        """
        makes a line with a bracket that connects the star names on the right side with
        the corresponding wavebands in the middle
        
        Args: 
            bar_positions: positions of wavebands formatted like [(x_bar,height,star_name),...]
            name_positions: positions of the start names formatted like [(y_pos,name),...]
        Returns:
            List of all the bracket line objects
        """
        bars, names, name_edge = bar_positions, name_positions, edge_of_name
        sorted_merged_list = sorted(bars + names, key=lambda x: x[-1])

        information_list = []
        object_list = []

        for name, group in groupby(sorted_merged_list,key=lambda x: x[-1]):
            group = [sublist[:-1] for sublist in list(group)]
            # group = [(x_bar,height),(name_y_pos,)]
            information_list.append([group[0][0],group[0][1],name_edge,group[1][0]])
            # information_list = [[a=x_bar,b=height,c=name_edge,d=y_pos]]
        [object_list.append(BracketLineObject(a,b,c,d,bar_height=self.bar_height)) for a,b,c,d in information_list]
        return object_list

    def update_angstrom_text(self,waveband_range):
        """ Updates the text of the passband to ensure it is accurate with the desired display """
        text = f"Passband: {waveband_range[0]} nm to {waveband_range[1]} nm"
        self.waveband_title.setText(text)

    def calculate_bar_length(self,waveband_range,which_grism):
        """
        calculates how long the waveband will be for the selected grism

        Args:
            waveband_range: the range of the waveband in nm
            which_grism: a string of the selected grism 
        Returns:
            length of the bar depending on selected grism
        """

        passband = (waveband_range[0]/1000,waveband_range[1]/1000) #conversion from nm to microns

        def blue_low_res(x):
            return 276.612*x**3 - 424.636*x**2 + 413.464*x - 120.251
        def blue_high_blue(x):
            return 1694.055*x**3 - 2185.377*x**2 + 1398.040*x - 303.935
        def blue_high_red(x):
            return 791.523*x**3 - 1338.208*x**2 + 1171.084*x - 348.142
        def red_low_res(x):
            return 21.979*x**3 - 60.775*x**2 + 183.657*x - 115.552
        def red_high_blue(x):
            return 117.366*x**3 - 273.597*x**2 + 461.561*x - 219.310
        def red_high_red(x):
            return 76.897*x**3 - 235.837*x**2 + 479.807*x - 292.794

        match which_grism:
            case 'blue_low_res':
                low_end, high_end = map(blue_low_res, passband)
                return high_end - low_end #this is the length of the bar
            case 'blue_high_blue':
                low_end, high_end = map(blue_high_blue, passband)
                return high_end - low_end #this is the length of the bar
            case 'blue_high_red':
                low_end, high_end = map(blue_high_red, passband)
                return high_end - low_end #this is the length of the bar
            case 'red_low_res':
                low_end, high_end = map(red_low_res, passband)
                return (high_end - low_end) #this is the length of the bar
            case 'red_high_blue':
                low_end, high_end = map(red_high_blue, passband)
                return high_end - low_end #this is the length of the bar
            case 'red_high_red':
                low_end, high_end = map(red_high_red, passband)
                return high_end - low_end #this is the length of the bar
    
    def get_farthest_bar_edge(self,scene):
        """ Locates the bar furthest to the right and returns the right edge x position of that bar """
        bar_edge_list = [
            bar.boundingRect().right()
            for bar in scene.items()
            if isinstance(bar, interactiveBars)
            ]
        farther_edge = max(bar_edge_list)
        return farther_edge + 1 # number is 0.5 + 0.5 from the bracket item in mask_objects (spacing and bracket width)
        
    
    def redefine_slit_positions(self,slit_positions):
        """ Converts the slit positions that were defined for the CSU 
            into the corresponding position on the CCD """
        y_ratio = self.CSU_dimensions[0]/CCD_HEIGHT
        new_pos = [(x/MAGNIFICATION_FACTOR,y/y_ratio, name) for x,y,name in slit_positions]
        return new_pos

    
    def initialize_scene(self, passband, which_grism): 
        """
        initializes scene of selected grism
        assumes index corresponds to Red low, red high blue, red high red, blue low, blue high blue, blue high red

        Args:
            index: the index of what box was selected (corresponds with the grism)
        Kwargs:    
        which_grism: name of the grism 
        waveband_range: wavelength range that will be covered
        returns: 
            None
        """

        new_scene = self.scene
        [new_scene.removeItem(item) for item in new_scene.items()] #removes all items

        passband_in_nm = passband
        grism = which_grism
        bar_length = self.calculate_bar_length(passband_in_nm,grism)

        # ADD all the bars with slits
        [new_scene.addItem(self.make_new_bar(x,y,name,length=bar_length)) for x,y,name in self.slit_positions] 

        # Add a rectangle representing the CCD camera FOV (is currently not accurate)
        camera_border = FieldOfView(width=CCD_WIDTH*MM_TO_PIXEL,height=CCD_HEIGHT*MM_TO_PIXEL,x=0,y=0, thickness=0.5)
        new_scene.addItem(camera_border)

        # Add all the names of the stars on the side
        rightmost_bar_x = self.get_farthest_bar_edge(new_scene)
        name_positions = self.concatenate_stars(self.slit_positions)
        [new_scene.addItem(self.make_star_text(rightmost_bar_x,y,text)) for y,text in name_positions]

        # Add lines and brackets to point from star name to bar
        all_bar_objects = [bar for bar in new_scene.items() if isinstance(bar, interactiveBars)]
        edge_of_bar_list = self.find_edge_of_bar(all_bar_objects)
        bracket_list = self.make_line_between_text_and_bar(edge_of_bar_list,name_positions,rightmost_bar_x)
        [new_scene.addItem(item) for item in bracket_list]

        # Update waveband text
        self.update_angstrom_text(passband_in_nm) #it is no longer the angstrom range

        new_scene.setSceneRect(new_scene.itemsBoundingRect())
        self.scene = new_scene
        self.view = CustomGraphicsView(new_scene)
        self.view.setContentsMargins(0,0,0,0)

    def update_mask_name(self,info):
        self.mask_name = info[0]
        print(self.mask_name)
        