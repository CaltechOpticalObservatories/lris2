# import logging
# import numpy as np
# from astroquery.gaia import Gaia
# from astropy.coordinates import SkyCoord
# import astropy.units as u
# from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal, QSize
# from PyQt6.QtGui import QBrush, QPen, QPainter, QColor, QFont, QTransform
# from slitmaskgui.mask_viewer import interactiveSlitMask, WavelengthView

from PyQt6.QtCore import pyqtSignal, Qt, QPoint, QTimer, QItemSelectionModel
from PyQt6.QtWidgets import (
    QTabWidget,
    QComboBox,
    QLabel,
    QVBoxLayout,
    QWidget,
    QListView

)
class CustomComboBox(QComboBox):
    def __init__(self):
        super().__init__()
        items = ['phot_bp_mean_mag', 'phot_g_mean_mag', 'phot_rp_mean_mag']
        self.addItems(items)

    def showPopup(self):
        popup = self.view().window()
        if popup.isVisible():
            popup.hide() 

        super().showPopup()

        pos = self.mapToGlobal(QPoint(0, self.height()))
        popup.move(pos)
        popup.show()

class TabBar(QTabWidget):
    waveview_change = pyqtSignal(int)
    def __init__(self,slitmask,waveview,skyview):
        super().__init__()
        #--------------defining widgets for tabs---------
        self.wavelength_view = waveview#QLabel("Spectral view is currently under development")#waveview #currently waveview hasn't been developed
        self.interactive_slit_mask = slitmask
        self.sky_view = skyview

        #--------------defining comobox------------------
        self.combobox = CustomComboBox()

        #--------------defining tabs--------------
        self.addTab(self.interactive_slit_mask,"Slit Mask")
        self.addTab(self.wavelength_view,"Spectral View")
        self.addTab(self.sky_view,"Sky View")

        self.setCornerWidget(self.combobox)
        self.combobox.hide()
        # self.mask_tab.setCornerWidget(self.combobox) #this would add the widget to the corner (only want it when spectral view is selected)
        #------------------other---------------
        # self.wavelength_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # self.wavelength_view.setStyleSheet("font-size: 20px;")

        #------------------connections------------
        self.tabBar().currentChanged.connect(self.wavetab_selected)
        self.combobox.currentIndexChanged.connect(self.send_to_view)
        # self.tabBar().currentChanged.connect()

    
    def wavetab_selected(self,selected):
        if selected == 1:
            self.combobox.show()
        else:
            self.combobox.hide()
    
    def send_to_view(self,index):
        self.waveview_change.emit(index)


