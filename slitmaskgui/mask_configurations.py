"""
This is a widget that will display all the masks that have been imported and if they have been saved.
A button at the bottom to save the mask, and one right next to it to save all the masks
3 buttons on the top: open, copy, close
"""

import json
import os
import logging
from slitmaskgui.backend.star_list import StarList
from PyQt6.QtCore import Qt, QAbstractTableModel,QSize, QModelIndex, pyqtSlot, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QPushButton,
    QGroupBox,
    QTableView,
    QSizePolicy,
    QHeaderView,
    QFileDialog,


)
config_logger = logging.getLogger(__name__)

class Button(QPushButton):
    def __init__(self,w,h,text):
        super().__init__()
        self.setText(text)
        self.setBaseSize(w,h)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setContentsMargins(0,0,0,0)
        # self.setStyleSheet("border: 1px solid; background-color: #ADD8E6")

class TableModel(QAbstractTableModel):
    def __init__(self, data=[]):
        super().__init__()
        self._data = data
        self.headers = ["Status","Name"]

    def headerData(self, section, orientation, role = ...):
        if role == Qt.ItemDataRole.DisplayRole:
            #should add something about whether its vertical or horizontal
            if orientation == Qt.Orientation.Horizontal:
                
                return self.headers[section]
                
            if orientation == Qt.Orientation.Vertical:
                return None
        
        
        return super().headerData(section, orientation, role)

    def data(self, index, role):
        if role == Qt.ItemDataRole.DisplayRole:
            return self._data[index.row()][index.column()]
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter
        return None
    
    def removeRow(self, row, count=1, parent=QModelIndex()):
        if 0 <= row < len(self._data):
            self.beginRemoveRows(parent, row, row)
            del self._data[row]
            self.endRemoveRows()
            return True
        return False

    def get_num_rows(self):
        return len(self._data)
    def get_row_num(self,index):
        if len(index) > 0:
            return index[0].row()
        return None

    def rowCount(self, index):
        return len(self._data)
    def columnCount(self, index):
        return 2
    
class CustomTableView(QTableView):
    def __init__(self):
        super().__init__()
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(0)
        #self.setEditTriggers(QTableView.EditTrigger.DoubleClicked)

        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        

    def setResizeMode(self):
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

    def setModel(self, model):
        super().setModel(model)
        self.setResizeMode()


        return 2
    




#I am unsure of whether to go with a abstract table model or an abstract list model
class MaskConfigurationsWidget(QWidget):
    change_data = pyqtSignal(list)
    change_slit_image = pyqtSignal(dict)
    change_row_widget = pyqtSignal(list)
    reset_scene = pyqtSignal(bool)
    def __init__(self):
        super().__init__()
        
        
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred
        )

        #--------------------------------Definitions---------------------
        title = QLabel("MASK CONFIGURATIONS")

        open_button = Button(80,30,"Open")
        save_button = Button(80,30,"Save")
        close_button = Button(80,30,"Close")

        export_button = Button(120,30,"Export")
        export_all_button = Button(120,30,"Export All")

        self.table = CustomTableView()
        self.model = TableModel()
        self.table.setModel(self.model)

        self.row_to_config_dict = {}

        #------------------------connections-----------------
        open_button.clicked.connect(self.open_button_clicked)
        save_button.clicked.connect(self.save_button_clicked)
        close_button.clicked.connect(self.close_button_clicked)
        export_button.clicked.connect(self.export_button_clicked)
        export_all_button.clicked.connect(self.export_all_button_clicked)
        self.table.selectionModel().selectionChanged.connect(self.selected) #sends the row number for the selected item

        #-------------------layout-------------------
        group_box = QGroupBox()
        main_layout = QVBoxLayout()
        group_layout = QVBoxLayout()
        top_hori_layout = QHBoxLayout()
        bot_hori_layout = QHBoxLayout()

        top_hori_layout.addWidget(open_button)
        top_hori_layout.addWidget(save_button)
        top_hori_layout.addWidget(close_button)
        top_hori_layout.setSpacing(0)

        bot_hori_layout.addWidget(export_button)
        bot_hori_layout.addWidget(export_all_button)
        bot_hori_layout.setSpacing(0)

        group_layout.addLayout(top_hori_layout)
        group_layout.addWidget(self.table)
        group_layout.addLayout(bot_hori_layout)
        group_layout.setSpacing(0)
        group_layout.setContentsMargins(0,0,0,0)

        group_box.setLayout(group_layout)
        group_box.setContentsMargins(2,0,2,0)
        
        main_layout.addWidget(title,alignment=Qt.AlignmentFlag.AlignHCenter)
        main_layout.addWidget(group_box)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0,0,0,0)

        self.setLayout(main_layout)
        #------------------------------------------------
    def sizeHint(self):
        return QSize(300,100)
    
    def open_button_clicked(self):
        config_logger.info(f"mask configurations: start of open button function {self.row_to_config_dict}")

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select a File",
            "",
            "All files (*)" #will need to make sure it is a specific file
        )
        #update this with the row to json dict thing
        try:
            if file_path: 
                with open(file_path,'r') as f:
                    temp = f.read()
                    data = json.loads(temp)
                mask_name = os.path.splitext(os.path.basename(file_path))[0]
                self.update_table((mask_name,data)) #doesn't work right now
                config_logger.info(f"mask_configurations: open button clicked {mask_name} {file_path}")
                #in the future this will take the mask config file and take the name from that file and display it
                #it will also auto select itself and display the mask configuration on the interactive slit mask
        except:
            pass
        config_logger.info(f"mask configurations: end of open button function {self.row_to_config_dict}")


    def save_button_clicked(self,item):
        #This will update the mask configuration file to fit the changed mask
        #can't make any edits to the data currently so i'll just wait to do this one
        print("save button clicked")
        pass

    def close_button_clicked(self,item):
        #this will delete the item from the list and the information that goes along with it
        #get selected item
        config_logger.info(f"mask configurations: start of close button function {self.row_to_config_dict}")
        row_num = self.model.get_row_num(self.table.selectedIndexes())
        if row_num is None:
            config_logger.warning("No row selected for removal.")
            return
        else:
            del self.row_to_config_dict[row_num]
            self.model.beginResetModel()
            self.model.removeRow(row_num)
            self.model.endResetModel()
        if not self.row_to_config_dict:
            config_logger.info("mask configuratios: reseting scene")
            self.reset_scene.emit(True)
            

    def export_button_clicked(self): #should probably change to export to avoid confusion with saved/unsaved which is actually updated/notupdated
        #this will save the current file selected in the table
        config_logger.info(f"mask configurations: start of export button function {self.row_to_config_dict}")
        row_num = self.model.get_row_num(self.table.selectedIndexes()) #this gets the row num
        try:
            index = self.model.index(row_num, 1)
            name = self.model.data(index,Qt.ItemDataRole.DisplayRole)
        except:
            #index has recieved nonetype
            pass
        if row_num is None:
            config_logger.warning("No row selected for export.")
            return
        else:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save File",
                f"{name}",
                "JSON Files (*.json)"
            )
            if file_path:
                data = json.dumps(self.row_to_config_dict[row_num])
                star_list = StarList(data,RA="00 00 00.00",Dec="+00 00 00.00",slit_width=0.7,auto_run=False)
                mask_name = os.path.splitext(os.path.basename(file_path))
                star_list.export_mask_config(file_path=file_path)

        config_logger.info(f"mask configurations: end of export button function {self.row_to_config_dict}")
        

    def export_all_button_clicked(self):
        #this will save all unsaved files
        row_num = self.model.get_row_num(self.table.selectedIndexes())

    pyqtSlot(name="update_table")
    def update_table(self,info=None):
        #the first if statement is for opening a mask file and making a mask in the gui which will be automatically added
        config_logger.info(f"mask configurations: start of update table function {self.row_to_config_dict}")
        if info is not None: #info for now will be a list [name,file_path]
            name, mask_info = info[0], info[1]
            self.model.beginResetModel()
            self.model._data.append(["Saved",name])
            self.model.endResetModel()
            row_num = self.model.get_num_rows() -1
            self.row_to_config_dict.update({row_num: mask_info})
            self.table.selectRow(row_num)
        else:
            print("will change thing to saved")
        config_logger.info(f"mask configurations: end of update table function {self.row_to_config_dict}")
        # when a mask configuration is run, this will save the data in a list
    @pyqtSlot(name="selected file path")
    def selected(self):
        #will update the slit mask depending on which item is selected
        if len(self.row_to_config_dict) >0:
            row = self.model.get_row_num(self.table.selectedIndexes())
            config_logger.info(f"mask_configurations: row is selected function {row} {self.row_to_config_dict}")
            data = json.dumps(self.row_to_config_dict[row])

            slit_mask = StarList(data,ra="00 00 00.00",dec="+00 00 00.00",slit_width=0.7,auto_run=False)
            interactive_slit_mask = slit_mask.send_interactive_slit_list()

            self.change_slit_image.emit(interactive_slit_mask)

            self.change_data.emit(slit_mask.send_target_list())
            self.change_row_widget.emit(slit_mask.send_row_widget_list())

        




