from PyQt5.QtWidgets import QApplication, QWidget
import sys
from PyQt5.QtCore import (Qt, QAbstractListModel, QAbstractItemModel, QAbstractTableModel, QModelIndex,
                          QVariant, QItemSelectionModel, QItemSelection, pyqtSignal, pyqtSlot, QMimeData, QByteArray, QDataStream, QIODevice)
from PyQt5 import QtCore
from PyQt5.QtWidgets import (QDialog, QLabel, QListWidgetItem, QListView, QVBoxLayout, QHBoxLayout,
                             QAbstractItemView, QMessageBox, QPushButton, QTreeView, QTableView, QHeaderView,
                             QLineEdit, QComboBox, QFileDialog, QCheckBox, QDoubleSpinBox, QItemDelegate, QComboBox)
from PyQt5.QtGui import QFont, QIcon, QDrag, QBrush

import traceback
import threading
_cookies = {}
_cookie_lock = threading.Lock()

class QObjectItemModel(QAbstractItemModel):
    ROLEMAPPING = {
            Qt.DisplayRole: "display",
            Qt.ToolTipRole: "tooltip",
            Qt.DecorationRole: "icon",
            Qt.SizeHintRole: "sizehint",
            Qt.EditRole: "editdata",
            Qt.BackgroundColorRole: "bgcolor",
            Qt.BackgroundRole: "bgdata",
            Qt.ForegroundRole: "fgdata",
            Qt.CheckStateRole: "checkstate",
            Qt.ItemDataRole: "itemdata",
            Qt.TextAlignmentRole: "textalign",
            Qt.FontRole: "font",
            Qt.UserRole + 1: "contextmenu",
            Qt.UserRole + 2: "keypress",
        }

    def __init__(self, items, columns, vheader=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.items = items
        self.columns = columns
        self.vheader = vheader
        self._parents = {}

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            ptr = parent.internalPointer()

            try:
                return len(ptr)

            except:
                return 0

        return len(self.items)

    def columnCount(self, parent=QModelIndex()):
        return len(self.columns)

    def index(self, row, column, parent=None):
        if parent and parent.isValid():
            parent_obj = parent.internalPointer()

        else:
            parent_obj = self.items

        items = parent_obj

        try:
            item = items[row]

        except:
            return QModelIndex()

        if id(item) in self._parents and self._parents[id(item)] is not parent_obj:
            raise ValueError()

        self._parents[id(item)] = parent_obj

        if isinstance(item, (int, str, float, complex)):
            return QAbstractItemModel.createIndex(self, row, column)

        return QAbstractItemModel.createIndex(self, row, column, item)

    def parent(self, in_index):
        if in_index.isValid():  
            item = in_index.internalPointer()

            if item is None:
                return QModelIndex()

            parent = self._parents[id(item)]

            if parent is self.items:
                return QModelIndex()

            grandparent = self._parents[id(parent)]

            return QAbstractItemModel.createIndex(self, grandparent.index(parent), 0, parent)

        return QModelIndex()

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            row_index = index.row()

            if role == Qt.UserRole:
                obj = index.internalPointer()

                if obj is None:
                    return self.items[index.row()]

                return obj

            obj = self.data(index, Qt.UserRole)
            col_index = index.column()
            col_obj = self.columns[col_index]

            if role in self.ROLEMAPPING.keys() and hasattr(col_obj, self.ROLEMAPPING[role]):
                role_obj = getattr(col_obj, self.ROLEMAPPING[role])

                if callable(role_obj):
                    try:
                        value = role_obj(index, obj)
                        return value

                    except:
                        print(traceback.format_exc(), file=sys.stderr)
                        return "ERR"

                else:
                    return role_obj

        return QVariant()

    def setData(self, index, data, role=Qt.EditRole):
        if index.isValid():
            row_index = index.row()
            obj = index.data(role=Qt.UserRole)
            col_index = index.column()
            col_obj = self.columns[col_index]

            if role in self.ROLEMAPPING.keys() and hasattr(col_obj, "set"+self.ROLEMAPPING[role]):
                role_obj = getattr(col_obj, "set"+self.ROLEMAPPING[role])

                if callable(role_obj):
                    role_obj(index, obj, data)
                    idx1 = self.createIndex(0, 0)
                    idx2 = self.createIndex(self.rowCount()-1, self.columnCount()-1)
                    self.dataChanged.emit(idx1, idx2)
                    return True

                else:
                    return False

            return False
        return False

    def headerData(self, index, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            col_obj = self.columns[index]

            if role in self.ROLEMAPPING.keys() and hasattr(col_obj, "header"+self.ROLEMAPPING[role]):
                role_obj = getattr(col_obj, "header" + self.ROLEMAPPING[role])

                if callable(role_obj):
                    return role_obj(index)

                else:
                    return role_obj

            elif role == Qt.DisplayRole:
                return index + 1

        elif orientation == Qt.Vertical:
            return index + 1

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

            if srcparent is destparent and newposition > position:
                newposition -= 1

            item = items1.pop(position)
            items2.insert(newposition, item)
            self.endMoveRows()

        return True

    def insertRow(self, row_id, row, parent=QModelIndex()):
        if parent.isValid():
            items = parent.internalPointer()

        else:
            items = self.items

        self.beginInsertRows(parent, row_id, row_id)

        items.insert(row_id, row)

        self._parents[id(row)] = items
        self.endInsertRows()
        return True

    def insertColumn(self, col_id, col, parent=QModelIndex()):
        self.beginInsertColumns(parent, col_id, col_id)
        self.columns.insert(col_id, col)
        self.endInsertColumns()
        return True

    def removeRow(self, row_id, parent=QModelIndex()):
        if parent.isValid():
            items = parent.internalPointer()

        else:
            items = self.items

        self.beginRemoveRows(parent, row_id, row_id)

        del items[row_id]

        self.endRemoveRows()
        return True

    def removeColumn(self, col_id, parent=QModelIndex()):
        self.beginRemoveColumns(parent, col_id, col_id)
        del self.columns[col_id]
        self.endRemoveRows()
        return True

    def flags(self, index):
        if index.isValid():
            row_index = index.row()
            obj = index.data(role=Qt.UserRole)
            col_index = index.column()
            col_obj = self.columns[col_index]

            if hasattr(col_obj, "flags"):
                if callable(col_obj.flags):
                    flags = col_obj.flags(index, obj)
                    return flags

                return col_obj.flags

        return Qt.ItemFlags(0)

    def hasChildren(self, index):
        if index.isValid():
            ptr = index.internalPointer()

            try:
                return hasattr(ptr, "__iter__")

            except:
                return False

        return True

    def getCookie(self, index):
        item = index.data(Qt.UserRole)
        cookie = f"0x{id(self):012x},0x{id(item):012x}"

        with _cookie_lock:
            _cookies[cookie] = item

        return cookie

    def mimeData(self, indexes):
        data = QMimeData()

        try:
            data.setData("application/x-qabstractitemmodeldatalist",
                     b";".join(self.getCookie(index).encode("utf8") for index in indexes))

        except:
            pass

        return data

    def dropMimeData(self, data, action, row, column, parent):
        cookies = data.data("application/x-qabstractitemmodeldatalist")
        items = []

        with _cookie_lock:
            for cookie in bytes(cookies).decode("utf8").split(";"):
                if cookie in _cookies.keys():
                    items.append(_cookies[cookie])

        return self.dropItems(items, action, row, column, parent)

    def findIndex(self, item):
        return QModelIndex()

    def dropItems(self, items, action, row, column, parent):
        return False

    def canDropMimeData(self, data, action, row, column, parent):
        cookies = data.data("application/x-qabstractitemmodeldatalist")
        items = []

        with _cookie_lock:
            for cookie in bytes(cookies).decode("utf8").split(";"):
                if cookie in _cookies.keys():
                    items.append(_cookies[cookie])

        ret = self.canDropItems(items, action, row, column, parent)
        print(items, parent.internalPointer(), ret)
        return ret

    def canDropItems(self, items, action, row, column, parent):
        return False

