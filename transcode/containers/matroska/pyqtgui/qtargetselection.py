from PyQt5.QtWidgets import (QWidget, QToolButton, QPushButton, QVBoxLayout, QHBoxLayout,
                             QWidgetAction, QMenu)
from PyQt5.QtCore import Qt, pyqtSignal, QModelIndex, QSize

from transcode.pyqtgui.qitemmodel import QItemModel, Node, ChildNodes, NoChildren
from transcode.pyqtgui.treeview import TreeView as QTreeView
from copy import deepcopy

from ..chapters import Editions, EditionEntry, ChapterAtom
from ...basewriter import TrackList, Track
from ..attachments import Attachments, AttachedFile


class TargetsRoot(Node):
    def _wrapChildren(self, children):
        return TargetChildren.fromValues(children, self)


class TargetChildren(ChildNodes):
    @staticmethod
    def _wrap(value):
        if isinstance(value, TrackList):
            return TargetTrackListNode(value)

        elif isinstance(value, Attachments):
            return TargetAttachmentsNode(value)

        if isinstance(value, Editions):
            return TargetEditionsNode(value)


class TargetTrackListNode(Node):
    def _wrapChildren(self, children):
        return TargetTrackListChildren.fromValues(children, self)


class TargetTrackListChildren(ChildNodes):
    @staticmethod
    def _wrap(value):
        return TargetTrackNode(value)


class TargetTrackNode(NoChildren):
    pass


class TargetAttachmentsNode(Node):
    def _wrapChildren(self, children):
        return TargetAttachmentsChildren.fromValues(children, self)


class TargetAttachmentsChildren(ChildNodes):
    @staticmethod
    def _wrap(value):
        return TargetAttachmentNode(value)


class TargetAttachmentNode(NoChildren):
    pass


class TargetEditionsNode(Node):
    def _wrapChildren(self, children):
        return TargetEditionsChildren.fromValues(children, self)


class TargetEditionsChildren(ChildNodes):
    @staticmethod
    def _wrap(value):
        return TargetEditionNode(value)


class TargetEditionNode(Node):
    def _wrapChildren(self, children):
        return TargetEditionChildren.fromValues(children, self)


class TargetEditionChildren(ChildNodes):
    @staticmethod
    def _wrap(value):
        return TargetChapterNode(value)


class TargetChapterNode(NoChildren):
    pass


class BaseTargetCol(object):
    def __init__(self, tracks, editions, attachments, targeteditions, targetchapters, targettracks, targetattachments):
        self.editions = editions
        self.tracks = tracks
        self.attachments = attachments
        self.targeteditions = targeteditions
        self.targetchapters = targetchapters
        self.targettracks = targettracks
        self.targetattachments = targetattachments

class TargetItemCol(BaseTargetCol):
    headerdisplay = "Target"
    width = 360

    def checkstate(self, index, obj):
        if isinstance(obj, EditionEntry):
            return 2 if obj in self.targeteditions else 0

        elif isinstance(obj, ChapterAtom):
            return 2 if obj in self.targetchapters else 0

        elif isinstance(obj, Track):
            return 2 if obj in self.targettracks else 0

        elif isinstance(obj, AttachedFile):
            return 2 if obj in self.targetattachments else 0

    def setcheckstate(self, index, obj, state):
        if state == 0:
            if isinstance(obj, EditionEntry):
                self.targeteditions.remove(obj)

            elif isinstance(obj, ChapterAtom):
                self.targetchapters.remove(obj)

            elif isinstance(obj, Track):
                self.targettracks.remove(obj)

            elif isinstance(obj, AttachedFile):
                self.targetattachments.remove(obj)

        elif state == 2:
            if isinstance(obj, EditionEntry):
                self.targeteditions.append(obj)

            elif isinstance(obj, ChapterAtom):
                self.targetchapters.append(obj)

            elif isinstance(obj, Track):
                self.targettracks.append(obj)

            elif isinstance(obj, AttachedFile):
                self.targetattachments.append(obj)

        return True

    def display(self, index, obj):
        if isinstance(obj, Editions):
            return "Chapter Editions"

        elif isinstance(obj, TrackList):
            return "Tracks"

        elif isinstance(obj, Attachments):
            return "Attachments"

        elif isinstance(obj, EditionEntry):
            return f"Edition {self.editions.index(obj)}"

        elif isinstance(obj, Track):
            return f"{obj.track_index}: {obj.name}"

        elif isinstance(obj, AttachedFile):
            return f"{self.attachments.index(obj)}: {obj.fileName}"

        elif isinstance(obj, ChapterAtom):
            if len(obj.displays):
                return f"{obj.parent.index(obj) + 1}. {obj.displays[0].string}"

            return f"Chapter {obj.parent.index(obj) + 1}"

        return repr(obj)

    tooltip = display

    def flags(self, index, obj):
        if isinstance(obj, (EditionEntry, ChapterAtom, Track, AttachedFile)):
            return Qt.ItemIsUserCheckable | Qt.ItemIsEnabled

        return Qt.ItemIsEnabled

    def sizehint(self, index, obj):
        return QSize(192, -1)

    def headersizehint(self, index):
        return QSize(192, -1)


class TargetUIDCol(BaseTargetCol):
    headerdisplay = "UID"

    def display(self, index, obj):
        if isinstance(obj, (EditionEntry, AttachedFile, ChapterAtom)):
            uid = obj.UID

        elif isinstance(obj, Track):
            uid = obj.trackUID

        else:
            return ""

        c, d = divmod(uid, 16**4)
        b, c = divmod(c, 16**4)
        a, b = divmod(b, 16**4)

        return f"{a:04x} {b:04x} {c:04x} {d:04x}"

    def flags(self, index, obj):
        return Qt.ItemIsEnabled


class QTargetSelectionTree(QTreeView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragEnabled(False)
        self.setAcceptDrops(False)
        self._selection = ([], [], [], [])
        self.setChoices([], [], [])
        self.setTargetSelection([], [], [], [])

    def setChoices(self, tracks, editions, attachments):
        choices = []

        if len(tracks):
            choices.append(tracks)

        if len(editions):
            choices.append(editions)

        if len(attachments):
            choices.append(attachments)

        root = TargetsRoot(choices)
        self.cols = [
            TargetItemCol(tracks, editions, attachments, *self._selection),
            TargetUIDCol(tracks, editions, attachments, *self._selection),
            ]
        self.setModel(QItemModel(root, self.cols))

        for k, col in enumerate(self.cols):
            if hasattr(col, "width") and isinstance(col.width, int):
                self.setColumnWidth(k, col.width)

            if hasattr(col, "itemDelegate") and callable(col.itemDelegate):
                self.setItemDelegateForColumn(k, col.itemDelegate(self))

        self.expandAll()

    def setTargetSelection(self, targettracks, targeteditions, targetchapters, targetattachments):
        self._selection = (targettracks, targeteditions, targetchapters, targetattachments)

        for col in self.cols:
            col.targeteditions = targeteditions
            col.targetchapters = targetchapters
            col.targettracks = targettracks
            col.targetattachments = targetattachments

        self.model().dataChanged.emit(QModelIndex(), QModelIndex())

    def clearSelection(self):
        for cat in self._selection:
            cat.clear()

        self.model().dataChanged.emit(QModelIndex(), QModelIndex())


class QTargetSelection(QToolButton):
    selectionChanged = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setPopupMode(QToolButton.MenuButtonPopup)
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        widget = QWidget(self)
        vlayout = QVBoxLayout()
        widget.setLayout(vlayout)

        self.tree = QTargetSelectionTree(widget)
        self.tree.setMinimumWidth(640)
        self.tree.setMinimumHeight(480)

        vlayout.addWidget(self.tree)

        hlayout = QHBoxLayout()
        vlayout.addLayout(hlayout)

        self.clearBtn = QPushButton("&Clear", widget)
        self.okayBtn = QPushButton("&OK", widget)
        self.cancelBtn = QPushButton("&Cancel", widget)

        self.clearBtn.clicked.connect(self.tree.clearSelection)
        self.okayBtn.clicked.connect(self._handleOKClicked)
        self.cancelBtn.clicked.connect(self._handleCancelClicked)


        hlayout.addWidget(self.clearBtn)
        hlayout.addStretch()
        hlayout.addWidget(self.okayBtn)
        hlayout.addWidget(self.cancelBtn)

        act = QWidgetAction(self)
        act.setDefaultWidget(widget)

        self.menu = QMenu(self)
        self.menu.addAction(act)
        self.setMenu(self.menu)
        self.menu.aboutToHide.connect(self._handleMenuHide)
        self.clicked.connect(self.showMenu)
        self.setTargetSelection([], [], [], [])

    def setChoices(self, tracks, editions, attachments):
        self.tree.setChoices(tracks, editions, attachments)

    def setTargetSelection(self, targettracks, targeteditions, targetchapters, targetattachments):
        self._selection = (targettracks, targeteditions, targetchapters, targetattachments)
        self._selection_copy = (targettracks.copy(), targeteditions.copy(),
                                targetchapters.copy(), targetattachments.copy())
        self.tree.setTargetSelection(*self._selection_copy)
        self.updateDisplay()

    def targetSelection(self):
        return self._selection

    def _handleOKClicked(self):
        for l1, l2 in zip(self._selection, self._selection_copy):
            l1.clear()
            l1.extend(l2)

        self.menu.close()
        self.updateDisplay()

    def _handleCancelClicked(self):
        self.menu.close()

    def _handleMenuHide(self):
        for l1, l2 in zip(self._selection, self._selection_copy):
            l2.clear()
            l2.extend(l1)

    def updateDisplay(self):
        display = []
        tracks, editions, chapters, attachments = self._selection

        if len(tracks) == 1:
            display.append("1 track")

        elif len(tracks) > 1:
            display.append(f"{len(tracks)} tracks")

        if len(editions) == 1:
            display.append("1 edition")

        elif len(editions) > 1:
            display.append(f"{len(editions)} editions")

        if len(chapters) == 1:
            display.append("1 chapter")

        elif len(chapters) > 1:
            display.append(f"{len(chapters)} chapters")

        if len(attachments) == 1:
            display.append("1 attachment")

        elif len(attachments) > 1:
            display.append(f"{len(attachments)} attachments")

        if len(display) == 0:
            display.append("No targets")

        self.setText(", ".join(display))
