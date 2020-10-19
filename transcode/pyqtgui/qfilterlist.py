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
from transcode.util import NewConfig
from .qitemmodel import QItemModel, Node, ChildNodes, NoChildren
from ..filters.filterchain import FilterChain
from ..filters.base import BaseFilter
from ..filters.concatenate import Concatenate
from transcode.containers.basereader import BaseReader, Track
#from transcode.util import ChildList
import sys
import traceback
import json
import regex
import av
import os
from functools import partial
import faulthandler
from itertools import count
faulthandler.enable()

class FiltersRoot(Node):
    def _wrapChildren(self, children):
        return Filters.fromValues(children, self)

class Filters(ChildNodes):
    @staticmethod
    def _wrap(item):
        if hasattr(item, "makeNode") and callable(item.makeNode):
            return item.makeNode()

        elif isinstance(item, FilterChain):
            return FilterChainNode(item)

        elif isinstance(item, Concatenate):
            return ConcatenateNode(item)

        return FilterNode(item)

class FilterChainNode(Node):
    def _wrapChildren(self, children):
        return FilterChainItems.fromValues(children, self)

class FilterChainItems(ChildNodes):
    @staticmethod
    def _wrap(item):
        return FilterChainItemNode(item)

class FilterChainItemNode(NoChildren):
    pass

class ConcatenateNode(Node):
    def _iterChildren(self):
        return self.value.segments

    def _wrapChildren(self, children):
        return ConcatenateItems.fromValues(children, self)

class ConcatenateItems(ChildNodes):
    @staticmethod
    def _wrap(item):
        return InputSlotNode(item)

class FilterNode(Node):
    def _iterChildren(self):
        if hasattr(self.value, "sources"):
            return self.value.sources

        elif hasattr(self.value, "source1"):
            sources = []

            for n in count(1):
                if hasattr(self.value, f"source{n}"):
                    sources.append(getattr(self.value, f"source{n}"))

                else:
                    return sources

        raise TypeError

    def _wrapChildren(self, children):
        return InputSlotNodes.fromValues(children, self)

class InputSlotNodes(ChildNodes):
    @staticmethod
    def _wrap(item):
        return InputSlotNode(item)

class InputSlotNode(NoChildren):
    pass

class FilterListModel(QItemModel):
    pass

class BaseFilterCol(object):
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled
    textalign = Qt.AlignLeft
    bgdata = QBrush()
    itemDelegate = None

    def __init__(self, input_files, filters, attrname=None):
        self.input_files = input_files
        self.filters = filters
        self.attrname = attrname

    def editdata(self, index, obj):
        return getattr(obj, self.attrname)

    def seteditdata(self, index, obj, data):
        setattr(obj, self.attrname, data)

class FilterName(BaseFilterCol):
    headerdisplay = "Filter"
    width = 240
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, input_files, filters):
        super().__init__(input_files, filters, "__name__")

    def display(self, index, obj):
        node = index.model().getNode(index)

        if isinstance(node, InputSlotNode):
            j = node.parent.index(node)
            return f"Input Slot {j}"

        if obj in self.filters:
            __name__ = obj.__name__
            k = self.filters.index(obj)
            return f"{k}: {__name__}"

        if isinstance(node, FilterChainItemNode):
            return obj.__name__

        return "???"

    def tooltip(self, index, obj):
        return f"{obj.__class__.__module__}.{obj.__class__.__name__}"

    def icon(self, index, obj):
        if not hasattr(obj, "type"):
            return

        if obj.type == "video":
            return QIcon.fromTheme("video-x-generic")

        if obj.type == "audio":
            return QIcon.fromTheme("audio-x-generic")

        if obj.type == "subtitle":
            return QIcon.fromTheme("text-x-generic")

class Source(BaseFilterCol):
    headerdisplay = "Source"
    width = 96
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, input_files, filters):
        super().__init__(input_files, filters, "prev")

    def display(self, index, obj):
        node = index.model().getNode(index)

        if isinstance(node, InputSlotNode):
            prev = obj

        elif isinstance(node, FilterChainItemNode):
            return ""

        elif isinstance(node, FilterChainNode) or node.children is None:
            prev = obj.prev

        else:
            return ""

        if isinstance(prev, Track):
            return f"{self.input_files.index(prev.container)}:{prev.track_index}"

        elif isinstance(prev, BaseFilter) and prev in self.filters:
            __name__ = prev.__name__
            return f"filters:{self.filters.index(prev)} ({__name__})"

        #if isinstance(obj.prev, Track):
            #return f"{self.input_files.index(obj.container)}:{obj.track_index}"

        #elif isinstance(obj, BaseFilter) and obj in self.filters:
            #__name__ = obj.__name__
            #return f"filters:{self.filters.index(obj)} ({__name__})"

        #elif node.children is None:
            #prev = self.editdata(index, obj)

            #if prev in self.filters:
                #filter_index = self.filters.index(prev)
                #return f"filters:{filter_index}"

            #elif isinstance(prev, Track):
                #file_index = self.input_files.index(prev.container)
                #return f"{file_index}:{prev.track_index}"

        return ""

    def tooltip(self, index, obj):
        return f"{obj.__class__.__module__}.{obj.__class__.__name__}"

class Options(BaseFilterCol):
    headerdisplay = "Options"
    width = 256
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, input_files, filters):
        super().__init__(input_files, filters, "prev")

    def display(self, index, obj):
        options = obj.__getstate__()
        optlist = []

        for key, value in options.items():
            if key == "prev":
                continue

            if isinstance(value, Track):
                file_index = self.input_files.index(prev.container)
                optlist.append(f"{key}={file_index}:{prev.track_index}")

            elif isinstance(value, BaseFilter) and value in self.filters:
                filter_index = self.filters.index(value)
                optlist.append(f"{key}=filters:{filter_index}")

            elif isinstance(value, float):
                optlist.append(f"{key}={value:.9f}")

            else:
                optlist.append(f"{key}={value}")

        return ", ".join(optlist)

    tooltip = display

class Format(BaseFilterCol):
    headerdisplay = "Format"
    width = 256
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, input_files, filters):
        super().__init__(input_files, filters, "format")

    def display(self, index, obj):
        if not hasattr(obj, "type"):
            return

        if obj.type == "video":
            fmt = []

            if obj.width is not None and obj.height is not None:
                fmt.append(f"{obj.width}×{obj.height}")

            if obj.sar is not None:
                fmt.append(f"sar: {obj.sar}")

            if obj.format is not None:
                fmt.append(f"{obj.format}")

            if obj.rate is not None:
                fmt.append(f"{obj.rate} fps")

            return ", ".join(fmt)

        if obj.type == "audio":
            fmt = []

            if obj.rate is not None:
                fmt.append(f"{obj.rate} kHz")

            if obj.channels is not None:
                fmt.append(f"{obj.channels} channels")

            if obj.layout is not None:
                fmt.append(f"{obj.layout}")

            if obj.format is not None:
                fmt.append(f"{obj.format}")

            return ", ".join(fmt)

class Duration(BaseFilterCol):
    headerdisplay = "Duration"
    width = 128
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, input_files, filters):
        super().__init__(input_files, filters, "format")

    def display(self, index, obj):
        if isinstance(obj.duration, (int, float)):
            m, s = divmod(obj.duration, 60)
            h, m = divmod(int(m), 60)
            return f"{h}:{m:02d}:{s:012.9f}"

class FilterTreeView(QTreeView):
    contentsChanged = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMinimumWidth(640)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.loadFilters(None, None)

    def loadFilters(self, input_files, filters):
        self.input_files = input_files
        self.filters = filters

        if filters is not None:
            cols = [
                    FilterName(input_files, filters),
                    Source(input_files, filters),
                    Format(input_files, filters),
                    Duration(input_files, filters),
                    Options(input_files, filters),
                ]

            self.setModel(FilterListModel(FiltersRoot(filters), cols))

            for k, col in enumerate(cols):
                if hasattr(col, "width"):
                    self.setColumnWidth(k, col.width)

        else:
            self.setModel(QItemModel(Node(None), []))
