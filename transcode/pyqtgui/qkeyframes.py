from .qframetablecolumn import BaseColumn
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

        else:
            self.forcekeyframes.add(obj)

    def checkstate(self, index, obj):
        return obj in self.forcekeyframes

