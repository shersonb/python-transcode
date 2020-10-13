from PyQt5.QtWidgets import QApplication, QWidget
import sys
from PyQt5.QtCore import (Qt, QAbstractListModel, QAbstractItemModel, QAbstractTableModel, QModelIndex,
                          QVariant, QItemSelectionModel, QItemSelection, pyqtSignal, pyqtSlot, QMimeData,
                          QByteArray, QDataStream, QIODevice, QRegExp)
from PyQt5 import QtCore
from PyQt5.QtWidgets import (QDialog, QLabel, QListWidgetItem, QListView, QVBoxLayout, QHBoxLayout,
                             QAbstractItemView, QMessageBox, QPushButton, QTreeView, QTableView, QHeaderView, QSpinBox,
                             QLineEdit, QComboBox, QFileDialog, QCheckBox, QDoubleSpinBox, QItemDelegate,
                             QMenu, QAction)
from PyQt5.QtGui import QFont, QIcon, QDrag, QBrush, QPainter, QRegExpValidator

from transcode.pyqtgui.qobjectitemmodel import QObjectItemModel, _cookie_lock, _cookies
from ..tags import Tag, Tags, SimpleTag
from transcode.pyqtgui.qlangselect import LanguageDelegate, LANGUAGES
from titlecase import titlecase
from functools import partial

class TagItemModel(QObjectItemModel):
    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            ptr = parent.internalPointer()

            try:
                if isinstance(ptr, Tags):
                    return len(ptr)

                elif isinstance(ptr, Tag):
                    return len(ptr.simpletags)

                elif isinstance(ptr, SimpleTag):
                    return len(ptr.subtags)

            except:
                return 0

        return len(self.items)

    def index(self, row, column, parent=QModelIndex()):
        if parent and parent.isValid():
            parent_obj = parent.internalPointer()

        else:
            parent_obj = self.items

        try:
            if isinstance(parent_obj, SimpleTag):
                item = parent_obj.subtags[row]

            elif isinstance(parent_obj, Tag):
                item = parent_obj.simpletags[row]

            elif isinstance(parent_obj, Tags):
                item = parent_obj[row]

            else:
                return QModelIndex()

        except:
            return QModelIndex()

        if isinstance(item, (int, str, float, complex)):
            return QAbstractItemModel.createIndex(self, row, column)

        return QAbstractItemModel.createIndex(self, row, column, item)

    #def removeRow() TODO

    def moveRow(self, position, newposition, srcparent=QModelIndex(), destparent=QModelIndex()):
        if self.beginMoveRows(srcparent, position, position, destparent, newposition):
            if srcparent.isValid():
                items1 = srcparent.internalPointer()

            else:
                items1 = self.items

            if destparent.isValid():
                items2 = destparent.internalPointer()

            else:
                items2 = self.items

            if isinstance(items1, Tags):
                item = items1.pop(position)

            elif isinstance(items1, Tag):
                item = items1.simpletags.pop(position)

            elif isinstance(items1, SimpleTag):
                item = items1.subtags.pop(position)

            if items1 is items2 and newposition > position:
                newposition -= 1

            if isinstance(items2, Tags):
                items2.insert(newposition, item)

            elif isinstance(items2, Tag):
                items2.simpletags.insert(newposition, item)

            elif isinstance(items2, SimpleTag):
                items2.subtags.insert(newposition, item)

            self.endMoveRows()

        return True

    def parent(self, in_index):
        if in_index.isValid():  
            item = in_index.internalPointer()

            if item is None:
                return QModelIndex()

            elif isinstance(item, SimpleTag):
                parent = item.parent

            else:
                parent = None

            if isinstance(parent, Tag):
                return QAbstractItemModel.createIndex(self, self.items.index(parent), 0, parent)

            elif isinstance(parent, SimpleTag):
                if isinstance(parent.parent, SimpleTag):
                    return QAbstractItemModel.createIndex(self, parent.parent.subtags.index(parent), 0, parent)

                return QAbstractItemModel.createIndex(self, parent.parent.simpletags.index(parent), 0, parent)

        return QModelIndex()

    def insertRow(self, row_id, item, parent=QModelIndex()):
        if parent.isValid():
            items = parent.internalPointer()

        else:
            items = self.items

        self.beginInsertRows(parent, row_id, row_id)

        if isinstance(items, Tags):
            items.insert(row_id, item)

        elif isinstance(items, Tag):
            items.simpletags.insert(row_id, item)

        elif isinstance(items, SimpleTag):
            items.subtags.insert(row_id, item)

        self.endInsertRows()
        return True

    def removeRow(self, row_id, parent=QModelIndex()):
        if parent.isValid():
            items = parent.internalPointer()

        else:
            items = self.items

        self.beginRemoveRows(parent, row_id, row_id)

        if isinstance(items, Tags):
            del items[row_id]

        elif isinstance(items, Tag):
            del items.simpletags[row_id]

        elif isinstance(items1, SimpleTag):
            del items.subtags[row_id]

        self.endRemoveRows()
        return True

    def hasChildren(self, index):
        if index.isValid():
            ptr = index.internalPointer()

            try:
                if isinstance(ptr, Tags):
                    return len(ptr) > 0

                elif isinstance(ptr, Tag):
                    return len(ptr.simpletags) > 0

                elif isinstance(ptr, SimpleTag):
                    return len(ptr.subtags) > 0

            except:
                return False

        return True

    def findIndex(self, item):
        if isinstance(item, Tags):
            return QModelIndex()

        elif isinstance(item, Tag):
            if item in self.items:
                return self.index(self.items.index(item), 0)

        elif isinstance(item, SimpleTag):
            if isinstance(item.parent, Tag):
                return self.findIndex(item.parent).child(item.parent.simpletags.index(item), 0)

            elif isinstance(item.parent, SimpleTag):
                return self.findIndex(item.parent).child(item.parent.subtags.index(item), 0)

        return QModelIndex()

    def dropItems(self, items, action, row, column, parent):
        if row == -1:
            row = self.rowCount(parent)

        parent_obj = parent.data(Qt.UserRole)

        j = 0

        for k, item in enumerate(items):
            if isinstance(item, SimpleTag):
                old_parent = self.findIndex(item.parent)

                if isinstance(item.parent, SimpleTag):
                    old_row = item.parent.subtags.index(item)

                elif isinstance(item.parent, Tag):
                    old_row = item.parent.simpletags.index(item)

                self.moveRow(old_row, row + k - j, old_parent, parent)

                if old_parent.data(Qt.UserRole) is parent.data(Qt.UserRole) and old_row < row:
                    j += 1

            if isinstance(item, Tag):
                old_row = self.items.index(item)
                self.moveRow(old_row, row + k - j)

                if old_row < row:
                    j += 1


            return False

        return True


    def canDropItems(self, items, action, row, column, parent):
        parent_obj = parent.data(Qt.UserRole)

        for item in items:
            if isinstance(item, SimpleTag) and isinstance(parent_obj, (SimpleTag, Tag)):
                continue

            if isinstance(item, Tag) and not parent.isValid():
                continue

            return False

        return True

    def supportedDropActions(self):
        return Qt.MoveAction

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

class NewTagDlg(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.typeLabel = QLabel("Tag Type:", self)
        self.typeComboBox = QComboBox(self)

        for (t, tValue) in TYPES:
            self.typeComboBox.addItem(f"{titlecase(t)} ({tValue})", (t, tValue))

        sublayout = QHBoxLayout()
        sublayout.addWidget(self.typeLabel)
        sublayout.addWidget(self.typeComboBox)
        sublayout.addStretch()
        layout.addLayout(sublayout)

        sublayout = QHBoxLayout()
        self.okayBtn = QPushButton("&OK", self)
        self.okayBtn.clicked.connect(self.applyAndClose)
        self.cancelBtn = QPushButton("&Cancel", self)
        self.cancelBtn.clicked.connect(self.close)
        sublayout.addStretch()

        sublayout.addWidget(self.okayBtn)
        sublayout.addWidget(self.cancelBtn)
        layout.addLayout(sublayout)

    def applyAndClose(self):
        self.done(1)
        self.close()

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

            appendSimpleTag = QAction("&Add SimpleTag at end", table,
                        triggered=partial(self.newSimpleTag, table=table, parent=index.parent(), model=index.model()))

            insertChildSimpleTag = QAction("&Add child SimpleTag", table,
                        triggered=partial(self.newSimpleTag, table=table, parent=index, model=index.model()))

            menu.addAction(insertSimpleTag)
            menu.addAction(appendSimpleTag)
            menu.addAction(insertChildSimpleTag)


        delete = QAction("&Delete Selected...", table,
                                triggered=partial(self.deleteTag, table=table, model=index.model()))
        menu.addAction(delete)

        if len(table.selectedIndexes()):
            delete.setEnabled(len(table.selectedIndexes()) > 0)

        return menu

    def newTag(self, table, model, row_id=-1):
        dlg = NewTagDlg(table)

        if dlg.exec_():
            type, typeValue = dlg.typeComboBox.currentData()
            tag = Tag(typeValue, type)

            if row_id == -1:
                row_id = model.rowCount(QModelIndex())

            model.insertRow(row_id, tag)

    def newSimpleTag(self, table, model, parent, row_id=-1):
        if row_id == -1:
            row_id = model.rowCount(parent)

        tag = SimpleTag("")
        model.insertRow(row_id, tag, parent)

    def deleteTag(self, table, model):
        answer = QMessageBox.question(table, "Delete tags", "Do you wish to delete the selected tags? Any child tags will also be lost!", QMessageBox.Yes | QMessageBox.No)

        if answer == QMessageBox.Yes:
            selected = {index.data(Qt.UserRole) for index in table.selectedIndexes()}

            for tag in selected.copy():
                index = model.findIndex(tag)

                if index.isValid():
                    model.removeRow(index.row(), index.parent())

    def flags(self, index, obj):
        if isinstance(obj, SimpleTag):
            return Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled

        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled

class NameCol(BaseColumn):
    width = 256
    headerdisplay = "Tag"

    def editdata(self, index, obj):
        if isinstance(obj, Tag):
            return (obj.typeValue, obj.type)

        elif isinstance(obj, SimpleTag):
            return obj.name

    def display(self, index, obj):
        if isinstance(obj, Tag):
            return f"{obj.type} ({obj.typeValue})"

        elif isinstance(obj, SimpleTag):
            return f"{obj.name}"

class TagLanguageDelegate(LanguageDelegate):
    def createEditor(self, parent, option, index):
        if isinstance(index.data(Qt.UserData), SimpleTag):
            return super().createEditor(parent, option, index)

class LangCol(BaseColumn):
    width = 120
    headerdisplay = "Language"

    def editdata(self, index, obj):
        if isinstance(obj, SimpleTag):
            return obj.language

        return ""

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

class TagTree(QTreeView):
    def __init__(self, tags, tracks, editions, attachments, *args, **kwargs):
        super(TagTree, self).__init__(*args, **kwargs)
        self.tags = tags
        self.tracks = tracks
        self.editions = editions
        self.attachments = attachments

        self.setDragDropMode(QTreeView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

        self.setSelectionBehavior(QAbstractItemView.SelectRows)

        cols = [
                NameCol(tags, tracks, editions, attachments),
                LangCol(tags, tracks, editions, attachments),
                ValueCol(tags, tracks, editions, attachments),
            ]

        self.setModel(TagItemModel(tags, cols))

        for k, col in enumerate(cols):
            if hasattr(col, "width") and isinstance(col.width, int):
                self.setColumnWidth(k, col.width)

            if hasattr(col, "itemDelegate") and callable(col.itemDelegate):
                self.setItemDelegateForColumn(k, col.itemDelegate(self))

    def contextMenuEvent(self, event):
        selected = self.currentIndex()
        menu = self.model().data(selected, role=Qt.UserRole + 1)

        if callable(menu):
            menu = menu(self)

        if isinstance(menu, QMenu):
            menu.exec_(self.mapToGlobal(event.pos()))

