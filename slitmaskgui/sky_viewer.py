import sys
import numpy as np
from PyQt6.QtWidgets import QApplication, QWidget, QHBoxLayout
from PyQt6.QtCore import pyqtSlot
from matplotlib.backends.backend_qtagg import FigureCanvas
from matplotlib.figure import Figure
import matplotlib.patches as patches


class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super().__init__(fig)


class SkyImageView(QWidget):
    def __init__(self):
        super().__init__()

        # Create the Matplotlib canvas and add it to the widget layout
        self.canvas = MplCanvas(self, width=5, height=4, dpi=100)
        self.canvas.axes.clear()
        self.canvas.axes.axis('off')

        layout = QHBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)
    pyqtSlot(np.ndarray)
    def show_image(self, data: np.ndarray):
        # Clear previous plot
        self.canvas.axes.clear()

        self.canvas.axes.imshow(data, origin='lower', cmap='gray')
        # self.canvas.axes.set_title("Sky Image (DSS2 Red)")

        self.canvas.axes.axis('off')
        #The image is 1000 px by 1000 px which I have no clue if that is good but it is what it is right now

        rect = patches.Rectangle(
            (250, 0),         # bottom-left corner (x, y)
            500, 1000,          # width, height
            linewidth=4,
            edgecolor='green',
            facecolor='none',
            alpha=0.4         # transparency
        )
        self.canvas.axes.add_patch(rect)

        self.canvas.figure.tight_layout(pad=0)

        self.canvas.draw()
