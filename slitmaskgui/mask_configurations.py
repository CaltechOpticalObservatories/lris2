"""
This is a widget that will display all the masks that have been imported and if they have been saved.
A button at the bottom to save the mask, and one right next to it to save all the masks
3 buttons on the top: open, copy, close
"""

from PyQt6.QtCore import Qt, QAbstractTableModel,QSize
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
)

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

    def rowCount(self, index):
        return len(self._data)

    def columnCount(self, index):
        return 2
    
class CustomTableView(QTableView):
    def __init__(self):
        super().__init__()
        self.verticalHeader().hide()

        # self.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
    def setResizeMode(self):
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    def setModel(self, model):
        super().setModel(model)
        self.setResizeMode()



#I am unsure of whether to go with a abstract table model or an abstract list model
class MaskConfigurationsWidget(QWidget):
    def __init__(self):
        super().__init__()
        
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred
        )

        #--------------------------------Definitions---------------------
        title = QLabel("MASK CONFIGURATIONS")

        open_button = Button(80,30,"Open")
        copy_button = Button(80,30,"Copy")
        close_button = Button(80,30,"Close")

        save_button = Button(120,30,"Save")
        save_all_button = Button(120,30,"Save All")

        group_box = QGroupBox()
        
        table = CustomTableView()
        model = TableModel()
        table.setModel(model)     


        #-------------------------------layout--------------------------
        main_layout = QVBoxLayout()
        group_layout = QVBoxLayout()
        top_hori_layout = QHBoxLayout()
        bot_hori_layout = QHBoxLayout()

        top_hori_layout.addWidget(open_button)
        top_hori_layout.addWidget(copy_button)
        top_hori_layout.addWidget(close_button)
        top_hori_layout.setSpacing(0)

        bot_hori_layout.addWidget(save_button)
        bot_hori_layout.addWidget(save_all_button)
        bot_hori_layout.setSpacing(0)

        group_layout.addLayout(top_hori_layout)
        group_layout.addWidget(table)
        group_layout.addLayout(bot_hori_layout)
        group_layout.setSpacing(0)
        group_layout.setContentsMargins(0,0,0,0)

        group_box.setLayout(group_layout)
        group_box.setContentsMargins(2,0,2,0)
        
        main_layout.addWidget(title)
        main_layout.addWidget(group_box)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0,0,0,0)

        self.setLayout(main_layout)
        #------------------------------------------------
    def sizeHint(self):
        return QSize(300,60)
    
    def open_button_clicked(self):
        pass

    def copy_button_clicked(self):
        pass

    def close_button_clicked(self):
        pass

    def save_button_clicked(self):
        pass

    def save_all_button_clicked(self):
        pass

    def update_table(self):
        pass



