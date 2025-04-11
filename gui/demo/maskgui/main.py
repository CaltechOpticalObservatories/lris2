import sys
from typing import Tuple
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QGraphicsView, QGraphicsScene,
    QComboBox, QPushButton, QHBoxLayout, QSplitter
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter
from bar import BarPair, SlitGUI
from lris2csu.remote import CSURemote
from lris2csu.slit import Slit, MaskConfig

# Constants
BAR_HEIGHT = 20
ROW_WIDTH = 340
SCENE_HEIGHT = 600
DEFAULT_BAR_WIDTH = 200  # Default width of the slit (total width of both bars + space between them)
DEFAULT_SPACE = 20  # Space between the left and right bars
VIEWPORT_WIDTH = 960  # Desired viewport width
VIEWPORT_HEIGHT = 540  # Desired viewport height

class SlitMaskGUI(QWidget):
    def __init__(self, slits: Tuple[Slit, ...], c: CSURemote):
        super().__init__()
        self.setWindowTitle("Demo: Slit Configurator")

        # Store the CSURemote instance
        self.c = c
        print(c)

        # Set window size for the desired viewport
        self.setGeometry(100, 100, VIEWPORT_WIDTH + 400, VIEWPORT_HEIGHT + 100)

        # Create a QGraphicsScene for the drawing area
        self.scene = QGraphicsScene(30, 0, ROW_WIDTH, SCENE_HEIGHT)
        self.view = QGraphicsView(self.scene)

        # Enable anti-aliasing for smoother rendering
        self.view.setRenderHints(QPainter.RenderHint.Antialiasing)

        # Create a QSplitter to make the layout resizable
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Create a layout for the ComboBox and Calibrate button to be placed side by side
        top_layout = QHBoxLayout()

        # Create the dropdown (ComboBox) for selecting the mask type
        self.combo_box = QComboBox()
        self.combo_box.addItem("Stair Mask")
        self.combo_box.addItem("N-Stair Mask")
        self.combo_box.addItem("Central Mask")
        self.combo_box.addItem("Window Mask")
        self.combo_box.addItem("N-Window Mask")

        # Create the "Calibrate" button
        self.calibrate_button = QPushButton("Configure")
        self.calibrate_button.clicked.connect(self.update_slit_configuration)

        # Create the "Stop" button
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_process)

        # Add ComboBox and Calibrate button to the top layout
        top_layout.addWidget(self.combo_box)
        top_layout.addWidget(self.calibrate_button)
        top_layout.addWidget(self.stop_button)

        # Create the "Calibrate" button
        self.calibrate_button = QPushButton("Calibrate")
        self.calibrate_button.clicked.connect(self.calibrate)

        # Create the "Reset" button
        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self.reset_configuration)

        # Create the "Shutdown" button
        self.shutdown_button = QPushButton("Shutdown")
        self.shutdown_button.clicked.connect(self.shutdown)

        # Create the "Status" button
        self.status_button = QPushButton("Status")
        self.status_button.clicked.connect(self.show_status)

        # Create a layout for the buttons
        button_layout = QVBoxLayout()
        button_layout.addWidget(self.calibrate_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addWidget(self.shutdown_button)
        button_layout.addWidget(self.status_button)
        button_layout.addWidget(self.stop_button)

        # Create a QWidget to hold the buttons and top layout
        control_widget = QWidget()
        control_layout = QVBoxLayout()
        control_layout.addLayout(top_layout)
        control_layout.addLayout(button_layout)
        control_widget.setLayout(control_layout)

        # Add the control widget to the splitter (on the left side)
        splitter.addWidget(control_widget)
        splitter.addWidget(self.view)  # Larger slit mask area for displaying shapes

        # Add spacing (gaps) between the widgets inside the splitter layout
        splitter.setHandleWidth(10)  # Adjust the width of the splitter handle
        splitter.setSizes([450, ROW_WIDTH + 400])  # Increased size for the slit mask display area

        # Create the main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(splitter)

        # Apply margin/gap around the layout
        main_layout.setContentsMargins(10, 10, 10, 10)  # Add margin to the window

        # Set the layout to the main window
        self.setLayout(main_layout)

        # Store the slits and initialize
        self.bar_pairs = []
        self.initalize_slit_configuration()

        # Apply QSS styles from the file
        self.apply_styles()

    def apply_styles(self):
        """Apply styles from an external QSS file."""
        try:
            with open("styles.qss", "r") as file:
                self.setStyleSheet(file.read())
        except FileNotFoundError:
            print("Stylesheet file 'styles.qss' not found!")

    def scale_scene_to_fit(self):
        """Scale the scene to fit within the QGraphicsView and center it properly."""
        # Calculate the bounding box of all slits
        min_x, max_x, min_y, max_y = float('inf'), float('-inf'), float('inf'), float('-inf')

        # Update the bounding box based on the rects of each bar pair
        for bar_pair in self.bar_pairs:
            left_rect = bar_pair.left_rect.rect()
            right_rect = bar_pair.right_rect.rect()

            # Update min/max values using the bounding boxes of the bar pairs
            min_x = min(min_x, left_rect.left(), right_rect.left())
            max_x = max(max_x, left_rect.right(), right_rect.right())
            min_y = min(min_y, left_rect.top(), right_rect.top())
            max_y = max(max_y, left_rect.bottom(), right_rect.bottom())

        # Ensure the scene rect is updated to cover the full area of all slits
        scene_width = max_x - min_x
        scene_height = max_y - min_y

        # Set the scene rect to match the bounding box of all slits
        self.scene.setSceneRect(min_x, min_y, scene_width, scene_height)

        # Get the size of the viewport (the visible area of the QGraphicsView)
        view_width = self.view.viewport().width()
        view_height = self.view.viewport().height()

        # Calculate the scaling factors based on the current scene size and the desired viewport size
        scale_x = view_width / scene_width
        scale_y = view_height / scene_height

        # Apply the scaling to fit the scene within the view
        self.view.setTransform(self.view.transform().scale(scale_x, scale_y))

        # After scaling, we want to center the scene within the view
        scene_center = self.scene.sceneRect().center()

        # Apply the transformation that centers the view on the scene's center
        self.view.centerOn(scene_center)

    def update_slit_configuration(self):
        """Update slit configuration based on the selected dropdown option."""
        # Clear existing bars
        for bar_pair in self.bar_pairs:
            self.scene.removeItem(bar_pair.left_rect)
            self.scene.removeItem(bar_pair.right_rect)

        self.bar_pairs.clear()  # Clear the list of bar pairs

        # Get the selected mask type from the dropdown
        mask_type = self.combo_box.currentText()

        # Define all possible slit configurations
        if mask_type == "Stair Mask":
            slits = tuple(Slit(i, 130 + i * 10 - 6 * 10, 20) for i in range(12))
        elif mask_type == "N-Stair Mask":
            slits = tuple(Slit(i, 130 - i * 10 + 6 * 10, 20) for i in range(12))
        elif mask_type == "Central Mask":
            slits = tuple(Slit(i, 130, 30) for i in range(12))
        elif mask_type == "Window Mask":
            slits = tuple(Slit(i, 130 / 2 + (i % 2) * 120, 20) for i in range(12))
        elif mask_type == "N-Window Mask":
            slits = tuple(Slit(i, 3 * 130 / 2 - (i % 2) * 120, 20) for i in range(12))

        # Create new bar pairs based on the selected slit configuration
        self.bar_pairs = [BarPair(self.scene, slit) for slit in slits]

        # Apply scaling after adding new items
        # self.scale_scene_to_fit()

    def initalize_slit_configuration(self):
        """Initalize slit configuration based on the selected dropdown option."""
        # Clear existing bars
        for bar_pair in self.bar_pairs:
            self.scene.removeItem(bar_pair.left_rect)
            self.scene.removeItem(bar_pair.right_rect)

        self.bar_pairs.clear()  # Clear the list of bar pairs

        # Create new bar pairs based on the selected slit configuration
        self.bar_pairs = [BarPair(self.scene, slit) for slit in slits]

        # Apply scaling after adding new items
        self.scale_scene_to_fit()

    def reset_configuration(self):
        """Reset the configuration to a default state."""
        self.combo_box.setCurrentIndex(0)  # Reset to "Stair Mask"
        self.update_slit_configuration()  # Apply the default configuration

    def calibrate(self):
        """Calibrate the CSU."""
        print("Hello")

    def shutdown(self):
        """Shutdown the application."""
        QApplication.quit()

    def show_status(self):
        """Display the current status."""
        current_mask = self.combo_box.currentText()
        print(f"Current configuration: {current_mask}")

    def stop_process(self):
        """Stop the process by sending the stop command to CSURemote."""
        print("Stopping the process...")
        self.c.stop()


if __name__ == "__main__":
    # Instantiate the CSURemote object
    c = CSURemote(registry_address='tcp://localhost:5570')

    # Create slit list dynamically
    slits = tuple(Slit(i, 130 + i * 10 - 6 * 10, 20) for i in range(12))

    app = QApplication(sys.argv)
    window = SlitMaskGUI(slits, c)
    window.show()
    sys.exit(app.exec())
