"""
this will display all the slit positions as well as the bar number and then width
additionally, when you click on the slits, it will highlight the corresponding bar in the 
interactive image and highlight the corresponding star in the target list table
"""

from slitmaskgui.menu_bar import MenuBar
from PyQt6.QtCore import Qt, QAbstractTableModel, pyqtSlot, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QWidget,
    QTableView,
    QVBoxLayout,
    QTableWidget,
    QSizePolicy,
    QLabel,
    QHeaderView,


)

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
        return len(self._data[0])
    
    def row_num(self,row):
        return self._data[row][0]
    
class CustomTableView(QTableView):
    def __init__(self):
        super().__init__()

        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(0)

        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableView.SelectionMode.SingleSelection)
    def setModel(self, model):
        super().setModel(model)
        self.setResizeMode()

    def setResizeMode(self):
        for i in range(3):
            self.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

    def event(self, event):
        return super().event(event)
        #what I will do in the future is make it so that if even == doublemousepress event that you can edit the data in the cell


width = .7
default_slit_display_list = [[i+1,0.00,width] for i in range(73)]


class SlitDisplay(QWidget):
    highlight_other = pyqtSignal(int,name="row selected") #change name to match that in the interactive slit mask
    def __init__(self,data=default_slit_display_list):
        super().__init__()

        self.setSizePolicy(
            QSizePolicy.Policy.Maximum,
            QSizePolicy.Policy.MinimumExpanding
        )

        #---------------------------definitions----------------------
        self.data = data #will look like [[row,center,width],...]
        self.table = CustomTableView()
        self.model = TableModel(self.data)
        self.table.setModel(self.model)
        title = QLabel("ROW DISPLAY WIDGET")

        #--------------------------connections-----------------------
        self.table.selectionModel().selectionChanged.connect(self.row_selected)

        #----------------------------layout----------------------
        main_layout = QVBoxLayout()
        main_layout.addWidget(title)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0,0,0,0)

        main_layout.addWidget(self.table)
        self.setLayout(main_layout)
        #------------------------------------------------------        

    def sizeHint(self):
        return QSize(40,120)
    
    @pyqtSlot(list,name="input slit positions")
    def change_data(self,data):
        self.model.beginResetModel()
        self.model._data = data
        self.model.endResetModel()

    
    def row_selected(self):
        #I have to emit a list of x,y positions [[x,y],...]
        #if there is no star in a row then we have to make it so that there is not change in position
        #I probably need to find the row
        selected_row = self.table.selectionModel().currentIndex().row()
        # item = int(self.model.row_num(selected_row))
        # if selected_row in (self.data, lambda x:x[0]):
        self.highlight_other.emit(selected_row)

    @pyqtSlot(int,name="other row selected")
    def select_corresponding(self,row):
        self.row = row
        self.table.selectRow(self.row)
 
