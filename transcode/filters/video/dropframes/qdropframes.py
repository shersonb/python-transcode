from transcode.pyqtgui.qframetablecolumn import BaseColumn
from PyQt5.QtCore import Qt


class DropFrameCol(BaseColumn):
    headerdisplay = "D"
    display = ""
    width = 48
    flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable

    def __init__(self, dropframes):
        self.dropframes = dropframes

    def setcheckstate(self, index, obj, data):
        if self.checkstate(index, obj):
            self.dropframes.remove(obj)
            return True

        else:
            self.dropframes.add(obj)
            return True

    def checkstate(self, index, obj):
        return obj in self.dropframes
