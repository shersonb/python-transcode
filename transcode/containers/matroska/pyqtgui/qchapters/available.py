from PyQt5.QtWidgets import (QHBoxLayout, QFileIconProvider, QVBoxLayout, QDialog,
                             QPushButton)
from PyQt5.QtCore import Qt, QFileInfo
from transcode.pyqtgui.qitemmodel import Node, ChildNodes, NoChildren, QItemModel
from transcode.pyqtgui.treeview import TreeView as QTreeView

from matroska.chapters import EditionEntry as InputEditionEntry
from matroska.chapters import ChapterAtom as InputChapterAtom
from matroska.chapters import ChapterDisplay as InputChapterDisplay

from transcode.containers.basereader import BaseReader
from transcode.containers.matroska.reader import MatroskaReader


icons = QFileIconProvider()


class AvailableEditionsNode(Node):
    def _wrapChildren(self, children):
        return InputFiles.fromValues(children, self)


class InputFiles(ChildNodes):
    @staticmethod
    def _wrap(value):
        return InputFileNode(value)


class InputFileNode(Node):
    def _iterChildren(self):
        if isinstance(self.value, MatroskaReader) and self.value.chapters:
            return self.value.chapters

        raise TypeError

    def _wrapChildren(self, children):
        return AvailableEditionEntries.fromValues(children, self)


class AvailableEditionEntries(ChildNodes):
    @staticmethod
    def _wrap(value):
        return AvailableEditionEntryNode(value)


class AvailableEditionEntryNode(Node):
    def _iterChildren(self):
        return self.value.chapterAtoms

    def _wrapChildren(self, children):
        return AvailableChapterAtoms.fromValues(children, self)


class AvailableChapterAtoms(ChildNodes):
    @staticmethod
    def _wrap(value):
        return AvailableChapterNode(value)


class AvailableChapterNode(Node):
    def _iterChildren(self):
        return self.value.chapterDisplays

    def _wrapChildren(self, children):
        return AvailableChapterDisplays.fromValues(children, self)


class AvailableChapterDisplays(ChildNodes):
    @staticmethod
    def _wrap(value):
        return AvailableChapterDisplayNode(value)


class AvailableChapterDisplayNode(NoChildren):
    pass


class AvailableEditionEntriesBaseColumn(object):
    checkstate = None
    fontmain = None
    fontalt = None
    fgcolor = None
    fgcoloralt = None
    bgcolor = None
    bgcoloralt = None
    name = None
    textalign = Qt.AlignLeft | Qt.AlignVCenter

    def __init__(self, input_files):
        self.input_files = input_files

    def flags(self, index, obj):
        if isinstance(obj, InputEditionEntry):
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable

        return Qt.ItemIsEnabled


class AvailableEditionEntryNameCol(AvailableEditionEntriesBaseColumn):
    headerdisplay = "Edition Entries"
    width = 192

    def display(self, index, obj):
        if isinstance(obj, BaseReader):
            return f"{self.input_files.index(obj)}: {obj.inputpathrel}"

        elif isinstance(obj, InputEditionEntry):
            return f"Edition Entry {obj.parent.editionEntries.index(obj) + 1}"

        elif isinstance(obj, InputChapterAtom):
            return f"Chapter {obj.parent.chapterAtoms.index(obj)}"

        elif isinstance(obj, InputChapterDisplay):
            return obj.chapString

    tooltip = display

    def icon(self, index, obj):
        if isinstance(obj, BaseReader):
            return icons.icon(QFileInfo(obj.inputpathrel))


class AvailableUIDCol(AvailableEditionEntriesBaseColumn):
    headerdisplay = "UID"
    width = 192

    def display(self, index, obj):
        if isinstance(obj, InputEditionEntry):
            c, d = divmod(obj.editionUID, 16**4)
            b, c = divmod(c, 16**4)
            a, b = divmod(b, 16**4)

            return f"{a:04x} {b:04x} {c:04x} {d:04x}"

        elif isinstance(obj, InputChapterAtom):
            c, d = divmod(obj.chapterUID, 16**4)
            b, c = divmod(c, 16**4)
            a, b = divmod(b, 16**4)

            return f"{a:04x} {b:04x} {c:04x} {d:04x}"

        return ""

    tooltip = display


class AvailableStartCol(AvailableEditionEntriesBaseColumn):
    headerdisplay = "Start Time"
    width = 192

    def display(self, index, obj):
        if isinstance(obj, InputChapterAtom) and obj.chapterTimeStart is not None:
            s = obj.chapterTimeStart/10**9
            m, s = divmod(s, 60)
            h, m = divmod(int(m), 60)

            return f"{h}:{m:02d}:{s:012.9f}"

        return ""

    tooltip = display


class AvailableEndCol(AvailableEditionEntriesBaseColumn):
    headerdisplay = "Start Time"
    width = 192

    def display(self, index, obj):
        if isinstance(obj, InputChapterAtom) and obj.chapterTimeEnd is not None:
            s = obj.chapterTimeEnd/10**9
            m, s = divmod(s, 60)
            h, m = divmod(int(m), 60)

            return f"{h}:{m:02d}:{s:012.9f}"

        return ""

    tooltip = display


class AvailableEditionsTree(QTreeView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setSelectionBehavior(QTreeView.SelectRows)
        self.setSelectionMode(QTreeView.ExtendedSelection)
        self.setInputFiles(None)
        self.setMinimumWidth(640)

    def setInputFiles(self, input_files):
        self.input_files = input_files

        if input_files is not None:
            root = AvailableEditionsNode(input_files)
            cols = [
                AvailableEditionEntryNameCol(input_files),
                AvailableUIDCol(input_files),
                AvailableStartCol(input_files),
                AvailableEndCol(input_files),
            ]
            model = QItemModel(root, cols)
            self.setModel(model)

            for k, col in enumerate(cols):
                if hasattr(col, "width") and isinstance(col.width, int):
                    self.setColumnWidth(k, col.width)

                if hasattr(col, "itemDelegate") and callable(col.itemDelegate):
                    self.setItemDelegateForColumn(k, col.itemDelegate(self))

            for k in range(len(input_files)):
                idx = model.index(k, 0)

                if model.hasChildren(idx):
                    self.expand(idx)

        else:
            self.setModel(QItemModel(Node(None), []))


class AvailableEditionsSelection(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.selectionTree = AvailableEditionsTree(self)
        layout.addWidget(self.selectionTree)

        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)
        self.okayBtn = QPushButton("&OK", self)
        self.cancelBtn = QPushButton("&Cancel", self)

        hlayout.addStretch()
        hlayout.addWidget(self.okayBtn)
        hlayout.addWidget(self.cancelBtn)

        self.okayBtn.clicked.connect(self.applyAndClose)
        self.cancelBtn.clicked.connect(self.close)

    def handleSelectionChanged(self):
        self.okayBtn.setEnabled(
            len(self.selectionTree.selectionModel().selectedRows()) > 0)

    def applyAndClose(self):
        self.selectedEditions = [
            (index.parent().data(Qt.UserRole), index.data(Qt.UserRole))
            for index in self.selectionTree.selectionModel().selectedRows()
        ]
        self.done(1)
        self.close()

    def setInputFiles(self, input_files):
        self.selectionTree.setInputFiles(input_files)
        self.selectionTree.selectionModel().selectionChanged.connect(
            self.handleSelectionChanged)
        self.okayBtn.setEnabled(len(self.selectionTree.selectedIndexes()) > 0)


