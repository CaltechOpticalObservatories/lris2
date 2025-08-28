"""
this will display all the slit positions as well as the bar number and then width
additionally, when you click on the slits, it will highlight the corresponding bar in the 
interactive image and highlight the corresponding star in the target list table
"""

from slitmaskgui.menu_bar import MenuBar
import logging
import itertools
from PyQt6.QtCore import Qt, QAbstractTableModel, pyqtSlot, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QWidget,
    QTableView,
    QVBoxLayout,
    QTableWidget,
    QSizePolicy,
    QLabel,
    QHeaderView,
    QFrame,
    QAbstractScrollArea,


)

logger = logging.getLogger(__name__)

class TableModel(QAbstractTableModel):
    def __init__(self, data=[]):
        super().__init__()
        self._data = data
        self.headers = ["Row","Center","Width"]
    def headerData(self, section, orientation, role = ...):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return self.headers[section]
            if orientation == Qt.Orientation.Vertical:
                return None
        return super().headerData(section, orientation, role)

    def data(self, index, role):
        if role == Qt.ItemDataRole.DisplayRole:
            value = self._data[index.row()][index.column()]
            if index.column() == 1:
                return f"{value:.1f}"
            return value
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter
        return None

    def rowCount(self, index):
        return len(self._data)
    
    def columnCount(self, index):
        try:
            return len(self._data[0])
        except:
            return 0
    
    def get_bar_id(self, row):
        return self._data[row][0]
    
    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.ItemIsEnabled
        if index.column() >1:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
        else:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
    
    def setData(self, index, value, role = ...):
        if role == Qt.ItemDataRole.EditRole:
            self._data[index.row()][index.column()] = value

            self.dataChanged.emit(index,index)
            return True
        return False

    
class CustomTableView(QTableView):
    data_changed = pyqtSignal(object,object)
    def __init__(self):
        super().__init__()
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(0)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)

    def setModel(self, model):
        super().setModel(model)
        self.setResizeMode()

    def setResizeMode(self):
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    

width = .7
default_slit_display_list = [[i+1,0.00,width] for i in range(72)]


class SlitDisplay(QWidget):
    highlight_other = pyqtSignal(int,name="row selected") #change name to match that in the interactive slit mask
    select_star = pyqtSignal(int)
    data_changed = pyqtSignal(dict) #it will have a bool as the first part of the list
    tell_unsaved = pyqtSignal()
    def __init__(self,data=default_slit_display_list):
        super().__init__()

        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.MinimumExpanding
        )

        #---------------------------definitions----------------------
        logger.info("slit_position_table: doing definitions")
        self.data = data #will look like [[bar_id,center,width],...]
        self.table = CustomTableView()
        self.model = TableModel(self.data)
        self.table.setModel(self.model)
        self.changed_data_dict = {}
        self.table.setEditTriggers(QTableView.EditTrigger.DoubleClicked)

        #--------------------------connections-----------------------
        logger.info("slit_position_table: doing conections")
        self.connect_signalers()

        #----------------------------layout----------------------
        logger.info("slit_position_table: defining layout")
        
        main_layout = QVBoxLayout()
        # main_layout.setSpacing(9)
        main_layout.setContentsMargins(0,0,9,0)
        
        main_layout.addWidget(self.table)
        self.setLayout(main_layout)
        #------------------------------------------------------        

    def sizeHint(self):
        return QSize(170,120)
    
    def connect_signalers(self):
        self.table.selectionModel().selectionChanged.connect(self.row_selected)
        self.model.dataChanged.connect(self.slit_width_changed)

    def disconnect_signalers(self):
        self.table.selectionModel().selectionChanged.disconnect(self.row_selected)
        self.model.dataChanged.disconnect(self.slit_width_changed)

    def change_data(self,data):
        logger.info("slit_position_table: change_data function called, changing data")
        if data:
            self.model.beginResetModel()
            replacement = list(x for x,_ in itertools.groupby(data))
            self.model._data = replacement
            self.data = replacement
            self.model.endResetModel()
            self.table.resizeColumnsToContents()
            self.table.resize(self.table.sizeHint())

    
    def row_selected(self):
        logger.info("slit_position_table: method row_selected is called, row in slit_table was selected")
        selected_row = self.table.selectionModel().currentIndex().row()
        corresponding_row = self.model.get_bar_id(row=selected_row)

        self.highlight_other.emit(corresponding_row-1)

    def select_corresponding(self,bar_id):
        logger.info("slit_position_table: method select_corresponding is called, selected corresponding row from slit mask view")
        self.disconnect_signalers
        self.bar_id = bar_id + 1

        filtered_row = list(filter(lambda x:x[0] == self.bar_id,self.data))
        if filtered_row:
            row = filtered_row[0]
            index_of_row = self.data.index(row)
            self.table.selectRow(index_of_row)
        else:
            #this means that the bar does not have a slit on it
            pass
        self.connect_signalers()
        
    def slit_width_changed(self,topLeft,bottomRight):
        row = topLeft.row()
        model = topLeft.model()
        new_data = model.data(topLeft, Qt.ItemDataRole.DisplayRole)
        bar_id = model.get_bar_id(row)
        self.changed_data_dict[bar_id]=new_data

        self.tell_unsaved.emit() 

    def data_saved(self):
        self.data_changed.emit(self.changed_data_dict)
        self.changed_data_dict = {}
 
