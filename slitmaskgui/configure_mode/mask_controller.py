import sys
from typing import Tuple
from PyQt6.QtWidgets import ( QVBoxLayout, QGraphicsView, QGraphicsScene,
    QComboBox, QPushButton, QHBoxLayout, QSplitter, QDialog, QSizePolicy,
    QWidget, QGroupBox, QLabel, QLineEdit, QDialogButtonBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer, QThreadPool
from PyQt6.QtGui import QPainter
from lris2csu.remote import CSURemote
from lris2csu.slit import Slit, MaskConfig
from slitmaskgui.mask_widgets.mask_objects import ErrorWidget
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

publish_socket = "tcp://131.215.200.105:5559"


def timeout_function(self, e):
    text = f"{e}\nMake sure you are connected to the CSU"
    self.error_widget = ErrorWidget(text)
    self.error_widget.show()


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
        self.worker_thread.slit_config_updated_signal.connect(self.handle_config_update)


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
        #--------------------- Timer & Threadpool --------------------------
        self.timer = QTimer()
        self.timer.setInterval(1500)
        self.timer.timeout.connect(self.still_run)
        self.old_config = None
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

    def identify_problem_slits(self):
        try:
            self.show_status()
        except:
            pass
        """ !PROBLEM SLITS! !PROBLEM SLITS! """ 
        """ !PROBLEM SLITS! !PROBLEM SLITS! """ 
        """ !PROBLEM SLITS! !PROBLEM SLITS! """ 
        problem_slits = [8] # manally edit this list during the dry run if any are acting up (you can check which ones are acting up by using status)
        """ !PROBLEM SLITS! !PROBLEM SLITS! """ 
        """ !PROBLEM SLITS! !PROBLEM SLITS! """ 
        """ !PROBLEM SLITS! !PROBLEM SLITS! """
        slits_status = self.worker_thread.slits
        set_slits = []
        for problem in problem_slits:
            [set_slits.append(slit) for slit in slits_status
             if slit.id == problem]
             #Hopefully this works
        print(set_slits) 
        return set_slits

    def define_slits(self,slits):
        try:
            self.slits = slits[:12]
            self.slits = tuple([Slit(bar_id,CSU_WIDTH/2+star["x_mm"],float(star["slit_width"])/PLATE_SCALE) # CSU_WIDTH + star because star could be negative
                        for bar_id,star in enumerate(self.slits)])
        except:
            print("no mask config found")
    def replace_problem_slits(self):
        set_slits = self.identify_problem_slits()

        new_slit_list = []
        problem_id_list = [slit.id for slit in set_slits]
        for slit in self.slits:
            if slit.id in problem_id_list:
                [new_slit_list.append(problem) for problem in set_slits if slit.id == problem.id]
            else:
                new_slit_list.append(slit)
        self.slits = new_slit_list
        
    def configure_slits(self):
        self.replace_problem_slits()
        print(self.slits)
        try:
            self.worker_thread.set_task("configure")
            self.worker_thread.configure_csu(self.slits)
        except AttributeError as e:
            text = f"{e}\nGenerate a Mask Configuration before configuring CSU"
            self.error_widget = ErrorWidget(text)
            self.error_widget.show()
        except TimeoutError as e:
            timeout_function(self, e)
    def still_run(self):
        self.current_config = repr(self.worker_thread)
        self.show_status()
        
        if self.current_config == self.old_config:
            self.timer.stop()

        self.old_config = self.current_config


    def reset_configuration(self):
        """Reset the configuration to a default state."""
        # Reset to "Stair Mask"
        print("Resetting CSU...")
        # self.update_slit_configuration()
        try:
            response = self.c.reset()
        except TimeoutError as e:
            timeout_function(self, e)
            response = e
        print(f'reset config {response}')

    def calibrate(self):
        """Start the calibration process in the worker thread."""
        print("Starting calibration in worker thread...")
        self.worker_thread.set_task("calibrate")
        self.worker_thread.start()

    def handle_calibration_done(self, response):
        """Handle calibration completion."""
        print(f"Calibration completed: {response}")
        self.timer.setInterval(1000)
        self.timer.start()
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
    
    def handle_config_update(self,response):
        print(f'Configuration started: {response}')
        self.timer.setInterval(750)
        self.timer.start()


    def shutdown(self):
        """Shutdown the application."""
        try:
            self.c.shutdown()
        except TimeoutError as e:
            timeout_function(self, e)

    def show_status(self):
        """Request slit status from worker thread."""
        print("Requesting status in worker thread...")
        self.worker_thread.set_task("status")
        self.worker_thread.start()

    def stop_process(self):
        """Stop the process by sending the stop command to CSURemote."""
        print("Stopping the process...")
        try:
            response = self.c.stop()
        except TimeoutError as e:
            timeout_function(self, e)
            response = e
        print(f"stop process {response}")
        try:
            self.timer.stop()
        except:
            pass #timer already stopped
    
