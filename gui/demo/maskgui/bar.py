from PyQt6.QtWidgets import QGraphicsScene, QGraphicsRectItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QLinearGradient, QColor


# Constants
BAR_HEIGHT = 20
ROW_WIDTH = 340
SCENE_HEIGHT = 600
DEFAULT_BAR_WIDTH = 200  # Default width of the slit (total width of both bars + space between them)
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

        # Create the left and right bars (rectangles)
        self.left_rect = QGraphicsRectItem()
        self.right_rect = QGraphicsRectItem()

        # Add the bars to the scene
        scene.addItem(self.left_rect)
        scene.addItem(self.right_rect)

        # Draw the slit bars
        self.draw_slit()

    def draw_slit(self):
        # Calculate the left and right positions based on slit position and width
        total_bar_width = DEFAULT_BAR_WIDTH  # Total width of both bars plus the space between them
        space_between_bars = DEFAULT_SPACE  # Space between the two bars
        bar_width = (total_bar_width) / 2  # Width of each bar
        
        left = bar_width
        right = bar_width

        # Ensure left bar doesn't extend past the center
        left = min(left, self.slit.x)

        # Ensure right bar doesn't extend past the end of the row
        right = min(right, self.total_width - self.slit.x)

        # Calculate the horizontal offset to center the bars in the window
        center_offset = (ROW_WIDTH - total_bar_width) / 2

        # Set the left bar: starts from the center and extends to the left
        self.left_rect.setRect(center_offset + self.slit.x - left, self.y, left, BAR_HEIGHT)
        
        # Apply your specified color for the left bar gradient
        left_grad = QLinearGradient(self.slit.x, 0, self.slit.x - left, 0)
        left_grad.setColorAt(0, QColor(67, 61, 139))  # Dark Purple: #433D8B
        left_grad.setColorAt(1, QColor(200, 172, 214))  # Light Purple: #C8ACD6
        self.left_rect.setBrush(QBrush(left_grad))

        # After the left bar is drawn, calculate the right bar's position
        # The right bar starts after the left bar and the space between the bars
        self.right_rect.setRect(center_offset + self.slit.x + space_between_bars, self.y, right, BAR_HEIGHT)

        # Apply your specified color for the right bar gradient
        right_grad = QLinearGradient(self.slit.x, 0, self.slit.x + right, 0)
        right_grad.setColorAt(0, QColor(67, 61, 139))  # Dark Purple: #433D8B
        right_grad.setColorAt(1, QColor(200, 172, 214))  # Light Purple: #C8ACD6
        self.right_rect.setBrush(QBrush(right_grad))


