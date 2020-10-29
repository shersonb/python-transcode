from PyQt5.QtWidgets import (QTreeView, QMenu, QAction, QMessageBox, QWidget, QHBoxLayout,
                             QFileIconProvider, QVBoxLayout, QLabel, QSpinBox, QTimeEdit,
                             QDialog, QPushButton)
from PyQt5.QtCore import Qt, QModelIndex, QTime, QFileInfo, pyqtSignal
from transcode.pyqtgui.qitemmodel import Node, ChildNodes, NoChildren, QItemModel
from ..chapters import ChapterAtom, ChapterDisplay, EditionEntry, Editions
from functools import partial
import random
from .quidspinbox import UIDDelegate
from transcode.pyqtgui.qimageview import QImageView
from transcode.pyqtgui.slider import Slider
from transcode.filters.video.scenes import Scenes
from ..reader import MatroskaReader
from matroska.chapters import EditionEntry as InputEditionEntry
from matroska.chapters import ChapterAtom as InputChapterAtom
from matroska.chapters import ChapterDisplay as InputChapterDisplay
from transcode.containers.basereader import BaseReader

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
            c, d = divmod(obj.editionUID, 16**8)
            b, c = divmod(c, 16**8)
            a, b = divmod(b, 16**8)

            return f"{a:08x} {b:08x} {c:08x} {d:08x}"

        elif isinstance(obj, InputChapterAtom):
            c, d = divmod(obj.chapterUID, 16**8)
            b, c = divmod(c, 16**8)
            a, b = divmod(b, 16**8)

            return f"{a:08x} {b:08x} {c:08x} {d:08x}"

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
            (index.data(Qt.UserRole), index.data(Qt.UserRole))
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
        return getattr(obj, self.attrname)

    def seteditdata(self, index, obj, data):
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

        menu = QMenu(table)

        insertEdition = QAction("Insert Edition Entry before", table,
                                triggered=partial(table.addEdition, row=edrow))
        menu.addAction(insertEdition)

        insertEditionAfter = QAction("Insert Edition Entry after", table,
                                     triggered=partial(table.addEdition, row=edrow+1))
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

        if isinstance(obj, EditionEntry):
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
                for edition in obj.parent:
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

    def flags(self, index, obj):
        return super().flags(index, obj) & ~Qt.ItemIsEditable

    def display(self, index, obj):
        if isinstance(obj, ChapterAtom):
            pts = self.editdata(index, obj)
            m, s = divmod(pts/10**9, 60)
            h, m = divmod(int(m), 60)
            return f"{h}:{m:02d}:{s:012.9f}"

        return ""

    def seteditdata(self, index, obj, data):
        if isinstance(obj, ChapterDisplay):
            super().seteditdata(index, obj, data.replace(" ", "").split(","))
            return True


class EndCol(BaseColumn):
    width = 128
    headerdisplay = "End Time"

    def __init__(self, tags, editions):
        super().__init__(tags, editions, "timeEnd")

    def flags(self, index, obj):
        return super().flags(index, obj) & ~Qt.ItemIsEditable

    def display(self, index, obj):
        if isinstance(obj, ChapterAtom):
            pts = self.editdata(index, obj)

            if pts is None:
                return "—"

            m, s = divmod(pts/10**9, 60)
            h, m = divmod(int(m), 60)
            return f"{h}:{m:02d}:{s:012.9f}"

        return ""

    def seteditdata(self, index, obj, data):
        if isinstance(obj, ChapterDisplay):
            super().seteditdata(index, obj, data.replace(" ", "").split(","))
            return True


class UIDCol(BaseColumn):
    width = 256
    headerdisplay = "UID"

    def __init__(self, tags, editions):
        super().__init__(tags, editions, "UID")

    def flags(self, index, obj):
        if isinstance(obj, (ChapterAtom, EditionEntry)):
            return super().flags(index, obj) | Qt.ItemIsEditable

        return super().flags(index, obj) & ~Qt.ItemIsEditable

    def display(self, index, obj):
        if isinstance(obj, (ChapterAtom, EditionEntry)):
            c, d = divmod(self.editdata(index, obj), 16**8)
            b, c = divmod(c, 16**8)
            a, b = divmod(b, 16**8)

            return f"{a:08x} {b:08x} {c:08x} {d:08x}"

        return ""

    def itemDelegate(self, parent):
        return UIDDelegate(parent)


class QChapterTree(QTreeView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMinimumWidth(540)
        self.setDragDropMode(QTreeView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionBehavior(QTreeView.SelectRows)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setData(None, None)

    def contextMenuEvent(self, event):
        selected = self.currentIndex()
        menu = self.model().data(selected, role=Qt.UserRole + 1)

        if callable(menu):
            menu = menu(self)

        if isinstance(menu, QMenu):
            menu.exec_(self.mapToGlobal(event.pos()))

    def setData(self, tags, editions):
        self.tags = tags
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

            for k, col in enumerate(cols):
                if hasattr(col, "width") and isinstance(col.width, int):
                    self.setColumnWidth(k, col.width)

                if hasattr(col, "itemDelegate") and callable(col.itemDelegate):
                    self.setItemDelegateForColumn(k, col.itemDelegate(self))

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
            self, "Delete tags", "Do you wish to delete the selected tags? Any child tags will also be lost!", QMessageBox.Yes | QMessageBox.No)

        if answer == QMessageBox.Yes:
            self.deleteSelected()

    def deleteSelected(self):
        model = self.model()
        selected = {model.getNode(index) for index in self.selectedIndexes()}
        removed = set()

        for node in selected:
            parent = node.parent

            if node not in removed:
                model.removeRow(parent.index(node), model.findIndex(parent))
                removed.add(node)

                if node.descendants is not None:
                    removed.update(node.descendants)

    def addEdition(self, row=-1):
        if row == -1:
            row = self.model().rowCount()

        existingUIDs = set()

        for edition in self.editions:
            existingUIDs.add(edition.UID)

        UID = random.randint(1, 2**128 - 1)

        while UID in existingUIDs:
            UID = random.randint(1, 2**128 - 1)

        edition = EditionEntry(UID=UID)
        self.model().insertRow(row, edition)
        self.setCurrentIndex(parent.child(row, 0))

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

        UID = random.randint(1, 2**128 - 1)

        while UID in existingUIDs:
            UID = random.randint(1, 2**128 - 1)

        chapter = ChapterAtom(UID, startFrame)
        self.model().insertRow(row, chapter, parent)
        self.setCurrentIndex(parent.child(row, 0))

    def addDisplay(self, row=-1, parent=QModelIndex()):
        if row == -1:
            row = self.model().rowCount(parent)

        self.model().insertRow(row, ChapterDisplay(""), parent)
        self.setCurrentIndex(parent.child(row, 0))
        self.edit(parent.child(row, 0))

    def addFromInput(self):
        dlg = AvailableEditionsSelection(self)
        dlg.setInputFiles(self.editions.parent.config.input_files)
        existingEditionUIDs = {edition.UID for edition in self.editions}
        existingChapterUIDs = {chapter.UID
                               for edition in self.editions
                               for chapter in edition
                               }

        vtrack = self.editions.parent.vtrack

        if dlg.exec_():
            model = self.model()
            neweditions = []

            for input_file, edition in dlg.selectedEditions:
                editionUID = edition.editionUID
                ordered = bool(edition.editionFlagOrdered)

                if vtrack:
                    frameIndexFromPts = vtrack.source.frameIndexFromPts

                else:
                    for track in input_files.tracks:
                        if track.type == "video":
                            frameIndexFromPts = track.frameIndexFromPts
                            break

                    else:
                        frameIndexFromPts = None

                while editionUID in existingEditionUIDs:
                    editionUID = random.randint(1, 2**128 - 1)

                chapters = []

                for chapteratom in edition.chapterAtoms:
                    chapterUID = chapteratom.chapterUID

                    while chapterUID in existingChapterUIDs:
                        chapterUID = random.randint(1, 2**128 - 1)

                    startFrame = frameIndexFromPts(
                        chapteratom.chapterTimeStart + 8*10**6, "-")

                    if ordered:
                        endFrame = frameIndexFromPts(
                            chapteratom.chapterTimeEnd, "-")

                    else:
                        endFrame = None

                    displays = []

                    for display in chapteratom.chapterDisplays:
                        displays.append(ChapterDisplay(
                            display.chapString,
                            list(display.chapLanguages or []),
                            langIETF=list(display.chapLanguageIETF or []),
                            countries=list(display.chapCountries or []),
                        ))

                    hidden = bool(chapteratom.chapterFlagHidden)
                    enabled = bool(chapteratom.chapterFlagEnabled)

                    newchapteratom = ChapterAtom(chapterUID, startFrame, endFrame,
                                                 displays, hidden, enabled)
                    chapters.append(newchapteratom)

                    existingChapterUIDs.add(chapterUID)

                default = bool(edition.editionFlagDefault)
                hidden = bool(edition.editionFlagHidden)
                newedition = EditionEntry(
                    chapters, editionUID, hidden, default, ordered)
                neweditions.append(newedition)
                existingEditionUIDs.add(editionUID)

            model.insertRows(model.rowCount(), neweditions, QModelIndex())


class QFrameSelect(QWidget):
    frameSelectionChanged = pyqtSignal(int, QTime)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
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
        self.setFrameSource(None, None)

    def setFrameSource(self, source, filters=None):
        self.source = source

        if source is not None:
            self.slider.setMaximum(self.source.framecount - 1)
            self.currentIndex.setMaximum(self.source.framecount - 1)
            self.filters = filters

            if self.filters is not None:
                lastpts = self.filters.pts_time[-1]

                for filter in self.filters:
                    if isinstance(filter, Scenes):
                        self.slider.setSnapValues(filter.zone_indices)
                        break
                else:
                    self.slider.setSnapValues(None)

            else:
                lastpts = self.source.pts_time[-1]
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

            self._frameChange(n)


class QChaptersWidget(QWidget):
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.chapterTree = QChapterTree(self)
        layout.addWidget(self.chapterTree)
        self.chapterTree.setMinimumWidth(640)
        self.chapterTree.setMinimumHeight(240)

        frameselectlayout = QHBoxLayout()
        layout.addLayout(frameselectlayout)
        self.startFrameSelect = QFrameSelect(self)
        self.startFrameSelect.imageView.setMaximumHeight(360)
        self.startFrameSelect.frameSelectionChanged.connect(
            self.handleStartSelectionChange)
        self.endFrameSelect = QFrameSelect(self)
        self.endFrameSelect.frameSelectionChanged.connect(
            self.handleEndSelectionChange)
        self.endFrameSelect.setHidden(True)
        self.endFrameSelect.imageView.setMaximumHeight(360)
        frameselectlayout.addWidget(self.startFrameSelect)
        frameselectlayout.addWidget(self.endFrameSelect)

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

    def handleStartSelectionChange(self, n, t):
        selected = self.chapterTree.currentIndex().data(Qt.UserRole)

        if isinstance(selected, ChapterDisplay):
            selected = selected.parent

        if isinstance(selected, ChapterAtom):
            selected.startFrame = n
            self.chapterTree.model().emitDataChanged()

    def handleEndSelectionChange(self, n, t):
        selected = self.chapterTree.currentIndex().data(Qt.UserRole)

        if isinstance(selected, ChapterDisplay):
            selected = selected.parent

        if isinstance(selected, ChapterAtom):
            selected.endFrame = n
            self.chapterTree.model().emitDataChanged()

    def handleIndexChange(self, newindex, oldindex):
        selected = newindex.data(Qt.UserRole)

        if isinstance(selected, ChapterDisplay):
            selected = selected.parent

        if isinstance(selected, ChapterAtom):
            self.endFrameSelect.setHidden(not selected.parent.ordered)
            self.startFrameSelect.blockSignals(True)
            self.startFrameSelect.slider.setValue(selected.startFrame)
            self.startFrameSelect.blockSignals(False)

            if selected.parent.ordered:
                self.endFrameSelect.blockSignals(True)
                self.endFrameSelect.slider.setValue(
                    selected.endFrame or selected.startFrame)
                self.endFrameSelect.blockSignals(False)

    def setData(self, tags, chapters):
        self.chapterTree.setData(tags, chapters)

        if chapters is not None:
            self.chapterTree.selectionModel().currentChanged.connect(self.handleIndexChange)
            self.chapterTree.model().dataChanged.connect(self.contentsModified)
            self.chapterTree.model().rowsInserted.connect(self.contentsModified)
            self.chapterTree.model().rowsRemoved.connect(self.contentsModified)
            self.chapterTree.model().rowsMoved.connect(self.contentsModified)
            self.chapterTree.selectionModel().selectionChanged.connect(
                self.handleSelectionChanged)
            self.handleSelectionChanged()

            if chapters.parent is not None and chapters.parent.vtrack is not None:
                self.startFrameSelect.blockSignals(True)
                self.startFrameSelect.setFrameSource(
                    chapters.parent.vtrack.source, chapters.parent.vtrack.filters)
                self.startFrameSelect.blockSignals(False)

                self.endFrameSelect.blockSignals(True)
                self.endFrameSelect.setFrameSource(
                    chapters.parent.vtrack.source, chapters.parent.vtrack.filters)
                self.endFrameSelect.blockSignals(False)

            else:
                self.startFrameSelect.blockSignals(True)
                self.startFrameSelect.setFrameSource(None)
                self.startFrameSelect.blockSignals(False)

                self.endFrameSelect.blockSignals(True)
                self.endFrameSelect.setFrameSource(None)
                self.endFrameSelect.blockSignals(False)

    def handleSelectionChanged(self):
        self.removeBtn.setEnabled(
            len(self.chapterTree.selectionModel().selectedRows()) > 0)
