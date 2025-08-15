
import logging
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QBrush, QPen, QPainter, QColor, QFont, QLinearGradient
from PyQt6.QtWidgets import (
    QGraphicsView,
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