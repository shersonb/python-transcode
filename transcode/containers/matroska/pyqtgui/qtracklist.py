from PyQt5.QtCore import (Qt, QAbstractListModel, QAbstractItemModel, QAbstractTableModel, QModelIndex,
                          QVariant, QItemSelectionModel, QItemSelection, pyqtSignal, pyqtSlot, QMimeData,
                          QByteArray, QDataStream, QIODevice, QRegExp)
from PyQt5 import QtCore
from PyQt5.QtWidgets import (QDialog, QLabel, QListWidgetItem, QListView, QVBoxLayout, QHBoxLayout,
                             QAbstractItemView, QMessageBox, QPushButton, QTreeView, QTableView, QHeaderView, QSpinBox,
                             QLineEdit, QFileDialog, QCheckBox, QDoubleSpinBox, QItemDelegate, QComboBox)
from PyQt5.QtGui import QFont, QIcon, QDrag, QBrush, QPainter, QRegExpValidator
from transcode.encoders import vencoders, aencoders, sencoders
from transcode.encoders import createConfigObj as createCodecConfigObj
from transcode.pyqtgui.qoutputtracklist import BaseOutputTrackCol
import sys
import traceback
import json
import regex
import av
import os
import random
from functools import partial
import faulthandler
faulthandler.enable()

from .quidspinbox import UIDDelegate
#class QHexSpinBox(QDoubleSpinBox):
    #def __init__(self, *args, **kwargs):
        #super(QHexSpinBox, self).__init__(*args, **kwargs)
        #regex = QRegExp("0x[0-9A-Fa-f]{1,16}")
        #regex.setCaseSensitivity(Qt.CaseInsensitive)
        #self._validator = QRegExpValidator(regex, self)
        #self.setPrefix("0x")
        #self.setMaximum(16**16 - 1)

    #def validate(self, text, pos):
        #return self._validator.validate(text, pos)

    #def valueFromText(self, text):
        #return int(text, 16)

    #def textFromValue(self, value):
        #value = int(value)
        #return f"{value:016x}"

#class UIDDelegate(QItemDelegate):
    #def createEditor(self, parent, option, index):
        #editor = QHexSpinBox(parent)
        #editor.setMinimum(1)
        #return editor

    #def setEditorData(self, editor, index):
        #editor.setValue(index.data(Qt.EditRole))

    #def setModelData(self, editor, model, index):
        #model.setData(index, editor.value(), Qt.EditRole)

    #def updateEditorGeometry(self, editor, option, index):
        #editor.setGeometry(option.rect)

class LacingDelegate(QItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QSpinBox(parent)
        editor.setMinimum(1)
        editor.setSpecialValueText("Lacing disabled")
        editor.setSuffix(" packets/block")
        editor.setMaximum(256)
        return editor

    def setEditorData(self, editor, index):
        editor.setValue(index.data(Qt.EditRole))

    def setModelData(self, editor, model, index):
        model.setData(index, editor.value(), Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

class CompressionDelegate(QItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.addItem("None", None)
        editor.addItem("zlib", 0)
        return editor

    def setEditorData(self, editor, index):
        idx = editor.findData(index.data(Qt.EditRole))
        editor.setCurrentIndex(idx)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentData(), Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

class TrackUIDCol(BaseOutputTrackCol):
    width = 256
    headerdisplay = "Track UID"
    flags = Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, input_files, filters, output_file):
        super().__init__(input_files, filters, output_file, "trackUID")

    def editdata(self, index, track):
        data = super().editdata(index, track)

        if data is None:
            otherUIDs = {track.trackUID for track in self.output_file.tracks}
            data = random.randint(1, 2**128 - 1)

            while data in otherUIDs:
                data = random.randint(1, 2**128 - 1)

            self.seteditdata(index, track, data)

        return data

    #def display(self, index, track):
        #return f"0x{self.editdata(index, track):032x}"

    def display(self, index, obj):
        c, d = divmod(self.editdata(index, obj), 16**8)
        b, c = divmod(c, 16**8)
        a, b = divmod(b, 16**8)

        return f"{a:08x} {b:08x} {c:08x} {d:08x}"

    tooltip = display

    def seteditdata(self, index, track, data):
        super().seteditdata(index, track, int(data))

    def itemDelegate(self, parent):
        return UIDDelegate(parent)

class DefaultTrackCol(BaseOutputTrackCol):
    display = ""
    headerdisplay = "Default"
    width = 64
    flags = Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def checkstate(self, index, track):
        if getattr(track.container, f"default{track.type}") is track:
            return 2

        return 0

    def setcheckstate(self, index, track, state):
        state = self.checkstate(index, track)

        if state == 2:
            setattr(track.container, f"default{track.type}", None)

        elif state == 0:
            setattr(track.container, f"default{track.type}", track)

class ForcedTrackCol(BaseOutputTrackCol):
    display = ""
    headerdisplay = "Forced"
    width = 64
    flags = Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, input_files, filters, output_file):
        super().__init__(input_files, filters, output_file, "forced")

    def checkstate(self, index, track):
        value = self.editdata(index, track)

        if value:
            return 2

        return 0

    def setcheckstate(self, index, track, state):
        state = self.checkstate(index, track)

        if state == 2:
            self.seteditdata(index, track, False)

        if state == 0:
            self.seteditdata(index, track, True)

class EnabledTrackCol(BaseOutputTrackCol):
    display = ""
    headerdisplay = "Enabled"
    width = 64
    flags = Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, input_files, filters, output_file):
        super().__init__(input_files, filters, output_file, "enabled")

    def checkstate(self, index, track):
        value = self.editdata(index, track)

        if value:
            return 2

        return 0

    def setcheckstate(self, index, track, state):
        state = self.checkstate(index, track)

        if state == 2:
            self.seteditdata(index, track, False)

        if state == 0:
            self.seteditdata(index, track, True)

class LacingCol(BaseOutputTrackCol):
    display = ""
    headerdisplay = "Lacing"
    width = 128
    flags = Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsEditable

    def __init__(self, input_files, filters, output_file):
        super().__init__(input_files, filters, output_file, "maxInLace")

    def display(self, index, track):
        maxInLace = self.editdata(index, track)

        if maxInLace > 1:
            return f"{maxInLace} packets/block"

        return f"Lacing disabled"

    def itemDelegate(self, parent):
        return LacingDelegate(parent)

class CompressionCol(BaseOutputTrackCol):
    headerdisplay = "Compression"
    width = 64
    flags = Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsEditable

    def __init__(self, input_files, filters, output_file):
        super().__init__(input_files, filters, output_file, "compression")

    def display(self, index, track):
        if self.editdata(index, track) == 0:
            return "zlib"

        return "None"

    def itemDelegate(self, parent):
        return CompressionDelegate(parent)

cols = [TrackUIDCol, DefaultTrackCol, ForcedTrackCol, EnabledTrackCol, LacingCol, CompressionCol]
