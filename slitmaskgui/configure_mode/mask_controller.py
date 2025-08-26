import sys
from typing import Tuple
from PyQt6.QtWidgets import ( QVBoxLayout, QGraphicsView, QGraphicsScene,
    QComboBox, QPushButton, QHBoxLayout, QSplitter, QDialog, QSizePolicy,
    QWidget, QGroupBox, QLabel, QLineEdit, QDialogButtonBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QPainter
from lris2csu.remote import CSURemote
from lris2csu.slit import Slit, MaskConfig
import time

from logging import basicConfig, DEBUG, getLogger
from slitmaskgui.configure_mode.csu_worker import CSUWorkerThread  # Import the worker thread


# basicConfig(filename='mktl.log', format='%(asctime)s %(message)s', filemode='w', level=DEBUG)
basicConfig(level=DEBUG)
getLogger('mktl').setLevel(DEBUG)
logger = getLogger('mktl')

registry = 'tcp://131.215.200.105:5571'
remote = CSURemote(registry_address=registry)
PLATE_SCALE = 0.7272
CSU_WIDTH = PLATE_SCALE*60*5


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


class MaskControllerWidget(QWidget):
    connect_with_slitmask_display = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Ignored
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
        self.slits = 0
        #-----------------------------connections---------------------------
        self.configure_button.clicked.connect(self.configure_slits)
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
        group_layout.addStretch(40)
        group_box.setLayout(group_layout)

        main_layout.setContentsMargins(9,4,9,9)
        main_layout.addWidget(group_box)

        self.setLayout(main_layout)
        #-----------------------------------------------
        #------------------------setting size hints for widgets------------------
        uniform_size_policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        [
            self.layout().itemAt(i).widget().setSizePolicy(uniform_size_policy)
            for i in range(self.layout().count())
        ]
    
    def sizeHint(self):
        return QSize(300,400)
    
    def connect_controller_with_slitmask_display(self, slitmask_display_class):
        self.slitmask_display = slitmask_display_class
        self.connect_with_slitmask_display.connect(self.slitmask_display.handle_configuration_mode)
        self.slitmask_display.connect_with_controller.connect(self.define_slits)

    def define_slits(self,slits):
        try:
            self.slits = slits[:12]
            self.slits = tuple([Slit(bar_id,CSU_WIDTH/2+star["x_mm"],float(star["slit_width"])) # CSU_WIDTH + star because star could be negative
                        for bar_id,star in enumerate(self.slits)])
        except:
            print("no mask config found")

    def configure_slits(self):
        try:
            self.get_status_of_moving_bars()
            self.c.configure(MaskConfig(self.slits), speed=6500)
            
        except AttributeError as e:
            text = """Generate a Mask Configuration before configuring CSU"""
            self.error_widget = ErrorWidget(text)
            self.error_widget.show()
            if self.error_widget.exec() == QDialog.DialogCode.Accepted:
                pass
        except TimeoutError as e:
            text = f"{e}"
            self.error_widget = ErrorWidget(text)
            self.error_widget.show()
    
    def get_status_of_moving_bars(self):
        # Something with Qtimer becuase I don't think it freezes the system
        # Every lets say 3 seconds query what the status is and then update it
        # Have to check if the status is the same between queries so we don't have unecessary 

        # extra_thread = Qthreadclass(self.worker_thread) #then have it do what is below and you can use time.sleep()
            
        pass

    def reset_configuration(self):
        """Reset the configuration to a default state."""
        # Reset to "Stair Mask"
        print("Resetting CSU...")
        # self.update_slit_configuration()
        try:
            self.c.reset()
        except TimeoutError as e:
            text = f"{e}"
            self.error_widget = ErrorWidget(text)
            self.error_widget.show()

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

        self.slitmask_display.get_slits(slits)

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
    def animate_bars(self):
        pass
