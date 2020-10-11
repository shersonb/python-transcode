#!/usr/bin/python
from PyQt5.QtCore import (QDir, Qt, QModelIndex, pyqtSignal, QThread, QAbstractListModel, QAbstractTableModel,
                          QVariant, QModelIndex, QAbstractItemModel, QItemSelectionModel)
from PyQt5.QtGui import QImage, QPainter, QPalette, QPixmap, QColor, QFont, QBrush, QPen, QStandardItemModel
from PyQt5.QtWidgets import (QAction, QApplication, QFileDialog, QLabel, QFrame,
        QMainWindow, QMenu, QMessageBox, QGridLayout, QScrollArea, QSizePolicy, QWidget,
        QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton, QTableWidget, QTableWidgetItem,
        QAbstractItemView, QHeaderView, QProgressBar, QStatusBar, QTabWidget, QVBoxLayout,
        QComboBox, QItemDelegate, QListView, QStyle, QTableView)
from PyQt5.QtPrintSupport import QPrintDialog, QPrinter
from PyQt5.QtCore import pyqtSlot
import sys
from functools import partial
import traceback

from transcode.util import ConfigStore
from .qobjectitemmodel import QObjectItemModel
from .qframetablecolumn import *

class QFrameTableModel(QObjectItemModel):
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

    def hasChildren(self, index):
        if index.isValid():
            return False

        return True

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0

        return len(self.items)

class FrameTable(QTableView):
    contentsUpdated = pyqtSignal()
    def __init__(self, filters, *args, **kwargs):
        super(QTableView, self).__init__(*args, **kwargs)
        self.filters = filters

        self._initModel(filters)
        cols = self.colsleft + self.colsright

        model = SortAndFilterProxy()
        model.setSourceModel(self.datamodel)
        self.setModel(model)

        for n, col in enumerate(cols):
            if hasattr(col, "width"):
                self.setColumnWidth(n, col.width)

            if hasattr(col, "itemdelegate") and isinstance(col.itemdelegate, QItemDelegate):
                self.setItemDelegateForColumn(n, col.itemdelegate)

        self.loadFilters(filters)

    def _initModel(self, filters):
        self.idcol = FrameNumberCol(filters.src)
        self.tscol = TimeStampCol(filters.src)
        self.colsleft = [self.idcol, self.tscol]

        self.id2col = NewFrameNumberCol(filters)
        self.ts2col = NewTimeStampCol(filters)
        self.diffcol = DiffCol(filters)
        self.colsright = [self.id2col, self.ts2col, self.diffcol]
        self.datamodel = QFrameTableModel(range(filters.prev.framecount), self.colsleft+self.colsright, self)
        self.filter_columns = []
        self.columns_by_filter = []

    def loadFilters(self, filters):
        newfiltercols = []
        headersizes = [self.columnWidth(k) for k in range(self.datamodel.columnCount())]


        """Create new filter column list."""
        for filter in filters:
            if hasattr(filter, "QtTableColumns"):
                if callable(filter.QtTableColumns):
                    filtercols = filter.QtTableColumns()

                else:
                    filtercols = filter.QtTableColumns

                newfiltercols.extend(filtercols)

        """Compare new filter column list to old."""
        for col in self.filter_columns.copy():
            if col not in newfiltercols:
                """Old column does not appear in newfiltercols, so it is removed from the model."""
                self.filter_columns.remove(col)
                m = self.datamodel.columns.index(col)
                self.datamodel.removeColumn(m)
                del headersizes[m]

        """Insert new columns, move existing columns."""
        for n, col in enumerate(newfiltercols, len(self.colsleft)):
            if col in self.datamodel.columns:
                """Column exists in model, so it will just be moved."""
                m = self.datamodel.columns.index(col)

                if m > n: # Should never have m < n.
                    self.datamodel.moveColumn(m, n)
                    size = headersizes.pop(m)
                    headersizes.insert(n, size)

            else:
                """Column is new."""
                self.datamodel.insertColumn(n, col)

                if hasattr(col, "width"):
                    headersizes.insert(n, col.width)

                else:
                    headersizes.insert(n, None)

                if hasattr(col, "itemdelegate") and isinstance(col.itemdelegate, QItemDelegate):
                    self.setItemDelegateForColumn(n, col.itemdelegate)

        for n, size in enumerate(headersizes):
            if size is not None:
                self.setColumnWidth(n, size)

        self.filter_columns = newfiltercols
        self.id2col.filter = filters
        self.ts2col.filter = filters
        self.diffcol.filter = filters

    def setCurrentCell(self, row, col):
        current = self.currentIndex()
        current = current.sibling(row, col)
        self.setCurrentIndex(idx)

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        idx = self.currentIndex()
        row = idx.row()
        col = idx.column()
        model = self.model()
        selectionModel = self.selectionModel()
        keypressfunc = model.data(self.currentIndex(), Qt.UserRole + 2)

        if key in (Qt.Key_Return, Qt.Key_Enter):
            if modifiers & Qt.ShiftModifier:
                for k in range(1, model.rowCount()):
                    q, r = divmod(row - k, model.rowCount())

                    if self.isRowHidden(r) == False:
                        p = (col + q) % model.columnCount()
                        sibling = idx.sibling(r, p)
                        self.setCurrentIndex(sibling)
                        break

            else:
                for k in range(1, model.rowCount()):
                    q, r = divmod(row + k, model.rowCount())

                    if self.isRowHidden(r) == False:
                        p = (col + q) % model.columnCount()
                        sibling = idx.sibling(r, p)
                        self.setCurrentIndex(sibling)
                        break

        elif key == Qt.Key_Tab:
            idx = self.currentIndex()

            if modifiers & Qt.ShiftModifier:
                if idx.column() > 0: 
                    self.setCurrentCell(idx.row(), idx.column()-1)

                elif idx.row() > 0:
                    self.setCurrentCell(self.row() - 1, idx.columncount()-1)

            elif self.state() == QAbstractItemView.EditingState:
                if idx.column() < model.columnCount() - 1: 
                    self.setCurrentCell(idx.row(), idx.column()+1)

                elif idx.row() < model.rowCount() - 1:
                    self.setCurrentCell(idx.row()+1, 0)

        elif self.state() == QAbstractItemView.EditingState and key == Qt.Key_Escape:
            self.closeEditor()

        elif callable(keypressfunc) and keypressfunc(self, event):
            return

        elif key == Qt.Key_Delete:
            model.blockSignals(True)

            for selected in self.selectedIndexes():
                try:
                    model.setData(selected, None, role=Qt.EditRole)

                except:
                    pass

            model.blockSignals(False)
            idx1 = model.index(0, 0)
            idx2 = model.index(model.rowCount() - 1, model.columnCount() - 1)
            model.dataChanged.emit(idx1, idx2)

        elif key == Qt.Key_V and modifiers == Qt.ControlModifier:
            current = self.currentIndex()
            clipboard = QApplication.clipboard()

            text = clipboard.text()

            if text:
                try:
                    self.model().setData(current, text)

                except:
                    print(traceback.format_exc(), file=sys.stderr)

        return QTableView.keyPressEvent(self, event)

    def contextMenuEvent(self, event):
        selected = self.currentIndex()
        menu = self.model().data(selected, role=Qt.UserRole + 1)

        if callable(menu):
            menu = menu(self)

        if isinstance(menu, QMenu):
            menu.exec_(self.mapToGlobal(event.pos()))

    def goto(self, row=None, col=None):
        current = self.currentIndex()
        current = self.model().mapToSource(current)

        if row is None and col is None:
            raise ValueError("Must specify at least one of 'row' or 'col'.")
        elif row is None:
            row = current.row()
        elif col is None:
            col = current.column()

        newindex = self.model().sourceModel().createIndex(row, col)
        newindex = self.model().mapFromSource(newindex)
        sm = self.selectionModel()
        sm.setCurrentIndex(newindex, QItemSelectionModel.Select)
        sm.currentChanged.emit(newindex, current)

        self.setCurrentIndex(newindex)
        self.scrollTo(newindex, QAbstractItemView.PositionAtCenter)

class SortAndFilterProxy(QSortFilterProxyModel):
    def __init__(self, filterFunc=None, *args, **kwargs):
        super(SortAndFilterProxy, self).__init__(*args, **kwargs)
        self._filter = filterFunc

    def setFilterFunc(self, filter):
        self._filter = filter
        self.invalidateFilter()

    def filterFunc(self):
        return self._filter

    def filterAcceptsRow(self, row, index=QModelIndex()):
        if callable(self._filter):
            return self._filter(row)

        elif isinstance(self._filter, (set, tuple, list)):
            return row in self._filter

        return True


