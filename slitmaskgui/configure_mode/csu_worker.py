"""
This function will instruct the csu
"""

from PyQt6.QtCore import QThread, pyqtSignal
from lris2csu.remote import CSURemote
from lris2csu.slit import Slit, MaskConfig
from slitmaskgui.mask_widgets.mask_objects import ErrorWidget
from logging import getLogger

# Setup logging
logger = getLogger('mktl')

class CSUWorkerThread(QThread):
    # Define signals to send results back to the main thread
    reset_signal = pyqtSignal(object)
    calibrate_signal = pyqtSignal(object)  # Calibration response
    status_signal = pyqtSignal(list)    # List of slits
    stop_signal = pyqtSignal(object)
    slit_config_updated_signal = pyqtSignal(object)

    def __init__(self, c: CSURemote):
        super().__init__()
        self.c = c
        self.task = None
        self.slits = []
    
    def __repr__(self):
        try:
            repr_list = []
            for slit in self.slits:
                new_slit = slit
                new_slit.x = f'{slit.x:.2f}'
                new_slit.width = f'{slit.width:.2f}'
                repr_list.append(new_slit)
        except:
            repr_list = None
        return f'{repr_list}'

    def set_task(self, task: str):
        """Set the current task (calibrate, status, etc.)."""
        self.task = task

    def run(self):
        """Execute the task based on the worker's task state."""
        if self.task == "calibrate":
            self._calibrate()
        elif self.task == "status":
            self._status()
        elif self.task == "configure":
            # self.configure_csu()
            pass
    def update_slits(self,slits):
        self.slits = slits

    def _calibrate(self):
        """Calibrate the CSU."""
        print("Calibrating CSU...")
        try:
            response = self.c.calibrate()  # Capture the response
            logger.debug(f"Calibration Response: {response}")
        except TimeoutError as e:
            logger.debug(f"Calibration Response: {e}")
            print(f"Calibration Response: {e}")

        # Emit calibration response
        self.calibrate_signal.emit(response)

    def _status(self):
        """Display the current status."""
        try:
            response = self.c.status()
            self.slits = self.parse_response(response)
            logger.debug(f"Status Response: {response}")
        except TimeoutError as e:
            logger.debug(f"Status Response: {e}")
            print(f'Status Response: {e}')
        
        # Emit slits list
        if self.slits:
            self.status_signal.emit(self.slits)

    def configure_csu(self, slits):
        """Call the CSU's configure method with the slits."""
        print("Configuring csu....")
        response = self.c.configure(MaskConfig(slits), speed=6500)
        self.slit_config_updated_signal.emit(response)  # Emit a signal indicating the configuration has been updated
        # self.log_message("Slit configuration updated successfully.")

    def parse_response(self, response):
        """Parse the response to extract the mask data."""
        try:
            mask_config = response[-1]  # Extract mask config from the response
            slits = mask_config.slits
            return slits
        except (IndexError, AttributeError) as e:
            error_message = f"Error parsing response: {e}"
            self.log_message(error_message)
            return []