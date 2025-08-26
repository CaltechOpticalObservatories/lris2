from PyQt6.QtWidgets import (
    QPushButton, QWidget, QVBoxLayout, QDialog, QLabel,
    QGraphicsRectItem, QGraphicsScene, QGraphicsView, QGraphicsLayout,
    )
from PyQt6.QtGui import QColor, QPen, QBrush
from PyQt6.QtCore import pyqtSignal, QPropertyAnimation, QParallelAnimationGroup, QEasingCurve
from slitmaskgui.mask_widgets.mask_objects import SimpleBarPair, FieldOfView, CustomGraphicsView

PLATE_SCALE = 0.7272 #(mm/arcsecond) on the sky
CSU_HEIGHT = PLATE_SCALE*60*10 #height of csu in mm (height is 10 arcmin)
CSU_WIDTH = PLATE_SCALE*60*5 #width of the csu in mm (widgth is 5 arcmin)


class CsuDisplauWidget(QWidget):
    connect_with_controller = pyqtSignal()
    def __init__(self):
        super().__init__()
        """will recieve data as position, bar_id, width"""

        main_widget = QLabel("CSU Display Mode")

        self.default_slit_width = 0.7 #
        self.scene = QGraphicsScene(0,0,CSU_WIDTH,CSU_HEIGHT)
        self.scene.setSceneRect(self.scene.itemsBoundingRect())

        self.view = CustomGraphicsView(self.scene)
        # -------------- set default layout numbers -------------
        default_layout_list = [[0,CSU_WIDTH/2,x,True] for x in range(12)] + [[0,CSU_WIDTH/2,x,False] for x in range(12)]

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
        bar_list = [SimpleBarPair(x[0],x[1],x[2],x[3]) for x in pos_list]
        [self.scene.addItem(bar) for bar in bar_list]
        self.scene.addItem(FieldOfView(height=CSU_HEIGHT/72*12)) # add green field of view
        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        self.view = CustomGraphicsView(self.scene)

    def get_slits(self, slits):
        print("csu_display_widget.py get_slits")
        bar_list = [SimpleBarPair(s.width/PLATE_SCALE,s.x,s.id,left_side=True) for s in slits]
        bar_list += [SimpleBarPair(s.width/PLATE_SCALE,s.x,s.id,left_side=False) for s in slits]
        print("get slits before aniating bars")
        try:
            current_bars = [item for item in self.scene.items() if isinstance(item, SimpleBarPair)]
            self.animate_bars(previous_bars=current_bars,future_bars=bar_list)
        except:
            pass

    def handle_configuration_mode(self):
        self.connect_with_controller.emit()
    def animate_bars(self, previous_bars: list, future_bars: list):
        self.anim_group = QParallelAnimationGroup()
        for prev, future in zip(previous_bars, future_bars):
            anim = QPropertyAnimation(prev, b"pos_anim")
            anim.setDuration(1500)
            anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            anim.setEndValue(future.get_pos())  # assuming future_bars[i] has correct pos
            
            self.anim_group.addAnimation(anim)
        self.anim_group.start()
        # self.update_layout(future_bars)
        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        self.view = CustomGraphicsView(self.scene)
        

