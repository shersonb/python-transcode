from .qframetable import FrameTable
from .qimageview import QMultiImageView
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QBoxLayout,
                             QGridLayout, QLabel, QSplitter, QTreeView, QMessageBox)
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QModelIndex, Qt, QTime
from PyQt5.QtGui import QFont
from .qitemmodel import QItemModel, Node, ChildNodes, NoChildren
from transcode.filters.video import filters
from transcode.filters.video.base import BaseVideoFilter
from transcode.filters.base import FilterChain
from .qfilterconfig import QFilterConfig
from .qframeselect import QFrameSelect
import sys
import traceback
from fractions import Fraction as QQ


class AvailableFiltersModel(QItemModel):
    def canDragItems(self, *args):
        return True

    def supportedDragActions(self):
        return Qt.CopyAction


class AvailableFiltersCol(object):
    font = QFont("DejaVu Serif", 8)
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
                if len(self.root.children) == 0:
                    prev = self.root.value.prev

                elif row < len(self.root.children):
                    prev = self.root.children[row].value.prev

                else:
                    prev = self.root.children[-1].value

                if item.value.hasQtDlg():
                    dlg = item.value.QtInitialize()
                    dlg.setFilterPrev(prev)

                    if dlg.exec_():
                        filter = dlg.filter

                    else:
                        filter = None

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


class CurrentFiltersRoot(Node):
    def _wrapChildren(self, children):
        return CurrentFiltersItems.fromValues(children, self)


class CurrentFiltersItems(ChildNodes):
    @staticmethod
    def _wrap(item):
        return CurrentFilterNode(item)


class CurrentFilterNode(NoChildren):
    pass


class CurrentFiltersCol(object):
    font = QFont("DejaVu Serif", 8)
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
            root = CurrentFiltersRoot(filters)
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

        selected = sorted(idx.row()
                          for idx in self.selectionModel().selectedRows())

        if key == Qt.Key_Delete and modifiers == Qt.NoModifier and len(self.selectionModel().selectedRows()):
            self.askDeleteSelected()

        super().keyPressEvent(event)

    def askDeleteSelected(self):
        answer = QMessageBox.question(
            self, "Delete tracks", "Do you wish to delete the selected tracks? All encoder and settings associated with selected tracks will be lost!", QMessageBox.Yes | QMessageBox.No)

        if answer == QMessageBox.Yes:
            self.deleteSelected()

    def deleteSelected(self):
        selected = sorted(idx.row()
                          for idx in self.selectionModel().selectedRows())

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
                filter.QtDlg(
                    parent=self, settingsApplied=self.contentsModified)

            except:
                (cls, exc, tb) = sys.exc_info()
                excmsg = QMessageBox(self)
                excmsg.setWindowTitle("Error")
                excmsg.setText("An exception was encountered\n\n%s" %
                               "".join(traceback.format_exception(cls, exc, tb)))
                excmsg.setStandardButtons(QMessageBox.Ok)
                excmsg.setIcon(QMessageBox.Critical)
                excmsg.exec_()


class QAvailableFilters(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        self.setLayout(layout)

        label = QLabel("Available Filters", self)
        label.setFont(QFont("DejaVu Serif", 18, QFont.Bold, italic=True))
        layout.addWidget(label)

        self.listView = AvailableFiltersListView(self)
        layout.addWidget(self.listView)


class QCurrentFilters(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        self.setLayout(layout)

        label = QLabel("Current Filters", self)
        label.setFont(QFont("DejaVu Serif", 18, QFont.Bold, italic=True))
        layout.addWidget(label)

        self.listView = CurrentFiltersListView(self)
        layout.addWidget(self.listView)


class VFrameView(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.setLayout(layout)

        self.inputPreviewWindow = QMultiImageView(self)
        self.inputFrameSelect = QFrameSelect(self)
        self.inputFrameSelect.frameSelectionChanged.connect(self.setInputFrame)
        self.inputFrameSelect.leftLabel.hide()
        self.inputFrameSelect.rightLabel.hide()

        self.outputPreviewWindow = QMultiImageView(self)
        self.outputFrameSelect = QFrameSelect(self)
        self.outputFrameSelect.frameSelectionChanged.connect(
            self.setOutputFrame)
        self.outputFrameSelect.leftLabel.hide()
        self.outputFrameSelect.rightLabel.hide()

        layout.addWidget(self.inputPreviewWindow, 0, 0)
        layout.addWidget(self.outputPreviewWindow, 0, 1)
        layout.addWidget(self.inputFrameSelect, 1, 0)
        layout.addWidget(self.outputFrameSelect, 1, 1)
        self.updateChildGeometry(self.size())

    def resizeEvent(self, event):
        self.updateChildGeometry(event.size())
        super().resizeEvent(event)

    def updateChildGeometry(self, size):
        W = size.width()
        H = size.height()

        fsH = max(self.inputFrameSelect.sizeHint().height(),
                  self.outputFrameSelect.sizeHint().height())

        if self.inputPreviewWindow.framesource is not None and \
                self.outputPreviewWindow.framesource is not None:
            inputDar = self.inputPreviewWindow.dar
            outputDar = self.outputPreviewWindow.dar
            ratio = QQ(inputDar, outputDar)

            self.layout().setColumnStretch(0, ratio.numerator)
            self.layout().setColumnStretch(1, ratio.denominator)

    def setInputSource(self, source):
        self.inputPreviewWindow.setFrameSource(source)
        self.inputFrameSelect.setPtsTimeArray(source.pts_time)
        self.inputPreviewWindow.setFrameOffset(
            self.inputFrameSelect.slider.value())
        self.updateChildGeometry(self.size())

    def setOutputSource(self, source):
        self.outputPreviewWindow.setFrameSource(source)
        self.outputFrameSelect.setPtsTimeArray(source.pts_time)
        self.outputPreviewWindow.setFrameOffset(
            self.outputFrameSelect.slider.value())
        self.updateChildGeometry(self.size())

    def setInputFrame(self, n, t):
        self.inputPreviewWindow.setFrameOffset(n)

    def setOutputFrame(self, n, t):
        self.outputPreviewWindow.setFrameOffset(n)


class VFilterEdit(QSplitter):
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.previews = VFrameView(self)
        self.frameTable = FrameTable(self)
        self.addWidget(self.previews)
        self.addWidget(self.frameTable)
        self.setOrientation(Qt.Vertical)
        self.setStretchFactor(0, 0)
        self.setStretchFactor(1, 1)

        sm = self.frameTable.selectionModel()
        sm.currentChanged.connect(self.handleCurrentItemChanged)
        self.frameTable.contentsModified.connect(self.tableUpdated)

        self.previews.inputFrameSelect.frameSelectionChanged.connect(
            self.handleInputFrameSelectionChanged)
        self.previews.outputFrameSelect.frameSelectionChanged.connect(
            self.handleOutputFrameSelectionChanged)

    def gotoRow(self, n):
        self.frameTable.selectionModel().blockSignals(True)
        self.frameTable.goto(row=n)
        self.frameTable.selectionModel().blockSignals(False)

    def setInputSlider(self, n):
        self.previews.inputFrameSelect.blockSignals(True)
        self.previews.inputFrameSelect.slider.setValue(n)
        self.previews.inputFrameSelect.blockSignals(False)
        self.previews.setInputFrame(n, QTime())

    def setOutputSlider(self, n):
        self.previews.outputFrameSelect.blockSignals(True)
        self.previews.outputFrameSelect.slider.setValue(n)
        self.previews.outputFrameSelect.blockSignals(False)
        self.previews.setOutputFrame(n, QTime())

    @pyqtSlot(int, QTime)
    def handleInputFrameSelectionChanged(self, n, t):
        self.gotoRow(n)

        m = self.filters.cumulativeIndexMap[n]

        while m < 0 and n < len(self.filters.cumulativeIndexMap):
            n += 1
            m = self.filters.cumulativeIndexMap[n]

        if m >= 0:
            self.setOutputSlider(m)

        else:
            self.setOutputSlider(self.filters.framecount - 1)

        self.update()

    @pyqtSlot(int, QTime)
    def handleOutputFrameSelectionChanged(self, n, t):
        self.gotoRow(self.filters.cumulativeIndexReverseMap[n])
        self.setInputSlider(self.filters.cumulativeIndexReverseMap[n])
        self.update()

    @pyqtSlot(QModelIndex, QModelIndex)
    def handleCurrentItemChanged(self, new, old):
        n1 = old.data(Qt.UserRole)
        n2 = new.data(Qt.UserRole)

        if n2 is None:
            return

        if n1 != n2 and self.previews.inputFrameSelect.slider.value() != n2:
            self.setInputSlider(n2)

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

        if m1 != m2 and self.previews.outputFrameSelect.slider.value() != m2:
            self.setOutputSlider(m2)

    @pyqtSlot()
    def tableUpdated(self):
        n = self.frameTable.currentIndex().data(role=Qt.UserRole)

        if n is not None:
            m = self.filters.cumulativeIndexMap[n]

            while m < 0 and n < len(self.filters.cumulativeIndexMap):
                n += 1
                m = self.filters.cumulativeIndexMap[n]

            if m < 0:
                m = self.filters.cumulativeIndexMap[-1]

            self.previews.outputFrameSelect.blockSignals(True)
            self.previews.outputFrameSelect.setPtsTimeArray(
                self.filters.pts_time)
            self.previews.outputFrameSelect.blockSignals(False)

            self.setOutputSlider(m)

        self.contentsModified.emit()

    def setFilters(self, filters):
        self.filters = filters

        if filters is not None:
            self.previews.inputPreviewWindow.setFrameSource(filters.source)
            self.previews.inputPreviewWindow.setSar(filters.source.sar)
            self.previews.inputFrameSelect.setPtsTimeArray(
                filters.source.pts_time)

            self.previews.outputPreviewWindow.setFrameSource(filters)
            self.previews.outputPreviewWindow.setSar(filters.sar)
            self.previews.outputFrameSelect.setPtsTimeArray(filters.pts_time)

        else:
            self.previews.inputPreviewWindow.setFrameSource(None)
            self.previews.inputPreviewWindow.setSar(1)
            self.previews.inputFrameSelect.setPtsTimeArray(None)

            self.previews.outputPreviewWindow.setFrameSource(None)
            self.previews.outputPreviewWindow.setSar(1)
            self.previews.outputFrameSelect.setPtsTimeArray(None)

        self.frameTable.setFilters(filters)

        if filters is not None:
            self.frameTable.goto(0, 0)
            self.setInputSlider(0)
            self.setOutputSlider(0)


class QFilterChain(QFilterConfig):
    contentsModified = pyqtSignal()

    def createNewFilterInstance(self):
        return FilterChain()

    def _createControls(self, *args, **kwargs):
        self.sourceWidget = QWidget(self)
        self.sourceSelection = self.createSourceControl(self.sourceWidget)
        self.sourceSelection.currentDataChanged.connect(self.setFilterSource)

        srclayout = QHBoxLayout()
        srclayout.addWidget(QLabel("Source: ", self.sourceWidget))
        srclayout.addWidget(self.sourceSelection)

        self.sourceWidget.setLayout(srclayout)

        self.availableFilters = QAvailableFilters(self)
        self.availableFilters.setMaximumWidth(240)

        self.currentFilters = QCurrentFilters(self)
        self.currentFilters.setMaximumWidth(240)
        self.currentFilters.listView.contentsModified.connect(self.isModified)

        self.vFilterEdit = VFilterEdit(self)
        self.vFilterEdit.contentsModified.connect(self.isModified)

        self.vFilterEdit.hide()

        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(self.sourceWidget)

        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)

        self.filterlistlayout = QBoxLayout(QBoxLayout.LeftToRight)
        hlayout.addLayout(self.filterlistlayout)

        self.filterlistlayout.addWidget(self.availableFilters)
        self.filterlistlayout.addWidget(self.currentFilters)

        hlayout.addWidget(self.vFilterEdit)

        self._prepareDlgButtons()
        self.setVideoMode(False)

    def setVideoMode(self, flag):
        self.vFilterEdit.setVisible(bool(flag))

        try:
            self.currentFilters.listView.filterMoved.disconnect()

        except:
            pass

        try:
            self.currentFilters.listView.filterRemoved.disconnect()

        except:
            pass

        try:
            self.currentFilters.listView.filterInserted.disconnect()

        except:
            pass

        if flag:
            self.currentFilters.listView.filterMoved.connect(
                self.vFilterEdit.frameTable.handleFilterMoved)
            self.currentFilters.listView.filterRemoved.connect(
                self.vFilterEdit.frameTable.handleFilterRemoved)
            self.currentFilters.listView.filterInserted.connect(
                self.vFilterEdit.frameTable.handleFilterInserted)

            self.filterlistlayout.setDirection(QBoxLayout.TopToBottom)

        else:
            self.filterlistlayout.setDirection(QBoxLayout.LeftToRight)

    def _resetControls(self):
        self.currentFilters.listView.setFilters(self.shadow)

        if self.shadow.type == "video":
            self.vFilterEdit.setFilters(self.shadow)

        self.setVideoMode(self.shadow.type == "video")


