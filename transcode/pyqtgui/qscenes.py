from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt, QObject, QPoint
from PyQt5.QtWidgets import (QAction, QAbstractItemView, QProgressDialog, QMessageBox,
                             QCheckBox, QComboBox)
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtGui import QRegExpValidator

from functools import partial
from numpy import isnan, arange, array

from .qzones import ZoneDlg
from transcode.filters.video.base import BaseVideoFilter
from transcode.filters.video.scenes import Scenes, AnalysisThread
from transcode.filters.base import BaseFilter
from transcode.containers.basewriter import Track
from .qframetablecolumn import ZoneCol
from more_itertools import windowed


class QScenes(ZoneDlg):
    zonename = "Scene"
    title = "Scene Editor"

    def createNewFilterInstance(self):
        return Scenes()

    def _createModeBox(self):
        self.modeBox = comboBox = QComboBox(self)
        comboBox.addItem("Input", 1)
        self._mode = 1

    def _createGlobalControls(self, layout=None, index=None):
        if layout is None:
            layout = self.layout()

        self.fixPtsCheckBox = QCheckBox(
            "Fix PTS times (for variable frame rate video)", self)
        self.fixPtsCheckBox.stateChanged.connect(self.toggleFixPts)
        layout.addWidget(self.fixPtsCheckBox)

    def _resetGlobalControls(self):
        self.fixPtsCheckBox.blockSignals(True)
        self.fixPtsCheckBox.setCheckState(2 if self.shadow.fixpts else 0)
        self.fixPtsCheckBox.blockSignals(False)

    def toggleFixPts(self, checkstate):
        if checkstate == Qt.Checked:
            self.shadow.fixpts = 1

        else:
            self.shadow.fixpts = 0

        self.isModified()


class BaseSceneCol(ZoneCol, QObject):
    analysisstarted = pyqtSignal()
    analysisprogress = pyqtSignal(int)
    analysisended = pyqtSignal()
    textalign = Qt.AlignRight | Qt.AlignVCenter
    bgcolor = QColor(128, 255, 128)
    bgcoloralt = QColor(255, 255, 255)
    fgcolor = QColor(0, 0, 0)
    fgcoloralt = QColor(160, 160, 160)
    width = 72
    progress = None

    def __init__(self, filter, *args, **kwargs):
        ZoneCol.__init__(self, filter, "scene")
        QObject.__init__(self, *args, **kwargs)

    def scrollTableToZone(self, table, zone):
        filtermodel = table.model()
        currentIndex = table.currentIndex()
        datamodel = filtermodel.sourceModel()
        col = filtermodel.mapToSource(currentIndex).column()
        newIndex = datamodel.index(zone.src_start, col)

        if isinstance(filtermodel.filterFunc(), set):
            self.setFilter(
                table, filtermodel.filterFunc().union({zone.src_start}))

        elif filtermodel.filterFunc() is not None:
            self.setFilter(table, None)

        newFilterIndex = filtermodel.mapFromSource(newIndex)
        table.setCurrentIndex(newFilterIndex)
        table.scrollTo(newFilterIndex, QAbstractItemView.PositionAtCenter)

    def createContextMenu(self, table, index, obj):
        menu = ZoneCol.createContextMenu(self, table, index, obj)
        menu.addSeparator()

        checkallselected = QAction("&Check all selected", table,
                                   triggered=partial(self.checkSelected, table=table, check=True))
        uncheckallselected = QAction("&Uncheck all selected", table,
                                     triggered=partial(self.checkSelected, table=table, check=False))

        menu.addAction(checkallselected)
        menu.addAction(uncheckallselected)
        menu.addSeparator()

        idx = table.indexAt(QPoint(0, 0))

        j = table.model().data(idx, Qt.UserRole)

        if not isinstance(self.filter.prev, Track):
            while self.filter.prev.cumulativeIndexMap[j] < 0:
                j += 1

        idx = table.indexAt(QPoint(0, table.height()-1))
        k = idx.data(Qt.UserRole)

        if k is None:
            k = len(self.filter.prev.cumulativeIndexMap)

        elif not isinstance(self.filter.prev, Track):
            while self.filter.prev.cumulativeIndexMap[k] < 0:
                k -= 1

        if not isinstance(self.filter.prev, Track):
            start = max(0, self.filter.prev.cumulativeIndexMap[j] - 1)

            if k >= len(self.filter.prev.cumulativeIndexMap):
                end = self.filter.prev.framecount

            else:
                end = min(
                    self.filter.prev.cumulativeIndexMap[k], self.filter.prev.framecount)

        else:
            start = j
            end = k

        analyzevisible = QAction("Analyze &visible", table, triggered=partial(self.startAnalysis,
                                                                              table=table, start=start, end=end))
        analyzeall = QAction("Analyze &all", table, triggered=partial(self.startAnalysis, table=table,
                                                                      start=0, end=self.filter.prev.framecount))
        autoscenes = QAction("A&utoscenes", table,
                             triggered=partial(self.autoScenes, table=table))

        if self.filter.stats is None or self.filter.stats.shape[0] < self.filter.source.framecount - 1 \
                or isnan(self.filter.stats[self.filter.prev.cumulativeIndexReverseMap[1:] - 1]).any():
            autoscenes.setDisabled(True)

        keyscenes = QAction("Scenes from &Key Frames", table, triggered=partial(
            self.scenesFromKeyFrames, table=table))
        menu.addAction(analyzevisible)
        menu.addAction(analyzeall)
        menu.addAction(autoscenes)
        menu.addAction(keyscenes)
        menu.addSeparator()
        scenedlg = QAction("Scene &Dialog...", table, triggered=partial(
            self.sceneDlg, table=table, index=index))
        menu.addAction(scenedlg)

        return menu

    def sceneDlg(self, table, index):
        J, zone = self.filter.zoneAt(index.row())
        dlg = QScenes(table)
        dlg.setFilter(self.filter, True)
        dlg.setZone(zone)
        dlg.contentsModified.connect(table.contentsModified)
        dlg.zoneChanged.connect(partial(self.scrollTableToZone, table))
        dlg.slider.slider.setValue(self.filter.cumulativeIndexMap[index.row()])
        dlg.exec_()

    def checkSelected(self, table, check=True):
        sm = table.selectionModel()
        selected = {table.model().data(idx, Qt.UserRole)
                    for idx in sm.selectedIndexes()}

        for k in selected:
            if table.isRowHidden(k):
                continue

            if check and k not in self.filter.zone_indices:
                self.filter.insertZoneAt(k)
            # and zone is self.filter[0]:
            elif not check and k in self.filter.zone_indices:
                self.filter.removeZoneAt(k)

        table.contentsModified.emit()

    def autoScenes(self, table):
        if len(self.filter) <= 1 or \
                QMessageBox.question(table, "Auto Scenes", "Current zone settings will be lost! Do you wish to proceed?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            isan = isnan(self.filter.stats).sum(axis=1) == 0
            N = arange(1, self.filter.source.framecount)[isan]
            stats = self.filter.stats[isan]

            newzones = set()
            Q = (stats[1:, 0] + 4)/(stats[:-1, 0] + 4)
            K1 = N[:-1][Q >= 2]
            newzones.update(K1 + 1)

            W = array(list(windowed(stats[47:], 13)))
            V = W.max(axis=2)
            K2 = N[47:-12][(V[:, :12] < 1).all(axis=1)*(V[:, 12] >= 1)]
            newzones.update(K2)

            #val = stats[:,0]
            #qvals = (val[1:] + 5)/(val[:-1] + 5)

            #newzones = set()

            # for k in range(1, self.filter.prev.framecount):
            #content_val, delta_hue, delta_sat, delta_lum = self.filter.stats[k - 1]

            # if k > 1:
            #qval = qvals[k-2]

            # else:
            #qval = 0

            # if qval >= 2 or \
            # (k + 12 < self.filter.prev.framecount and (self.filter.stats[k - 1:k + 11] <= 1).all() and (self.filter.stats[k + 11] > 1).any()):
            # newzones.add(k)

            existing = set()
            zonestoremove = set()

            for zone in self.filter[1:]:
                if zone.src_start not in newzones:
                    zonestoremove.add(zone)

                else:
                    existing.add(zone.src_start)

            for zone in zonestoremove:
                self.filter.removeZoneAt(zone.src_start)

            fixpts = self.filter.fixpts
            self.filter.fixpts = 0

            for k in newzones:
                if k not in existing:
                    self.filter.insertZoneAt(int(k))

            self.filter.fixpts = fixpts
            table.contentsModified.emit()

    def scenesFromKeyFrames(self, table):
        answer = QMessageBox.question(
            table, "Scenes from Key Frames", "Current zone settings will be lost! Do you wish to proceed?", QMessageBox.Yes | QMessageBox.No)
        if answer == QMessageBox.Yes:
            while len(self.filter) > 1:
                self.filter.removeZoneAt(self.filter[1].src_start)

            for k in self.filter.source.keyframes:
                self.filter.insertZoneAt(k)

            table.contentsModified.emit()

    def startAnalysis(self, table, start, end):
        # table.setDisabled(True)
        self.progress = QProgressDialog(
            "Analyzing Frames", "&Cancel", 0, end - start - 1, table)
        self.analysisended.connect(partial(self.endAnalysis, table))
        self.analysisprogress.connect(self.progress.setValue)
        self.progress.setWindowTitle("Analyzing Frames")
        self.progress.show()
        t = AnalysisThread(self.filter, start, end,
                           self.analysisprogress.emit, self.analysisended.emit)
        self.progress.canceled.connect(t.interrupt)
        t.start()

    def endAnalysis(self, table):
        self.progress.canceled.disconnect()
        self.progress.close()
        self.progress = None
        # table.setEnabled(True)
        self.analysisprogress.disconnect()
        self.analysisended.disconnect()
        table.contentsModified.emit()
        table.setFocus()

    def _keyPressFunc(self, table, event):
        current = table.currentIndex()
        selection = table.selectionModel().selectedIndexes()
        key = event.key()
        modifiers = event.modifiers()
        model = table.model()

        if key == Qt.Key_S and modifiers & Qt.ShiftModifier:
            zones = set(self.filter.zone_indices)
            self.setFilter(table, zones)
            return True

        elif key == Qt.Key_A and modifiers & Qt.ShiftModifier:
            self.setFilter(table, None)
            return True

        return False


class SceneCol(BaseSceneCol):
    headerdisplay = "Scene"

    def _keyPressFunc(self, table, event):
        current = table.currentIndex()
        selection = table.selectionModel().selectedIndexes()
        key = event.key()
        modifiers = event.modifiers()
        model = table.model()

        if key == Qt.Key_Space and modifiers == Qt.NoModifier:
            newcheckstate = not model.data(current, Qt.CheckStateRole)
            N = model.data(current, Qt.UserRole)

            if newcheckstate:
                self.filter.insertZoneAt(N)

            elif N > 0 and N in self.filter.zone_indices:
                self.filter.removeZoneAt(N)

            for idx in selection:
                n = model.data(idx, Qt.UserRole)

                if n == N:
                    continue

                if newcheckstate:
                    self.filter.insertZoneAt(n)

                elif n > 0 and n in self.filter.zone_indices:
                    self.filter.removeZoneAt(n)

            idx1 = table.model().index(0, 0)
            idx2 = table.model().index(table.model().rowCount() -
                                       1, table.model().columnCount()-1)
            table.model().dataChanged.emit(idx1, idx2)
            table.contentsModified.emit()

            return True

        return BaseSceneCol._keyPressFunc(self, table, event)


class ContentCol(BaseSceneCol):
    checkstate = None
    headerdisplay = "Score"

    def display(self, index, n):
        if isinstance(self.filter.prev, BaseVideoFilter):
            while self.filter.prev.cumulativeIndexMap[n] < 0:
                n += 1

        if n > 0 and self.filter.stats is not None and \
                self.filter.stats.shape[0] >= n and \
                self.filter.stats.shape[1] >= 1 and \
                not isnan(self.filter.stats[n - 1, 0]):
            return "%0.3f" % self.filter.stats[n - 1, 0]

        return "-"

    def fgdata(self, index, n):
        if not isinstance(self.filter.prev, BaseFilter):
            return self.fgcolor

        if n >= 0 and self.filter.prev.cumulativeIndexMap[n] >= 0:
            return self.fgcolor

        return self.fgcoloralt


class DeltaHueCol(BaseSceneCol):
    checkstate = None
    headerdisplay = "\u2206Hue"

    def display(self, index, n):
        if isinstance(self.filter.prev, BaseVideoFilter):
            while self.filter.prev.cumulativeIndexMap[n] < 0:
                n += 1

        if n > 0 and self.filter.stats is not None and \
                self.filter.stats.shape[0] >= n and \
                self.filter.stats.shape[1] >= 2 and \
                not isnan(self.filter.stats[n - 1, 1]):
            return "%0.3f" % self.filter.stats[n - 1, 1]

        return "-"

    def fgdata(self, index, n):
        if not isinstance(self.filter.prev, BaseFilter):
            return self.fgcolor

        if n >= 0 and self.filter.prev.cumulativeIndexMap[n] >= 0:
            return self.fgcolor

        return self.fgcoloralt


class DeltaSatCol(BaseSceneCol):
    checkstate = None
    headerdisplay = "\u2206Sat"

    def display(self, index, n):
        if isinstance(self.filter.prev, BaseVideoFilter):
            while self.filter.prev.cumulativeIndexMap[n] < 0:
                n += 1

        if n > 0 and self.filter.stats is not None and \
                self.filter.stats.shape[0] >= n and \
                self.filter.stats.shape[1] >= 3 and \
                not isnan(self.filter.stats[n - 1, 2]):
            return "%0.3f" % self.filter.stats[n - 1, 2]

        return "-"

    def fgdata(self, index, n):
        if not isinstance(self.filter.prev, BaseFilter):
            return self.fgcolor

        if n >= 0 and self.filter.prev.cumulativeIndexMap[n] >= 0:
            return self.fgcolor

        return self.fgcoloralt


class DeltaLumCol(BaseSceneCol):
    checkstate = None
    headerdisplay = "\u2206Lum"

    def display(self, index, n):
        if isinstance(self.filter.prev, BaseVideoFilter):
            while self.filter.prev.cumulativeIndexMap[n] < 0:
                n += 1

        if n > 0 and self.filter.stats is not None and \
                self.filter.stats.shape[0] >= n and \
                self.filter.stats.shape[1] >= 4 and \
                not isnan(self.filter.stats[n - 1, 3]):
            return "%0.3f" % self.filter.stats[n - 1, 3]

        return "-"

    def fgdata(self, index, n):
        if not isinstance(self.filter.prev, BaseFilter):
            return self.fgcolor

        if n >= 0 and self.filter.prev.cumulativeIndexMap[n] >= 0:
            return self.fgcolor

        return self.fgcoloralt
