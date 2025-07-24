"""
This is the interactive slit mask feature. It will interact with the bar table on the left.
when you click the bar on the left then the image will display which row that is
additionally It will also interact with the target list
it will display where the slit is place and what stars will be shown
"""
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


)

#will have another thing that will dispaly all the stars in the sky at the time
PLATE_SCALE = 0.7272 #(mm/arcsecond) on the sky
CSU_HEIGHT = PLATE_SCALE*60*10 #height of csu in mm (height is 10 arcmin)
CSU_WIDTH = PLATE_SCALE*60*5 #width of the csu in mm (widgth is 5 arcmin)

class interactiveBars(QGraphicsRectItem):
    
    def __init__(self,x,y,bar_length,bar_width,this_id):
        super().__init__()
        #creates a rectangle that can cha
        self.length = bar_length
        self.width = bar_width
        self.setRect(x,y, self.length,self.width)
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
    def __init__(self,image_height,x=0,y=0):
        super().__init__()

        self.height = image_height
        self.ratio = CSU_WIDTH/CSU_HEIGHT #ratio of height to width 

        self.setRect(x,y,self.height*self.ratio,self.height)

        self.setPen(QPen(Qt.GlobalColor.darkGreen,4))
        #self.setFlags(self.GraphicsItemFlag.ItemIsSelectable,False)
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

        self.addToGroup(self.line)
        self.addToGroup(self.star)
    def get_y_value(self):
        return self.y_pos

class CustomGraphicsView(QGraphicsView):
    def __init__(self,scene):
        super().__init__(scene)
        # self.scene() == scene
        self.previous_height = self.height()
        self.previous_width = self.width()
    
        self.scale(1,0.9)

    def resizeEvent(self,event):
        new_width = self.size().width()
        new_height = self.size().height()

        scale_x = new_width / self.previous_width
        scale_y = new_height / self.previous_height

        self.scale(scale_x, scale_y)

        self.previous_width = new_width
        self.previous_height = new_height

        super().resizeEvent(event)

    def sizePolicy(self):
        return super().sizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    def renderHints(self):
        return super().renderHints(QPainter.RenderHint.Antialiasing)

class interactiveSlitMask(QWidget):
    row_selected = pyqtSignal(int,name="row selected")
    def __init__(self):
        super().__init__()

        #--------------------definitions-----------------------
        scene_width = 480
        scene_height = 520
        self.scene = QGraphicsScene(0,0,scene_width,scene_height)

        total_height_of_bars = 7*72
        xcenter_of_image = self.scene.width()/2

        blank_space = " "*65
        title = QLabel(f"{blank_space}SLIT MASK VIEWER")
        
        initial_bar_width = 7
        initial_bar_length = 480

        for i in range(72):
            temp_rect = interactiveBars(0,i*7+7,this_id=i,bar_width=initial_bar_width,bar_length=initial_bar_length)
            temp_slit = interactiveSlits(scene_width/2,7*i+7)
            self.scene.addItem(temp_rect)
            self.scene.addItem(temp_slit)

        fov = FieldOfView(total_height_of_bars,x=xcenter_of_image/2,y=7)
        self.scene.addItem(fov)

        self.view = CustomGraphicsView(self.scene)

        #-------------------connections-----------------------
        self.scene.selectionChanged.connect(self.row_is_selected)


        #------------------------layout-----------------------
        main_layout = QVBoxLayout()
        
        main_layout.addWidget(title)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.addWidget(self.view)

        self.setLayout(main_layout)
        #-------------------------------------------
    def sizeHint(self):
        return QSize(650,620)
    
    @pyqtSlot(int,name="row selected")
    def select_corresponding_row(self,row):
        
        all_bars = [
            item for item in reversed(self.scene.items())
            if isinstance(item, QGraphicsRectItem)
        ]
        
        self.scene.clearSelection()
        if 0 <= row <len(all_bars):
            self.row_num = row
            all_bars[self.row_num].setSelected(True)

    
    def row_is_selected(self):
        try:
            row_num = self.scene.selectedItems()[0].check_id()
            self.row_selected.emit(row_num)
        except:
            pass

    @pyqtSlot(dict,name="targets converted")
    def change_slit_and_star(self,pos):
        #will get it in the form of {1:(position,star_names),...}
        self.position = list(pos.values())
        magic_number = 7
        new_items = []
        slits_to_replace = [
            item for item in reversed(self.scene.items())
            if isinstance(item, QGraphicsItemGroup)
        ]
        for num, item in enumerate(slits_to_replace):

            try:
                self.scene.removeItem(item)

                x_pos, bar_id, name = self.position[num]
                new_item = interactiveSlits(x_pos, bar_id*magic_number+7, name) #7 is the margin at the top 
                new_items.append(new_item)
            except Exception as e:
                print(f"Error processing item {num}: {e}")
                continue
        #item_list.reverse()
        for item in new_items:
            self.scene.addItem(item)
        self.view = QGraphicsScene(self.scene)


        

