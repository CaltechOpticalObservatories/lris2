# import logging
# import numpy as np
# from astroquery.gaia import Gaia
# from astropy.coordinates import SkyCoord
# import astropy.units as u
# from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal, QSize
# from PyQt6.QtGui import QBrush, QPen, QPainter, QColor, QFont, QTransform
# from slitmaskgui.mask_viewer import interactiveSlitMask, WavelengthView

from PyQt6.QtCore import pyqtSignal, Qt, QPoint, pyqtSlot
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
        self.spectral_view_list = [
            '[RED] Low Res Grism', 
            '[RED] High Res Grism (Blue End)',
            '[RED] High Res Grism (Red End)',
            '[BLUE] Low Res Grism',
            '[BLUE] High Res Grism (Blue End)',
            '[BLUE] High Res Grism (Red End)',
        ]

        self.addItems(self.spectral_view_list)

        self.passbands = { #this is all in nm
            "red_low": (550,1000), #low end, high end
            "red_high_blue": (550,775), 
            "red_high_red": (775,1000),
            "blue_low": (310,550), #low end, high end 
            "blue_high_blue": (310,435),
            "blue_high_red": (430,565), 
        }

    def showPopup(self):
        popup = self.view().window()
        if popup.isVisible():
            popup.hide() 

        super().showPopup()

        pos = self.mapToGlobal(QPoint(0, self.height()))
        popup.move(pos)
        popup.show()
    
    
    def return_passband_from_index(self,index) -> tuple:
        keys = list(self.passbands.keys())
        key = keys[index]
        return self.passbands[key]

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

        #------------------connections------------
        self.tabBar().currentChanged.connect(self.wavetab_selected)
        self.combobox.currentIndexChanged.connect(self.send_to_view)

    
    def wavetab_selected(self,selected):
        if selected == 1: #there are 3 tabs, Spectral view is the second tab so this would show combo box if spectral tab selected
            self.combobox.show()
        else:
            self.combobox.hide()
    
    def send_to_view(self):
        # I might make it so that I emit the index and a code so like Red low red is red low res red end grism as well as index
        index = self.tabBar().currentIndex()
        passband = self.combobox.return_passband_from_index(index)
        self.wavelength_view.initialize_scene(index,passband=passband)
    
    pyqtSlot(list)
    def initialize_spectral_view(self, slit_positions):
        index = self.tabBar().currentIndex()
        passband = self.combobox.return_passband_from_index(index)
        self.wavelength_view.get_slit_positions(slit_positions,index,passband)


