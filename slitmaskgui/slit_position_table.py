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
    QAbstractScrollArea


)

logger = logging.getLogger(__name__)

class TableModel(QAbstractTableModel):
    def __init__(self, data=[]):
        super().__init__()
        self._data = data
        self.headers = ["Row","Center","Width"]
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
            # Set the value into the frame.
            self._data[index.row()][index.column()] = value
            self.dataChanged.emit(index, index)
            return True

        return False
        # return super().setData(index, value, role)
    
class CustomTableView(QTableView):
    def __init__(self):
        super().__init__()

        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(0)

        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableView.SelectionMode.SingleSelection)

        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
    def setModel(self, model):
        super().setModel(model)
        self.setResizeMode()

    def setResizeMode(self):
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

    def event(self, event):
        return super().event(event)
        #what I will do in the future is make it so that if even == doublemousepress event that you can edit the data in the cell
    



width = .7
default_slit_display_list = [[i+1,0.00,width] for i in range(72)]


class SlitDisplay(QWidget):
    highlight_other = pyqtSignal(int,name="row selected") #change name to match that in the interactive slit mask
    select_star = pyqtSignal(int)
    data_changed = pyqtSignal(list) #it will have a bool as the first part of the list
    tell_unsaved = pyqtSignal(object)
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
        self.changed_data_list = [False,{}]

        #--------------------------connections-----------------------
        logger.info("slit_position_table: doing conections")
        self.table.selectionModel().selectionChanged.connect(self.row_selected)
        self.model.dataChanged.connect(self.slit_width_changed)


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
    def connect_on(self,answer:bool):
        #---------------reconnect connections---------------
        if answer:
            self.table.selectionModel().selectionChanged.connect(self.row_selected)
        else:
            self.table.selectionModel().selectionChanged.disconnect(self.row_selected)
    
    @pyqtSlot(list,name="input slit positions")
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


    @pyqtSlot(int,name="other row selected")
    def select_corresponding(self,bar_id):
        logger.info("slit_position_table: method select_corresponding is called, selected corresponding row from slit mask view")
        self.connect_on(False)
        self.bar_id = bar_id + 1

        filtered_row = list(filter(lambda x:x[0] == self.bar_id,self.data))
        if filtered_row:
            row = filtered_row[0]
            index_of_row = self.data.index(row)
            self.table.selectRow(index_of_row)
        else:
            #this means that the bar does not have a slit on it
            pass
        self.connect_on(True)
    
    def slit_width_changed(self,index1,index2):
        #essentially, if the data was changed, this would be set to true and the rest of the program would know the data is changed
        #so the config would set the state to be unsaved
        #once the mask config has been saved everything else will update
        #it will also say what has been changed
        index_1, index_2 = index1, index2
        self.changed_data_list[0]=True

        #if index_1 and index_2 do not equal each other then multiple lines of data have been changed
        #I won't worry about that right now
        if index_1 == index_2:
            value = self.model.data(index_2,Qt.ItemDataRole.DisplayRole)
            bar_id = self.model.get_bar_id(index_2.row())
            self.changed_data_list[1][bar_id]=value
        else:
            pass #will add all the changed data in a loop
        self.tell_unsaved.emit(None) #doesn't have to be a bool or really anything just need to signal
    pyqtSlot(object)
    def data_saved(self):
        list_copy = self.changed_data_list
        self.changed_data_list = [False,{}]
        self.data_changed.emit(list_copy)
 
