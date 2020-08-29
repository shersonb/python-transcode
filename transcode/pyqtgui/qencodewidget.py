#!/usr/bin/python
from PyQt5.QtCore import QDir, Qt, QModelIndex, pyqtSignal, pyqtBoundSignal, QThread, QRect, QObject
from PyQt5.QtGui import QImage, QPainter, QPalette, QPixmap, QColor, QFont, QBrush, QPen, QIcon, QFontMetrics, QPainterPath
from PyQt5.QtWidgets import (QAction, QApplication, QFileDialog, QLabel, QFrame,
        QMainWindow, QMenu, QMessageBox, QGridLayout, QScrollArea, QSizePolicy, QWidget,
        QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton, QTableWidget, QTableWidgetItem,
        QAbstractItemView, QHeaderView, QProgressBar, QStatusBar, QTabWidget, QVBoxLayout,
        QComboBox, QGridLayout, QHBoxLayout, QDialog)
from PyQt5.QtPrintSupport import QPrintDialog, QPrinter
from PyQt5.QtCore import pyqtSlot
from PIL import Image
from av.video import VideoFrame
from transcode.util import Packet
from .qimageview import QImageView
import av
import time
from itertools import count
import numpy
from fractions import Fraction as QQ
import transcode.util
import types
import traceback
import io

av.logging.set_level(av.logging.ERROR)

class ProgressBar(QProgressBar):
    progressStarted = pyqtSignal(float)
    progressUpdated = pyqtSignal(float)
    progressEnded = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super(ProgressBar, self).__init__(*args, **kwargs)
        self.progressStarted.connect(self.progressStart)
        self.progressUpdated.connect(self.setValue)
        self.progressEnded.connect(self.progressEnd)
        self.setHidden(True)

    def progressStart(self, maximum):
        self.setMaximum(maximum)
        self.setValue(0)
        self.setHidden(False)

    def setValue(self, value):
        QProgressBar.setValue(self, value)

        if self.maximum() > 0:
            self.setFormat("{0:.3%}".format(value/self.maximum()))

        else:
            self.setFormat("???")

    def progressEnd(self):
        self.setHidden(True)

class Graph(QWidget):
    dataadded = pyqtSignal(list)
    def __init__(self, A, font, pens, *args, **kwargs):
        super(Graph, self).__init__(*args, **kwargs)
        self.A = A
        self.font = font
        self.dataadded.connect(self.addPoints)
        self.setMinimumHeight(120)
        self.pens = pens

    def addPoints(self, points):
        try:
            self.A = numpy.concatenate((self.A, numpy.moveaxis([points], 0, 1)), axis=1)
        except:
            print("Failed to add %s" % points)
            return
        self.repaint()

    def paintEvent(self, event):
        metrics = QFontMetrics(self.font)
        fw = metrics.width("0000000")
        fh = metrics.height()
        ascent = metrics.ascent()

        w, h = self.width(), self.height()

        painter = QPainter(self)
        painter.setFont(self.font)
        blackpen = QPen(Qt.black, 1)
        redpen = QPen(Qt.red, 1)
        greypen = QPen(Qt.gray, 1)
        painter.setPen(blackpen)
        fill = QBrush(QColor(255, 255, 255))
        painter.fillRect(QRect(fw, 0, w - fw - 1, h - fh), fill)

        if self.A.shape[1]:
            X, Y = numpy.moveaxis(self.A[:,-w//2:], 2, 0)
            Ymin = min(0, Y.min())
            Ymax = Y.max()

            maxticks = int((h - fh)/(1.5*fh))

            for k in count(0):
                if 2**k*maxticks >= Ymax:
                    break

            ticks = Ymax/2**k
            ticks = int(ticks + (-ticks)%1)
            Ymax = ticks*2**k

            Xmax = X.max()
            Xmin = Xmax - w/2


            for x in range(int(Xmin + (120 - Xmin) % 120), int(Xmax), 120):
                if x < 0:
                    continue
                u = (w - fw)*(x - Xmin)/(Xmax - Xmin) + fw
                painter.setPen(greypen)
                painter.drawLine(u, 0, u, h - fh)

                painter.setPen(blackpen)
                sw = metrics.width(str(x))
                if u - sw//2 > fw and u + sw//2 < w:
                    painter.drawText(u - sw//2, h, str(x))

            for y in range(0, int(Ymax), 2**k):
                v = h - fh - (h - fh)*(y - Ymin)/(Ymax - Ymin)
                painter.setPen(greypen)
                painter.drawLine(fw, v, w, v)

                painter.setPen(blackpen)
                sw = metrics.width(str(y))
                #u = (w - fw)*(x - Xmin)/(Xmax - Xmin) + fw
                #if u - sw//2 > fw and u + sw//2 < w:
                painter.drawText(fw - sw - 4, v + ascent/3, str(y))

            for pen, row in zip(self.pens, self.A):
                X, Y = row[-w//2:].transpose()
                U = (w - fw)*(X - Xmin)/(Xmax - Xmin) + fw
                V = h - fh - (h - fh)*(Y - Ymin)/(Ymax - Ymin)

                painter.setPen(pen)
                path = QPainterPath()
                #painter.begin(self)
                painter.setRenderHint(QPainter.Antialiasing)
                path.moveTo(U[0], V[0])

                for x, y in zip(U[1:], V[1:]):
                    path.lineTo(x, y)

                painter.drawPath(path)

        painter.setPen(blackpen)
        painter.drawRect(QRect(fw, 0, w - fw - 1, h - fh))

class TrackStats(QWidget):
    def __init__(self, duration, title="Untitled", framecount=None, time_base=QQ(1/1000), keep=7200, font=QFont("DejaVu Serif", 8), parent=None):
        super(TrackStats, self).__init__(parent)
        self.setHidden(True)
        self.framecount = framecount
        self.duration = duration
        self.timestamps = []
        self.sizes = []
        self.bytesreceived = 0
        self.packetsreceived = 0
        self.lastpts = 0
        self.keep = keep
        self.time_base = time_base
        self.font = font

        self.titleLabel = QLabel(title, self)
        self.titleLabel.setFont(self.font)

        self.frameCountLabel = QLabel(self)
        self.sizeLabel = QLabel(self)
        self.bitrateLabel = QLabel(self)
        self.timestampLabel = QLabel(self)
        self.etaLabel = QLabel(self)
        self.etaLabel.setHidden(True)

        self.frameCountLabel.setFont(self.font)
        self.sizeLabel.setFont(self.font)
        self.bitrateLabel.setFont(self.font)
        self.timestampLabel.setFont(self.font)
        self.etaLabel.setFont(self.font)
        self.reset()

    def reset(self):
        self.timestamps = []
        self.bytesreceived = 0
        self.packetsreceived = 0
        self.lastpts = 0

        if self.framecount is not None:
            self.frameCountLabel.setText(f"—/{self.framecount:,d} (— fps)")

        else:
            self.frameCountLabel.setText("— (— fps)")

        self.sizeLabel.setText("0 B")
        self.bitrateLabel.setText("— kbps")
        self.timestampLabel.setText("0:00:00.000")
        self.etaLabel.setText("—")

    def newPacket(self, packet):
        self.timestamps.append(time.time())

        if self.keep and len(self.timestamps) > self.keep:
            del self.timestamps[:-self.keep]

        self.bytesreceived += packet.size
        self.sizeLabel.setText(transcode.util.h(self.bytesreceived))
        self.packetsreceived += 1

        if len(self.timestamps) >= 2 and self.timestamps[-1] - self.timestamps[0] > 0:
            rate = (len(self.timestamps) - 1)/(self.timestamps[-1] - self.timestamps[0])

        else:
            rate = None

        if rate and self.framecount is not None:
            self.frameCountLabel.setText(f"{self.packetsreceived:,d}/{self.framecount:,d} ({rate:,.2f} fps)")
            timeleft = int((self.framecount - self.packetsreceived)/rate)
            m, s = divmod(timeleft, 60)
            h, m = divmod(m, 60)
            d, h = divmod(h, 24)
            eta = time.time() + timeleft
            etastr = time.strftime("%A, %B %-d, %Y, %-I:%M:%S %p", time.localtime(eta))

            if d > 1:
                self.etaLabel.setText(f"{d:d} days, {h:d}:{m:02d}:{s:02d} ({etastr})")

            elif d == 1:
                self.etaLabel.setText(f"1 day, {h:d}:{m:02d}:{s:02d} ({etastr})")

            else:
                self.etaLabel.setText(f"{h:d}:{m:02d}:{s:02d} ({etastr})")

        elif self.framecount is not None:
            self.frameCountLabel.setText(f"{self.packetsreceived:,d}/{self.framecount:,d} (— fps)")

        elif rate:
            self.frameCountLabel.setText(f"{self.packetsreceived:,d} ({rate:,.2f} fps)")

        else:
            self.frameCountLabel.setText(f"{self.packetsreceived:,d} (— fps)")

        self.lastpts = max(self.lastpts, (packet.pts + packet.duration)*packet.time_base)

        if self.lastpts:
            self.bitrateLabel.setText(f"{float(self.bytesreceived/self.lastpts/125):,.2f} kbps")

        m, s = divmod(float(self.lastpts), 60)
        h, m = divmod(int(m), 60)
        self.timestampLabel.setText(f"{h:d}:{m:02d}:{s:06.3f}")

class QEncodeDialog(QDialog):
    framesenttoencoder = pyqtSignal(VideoFrame)
    packetreceived = pyqtSignal(Packet)
    statsloaded = pyqtSignal(numpy.ndarray)
    encodefinished = pyqtSignal()
    encodepaused = pyqtSignal(str)
    encodeinterrupted = pyqtSignal()
    encodeerror = pyqtSignal(BaseException, types.TracebackType)

    def __init__(self, output_file, pass_=None, encoderoverrides=[], logfile=None, *args, **kwargs):
        super(QEncodeDialog, self).__init__(*args, **kwargs)
        self.packetreceived.connect(self.packetReceived)
        self.encodefinished.connect(self.encodeFinished)
        self.encodepaused.connect(self.encodePaused)
        self.encodeinterrupted.connect(self.encodeInterrupted)
        self.encodeerror.connect(self.encodeError)
        self.framesenttoencoder.connect(self.setFrame)
        self.statsloaded.connect(self.statsLoaded)
        self.output_file = output_file
        self.pass_ = pass_
        self.logfile = logfile
        self.encoderoverrides = encoderoverrides
        self.setWindowTitle(output_file.title)

        try:
            if hasattr(output_file, "attachments") and output_file.attachments:
                for attachment in output_file.attachments:
                    try:
                        if attachment.fileName.lower() in ("cover.png", "cover.jpg"):
                            bytesio = io.BytesIO()
                            bytesio.write(attachment.fileData)
                            bytesio.seek(0)
                            qim = Image.open(bytesio).toqpixmap()
                            icon = QIcon(qim)
                            self.setWindowIcon(icon)
                            bytesio.close()
                            break

                    except:
                        pass

        except:
            pass

        fonthead = QFont("DejaVu Serif", 10, QFont.Bold, italic=True)
        fonttotal = QFont("DejaVu Serif", 8, italic=True)
        font = QFont("DejaVu Serif", 8)
        self.setFont(font)

        self._layout = QVBoxLayout(self)
        self.setLayout(self._layout)

        if self.output_file.vtrack is not None:
            self._hlayout = QHBoxLayout(self)
            k = self._layout.count()
            self.imageWindow = QImageView(self)
            w = self.output_file.vtrack.width
            h = self.output_file.vtrack.height
            self.imageWindow.setPixmap(QPixmap(w, h))
            self._layout.addWidget(self.imageWindow)
            self._layout.setStretch(k, 2)
            self._layout.addStretch()
            self.imageWindow.setSar(self.output_file.vtrack.sar)

        self.scroll = QScrollArea(self)
        self._layout.addWidget(self.scroll)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setWidgetResizable(True)
        self.scroll.setMinimumHeight(128)
        self.scroll.setMaximumHeight(192)

        self.scrollwidget = QWidget(self.scroll)
        self.scroll.setWidget(self.scrollwidget)

        self._gridlayout = QGridLayout(self)
        self.scrollwidget.setLayout(self._gridlayout)

        self.tracklabel = QLabel("Track", self)
        self._gridlayout.addWidget(self.tracklabel, 0, 0)
        self.tracklabel.setFont(fonthead)

        self.pktlabel = QLabel("Packets", self)
        self._gridlayout.addWidget(self.pktlabel, 0, 1)
        self.pktlabel.setFont(fonthead)

        self.ptslabel = QLabel("Timestamp", self)
        self._gridlayout.addWidget(self.ptslabel, 0, 2)
        self.ptslabel.setFont(fonthead)

        self.sizelabel = QLabel("Size", self)
        self._gridlayout.addWidget(self.sizelabel, 0, 3)
        self.sizelabel.setFont(fonthead)

        self.bitratelabel = QLabel("Bitrate", self)
        self._gridlayout.addWidget(self.bitratelabel, 0, 4)
        self.bitratelabel.setFont(fonthead)

        self.trackinfo = []
        self.encodeThread = None

        videofound = False

        for k, track in enumerate(output_file.tracks):
            lang = track.language if track.language is not None else "und"

            if track.name is None:
                title = track.type[0].upper() + track.type[1:]

            else:
                title = track.name

            title = f"{k}: {title} ({lang})"
            time_base = track.time_base

            trackinfo = TrackStats(duration=min(track.duration, track.container.duration), title=title,
                                   framecount=track.framecount, time_base=track.time_base, keep=7200, parent=self)

            self.trackinfo.append(trackinfo)
            self._gridlayout.addWidget(trackinfo.titleLabel, k+1, 0)
            self._gridlayout.addWidget(trackinfo.frameCountLabel, k+1, 1)
            self._gridlayout.addWidget(trackinfo.timestampLabel, k+1, 2)
            self._gridlayout.addWidget(trackinfo.sizeLabel, k+1, 3)
            self._gridlayout.addWidget(trackinfo.bitrateLabel, k+1, 4)

        self.totalinfo = TrackStats(None, title="Total", framecount=sum(track.framecount for track in output_file.tracks),
                                    keep=7200, font=fonttotal, parent=self)
        self._gridlayout.addWidget(self.totalinfo.titleLabel, len(output_file.tracks) + 2, 0)
        self._gridlayout.addWidget(self.totalinfo.frameCountLabel, len(output_file.tracks) + 2, 1)
        self._gridlayout.addWidget(self.totalinfo.timestampLabel, len(output_file.tracks) + 2, 2)
        self._gridlayout.addWidget(self.totalinfo.sizeLabel, len(output_file.tracks) + 2, 3)
        self._gridlayout.addWidget(self.totalinfo.bitrateLabel, len(output_file.tracks) + 2, 4)


        k = self._layout.count()
        self.graph = Graph(numpy.zeros((1, 0, 2)), QFont("Dejavu Serif", 6), [QPen(QColor(255, 0, 0), 1)], self)
        self._layout.addWidget(self.graph)
        self._layout.setStretch(k, 2)
        self.graph.setHidden(output_file.vtrack is None)

        self.progressBar = ProgressBar(self)
        self._layout.addWidget(self.progressBar)
        self.progressBar.setMaximum(sum(info.framecount for info in self.trackinfo if info.framecount))
        self.progressBar.setHidden(False)

        if self.output_file.vtrack is not None:
            self._stats = QHBoxLayout(self)
            self._layout.addLayout(self._stats)

            m, s = divmod(self.output_file.vtrack.duration, 60)
            m = int(m)
            h, m = divmod(m, 60)
            self._durationLabel = QLabel(f"Duration: {h:d}:{m:02d}:{s:06.3f}", self)
            self._stats.addWidget(self._durationLabel)
            self._stats.addStretch()

            self._etaTextLabel = QLabel("ETA:", self)
            self._stats.addWidget(self._etaTextLabel)
            self._etaTextLabel.setFont(font)

            etaLabel = self.trackinfo[self.output_file.vtrack.track_index].etaLabel
            etaLabel.setHidden(False)
            self._stats.addWidget(etaLabel)

        self._btnlayout = QHBoxLayout()
        self._layout.addLayout(self._btnlayout)

        self.autoClose = QCheckBox("&Auto-close")
        self._btnlayout.addWidget(self.autoClose)
        self.autoClose.setChecked(True)

        self._btnlayout.addStretch()

        self.pauseBtn = QPushButton("&Pause")
        self._btnlayout.addWidget(self.pauseBtn)
        self.pauseBtn.clicked.connect(self.onPauseBtn)
        self.pauseBtn.setEnabled(False)
        self.pauseBtn.setIcon(QIcon.fromTheme("media-playback-pause"))

        self.cancelBtn = QPushButton("&Cancel")
        self._btnlayout.addWidget(self.cancelBtn)
        self.cancelBtn.setIcon(QIcon.fromTheme("process-stop"))
        self.cancelBtn.clicked.connect(self.close)

        self.cancelEncodeDlg = QMessageBox(self)
        self.cancelEncodeDlg.setWindowTitle("Cancel Encode?")
        self.cancelEncodeDlg.setText("Do you wish to cancel the current encode job?")              
        self.cancelEncodeDlg.setStandardButtons(QMessageBox.Yes)
        self.cancelEncodeDlg.addButton(QMessageBox.No)
        self.cancelEncodeDlg.setDefaultButton(QMessageBox.No)
        self.cancelEncodeDlg.setIcon(QMessageBox.Question)

    def setFrame(self, frame):
        im = frame.to_image()
        pix = im.toqpixmap()
        self.imageWindow.setPixmap(pix)

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()

        if key == Qt.Key_Escape and modifiers == Qt.NoModifier:
            self.close()
            return

        return QDialog.keyPressEvent(self, event)

    def exec_(self):
        self.startTranscode()
        return QDialog.exec_(self)

    def packetReceived(self, pkt):
        if self.output_file is not None and self.output_file.vtrack is not None and pkt.track_index == self.output_file.vtrack.track_index:
            k = self.trackinfo[pkt.track_index].packetsreceived

            if self.vhist is not None and self.vhist.ndim:
                if len(self.vhist) >= 2:
                    self.graph.addPoints([(k, self.vhist[-2, k]), (k, self.vhist[-1, k]), (k, pkt.size)])

                elif len(self.vhist) == 1:
                    self.graph.addPoints([(k, self.vhist[-1, k]), (k, pkt.size)])

            else:
                self.graph.addPoints([(k, pkt.size)])

        self.trackinfo[pkt.track_index].newPacket(pkt)
        self.totalinfo.newPacket(pkt)
        framesdone = sum(info.packetsreceived for info in self.trackinfo if info.framecount)
        self.progressBar.setValue(framesdone)

    @pyqtSlot(numpy.ndarray)
    def statsLoaded(self, stats):
        self.vhist = stats

        if stats.ndim:
            if len(stats) >= 2:
                pens = [QPen(QColor(160, 160, 255), 1), QPen(QColor(80, 80, 255), 1), QPen(QColor(255, 0, 0), 1)]

            elif len(stats) == 1:
                pens = [QPen(QColor(80, 80, 255), 1), QPen(QColor(255, 0, 0), 1)]

            self.graph.pens = pens
            self.graph.A = numpy.zeros((1 + min(2, len(stats)), 0, 2))
        

    def startTranscode(self):
        for stats in self.trackinfo:
            stats.reset()

        self.totalinfo.reset()
        self.vhist = None

        self.encodeThread = self.output_file.createTranscodeThread(pass_=self.pass_, logfile=self.logfile,
                            encoderoverrides=self.encoderoverrides, notifyvencode=self.framesenttoencoder.emit,
                            notifymux=self.packetreceived.emit, notifypaused=self.encodepaused.emit,
                            notifyerror=self.encodeerror.emit, notifyfinish=self.encodefinished.emit,
                            notifycancelled=self.encodeinterrupted.emit,
                            notifystats=self.statsloaded.emit, autostart=False)

        self.encodeThread.start()
        self.pauseBtn.setEnabled(True)

    def closeEvent(self, event):
        if self.output_file.transcode_started and self.cancelEncodeDlg.exec_() == QMessageBox.No:
            event.ignore()
            return

        self.output_file.stopTranscode()

        if self.encodeThread is not None:
            self.encodeThread.join()

        event.accept()

    def stopTranscode(self):
        if not self.output_file._unpaused.isSet():
            self.output_file.unpauseMux()

        self.output_file.stopTranscode()

    def encodeInterrupted(self):
        self.autoClose.setEnabled(False)

    @pyqtSlot(BaseException, types.TracebackType)
    def encodeError(self, exc, tb):
        message = "".join(traceback.format_exception(type(exc), exc, tb))
        self.pauseBtn.setEnabled(False)
        self.cancelBtn.setText("&Close")
        errorDlg = QMessageBox(self)
        errorDlg.setWindowTitle("Encoding Error")
        errorDlg.setText("The following exception was encountered while encoding \"%s\":\n\n%s" % (self.output_file.title, message))              
        errorDlg.setStandardButtons(QMessageBox.Ok)
        errorDlg.setDefaultButton(QMessageBox.Ok)
        errorDlg.setIcon(QMessageBox.Critical)
        errorDlg.exec_()
        self.autoClose.setEnabled(False)

    @pyqtSlot(str)
    def encodePaused(self, message="Encoding Paused"):
        self.pauseBtn.setText("&Resume")
        pausedDlg = QMessageBox(self)
        pausedDlg.setWindowTitle("Encoding Paused")
        pausedDlg.setText(message)              
        pausedDlg.setStandardButtons(QMessageBox.Ok)
        pausedDlg.setDefaultButton(QMessageBox.Ok)
        pausedDlg.setIcon(QMessageBox.Critical)
        pausedDlg.exec_()

    def encodeFinished(self):
        if self.autoClose.checkState():
            self.done(1)
            self.close()

        else:
            self.setResult(1)
            self.autoClose.setEnabled(False)
            self.pauseBtn.setEnabled(False)
            self.cancelBtn.setText("&Close")

    def onPauseBtn(self):
        if self.output_file._unpaused.isSet():
            self.pauseEncode()

        else:
            self.resumeEncode()

    def pauseEncode(self):
        self.output_file.pauseMux()
        self.pauseBtn.setText("&Resume")

    def resumeEncode(self):
        self.output_file.unpauseMux()
        self.pauseBtn.setText("&Pause")

        for stats in self.trackinfo:
            stats.timestamps = []

        self.totalinfo.timestamps = []
