from transcode.pyqtgui.qinputtracklist import FileTrackCol, LanguageCol, InputFmtCol
from transcode.pyqtgui.qfilterlist import FilterNameCol, SourceCol, FormatCol
from transcode.pyqtgui.qinputselection import InputSelectionRoot, ColumnUnion
from transcode.pyqtgui.qitemmodel import Node, ChildNodes, NoChildren, QItemModel
from transcode.pyqtgui.qfilterconfig import QFilterConfig
from transcode.pyqtgui.qframeselect import QFrameSelect
from transcode.pyqtgui.qimageview import QImageView
from PyQt5.QtWidgets import (QVBoxLayout, QTreeView, QLabel, QSplitter, QWidget, QMessageBox,
                             QMenu, QAction)
from transcode.pyqtgui.treeview import TreeView as QTreeView
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, pyqtSignal, pyqtBoundSignal, QTime
from transcode.containers.basereader import Track
from . import Concatenate
from ..base import BaseFilter, FilterChain
from copy import copy
from functools import partial


class SegmentsRoot(Node):
    def _wrapChildren(self, children):
        return SegmentsList.fromValues(children, self)

    def canDropChildren(self, model, parent, items, row, action):
        if action == Qt.CopyAction:
            for item in items:
                if not isinstance(item.value, (Track, BaseFilter)):
                    return False

        elif action == Qt.MoveAction:
            for item in items:
                if item not in self.children:
                    return False

        return True

    def dropChildren(self, model, parent, items, row, action):
        if action == Qt.CopyAction:
            for k, item in enumerate(items, row):
                model.insertRow(k, item.value, parent)

        elif action == Qt.MoveAction:
            j = 0

            for k, item in enumerate(items, row):
                old_row = self.children.index(item)
                model.moveRow(old_row, k - j, parent)

                if old_row < row:
                    j += 1

        return True

    def canDropItems(self, model, parent, items, action):
        return self.canDropChildren(model, parent, items, len(self.children), action)

    def dropItems(self, model, parent, items, action):
        return self.dropChildren(model, parent, items, len(self.children), action)


class SegmentsList(ChildNodes):
    @staticmethod
    def _wrap(item):
        return SegmentNode(item)

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


class SegmentNode(NoChildren):
    pass


class SourcesModel(QItemModel):
    def supportedDragActions(self):
        return Qt.CopyAction


class SegmentsModel(QItemModel):
    def supportedDragActions(self):
        return Qt.MoveAction

    def supportedDropActions(self):
        return Qt.MoveAction | Qt.CopyAction


class BaseColumn(object):
    flags = Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsEnabled

    def __init__(self, input_files, available_filters, filter):
        self.input_files = input_files
        self.available_filters = available_filters
        self.filter = filter

    def contextmenu(self, index, obj):
        return partial(self.createContextMenu, obj=obj, index=index)

    def createContextMenu(self, table, index, obj):
        menu = QMenu(table)

        editfilter = QAction(f"Configure filter...", table,
                             triggered=partial(self.configureFilter, obj, table))

        editfilter.setEnabled(obj.hasQtDlg())

        menu.addAction(editfilter)

        return menu

    def configureFilter(self, filter, parent=None):
        dlg = filter.QtDlg(parent)
        dlg.setSources(self.input_files, self.available_filters)

        if hasattr(parent, "contentsModified") and isinstance(parent.contentsModified, pyqtBoundSignal):
            dlg.settingsApplied.connect(parent.contentsModified)

        dlg.exec_()


class NameCol(BaseColumn):
    width = 256
    headerdisplay = "Segment"

    def display(self, index, obj):
        segment_index = list(self.filter).index(obj)
        
        if isinstance(obj, Track) and obj.container in self.input_files:
            container_index = self.input_files.index(obj.container)
            return f"{segment_index}: input:{container_index}:{obj.track_index}"

        if self.available_filters is not None and obj in self.available_filters:
            filter_index = self.available_filters.index(obj)
            return f"{segment_index}: filter:{filter_index}"


class DurationCol(BaseColumn):
    width = 128
    headerdisplay = "Duration"

    def display(self, index, obj):
        m, s = divmod(float(obj.duration), 60)
        h, m = divmod(int(m), 60)
        return f"{h}:{m:02d}:{s:012.9f}"


class StartCol(BaseColumn):
    width = 128
    headerdisplay = "Start Time"

    def display(self, index, obj):
        k = index.row()
        t = sum(segment.duration for segment in list(self.filter)[:k])
        m, s = divmod(t, 60)
        h, m = divmod(int(m), 60)
        return f"{h}:{m:02d}:{s:012.9f}"


class EndCol(BaseColumn):
    width = 128
    headerdisplay = "End Time"

    def display(self, index, obj):
        k = index.row()
        t = sum(segment.duration for segment in list(self.filter)[:k+1])
        m, s = divmod(float(t), 60)
        h, m = divmod(int(m), 60)
        return f"{h}:{m:02d}:{s:012.9f}"


class QSegmentTree(QTreeView):
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setSelectionMode(QTreeView.ExtendedSelection)
        #self.contentsModified.connect(self._handleContentsModified)

    #def _handleContentsModified(self):
        #self.model().root.value.reset_cache()

    def contextMenuEvent(self, event):
        selected = self.currentIndex()
        menu = self.model().data(selected, role=Qt.UserRole + 1)

        if callable(menu):
            menu = menu(self)

        if isinstance(menu, QMenu):
            menu.exec_(self.mapToGlobal(event.pos()))

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


class QVideoPreview(QWidget):
    frameChanged = pyqtSignal(int, QTime)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.imageView = QImageView(self)
        self.frameSelection = QFrameSelect(self)
        self.frameSelection.frameSelectionChanged.connect(self.updateImage)
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(self.imageView)
        layout.addWidget(self.frameSelection)

    def setSource(self, source):
        self._source = source
        self.frameSelection.setPtsTimeArray(source.pts_time)
        self.setFrameIndex(0)
        s, ms = divmod(int(1000*source.pts_time[0]), 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        self.updateImage(0, QTime(h, m, s, ms))

    def setFrameIndex(self, value):
        self.frameSelection.slider.setValue(value)

    def updateImage(self, n, t):
        try:
            frame = next(self._source.iterFrames(n, whence="framenumber"))

        except:
            return

        self.imageView.setFrame(frame.to_image().toqpixmap())
        self.frameChanged.emit(n, t)


class QConcatenate(QFilterConfig):
    def createNewFilterInstance(self):
        return Concatenate()

    def _createControls(self):
        self.setMinimumWidth(720)
        layout = QVBoxLayout()
        #layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.outersplitter = QSplitter(Qt.Vertical, self)
        layout.addWidget(self.outersplitter)

        self.innersplitter = QSplitter(Qt.Vertical, self.outersplitter)
        self.outersplitter.addWidget(self.innersplitter)

        col1 = QWidget(self.innersplitter)
        col2 = QWidget(self.innersplitter)

        vlayout1 = QVBoxLayout()
        vlayout1.setContentsMargins(0, 16, 0, 0)
        col1.setLayout(vlayout1)

        vlayout2 = QVBoxLayout()
        vlayout2.setContentsMargins(0, 16, 0, 0)
        col2.setLayout(vlayout2)

        self.innersplitter.addWidget(col1)
        self.innersplitter.addWidget(col2)

        self.sourcesLabel = QLabel("Sources", self)
        self.sourcesLabel.setFont(
            QFont("DejaVu Serif", 18, QFont.Bold, italic=True))
        self.sourcesList = QTreeView(self)
        self.sourcesList.setDragEnabled(True)
        self.sourcesList.setSelectionMode(QTreeView.ExtendedSelection)

        vlayout1.addWidget(self.sourcesLabel)
        vlayout1.addWidget(self.sourcesList)

        self.segmentsLabel = QLabel("Segments", self)
        self.segmentsLabel.setFont(
            QFont("DejaVu Serif", 18, QFont.Bold, italic=True))
        self.segmentsList = QSegmentTree(self)
        self.segmentsList.contentsModified.connect(self.isModified)

        vlayout2.addWidget(self.segmentsLabel)
        vlayout2.addWidget(self.segmentsList)

        self.preview = QVideoPreview(self.outersplitter)
        self.outersplitter.addWidget(self.preview)

        self._prepareDlgButtons()

    def _resetSourceModels(self):
        if self.inputFiles is not None:
            self.cols = [
                ColumnUnion("Input",
                            FileTrackCol(self.inputFiles), FilterNameCol(
                                self.availableFilters),
                            width=256),
                ColumnUnion("Language",
                            LanguageCol(self.inputFiles), None, width=96),
                ColumnUnion("Source",
                            None, SourceCol(self.availableFilters), width=96),
                ColumnUnion("Format",
                            InputFmtCol(self.inputFiles), FormatCol(self.availableFilters), width=128),
            ]

            if self.availableFilters:
                root = InputSelectionRoot(
                    [self.inputFiles, self.availableFilters])

            else:
                root = InputSelectionRoot([self.inputFiles])

            model = SourcesModel(root, self.cols)
            self.sourcesList.setModel(model)

            for k, col in enumerate(self.cols):
                if hasattr(col, "width"):
                    self.sourcesList.setColumnWidth(k, col.width)

                col.selectfunc = self.isValidSource

            self.sourcesList.expandAll()

        else:
            self.sourcesList.setModel(QItemModel(Node(None), []))

        self._resetConcatModel()

    def _resetControls(self):
        self._resetConcatModel()

        if self.filtercopy.type == "video":
            self.preview.setSource(self.filtercopy)
            self.preview.show()
            self.innersplitter.setOrientation(Qt.Horizontal)

        else:
            self.preview.hide()
            self.innersplitter.setOrientation(Qt.Vertical)

    def _resetConcatModel(self):
        root = SegmentsRoot(self.filtercopy)

        cols = [
            NameCol(self.inputFiles, self.availableFilters, self.filtercopy),
            DurationCol(self.inputFiles, self.availableFilters, self.filtercopy),
            StartCol(self.inputFiles, self.availableFilters, self.filtercopy),
            EndCol(self.inputFiles, self.availableFilters, self.filtercopy)
        ]

        model = SegmentsModel(root, cols)
        self.segmentsList.setModel(model)
        model.rowsRemoved.connect(self._handleSegmentsRemoved)
        model.rowsMoved.connect(self._handleSegmentsMoved)
        model.rowsInserted.connect(self._handleSegmentsInserted)
        self.segmentsList.selectionModel().currentChanged.connect(self._handleCurrentIndexChanged)

        #for k, col in enumerate(cols):
            #if hasattr(col, "width"):
                #self.segmentsList.setColumnWidth(k, col.width)

        self.segmentsList.expandAll()

    def _handleCurrentIndexChanged(self, current, previous):
        if self.filtercopy.type == "video":
            try:
                k = sum(segment.framecount for segment in self.filtercopy[:current.row()])

            except:
                return

            self.segmentsList.selectionModel().blockSignals(True)
            self.preview.frameSelection.slider.setValue(k)
            self.segmentsList.selectionModel().blockSignals(False)
            self.segmentsList.update()

    def _handleSegmentsRemoved(self, parent, first, last):
        if self.filtercopy.type == "video":
            k = self.preview.frameSelection.slider.value()
            self.preview.frameSelection.blockSignals(True)
            self.preview.frameSelection.setPtsTimeArray(self.filtercopy.pts_time)

            try:
                framesBeforeRemoval = sum(segment.framecount for segment in self.filtercopy[:first])
                framesRemoved = self.preview.frameSelection.slider.maximum() + 1 - self.filtercopy.framecount

                if framesBeforeRemoval <= k < framesBeforeRemoval + framesRemoved:
                    self.preview.frameSelection.blockSignals(False)
                    self.preview.frameSelection.slider.setValue(k + framesInserted)

                elif k >= framesBeforeRemoval + framesRemoved:
                    self.preview.frameSelection.slider.setValue(k - framesRemoved)

            except:
                pass

            finally:
                self.preview.frameSelection.blockSignals(False)

    def _handleSegmentsMoved(self, parent, first, last, dest, row):
        # Notice: first, last, and row indicate OLD offsets, but we are looking at the segments AFTER the swap.
        if first > row:
            # Swapping [row, row+1, ..., first-1] with [first, first+1, ..., last]...
            # is equivalent to...
            return self._handleSegmentsMoved(parent, row, first - 1, dest, last+1)

        # Swapping [first, first+1, ..., last] with [last+1, last+2, ..., row-1]

        if self.filtercopy.type == "video":
            k = self.preview.frameSelection.slider.value()
            self.preview.frameSelection.blockSignals(True)
            self.preview.frameSelection.setPtsTimeArray(self.filtercopy.pts_time)
            segmentsMoved = last - first + 1

            try:
                framesMoved = sum(segment.framecount for segment in self.filtercopy[row - segmentsMoved:row])
                framesBeforeInsertion = sum(segment.framecount for segment in self.filtercopy[:row - segmentsMoved])
                framesBeforeMoved = sum(segment.framecount for segment in self.filtercopy[:first])

                if framesBeforeMoved <= k < framesBeforeMoved + framesMoved:
                    self.preview.frameSelection.slider.setValue(k + framesBeforeInsertion - framesBeforeMoved)

                elif framesBeforeMoved + framesMoved <= k < framesBeforeInsertion + framesMoved:
                    self.preview.frameSelection.slider.setValue(k - framesMoved)

            except:
                pass

            finally:
                self.preview.frameSelection.blockSignals(False)

    def _handleSegmentsInserted(self, parent, first, last):
        if self.filtercopy.type == "video":
            k = self.preview.frameSelection.slider.value()
            self.preview.frameSelection.blockSignals(True)
            self.preview.frameSelection.setPtsTimeArray(self.filtercopy.pts_time)

            try:
                try:
                    framesBeforeInsertion = sum(segment.framecount for segment in self.filtercopy[:first])
                    framesInserted = sum(segment.framecount for segment in self.filtercopy[first:last+1])

                except:
                    return

                if k >= framesBeforeInsertion:
                    self.preview.frameSelection.slider.setValue(k + framesInserted)

            finally:
                self.preview.frameSelection.blockSignals(False)

    def reset(self, nocopy=False):
        if not nocopy:
            self.filtercopy = self.filter.copy()

        else:
            self.filtercopy = self.filter

        self._resetSourceControls()
        self._resetControls()

        self.notModified()

    def isValidSource(self, other):
        if isinstance(other, BaseFilter) and (self.filter in other.dependencies or self.filter is other):
            return False

        if len(self.filtercopy):
            first = self.filtercopy[0]

            if first.type != other.type:
                return False

            if first.type == "video":
                return (other.width, other.height) == (first.width, first.height)

            elif first.type == "audio":
                return (other.rate, other.channels) == (first.rate, first.channels)

            return (other.codec) == (first.codec)

        return True
