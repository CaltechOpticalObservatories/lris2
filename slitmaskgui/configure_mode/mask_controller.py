import sys
from typing import Tuple
from PyQt6.QtWidgets import ( QVBoxLayout, QGraphicsView, QGraphicsScene,
    QComboBox, QPushButton, QHBoxLayout, QSplitter, QDialog, QSizePolicy,
    QWidget, QGroupBox, QLabel, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPainter
from lris2csu.remote import CSURemote
from lris2csu.slit import Slit, MaskConfig

from logging import basicConfig, DEBUG, getLogger
from slitmaskgui.configure_mode.csu_worker import CSUWorkerThread  # Import the worker thread

basicConfig(level=DEBUG)
getLogger('mktl').setLevel(DEBUG)
logger = getLogger('mktl')

registry = 'tcp://131.215.200.105:5571'
remote = CSURemote(registry)
PLATE_SCALE = 0.7272
CSU_WIDTH = PLATE_SCALE*60*5

class MaskControllerWidget(QWidget):
    connect_with_slitmask_display = pyqtSignal()
    def __init__(self):
        super().__init__()

        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding
        )
        #------------------------definitions----------------------------
        self.remote_label = QLabel("Registry:")
        self.remote_add = QLineEdit(registry)
        self.configure_button = QPushButton("Configure")
        self.stop_button = QPushButton("Stop")
        self.calibrate_button = QPushButton("Calibrate")
        self.reset_button = QPushButton("Reset")
        self.shutdown_button = QPushButton("Shutdown")
        self.status_button = QPushButton("Status")

        self.c = remote
        self.worker_thread = CSUWorkerThread(remote)

        self.bar_pairs = []
        #-----------------------------connections---------------------------
        self.configure_button.clicked.connect(self.update_slit_configuration)
        self.stop_button.clicked.connect(self.stop_process)
        self.calibrate_button.clicked.connect(self.calibrate)
        self.reset_button.clicked.connect(self.reset_configuration)
        self.shutdown_button.clicked.connect(self.shutdown)
        self.status_button.clicked.connect(self.show_status)

        self.worker_thread.calibrate_signal.connect(self.handle_calibration_done)
        self.worker_thread.status_signal.connect(self.handle_status_updated)
        #------------------------------------------layout-------------------------
        logger.info("mask_gen_widget: defining the layout")
        group_box = QGroupBox("CONFIGURATION MODE")
        main_layout = QVBoxLayout()
        group_layout = QVBoxLayout()

        group_layout.addWidget(self.remote_label)
        group_layout.addWidget(self.remote_add)
        group_layout.addWidget(self.configure_button)
        group_layout.addWidget(self.stop_button)
        group_layout.addWidget(self.calibrate_button)
        group_layout.addWidget(self.reset_button)
        group_layout.addWidget(self.shutdown_button)
        group_layout.addWidget(self.status_button)

        group_box.setLayout(group_layout)

        main_layout.setContentsMargins(9,4,9,9)
        main_layout.addWidget(group_box)

        self.setLayout(main_layout)
        #-----------------------------------------------
    
    def sizeHint(self):
        return QSize(300,400)
    
    def connect_controller_with_slitmask_display(self, mask_controller_class, slitmask_display_class):
        self.slitmask_display = slitmask_display_class
        self.controller_class = mask_controller_class
        self.connect_with_slitmask_display.connect(self.slitmask_display.handle_configuration_mode)
        self.slitmask_display.connect_with_controller.connect(self.controller_class.define_slits)
        

    
    def update_slitmask_display(self,pos_dict):
        self.slitmask_display.change_slit_and_star(pos_dict) # should be pos_dict
    
    def define_slits(self,slits):
        print("Communication successful")
        try:
            self.slits = slits[:10]
            self.slits = [(star["x_mm"],bar_id,star["slit_width"]) for bar_id,star in enumerate(self.slits)]
        except:
            print("no mask config found")
    
    def update_slit_configuration(self):
        """Update slit configuration based on the selected dropdown option."""
        # Clear existing bars
        for bar_pair in self.bar_pairs:
            self.scene.removeItem(bar_pair.left_rect)
            self.scene.removeItem(bar_pair.right_rect)

        self.bar_pairs.clear()  # Clear the list of bar pairs

        # Get the selected mask type from the dropdown

        self.c.configure(MaskConfig(slits), speed=6500)

    def reset_configuration(self):
        """Reset the configuration to a default state."""
        # Reset to "Stair Mask"
        print("Resetting CSU...")
        # self.update_slit_configuration()
        self.c.reset()

    def calibrate(self):
        """Start the calibration process in the worker thread."""
        print("Starting calibration in worker thread...")
        self.worker_thread.set_task("calibrate")
        self.worker_thread.start()

    def handle_calibration_done(self, response):
        """Handle calibration completion."""
        print(f"Calibration completed: {response}")
        # Update UI accordingly, e.g., show a message or update a label

    def handle_status_updated(self, slits):
        """Update GUI with slits returned from CSUWorkerThread."""
        if not slits:
            print("No slits received.")
            return

        # Clear existing bars
        for bar_pair in self.bar_pairs:
            self.scene.removeItem(bar_pair.left_rect)
            self.scene.removeItem(bar_pair.right_rect)

        self.bar_pairs.clear()  # Clear the list of bar pairs

        # Create new bar pairs based on the received slits
        self.bar_pairs = [BarPair(self.scene, slit) for slit in slits]

        print("Scene updated with new slit configuration.")

    def handle_error(self, error_message):
        """Handle error in the worker thread."""
        print(f"Error occurred: {error_message}")
        # Display error in the UI, e.g., using a dialog

    def shutdown(self):
        """Shutdown the application."""
        self.quit()
        self.c.shutdown()

    def show_status(self):
        """Request slit status from worker thread."""
        print("Requesting status in worker thread...")
        self.worker_thread.set_task("status")
        self.worker_thread.start()

    def stop_process(self):
        """Stop the process by sending the stop command to CSURemote."""
        print("Stopping the process...")
        self.c.stop()

    def parse_response(self, response):
        """Parse the response to extract the mask data."""
        try:
            # Access the last element of the response to get the MaskConfig object
            mask_config = response[-1]  # Using dot notation instead of dictionary access
            slits = mask_config.slits
            log_message = f"Extracted MaskConfig: {mask_config}"
            print(log_message)
            print(f"Slits: {slits}")
            return slits
        except (IndexError, AttributeError) as e:
            # Handle cases where the structure is not as expected
            error_message = f"Error parsing response: {e}"
            print(error_message)
            return None
