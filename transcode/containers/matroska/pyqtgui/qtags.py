from PyQt5.QtWidgets import QApplication, QWidget
import sys
from PyQt5.QtCore import (Qt, QAbstractListModel, QAbstractItemModel, QAbstractTableModel, QModelIndex,
                          QVariant, QItemSelectionModel, QItemSelection, pyqtSignal, pyqtSlot, QMimeData)
from PyQt5 import QtCore
from PyQt5.QtWidgets import (QDialog, QLabel, QListWidgetItem, QListView, QVBoxLayout, QHBoxLayout,
                             QAbstractItemView, QMessageBox, QPushButton, QTreeView, QTableView, QHeaderView, QSpinBox, QFrame,
                             QLineEdit, QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox, QItemDelegate,
                             QMenu, QAction, QScrollArea)
from PyQt5.QtGui import QFont, QIcon, QDrag, QBrush, QPainter, QRegExpValidator

from transcode.pyqtgui.qitemmodel import QItemModel, Node, ChildNodes
from ..tags import Tag, Tags, SimpleTag
from transcode.pyqtgui.qlangselect import LanguageDelegate, LANGUAGES
from titlecase import titlecase
from functools import partial

from ..chapters import Editions, EditionEntry, ChapterAtom
from ...basewriter import TrackList, Track
from ..attachments import Attachments, AttachedFile

class TagItemModel(QItemModel):
    def dropItems(self, items, action, row, column, parent):
        if row == -1:
            row = self.rowCount(parent)

        node = self.getNode(parent)

        j = 0

        for k, item in enumerate(items):
            old_parent = self.findIndex(item.parent)
            old_row = item.parent.index(item)
            self.moveRow(old_row, row + k - j, old_parent, parent)

            if self.getNode(old_parent) is self.getNode(parent) and old_row < row:
                j += 1


            return False

        return True

    def canDropItems(self, items, action, row, column, parent):
        node = self.getNode(parent)

        for item in items:
            o = item

            while o.parent is not None:
                o = o.parent

            if o is not self.root:
                return False

            if isinstance(item.value, SimpleTag) and isinstance(node.value, (SimpleTag, Tag)):
                continue

            if isinstance(item.value, Tag) and isinstance(node.value, Tags):
                continue

            return False

        return True

    def supportedDropActions(self):
        return Qt.MoveAction

class TagsNode(Node):
    def _wrapChildren(self, children):
        return TagsChildren.fromValues(children, self)

class TagsChildren(ChildNodes):
    @staticmethod
    def _wrap(value):
        return TagNode(value)

class TagNode(Node):
    def _wrapChildren(self, children):
        return TagChildren.fromValues(children, self)

    def _iterChildren(self):
        return self.value.simpletags

class TagChildren(ChildNodes):
    @staticmethod
    def _wrap(value):
        return SimpleTagNode(value)

    def _append(self, value):
        self.parent.value.simpletags.append(value)

    def _insert(self, index, value):
        self.parent.value.simpletags.insert(index, value)
    
    def _extend(self, values):
        self.parent.value.simpletags.extend(values)

    def _delitem(self, index):
        del self.parent.value.simpletags[index]

    def _setitem(self, index, value):
        self.parent.value.simpletags[index] = value

class SimpleTagNode(Node):
    def _wrapChildren(self, children):
        return SimpleTagChildren.fromValues(children, self)

    def _iterChildren(self):
        return self.value.subtags

class SimpleTagChildren(ChildNodes):
    @staticmethod
    def _wrap(value):
        return SimpleTagNode(value)

    def _append(self, value):
        self.parent.value.subtags.append(value)

    def _insert(self, index, value):
        self.parent.value.subtags.insert(index, value)
    
    def _extend(self, values):
        self.parent.value.subtags.extend(values)

    def _delitem(self, index):
        del self.parent.value.subtags[index]

    def _setitem(self, index, value):
        self.parent.value.subtags[index] = value

class TagItemCol(object):
    def __init__(self, editions, tracks, attachments,
                 targeteditions, targetchapters, targettracks, targetattachments):
        self.editions = editions
        self.tracks = tracks
        self.attachments = attachments

        self.targeteditions = targeteditions
        self.targetchapters = targetchapters
        self.targettracks = targettracks
        self.targetattachments = targetattachments

    def checkstate(self, index, obj):
        if isinstance(obj, EditionEntry):
            return 2 if obj.UID in self.targeteditions else 0

        elif isinstance(obj, ChapterAtom):
            return 2 if obj.UID in self.targetchapters else 0

        elif isinstance(obj, Track):
            return 2 if obj.trackUID in self.targettracks else 0

        elif isinstance(obj, AttachedFile):
            return 2 if obj.UID in self.targetattachments else 0

    def setcheckstate(self, index, obj, state):
        if state == 0:
            if isinstance(obj, EditionEntry):
                self.targeteditions.remove(obj.UID)

            elif isinstance(obj, ChapterAtom):
                self.targetchapters.remove(obj.UID)

            elif isinstance(obj, Track):
                self.targettracks.remove(obj.trackUID)

            elif isinstance(obj, AttachedFile):
                self.targetattachments.remove(obj.UID)

        elif state == 2:
            if isinstance(obj, EditionEntry):
                self.targeteditions.append(obj.UID)
                self.targeteditions.sort()

            elif isinstance(obj, ChapterAtom):
                self.targetchapters.append(obj.UID)
                self.targetchapters.sort()

            elif isinstance(obj, Track):
                self.targettracks.append(obj.trackUID)
                self.targettracks.sort()

            elif isinstance(obj, AttachedFile):
                self.targetattachments.append(obj.UID)
                self.targetattachments.sort()

    def display(self, index, obj):
        if isinstance(obj, Editions):
            return "Chapter Editions"

        elif isinstance(obj, TrackList):
            return "Tracks"

        if isinstance(obj, Attachments):
            return "Attachments"

        if isinstance(obj, EditionEntry):
            return f"Edition {obj.parent.chapters.index(obj)}"

        if isinstance(obj, Track):
            return f"{obj.track_index}: {obj.name}"

        if isinstance(obj, AttachedFile):
            return f"{obj.parent.attachments.index(obj)}: {obj.fileName}"

        if isinstance(obj, ChapterAtom):
            if len(obj.displays):
                return f"{obj.parent.index(obj) + 1}. {obj.displays[0].string}"

            return f"Chapter {obj.parent.index(obj) + 1}"

        return repr(obj)

    def flags(self, index, obj):
        if isinstance(obj, (EditionEntry, ChapterAtom, Track, AttachedFile)):
            return Qt.ItemIsUserCheckable | Qt.ItemIsEnabled

        return Qt.ItemIsEnabled

class OutputFileNode(Node):
    def _iterChildren(self):
        return (self.value.tracks, self.value.chapters, self.value.attachments)

TYPES = [
        ("COLLECTION", 70),
        ("EDITION", 60),
        ("ISSUE", 60),
        ("VOLUME", 60),
        ("OPUS", 60),
        ("SEASON", 60),
        ("SEQUEL", 60),
        ("VOLUME", 60),
        ("ALBUM", 50),
        ("OPERA", 50),
        ("CONCERT", 50),
        ("MOVIE", 50),
        ("EPISODE", 50),
        ("PART", 40),
        ("SESSION", 40),
        ("TRACK", 30),
        ("SONG", 30),
        ("CHAPTER", 30),
        ("SUBTRACK", 20),
        ("PART", 20),
        ("MOVEMENT", 20),
        ("SCENE", 20),
        ("SHOT", 10)
    ]

NESTING_NAMES = ["ORIGINAL", "SAMPLE", "COUNTRY"]
ORGANIZATION = ["TOTAL_PARTS", "PART_NUMBER", "PART_OFFSET"]
TITLES = ["TITLE", "SUBTITLE"]
NESTED_INFO = ["URL", "SORT_WITH", "INSTRUMENTS", "EMAIL",
               "ADDRESS", "FAX", "PHONE"]
ENTITIES = [
        "DIRECTOR", "ASSISTANT_DIRECTOR",
        "DIRECTOR_OF_PHOTOGRAPHY", "SOUND_ENGINEER",
        "ART_DIRECTOR", "PRODUCTION_DESIGNER", "CHOREGRAPHER",
        "COSTUME_DESIGNER", "ACTOR", "CHARACTER", "WRITTEN_BY",
        "SCREENPLAY_BY", "EDITED_BY", "PRODUCER", "COPRODUCER",
        "EXECUTIVE_PRODUCER", "DISTRIBUTED_BY", "MASTERED_BY",
        "ARTIST", "LEAD_PERFORMER", "ACCOMPANIEMENT",
        "COMPOSER", "ARRANGER", "LYRICS", "LYRICIST",
        "CONDUCTOR",
        "ENCODED_BY", "MIXED_BY", "REMIXED_BY",
        "PRODUCTION_STUDIO", "THANKS_TO", "PUBLISHER", "LABEL"
    ]

SEARCH_CLASS = [
        "GENRE",
        "MOOD",
        "ORIGINAL_MEDIA_TYPE",
        "CONTENT_TYPE",
        "SUBJECT",
        "DESCRIPTION",
        "KEYWORDS",
        "SUMMARY",
        "SYNOPSIS",
        "INITIAL_KEY",
        "PERIOD",
        "LAW_RATING",
    ]

TEMPORAL = [
        "DATE_RELEASED",
        "DATE_RECORDED",
        "DATE_ENCODED",
        "DATE_TAGGED",
        "DATE_DIGITIZED",
        "DATE_WRITTEN",
        "DATE_PURCHASED",
    ]

SPATIAL = [
        "RECORDING_LOCATION",
        "COMPOSITION_LOCATION",
        "COMPOSER_NATIONALITY",
    ]

PERSONAL = [
        "COMMENT",
        "PLAY_COUNTER",
        "RATING",
    ]

TECHNICAL = [
        "ENCODER",
        "ENCODER_SETTINGS",
        "BPS",
        "FPS",
        "BPM",
        "MEASURE",
        "TUNING",
        "REPLAYGAIN_GAIN",
        "REPLAYGAIN_PEAK",
    ]

IDENTIFIERS = [
        "ISRC",
        "MCDI",
        "ISBN",
        "BARCODE",
        "CATALOG_NUMBER",
        "LABEL_CODE",
        "LCCN",
        "IMDB",
        "TMDB",
        "TVDB",
    ]

COMMERCIAL = [
        "PURCHASE_ITEM",
        "PURCHASE_INFO",
        "PURCHASE_OWNER",
        "PURCHASE_PRICE",
        "PURCHASE_CURRENCY",
    ]

LEGAL = [
        "COPYRIGHT",
        "PRODUCTION_COPYRIGHT",
        "LICENSE",
        "TERMS_OF_USE",
    ]

SECTIONS = [
        ("Titles", TITLES),
        ("Temporal", TEMPORAL),
        ("Organization", ORGANIZATION),
        ("Entities", ENTITIES),
        ("Nesting", NESTING_NAMES),
        ("Search/Classification", SEARCH_CLASS),
        ("Spatial", SPATIAL),
        ("Personal", PERSONAL),
        ("Technical", TECHNICAL),
        ("Identifiers", IDENTIFIERS),
        ("Commercial", COMMERCIAL),
        ("Legal", LEGAL)
        ]

BINARY = {"ICRA", "REPLAYGAIN_GAIN", "REPLAYGAIN_PEAK",
          "MCDI"}

AUTOSELECT = {
        ("COLLECTION", 70): {"TITLE", "TOTAL_PARTS"},
        ("EDITION", 60): {"TITLE"},
        #("ISSUE", 60),
        #("VOLUME", 60),
        #("OPUS", 60),
        ("SEASON", 60): {"TOTAL_PARTS", "PART_NUMBER", "DATE_RELEASED"},
        #("SEQUEL", 60),
        #("VOLUME", 60),
        #("ALBUM", 50),
        #("OPERA", 50),
        #("CONCERT", 50),
        ("MOVIE", 50): {
            "TITLE", "DIRECTOR", "ASSISTANT_DIRECTOR",
            "DIRECTOR_OF_PHOTOGRAPHY", "SOUND_ENGINEER",
            "ART_DIRECTOR", "PRODUCTION_DESIGNER", "CHOREGRAPHER",
            "COSTUME_DESIGNER", "ACTOR", "CHARACTER", "WRITTEN_BY",
            "SCREENPLAY_BY", "EDITED_BY", "PRODUCER", "COPRODUCER",
            "EXECUTIVE_PRODUCER", "DISTRIBUTED_BY", "PRODUCTION_STUDIO",
            "DATE_RELEASED"
            },
        ("EPISODE", 50): {
            "TITLE", "PART_NUMBER", "DIRECTOR", "ACTOR",
            "WRITTEN_BY", "PRODUCER", "COPRODUCER"
            "EXECUTIVE_PRODUCER", "SCREENPLAY_BY", "DATE_RELEASED"},
        #("PART", 40),
        #("SESSION", 40),
        #("TRACK", 30),
        #("SONG", 30),
        #("CHAPTER", 30),
        #("SUBTRACK", 20),
        #("PART", 20),
        #("MOVEMENT", 20),
        #("SCENE", 20),
        #("SHOT", 10)
    }

SUBTAGS = {
    "ACTOR": ["CHARACTER"]
    }

class NewSimpleTags(QWidget):
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        self.setLayout(layout)
        self._tags = []

        for k, (section, items) in enumerate(SECTIONS):
            if k > 0:
                frame = QFrame(self)
                frame.setFrameStyle(QFrame.HLine)
                layout.addWidget(frame)

            hlayout = QHBoxLayout()
            label = QLabel(section, self)
            f = self.font()
            f.setPointSize(14)
            f.setItalic(True)
            f.setBold(QFont.Bold)
            label.setFont(f)
            hlayout.addWidget(label)
            hlayout.addStretch()

            layout.addLayout(hlayout)

            for item in items:
                hlayout = QHBoxLayout()
                checkBox = QCheckBox(titlecase(item.replace("_", " ")), self)

                spinBox = QSpinBox(self)
                spinBox.setMinimum(1)
                spinBox.setMaximum(512)
                spinBox.valueChanged.connect(self.contentsModified)
                spinBox.setPrefix("×")
                spinBox.setEnabled(False)

                checkBox.stateChanged.connect(partial(self.checkChanged, spinBox))

                hlayout.addWidget(checkBox)
                hlayout.addStretch()
                hlayout.addWidget(spinBox)
                layout.addLayout(hlayout)
                self._tags.append((item, checkBox, spinBox))

    def checkChanged(self, spinBox, state):
        spinBox.setEnabled(state == 2)
        self.contentsModified.emit()

    def tags(self):
        return [(item, checkBox.checkState(), spinBox.value()) for (item, checkBox, spinBox) in self]

    def __iter__(self):
        return iter(self._tags)

class NewTagDlg(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.typeLabel = QLabel("Tag Type:", self)
        self.typeComboBox = QComboBox(self)

        for (t, tValue) in TYPES:
            self.typeComboBox.addItem(f"{titlecase(t)} ({tValue})", [t, tValue])

        sublayout = QHBoxLayout()
        sublayout.addWidget(self.typeLabel)
        sublayout.addWidget(self.typeComboBox)
        sublayout.addStretch()
        layout.addLayout(sublayout)

        scrollArea = QScrollArea(self)
        scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.newTags = NewSimpleTags(scrollArea)
        scrollArea.setWidget(self.newTags)
        layout.addWidget(scrollArea)

        sublayout = QHBoxLayout()
        self.okayBtn = QPushButton("&OK", self)
        self.okayBtn.clicked.connect(self.applyAndClose)
        self.cancelBtn = QPushButton("&Cancel", self)
        self.cancelBtn.clicked.connect(self.close)
        sublayout.addStretch()

        sublayout.addWidget(self.okayBtn)
        sublayout.addWidget(self.cancelBtn)
        layout.addLayout(sublayout)

        self.typeComboBox.currentIndexChanged.connect(self.autoSelectSubtags)

    def applyAndClose(self):
        self.done(1)
        self.close()

    def autoSelectSubtags(self):
        data = self.typeComboBox.currentData()
        autoselect = AUTOSELECT.get(tuple(data), {})

        for tag, checkBox, spinBox in self.newTags:
            if tag in autoselect:
                checkBox.setCheckState(2)

            else:
                checkBox.setCheckState(0)

    def selectedTags(self):
        return [(tag, count) for (tag, checkstate, count) in self.newTags.tags() if checkstate]

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

    def __init__(self, tags, tracks, editions, attachments):
        self.tags = tags
        self.tracks = tracks
        self.editions = editions
        self.attachments = attachments

    def font(self, index, obj):
        return self.fontmain

    def bgdata(self, index, obj):
        return self.bgcolor

    def fgdata(self, index, obj):
        return self.fgcolor

    def contextmenu(self, index, obj):
        return partial(self.createContextMenu, obj=obj, index=index)

    def createContextMenu(self, table, index, obj):
        menu = QMenu(table)

        if isinstance(obj, Tags):
            newAtBottom = QAction("&New Tag...", table,
                                  triggered=partial(self.newTag, table=table, model=index.model()))
            menu.addAction(newAtBottom)

        if isinstance(obj, Tag):
            newAtBottom = QAction("&New Tag...", table,
                                  triggered=partial(self.newTag, table=table, model=index.model()))

            insertAbove = QAction("&Insert Tag Before...", table,
                                  triggered=partial(self.newTag, table=table, row_id=index.row(), model=index.model()))


            newSimpleTag = QAction("&New SimpleTag", table,
                                    triggered=partial(self.newSimpleTag, table=table, parent=index, model=index.model()))

            menu.addAction(newAtBottom)
            menu.addAction(insertAbove)
            menu.addAction(newSimpleTag)


        if isinstance(obj, SimpleTag):
            if isinstance(obj.parent, Tag):
                row_id = obj.parent.simpletags.index(obj)

            elif isinstance(obj.parent, SimpleTag):
                row_id = obj.parent.subtags.index(obj)

            insertSimpleTag = QAction("&Insert SimpleTag Before", table,
                        triggered=partial(self.newSimpleTag, table=table, parent=index.parent(), model=index.model(), row_id=row_id))

            insertAfterTag = QAction(f"&Insert '{titlecase(obj.name.replace('_', ' '))}' After", table,
                        triggered=partial(self.newSimpleTag, table=table, parent=index.parent(), model=index.model(), row_id=row_id+1, tagname=obj.name))

            appendSimpleTag = QAction("&Add SimpleTag at end", table,
                        triggered=partial(self.newSimpleTag, table=table, parent=index.parent(), model=index.model()))

            insertChildSimpleTag = QAction("&Add child SimpleTag", table,
                        triggered=partial(self.newSimpleTag, table=table, parent=index, model=index.model()))

            menu.addAction(insertSimpleTag)
            menu.addAction(insertAfterTag)

            menu.addAction(appendSimpleTag)
            menu.addAction(insertChildSimpleTag)

            for childtag in SUBTAGS.get(obj.name, set()):
                addChildSimpleTag = QAction(f"&Add child '{titlecase(childtag.replace('_', ' '))}' SimpleTag", table,
                        triggered=partial(self.newSimpleTag, table=table, parent=index, model=index.model(), tagname=childtag))
                menu.addAction(addChildSimpleTag)



        delete = QAction("&Delete Selected...", table,
                                triggered=table.askDeleteSelected)
        menu.addAction(delete)

        if len(table.selectedIndexes()):
            delete.setEnabled(len(table.selectedIndexes()) > 0)

        return menu

    def newTag(self, table, model, row_id=-1):
        if model is None:
            model = table.model()

        existing = [(tag.type, tag.typeValue) for tag in self.tags]
        dlg = NewTagDlg(table)

        for (type, typeValue) in TYPES:
            if (type, typeValue) not in existing:
                cbindex = dlg.typeComboBox.findData([type, typeValue])

                if cbindex >= 0:
                    dlg.typeComboBox.setCurrentIndex(cbindex)
                    break

        else:
            dlg.typeComboBox.setCurrentIndex(0)

        if dlg.exec_():
            type, typeValue = dlg.typeComboBox.currentData()
            tag = Tag(typeValue, type)

            for simpleTag, N in dlg.selectedTags():
                for k in range(N):
                    tag.simpletags.append(SimpleTag(simpleTag))

            if row_id == -1:
                row_id = model.rowCount(QModelIndex())

            model.insertRow(row_id, tag)

    def newSimpleTag(self, table, model, parent, row_id=-1, tagname=""):
        if model is None:
            model = table.model()

        for col_id, col in enumerate(model.columns):
            if isinstance(col, ValueCol):
                break

        else:
            col_id = 0

        if row_id == -1:
            row_id = model.rowCount(parent)

        tag = SimpleTag(tagname)
        model.insertRow(row_id, tag, parent)

        idx = model.index(row_id, col_id, parent)
        table.setCurrentIndex(idx)
        table.edit(idx)

    def flags(self, index, obj):
        if isinstance(obj, SimpleTag):
            return Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled

        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled

class TagNameDelegate(QItemDelegate):
    def createEditor(self, parent, option, index):
        obj = index.data(Qt.UserRole)

        if isinstance(obj, SimpleTag):
            widget = QComboBox(parent)
            widget.setEditable(True)

            for k, (section, items) in enumerate(SECTIONS):
                if k > 0:
                    widget.insertSeparator(len(widget))

                for item in items:
                    widget.addItem(titlecase(item.replace("_", " ")), item)

        elif isinstance(obj, Tag):
            widget = QComboBox(parent)

            for (type, typeValue) in TYPES:
                widget.addItem(f"{titlecase(type)} ({typeValue})", [type, typeValue])

        return widget

    def setEditorData(self, editor, index):
        obj = index.data(Qt.UserRole)
        data = index.data(Qt.EditRole)

        if isinstance(obj, Tag):
            cbindex = editor.findData(list(data))
            editor.setCurrentIndex(cbindex)

        elif isinstance(obj, SimpleTag):
            cbindex = editor.findData(data)

            if cbindex >= 0:
                editor.setCurrentIndex(cbindex)

            else:
                editor.setCurrentText(titlecase(data.replace("_", " ")))

    def setModelData(self, editor, model, index):
        obj = index.data(Qt.UserRole)
        data = editor.currentData()

        if isinstance(obj, Tag) and data:
            model.setData(index, editor.currentData(), Qt.EditRole)

        elif isinstance(obj, SimpleTag):
            model.setData(index, editor.currentText().upper().replace(" ", "_"))

class NameCol(BaseColumn):
    width = 256
    headerdisplay = "Tag"
    flags = Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled

    def editdata(self, index, obj):
        if isinstance(obj, Tag):
            return (obj.type, obj.typeValue)

        elif isinstance(obj, SimpleTag):
            return obj.name

    def seteditdata(self, index, obj, data):
        if isinstance(obj, Tag):
            (obj.type, obj.typeValue) = data

        elif isinstance(obj, SimpleTag):
            obj.name = data

    def display(self, index, obj):
        if isinstance(obj, Tag):
            return f"{titlecase(obj.type)} ({obj.typeValue})"

        elif isinstance(obj, SimpleTag):
            return f"{titlecase(obj.name.replace('_', ' '))}"

    def itemDelegate(self, parent):
        return TagNameDelegate(parent)

class TagLanguageDelegate(LanguageDelegate):
    def createEditor(self, parent, option, index):
        if isinstance(index.data(Qt.UserRole), SimpleTag):
            return super().createEditor(parent, option, index)

class LangCol(BaseColumn):
    width = 120
    headerdisplay = "Language"

    def editdata(self, index, obj):
        if isinstance(obj, SimpleTag):
            return obj.language

        return ""

    def seteditdata(self, index, obj, value):
        if isinstance(obj, SimpleTag):
            obj.language = value

    def display(self, index, obj):
        if isinstance(obj, SimpleTag):
            lang = self.editdata(index, obj)

            if lang is None:
                return "Unknown (und)"

            return f"{LANGUAGES.get(lang, 'Unknown')} ({lang})"

        return ""

    tooltip = display

    def itemDelegate(self, parent):
        return LanguageDelegate(parent)

class ValueCol(BaseColumn):
    headerdisplay = "Value"

    def __init__(self, tags, tracks, editions, attachments):
        self.tags = tags
        self.tracks = tracks
        self.editions = editions
        self.attachments = attachments

    def editdata(self, index, obj):
        if isinstance(obj, Tag):
            return None

        elif isinstance(obj, SimpleTag):
            return obj.string

    def seteditdata(self, index, obj, value):
        if isinstance(obj, Tag):
            return None

        elif isinstance(obj, SimpleTag):
            if isinstance(value, str):
                obj.string = value

            elif isinstance(value, bytes):
                obj.data -= value

    def display(self, index, obj):
        return self.editdata(index, obj) or ""

    def flags(self, index, obj):
        if isinstance(obj, SimpleTag):
            return Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled

        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled

class QTagTree(QTreeView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMinimumWidth(540)
        self.setDragDropMode(QTreeView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QTreeView.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setData(None, None, None, None)

        self.setSelectionBehavior(QAbstractItemView.SelectRows)

    def contextMenuEvent(self, event):
        selected = self.currentIndex()
        menu = self.model().data(selected, role=Qt.UserRole + 1)

        if callable(menu):
            menu = menu(self)

        if isinstance(menu, QMenu):
            menu.exec_(self.mapToGlobal(event.pos()))

    def setData(self, tags, tracks, editions, attachments):
        self.tags = tags
        self.tracks = tracks
        self.editions = editions
        self.attachments = attachments

        if self.tags is not None:
            cols = [
                    NameCol(tags, tracks, editions, attachments),
                    LangCol(tags, tracks, editions, attachments),
                    ValueCol(tags, tracks, editions, attachments),
                ]

            root = TagsNode(tags)
            model = TagItemModel(root, cols)
            self.setModel(model)

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

        selected = sorted(idx.row() for idx in self.selectionModel().selectedRows())

        if key == Qt.Key_Delete and modifiers == Qt.NoModifier and len(self.selectionModel().selectedRows()):
            self.askDeleteSelected()

        super().keyPressEvent(event)

    def askDeleteSelected(self):
        answer = QMessageBox.question(self, "Delete tags", "Do you wish to delete the selected tags? Any child tags will also be lost!", QMessageBox.Yes | QMessageBox.No)

        if answer == QMessageBox.Yes:
            self.deleteSelected()

    def deleteSelected(self):
        model = self.model()
        sm = self.selectionModel()
        selected = {model.getNode(index) for index in sm.selectedRows()}
        removed = set()

        for node in selected:
            parent = node.parent

            if node not in removed:
                model.removeRow(parent.index(node), model.findIndex(parent))
                removed.add(node)

                if node.descendants is not None:
                    removed.update(node.descendants)

class QTagsWidget(QWidget):
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.tagTree = QTagTree(self)
        layout.addWidget(self.tagTree)

        btnlayout = QHBoxLayout()
        layout.addLayout(btnlayout)

        self.addTagBtn = QPushButton("&Add top-level tag", self)
        self.addSubTagBtn = QPushButton("&Add simple tag", self)
        self.removeTagBtn = QPushButton("&Delete selected", self)
        self.removeTagBtn.clicked.connect(self.tagTree.askDeleteSelected)

        btnlayout.addWidget(self.addTagBtn)
        btnlayout.addWidget(self.addSubTagBtn)
        btnlayout.addWidget(self.removeTagBtn)
        btnlayout.addStretch()

    def setData(self, tags, tracks, editions, attachments):
        self.tagTree.setData(tags, tracks, editions, attachments)

        if tags is not None:
            self.tagTree.model().dataChanged.connect(self.contentsModified)
            self.tagTree.model().rowsInserted.connect(self.contentsModified)
            self.tagTree.model().rowsRemoved.connect(self.contentsModified)
            self.tagTree.model().rowsMoved.connect(self.contentsModified)

