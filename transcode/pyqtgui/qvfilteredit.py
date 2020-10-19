from .qframetable import FrameTable
from .qimageview import QMultiImageView
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QSpinBox, QLabel, QDialog,
                             QPushButton, QSplitter, QTreeView, QMessageBox)
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QModelIndex, Qt
from PyQt5.QtGui import QFont
from .qitemmodel import QItemModel, Node, ChildNodes, NoChildren
from transcode.filters.video import filters
from transcode.filters.video.base import BaseVideoFilter
import sys
import traceback

class AvailableFiltersModel(QItemModel):
    def canDragItems(self, *args):
        return True

    def supportedDragActions(self):
        return Qt.CopyAction

class AvailableFiltersCol(object):
    font  = QFont("DejaVu Serif", 8)
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled
    textalign = Qt.AlignLeft

    def display(self, index, obj):
        return obj.__str__(None)

    def tooltip(self, index, obj):
        mod = ".".join(obj.__module__.split(".")[2:])

        if obj.__doc__:
            return f"{mod}.{obj.__name__}\n\n{obj.__doc__}"

        return f"{mod}.{obj.__name__}"

class AvailableFiltersListView(QTreeView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragEnabled(True)
        self.setDragDropMode(QTreeView.DragOnly)
        self.setIndentation(0)
        self.setHeaderHidden(True)
        root = Node(sorted(filters.values(), key=lambda cls: cls.__name__))
        self.setModel(AvailableFiltersModel(root, [AvailableFiltersCol()]))

class CurrentFiltersModel(QItemModel):
    def canDragItems(self, *args):
        return True

    def canDropItems(self, items, action, row, column, parent):
        if action == Qt.CopyAction:
            for item in items:
                if not (isinstance(item.value, type) and issubclass(item.value, BaseVideoFilter)):
                    return False

        elif action == Qt.MoveAction:
            for item in items:
                if item not in self.root.children:
                    return False

        return True

    def dropItems(self, items, action, row, column, parent):
        if row == -1:
            row = self.rowCount(parent)

        if action == Qt.CopyAction:
            for k, item in enumerate(items):
                if hasattr(item.value, "QtInitialize") and callable(item.value.QtInitialize):
                    if row < len(self.root.children):
                        prev = self.root.children[row].value.prev

                    else:
                        prev = self.root.children[-1].value

                    filter = item.value.QtInitialize(prev)

                else:
                    filter = item.value()

                if filter is not None:
                    self.insertRow(row, filter)

        elif action == Qt.MoveAction:
            j = 0

            for k, item in enumerate(items):
                oldrow = self.root.index(item)
                self.moveRow(oldrow, row + k - j)

                if oldrow < row:
                    j += 1

        return True

    def supportedDragActions(self):
        return Qt.MoveAction

    def supportedDropActions(self):
        return Qt.CopyAction | Qt.MoveAction

class CurrentFiltersNode(Node):
    def _wrapChildren(self, children):
        return CurrentFiltersItems.fromValues(children, self)

class CurrentFiltersItems(ChildNodes):
    @staticmethod
    def _wrap(item):
        return CurrentFilterNode(item)

class CurrentFilterNode(NoChildren):
    pass

class CurrentFiltersCol(object):
    font  = QFont("DejaVu Serif", 8)
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled
    textalign = Qt.AlignLeft

    def display(self, index, obj):
        return str(obj)

    def tooltip(self, index, obj):
        cls = obj.__class__.__name__
        mod = ".".join(obj.__class__.__module__.split(".")[2:])

        if obj.__doc__:
            return f"{mod}.{cls}\n\n{obj.__doc__}"

        return f"{mod}.{cls}"

class CurrentFiltersListView(QTreeView):
    contentsModified = pyqtSignal()
    filterMoved = pyqtSignal(int, int)
    filterInserted = pyqtSignal(int)
    filterRemoved = pyqtSignal(int)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragEnabled(True)
        self.setDragDropMode(QTreeView.DragDrop)
        self.setAcceptDrops(True)
        self.setIndentation(0)
        self.setHeaderHidden(True)
        self.setFilters(None)

    def setFilters(self, filters):
        self.filters = filters

        if filters is not None:
            root = CurrentFiltersNode(filters)
            model = CurrentFiltersModel(root, [CurrentFiltersCol()])
            self.setModel(model)
            model.dataChanged.connect(self.contentsModified)
            model.rowsMoved.connect(self._emitFilterMoved)
            model.rowsInserted.connect(self._emitFilterInserted)
            model.rowsRemoved.connect(self._emitFilterRemoved)

        else:
            self.setModel(QItemModel(Node(None), []))

    def _emitFilterMoved(self, parent, start, end, dest, dest_row):
        self.filterMoved.emit(start, dest_row)
        self.contentsModified.emit()

    def _emitFilterInserted(self, parent, start, end):
        self.filterInserted.emit(start)
        print("Inserted")
        self.contentsModified.emit()

    def _emitFilterRemoved(self, parent, start, end):
        self.filterRemoved.emit(start)
        self.contentsModified.emit()

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
        answer = QMessageBox.question(self, "Delete tracks", "Do you wish to delete the selected tracks? All encoder and settings associated with selected tracks will be lost!", QMessageBox.Yes | QMessageBox.No)

        if answer == QMessageBox.Yes:
            self.deleteSelected()

    def deleteSelected(self):
        selected = sorted(idx.row() for idx in self.selectionModel().selectedRows())

        for k, row in enumerate(selected):
            self.model().removeRow(row - k)

        self.contentsModified.emit()

    def mouseDoubleClickEvent(self, event):
        idx = self.indexAt(event.pos())
        filter = idx.data(Qt.UserRole)
        self.configureFilter(filter)

    def configureFilter(self, filter):
        if hasattr(filter, "QtDlg") and callable(filter.QtDlg):
            try:
                if filter.QtDlg(parent=self).exec_():
                    self.contentsModified.emit()

            except:
                (cls, exc, tb) = sys.exc_info()
                excmsg = QMessageBox(self)
                excmsg.setWindowTitle("Error")
                excmsg.setText("An exception was encountered\n\n%s" % "".join(traceback.format_exception(cls, exc, tb)))              
                excmsg.setStandardButtons(QMessageBox.Ok)
                excmsg.setIcon(QMessageBox.Critical)
                excmsg.exec_()


class VFilterEdit(QWidget):
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        splitter = QSplitter(Qt.Horizontal, self)
        layout.addWidget(splitter)

        subsplitter = QSplitter(Qt.Vertical, splitter)
        splitter.addWidget(subsplitter)

        self.availableFilters = AvailableFiltersListView(subsplitter)
        self.availableFilters.setMaximumWidth(240)
        subsplitter.addWidget(self.availableFilters)

        self.currentFilters = CurrentFiltersListView(subsplitter)
        self.currentFilters.setMaximumWidth(240)
        subsplitter.addWidget(self.currentFilters)

        subsplitter = QSplitter(Qt.Vertical, splitter)
        splitter.addWidget(subsplitter)

        subsplitter2 = QSplitter(Qt.Horizontal, subsplitter)

        self.inputPreviewWindow = QMultiImageView(subsplitter2)
        self.inputPreviewWindow.setMinimumHeight(320)
        self.outputPreviewWindow = QMultiImageView(subsplitter2)
        subsplitter2.addWidget(self.inputPreviewWindow)
        subsplitter2.addWidget(self.outputPreviewWindow)

        w = QWidget(subsplitter)
        subsplitter.addWidget(w)
        wlayout = QVBoxLayout()
        w.setLayout(wlayout)

        self.frameTable = FrameTable(w)
        self.frameTable.setMinimumWidth(640)
        self.frameTable.setMinimumHeight(360)
        sm = self.frameTable.selectionModel()
        sm.currentChanged.connect(self.currentItemChanged)
        self.frameTable.contentsModified.connect(self.tableUpdated)
        self.currentFilters.filterMoved.connect(self.frameTable.handleFilterMoved)
        self.currentFilters.filterRemoved.connect(self.frameTable.handleFilterRemoved)
        self.currentFilters.filterInserted.connect(self.frameTable.handleFilterInserted)
        self.currentFilters.contentsModified.connect(self.contentsModified)

        wlayout.addWidget(self.frameTable)

        self.oldFrameIndex = QSpinBox(w)
        self.oldFrameIndex.editingFinished.connect(self.scrollToOld)
        self.newFrameIndex = QSpinBox(w)
        self.newFrameIndex.editingFinished.connect(self.scrollToNew)

        w2layout = QHBoxLayout()
        wlayout.addLayout(w2layout)
        w2layout.addWidget(QLabel("Old #", self))
        w2layout.addWidget(self.oldFrameIndex)

        w2layout.addWidget(QLabel("New #", self))
        w2layout.addWidget(self.newFrameIndex)
        w2layout.addStretch()

        gotoLayout = QVBoxLayout()
        self.setFilters(None)

    def setFilters(self, filters):
        self.filters = filters

        if filters is not None:
            self.oldFrameIndex.setMaximum(filters.src.framecount - 1)
            self.newFrameIndex.setMaximum(filters.framecount - 1)

            self.inputPreviewWindow.setFrameSource(filters.src)
            self.inputPreviewWindow.setSar(filters.src.sar)

            self.outputPreviewWindow.setFrameSource(filters)
            self.outputPreviewWindow.setSar(filters.sar)

        else:
            self.inputPreviewWindow.setFrameSource(None)
            self.inputPreviewWindow.setSar(1)

            self.outputPreviewWindow.setFrameSource(None)
            self.outputPreviewWindow.setSar(1)

        self.currentFilters.setFilters(filters)
        self.frameTable.setFilters(filters)

    @pyqtSlot()
    def scrollToOld(self):
        index = self.oldFrameIndex.value()
        self.frameTable.goto(row=index)

    @pyqtSlot()
    def scrollToNew(self):
        index = self.newFrameIndex.value()
        self.frameTable.goto(row=self.filters.cumulativeIndexReverseMap[index])

    @pyqtSlot(QModelIndex, QModelIndex)
    def currentItemChanged(self, new, old):
        n1 = old.data(Qt.UserRole)
        n2 = new.data(Qt.UserRole)

        if n1 != n2:
            self.oldFrameIndex.setValue(n2)
            self.inputPreviewWindow.setFrameOffset(n2)

        if n1 is not None:
            m1 = self.filters.cumulativeIndexMap[n1]

            while m1 < 0:
                n1 += 1

                if n1 >= len(self.filters.cumulativeIndexMap):
                    m1 = self.filters.framecount - 1
                    break

                m1 = self.filters.cumulativeIndexMap[n1]

        else:
            m1 = None

        m2 = self.filters.cumulativeIndexMap[n2]

        while m2 < 0:
            n2 += 1

            if n2 >= len(self.filters.cumulativeIndexMap):
                m2 = self.filters.framecount - 1
                break

            m2 = self.filters.cumulativeIndexMap[n2]

        if m1 != m2:
            self.newFrameIndex.setValue(m2)
            self.outputPreviewWindow.setFrameOffset(m2)

    @pyqtSlot()
    def tableUpdated(self):
        n = self.frameTable.currentIndex().data(role=Qt.UserRole)

        if n is not None:
            m = self.filters.cumulativeIndexMap[n]

            while m < 0:
                n += 1
                m = self.filters.cumulativeIndexMap[n]

            self.outputPreviewWindow.setFrameOffset(m)

        self.contentsModified.emit()

class VFilterEditDlg(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle("Video Filter Editor")

        layout = QVBoxLayout()
        self.setLayout(layout)
        self.editor = VFilterEdit(self)
        self.editor.contentsModified.connect(self.isModified)
        layout.addWidget(self.editor)
        btnlayout = QHBoxLayout()
        layout.addLayout(btnlayout)
        self.okayBtn = QPushButton("&Okay", self)
        self.applyBtn = QPushButton("&Apply", self)
        self.closeBtn = QPushButton("&Close", self)

        self.okayBtn.clicked.connect(self.applyAndClose)
        self.applyBtn.clicked.connect(self.apply)
        self.closeBtn.clicked.connect(self.close)

        btnlayout.addStretch()
        btnlayout.addWidget(self.okayBtn)
        btnlayout.addWidget(self.applyBtn)
        btnlayout.addWidget(self.closeBtn)
        self.notModified()
        self.setFilters(None)

    def setFilters(self, filters):
        self.filters = filters
        self.editor.setFilters(filters)
        self.notModified()

    def isModified(self):
        self.modified = True
        self.closeBtn.setText("&Cancel")
        self.okayBtn.setDisabled(False)
        self.applyBtn.setDisabled(False)

    def notModified(self):
        self.modified = False
        self.closeBtn.setText("&Close")
        self.okayBtn.setDisabled(True)
        self.applyBtn.setDisabled(True)

    @pyqtSlot()
    def show(self):
        if self.parent() is not None:
            self.parent().setDisabled(True)

        super().show()

    @pyqtSlot()
    def applyAndClose(self):
        self.apply()
        self.close()

    @pyqtSlot()
    def apply(self):
        self.done(1)
        self.notModified()

    @pyqtSlot()
    def close(self):
        if self.parent() is not None:
            self.parent().setEnabled(True)

        super().close()
