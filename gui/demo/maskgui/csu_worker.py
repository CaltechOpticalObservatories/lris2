from PyQt6.QtCore import QThread, pyqtSignal
from lris2csu.remote import CSURemote
from lris2csu.slit import Slit, MaskConfig
from logging import getLogger

# Setup logging
logger = getLogger('mktl')

class CSUWorkerThread(QThread):
    # Define signals to send results back to the main thread
    reset_signal = pyqtSignal()
    calibrate_signal = pyqtSignal(str)  # Calibration response
    status_signal = pyqtSignal(list)    # List of slits
    stop_signal = pyqtSignal()
    slit_config_updated_signal = pyqtSignal()

    def __init__(self, c: CSURemote):
        super().__init__()
        self.c = c
        self.task = None

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
            self._configure_slits()

    def reset_configuration(self):
        """Reset the configuration to a default state."""
        self.log_message("Resetting CSU...")
        self.c.reset()
        # Emit reset signal after reset
        self.reset_signal.emit()

    def _calibrate(self):
        """Calibrate the CSU."""
        print("Calibrating CSU...")
        response = self.c.calibrate()  # Capture the response
        logger.debug(f"Calibration Response: {response}")

        # Emit calibration response
        self.calibrate_signal.emit(response)

    def _status(self, verbose=False):
        """Display the current status."""
        response = self.c.status(verbose)
        logger.debug(f"Status Response: {response}")
        slits = self.parse_response(response)

        # Emit slits list
        if slits:
            self.status_signal.emit(slits)

    def _configure_slits(self):
        """Configure the CSU with the selected slit configuration."""
        mask_type = self.task_data.get("mask_type")  # Assuming task_data contains the mask_type
        if mask_type:
            self.log_message(f"Configuring slits with mask type: {mask_type}")
            self.update_slit_configuration(mask_type)

    def update_slit_configuration(self, mask_type: str):
        """Update slit configuration based on the selected mask type."""
        # Define slit configurations based on the mask type
        if mask_type == "Stair Mask":
            slits = tuple(Slit(i, 130 + i * 10 - 6 * 10, 20) for i in range(12))
        elif mask_type == "N-Stair Mask":
            slits = tuple(Slit(i, 130 - i * 10 + 6 * 10, 20) for i in range(12))
        elif mask_type == "Central Mask":
            slits = tuple(Slit(i, 130, 30) for i in range(12))
        elif mask_type == "Window Mask":
            slits = tuple(Slit(i, 130 / 2 + (i % 2) * 120, 20) for i in range(12))

        # Now call the configure method
        self.configure_csu(slits)

    def configure_csu(self, slits):
        """Call the CSU's configure method with the slits."""
        self.c.configure(MaskConfig(slits), speed=6500)
        self.slit_config_updated_signal.emit()  # Emit a signal indicating the configuration has been updated
        self.log_message("Slit configuration updated successfully.")

    def stop_process(self):
        """Stop the process and emit stop signal."""
        self.log_message("Stopping the process...")
        self.c.stop()
        # Emit stop signal
        self.stop_signal.emit()

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
