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
from slitmaskgui.mask_widgets.slitmask_view import interactiveSlitMask
from slitmaskgui.mask_widgets.waveband_view import WavelengthView
from slitmaskgui.mask_widgets.sky_viewer import SkyImageView
from slitmaskgui.mask_configurations import MaskConfigurationsWidget
from slitmaskgui.slit_position_table import SlitDisplay
from slitmaskgui.mask_widgets.mask_view_tab_bar import TabBar
from slitmaskgui.configure_mode.mode_toggle_button import ShowControllerButton
from slitmaskgui.configure_mode.mask_controller import MaskControllerWidget
from slitmaskgui.configure_mode.csu_display_widget import CsuDisplauWidget
from slitmaskgui.offline_mode import OfflineMode
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QStackedLayout


)

#need to add something that will query where the stars will be depending on the time of day
main_logger = logging.getLogger()
main_logger.info("starting logging")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LRIS-2 Slit Configuration Tool")
        self.setGeometry(100,100,1200,790)
        self.setMenuBar(MenuBar()) #sets the menu bar
        self.update_theme()
        
        
        #----------------------------definitions---------------------------
        main_logger.info("app: doing definitions")

        self.connection_status = OfflineMode()
        self.start_checking_internet_connection()
        
        mask_config_widget = MaskConfigurationsWidget()
        mask_gen_widget = MaskGenWidget()
        self.mode_toggle_button = ShowControllerButton()
        mask_controller_widget = MaskControllerWidget()
        csu_display_widget = CsuDisplauWidget()
        
        self.target_display = TargetDisplayWidget()
        self.interactive_slit_mask = interactiveSlitMask()
        self.slit_position_table = SlitDisplay()
        self.wavelength_view = WavelengthView()
        self.sky_view = SkyImageView()

        #------------- stacked layout in mask_tab --------------------
        self.slitmask_and_csu_display = QStackedLayout()
        self.slitmask_and_csu_display.addWidget(self.interactive_slit_mask)
        self.slitmask_and_csu_display.addWidget(csu_display_widget)

        self.mask_tab = TabBar(slitmask_layout=self.slitmask_and_csu_display,waveview=self.wavelength_view,skyview=self.sky_view)

        #---------------------------------connections-----------------------------
        main_logger.info("app: doing connections")
        self.slit_position_table.highlight_other.connect(self.interactive_slit_mask.select_corresponding_row)
        self.interactive_slit_mask.row_selected.connect(self.slit_position_table.select_corresponding)
        self.interactive_slit_mask.row_selected.connect(self.wavelength_view.select_corresponding_row)
        self.target_display.selected_le_star.connect(self.interactive_slit_mask.get_row_from_star_name)
        self.interactive_slit_mask.select_star.connect(self.target_display.select_corresponding)
        self.wavelength_view.row_selected.connect(self.interactive_slit_mask.select_corresponding_row)
        self.interactive_slit_mask.new_slit_positions.connect(self.mask_tab.initialize_spectral_view)

        mask_gen_widget.change_data.connect(self.target_display.change_data)
        mask_gen_widget.change_slit_image.connect(self.interactive_slit_mask.update_slit_and_star)
        mask_gen_widget.change_row_widget.connect(self.slit_position_table.change_data)
        mask_gen_widget.send_mask_config.connect(mask_config_widget.initialize_configuration)

        mask_config_widget.change_data.connect(self.target_display.change_data)
        mask_config_widget.change_row_widget.connect(self.slit_position_table.change_data)
        mask_config_widget.change_slit_image.connect(self.interactive_slit_mask.update_slit_and_star)
        mask_config_widget.reset_scene.connect(self.reset_scene)
        mask_config_widget.update_image.connect(self.sky_view.update_image)
        mask_config_widget.change_name_above_slit_mask.connect(self.interactive_slit_mask.update_name_center_pa)

        #if the data is changed connections
        self.slit_position_table.tell_unsaved.connect(mask_config_widget.update_table_to_unsaved)
        mask_config_widget.data_to_save_request.connect(self.slit_position_table.data_saved)
        self.slit_position_table.data_changed.connect(mask_config_widget.save_data_to_mask)

        #sending to csu connections
        self.mode_toggle_button.connect_controller_with_config(mask_controller_widget,mask_config_widget)
        mask_controller_widget.connect_controller_with_slitmask_display(csu_display_widget)
        self.mode_toggle_button.button.clicked.connect(self.mode_toggle_button.on_button_clicked)
        self.mode_toggle_button.button.clicked.connect(self.switch_modes)

        self.connection_status.current_mode.connect(self.switch_internet_connection_mode)


        #-----------------------------------layout-----------------------------
        main_logger.info("app: setting up layout")
        self.layoutH1 = QHBoxLayout() #Contains slit position table and interactive slit mask
        self.splitterV1 = QSplitter()
        main_splitter = QSplitter()
        self.splitterV2 = QSplitter()
        self.mask_viewer_main = QVBoxLayout()
        self.stacked_layout = QStackedLayout()
        switcher_widget = QWidget()

        self.stacked_layout.addWidget(mask_gen_widget)
        self.stacked_layout.addWidget(mask_controller_widget)
        switcher_widget.setLayout(self.stacked_layout)

        self.interactive_slit_mask.setContentsMargins(0,0,0,0)
        self.slit_position_table.setContentsMargins(0,0,0,0)
        self.slit_position_table.setMinimumHeight(1)
        self.mask_tab.setMinimumSize(1,1)
        mask_config_widget.setMinimumSize(1,1)
        mask_gen_widget.setMinimumSize(1,1)

        self.splitterV2.addWidget(mask_config_widget)
        self.splitterV2.addWidget(switcher_widget)
        self.splitterV2.addWidget(self.mode_toggle_button)
        self.splitterV2.setOrientation(Qt.Orientation.Vertical)
        self.splitterV2.setContentsMargins(0,0,0,0)

        self.layoutH1.addWidget(self.slit_position_table)
        self.layoutH1.addWidget(self.mask_tab)
        self.layoutH1.setSpacing(0)
        self.layoutH1.setContentsMargins(9,9,9,9)
        widgetH1 = QWidget()
        widgetH1.setLayout(self.layoutH1)

        self.splitterV1.addWidget(widgetH1)
        self.splitterV1.addWidget(self.target_display)
        self.splitterV1.setOrientation(Qt.Orientation.Vertical)
        self.splitterV1.setContentsMargins(0,0,0,0)

        main_splitter.addWidget(self.splitterV1)
        main_splitter.addWidget(self.splitterV2)

        self.setCentralWidget(main_splitter)
        self.setContentsMargins(9,9,9,9)

        #--------------------------change theme-----------------------------
        QApplication.instance().styleHints().colorSchemeChanged.connect(self.update_theme)


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
    
    def update_theme(self):
        theme = QApplication.instance().styleHints().colorScheme()
        if theme == Qt.ColorScheme.Dark:
            with open("slitmaskgui/dark_mode.qss", "r") as f:
                self.setStyleSheet(f.read())
        elif theme == Qt.ColorScheme.Light:
            with open("slitmaskgui/light_mode.qss", "r") as f:
                self.setStyleSheet(f.read())
        else:
            with open("slitmaskgui/dark_mode.qss", "r") as f:
                self.setStyleSheet(f.read())
    
    def switch_modes(self):
        index = abs(self.stacked_layout.currentIndex()-1)
        self.stacked_layout.setCurrentIndex(index)
        self.slitmask_and_csu_display.setCurrentIndex(index)
        button_text = "Configuration Mode (ON)" if index == 1 else "Configuration Mode (OFF)"
        self.mode_toggle_button.button.setText(button_text)

    def start_checking_internet_connection(self):
        self.connection_status.start_checking_internet_connection()
        self.connection_status.start_timer()
        
    def switch_internet_connection_mode(self):
        self.sky_view.offline = self.connection_status.offline
        self.setWindowTitle(f"LRIS-2 Slit Configuration Tool ({repr(self.connection_status)})")
        
        
    
        


if __name__ == '__main__':
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()
    app.exec()