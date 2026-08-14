from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import pyqtSignal


class PlainTextEdit(QtWidgets.QPlainTextEdit):
    dropped = pyqtSignal()
    def __init__(self, parent):
        super(PlainTextEdit, self).__init__(parent)

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        super(PlainTextEdit, self).dropEvent(event)

        self.dropped.emit()


