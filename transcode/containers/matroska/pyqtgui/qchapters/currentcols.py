from PyQt5.QtWidgets import QMenu, QAction
from PyQt5.QtCore import Qt, QModelIndex
from functools import partial
import random

from matroska.chapters import ChapterAtom as InputChapterAtom
from matroska.chapters import ChapterDisplay as InputChapterDisplay

from transcode.containers.matroska.chapters import (ChapterAtom, ChapterDisplay,
                                                    EditionEntry, Editions)
from transcode.pyqtgui.qitemmodel import Node, ChildNodes, NoChildren, QItemModel
from ..quidspinbox import UIDDelegate
from .timeselect import TimeSelectDelegate


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

            except Exception:
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

        #addEdition = QAction("Add Edition Entry at end", table,
                             #triggered=table.addEdition)
        #menu.addAction(addEdition)

        addFromInput = QAction("&Import existing Edition Entries from input file...", table,
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

        #addChapter = QAction("Add Chapter at end", table,
                             #triggered=partial(table.addChapter,
                                               #row=table.model().rowCount(edindex), parent=edindex))
        #menu.addAction(addChapter)

        menu.addSeparator()

        insertChapterDisplay = QAction("Insert Chapter Display before", table,
                                       triggered=partial(table.addDisplay,
                                                         row=disprow, parent=chapindex))
        menu.addAction(insertChapterDisplay)

        insertChapterDisplayAfter = QAction("Insert Chapter Display after", table,
                                            triggered=partial(table.addDisplay,
                                                              row=disprow+1, parent=chapindex))
        menu.addAction(insertChapterDisplayAfter)

        #addChapterDisplay = QAction("Add Chapter Display at end", table,
                                    #triggered=partial(table.addDisplay,
                                                      #row=table.model().rowCount(chapindex), parent=chapindex))
        #menu.addAction(addChapterDisplay)


        if not index.isValid():
            insertChapter.setEnabled(False)
            insertChapterAfter.setEnabled(False)
            #addChapter.setEnabled(False)
            #addChapterDisplay.setEnabled(False)
            insertChapterDisplay.setEnabled(False)
            insertChapterDisplayAfter.setEnabled(False)

        elif isinstance(obj, EditionEntry):
            insertChapter.setEnabled(False)
            insertChapterAfter.setEnabled(False)
            #addChapterDisplay.setEnabled(False)
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

        menu.addSeparator()

        importChapters = QAction("&Import chapters from xml...", table,
                             triggered=table.importChapters)

        exportChapters = QAction("&Export selected chapters...", table,
                             triggered=table.exportChapters)

        menu.addAction(importChapters)
        menu.addAction(exportChapters)
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
    width = 192
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
    width = 192
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

            if n is None and not obj.parent.ordered:
                if obj.next is not None:
                    n = obj.next.startFrame

                elif obj.mkvfile is not None and obj.mkvfile.vtrack is not None:
                    n = obj.mkvfile.vtrack.framecount

            if pts is None:
                return "—"

            m, s = divmod(pts/10**9, 60)
            h, m = divmod(int(m), 60)
            return f"{h}:{m:02d}:{s:012.9f} ({n})"

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
