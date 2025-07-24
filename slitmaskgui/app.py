"""
The GUI is in its very early stages. Its current features are the ability to take in a starlist file
and then display that file in a list
and a menu that doesn't do anything. 7/9/25
"""
"""
random stuff
GUI has to be able to send a command with the target lists to the mask back end
to call the slit mask algorithm with the code from the backend

the back end kind of already parses through a file that sorts all of the objects so I will
just take that and display that instead of through my awful input targets function 
(they also have a function to view the list)
"""


#just importing everything for now. When on the final stages I will not import what I don't need
from slitmaskgui.target_list_widget import TargetDisplayWidget
from slitmaskgui.mask_gen_widget import MaskGenWidget
from slitmaskgui.menu_bar import MenuBar
from slitmaskgui.interactive_slit_mask import interactiveSlitMask
from slitmaskgui.mask_configurations import MaskConfigurationsWidget
from slitmaskgui.slit_position_table import SlitDisplay
from PyQt6.QtCore import Qt, QSize
import sys
import random
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QSizePolicy,
    QSplitter,
    QLayout,

)

# pos_dict = {1:(240,0,"none")}
# for i in range(2,73):
#     pos_dict[i]=(random.randint(100,400),i,"bob")



class TempWidgets(QLabel):
    def __init__(self,w,h,text:str="hello"):
        super().__init__()
        self.setFixedSize(w,h)
        self.setText(text)
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.setStyleSheet("border: 2px solid black;")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LRIS-2 Slit Configuration Tool")
        self.setGeometry(100,100,1000,700)
        self.setMenuBar(MenuBar()) #sets the menu bar
        
        #----------------------------definitions---------------------------
        mask_config_widget = MaskConfigurationsWidget()
        mask_gen_widget = MaskGenWidget()
        
        target_display = TargetDisplayWidget()
        interactive_slit_mask = interactiveSlitMask()
        slit_position_table = SlitDisplay()
        

        #---------------------------------connections-----------------------------
        slit_position_table.highlight_other.connect(interactive_slit_mask.select_corresponding_row)
        interactive_slit_mask.row_selected.connect(slit_position_table.select_corresponding)

        mask_gen_widget.change_data.connect(target_display.change_data)
        mask_gen_widget.change_slit_image.connect(interactive_slit_mask.change_slit_and_star)
        mask_gen_widget.change_row_widget.connect(slit_position_table.change_data)


        #-----------------------------------layout-----------------------------
        layoutH1 = QHBoxLayout() #Contains slit position table and interactive slit mask
        splitterV1 = QSplitter()
        main_splitter = QSplitter()
        splitterV2 = QSplitter()
        # line_color = "#aeb5ad"
        # splitterV1.setStyleSheet(f"QSplitter::handle {{background-color: {line_color};}}")
        # splitterV2.setStyleSheet(f"QSplitter::handle {{background-color: {line_color};}}")
        # main_splitter.setStyleSheet(f"QSplitter::handle {{background-color: {line_color};}}")

        interactive_slit_mask.setContentsMargins(0,0,0,0)
        slit_position_table.setContentsMargins(0,0,0,0)
        mask_config_widget.setMaximumHeight(200)

        splitterV2.addWidget(mask_config_widget)
        splitterV2.addWidget(mask_gen_widget)
        splitterV2.setOrientation(Qt.Orientation.Vertical)
        splitterV2.setContentsMargins(0,0,0,0)

        layoutH1.addWidget(slit_position_table)#temp_widget2)
        layoutH1.addWidget(interactive_slit_mask) #temp_widget3
        layoutH1.setSpacing(0)
        layoutH1.setContentsMargins(0,0,0,0)
        widgetH1 = QWidget()
        widgetH1.setLayout(layoutH1)

        splitterV1.addWidget(widgetH1)
        splitterV1.setCollapsible(0,False)
        splitterV1.addWidget(target_display)
        splitterV1.setOrientation(Qt.Orientation.Vertical)
        splitterV1.setContentsMargins(0,0,0,0)

        main_splitter.addWidget(splitterV1)
        main_splitter.setCollapsible(0,False)
        main_splitter.addWidget(splitterV2)
        main_splitter.setContentsMargins(9,9,9,9)

        self.setCentralWidget(main_splitter)
        #-------------------------------------------------------


if __name__ == '__main__':
    app = QApplication(sys.argv)

    with open("/Users/austinbowman/lris2/slitmaskgui/styles.qss", "r") as f:
        _style = f.read()
    app.setStyleSheet(_style)

    window = MainWindow()
    window.show()
    app.exec()