#!/usr/bin/python
from PyQt5.QtCore import (Qt, QModelIndex, pyqtSignal, QModelIndex, QItemSelectionModel)
from PyQt5.QtWidgets import (QApplication, QMenu, QAbstractItemView, QItemDelegate,
                             QTableView)
from PyQt5.QtCore import pyqtSlot
import sys
import traceback

from .qitemmodel import QIntegerModel
from .qframetablecolumn import *


class FrameTable(QTableView):
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initCols()
        model = SortAndFilterProxy()
        model.dataChanged.connect(self.contentsModified)
        self.setModel(model)
        self.setFilters(None)
        self.verticalHeader().setDefaultSectionSize(self.fontMetrics().height())

    def setFont(self, font):
        super().setFont(font)
        self.verticalHeader().setDefaultSectionSize(self.fontMetrics().height())

    def _initCols(self):
        self.idcol = FrameNumberCol(None)
        self.tscol = TimeStampCol(None)
        self.colsleft = [self.idcol, self.tscol]

        self.id2col = NewFrameNumberCol(None)
        self.ts2col = NewTimeStampCol(None)
        self.diffcol = DiffCol(None)
        self.colsright = [self.id2col, self.ts2col, self.diffcol]

        self.filter_columns = []

    def setFilters(self, filters):
        self.filters = filters

        if filters is not None:
            self.columns_by_filter = []
            self.idcol.srcstream = filters.source
            self.tscol.stream = filters.source
            self.id2col.filter = filters
            self.ts2col.filter = filters
            self.diffcol.filter = filters

            newfiltercols = []

            """Create new filter column list."""
            for filter in filters:
                if hasattr(filter, "QtTableColumns"):
                    if callable(filter.QtTableColumns):
                        filtercols = filter.QtTableColumns()

                    else:
                        filtercols = filter.QtTableColumns

                    newfiltercols.extend(filtercols)
                    self.columns_by_filter.append(filtercols)

            #"""Compare new filter column list to old."""
            # for col in self.filter_columns.copy():
                # if col not in newfiltercols:
                    #"""Old column does not appear in newfiltercols, so it is removed from the model."""
                    # self.filter_columns.remove(col)

                    # if col in self.datamodel.columns:
                    #m = self.datamodel.columns.index(col)
                    # self.datamodel.removeColumn(m)
                    #del headersizes[m]

            #"""Insert new columns, move existing columns."""
            # for n, col in enumerate(newfiltercols, len(self.colsleft)):
                # if col in self.datamodel.columns:
                    #"""Column exists in model, so it will just be moved."""
                    #m = self.datamodel.columns.index(col)

                    # if m > n: # Should never have m < n.
                    #self.datamodel.moveColumn(m, n)
                    #size = headersizes.pop(m)
                    #headersizes.insert(n, size)

                # else:
                    #"""Column is new."""
                    #self.datamodel.insertColumn(n, col)

                    # if hasattr(col, "width"):
                    #headersizes.insert(n, col.width)

                    # else:
                    #headersizes.insert(n, None)

            self.datamodel = QIntegerModel(filters.prev.framecount,
                                           self.colsleft + newfiltercols + self.colsright, self)
            self.model().setSourceModel(self.datamodel)

            #headersizes = [self.columnWidth(k) for k in range(self.datamodel.columnCount())]

            for n, col in enumerate(self.colsleft + newfiltercols + self.colsright):
                if hasattr(col, "itemdelegate") and isinstance(col.itemdelegate, QItemDelegate):
                    self.setItemDelegateForColumn(n, col.itemdelegate)

                if hasattr(col, "width") and col.width is not None:
                    self.setColumnWidth(n, col.width)

            self.filter_columns = newfiltercols

        else:
            self.idcol.srcstream = None
            self.tscol.stream = None
            self.id2col.filter = None
            self.ts2col.filter = None
            self.diffcol.filter = None
            self.filter_columns = []
            self.datamodel = QIntegerModel(0, [])
            self.model().setSourceModel(self.datamodel)

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

        return super().keyPressEvent(event)

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
            col = max(0, current.column())

        newindex = self.model().sourceModel().index(row, col)
        newindex = self.model().mapFromSource(newindex)
        self.setCurrentIndex(newindex)
        sm = self.selectionModel()
        sm.setCurrentIndex(newindex, QItemSelectionModel.ClearAndSelect)
        #sm.currentChanged.emit(newindex, current)

        self.setCurrentIndex(newindex)
        self.scrollTo(newindex, QAbstractItemView.PositionAtCenter)

    def handleFilterMoved(self, oldindex, newindex):
        movedcolumns = self.columns_by_filter[oldindex]
        columns_before_old = self.columns_by_filter[:oldindex]
        columns_before_new = self.columns_by_filter[:newindex]

        K = len(self.colsleft)
        M = sum(map(len, columns_before_old))
        N = sum(map(len, columns_before_new))
        L = len(movedcolumns)

        if L:
            self.datamodel.moveColumns(K + M, K + M + L, K + N)

        del self.columns_by_filter[oldindex]
        del self.filter_columns[K+M: K+M+len(movedcolumns)]

        W1 = [self.columnWidth(k) for k in range(K+M, K+M+L)]

        if newindex > oldindex:
            newindex -= 1
            W2 = [self.columnWidth(k) for k in range(K+M+L, K+N)]
            N -= len(movedcolumns)

        else:
            W2 = [self.columnWidth(k) for k in range(K+N, K+M)]

        self.columns_by_filter.insert(newindex, movedcolumns)

        for k, col in enumerate(movedcolumns, K+N):
            self.filter_columns.insert(k, col)

        if newindex > oldindex:
            W = W2 + W1

        else:
            W = W1 + W2

        for k, w in enumerate(W, K + min(M, N)):
            self.setColumnWidth(k, w)

    def handleFilterRemoved(self, index):
        removedcolumns = self.columns_by_filter[index]
        columns_before = self.columns_by_filter[:index]

        K = len(self.colsleft)
        M = sum(map(len, columns_before))
        L = len(removedcolumns)

        if L:
            self.datamodel.removeColumns(K + M, K + M + L)

        del self.columns_by_filter[index]
        del self.filter_columns[K+M: K+M+L]

    def handleFilterInserted(self, index):
        filter = self.filters[index]
        K = len(self.colsleft)
        M = sum(map(len, self.columns_by_filter[:index]))

        if hasattr(filter, "QtTableColumns"):
            if callable(filter.QtTableColumns):
                filtercols = filter.QtTableColumns()

            else:
                filtercols = filter.QtTableColumns

            self.datamodel.insertColumns(K + M, filtercols)
            self.columns_by_filter.insert(index, filtercols)

            for n, col in enumerate(filtercols, K + M):
                if hasattr(col, "width") and isinstance(col.width, (int, float)):
                    self.setColumnWidth(n, col.width)

                if hasattr(col, "itemdelegate") and isinstance(col.itemdelegate, QItemDelegate):
                    self.setItemDelegateForColumn(n, col.itemdelegate)


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
