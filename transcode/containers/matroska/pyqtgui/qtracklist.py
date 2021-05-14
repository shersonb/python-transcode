from .quidspinbox import UIDDelegate
from PyQt5.QtCore import (Qt, QAbstractListModel, QAbstractItemModel, QAbstractTableModel, QModelIndex,
                          QVariant, QItemSelectionModel, QItemSelection, pyqtSignal, pyqtSlot, QMimeData,
                          QByteArray, QDataStream, QIODevice, QRegExp)
from PyQt5.QtWidgets import (QDialog, QLabel, QListWidgetItem, QListView, QVBoxLayout, QHBoxLayout,
                             QAbstractItemView, QMessageBox, QPushButton, QTreeView, QTableView,
                             QHeaderView, QSpinBox, QMenu, QAction,
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
    width = 128
    headerdisplay = "Track UID"
    flags = Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, input_files, filters, output_file):
        super().__init__(input_files, filters, output_file, "trackUID")

    def editdata(self, index, track):
        data = super().editdata(index, track)

        if data is None:
            otherUIDs = {track.trackUID for track in self.output_file.tracks}
            data = random.randint(1, 2**64 - 1)

            while data in otherUIDs:
                data = random.randint(1, 2**64 - 1)

            self.seteditdata(index, track, data)

        return data

    def display(self, index, obj):
        c, d = divmod(self.editdata(index, obj), 16**4)
        b, c = divmod(c, 16**4)
        a, b = divmod(b, 16**4)

        return f"{a:04x} {b:04x} {c:04x} {d:04x}"

    tooltip = display

    def seteditdata(self, index, track, data):
        super().seteditdata(index, track, int(data))

    def itemDelegate(self, parent):
        return UIDDelegate(parent)

    def contextmenu(self, index, obj):
        return partial(self.createContextMenu, obj=obj, index=index)

    def createContextMenu(self, table, index, obj):
        menu = QMenu(table)
        selectRandom = QAction(f"Select random UID", table,
                             triggered=partial(self.selectRandomUID, obj, table.model()))

        menu.addAction(selectRandom)
        return menu

    def selectRandomUID(self, obj, model):
        UID = random.randint(1, 2**64 - 1)

        existingUIDs = {track.trackUID for track in self.output_file.tracks if track is not obj}

        while UID in existingUIDs:
            UID = random.randint(1, 2**64 - 1)

        obj.trackUID = UID
        model.dataChanged.emit(QModelIndex(), QModelIndex())


class DefaultTrackCol(BaseOutputTrackCol):
    display = ""
    headerdisplay = "Default"
    width = 64
    flags = Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def checkstate(self, index, track):
        if track.type is None:
            if track.container.defaultvideo is track:
                track.container.defaultvideo = None

            if track.container.defaultaudio is track:
                track.container.defaultaudio = None

            if track.container.defaultsubtitle is track:
                track.container.defaultsubtitle = None

            return 0

        if getattr(track.container, f"default{track.type}") is track:
            return 2

        return 0

    def setcheckstate(self, index, track, state):
        state = self.checkstate(index, track)

        if state == 2:
            setattr(track.container, f"default{track.type}", None)
            return True

        elif state == 0:
            setattr(track.container, f"default{track.type}", track)
            return True

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


cols = [TrackUIDCol, DefaultTrackCol, ForcedTrackCol,
        EnabledTrackCol, LacingCol, CompressionCol]
