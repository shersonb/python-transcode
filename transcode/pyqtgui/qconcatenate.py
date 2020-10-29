from .qinputtracklist import FileTrackCol, LanguageCol, InputFmtCol
from .qfilterlist import FilterNameCol, SourceCol, FormatCol
from .qinputselection import InputSelectionRoot, ColumnUnion
from .qitemmodel import Node, ChildNodes, NoChildren, QItemModel
from .qfilterconfig import QFilterConfig
from PyQt5.QtWidgets import QVBoxLayout, QTreeView, QLabel, QSplitter, QWidget, QMessageBox
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, pyqtSignal
from transcode.containers.basereader import Track
from transcode.filters.concatenate import Concatenate
from transcode.filters.base import BaseFilter, FilterChain
from copy import copy


class SegmentsRoot(Node):
    def _iterChildren(self):
        return self.value.segments

    def _wrapChildren(self, children):
        return SegmentsList.fromValues(children, self)

    def canDropChildren(self, model, parent, items, row, action):
        if action == Qt.CopyAction:
            for item in items:
                if not isinstance(item.value, (Track, BaseFilter)):
                    return False

        elif action == Qt.MoveAction:
            for item in items:
                if item not in self.children:
                    return False

        return True

    def dropChildren(self, model, parent, items, row, action):
        if action == Qt.CopyAction:
            for k, item in enumerate(items, row):
                model.insertRow(k, item.value, parent)

        elif action == Qt.MoveAction:
            j = 0

            for k, item in enumerate(items, row):
                old_row = self.children.index(item)
                model.moveRow(old_row, k - j, parent)

                if old_row < row:
                    j += 1

        return True


class SegmentsList(ChildNodes):
    @staticmethod
    def _wrap(item):
        return SegmentNode(item)

    def _append(self, value):
        self.parent.value.segments.append(node.value)

    def _insert(self, index, value):
        self.parent.value.segments.insert(index, value)

    def _extend(self, values):
        self.parent.value.segments.extend(values)

    def _delitem(self, index):
        del self.parent.value.segments[index]

    def _setitem(self, index, value):
        self.parent.value.segments[index] = value


class SegmentNode(NoChildren):
    pass


class SourcesModel(QItemModel):
    def supportedDragActions(self):
        return Qt.CopyAction


class SegmentsModel(QItemModel):
    def supportedDragActions(self):
        return Qt.MoveAction

    def supportedDropActions(self):
        return Qt.MoveAction | Qt.CopyAction


class BaseColumn(object):
    flags = Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsEnabled

    def __init__(self, input_files, available_filters, filter):
        self.input_files = input_files
        self.available_filters = available_filters
        self.filter = filter


class NameCol(BaseColumn):
    width = 256
    headerdisplay = "Segment"

    def display(self, index, obj):
        if isinstance(obj, Track) and obj.container in self.input_files:
            return f"{self.filter.segments.index(obj)}: input:{self.input_files.index(obj.container)}:{obj.track_index}"

        return f"{self.filter.segments.index(obj)}: filter:{self.available_filters.index(obj)}"


class DurationCol(BaseColumn):
    width = 128
    headerdisplay = "Duration"

    def display(self, index, obj):
        m, s = divmod(obj.duration, 60)
        h, m = divmod(int(m), 60)
        return f"{h}:{m:02d}:{s:012.9f}"


class StartCol(BaseColumn):
    width = 128
    headerdisplay = "Start Time"

    def display(self, index, obj):
        k = self.filter.segments.index(obj)
        t = sum(segment.duration for segment in self.filter.segments[:k])
        m, s = divmod(t, 60)
        h, m = divmod(int(m), 60)
        return f"{h}:{m:02d}:{s:012.9f}"


class EndCol(BaseColumn):
    width = 128
    headerdisplay = "End Time"

    def display(self, index, obj):
        k = self.filter.segments.index(obj)
        t = sum(segment.duration for segment in self.filter.segments[:k+1])
        m, s = divmod(t, 60)
        h, m = divmod(int(m), 60)
        return f"{h}:{m:02d}:{s:012.9f}"


class QSegmentTree(QTreeView):
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setSelectionMode(QTreeView.ExtendedSelection)

    def contextMenuEvent(self, event):
        selected = self.currentIndex()
        menu = self.model().data(selected, role=Qt.UserRole + 1)

        if callable(menu):
            menu = menu(self)

        if isinstance(menu, QMenu):
            menu.exec_(self.mapToGlobal(event.pos()))

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        idx = self.currentIndex()
        row = idx.row()
        col = idx.column()
        model = self.model()

        selected = sorted(idx.row()
                          for idx in self.selectionModel().selectedRows())

        if key == Qt.Key_Delete and modifiers == Qt.NoModifier and len(self.selectionModel().selectedRows()):
            self.askDeleteSelected()

        super().keyPressEvent(event)

    def askDeleteSelected(self):
        answer = QMessageBox.question(
            self, "Delete tracks", "Do you wish to delete the selected tracks? All encoder and settings associated with selected tracks will be lost!", QMessageBox.Yes | QMessageBox.No)

        if answer == QMessageBox.Yes:
            self.deleteSelected()

    def deleteSelected(self):
        selected = sorted(idx.row()
                          for idx in self.selectionModel().selectedRows())

        for k, row in enumerate(selected):
            self.model().removeRow(row - k)

        self.contentsModified.emit()


class QConcatenate(QFilterConfig):
    def createNewFilterInstance(self):
        return Concatenate()

    def _createControls(self):
        self.setMinimumWidth(720)
        layout = QVBoxLayout()
        #layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        splitter = QSplitter(Qt.Vertical, self)
        layout.addWidget(splitter)

        col1 = QWidget(splitter)
        col2 = QWidget(splitter)

        vlayout1 = QVBoxLayout()
        vlayout1.setContentsMargins(0, 16, 0, 0)
        col1.setLayout(vlayout1)

        vlayout2 = QVBoxLayout()
        vlayout2.setContentsMargins(0, 16, 0, 0)
        col2.setLayout(vlayout2)

        splitter.addWidget(col1)
        splitter.addWidget(col2)

        self.sourcesLabel = QLabel("Sources", self)
        self.sourcesLabel.setFont(
            QFont("DejaVu Serif", 18, QFont.Bold, italic=True))
        self.sourcesList = QTreeView(self)
        self.sourcesList.setDragEnabled(True)
        self.sourcesList.setSelectionMode(QTreeView.ExtendedSelection)

        vlayout1.addWidget(self.sourcesLabel)
        vlayout1.addWidget(self.sourcesList)

        self.segmentsLabel = QLabel("Segments", self)
        self.segmentsLabel.setFont(
            QFont("DejaVu Serif", 18, QFont.Bold, italic=True))
        self.segmentsList = QSegmentTree(self)

        vlayout2.addWidget(self.segmentsLabel)
        vlayout2.addWidget(self.segmentsList)

        self._prepareDlgButtons()

    def _resetSourceModels(self):
        if self.inputFiles is not None:
            self.cols = [
                ColumnUnion("Input",
                            FileTrackCol(self.inputFiles), FilterNameCol(
                                self.availableFilters),
                            width=256),
                ColumnUnion("Language",
                            LanguageCol(self.inputFiles), None, width=96),
                ColumnUnion("Source",
                            None, SourceCol(self.availableFilters), width=96),
                ColumnUnion("Format",
                            InputFmtCol(self.inputFiles), FormatCol(self.availableFilters), width=128),
            ]

            if self.availableFilters:
                root = InputSelectionRoot(
                    [self.inputFiles, self.availableFilters])

            else:
                root = InputSelectionRoot([self.inputFiles])

            model = SourcesModel(root, self.cols)
            self.sourcesList.setModel(model)

            for k, col in enumerate(self.cols):
                if hasattr(col, "width"):
                    self.sourcesList.setColumnWidth(k, col.width)

                col.selectfunc = self.isValidSource

            self.sourcesList.expandAll()

        else:
            self.sourcesList.setModel(QItemModel(Node(None), []))

        self._resetConcatModel()

    def _resetControls(self):
        self._resetConcatModel()

    def _resetConcatModel(self):
        root = SegmentsRoot(self.shadow)

        cols = [
            NameCol(self.inputFiles, self.availableFilters, self.shadow),
            DurationCol(self.inputFiles, self.availableFilters, self.shadow),
            StartCol(self.inputFiles, self.availableFilters, self.shadow),
            EndCol(self.inputFiles, self.availableFilters, self.shadow)
        ]

        model = SegmentsModel(root, cols)
        self.segmentsList.setModel(model)
        model.rowsRemoved.connect(self.isModified)
        model.rowsMoved.connect(self.isModified)
        model.rowsInserted.connect(self.isModified)

        for k, col in enumerate(cols):
            if hasattr(col, "width"):
                self.segmentsList.setColumnWidth(k, col.width)

        self.segmentsList.expandAll()

    def reset(self):
        self.shadow = copy(self.filter)

        if isinstance(self.filter.parent, FilterChain):
            self.shadow.parent = self.filter.parent
            self.shadow.prev = self.filter.prev

        self._resetControls()

        self.notModified()

    def isValidSource(self, other):
        if isinstance(other, BaseFilter) and (self.filter in other.dependencies or self.filter is other):
            return False

        if len(self.shadow.segments):
            first = self.shadow.segments[0]

            if first.type != other.type:
                return False

            if first.type == "video":
                return (other.width, other.height) == (first.width, first.height)

            elif first.type == "audio":
                return (other.rate, other.channels) == (first.rate, first.channels)

            return (other.codec) == (first.codec)

        return True
