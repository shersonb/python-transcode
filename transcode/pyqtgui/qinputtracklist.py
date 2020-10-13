from PyQt5.QtWidgets import QApplication, QWidget
import sys
from PyQt5.QtCore import (Qt, QAbstractListModel, QAbstractItemModel, QAbstractTableModel, QModelIndex,
                          QVariant, QItemSelectionModel, QItemSelection, pyqtSignal, pyqtSlot, QMimeData, QByteArray,
                          QDataStream, QIODevice, QSortFilterProxyModel)
from PyQt5.QtWidgets import (QDialog, QLabel, QListWidgetItem, QListView, QVBoxLayout, QHBoxLayout,
                             QAbstractItemView, QMessageBox, QPushButton, QTreeView, QTableView, QHeaderView,
                             QLineEdit, QComboBox, QFileDialog, QCheckBox, QDoubleSpinBox, QItemDelegate, QComboBox,
                             QCompleter)
from PyQt5.QtGui import QFont, QIcon, QDrag, QBrush, QPainter, QStandardItemModel, QStandardItem, QPen, QCursor

from .qobjectitemmodel import QObjectItemModel
from transcode.containers.basereader import BaseReader, Track
import sys
import traceback
import json
import regex
import av
import os
from functools import partial
import faulthandler
faulthandler.enable()

from .qlangselect import LANGUAGES

class BaseInputCol(object):
    fontmain = QFont("DejaVu Serif", 8)
    fontalt = QFont("DejaVu Serif", 12, QFont.Bold, italic=True)

    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled
    textalign = Qt.AlignLeft
    bgdata = QBrush()
    itemDelegate = None

    def __init__(self, input_files, attrname=None):
        self.input_files = input_files
        self.attrname = attrname

    def editdata(self, index, obj):
        return getattr(obj, self.attrname)

    def seteditdata(self, index, obj, data):
        setattr(obj, attrname, data)

    def font(self, index, obj):
        if isinstance(obj, BaseReader):
            return self.fontalt

        return self.fontmain

class FileTrackCol(BaseInputCol):
    headerdisplay = "File/Track"
    width = 240
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, input_files):
        super().__init__(input_files, "name")

    def display(self, index, obj):
        if isinstance(obj, BaseReader):
            return f"{obj.config.input_files.index(obj)}: {obj.inputpathrel}"

        elif isinstance(obj, Track):
            if hasattr(obj, "name") and obj.name:
                return f"{obj.container.tracks.index(obj)}: {obj.name}"

            elif obj.type == "video":
                return f"{obj.container.tracks.index(obj)}: Video"

            elif obj.type == "audio":
                return f"{obj.container.tracks.index(obj)}: Audio"

            elif obj.type == "subtitle":
                return f"{obj.container.tracks.index(obj)}: Subtitle"

            return f"{obj.container.tracks.index(obj)}: {obj}"

    def tooltip(self, index, obj):
        if isinstance(obj, BaseReader):
            mod = obj.__class__.__module__

            if mod.split(".")[:2] == ["transcode", "containers"]:
                mod = ".".join(mod.split(".")[2:])

            return f"{obj.config.input_files.index(obj)}: {obj.inputpathabs}"

        elif isinstance(obj, Track):
            if hasattr(obj, "name") and obj.name:
                return f"{obj.container.tracks.index(obj)}: {obj.name}"

            elif obj.type == "video":
                return f"{obj.container.tracks.index(obj)}: Video"

            elif obj.type == "audio":
                return f"{obj.container.tracks.index(obj)}: Audio"

            elif obj.type == "subtitle":
                return f"{obj.container.tracks.index(obj)}: Subtitle"

            return f"{obj.container.tracks.index(obj)}: {obj}"

    def icon(self, index, obj):
        if isinstance(obj, Track):
            if obj.type == "video":
                return QIcon.fromTheme("video-x-generic")

            if obj.type == "audio":
                return QIcon.fromTheme("audio-x-generic")

            if obj.type == "subtitle":
                return QIcon.fromTheme("text-x-generic")

class LanguageCol(BaseInputCol):
    width = 96
    headerdisplay = "Language"
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, input_files):
        super().__init__(input_files, "language")

    def display(self, index, obj):
        if isinstance(obj, Track):
            try:
                lang = obj.language

            except AttributeError:
                lang = None

            if lang is None:
                return "Unknown (und)"

            return f"{LANGUAGES.get(lang, 'Unknown')} ({lang})"

    tooltip = display

    def itemDelegate(self, parent):
        return LanguageDelegate(parent)

class InputTypeCol(BaseInputCol):
    width = 128
    headerdisplay = "Format/Codec"

    def display(self, index, obj):
        if isinstance(obj, BaseReader):
            return obj.fmtname

        elif isinstance(obj, Track):
            codec = obj.codec

            try:
                codec_long = av.Codec(codec, "r").long_name

            except:
                codec_long = "Unknown"

            return f"{codec_long} ({codec})"

    def tooltip(self, index, obj):
        if isinstance(obj, BaseReader):
            mod = obj.__class__.__module__

            if mod.split(".")[:2] == ["transcode", "containers"]:
                mod = ".".join(mod.split(".")[2:])

            return f"{obj.fmtname}\n"\
                f"[{mod}.{obj.__class__.__name__}]"

        elif isinstance(obj, Track):
            codec = obj.codec

            try:
                codec_long = av.Codec(codec, "r").long_name

            except:
                codec_long = "Unknown"

            return f"{codec_long} ({codec})"



class InputFmtCol(BaseInputCol):
    width = 192
    headerdisplay = "Track Format"

    def display(self, index, obj):
        if isinstance(obj, BaseReader):
            return None

        elif isinstance(obj, Track):
            fmtlist = []

            if obj.type == "video":
                if obj.width and obj.height:
                    fmtlist.append(f"{obj.width}×{obj.height}")

                if obj.sar:
                    fmtlist.append(f"SAR: {obj.sar}")

                if obj.width and obj.height and obj.sar:
                    fmtlist.append(f"DAR: {obj.sar*obj.width/obj.height}")

                if obj.rate:
                    fmtlist.append(f"{obj.rate} fps")

                if obj.format:
                    fmtlist.append(f"{obj.format}")

            elif obj.type == "audio":
                if obj.rate:
                    fmtlist.append(f"{obj.rate}Hz")

                if obj.layout:
                    fmtlist.append(f"{obj.layout}")

                if obj.format:
                    fmtlist.append(f"{obj.format}")

            return ", ".join(fmtlist)

    tooltip = display

class InputFileModel(QObjectItemModel):
    def parentObject(self, obj):
        if isinstance(obj, BaseReader):
            return self.items

        elif isinstance(obj, Track):
            return obj.container

    def getItems(self, parent):
        if parent.isValid():
            parent_obj = parent.data(Qt.UserRole)

            if isinstance(parent_obj, BaseReader):
                return parent_obj.tracks

            return None

        return self.items

class QInputTrackList(QTreeView):
    contentsChanged = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMinimumWidth(640)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setInputFiles(None)

    def setInputFiles(self, input_files):
        self.input_files = input_files

        if input_files is not None:
            cols = [
                    FileTrackCol(input_files),
                    InputTypeCol(input_files),
                    InputFmtCol(input_files),
                    LanguageCol(input_files),
                ]

            self.setModel(InputFileModel(input_files, cols))

            for k, col in enumerate(cols):
                if hasattr(col, "width"):
                    self.setColumnWidth(k, col.width)

        else:
            self.setModel(QObjectItemModel([], []))
