
import logging
from PyQt6.QtCore import Qt, QPointF, pyqtProperty, QRectF
from PyQt6.QtGui import QBrush, QPen, QPainter, QColor, QFont, QLinearGradient
from PyQt6.QtWidgets import (
    QGraphicsView,
    QGraphicsRectItem,
    QGraphicsLineItem,
    QGraphicsTextItem,
    QGraphicsItemGroup,
    QSizePolicy,
    QApplication,
    QGraphicsObject,
    QVBoxLayout,
    QDialogButtonBox,
    QLabel,
    QDialog


)

#taken from https://catppuccin.com/palette/

dark_palette = {
    'green': "#a6e3a1",
    'blue': "#89b4fa",
    'sapphire': "#74c7ec",
    'base': "#1e1e2e",
    'overlay_0': "#6c7086",
    'overlay_2': "#9399b2",
    'maroon': "#eba0ac",
    'text': "#cdd6f4",
}
light_palette = {
    'green': "#40a02b",
    'blue': "#1e66f5",
    'sapphire': "#209fb5",
    'base': "#eff1f5",
    'overlay_0': "#7c7f93", #switched with overlay 2
    'overlay_2': "#9ca0b0", #switched with overlay 0
    'maroon': "#e64553",
    'text': "#4c4f69"
}


def get_theme() -> dict:
    theme = QApplication.instance().styleHints().colorScheme()
    if theme == Qt.ColorScheme.Dark:
        return dark_palette
    elif theme == Qt.ColorScheme.Light:
        return light_palette
    return dark_palette



#will have another thing that will dispaly all the stars in the sky at the time
PLATE_SCALE = 0.7272 #(mm/arcsecond) on the sky
CSU_HEIGHT = PLATE_SCALE*60*10 #height of csu in mm (height is 10 arcmin)
CSU_WIDTH = PLATE_SCALE*60*5 #width of the csu in mm (widgth is 5 arcmin)
MM_TO_PIXEL = 1 #this is a mm to pixel ratio, it is currently just made up
CCD_HEIGHT = 61.2 #in mm
CCD_WIDTH = 61.2 #in mm
DEMO_WIDTH = 260
DEMO_HEIGHT = 75


logger = logging.getLogger(__name__)


class ErrorWidget(QDialog):
    def __init__(self,dialog_text):
        super().__init__()
        self.setWindowTitle("ERROR")
        layout = QVBoxLayout()
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlags(
            self.windowFlags() |
            Qt.WindowType.WindowStaysOnTopHint
        )
        
        self.label = QLabel(dialog_text)
        buttons = QDialogButtonBox.StandardButton.Ok
        button_box = QDialogButtonBox(buttons)
        button_box.accepted.connect(self.accept)
        layout.addWidget(self.label)
        layout.addWidget(button_box)
        self.setLayout(layout)

class SimpleTextItem(QGraphicsTextItem):
    def __init__(self,text):
        super().__init__()
        self.setPlainText(text)
        self.theme = get_theme()
        self.setDefaultTextColor(QColor(self.theme['text']))
        self.setFont(QFont("Arial",1))

        QApplication.instance().styleHints().colorSchemeChanged.connect(self.update_theme)
        
    def update_theme(self):
        self.theme = get_theme()
    
class SimpleBarPair(QGraphicsObject):
    def __init__(self, slit_width: float, x_position: float, bar_id: int, left_side: bool = True):
        super().__init__()
        self.bar_length = DEMO_WIDTH # I will fact check this
        self.bar_height = DEMO_HEIGHT/12 # I will change this later

        self.slit_width = slit_width # needs to be in mm
        self.x_pos = x_position - self.slit_width/2
        self.y_pos = bar_id * self.bar_height
        self.theme = get_theme()
        self.side = left_side
        self.setPos(self.x_pos,self.y_pos)
        #I might paint differently depending on themes

        QApplication.instance().styleHints().colorSchemeChanged.connect(self.update_theme)
    def update_theme(self):
        self.theme = get_theme()
        # self.setPen(QPen(QColor.fromString(self.theme['green']),self.thickness))
    def paint(self, painter: QPainter, option, widget = None):
        painter.setBrush(QBrush(QColor.fromString(self.theme['overlay_2'])))
        painter.setPen(QPen(QColor.fromString(self.theme['overlay_0']), 1))
        if self.side:
            painter.drawRect(self.left_side())
        else:
            painter.drawRect(self.right_side())
    def left_side(self):
        rect_item = QRectF(0,0, - self.bar_length, self.bar_height)
        return rect_item
    def right_side(self):
        rect_item = QRectF(self.slit_width,0, self.bar_length, self.bar_height)
        return rect_item
    def boundingRect(self):
        if self.side:
            return self.left_side()
        else:
            return self.right_side()
    def get_pos(self):
        return QPointF(self.x(), self.slit_width)
    def set_pos(self, pos: QPointF):
        self.setX(pos.x())
        self.slit_width = pos.y()

    pos_anim = pyqtProperty(QPointF, fget=get_pos, fset=set_pos)

class MoveableFieldOfView(QGraphicsObject):
    def __init__(self,height=DEMO_HEIGHT,width=DEMO_WIDTH,x=0,y=0,thickness = 4):
        super().__init__()

        self.theme = get_theme()
        self.width = width
        self.height = height

        self.setPos(x,y)
        self.thickness = thickness

        # self.setOpacity(0.5)
        QApplication.instance().styleHints().colorSchemeChanged.connect(self.update_theme)
    def paint(self, painter: QPainter, option, widget = None):
        painter.setPen(QPen(QColor.fromString(self.theme['green']),self.thickness))
        painter.drawRect(self.rect())
    def rect(self):
        rect_item = QRectF(0,0, self.width, self.height)
        return rect_item
    def update_theme(self):
        self.theme = get_theme()
    def boundingRect(self):
        return self.rect()
    def get_pos(self):
        return self.pos()
    def set_pos(self, pos: QPointF):
        self.setPos(pos)

    pos_anim = pyqtProperty(QPointF, fget=get_pos, fset=set_pos)
    

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
        self.theme = get_theme()

        QApplication.instance().styleHints().colorSchemeChanged.connect(self.update_theme)
        
    def update_theme(self):
        self.theme = get_theme()

    def check_id(self):
        return self.id
    
    def paint(self, painter: QPainter, option, widget = None):

        if self.has_gradient:
            gradient = self.draw_with_gradient()
            painter.setBrush(QBrush(gradient))
            if self.isSelected():
                painter.setPen(QPen(QColor.fromString(self.theme['blue']), 0))
            else:
                painter.setPen(QPen(QColor.fromString(self.theme['base']), 0))
        elif self.isSelected():
            painter.setBrush(QBrush(QColor.fromString(self.theme['blue'])))
            painter.setPen(QPen(QColor.fromString(self.theme['base']), 0))
        else:
            painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            painter.setPen(QPen(QColor.fromString(self.theme['overlay_0']), 0))
        
        painter.drawRect(self.rect())
    
    def draw_with_gradient(self):
        start_point = QPointF(self.x_pos, self.y_pos)
        end_point = QPointF(self.x_pos+self.length, self.y_pos +self.width)

        gradient = QLinearGradient(start_point, end_point)
        gradient.setColorAt(0.0, QColor(self.theme['overlay_0']))
        gradient.setColorAt(1.0, QColor(self.theme['overlay_2']))
        return gradient
    
    def send_size(self):
        return (self.length,self.width)


class FieldOfView(QGraphicsRectItem):
    def __init__(self,height=CSU_HEIGHT*MM_TO_PIXEL,width=CSU_WIDTH*MM_TO_PIXEL,x=0,y=0,thickness = 4):
        super().__init__()

        self.theme = get_theme()

        self.setRect(x,y,width,height)
        self.thickness = thickness

        self.setPen(QPen(QColor.fromString(self.theme['green']),self.thickness))
        self.setFlags(self.flags() & ~self.GraphicsItemFlag.ItemIsSelectable)

        self.setOpacity(0.5)
        

        QApplication.instance().styleHints().colorSchemeChanged.connect(self.update_theme)
        
    def update_theme(self):
        self.theme = get_theme()
        self.setPen(QPen(QColor.fromString(self.theme['green']),self.thickness))


class interactiveSlits(QGraphicsItemGroup):
    
    def __init__(self,x,y,name="NONE"):
        super().__init__()
        #line length will be dependent on the amount of slits
        #line position will depend on the slit position of the slits (need to check slit width and postion)
        #will have default lines down the middle
        #default NONE next to lines that don't have a star
        self.theme = get_theme()
        self.setPos(x,y)

        self.bar_height = round(CSU_HEIGHT/72*MM_TO_PIXEL) #without round it = 6.06 which causes some errors
        self.line = QGraphicsLineItem(x,y,x,y+self.bar_height)
        self.line.setPen(QPen(QColor.fromString(self.theme['maroon']), 2))

        self.star_name = name
        self.star = QGraphicsTextItem(self.star_name)
        self.star.setDefaultTextColor(QColor.fromString(self.theme['maroon']))
        self.star.setFont(QFont("Arial",6))
        self.star.setPos(x+5,y-4)
        self.setFlags(self.flags() & ~self.GraphicsItemFlag.ItemIsSelectable)

        self.addToGroup(self.line)
        self.addToGroup(self.star)

        QApplication.instance().styleHints().colorSchemeChanged.connect(self.update_theme)
        
    def update_theme(self):
        self.theme = get_theme()
        self.line.setPen(QPen(QColor.fromString(self.theme['maroon']), 2))
        self.star.setDefaultTextColor(QColor.fromString(self.theme['maroon']))
        #have to call a paint event
    def get_y_value(self):
        return self.y()
    def get_bar_id(self):
        return int(self.y()/self.bar_height)
    def get_star_name(self):
        return self.star_name
    
class BracketLineObject(QGraphicsItemGroup):
    
    def __init__(self, x_pos_of_edge_of_bar, total_height_of_bars, x_pos_of_edge_of_name, y_position_of_name,bar_height):
        super().__init__()

        self.theme = get_theme()

        self.bar_pos = x_pos_of_edge_of_bar
        self.height = total_height_of_bars
        self.x_name_pos = x_pos_of_edge_of_name
        self.y_name_pos = y_position_of_name + bar_height/2

        self.bracket_width = 0.5
        self.padding = 0.5
        self.pen = QPen(QColor(self.theme['text']))
        self.pen.setWidth(0)
        # self.pen.setStyle(Qt.PenStyle.DashLine)
        multiplier = 2
        self.pen.setDashPattern([2*multiplier,1*multiplier])

        if self.height:
            self.make_bracket_and_line()
        else:
            self.make_line()


        QApplication.instance().styleHints().colorSchemeChanged.connect(self.update_theme)
        
    def update_theme(self):
        self.theme = get_theme()
        self.pen = QPen(QColor(self.theme['text']))

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