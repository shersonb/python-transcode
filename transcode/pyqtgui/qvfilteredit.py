from .qframetable import FrameTable
from .qimageview import QMultiImageView
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QSpinBox, QLabel, QDialog, QPushButton
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QModelIndex, Qt
from transcode.objwrapper import Collection, ObjectWrapper

class VFilterEdit(QWidget):
    settingsApplied = pyqtSignal()

    def __init__(self, filters, *args, **kwargs):
        super(QWidget, self).__init__(*args, **kwargs)
        self.filters = filters

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        self.inputPreviewWindow = QMultiImageView(self)
        self.inputPreviewWindow.setFrameSource(filters.src)
        self.inputPreviewWindow.setSar(filters.src.sar)

        self.outputPreviewWindow = QMultiImageView(self)
        self.outputPreviewWindow.setFrameSource(filters)
        self.outputPreviewWindow.setSar(filters.sar)

        previewWindowLayout = QHBoxLayout()
        previewWindowLayout.setContentsMargins(0, 0, 0, 0)
        previewWindowLayout.setSpacing(8)
        previewWindowLayout.addWidget(self.inputPreviewWindow)
        previewWindowLayout.addWidget(self.outputPreviewWindow)
        previewWindowLayout.addStretch()

        editLayout = QHBoxLayout()
        editLayout.setContentsMargins(0, 0, 0, 0)
        editLayout.setSpacing(4)

        self.frameTable = FrameTable(filters, self)
        sm = self.frameTable.selectionModel()
        sm.currentChanged.connect(self.currentItemChanged)
        tm = self.frameTable.model()
        tm.dataChanged.connect(self.tableUpdated)

        editLayout.addWidget(self.frameTable)

        self.oldFrameIndex = QSpinBox(self)
        self.oldFrameIndex.setMaximum(filters.src.framecount - 1)
        self.oldFrameIndex.editingFinished.connect(self.scrollToOld)
        self.newFrameIndex = QSpinBox(self)
        self.newFrameIndex.setMaximum(filters.framecount - 1)
        self.newFrameIndex.editingFinished.connect(self.scrollToNew)

        gotoOldLayout = QHBoxLayout()
        gotoOldLayout.setContentsMargins(0, 0, 0, 0)
        gotoOldLayout.setSpacing(4)
        gotoOldLayout.addWidget(QLabel("Old #", self))
        gotoOldLayout.addWidget(self.oldFrameIndex)

        gotoNewLayout = QHBoxLayout()
        gotoNewLayout.setContentsMargins(0, 0, 0, 0)
        gotoNewLayout.setSpacing(4)
        gotoNewLayout.addWidget(QLabel("New #", self))
        gotoNewLayout.addWidget(self.newFrameIndex)

        gotoLayout = QVBoxLayout()
        gotoLayout.setContentsMargins(0, 0, 0, 0)
        gotoLayout.setSpacing(4)
        gotoLayout.addLayout(gotoOldLayout)
        gotoLayout.addLayout(gotoNewLayout)
        gotoLayout.addStretch()

        editLayout.addLayout(gotoLayout)

        layout.addLayout(previewWindowLayout)
        layout.addLayout(editLayout)

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
        #self.updateChildGeometry()
        n = self.frameTable.currentIndex().data(role=Qt.UserRole)
        m = self.filters.cumulativeIndexMap[n]

        while m < 0:
            n += 1
            m = self.filters.cumulativeIndexMap[n]

        self.outputPreviewWindow.setFrameOffset(m)
        self.settingsApplied.emit()


class VFilterEditDlg(QDialog):
    def __init__(self, filters, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if isinstance(filters, ObjectWrapper):
            self._collection = Collection(prev=filters.__collection__)

        else:
            self._collection = Collection()

        #self.filters = self._collection.wrap_obj(filters)
        self.filters = filters

        layout = QVBoxLayout()
        self.setLayout(layout)
        self.editor = VFilterEdit(self.filters, self)
        self.editor.settingsApplied.connect(self.isModified)
        layout.addWidget(self.editor)
        btnlayout = QHBoxLayout()
        layout.addLayout(btnlayout)
        self.okayBtn = QPushButton("&Okay", self)
        self.applyBtn = QPushButton("&Apply", self)
        self.resetBtn = QPushButton("&Reset", self)
        self.closeBtn = QPushButton("&Close", self)

        self.okayBtn.clicked.connect(self.applyAndClose)
        self.applyBtn.clicked.connect(self.apply)
        self.resetBtn.clicked.connect(self.reset)
        self.closeBtn.clicked.connect(self.close)

        btnlayout.addStretch()
        btnlayout.addWidget(self.okayBtn)
        btnlayout.addWidget(self.applyBtn)
        btnlayout.addWidget(self.resetBtn)
        btnlayout.addWidget(self.closeBtn)
        self.notModified()

    def isModified(self):
        self.modified = True
        self.closeBtn.setText("&Cancel")
        self.okayBtn.setDisabled(False)
        self.resetBtn.setDisabled(False)
        self.applyBtn.setDisabled(False)

    def notModified(self):
        self.modified = False
        self.closeBtn.setText("&Close")
        self.okayBtn.setDisabled(True)
        self.resetBtn.setDisabled(True)
        self.applyBtn.setDisabled(True)

    @pyqtSlot()
    def show(self):
        if self.parent() is not None:
            self.parent().setDisabled(True)

        QDialog.show(self)

    @pyqtSlot()
    def applyAndClose(self):
        self.apply()
        self.close()

    @pyqtSlot()
    def apply(self):
        self.done(1)
        self._collection.commit()
        #self.settingsApplied.emit()
        self.notModified()

    @pyqtSlot()
    def reset(self):
        self._collection.reset()
        tm = self.editor.frameTable.model().sourceModel()
        idx1 = tm.index(0, 0)
        idx2 = tm.index(tm.rowCount() - 1, tm.columnCount() - 1)
        tm.dataChanged.emit(idx1, idx2)
        self.notModified()

    @pyqtSlot()
    def close(self):
        if self.parent() is not None:
            self.parent().setEnabled(True)

        QDialog.close(self)

