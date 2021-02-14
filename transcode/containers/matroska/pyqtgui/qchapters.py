from PyQt5.QtWidgets import (QTreeView, QMenu, QAction, QMessageBox, QWidget, QHBoxLayout,
                             QFileIconProvider, QVBoxLayout, QLabel, QSpinBox, QTimeEdit,
                             QDialog, QPushButton, QItemDelegate, QMenu, QWidgetAction,
                             QToolButton, QCheckBox)
from PyQt5.QtCore import Qt, QModelIndex, QTime, QFileInfo, pyqtSignal, QSize
from transcode.pyqtgui.qitemmodel import Node, ChildNodes, NoChildren, QItemModel
from ..chapters import ChapterAtom, ChapterDisplay, EditionEntry, Editions
from functools import partial
import random
from .quidspinbox import UIDDelegate
from transcode.pyqtgui.qimageview import QImageView
from transcode.pyqtgui.slider import Slider
from transcode.pyqtgui.qtimeselect import QTimeSelect
from transcode.pyqtgui.treeview import TreeView as QTreeView
from transcode.filters.video.scenes import Scenes
from ..reader import MatroskaReader
from matroska.chapters import EditionEntry as InputEditionEntry
from matroska.chapters import ChapterAtom as InputChapterAtom
from matroska.chapters import ChapterDisplay as InputChapterDisplay
from transcode.containers.basereader import BaseReader, Track
from transcode.filters.base import BaseFilter

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


class EditionsNode(Node):
    def _wrapChildren(self, children):
        return EditionsChildren.fromValues(children, self)


class EditionsChildren(ChildNodes):
    @staticmethod
    def _wrap(value):
        return EditionNode(value)


class EditionNode(Node):
    def _wrapChildren(self, children):
        return EditionChildren.fromValues(children, self)


class EditionChildren(ChildNodes):
    @staticmethod
    def _wrap(value):
        return ChapterNode(value)


class ChapterNode(Node):
    def _iterChildren(self):
        return self.value.displays

    def _wrapChildren(self, children):
        return ChapterChildren.fromValues(children, self)


class ChapterChildren(ChildNodes):
    @staticmethod
    def _wrap(value):
        return DisplayNode(value)

    def _append(self, value):
        self.parent.value.displays.append(node.value)

    def _insert(self, index, value):
        self.parent.value.displays.insert(index, value)

    def _extend(self, values):
        self.parent.value.displays.extend(values)

    def _delitem(self, index):
        del self.parent.value.displays[index]

    def _setitem(self, index, value):
        self.parent.value.displays[index] = value


class DisplayNode(NoChildren):
    pass


class BaseColumn(object):
    checkstate = None
    fontmain = None
    fontalt = None
    fgcolor = None
    fgcoloralt = None
    bgcolor = None
    bgcoloralt = None
    name = None
    flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
    textalign = Qt.AlignLeft | Qt.AlignVCenter

    def __init__(self, tags, editions, attrname):
        self.tags = tags
        self.editions = editions
        self.attrname = attrname

    def editdata(self, index, obj):
        if isinstance(self.attrname, str):
            return getattr(obj, self.attrname)

    def seteditdata(self, index, obj, data):
        if data != self.editdata(index, obj):
            try:
                setattr(obj, self.attrname, data)

            except:
                return False

            return True

    def display(self, index, obj):
        return str(self.editdata(index, obj))

    def font(self, index, obj):
        return self.fontmain

    def bgdata(self, index, obj):
        return self.bgcolor

    def fgdata(self, index, obj):
        return self.fgcolor

    def contextmenu(self, index, obj):
        return partial(self.createContextMenu, obj=obj, index=index)

    def createContextMenu(self, table, index, obj):
        if isinstance(obj, EditionEntry):
            edrow = self.editions.index(obj)
            chrow = -1
            disprow = -1
            edindex = index
            chapindex = QModelIndex()

        elif isinstance(obj, ChapterAtom):
            edrow = self.editions.index(obj.parent)
            chrow = obj.parent.index(obj)
            disprow = -1
            edindex = index.parent()
            chapindex = index

        elif isinstance(obj, ChapterDisplay):
            edrow = self.editions.index(obj.parent.parent)
            chrow = obj.parent.parent.index(obj.parent)
            disprow = obj.parent.displays.index(obj)
            edindex = index.parent().parent()
            chapindex = index.parent()

        else:
            edrow = chrow = disprow = -1
            edindex = chapindex = index

        menu = QMenu(table)

        insertEdition = QAction("Insert Edition Entry before", table,
                                triggered=partial(table.addEdition, row=edrow))
        insertEdition.setEnabled(index.isValid())
        menu.addAction(insertEdition)


        insertEditionAfter = QAction("Insert Edition Entry after", table,
                                     triggered=partial(table.addEdition, row=edrow+1))
        insertEditionAfter.setEnabled(index.isValid())
        menu.addAction(insertEditionAfter)

        addEdition = QAction("Add Edition Entry at end", table,
                             triggered=table.addEdition)
        menu.addAction(addEdition)

        addFromInput = QAction("&Import existing Edition Entries from input...", table,
                               triggered=table.addFromInput)
        menu.addAction(addFromInput)

        menu.addSeparator()

        insertChapter = QAction("Insert Chapter before", table,
                                triggered=partial(table.addChapter,
                                                  row=chrow, parent=edindex))
        menu.addAction(insertChapter)

        insertChapterAfter = QAction("Insert Chapter after", table,
                                     triggered=partial(table.addChapter,
                                                       row=chrow+1, parent=edindex))
        menu.addAction(insertChapterAfter)

        addChapter = QAction("Add Chapter at end", table,
                             triggered=partial(table.addChapter,
                                               row=table.model().rowCount(edindex), parent=edindex))
        menu.addAction(addChapter)

        menu.addSeparator()

        insertChapterDisplay = QAction("Insert Chapter Display before", table,
                                       triggered=partial(table.addDisplay,
                                                         row=disprow, parent=chapindex))
        menu.addAction(insertChapterDisplay)

        insertChapterDisplayAfter = QAction("Insert Chapter Display after", table,
                                            triggered=partial(table.addDisplay,
                                                              row=disprow+1, parent=chapindex))
        menu.addAction(insertChapterDisplayAfter)

        addChapterDisplay = QAction("Add Chapter Display at end", table,
                                    triggered=partial(table.addDisplay,
                                                      row=table.model().rowCount(chapindex), parent=chapindex))
        menu.addAction(addChapterDisplay)


        if not index.isValid():
            insertChapter.setEnabled(False)
            insertChapterAfter.setEnabled(False)
            addChapter.setEnabled(False)
            addChapterDisplay.setEnabled(False)
            insertChapterDisplay.setEnabled(False)
            insertChapterDisplayAfter.setEnabled(False)

        elif isinstance(obj, EditionEntry):
            insertChapter.setEnabled(False)
            insertChapterAfter.setEnabled(False)
            addChapterDisplay.setEnabled(False)
            insertChapterDisplay.setEnabled(False)
            insertChapterDisplayAfter.setEnabled(False)

        elif isinstance(obj, ChapterAtom):
            insertChapterDisplay.setEnabled(False)
            insertChapterDisplayAfter.setEnabled(False)

        menu.addSeparator()

        removeSelected = QAction("Remove selected...", table,
                                 triggered=table.askDeleteSelected)

        removeSelected.setEnabled(
            len(table.selectionModel().selectedRows()) > 0)

        menu.addAction(removeSelected)

        return menu

    def flags(self, index, obj):
        if isinstance(obj, EditionEntry):
            return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

        elif isinstance(obj, ChapterAtom):
            if obj.parent.ordered:
                return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

            return Qt.ItemIsSelectable | Qt.ItemIsEnabled

        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsDragEnabled


class NameCol(BaseColumn):
    width = 192
    headerdisplay = "Edition/Chapter"

    def __init__(self, tags, editions):
        super().__init__(tags, editions, None)

    def editdata(self, index, obj):
        if isinstance(obj, ChapterDisplay):
            return obj.string

    def seteditdata(self, index, obj, value):
        if isinstance(obj, ChapterDisplay) and obj.string != value:
            obj.string = value
            return True

        return False

    def display(self, index, obj):
        if isinstance(obj, EditionEntry):
            return f"{self.editions.index(obj)}: Edition Entry"

        elif isinstance(obj, ChapterAtom):
            if obj.parent.ordered:
                if obj.displays:
                    return f"{obj.parent.index(obj)}: {obj.displays[0].string}"

                return f"{obj.parent.index(obj)}: Chapter"

            if obj.displays:
                return f"{obj.parent.index(obj) + 1}. {obj.displays[0].string}"

            return f"Chapter {obj.parent.index(obj) + 1}"

        elif isinstance(obj, ChapterDisplay):
            return obj.string


class DefaultCol(BaseColumn):
    width = 32
    headerdisplay = "Def"
    headertooltop = "Default"

    def __init__(self, tags, editions):
        super().__init__(tags, editions, "hidden")

    def flags(self, index, obj):
        if isinstance(obj, EditionEntry):
            return (super().flags(index, obj) | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEditable

        return super().flags(index, obj) & ~Qt.ItemIsEditable

    def checkstate(self, index, obj):
        if isinstance(obj, EditionEntry):
            return 2 if obj.default else 0

    def setcheckstate(self, index, obj, state):
        if isinstance(obj, EditionEntry):
            if obj.default and state == 0:
                obj.default = False
                return True

            elif not obj.default and state == 2:
                for edition in self.editions:
                    edition.default = edition is obj

                return True

    def display(self, index, obj):
        return ""


class EnabledCol(BaseColumn):
    width = 32
    headerdisplay = "En"
    headertooltop = "Enabled"

    def __init__(self, tags, editions):
        super().__init__(tags, editions, "enabled")

    def flags(self, index, obj):
        if isinstance(obj, ChapterAtom):
            return (super().flags(index, obj) | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEditable

        return super().flags(index, obj) & ~Qt.ItemIsEditable

    def checkstate(self, index, obj):
        if isinstance(obj, ChapterAtom):
            return 2 if obj.enabled else 0

    def setcheckstate(self, index, obj, state):
        if isinstance(obj, ChapterAtom):
            if obj.enabled and state == 0:
                obj.enabled = False
                return True

            elif not obj.enabled and state == 2:
                obj.enabled = True
                return True

    def display(self, index, obj):
        return ""


class OrderedCol(BaseColumn):
    width = 32
    headerdisplay = "Ord"
    headertooltip = "Ordered"

    def __init__(self, tags, editions):
        super().__init__(tags, editions, "ordered")

    def flags(self, index, obj):
        if isinstance(obj, EditionEntry):
            return (super().flags(index, obj) | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEditable

        return super().flags(index, obj) & ~Qt.ItemIsEditable

    def checkstate(self, index, obj):
        if isinstance(obj, EditionEntry):
            return 2 if obj.ordered else 0

    def setcheckstate(self, index, obj, state):
        if isinstance(obj, EditionEntry):
            if obj.ordered and state == 0:
                obj.ordered = False
                return True

            elif not obj.ordered and state == 2:
                obj.ordered = True
                return True

    def display(self, index, obj):
        return ""


class HiddenCol(BaseColumn):
    width = 32
    headerdisplay = "Hid"
    headertooltip = "Hidden"

    def __init__(self, tags, editions):
        super().__init__(tags, editions, "hidden")

    def flags(self, index, obj):
        if isinstance(obj, (EditionEntry, ChapterAtom)):
            return (super().flags(index, obj) | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEditable

        return super().flags(index, obj) & ~Qt.ItemIsEditable

    def checkstate(self, index, obj):
        if isinstance(obj, (EditionEntry, ChapterAtom)):
            return 2 if obj.hidden else 0

    def setcheckstate(self, index, obj, state):
        if isinstance(obj, (EditionEntry, ChapterAtom)):
            if obj.hidden and state == 0:
                obj.hidden = False
                return True

            elif not obj.hidden and state == 2:
                obj.hidden = True
                return True

    def display(self, index, obj):
        return ""


class LangCol(BaseColumn):
    width = 96
    headerdisplay = "Languages"

    def __init__(self, tags, editions):
        super().__init__(tags, editions, "languages")

    def flags(self, index, obj):
        if isinstance(obj, ChapterDisplay):
            return super().flags(index, obj) | Qt.ItemIsEditable

        return super().flags(index, obj) & ~Qt.ItemIsEditable

    def display(self, index, obj):
        if isinstance(obj, ChapterDisplay):
            editdata = self.editdata(index, obj)
            return ", ".join(editdata)

        return ""

    def seteditdata(self, index, obj, data):
        if isinstance(obj, ChapterDisplay):
            super().seteditdata(index, obj, data.replace(" ", "").split(","))
            return True


class CountryCol(BaseColumn):
    width = 96
    headerdisplay = "Countries"

    def __init__(self, tags, editions):
        super().__init__(tags, editions, "countries")

    def flags(self, index, obj):
        if isinstance(obj, ChapterDisplay):
            return super().flags(index, obj) | Qt.ItemIsEditable

        return super().flags(index, obj) & ~Qt.ItemIsEditable

    def display(self, index, obj):
        if isinstance(obj, ChapterDisplay):
            editdata = self.editdata(index, obj)
            return ", ".join(editdata)

        return ""

    def seteditdata(self, index, obj, data):
        if isinstance(obj, ChapterDisplay):
            super().seteditdata(index, obj, data.replace(" ", "").split(","))
            return True


class StartCol(BaseColumn):
    width = 128
    headerdisplay = "Start Time"

    def __init__(self, tags, editions):
        super().__init__(tags, editions, "timeStart")

    def editdata(self, index, obj):
        if isinstance(obj, ChapterAtom):
            return (obj.startFrame, obj.timeStart)

    def seteditdata(self, index, obj, value):
        if isinstance(obj, ChapterAtom):
            (n, t) = value

            if n is not None:
                if obj.startFrame != n:
                    obj.startFrame = n
                    return True

            else:
                if obj.timeStart != t:
                    obj.timeStart = t
                    return True

        return False

    def flags(self, index, obj):
        return super().flags(index, obj) | Qt.ItemIsEditable

    def display(self, index, obj):
        if isinstance(obj, ChapterAtom):
            (n, pts) = self.editdata(index, obj)

            if pts is None:
                return "—"

            m, s = divmod(pts/10**9, 60)
            h, m = divmod(int(m), 60)
            return f"{h}:{m:02d}:{s:012.9f} ({n})"

        return ""

    def itemDelegate(self, parent):
        delegate = TimeSelectDelegate(parent)
        delegate.setSource(self.editions.parent.vtrack)
        return delegate


class EndCol(BaseColumn):
    width = 128
    headerdisplay = "End Time"

    def __init__(self, tags, editions):
        super().__init__(tags, editions, None)

    def editdata(self, index, obj):
        if isinstance(obj, ChapterAtom):
            return (obj.endFrame, obj.timeEnd)

    def seteditdata(self, index, obj, value):
        if isinstance(obj, ChapterAtom):
            (n, t) = value

            if n is not None:
                if obj.endFrame != n:
                    obj.endFrame = n
                    return True

            else:
                if obj.timeEnd != t:
                    obj.timeEnd = t
                    return True

        return False

    def flags(self, index, obj):
        if isinstance(obj, ChapterAtom) and obj.parent.ordered:
            return super().flags(index, obj) | Qt.ItemIsEditable

        return super().flags(index, obj) & ~Qt.ItemIsEditable

    def display(self, index, obj):
        if isinstance(obj, ChapterAtom):
            (n, pts) = self.editdata(index, obj)

            if pts is None:
                return "—"

            m, s = divmod(pts/10**9, 60)
            h, m = divmod(int(m), 60)
            return f"{h}:{m:02d}:{s:012.9f}"

        return ""


class UIDCol(BaseColumn):
    width = 128
    headerdisplay = "UID"

    def __init__(self, tags, editions):
        super().__init__(tags, editions, "UID")

    def flags(self, index, obj):
        if isinstance(obj, (ChapterAtom, EditionEntry)):
            return super().flags(index, obj) | Qt.ItemIsEditable

        return super().flags(index, obj) & ~Qt.ItemIsEditable

    def display(self, index, obj):
        if isinstance(obj, (ChapterAtom, EditionEntry)):
            c, d = divmod(self.editdata(index, obj), 16**4)
            b, c = divmod(c, 16**4)
            a, b = divmod(b, 16**4)

            return f"{a:04x} {b:04x} {c:04x} {d:04x}"

        return ""

    def itemDelegate(self, parent):
        return UIDDelegate(parent)

    def contextmenu(self, index, obj):
        return partial(self.createContextMenu, obj=obj, index=index)

    def createContextMenu(self, table, index, obj):
        menu = super().createContextMenu(table, index, obj)
        selectRandom = QAction(f"Select random UID", table,
                               triggered=partial(self.selectRandomUID, obj, table.model()))

        menu.addAction(selectRandom)

        selectRandom.setEnabled(isinstance(obj, (ChapterAtom, EditionEntry)))

        return menu

    def selectRandomUID(self, obj, model):
        UID = random.randint(1, 2**64 - 1)

        if isinstance(obj, ChapterAtom):
            existingUIDs = {
                chap.UID for ed in self.editions for chap in ed if chap is not obj}

        else:
            existingUIDs = {ed.UID for ed in self.editions if ed is not obj}

        while UID in existingUIDs:
            UID = random.randint(1, 2**64 - 1)

        obj.UID = UID
        model.dataChanged.emit(QModelIndex(), QModelIndex())


class NewEditionDlg(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle("New Edition Entry")

        layout = QVBoxLayout()
        self.setLayout(layout)

        label = QLabel("Chapters:", self)
        self.chapterSpinBox = QSpinBox(self)
        self.chapterSpinBox.setMaximum(999)
        self.chapterSpinBox.setSpecialValueText("None")
        self.chapterSpinBox.valueChanged.connect(self._handleValueChanged)

        hlayout = QHBoxLayout()
        hlayout.addWidget(label)
        hlayout.addWidget(self.chapterSpinBox)
        layout.addLayout(hlayout)

        self.withDisplays = QCheckBox("Create ChapterDisplay entries", self)
        layout.addWidget(self.withDisplays)

        self.okayBtn = QPushButton("&OK", self)
        self.okayBtn.clicked.connect(self.accept)
        self.closeBtn = QPushButton("&Cancel", self)
        self.closeBtn.clicked.connect(self.reject)

        hlayout = QHBoxLayout()
        hlayout.addStretch()
        hlayout.addWidget(self.okayBtn)
        hlayout.addWidget(self.closeBtn)
        layout.addLayout(hlayout)

    def _handleValueChanged(self, value):
        self.withDisplays.setEnabled(bool(value))


class QChapterTree(QTreeView):
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMinimumWidth(540)
        self.setDragDropMode(QTreeView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionBehavior(QTreeView.SelectRows)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setData(None, None, None)

    def contextMenuEvent(self, event):
        selected = self.currentIndex()
        menu = self.model().data(selected, role=Qt.UserRole + 1)

        if callable(menu):
            menu = menu(self)

        if isinstance(menu, QMenu):
            menu.exec_(self.mapToGlobal(event.pos()))

    def setData(self, track, tags, editions):
        self.tags = tags
        self.vtrack = track
        self.editions = editions

        if editions is not None:
            cols = [
                NameCol(tags, editions),
                DefaultCol(tags, editions),
                OrderedCol(tags, editions),
                EnabledCol(tags, editions),
                HiddenCol(tags, editions),
                LangCol(tags, editions),
                CountryCol(tags, editions),
                StartCol(tags, editions),
                EndCol(tags, editions),
                UIDCol(tags, editions),
            ]

            root = EditionsNode(editions)
            model = QItemModel(root, cols)
            self.setModel(model)
            self.expandAll()

        else:
            self.setModel(QItemModel(Node(None), []))

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
            self, "Delete editions/chapters", "Do you wish to delete the selected editions/chapters?", QMessageBox.Yes | QMessageBox.No)

        if answer == QMessageBox.Yes:
            self.deleteSelected()

    def addEdition(self, row=-1):
        dlg = NewEditionDlg(self)

        if dlg.exec_():
            if row == -1:
                row = self.model().rowCount()

            existingUIDs = set()
            existingChapterUIDs = set()

            for edition in self.editions:
                existingUIDs.add(edition.UID)

                for atom in edition:
                    existingChapterUIDs.add(atom.UID)

            UID = random.randint(1, 2**64 - 1)

            while UID in existingUIDs:
                UID = random.randint(1, 2**64 - 1)

            edition = EditionEntry(UID=UID)

            for k in range(1, dlg.chapterSpinBox.value() + 1):
                UID = random.randint(1, 2**64 - 1)

                while UID in existingChapterUIDs:
                    UID = random.randint(1, 2**64 - 1)

                atom = ChapterAtom(UID, 0)
                edition.append(atom)
                existingChapterUIDs.add(UID)

                if dlg.withDisplays.checkState():
                    atom.displays.append(ChapterDisplay(f"Chapter {k}"))

            self.model().insertRow(row, edition)
            self.setCurrentIndex(self.model().index(row, 0))

    def addChapter(self, row=-1, parent=QModelIndex()):
        if row == -1:
            row = self.model().rowCount(parent)

        if row == 0:
            startFrame = 0

        else:
            startFrame = parent.child(row - 1, 0).data(Qt.UserRole).startFrame

        existingUIDs = set()

        for edition in self.editions:
            for chapter in edition:
                existingUIDs.add(chapter.UID)

        UID = random.randint(1, 2**64 - 1)

        while UID in existingUIDs:
            UID = random.randint(1, 2**64 - 1)

        chapter = ChapterAtom(UID, startFrame)
        self.model().insertRow(row, chapter, parent)
        self.setCurrentIndex(parent.child(row, 0))

    def addDisplay(self, row=-1, parent=QModelIndex()):
        if row == -1:
            row = self.model().rowCount(parent)

        self.model().insertRow(row, ChapterDisplay(""), parent)
        self.setCurrentIndex(parent.child(row, 0))
        self.edit(parent.child(row, 0))

    def importChapterAtom(self, chapteratom, existingChapterUIDs, ordered=False):
        chapterUID = chapteratom.chapterUID

        while chapterUID in existingChapterUIDs:
            chapterUID = random.randint(1, 2**64 - 1)

        if self.vtrack is not None:
            m, s = divmod(float(chapteratom.chapterTimeStart)/10**9, 60)
            h, m = divmod(int(m), 60)
            startFrame = self.vtrack.source.frameIndexFromPts(
                chapteratom.chapterTimeStart + 8*10**6, "-")

            if ordered:
                endFrame = self.vtrack.source.frameIndexFromPts(
                    chapteratom.chapterTimeEnd + 8*10**6, "-")

            else:
                endFrame = None

            timeStart = timeEnd = None

        else:
            startFrame = endFrame = None
            timeStart = chapteratom.chapterTimeStart

            if ordered:
                timeEnd = chapteratom.chapterTimeEnd

            else:
                timeEnd = None

        displays = []

        for display in chapteratom.chapterDisplays:
            displays.append(ChapterDisplay(
                display.chapString,
                list(display.chapLanguages or []),
                langIETF=list(display.chapLanguagesIETF or []),
                countries=list(display.chapCountries or []),
            ))

        hidden = bool(chapteratom.chapterFlagHidden)
        enabled = bool(chapteratom.chapterFlagEnabled)

        existingChapterUIDs.add(chapterUID)
        return ChapterAtom(chapterUID, startFrame, endFrame,
                           timeStart, timeEnd, displays, hidden, enabled)

    def importEdition(self, edition):
        existingEditionUIDs = {edition.UID for edition in self.editions}
        existingChapterUIDs = {chapter.UID
                               for edition in self.editions
                               for chapter in edition
                               }

        editionUID = edition.editionUID
        ordered = bool(edition.editionFlagOrdered)

        while editionUID in existingEditionUIDs:
            editionUID = random.randint(1, 2**64 - 1)

        chapters = []

        for chapteratom in edition.chapterAtoms:
            chapters.append(self.importChapterAtom(
                chapteratom, existingChapterUIDs, ordered))

        default = bool(edition.editionFlagDefault)
        hidden = bool(edition.editionFlagHidden)
        return EditionEntry(chapters, editionUID, hidden, default, ordered)

    def addFromInput(self):
        input_files = self.editions.parent.config.input_files
        dlg = AvailableEditionsSelection(self)
        dlg.setInputFiles(input_files)

        if dlg.exec_():
            model = self.model()
            neweditions = []

            for input_file, edition in dlg.selectedEditions:
                neweditions.append(self.importEdition(edition))

            model.insertRows(model.rowCount(), neweditions, QModelIndex())


class FrameSelectWidget(QWidget):
    frameSelectionChanged = pyqtSignal(int, QTime)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMaximumWidth(960)

        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self.setLayout(layout)

        self.imageView = QImageView(self)
        layout.addWidget(self.imageView)

        self.slider = Slider(self)
        self.slider.setOrientation(Qt.Horizontal)
        self.slider.valueChanged.connect(self.handleSliderChange)
        self.slider.setTickInterval(1)
        layout.addWidget(self.slider)

        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)

        self.prevLabel = QLabel(self)
        self.currentIndex = QSpinBox(self)
        self.currentIndex.valueChanged.connect(self.handleIndexChange)
        self.currentTime = QTimeEdit(self)
        self.currentTime.setDisplayFormat("H:mm:ss.zzz")
        self.currentTime.timeChanged.connect(self.handleTimeChange)
        self.nextLabel = QLabel(self)

        hlayout.addWidget(self.prevLabel)
        hlayout.addStretch()
        hlayout.addWidget(QLabel("Frame index:", self))
        hlayout.addWidget(self.currentIndex)
        hlayout.addWidget(QLabel("Timestamp:", self))
        hlayout.addWidget(self.currentTime)
        hlayout.addStretch()
        hlayout.addWidget(self.nextLabel)

        hlayout = QHBoxLayout()
        hlayout.setContentsMargins(0, 0, 0, 0)
        hlayout.setSpacing(4)
        layout.addLayout(hlayout)

        self.okayBtn = QPushButton("&OK", self)
        self.cancelBtn = QPushButton("&Cancel", self)

        hlayout.addStretch()
        hlayout.addWidget(self.okayBtn)
        hlayout.addWidget(self.cancelBtn)
        self.setFrameSource(None, None)

    def sizeHint(self):
        widgetHeights = (
            self.slider.height()
            + max([self.okayBtn.height(), self.cancelBtn.height()])
            + max([self.currentIndex.height(), self.currentTime.height()])
        )

        if isinstance(self.filters, BaseFilter):
            w, h = self.filters.width, self.filters.height
            sar = self.filters.sar

        elif isinstance(self.source, (Track, BaseFilter)):
            w, h = self.source.width, self.source.height
            sar = self.source.sar

        else:
            return super().sizeHint()

        dar = w*sar/h
        W, H = min([
            max([(w, h/sar), (w*sar, h)]),
            (960 - 8, (960 - 8)/dar),
            ((720 - 20 - widgetHeights)*dar, 720 - 20 - widgetHeights)
        ])

        return QSize(int(W + 8), int(H + 20 + widgetHeights))

    def setFrameSource(self, source, filters=None):
        self.source = source

        if source is not None:
            self.slider.setMaximum(self.source.framecount - 1)
            self.currentIndex.setMaximum(self.source.framecount - 1)
            self.filters = filters

            if self.filters is not None:
                lastpts = self.filters.pts_time[-1]
                self.slider.setSnapValues(self.filters.keyframes)

            else:
                lastpts = self.source.pts_time[-1]

                if isinstance(self.source, BaseFilter):
                    self.slider.setSnapValues(self.source.keyframes)

                else:
                    self.slider.setSnapValues(None)

            ms = int(lastpts*1000 + 0.5)
            s, ms = divmod(ms, 1000)
            m, s = divmod(s, 60)
            h, m = divmod(m, 60)
            self.currentTime.setMaximumTime(QTime(h, m, s, ms))
            self.slider.setValue(0)
            self._frameChange(0)

        else:
            self.slider.setSnapValues(None)

        self.update()

    def handleIndexChange(self, n):
        self._frameChange(n)

        self.slider.blockSignals(True)
        self.slider.setValue(n)
        self.slider.blockSignals(False)

    def handleSliderChange(self, n):
        self._frameChange(n)

        self.currentIndex.blockSignals(True)
        self.currentIndex.setValue(n)
        self.currentIndex.blockSignals(False)

    def _frameChange(self, n):
        if self.source is not None:
            if self.filters is not None:
                nn = n
                m = -1

                while m < 0 and nn < len(self.filters.indexMap):
                    m = self.filters.indexMap[nn]
                    nn += 1

                try:
                    pts = self.filters.pts_time[m]

                except:
                    pts = None

                try:
                    frame = next(self.filters.iterFrames(
                        m, whence="framenumber"))

                except StopIteration:
                    frame = None

                sar = self.filters.sar

            else:
                try:
                    pts = self.source.pts_time[n]

                except IndexError:
                    pts = None

                try:
                    frame = next(self.source.iterFrames(
                        n, whence="framenumber"))

                except StopIteration:
                    frame = None

                sar = self.source.sar

            if frame is not None:
                im = frame.to_image()
                self.imageView.setFrame(im.toqpixmap())
                self.imageView.setSar(sar)

            if pts is not None:
                ms = int(pts*1000+0.5)
                s, ms = divmod(ms, 1000)
                m, s = divmod(s, 60)
                h, m = divmod(m, 60)

                self.currentTime.blockSignals(True)
                self.currentTime.setTime(QTime(h, m, s, ms))
                self.currentTime.blockSignals(False)

            self.frameSelectionChanged.emit(n, self.currentTime.time())

    def handleTimeChange(self, t):
        if self.source is not None:
            if self.filters is not None:
                pts = t.msecsSinceStartOfDay()/1000
                n = self.filters.frameIndexFromPtsTime(pts, dir="-")

            else:
                pts = t.msecsSinceStartOfDay()/1000
                n = self.source.frameIndexFromPtsTime(pts, dir="-")

            self.slider.blockSignals(True)
            self.slider.setValue(n)
            self.slider.blockSignals(False)

            self.currentIndex.blockSignals(True)
            self.currentIndex.setValue(n)
            self.currentIndex.blockSignals(False)

            self._frameChange(n)


class QFrameSelect(QToolButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setPopupMode(QToolButton.MenuButtonPopup)
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.widget = FrameSelectWidget(self)
        self.widget.okayBtn.clicked.connect(self._handleOKClicked)
        self.widget.cancelBtn.clicked.connect(self._handleCancelClicked)

        act = QWidgetAction(self)
        act.setDefaultWidget(self.widget)

        self.menu = QMenu(self)
        self.menu.addAction(act)
        self.setMenu(self.menu)

        self.clicked.connect(self.showMenu)
        self.setFrameSource(None, None)
        self.setFrameSelection((0, 0))

    def showMenu(self):
        n, t = self.frameSelection()
        self.widget.slider.setValue(n)
        super().showMenu()

    def frameSelection(self):
        return self._frameSelection

    def setFrameSelection(self, value):
        n, t = value

        if self.widget.source is not None:
            if self.widget.filters is not None:
                self._frameSelection = (
                    n, int(10**9*self.widget.filters.pts_time[n]))

            else:
                self._frameSelection = (
                    n, int(10**9*self.widget.source.pts_time[n]))

        m, s = divmod(float(t/10**9), 60)
        h, m = divmod(int(m), 60)

        self.setText(f"{h}:{m:02d}:{s:012.9f}")

    def setFrameSource(self, source, filters=None):
        self.widget.setFrameSource(source, filters)

    def _handleOKClicked(self):
        self.setFrameSelection((self.widget.slider.value(
        ), self.widget.currentTime.time().msecsSinceStartOfDay()*10**6))
        self.menu.close()

    def _handleCancelClicked(self):
        self.menu.close()


class TimeSelectDelegate(QItemDelegate):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setSource(None)

    def setSource(self, source):
        self._source = source

    def source(self):
        return self._source

    def createEditor(self, parent, option, index):
        if self.source() is not None:
            editor = QFrameSelect(parent)
            editor.setFrameSource(self.source().source, self.source().filters)
            return editor

    def setEditorData(self, editor, index):
        if self.source() is not None:
            data = index.data(Qt.EditRole)
            editor.setFrameSelection(data)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.frameSelection(), Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class QChaptersWidget(QWidget):
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.chapterTree = QChapterTree(self)
        self.chapterTree.contentsModified.connect(self.contentsModified)
        layout.addWidget(self.chapterTree)
        self.chapterTree.setMinimumWidth(640)
        self.chapterTree.setMinimumHeight(240)

        btnlayout = QHBoxLayout()
        layout.addLayout(btnlayout)

        self.importBtn = QPushButton(
            "&Import existing Edition Entries from input...", self)
        self.removeBtn = QPushButton("&Remove selected...", self)
        self.importBtn.clicked.connect(self.chapterTree.addFromInput)
        self.removeBtn.clicked.connect(self.chapterTree.askDeleteSelected)

        btnlayout.addWidget(self.importBtn)
        btnlayout.addWidget(self.removeBtn)
        btnlayout.addStretch()

    def setData(self, tracks, tags, chapters):
        for track in tracks:
            if track.type == "video":
                self.vtrack = track
                break

        else:
            self.vtrack = None

        self.chapterTree.setData(self.vtrack, tags, chapters)

    def handleSelectionChanged(self):
        self.removeBtn.setEnabled(
            len(self.chapterTree.selectionModel().selectedRows()) > 0)
