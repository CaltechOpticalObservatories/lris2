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
import sys
import random
import logging
logging.basicConfig(
    filename="main.log",
    format='%(asctime)s %(message)s',
    filemode='w',
    level=logging.INFO
)


from slitmaskgui.target_list_widget import TargetDisplayWidget
from slitmaskgui.mask_gen_widget import MaskGenWidget
from slitmaskgui.menu_bar import MenuBar
from slitmaskgui.mask_viewer import interactiveSlitMask, WavelengthView, SkyImageView
from slitmaskgui.mask_configurations import MaskConfigurationsWidget
from slitmaskgui.slit_position_table import SlitDisplay
from slitmaskgui.mask_view_tab_bar import TabBar
from PyQt6.QtCore import Qt, QSize, pyqtSlot
from PyQt6.QtGui import QFontDatabase
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
    QTreeWidgetItem,
    QTreeWidget,
    QTabWidget,
    QComboBox


)

#need to add something that will query where the stars will be depending on the time of day
main_logger = logging.getLogger()
main_logger.info("starting logging")

"""
currently use center of priority doesn't work (don't know the problem will diagnose it at some later point)
need to make it so that it doesn't randomly generate a starlist with random priority
add more logging to all the functions
"""

"""
Things to do before launch
photo display of the stars
use center of priority should work
ability to modulate slit width
actually use a starlist instead of generating your own
add logging to everything
ability to state max slit length
"""

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LRIS-2 Slit Configuration Tool")
        self.setGeometry(100,100,1000,760)
        self.setMenuBar(MenuBar()) #sets the menu bar
        
        #----------------------------definitions---------------------------
        main_logger.info("app: doing definitions")
        
        mask_config_widget = MaskConfigurationsWidget()
        mask_gen_widget = MaskGenWidget()
        
        self.target_display = TargetDisplayWidget()
        self.interactive_slit_mask = interactiveSlitMask()
        self.slit_position_table = SlitDisplay()
        self.wavelength_view = WavelengthView()
        self.sky_view = SkyImageView()
        self.mask_tab = TabBar(slitmask=self.interactive_slit_mask,waveview=self.wavelength_view,skyview=self.sky_view)
        

        #---------------------------------connections-----------------------------
        main_logger.info("app: doing connections")
        self.slit_position_table.highlight_other.connect(self.interactive_slit_mask.select_corresponding_row)
        self.interactive_slit_mask.row_selected.connect(self.slit_position_table.select_corresponding)
        self.interactive_slit_mask.row_selected.connect(self.wavelength_view.select_corresponding_row)
        self.target_display.selected_le_star.connect(self.interactive_slit_mask.get_row_from_star_name)
        self.interactive_slit_mask.select_star.connect(self.target_display.select_corresponding)
        self.wavelength_view.row_selected.connect(self.interactive_slit_mask.select_corresponding_row)
        self.mask_tab.waveview_change.connect(self.wavelength_view.re_initialize_scene)

        mask_gen_widget.change_data.connect(self.target_display.change_data)
        mask_gen_widget.change_slit_image.connect(self.interactive_slit_mask.change_slit_and_star)
        mask_gen_widget.change_row_widget.connect(self.slit_position_table.change_data)
        mask_gen_widget.send_mask_config.connect(mask_config_widget.update_table)
        mask_gen_widget.change_mask_name.connect(self.interactive_slit_mask.update_name_center_pa)
        mask_gen_widget.change_wavelength_data.connect(self.wavelength_view.get_spectra_of_star)
        mask_gen_widget.update_image.connect(self.sky_view.show_image)

        mask_config_widget.change_data.connect(self.target_display.change_data)
        mask_config_widget.change_row_widget.connect(self.slit_position_table.change_data)
        mask_config_widget.change_slit_image.connect(self.interactive_slit_mask.change_slit_and_star)
        mask_config_widget.reset_scene.connect(self.reset_scene)


        #-----------------------------------layout-----------------------------
        main_logger.info("app: setting up layout")
        self.layoutH1 = QHBoxLayout() #Contains slit position table and interactive slit mask
        self.splitterV1 = QSplitter()
        main_splitter = QSplitter()
        self.splitterV2 = QSplitter()
        self.mask_viewer_main = QVBoxLayout()

        self.interactive_slit_mask.setContentsMargins(0,0,0,0)
        self.slit_position_table.setContentsMargins(0,0,0,0)
        self.slit_position_table.setMinimumHeight(1)
        self.mask_tab.setMinimumSize(1,1)
        mask_config_widget.setMinimumSize(1,1)
        mask_gen_widget.setMinimumSize(1,1)


        self.splitterV2.addWidget(mask_config_widget)
        self.splitterV2.addWidget(mask_gen_widget)
        self.splitterV2.setOrientation(Qt.Orientation.Vertical)
        self.splitterV2.setContentsMargins(0,0,0,0)

        self.layoutH1.addWidget(self.slit_position_table)#temp_widget2)
        self.layoutH1.addWidget(self.mask_tab)
        # self.layoutH1.addWidget(self.combobox)
        self.layoutH1.setSpacing(0)
        self.layoutH1.setContentsMargins(0,0,0,0)
        widgetH1 = QWidget()
        widgetH1.setLayout(self.layoutH1)

        self.splitterV1.addWidget(widgetH1)
        # self.splitterV1.setCollapsible(0,False)
        self.splitterV1.addWidget(self.target_display)
        self.splitterV1.setOrientation(Qt.Orientation.Vertical)
        self.splitterV1.setContentsMargins(0,0,0,0)

        main_splitter.addWidget(self.splitterV1)
        # main_splitter.setCollapsible(0,False)
        main_splitter.addWidget(self.splitterV2)
        main_splitter.setContentsMargins(9,9,9,9)

        self.setCentralWidget(main_splitter)
        #-------------------------------------------------------
    @pyqtSlot(name="reset scene")
    def reset_scene(self):
        main_logger.info("app: scene is being reset")
        # --- Remove old widgets from layout ---
        self.interactive_slit_mask.setParent(None)
        self.slit_position_table.setParent(None)
        self.target_display.setParent(None)
        self.mask_tab.setParent(None)
        self.wavelength_view.setParent(None)

        # --- Create new widgets ---
        self.target_display = TargetDisplayWidget()
        self.interactive_slit_mask = interactiveSlitMask()
        self.slit_position_table = SlitDisplay()
        self.wavelength_view = WavelengthView()
        self.mask_tab = QTabWidget()
        self.mask_tab.addTab(self.interactive_slit_mask,"Slit Mask")
        self.mask_tab.addTab(self.wavelength_view,"Spectral View")
        self.mask_tab.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        # --- Reconnect signals ---
        self.slit_position_table.highlight_other.connect(self.interactive_slit_mask.select_corresponding_row)
        self.interactive_slit_mask.row_selected.connect(self.slit_position_table.select_corresponding)
        self.interactive_slit_mask.row_selected.connect(self.wavelength_view.select_corresponding_row)
        self.target_display.selected_le_star.connect(self.interactive_slit_mask.get_row_from_star_name)
        self.interactive_slit_mask.select_star.connect(self.target_display.select_corresponding)
        self.wavelength_view.row_selected.connect(self.interactive_slit_mask.select_corresponding_row)

        # --- readd to layout --- 
        self.layoutH1.addWidget(self.slit_position_table)
        self.layoutH1.addWidget(self.mask_tab)
        self.splitterV1.insertWidget(1, self.target_display)
        

    

if __name__ == '__main__':
    app = QApplication(sys.argv)

    with open("slitmaskgui/styles.qss", "r") as f:
        _style = f.read()
    app.setStyleSheet(_style)
    

    window = MainWindow()
    window.show()
    app.exec()