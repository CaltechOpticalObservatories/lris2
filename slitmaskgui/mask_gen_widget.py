
from slitmaskgui.input_targets import TargetList
from slitmaskgui.backend.star_list import StarList
from slitmaskgui.backend.sample import query_gaia_starlist_rect
import re
from PyQt6.QtCore import QObject, pyqtSignal, Qt, QSize
from PyQt6.QtWidgets import (
    QFileDialog,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QStackedLayout,
    QLineEdit,
    QFormLayout,
    QGroupBox,
    QBoxLayout,
    QSizePolicy,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    
)

#need to add another class to load parameters from a text file



class MaskGenWidget(QWidget):
    change_data = pyqtSignal(list)
    change_slit_image = pyqtSignal(dict)
    change_row_widget = pyqtSignal(list)
    def __init__(self):
        super().__init__()

        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding
        )

        #------------------------definitions----------------------------
        import_target_list_button = QPushButton(text = "Import Target List")
        name_of_mask = QLineEdit()
        self.center_of_mask = QLineEdit("00 00 00.00 +00 00 00.00")
        self.slit_width = QLineEdit("0.7")
        run_button = QPushButton(text="Run")
        
        #worry about the formatting of center_of_mask later

        #-----------------------------connections---------------------------
        import_target_list_button.clicked.connect(self.starlist_file_button_clicked)
        run_button.clicked.connect(self.run_button)

        #------------------------------------------layout-------------------------
        group_box = QGroupBox()
        main_layout = QVBoxLayout()
        secondary_layout = QFormLayout() #above import targets
        below_form_layout = QFormLayout()
        below_layout = QHBoxLayout() # displayed below import targets
        unit_layout = QVBoxLayout()
        group_layout = QVBoxLayout()
        group_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        name_of_mask.setAlignment(Qt.AlignmentFlag.AlignTop)
        import_target_list_button.setFixedSize(150,40)
        run_button.setFixedSize(150,30)

        secondary_layout.addRow("Mask Name:",name_of_mask)
        below_form_layout.addRow("Slit Width:",self.slit_width)
        below_form_layout.addRow("Center Ra/Dec:", self.center_of_mask)
        unit_layout.addWidget(QLabel("arcsec")) #units for slit width
        unit_layout.addWidget(QLabel("h m s ° ' \"")) #units for center of mask
        
        below_layout.addLayout(below_form_layout)
        below_layout.addLayout(unit_layout)
        group_layout.addLayout(secondary_layout)

        group_layout.addWidget(import_target_list_button, alignment=Qt.AlignmentFlag.AlignCenter)
        group_layout.addLayout(below_layout)
        group_layout.addStretch(40)
        group_layout.addWidget(run_button, alignment=Qt.AlignmentFlag.AlignBottom| Qt.AlignmentFlag.AlignCenter)
        group_box.setLayout(group_layout)

        title = QLabel("MASK GENERATION")
        main_layout.addWidget(title)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.addWidget(group_box)

        self.setLayout(main_layout)
        #-----------------------------------------------
    
    def sizeHint(self):
        return QSize(300,400)
        

    def starlist_file_button_clicked(self):
        text_file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select a File",
            "",
            "All files (*)" 
        )

        if text_file_path: 
            self.file_path = text_file_path


        
    def run_button(self):
        #this right now will generate a starlist depending on center to speed up testing
        path_to_file = self.file_path
        path_to_file = "/Users/austinbowman/lris2/gaia_starlist.txt"


        center = re.match(r"(?P<Ra>\d{2} \d{2} \d{2}\.\d{2}(?:\.\d+)?) (?P<Dec>[\+|\-]\d{2} \d{2} \d{2}(?:\.\d+)?)",self.center_of_mask.text())
        ra = center.group("Ra")
        dec = center.group("Dec")
        width = self.slit_width.text()


        query_gaia_starlist_rect(
            ra_center=ra,              # RA in degrees
            dec_center=dec,               # Dec in degrees
            width_arcmin=5,
            height_arcmin=10,
            n_stars=104,
            output_file='gaia_starlist.txt'
            )

        #--------------------------connections ----------
        target_list = TargetList(path_to_file)
        slit_mask = StarList(target_list.send_json(),ra,dec,slit_width=width)
        interactive_slit_mask = slit_mask.send_interactive_slit_list()

        self.change_slit_image.emit(interactive_slit_mask)

        self.change_data.emit(slit_mask.send_target_list())
        self.change_row_widget.emit(slit_mask.send_row_widget_list())
        #--------------------------------------------------------------------------






            

            