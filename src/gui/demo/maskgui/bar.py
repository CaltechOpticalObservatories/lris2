from PyQt6.QtWidgets import QGraphicsScene, QGraphicsRectItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QLinearGradient, QColor
from lris2csu.slit import Slit, MaskConfig

# Constants
BAR_HEIGHT = 20
ROW_WIDTH = 340
SCENE_HEIGHT = 600
DEFAULT_BAR_WIDTH = 260  # Default width of the slit (total width of both bars + space between them)
DEFAULT_SPACE = .5  # Space between the left and right bars

class SlitGUI:
    """
    A slit defined by a bar pair id, a position (treated as the lower left corner of the slit opening), and a width (mm).
    """

    def __init__(self, id: int, x: float, width: float):
        self.id = id
        self.x = x
        self.width = width

    def __repr__(self):
        return f"Slit(id={self.id}, x={self.x}, width={self.width})"


class BarPair:
    def __init__(self, scene: QGraphicsScene, slit: SlitGUI):
        self.scene = scene
        self.slit = slit
        self.total_width = ROW_WIDTH
        self.y = slit.id * BAR_HEIGHT

        # Create the left and right bars
        self.left_rect = QGraphicsRectItem()
        self.right_rect = QGraphicsRectItem()

        # Add the bars to the scene
        scene.addItem(self.left_rect)
        scene.addItem(self.right_rect)

        # Draw the slit bars
        self.draw_slit()

    def draw_slit(self):
        # Calculate the total width of the bars plus the gap between them
        total_bar_width = DEFAULT_BAR_WIDTH
        space_between_bars = self.slit.width
        # Width of each bar, adjusted for the gap
        bar_width = (total_bar_width - space_between_bars) / 2

        # Ensure the left and right bars don't extend beyond the row boundaries
        left = min(bar_width, self.slit.x)
        right = min(bar_width,
                    self.total_width - (self.slit.x + space_between_bars))

        # Calculate the horizontal offset to center the entire slit in the window
        center_offset = (ROW_WIDTH - total_bar_width) / 2

        # Set the left bar: starts from the center and extends to the left
        self.left_rect.setRect(center_offset + self.slit.x - left, self.y, left, BAR_HEIGHT)

        left_grad = QLinearGradient(self.slit.x, 0, self.slit.x - left, 0)
        left_grad.setColorAt(0, QColor(67, 61, 139))  # Dark Purple: #433D8B
        left_grad.setColorAt(1, QColor(200, 172, 214))  # Light Purple: #C8ACD6
        self.left_rect.setBrush(QBrush(left_grad))

        # Set the right bar: starts after the left bar and the gap (width), extends to the right by 'right'
        self.right_rect.setRect(center_offset + self.slit.x + space_between_bars, self.y, right, BAR_HEIGHT)

        right_grad = QLinearGradient(self.slit.x, 0, self.slit.x + right, 0)
        right_grad.setColorAt(0, QColor(67, 61, 139))  # Dark Purple: #433D8B
        right_grad.setColorAt(1, QColor(200, 172, 214))  # Light Purple: #C8ACD6
        self.right_rect.setBrush(QBrush(right_grad))
