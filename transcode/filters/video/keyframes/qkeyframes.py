from transcode.pyqtgui.qframetablecolumn import BaseColumn
from PyQt5.QtCore import Qt


class KeyFrameCol(BaseColumn):
    headerdisplay = "K"
    display = ""
    width = 48
    flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable

    def __init__(self, forcekeyframes):
        self.forcekeyframes = forcekeyframes

    def setcheckstate(self, index, obj, data):
        if self.checkstate(index, obj):
            self.forcekeyframes.remove(obj)
            return True

        else:
            self.forcekeyframes.add(obj)
            return True

    def checkstate(self, index, obj):
        return 2 if obj in self.forcekeyframes else 0
