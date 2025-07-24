
#from inputTargets import TargetList
from slitmaskgui.menu_bar import MenuBar
from PyQt6.QtCore import Qt, QAbstractTableModel, pyqtSlot, QSize
from PyQt6.QtWidgets import (
    QWidget,
    QTableView,
    QVBoxLayout,
    QLabel,
    QSizePolicy,
    QHeaderView,
    


)
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
    def __init__(self,data=[]):
        super().__init__()

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred
        )

        #---------------------------definitions------------------------
        self.data = data
        self.table = CustomTableView()
        self.model = TableModel(self.data)
        self.table.setModel(self.model)
        title = QLabel("TARGET LIST")


        #-------------------------layout-----------------------------
        main_layout = QVBoxLayout()
        main_layout.addWidget(title)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0,0,0,0)

        main_layout.addWidget(self.table)
        self.setLayout(main_layout)
        #-------------------------------------------

    def sizeHint(self):
        return QSize(700,200)
    
    @pyqtSlot(list,name="target list")
    def change_data(self,data):
        self.model.beginResetModel()
        self.model._data = data
        self.model.endResetModel()

#default margin is 9 or 11 pixels





