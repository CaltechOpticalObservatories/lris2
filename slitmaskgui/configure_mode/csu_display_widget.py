from PyQt6.QtWidgets import (
    QPushButton, QWidget, QVBoxLayout, QDialog, QLabel,
    QGraphicsRectItem, QGraphicsScene, QGraphicsView, QGraphicsLayout
    )
from PyQt6.QtGui import QColor, QPen, QBrush
from slitmaskgui.mask_widgets.mask_objects import SimpleBar, FieldOfView

PLATE_SCALE = 0.7272 #(mm/arcsecond) on the sky
CSU_HEIGHT = PLATE_SCALE*60*10 #height of csu in mm (height is 10 arcmin)
CSU_WIDTH = PLATE_SCALE*60*5 #width of the csu in mm (widgth is 5 arcmin)


class CsuDisplauWidget(QWidget):
    def __init__(self):
        super().__init__()
        """will recieve data as position, bar_id, width"""

        main_widget = QLabel("CSU Display Mode")

        self.default_slit_width = 0.7 #
        self.scene = QGraphicsScene(0,0,CSU_WIDTH,CSU_HEIGHT)

        self.view = QGraphicsView(self.scene)
        # -------------- set default layout numbers -------------
        default_layout_list = [[True, 0,CSU_WIDTH/2,x] for x in range(10)]
        [default_layout_list.append([False, 0, CSU_WIDTH/2,x]) for x in range(10)]

        # -------------- layout ------------------
        main_layout = QVBoxLayout()
        main_layout.addWidget(main_widget)
        main_layout.addWidget(self.view)
        main_layout.setContentsMargins(0,0,0,0)
        self.setLayout(main_layout)

        # ------------- initialize layout -------------
        self.set_layout(default_layout_list)
    
    def set_layout(self,pos_list):
        self.scene.clear()
        bar_list = [SimpleBar(x[0],x[1],x[2],x[3]) for x in pos_list]
        [self.scene.addItem(bar) for bar in bar_list]
        self.scene.addItem(FieldOfView()) # add green field of view

