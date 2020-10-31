from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (QGridLayout, QHBoxLayout, QPushButton, QDialog, QWidget)
import abc
from transcode.containers.basereader import Track
from transcode.filters.base import FilterChain
from .qinputselection import QInputSelection


class QFilterConfig(QDialog):
    allowedtypes = ("video", "audio")
    settingsApplied = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._newconfig = False
        self.modified = False
        self._createControls()
        self.inputFiles = self.availableFilters = None
        self.setFilter(None)

    def newConfig(self):
        return self._newconfig

    def setNewConfig(self, value):
        self._newconfig = bool(value)

        if self.modified:
            self.isModified()

        else:
            self.notModified()

        self.applyBtn.setHidden(self._newconfig)

    def setFilter(self, filter=None, nocopy=False):
        if filter is not None:
            self.filter = filter

        else:
            self.filter = self.createNewFilterInstance()

        if hasattr(self, "applyBtn"):
            self.applyBtn.setHidden(filter is None)

        if nocopy:
            self.okayBtn.hide()
            self.applyBtn.hide()
            self.resetBtn.hide()
            self.closeBtn.setText("&Close")

        else:
            self.okayBtn.show()
            self.applyBtn.show()
            self.resetBtn.show()
            self.closeBtn.setText("&Cancel")

        self.reset(nocopy)

    def setSources(self, inputFiles, availableFilters):
        self.inputFiles = inputFiles
        self.availableFilters = availableFilters
        self._resetSourceModels()
        self._resetSourceControls()

    def setFilterPrev(self, source):
        self.shadow.prev = source
        self._prevChanged(source)

    def setFilterSource(self, source):
        if self.shadow.parent is None:
            self.shadow.source = source
            self.isModified()
            self._prevChanged(source)

    def _prevChanged(self, source):
        pass

    def reset(self, nocopy=False):
        if not nocopy:
            self.shadow = self.filter.copy()

            if isinstance(self.filter.parent, FilterChain):
                self.shadow.parent = self.filter.parent
                self.shadow.prev = self.filter.prev

            if self.shadow.prev is None and self.filter.prev is not None:
                self.shadow.prev = self.filter.prev
                self._prevChanged(self.shadow.prev)

        else:
            self.shadow = self.filter

        self._resetSourceControls()
        self._resetControls()

        self.notModified()

    def _resetSourceModels(self):
        if hasattr(self, "sourceSelection") and \
                isinstance(self.sourceSelection, QInputSelection):
            self._resetSourceModel(self.sourceSelection)

    def _resetSourceModel(self, sourceSelection):
        sourceSelection.setSources(self.inputFiles, self.availableFilters)

    def _showSourceControls(self, value):
        if hasattr(self, "sourceWidget") and isinstance(self.sourceWidget, QWidget):
            self.sourceWidget.setHidden(not value)

    def _resetSourceControls(self):
        self._showSourceControls(self.inputFiles or self.availableFilters)

        if hasattr(self, "sourceSelection") and isinstance(self.sourceSelection, QInputSelection):
            self._setSourceSelection(self.sourceSelection, self.shadow.source)

    def _setSourceSelection(self, sourceSelection, source):
        if isinstance(source, Track) and self.inputFiles and \
                source.container in self.inputFiles:

            file_index = self.inputFiles.index(source.container)
            track_index = source.track_index
            index = sourceSelection.model().index(1, 0).child(
                file_index, 0).child(track_index, 0)

        elif self.availableFilters and source in self.availableFilters:
            filter_index = self.availableFilters.index(source)
            index = sourceSelection.model().index(2, 0).child(filter_index, 0)

        elif source is None:
            index = sourceSelection.model().index(0, 0)

        else:
            return

        sourceSelection.blockSignals(True)
        sourceSelection.setCurrentIndex(index)
        sourceSelection.blockSignals(False)

    @abc.abstractmethod
    def _createControls(self):
        raise NotImplementedError

    @abc.abstractmethod
    def createNewFilterInstance(self):
        """Creates a new instance of the filter."""
        raise NotImplementedError

    @abc.abstractmethod
    def _resetControls(self):
        """Abstract method that sets all controls in dialog as needed."""
        raise NotImplementedError

    def createSourceControl(self, parent=None):
        selection = QInputSelection(parent)
        selection.setSelectFunc(self.isValidSource)
        return selection

    def isValidSource(self, other):
        return hasattr(other, "type") and other.type in self.allowedtypes and \
            (isinstance(other, Track) or self.filter not in other.dependencies)

    def apply(self):
        if self.shadow is not self.filter:
            cls, args, *more = self.shadow.__reduce__()

            if len(more) == 0:
                return

            state, *more = more

            if len(more):
                items, *more = more

            else:
                items = None

            if len(more):
                dictitems, *more = more

            else:
                dictitems = None

            self.filter.__setstate__(state)

            if items is not None or dictitems is not None:
                self.filter.clear()

            if items is not None:
                self.filter.extend(items)

            if dictitems is not None:
                self.filter.extend(dictitems)

            self.settingsApplied.emit()

        self.notModified()

    def applyAndClose(self):
        self.apply()
        self.done(1)

    def _prepareDlgButtons(self, layout=None, index=None, layoutcls=QHBoxLayout):
        if layout is None:
            layout = self.layout()

        self.okayBtn = QPushButton("&OK", self)
        self.okayBtn.setDefault(True)
        self.okayBtn.clicked.connect(self.applyAndClose)

        self.applyBtn = QPushButton("&Apply", self)
        self.applyBtn.clicked.connect(self.apply)

        self.resetBtn = QPushButton("&Reset", self)
        self.resetBtn.clicked.connect(self.reset)

        self.closeBtn = QPushButton("&Close", self)
        self.closeBtn.clicked.connect(self.close)

        sublayout = layoutcls()
        sublayout.addStretch()
        sublayout.addWidget(self.okayBtn)
        sublayout.addWidget(self.applyBtn)
        sublayout.addWidget(self.resetBtn)
        sublayout.addWidget(self.closeBtn)

        if isinstance(layout, QGridLayout):
            layout.addLayout(sublayout, *index)

        elif index is not None:
            layout.insertLayout(index, sublayout)

        else:
            layout.addLayout(sublayout)

    def isModified(self):
        if self.shadow is self.filter:
            self.settingsApplied.emit()

        else:
            self.closeBtn.setText("&Cancel")

        self.okayBtn.setEnabled(True)
        self.applyBtn.setEnabled(True)
        self.resetBtn.setEnabled(True)
        self.modified = True

    def notModified(self):
        self.modified = False

        if self._newconfig:
            self.closeBtn.setText("&Cancel")

        else:
            self.closeBtn.setText("&Close")

        self.okayBtn.setEnabled(self._newconfig)
        self.applyBtn.setEnabled(False)
        self.resetBtn.setEnabled(False)
