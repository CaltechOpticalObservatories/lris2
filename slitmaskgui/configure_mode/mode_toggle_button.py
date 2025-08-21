from PyQt6.QtWidgets import QPushButton, QWidget, QVBoxLayout, QDialog, QSizePolicy, QHBoxLayout
from PyQt6.QtCore import pyqtSignal, QSize
from slitmaskgui.configure_mode.csu_worker import CSUWorkerThread
from slitmaskgui.configure_mode.mask_controller import MaskControllerWidget
from lris2csu.remote import CSURemote


"""
will define in a better way later
"""
remote = CSURemote('tcp://131.215.200.105:5571')


class ShowControllerButton(QWidget):
    get_from_mask_config = pyqtSignal(object)
    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        print(self.minimumSize())
        self.button = QPushButton("Toggle Configure Mode")
        # self.button.clicked.connect(self.on_button_clicked)
        self.button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Maximum)
        print(self.button.minimumSize())


        layout = QHBoxLayout()
        layout.addWidget(self.button)
        self.setLayout(layout)
    
    def sizeHint(self):
        return QSize(100, 60) 

    
    def connect_controller_with_config(self, mask_controller_class, mask_config_class): #change this to connect to specific class
        self.mask_class = mask_config_class
        self.controller_class = mask_controller_class
        self.get_from_mask_config.connect(self.mask_class.emit_last_used_slitmask)
        self.mask_class.send_to_csu.connect(self.controller_class.define_slits)

    
    def start_communication(self):
        self.get_from_mask_config.emit("Start Communication")

    def on_button_clicked(self):
        #handle button click
        self.start_communication()
        print("Configure mode toggle button was clicked!")
    
    





