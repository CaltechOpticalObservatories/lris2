from slitmaskgui.mask_widgets.mask_objects import *
from itertools import groupby
import logging
import numpy as np
import time
import requests
import socket
from PyQt6.QtCore import Qt, QThreadPool, QRunnable, pyqtSlot, QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
)




HOST = '131.215.200.105'
PORT = 5571


""" 
Initially I will have this just check if you are offline or not.
But in the future I might have it check if you are also connected to the CSU using the socket module
"""

class OfflineCheckerSignals(QObject):
    started = pyqtSignal()
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    connection_status = pyqtSignal(object)
    

class CSUConnectionSignals(QObject):
    started = pyqtSignal()
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    connection_status = pyqtSignal(bool)


class InternetConnectionChecker(QRunnable):
    """ class that constantly checks if the user is online or offline """

    def __init__(self):
        super().__init__()
        self.signals = OfflineCheckerSignals()

    @pyqtSlot()
    def run(self):
        """ the online and having to do not online is needlessly confusing I think """
        self.signals.started.emit()
        online = self.check_internet_connection()
        self.signals.connection_status.emit(not online) # return not online because we are seeing if it is offline
        self.signals.finished.emit()

    def check_internet_connection(self):
        """ I feel like this is not a good way to do this """
        try:
            response = requests.get("https://www.google.com/", timeout=5)
            return True
        except requests.ConnectionError:
            return False
        
    
class CSUConnectionChecker(QRunnable):
    """ Checks the connection to the CSU """
    def __init__(self):
        super().__init__()
        self.signals = CSUConnectionSignals()
    
    @pyqtSlot()
    def run(self):
        self.signals.started.emit()
        csu_connection_status = self.check_connected_to_CSU()
        self.signals.connection_status.emit(csu_connection_status)
        self.signals.finished.emit()

    def check_connected_to_CSU(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)
            try:
                sock.connect((HOST,PORT))
                return True
            except socket.error:
                return False


class OfflineMode(QObject):

    current_mode = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.offline = False

        self.threadpool = QThreadPool()
        self.offline_checker = InternetConnectionChecker()

        # ------------- timer ----------------
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.start_checking_internet_connection) # having what the timer is connected to not be known by the user is a bit confusing
        # ------------------------------------
    
    def __repr__(self):
        if self.offline:
            return f'Offline'
        return f'Online'
        
    def start_checking_internet_connection(self): # this feels kind of bad but its fine for now
        self.offline_checker.signals.connection_status.connect(self.change_mode)
        self.threadpool.start(self.offline_checker)
        self.offline_checker = InternetConnectionChecker()
    
    def start_timer(self):
        self.timer.start()
    
    def stop_timer(self):
        self.timer.stop()

    def change_mode(self,mode):
        self.offline = mode
        self.current_mode.emit(self.offline)

    



    # def check_csu_connection(self): # Offline mode will soon not be able to check if csu is connected or not
    #     self.threadpool.connect_internet_checker_signals(self.change_mode)
    #     self.threadpool.start_csu_connection_checker()
    