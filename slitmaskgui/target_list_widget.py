
#from inputTargets import TargetList
import logging
from slitmaskgui.menu_bar import MenuBar
from PyQt6.QtCore import Qt, QAbstractTableModel, pyqtSlot, QSize, pyqtSignal
import itertools
from PyQt6.QtWidgets import (
    QWidget,
    QTableView,
    QVBoxLayout,
    QLabel,
    QSizePolicy,
    QHeaderView,
    
)
logger = logging.getLogger(__name__)

class TableModel(QAbstractTableModel):
    def __init__(self, data=[]):
        super().__init__()
        self._data = data
        self.header = ["Name","Priority","Magnitude","Ra","Dec","Center Distance"]


    def headerData(self, section, orientation, role = ...):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return self.header[section]
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if orientation == Qt.Orientation.Horizontal:
                return Qt.AlignmentFlag.AlignCenter
        return super().headerData(section, orientation, role)

    def data(self, index, role):
        if role == Qt.ItemDataRole.DisplayRole:
            return self._data[index.row()][index.column()]
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter
        
        return None

    def rowCount(self, index):
        return len(self._data)

    def columnCount(self, index):
        return len(self.header)
    
    def get_star_name(self, row):
        return self._data[row][0]
    
    def get_row(self,name):
        for x in self._data:
            if x[0] == name:
                return self._data.index(x)


class CustomTableView(QTableView):
    def __init__(self):
        super().__init__()
        self.verticalHeader().show()
        self.horizontalHeader().show()
        self.verticalHeader().setDefaultSectionSize(0)

        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableView.SelectionMode.SingleSelection)

    def setResizeMode(self):
        for col in range(self.model().columnCount(None)):
            self.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
    def sizePolicy(self):
        return super().sizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def setModel(self, model):
        super().setModel(model)
        self.setResizeMode()

class TargetDisplayWidget(QWidget):
    selected_le_star = pyqtSignal(str)
    def __init__(self,data=[]):
        super().__init__()

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Ignored
        )

        #---------------------------definitions------------------------
        logger.info("target_list_widget: doing definitions")
        self.data = data
        self.table = CustomTableView()
        self.model = TableModel(self.data)
        self.table.setModel(self.model)
        # title = QLabel("TARGET LIST")

        #------------------------connections----------------------
        logger.info("target_list_widget: establishing connections")
        self.table.selectionModel().selectionChanged.connect(self.selected_star)

        #-------------------------layout-----------------------------
        logger.info("target_list_widget: defining layout")
        main_layout = QVBoxLayout()
        # main_layout.addWidget(title)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0,0,0,0)

        main_layout.addWidget(self.table)
        self.setLayout(main_layout)
        #-------------------------------------------

    def sizeHint(self):
        return QSize(700,100)
    def connect_on(self,answer:bool):
        #---------------reconnect connections---------------
        if answer:
            self.table.selectionModel().selectionChanged.connect(self.selected_star)
        else:
            self.table.selectionModel().selectionChanged.disconnect(self.selected_star)
    
    @pyqtSlot(list,name="target list")
    def change_data(self,data):
        logger.info("target_list_widget: method change_data called, changing data")
        self.model.beginResetModel()
        replacement = list(x for x,_ in itertools.groupby(data))
        self.model._data = replacement
        self.data = replacement
        self.model.endResetModel()
    
    def selected_star(self):
        
        selected_row = self.table.selectionModel().currentIndex().row()
        corresponding_name = self.model.get_star_name(row=selected_row)
        logger.info(f"target_list_widget: method selected_star called, corresponding name: {corresponding_name}")
        self.selected_le_star.emit(corresponding_name)

    @pyqtSlot(str)
    def select_corresponding(self,star): #everything will be done with the row widget
        self.connect_on(False)
        row = self.model.get_row(star)
        if row:
            logger.info(f'target_list_widget: method select_corresponding called: row {row}')
            self.table.selectRow(row)
        self.connect_on(True)



#default margin is 9 or 11 pixels





