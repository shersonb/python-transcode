import sys
from PyQt5.QtCore import (Qt, QAbstractItemModel,
                          QModelIndex, QVariant, QMimeData)
from transcode.util import cached, ChildList, WeakRefProperty

import traceback
import threading

_cookies = {}
_cookie_lock = threading.Lock()


class ChildNodes(ChildList):
    @staticmethod
    def _wrap(value):
        return Node(value)

    @classmethod
    def fromValues(cls, values, parent=None):
        return cls(map(cls._wrap, values), parent=parent)

    def getValue(self, index):
        return self[index].value

    def setValue(self, index, value):
        self[index].value = value

    def insertValue(self, index, value):
        self.insert(index, self._wrap(value))

    def appendValue(self, index, value):
        self.append(self._wrap(value))

    def extendValues(self, items):
        self.extend(map(self._wrap, items))

    def _append(self, value):
        self.parent.value.append(node.value)

    def _insert(self, index, value):
        self.parent.value.insert(index, value)

    def _extend(self, values):
        self.parent.value.extend(values)

    def _delitem(self, index):
        del self.parent.value[index]

    def _setitem(self, index, value):
        self.parent.value[index] = value

    def append(self, node):
        self._append(node.value)
        super().append(node)

    def insert(self, index, node):
        self._insert(index, node.value)
        super().insert(index, node)

    def extend(self, nodes):
        self._extend(node.value for node in nodes)
        super().extend(nodes)

    def __delitem__(self, index):
        self._delitem(index)
        super().__delitem__(index)

    def __setitem__(self, index, node):
        self._setitem(index, node.value)
        super().__setitem__(index)

    def pop(self, index):
        self._delitem(index)
        return super().pop(index)


class Node(object):
    parent = WeakRefProperty("parent")
    value = WeakRefProperty("value")

    def __init__(self, value):
        self.parent = None
        self.value = value

    @value.setter
    def value(self, value):
        del self.children
        parent = self.parent

        if parent is not None:
            parent.children._setitem(self.indexInParent, value)

        return value

    @property
    def indexInParent(self):
        parent = self.parent
        if parent is not None:
            return parent.index(self)

    def _iterChildren(self):
        return iter(self.value)

    def _wrapChildren(self, children):
        return ChildNodes.fromValues(children, self)

    def index(self, child):
        return self.children.index(child)

    @cached
    def children(self):
        try:
            children = self._iterChildren()

        except TypeError:
            return

        return self._wrapChildren(children)

    @property
    def descendants(self):
        if self.children is None:
            return None

        s = set()

        for child in self.children:
            s.add(child)

            if child.descendants is not None:
                s.update(child.descendants)

        return s

    def canDropChildren(self, model, index, items, row, action):
        return False

    def dropChildren(self, model, index, items, row, action):
        return False


class NoChildren(Node):
    def _iterChildren(self):
        raise TypeError


class QItemModel(QAbstractItemModel):
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

    def __init__(self, root, columns, vheader=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.root = root
        self.columns = columns
        self.vheader = vheader

    def getNode(self, index=QModelIndex()):
        if index.isValid():
            return index.internalPointer() or self.root

        return self.root

    def rowCount(self, parent=QModelIndex()):
        if not self.hasChildren(parent):
            return 0

        return len(self.getNode(parent).children)

    def columnCount(self, parent=QModelIndex()):
        return len(self.columns)

    def index(self, row, column, parent=QModelIndex()):
        node = self.getNode(parent)

        if not node.children or row >= len(node.children):
            return QModelIndex()

        return self.createIndex(row, column, node.children[row])

    def parent(self, index):
        if index.isValid():
            node = index.internalPointer()

            if node is None or node.parent is None or node.parent.parent is None:
                return QModelIndex()

            return self.createIndex(node.parent.parent.index(node.parent), 0, node.parent)

        return QModelIndex()

    @staticmethod
    def _callsafe(func, *args, **kwargs):
        try:
            return func(*args, **kwargs)

        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
            return "ERR"

    def data(self, index, role=Qt.DisplayRole):
        obj = self.getNode(index).value

        if role == Qt.UserRole:
            return obj

        row_index = index.row()
        col_index = index.column()
        col_obj = self.columns[col_index]

        if role in self.ROLEMAPPING.keys() and hasattr(col_obj, self.ROLEMAPPING[role]):
            role_obj = getattr(col_obj, self.ROLEMAPPING[role])

            if callable(role_obj):
                return self._callsafe(role_obj, index, obj)

            else:
                return role_obj

        return QVariant()

    def setData(self, index, data, role=Qt.EditRole):
        if index.isValid():
            row_index = index.row()
            obj = index.data(role=Qt.UserRole)
            col_index = index.column()
            col_obj = self.columns[col_index]

            if role in self.ROLEMAPPING.keys() and \
                    hasattr(col_obj, "set"+self.ROLEMAPPING[role]):
                role_obj = getattr(col_obj, "set"+self.ROLEMAPPING[role])

                if callable(role_obj) and self._callsafe(role_obj, index, obj, data):
                    idx1 = self.index(0, 0, index.parent())
                    idx2 = self.index(self.rowCount()-1,
                                      self.columnCount()-1, index.parent())
                    self.dataChanged.emit(idx1, idx2)
                    return True

        return False

    def headerData(self, index, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if index >= len(self.columns):
                return QVariant()

            col_obj = self.columns[index]

            if role in self.ROLEMAPPING.keys() and hasattr(col_obj, "header"+self.ROLEMAPPING[role]):
                role_obj = getattr(col_obj, "header" + self.ROLEMAPPING[role])

                if callable(role_obj):
                    return self._callsafe(role_obj, index)

                else:
                    return role_obj

            elif role == Qt.DisplayRole:
                return index + 1

        elif orientation == Qt.Vertical:
            return index + 1

    def emitDataChanged(self, parent=QModelIndex()):
        if parent.isValid():
            idx1 = parent.child(0, 0)
            idx2 = parent.child(self.rowCount(parent) -
                                1, self.columnCount() - 1)

        else:
            idx1 = self.index(0, 0)
            idx2 = self.index(self.rowCount() - 1, self.columnCount() - 1)

        self.dataChanged.emit(idx1, idx2)

    def insertRow(self, row_id, row, parent=QModelIndex()):
        node = self.getNode(parent)
        old_rowcount = len(node.children)
        self.beginInsertRows(parent, row_id, row_id)
        node.children.insertValue(row_id, row)
        self.endInsertRows()

        if old_rowcount > 0 or not parent.isValid():
            self.emitDataChanged(parent)

        else:
            self.emitDataChanged(parent.parent())

        return True

    def insertRows(self, row_id, rows, parent=QModelIndex()):
        node = self.getNode(parent)
        self.beginInsertRows(parent, row_id, row_id + len(rows) - 1)

        for k, row in enumerate(rows, row_id):
            node.children.insertValue(k, row)

        self.endInsertRows()
        self.emitDataChanged(parent)
        return True

    def appendRow(self, row, parent=QModelIndex()):
        self.insertRow(self.rowCount(parent), row, parent)

    def moveRow(self, position, newposition, srcparent=QModelIndex(), destparent=QModelIndex()):
        srcnode = self.getNode(srcparent)
        destnode = self.getNode(destparent)

        if self.beginMoveRows(srcparent, position, position, destparent, newposition):
            if srcnode is destnode and newposition > position:
                newposition -= 1

            value = srcnode.children[position].value
            node = srcnode.children.pop(position)
            destnode.children.insert(newposition, node)
            self.endMoveRows()

        self.emitDataChanged(srcparent)

        if srcnode is not destnode:
            self.emitDataChanged(destparent)

        return True

    def removeRow(self, row_id, parent=QModelIndex()):
        node = self.getNode(parent)

        self.beginRemoveRows(parent, row_id, row_id)

        item = node.children.pop(row_id)
        cookie = f"0x{id(self):012x},0x{id(item):012x}"

        with _cookie_lock:
            if cookie in _cookies:
                del _cookies[cookie]

        self.endRemoveRows()

        return True

    def setRow(self, position, row, parent=QModelIndex()):
        node = self.getNode(parent)
        node.children.setValue(position, value)
        self.emitDataChanged(parent)

    def insertColumn(self, col_id, col, parent=QModelIndex()):
        self.beginInsertColumns(parent, col_id, col_id)
        self.columns.insert(col_id, col)
        self.endInsertColumns()
        return True

    def moveColumn(self, position, newposition, srcparent=QModelIndex(), destparent=QModelIndex()):
        if self.beginMoveColumns(srcparent, position, position, destparent, newposition):
            if newposition > position:
                newposition -= 1

            column = self.columns.pop(position)
            self.columns.insert(newposition, column)
            self.endMoveColumns()

        self.emitDataChanged(srcparent)
        self.emitDataChanged(destparent)

        return True

    def moveColumns(self, start, end, newposition, srcparent=QModelIndex(), destparent=QModelIndex()):
        if self.beginMoveColumns(srcparent, start, end - 1, destparent, newposition):
            if newposition > start:
                newposition -= end - start

            columns = self.columns[start:end]
            del self.columns[start:end]

            for k, column in enumerate(columns):
                self.columns.insert(newposition+k, column)

            self.endMoveColumns()

        self.emitDataChanged(srcparent)
        self.emitDataChanged(destparent)

        return True

    def removeColumn(self, col_id, parent=QModelIndex()):
        self.beginRemoveColumns(parent, col_id, col_id)
        del self.columns[col_id]
        self.endRemoveRows()
        return True

    def flags(self, index=QModelIndex()):
        if index.isValid():
            row_index = index.row()
            obj = index.data(role=Qt.UserRole)
            col_index = index.column()
            col_obj = self.columns[col_index]

            if hasattr(col_obj, "flags"):
                if callable(col_obj.flags):
                    flags = self._callsafe(col_obj.flags, index, obj)

                else:
                    flags = col_obj.flags

                if isinstance(flags, Qt.ItemFlags):
                    return flags

        return Qt.ItemIsDropEnabled

    def hasChildren(self, index=QModelIndex()):
        if index.isValid():
            node = index.internalPointer()

        else:
            node = self.root

        return node.children is not None and len(node.children) > 0

    def findIndex(self, node):
        if node.parent is None:
            if node is not self.root:
                raise ValueError("Node not found within root.")

            return QModelIndex()

        return self.index(node.parent.index(node), 0, self.findIndex(node.parent))

    def getCookie(self, index):
        item = index.internalPointer()
        cookie = f"0x{id(self):012x},0x{id(item):012x}"

        with _cookie_lock:
            _cookies[cookie] = item

        return cookie

    def mimeData(self, indexes):
        data = QMimeData()
        cookies = []

        for index in indexes:
            cookie = self.getCookie(index)

            if cookie not in cookies:
                cookies.append(cookie)

        try:
            data.setData("application/x-qabstractitemmodeldatalist",
                         ";".join(cookies).encode("utf8"))

        except Exception:
            pass

        return data

    def dropMimeData(self, data, action, row, column, parent):
        if data.hasUrls():
            return self.dropUrls(data.urls(), action, row, column, parent)

        cookies = data.data("application/x-qabstractitemmodeldatalist")
        items = []

        with _cookie_lock:
            for cookie in bytes(cookies).decode("utf8").split(";"):
                if cookie in _cookies.keys():
                    items.append(_cookies[cookie])

        return self.dropItems(items, action, row, column, parent)

    def dropItems(self, items, action, row, column, parent):
        node = self.getNode(parent)
        obj = node.value
        col_index = parent.column()
        col_obj = self.columns[col_index]

        if row == -1:
            if hasattr(col_obj, "dropItems") and callable(col_obj.dropItems) and self._callsafe(col_obj.dropItems, self, obj, items, action):
                return True

            if hasattr(node, "dropItems") and callable(node.dropChildren):
                return bool(self._callsafe(node.dropItems, self, parent, items, action))

        elif row >= 0 and hasattr(node, "dropChildren") and callable(node.dropChildren):
            return bool(self._callsafe(node.dropChildren, self, parent, items, row, action))

        return False

    def dropUrls(self, urls, action, row, column, parent):
        return False

    def canDropMimeData(self, data, action, row, column, parent):
        if data.hasUrls():
            return self.canDropUrls(data.urls(), action, row, column, parent)

        cookies = data.data("application/x-qabstractitemmodeldatalist")
        items = []

        with _cookie_lock:
            for cookie in bytes(cookies).decode("utf8").split(";"):
                if cookie in _cookies.keys():
                    items.append(_cookies[cookie])

        return self.canDropItems(items, action, row, column, parent)

    def canDropUrls(self, urls, action, row, column, parent):
        return False

    def canDropItems(self, items, action, row, column, parent):
        node = self.getNode(parent)
        obj = node.value
        col_index = parent.column()
        col_obj = self.columns[col_index]

        if row == -1:
            if hasattr(col_obj, "canDropItems"):
                if callable(col_obj.canDropItems) and self._callsafe(col_obj.canDropItems, parent, obj, items, action):
                    return True

                if col_obj.canDropItems:
                    return True

            if hasattr(node, "canDropItems"):
                if callable(node.canDropItems):
                    return bool(self._callsafe(node.canDropItems, self, parent, items, action))

                return bool(node.canDropItems)

            return False

        if hasattr(node, "canDropChildren"):
            if callable(node.canDropChildren):
                return bool(self._callsafe(node.canDropChildren, self, parent, items, row, action))

            return bool(node.canDropChildren)

        return False

    def clearCookies(self):
        prefix = f"0x{id(self):012x},"

        with _cookie_lock:
            for key in list(_cookies.keys()):
                if key.startswith(prefix):
                    del _cookies[key]

    def __del__(self):
        self.clearCookies()


class QIntegerModel(QAbstractItemModel):
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

    def __init__(self, rowcount, columns, vheader=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rowcount = rowcount
        self.columns = columns
        self.vheader = vheader

    def getNode(self, index=QModelIndex()):
        if index.isValid():
            return index.internalPointer() or self.root

        return self.root

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0

        return self._rowcount

    def columnCount(self, parent=QModelIndex()):
        return len(self.columns)

    def index(self, row, column, parent=QModelIndex()):
        if parent.isValid():
            return QModelIndex()

        return self.createIndex(row, column)

    def parent(self, index):
        return QModelIndex()

    @staticmethod
    def _callsafe(func, *args, **kwargs):
        try:
            return func(*args, **kwargs)

        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
            return "ERR"

    def data(self, index, role=Qt.DisplayRole):
        row_index = index.row()

        if role == Qt.UserRole:
            return row_index

        col_index = index.column()
        col_obj = self.columns[col_index]

        if role in self.ROLEMAPPING.keys() and hasattr(col_obj, self.ROLEMAPPING[role]):
            role_obj = getattr(col_obj, self.ROLEMAPPING[role])

            if callable(role_obj):
                return self._callsafe(role_obj, index, row_index)

            else:
                return role_obj

        return QVariant()

    def setData(self, index, data, role=Qt.EditRole):
        if index.isValid():
            row_index = index.row()
            col_index = index.column()
            col_obj = self.columns[col_index]

            if role in self.ROLEMAPPING.keys() and \
                    hasattr(col_obj, "set"+self.ROLEMAPPING[role]):
                role_obj = getattr(col_obj, "set"+self.ROLEMAPPING[role])

                if callable(role_obj) and self._callsafe(role_obj, index, row_index, data):
                    idx1 = self.index(0, 0, index.parent())
                    idx2 = self.index(self.rowCount()-1,
                                      self.columnCount()-1, index.parent())
                    self.dataChanged.emit(idx1, idx2)
                    return True

        return False

    def headerData(self, index, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if index >= len(self.columns):
                return QVariant()

            col_obj = self.columns[index]

            if role in self.ROLEMAPPING.keys() and hasattr(col_obj, "header"+self.ROLEMAPPING[role]):
                role_obj = getattr(col_obj, "header" + self.ROLEMAPPING[role])

                if callable(role_obj):
                    return self._callsafe(role_obj, index)

                else:
                    return role_obj

            elif role == Qt.DisplayRole:
                return index + 1

        elif orientation == Qt.Vertical:
            return index + 1

    def emitDataChanged(self, parent=QModelIndex()):
        if parent.isValid():
            idx1 = parent.child(0, 0)
            idx2 = parent.child(self.rowCount(parent) -
                                1, self.columnCount() - 1)

        else:
            idx1 = self.index(0, 0)
            idx2 = self.index(self.rowCount() - 1, self.columnCount() - 1)

        self.dataChanged.emit(idx1, idx2)

    def setRowCount(self, rowcount, parent=QModelIndex()):
        if rowcount < self._rowcount:
            self.beginRemoveRows(parent, rowcount, self._rowcount - 1)
            self._rowcount = rowcount
            self.endRemoveRows()

        elif rowcount > self._rowcount:
            self.beginInsertRows(parent, self._rowcount, rowcount - 1)
            self._rowcount = rowCount
            self.endInsertRows()

    def insertColumn(self, col_id, col, parent=QModelIndex()):
        self.beginInsertColumns(parent, col_id, col_id)
        self.columns.insert(col_id, col)
        self.endInsertColumns()
        return True

    def insertColumns(self, col_id, cols, parent=QModelIndex()):
        self.beginInsertColumns(parent, col_id, col_id + len(cols) - 1)

        for k, col in enumerate(cols, col_id):
            self.columns.insert(k, col)

        self.endInsertColumns()
        return True

    def moveColumn(self, position, newposition, srcparent=QModelIndex(), destparent=QModelIndex()):
        if self.beginMoveColumns(srcparent, position, position, destparent, newposition):
            if newposition > position:
                newposition -= 1

            column = self.columns.pop(position)
            self.columns.insert(newposition, column)
            self.endMoveColumns()

        self.emitDataChanged(srcparent)
        self.emitDataChanged(destparent)

        return True

    def moveColumns(self, start, end, newposition, srcparent=QModelIndex(), destparent=QModelIndex()):
        if self.beginMoveColumns(srcparent, start, end - 1, destparent, newposition):
            if newposition > start:
                newposition -= end - start

            columns = self.columns[start:end]
            del self.columns[start:end]

            for k, column in enumerate(columns):
                self.columns.insert(newposition+k, column)

            self.endMoveColumns()

        self.emitDataChanged(srcparent)
        self.emitDataChanged(destparent)

        return True

    def removeColumn(self, col_id, parent=QModelIndex()):
        self.beginRemoveColumns(parent, col_id, col_id)
        del self.columns[col_id]
        self.endRemoveRows()
        return True

    def removeColumns(self, start, end, parent=QModelIndex()):
        self.beginRemoveColumns(parent, start, end - 1)
        del self.columns[start:end]
        self.endRemoveRows()
        return True

    def flags(self, index=QModelIndex()):
        if index.isValid():
            row_index = index.row()
            col_index = index.column()

            if col_index >= len(self.columns):
                return Qt.ItemIsDropEnabled

            col_obj = self.columns[col_index]

            if hasattr(col_obj, "flags"):
                if callable(col_obj.flags):
                    flags = self._callsafe(col_obj.flags, index, row_index)

                else:
                    flags = col_obj.flags

                if isinstance(flags, Qt.ItemFlags):
                    return flags

        return Qt.ItemIsDropEnabled

    def hasChildren(self, index=QModelIndex()):
        return not index.isValid()
