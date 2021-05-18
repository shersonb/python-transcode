from .qframetable import FrameTable
from .qimageview import QMultiImageView
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QBoxLayout,
                             QMenu, QAction, QFileDialog, QGridLayout, QLabel,
                             QSplitter)
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QModelIndex, Qt, QTime
from PyQt5.QtGui import QFont
from .qitemmodel import QItemModel, Node, ChildNodes, NoChildren
from transcode.filters.video import filters
from transcode.filters.video.base import BaseVideoFilter
from transcode.filters.base import BaseFilter, FilterChain
from transcode.config.ebml.filterchains import (FilterChainElement,
                                                FilterChains)
from transcode.config.obj import FilterList
from .qfilterconfig import QFilterConfig
from .qframeselect import QFrameSelect
import sys
from fractions import Fraction as QQ
from .qavailablefilters import QAvailableFilters
from .treeview import TreeView as QTreeView
from functools import partial
from copy import deepcopy


class CurrentFiltersModel(QItemModel):
    def canDragItems(self, *args):
        return True

    def canDropItems(self, items, action, row, column, parent):
        if action == Qt.CopyAction:
            for item in items:
                if not (isinstance(item.value, type)
                        and issubclass(item.value, BaseVideoFilter)):
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
                    dlg.setNewConfig(True)

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

    def contextmenu(self, index, obj):
        return partial(self.createContextMenu, obj=obj, index=index)

    def createContextMenu(self, table, index, obj):
        menu = QMenu(table)
        selected = table.selectedIndexes()
        current = table.currentIndex()
        filters = [item.data(Qt.UserRole) for item in selected]
        filter = current.data(Qt.UserRole)

        configurefilter = QAction(
            "Configure Filter...", table,
            triggered=partial(table.configureFilter, filter))

        configurefilter.setDisabled(isinstance(
            filter, BaseFilter) and filter.hasQtDlg())

        importfilters = QAction(
            "Import Filter(s)...", table, triggered=table.importFilters)

        exportfilters = QAction(
            "Export Selected Filter(s)...", table,
            triggered=partial(table.exportFilters, filters))

        exportfilters.setEnabled(len(filters) > 0)

        exportfilterchain = QAction("Export Filterchain...",
                                    table, triggered=table.exportFilterChain)

        menu.addAction(configurefilter)
        menu.addAction(importfilters)
        menu.addAction(exportfilters)
        menu.addAction(exportfilterchain)

        delete = QAction("Delete selected...",
                         table, triggered=partial(table.askDeleteSelected))

        if len(selected) == 0:
            delete.setDisabled(True)

        menu.addAction(delete)

        return menu


class CurrentFiltersListView(QTreeView):
    contentsModified = pyqtSignal()
    filterMoved = pyqtSignal(int, int)
    filterInserted = pyqtSignal(int)
    filterRemoved = pyqtSignal(int)
    _deletetitle = "Delete filters"
    _deletemsg = ("Do you wish to delete the selected filters? All encoder"
                  " and settings associated with selected filters"
                  " will be lost!")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragEnabled(True)
        self.setDragDropMode(QTreeView.DragDrop)
        self.setAcceptDrops(True)
        self.setIndentation(0)
        self.setHeaderHidden(True)
        self.setSelectionBehavior(QTreeView.SelectRows)
        self.setFilters(None)

    def setFilters(self, filters):
        self.filters = filters

        if filters is not None:
            root = CurrentFiltersRoot(filters)
            model = CurrentFiltersModel(root, [CurrentFiltersCol()])
            self.setModel(model)
            # model.dataChanged.connect(self.contentsModified)
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

    def mouseDoubleClickEvent(self, event):
        idx = self.indexAt(event.pos())
        filter = idx.data(Qt.UserRole)
        self.configureFilter(filter)

    def configureFilter(self, filter):
        if hasattr(filter, "QtDlg") and callable(filter.QtDlg):
            try:
                dlg = filter.QtDlg()
                dlg.settingsApplied.connect(self.contentsModified)
                dlg.exec_()

            except Exception:
                self._handleException(*sys.exc_info())

    def exportFilters(self, filters):
        fl = FilterList(deepcopy(filters))
        filefilters = ("Filters (*.filters *.filters.gz "
                       "*.filters.bz2 *.filters.xz)")

        defaultname = "untitled.filters.xz"
        fileName, _ = QFileDialog.getSaveFileName(self, "Save File",
                                                  defaultname, filefilters)

        if fileName:
            try:
                FilterChains.save(fl, fileName)

            except Exception:
                self._handleException(*sys.exc_info())

    def exportFilterChain(self):
        filefilters = ("Filterchains (*.filterchain *.filterchain.gz "
                       "*.filterchain.bz2 *.filterchain.xz)")

        defaultname = "untitled.filterchain.xz"
        fileName, _ = QFileDialog.getSaveFileName(self, "Save File",
                                                  defaultname, filefilters)

        if fileName:
            try:
                FilterChainElement.save(self.filters, fileName)

            except Exception:
                self._handleException(*sys.exc_info())

    def importFilters(self):
        model = self.model()
        filefilters = ("Filters (*.filters *.filters.gz "
                       "*.filters.bz2 *.filters.xz)")

        defaultname = "untitled.filters.xz"
        fileName, _ = QFileDialog.getOpenFileName(self, "Save File",
                                                  defaultname, filefilters)

        if fileName:
            try:
                filters = FilterChains.load(fileName)

            except Exception:
                self._handleException(*sys.exc_info())

            for filter in filters:
                model.appendRow(filter, QModelIndex())


class QCurrentFilters(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        label = QLabel("Current Filters", self)
        label.setFont(QFont("DejaVu Serif", 14, QFont.Bold, italic=True))
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
        if (self.inputPreviewWindow.framesource is not None
                and self.outputPreviewWindow.framesource is not None):
            inputDar = self.inputPreviewWindow.dar
            outputDar = self.outputPreviewWindow.dar

            if (isinstance(inputDar, (QQ, int))
                    and isinstance(outputDar, (QQ, int))):
                ratio = QQ(inputDar, outputDar)
                self.layout().setColumnStretch(0, ratio.numerator)
                self.layout().setColumnStretch(1, ratio.denominator)

            else:
                ratio = inputDar/outputDar
                self.layout().setColumnStretch(0, int(1000*ratio))
                self.layout().setColumnStretch(1, 1000)

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
            self.previews.inputPreviewWindow.setFrameSource(filters.prev)
            self.previews.inputPreviewWindow.setSar(filters.prev.sar)
            self.previews.inputFrameSelect.setPtsTimeArray(
                filters.prev.pts_time)

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
        self.setWindowTitle("Configure Filter Chain")
        self.sourceWidget = QWidget(self)
        self.sourceSelection = self.createSourceControl(self.sourceWidget)
        self.sourceSelection.currentDataChanged.connect(self.setFilterSource)

        srclayout = QHBoxLayout()
        srclayout.addWidget(QLabel("Source: ", self.sourceWidget))
        srclayout.addWidget(self.sourceSelection)

        self.sourceWidget.setLayout(srclayout)

        self.availableFilters = QAvailableFilters(self)
        self.availableFilters.setAvailableFilters(filters.values())
        self.availableFilters.setMaximumWidth(240)

        self.currentFilters = QCurrentFilters(self)
        self.currentFilters.setMaximumWidth(240)
        self.currentFilters.listView.contentsModified.connect(self.isModified)

        self.vFilterEdit = VFilterEdit(self)
        self.vFilterEdit.contentsModified.connect(
            self.currentFilters.listView.viewport().update)
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

        except Exception:
            pass

        try:
            self.currentFilters.listView.filterRemoved.disconnect()

        except Exception:
            pass

        try:
            self.currentFilters.listView.filterInserted.disconnect()

        except Exception:
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
        self.currentFilters.listView.setFilters(self.filtercopy)

        if self.filtercopy.type == "video":
            self.vFilterEdit.setFilters(self.filtercopy)

        self.setVideoMode(self.filtercopy.type == "video")
