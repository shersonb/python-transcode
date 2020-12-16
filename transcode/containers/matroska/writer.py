from .. import basewriter
import matroska
from ...encoders.base import EncoderContext
from ...util import h
#from ...encoders.audio.base import AudioEncoderContext
from fractions import Fraction as QQ
from collections import OrderedDict
from numpy import (array, int0, unique, searchsorted, concatenate, sort,
                   diff, insert, zeros, ones, log2, concatenate)
from ..basereader import BaseReader
from .attachments import AttachmentRef
from .uid import formatUID
import random
from more_itertools import windowed
from ebml.ndarray import EBMLNDArray
from ebml.base import EBMLList, EBMLMasterElement, EBMLProperty
from ebml.util import toVint


codecs = dict(
    hevc="V_MPEGH/ISO/HEVC",
    libx265="V_MPEGH/ISO/HEVC",
    h264="V_MPEG4/ISO/AVC",
    libx264="V_MPEG4/ISO/AVC",
    vc1="V_MS/VFW/FOURCC",
    ac3="A_AC3",
    eac3="A_EAC3",
    aac="A_AAC",
    flac="A_FLAC",
    dts="A_DTS",
    dca="A_DTS",
    libfdk_aac="A_AAC",
    ssa="S_TEXT/ASS",
    pgssub="S_HDMV/PGS",
    dvdsub="S_VOBSUB",
    ass="S_TEXT/ASS",
    mpeg2video="V_MPEG2",
    dvd_subtitle="S_VOBSUB"

)


class PtsArray(EBMLNDArray):
    ebmlID = b"\xde"


class PtsArrays(EBMLList):
    itemclass = PtsArray


class ClusterPts(EBMLMasterElement):
    ebmlID = b"\x14\xae\x04\x35"
    __ebmlchildren__ = (
            EBMLProperty("ptsArrays", PtsArrays),
        )


def calcKeyFrames(iterable, maxint, end):
    """
    Takes an iterable of increasing integers and inserts values so that two consecutive
    values do not differ more than maxint. Much like inserting keyframes every n frames if
    no scene cuts have been encountered.
    """
    for x1, x2 in windowed(iterable, 2):
        if x2 is None or end < x2:
            for x in range(x1, end, maxint):
                yield x

            return

        for x in range(x1, x2, maxint):
            yield x

    for x in range(x2, end, maxint):
        yield x


class Track(basewriter.Track):
    """Track class for the Matroska media format."""

    def __init__(self, source, encoder=None, filters=None, name=None, language=None, trackUID=None,
                 maxInLace=1, enabled=True, forced=False, compression=None, mincache=None, maxcache=None, container=None):
        self.name = name
        self.language = language
        self.trackUID = trackUID
        self.maxInLace = maxInLace
        self.compression = compression
        self.forced = forced
        self.enabled = enabled
        self.trackEntry = None
        self.mincache = mincache
        self.maxcache = maxcache
        self.clusterPts = None
        self.clusterPtsHist = ClusterPts([])
        super().__init__(source, encoder, filters, name=name,
                         language=language, container=container)

    def __getstate__(self):
        state = super().__getstate__() or OrderedDict()

        if self.trackUID:
            state["trackUID"] = self.trackUID

        if self.maxInLace:
            state["maxInLace"] = self.maxInLace

        if self.enabled is not None:
            state["enabled"] = self.enabled

        if self.forced is not None:
            state["forced"] = self.forced

        if self.compression is not None:
            state["compression"] = self.compression

        if self.mincache is not None:
            state["mincache"] = self.mincache

        if self.maxcache is not None:
            state["maxcache"] = self.maxcache

        return state

    def __setstate__(self, state):
        self.trackUID = state.get("trackUID")
        self.maxInLace = state.get("maxInLace")
        self.compression = state.get("compression")
        self.forced = state.get("forced")
        self.enabled = state.get("enabled")
        self.mincache = state.get("mincache")
        self.maxcache = state.get("maxcache")
        super().__setstate__(state)

    def _prepareentry(self, packets, logfile=None):
        if self.type == "video":
            self.trackEntry = self.container.mkvfile.tracks.new(
                codecs[self.codec], pixelWidth=self.width, pixelHeight=self.height)

            if self.sar > 1:
                self.trackEntry.video.displayWidth = self.sar*self.width
                self.trackEntry.video.displayHeight = self.height

            elif self.sar < 1:
                self.trackEntry.video.displayWidth = self.width
                self.trackEntry.video.displayHeight = self.height/self.sar

        elif self.type == "audio":
            self.trackEntry = self.container.mkvfile.tracks.new(
                codecs[self.codec], samplingFrequency=self.rate, channels=self.channels)

            if self.bitdepth:
                self.trackEntry.audio.bitDepth = self.bitdepth

        else:
            self.trackEntry = self.container.mkvfile.tracks.new(
                codecs[self.codec])

        self.trackEntry.trackUID = self.trackUID
        print(f"    Track UID: {formatUID(self.trackUID)}", file=logfile)

        self.trackEntry.defaultDuration = self.defaultDuration

        self.trackEntry.flagDefault = self in (
            self.container.defaultvideo, self.container.defaultaudio, self.container.defaultsubtitle)
        print(
            f"    Default: {bool(self.trackEntry.flagDefault)}", file=logfile)

        self.trackEntry.flagEnabled = self.enabled
        print(f"    Enabled: {bool(self.enabled)}", file=logfile)

        self.trackEntry.flagForced = self.forced
        print(f"    Forced: {bool(self.forced)}", file=logfile)

        self.trackEntry.flagLacing = self.maxInLace > 1
        self.trackEntry.maxInLace = self.maxInLace

        if self.trackEntry.flagLacing:
            print(
                f"    Lacing: Enabled (Maximum of {self.maxInLace} packets per block)", file=logfile)

        else:
            print(f"    Lacing: Disabled", file=logfile)

        self.trackEntry.name = self.name
        self.trackEntry.language = self.language
        self.trackEntry.compression = self.compression

        if self.compression is not None:
            compressionalgo = ["zlib"]
            print(
                f"    Packet Compression: Enabled ({compressionalgo[self.compression]})", file=logfile)

        else:
            print(f"    Packet Compression: Disabled", file=logfile)

        if isinstance(packets, EncoderContext):
            self.trackEntry.codecPrivate = packets.extradata

        else:
            self.trackEntry.codecPrivate = self.source.extradata

    def _getClusterSplit(self):
        vtrack = self.container.vtrack

        if self.container:
            if self.container.clusterPtsHist.ptsArrays:
                # Get clusterPts data from previous encode.
                return iter(self.container.clusterPtsHist.ptsArrays[-1])

            elif vtrack is not None:
                # Fallback: Predict clusterPts data
                if vtrack.filters:
                    kf = sorted(vtrack.filters.keyframes)

                else:
                    kf = [0]

                if hasattr(vtrack.encoder, "keyint"):
                    kf = list(calcKeyFrames(kf, vtrack.encoder.keyint, vtrack.framecount))

                clusterPts = vtrack.pts[kf]

                return calcKeyFrames(clusterPts, 32768*10**6,
                                   int(vtrack.duration*10**9+0.5))

    @property
    def sizes(self):
        if self.sizeStats is not None and len(self.sizeStats):
            sizes = self.sizeStats[-1].copy()

        elif self.compression == 0 and hasattr(self.source, "zsizes"):
            sizes = self.source.zsizes.copy()

        elif hasattr(self.source, "sizes"):
            sizes = self.source.sizes.copy()

        else:
            sizes = 1024*ones(self.framecount, dtype=int0)

        sizes = sizes[:self.framecount]

        if len(sizes) < self.framecount:
            sizes = concatenate((sizes, [0]*(self.framecount - len(sizes))))

        if self.encoder:
            if self.codec in ("libx265", "libx264", "hevc", "h264"):
                sizes += 4

        return sizes

    def calcOverhead(self):
        sizes = self.sizes.copy()

        if self.maxInLace > 1:
            clusterPts = array(list(self._getClusterSplit()))
            B = unique(searchsorted(self.pts, clusterPts))

            if self.defaultDuration:
                isNotDefaultDuration = abs(self.durations - int(self.defaultDuration)) >= 10**6
                B = unique(sort(concatenate((B, isNotDefaultDuration.nonzero()[0]))))

            B = array(list(calcKeyFrames(B, self.maxInLace, self.framecount)) + [self.framecount])

            NumInLace = diff(B)
            lacingOverhead = zeros(NumInLace.shape, dtype=int0)
            dsizes = insert(0, 1, diff(sizes))
            csizes = insert(0, 1, sizes.cumsum())
            cadsizes = abs(dsizes).cumsum()

            var = cadsizes[B[1:] - 1] - cadsizes[B[:-1]]

            fixedLaceBlocks = (var == 0)*(NumInLace > 1)
            varLaceBlocks = (var > 0)*(NumInLace > 1)

            lacingOverhead[fixedLaceBlocks] = 1

            EBMLLacingOverheadByPacket = int0((log2(abs(dsizes) + 1) + 1)/7) + 1
            EBMLLacingOverheadByPacket[B[:-1]] = int0(log2(sizes[B[:-1]] + 1)/7) + 1
            cE = insert(0, 1, EBMLLacingOverheadByPacket.cumsum())
            EBMLLacingOverhead = cE[B[1:]] - cE[B[:-1]]

            lacingOverhead[varLaceBlocks] = EBMLLacingOverhead[varLaceBlocks]

            Hsizes = int(log2(self.track_index + 1)/7 + 1) + 2 + 1 + lacingOverhead
            Psizes = csizes[B[1:]] - csizes[B[:-1]]
            Dsizes = Hsizes + Psizes
            overhead = (1 + int0(log2(Dsizes + 1)/7 + 1) + Hsizes).sum()

        else:
            if self.defaultDuration:
                isNotDefaultDuration = abs(self.durations - int(self.defaultDuration)) >= 10**6
                isDefaultDuration = ~isNotDefaultDuration

            else:
                isNotDefaultDuration = abs(self.durations) >= 10**6
                isDefaultDuration = ~isNotDefaultDuration

            overheads = zeros(isDefaultDuration.shape, dtype=int0)
            BlockDurationSizes = zeros(isDefaultDuration.shape, dtype=int0)
            BGoverhead = zeros(isDefaultDuration.shape, dtype=int0)

            HeadSizes = int(log2(self.track_index + 1)/7 + 1) + 2 + 1
            BlockPayloadSizes = HeadSizes + sizes
            BlockOverheadSizes = 1 + int0(log2(BlockPayloadSizes + 1)/7 + 1) + HeadSizes
            BlockDurationSizes[isNotDefaultDuration*(self.durations >= 256*10**6)] = 4
            BlockDurationSizes[isNotDefaultDuration*(self.durations < 256*10**6)] = 3
            BlockGroupPayloadSizes = BlockOverheadSizes + sizes + BlockDurationSizes
            BlockGroupOverheadSizes = 1 + int0(log2(BlockGroupPayloadSizes + 1)/7 + 1) + BlockDurationSizes
            overhead = BlockOverheadSizes.sum() + BlockGroupOverheadSizes[isNotDefaultDuration].sum()
            #return (HeadSizes, BlockPayloadSizes, BlockOverheadSizes, BlockDurationSizes, BlockGroupPayloadSizes, BlockGroupOverheadSizes)

        if self.encoder:
            if self.codec in ("libx265", "libx264", "hevc", "h264"):
                overhead += 4*self.framecount

        else:
            overhead += sum(sizes)

        return overhead


    def _iterFrames(self, duration=None, logfile=None):
        frames = super()._iterFrames(duration, logfile)

        if self.type == "video" and self.container and self.container.chapters:
            key_pts = sorted({ts for edition in self.container.chapters
                              for atom in edition
                              for ts in (atom.timeStart, atom.timeEnd)
                              if atom.segment is self.container
                              and (not atom.tracks or self in atom.tracks)})

            for frame in frames:
                if len(key_pts) and frame.pts*frame.time_base >= key_pts[0]*self.time_base:
                    frame.pict_type = "I"
                    del key_pts[0]

                yield frame

        else:
            for frame in frames:
                yield frame


    def _iterPackets(self, packets, duration=None, logfile=None):
        packets = super()._iterPackets(packets, duration, logfile)

        if self.container is not None and self.encoder is not None and self.type == "video":
            for packet in packets:
                if hasattr(packet, "keyframe") and packet.keyframe:
                    self.container.clusterPts.append(packet.pts)

                yield packet

        else:
            for packet in packets:
                yield packet

class MatroskaWriter(basewriter.BaseWriter):
    """Writer class for the Matroska media format."""
    trackclass = Track
    extensions = (".mkv", ".mka", ".mks")
    fmtname = "Matroska"

    def __init__(self, outputpath, tracks=[], targetsize=None, config=None,
                 title=None, chapters=None, attachments=None, tags=None,
                 segmentUID=None, nextUID=None, prevUID=None,
                 segmentFilename=None, nextFilename=None, prevFilename=None, segmentFamilies=[],
                 defaultvideo=None, defaultaudio=None, defaultsubtitle=None, writingApp="python-transcode"):
        self.title = title
        self.chapters = chapters
        self.attachments = attachments
        self.tags = tags
        self.mkvfile = None
        self.writingApp = writingApp
        self.segmentUID = segmentUID
        self.nextUID = nextUID
        self.prevUID = prevUID
        self.segmentFilename = segmentFilename
        self.nextFilename = nextFilename
        self.prevFilename = prevFilename
        self.segmentFamilies = segmentFamilies
        super().__init__(outputpath, tracks, targetsize, config)
        self.defaultvideo = defaultvideo
        self.defaultaudio = defaultaudio
        self.defaultsubtitle = defaultsubtitle

    def __getstate__(self):
        state = super().__getstate__() or OrderedDict()

        if self.title:
            state["title"] = self.title

        if self.chapters:
            state["chapters"] = self.chapters

        if self.attachments:
            state["attachments"] = self.attachments

        if self.tags:
            state["tags"] = self.tags

        if self.defaultvideo is not None:
            state["defaultvideo"] = self.defaultvideo

        if self.defaultaudio is not None:
            state["defaultaudio"] = self.defaultaudio

        if self.defaultsubtitle is not None:
            state["defaultsubtitle"] = self.defaultsubtitle

        if self.segmentUID is not None:
            state["segmentUID"] = self.segmentUID

        if self.nextUID is not None:
            state["nextUID"] = self.nextUID

        if self.prevUID is not None:
            state["prevUID"] = self.prevUID

        if self.segmentFilename is not None:
            state["segmentFilename"] = self.segmentFilename

        if self.nextFilename is not None:
            state["nextFilename"] = self.nextFilename

        if self.prevFilename is not None:
            state["prevFilename"] = self.prevFilename

        if self.segmentFamilies is not None:
            state["segmentFamilies"] = self.segmentFamilies

        return state

    def __setstate__(self, state):
        super().__setstate__(state)
        self.title = state.get("title")
        self.chapters = state.get("chapters")
        self.attachments = state.get("attachments")
        self.tags = state.get("tags")
        self.defaultvideo = state.get("defaultvideo")
        self.defaultaudio = state.get("defaultaudio")
        self.defaultsubtitle = state.get("defaultsubtitle")

        self.segmentUID = state.get("segmentUID")
        self.nextUID = state.get("nextUID")
        self.prevUID = state.get("prevUID")
        self.segmentFilename = state.get("segmentFilename")
        self.nextFilename = state.get("nextFilename")
        self.prevFilename = state.get("prevFilename")
        self.segmentFamilies = state.get("segmentFamilies")

    @property
    def chapters(self):
        return self._chapters

    @chapters.setter
    def chapters(self, value):
        if value:
            value.parent = self

        self._chapters = value

    @property
    def attachments(self):
        return self._attachments

    @attachments.setter
    def attachments(self, value):
        if value:
            value.parent = self

        self._attachments = value

    @property
    def tags(self):
        return self._tags

    @tags.setter
    def tags(self, value):
        if value:
            value.parent = self

        self._tags = value

    def calcOverhead(self):
        overhead = [40, 12, 128]  # EBML Head, Segment header, Seek Head + Void

        # Tracks
        trackSizes = self.lastoverhead.get("trackEntrySizes", ())
        overhead.append(len(matroska.Tracks.ebmlID))
        overhead.append(len(toVint(sum(trackSizes))))
        overhead.extend(trackSizes)
        overhead.append(128)

        if self.mkvfile:
            """
            'self.mkvfile' should never be none when transcode is started, but in case this method
            is called outside if self.transcode(), we will use sizes from the previous transcode
            if available (see 'else:' clause), provided that self.loadOverhead() is called beforehand.
            """

            overhead.append(self.mkvfile.segment.info.size())

            if len(self.mkvfile.chapters):
                overhead.append(self.mkvfile.chapters.size())

            if len(self.mkvfile.attachments):
                overhead.append(self.mkvfile.attachments.size())

            if len(self.mkvfile.tags):
                overhead.append(self.mkvfile.tags.size())

        else:
            overhead.append(self.lastoverhead.get("infoSize", 0))
            overhead.append(self.lastoverhead.get("chaptersSize", 0))
            overhead.append(self.lastoverhead.get("attachmentsSize", 0))
            overhead.append(self.lastoverhead.get("tagsSize", 0))

        overheadPerCluster = len(
            matroska.cluster.Cluster.ebmlID) + len(matroska.cluster.Timestamp.ebmlID) + 4
        overhead.append(
            overheadPerCluster*self.lastoverhead.get("clusterCount", int(self.duration/32.768 + 1)))
        return sum(overhead)

    @property
    def defaultvideo(self):
        return self._defaultvideo

    @defaultvideo.setter
    def defaultvideo(self, value):
        if value is None:
            self._defaultvideo = None

        elif isinstance(value, int):
            self._defaultvideo = self.tracks[value]

        elif value in self.tracks:
            self._defaultvideo = value

        else:
            raise ValueError("Not a valid track entry.")

    @property
    def defaultaudio(self):
        return self._defaultaudio

    @defaultaudio.setter
    def defaultaudio(self, value):
        if value is None:
            self._defaultaudio = None

        elif isinstance(value, int):
            self._defaultaudio = self.tracks[value]

        elif value in self.tracks:
            self._defaultaudio = value

        else:
            raise ValueError("Not a valid track entry.")

    @property
    def defaultsubtitle(self):
        return self._defaultsubtitle

    @defaultsubtitle.setter
    def defaultsubtitle(self, value):
        if value is None:
            self._defaultsubtitle = None

        elif isinstance(value, int):
            self._defaultsubtitle = self.tracks[value]

        elif value in self.tracks:
            self._defaultsubtitle = value

        else:
            raise ValueError("Not a valid track entry.")

    def _open(self):
        self.mkvfile = matroska.MatroskaFile(self.outputpathabs, "w")

    def _preparefile(self, logfile=None):
        self.clusterPts = []

        if self.title:
            self.mkvfile.title = self.title
            print(f"Title: {self.title}", file=logfile)

        if isinstance(self.segmentUID, (bytes, int)):
            self.mkvfile.info.segmentUID = self.segmentUID
            print(
                f"Segment UID: {' '.join(f'{x:02x}' for x in self.segmentUID)}", file=logfile)

        if self.segmentFilename is not None:
            self.mkvfile.info.segmentFilename = self.segmentFilename
            print(f"Segment Filename: {self.segmentFilename}", file=logfile)

        if isinstance(self.prevUID, (bytes, int)):
            self.mkvfile.info.prevUID = self.prevUID
            print(
                f"Previous UID: {' '.join(f'{x:02x}' for x in self.prevUID)}", file=logfile)

        if self.prevFilename is not None:
            self.mkvfile.info.prevFilename = self.prevFilename
            print(f"Previous Filename: {self.prevFilename}", file=logfile)

        if isinstance(self.nextUID, (bytes, int)):
            self.mkvfile.info.nextUID = self.nextUID
            print(
                f"Next UID: {' '.join(f'{x:02x}' for x in self.nextUID)}", file=logfile)

        if self.nextFilename is not None:
            self.mkvfile.info.nextFilename = self.nextFilename
            print(f"Next Filename: {self.nextFilename}", file=logfile)

        if self.segmentFamilies:
            state["segmentFamilies"] = self.segmentFamilies
            s = ", ".join(' '.join(f'{x:02x}' for x in segmentFamily)
                          for segmentFamily in self.segmentFamilies)

            if len(self.segmentFamilies) > 1:
                print(f"Segment Families: {s}", file=logfile)

            else:
                print(f"Segment Family: {s}", file=logfile)

        self.mkvfile.writingApp = self.writingApp

        if self.chapters:
            self.mkvfile.segment.chapters = self.chapters.prepare(logfile)

        if self.attachments:
            self.mkvfile.segment.attachments = self.attachments.prepare(
                logfile)

        if self.tags:
            self.mkvfile.segment.tags = self.tags.prepare(logfile)

    def _finalize(self, logfile):
        self.mkvfile.close()
        filesize = self.mkvfile.fileSize

        if self.targetsize:
            if filesize > self.targetsize:
                print(
                    f"Resulting file size: {h(filesize)} ({h(filesize - self.targetsize)} OVER target)", file=logfile)
            elif filesize == self.targetsize:
                print(
                    f"Resulting file size: {h(filesize)} (on target)", file=logfile)
            elif filesize > self.targetsize - 125*self.vtrack.duration*self.vtrack.avgfps/self.vtrack.rate:
                print(
                    f"Resulting file size: {h(filesize)} ({h(self.targetsize - filesize)} below target, within tolerance)", file=logfile)
            else:
                print(
                    f"Resulting file size: {h(filesize)} ({h(self.targetsize - filesize)} below target, additional pass recommended)", file=logfile)
        else:
            print(f"Resulting file size: {h(filesize)}", file=logfile)

        self.newoverhead["fileSize"] = filesize

        self.newoverhead["infoSize"] = self.mkvfile.segment.info.size()
        self.newoverhead["trackEntrySizes"] = [track.size()
                                               for track in self.mkvfile.tracks]

        if len(self.mkvfile.chapters):
            self.newoverhead["chaptersSize"] = self.mkvfile.chapters.size()

        else:
            self.newoverhead["chaptersSize"] = 0

        if len(self.mkvfile.attachments):
            self.newoverhead["attachmentsSize"] = self.mkvfile.attachments.size()

        else:
            self.newoverhead["attachmentsSize"] = 0

        self.newoverhead["cuesSize"] = self.mkvfile.segment.cues.size()
        self.newoverhead["tagsSize"] = self.mkvfile.tags.size()

        self.newoverhead["firstClusterOffset"] = self.mkvfile.segment.contentsOffset + \
            self.mkvfile.segment.firstClusterOffset
        self.newoverhead["lastClusterEnd"] = self.mkvfile.segment.contentsOffset + \
            self.mkvfile.segment.lastClusterEnd
        self.newoverhead["clusterCount"] = self.mkvfile.segment.clusterCount

        self.mkvfile = None

    def _mux(self, packet):
        track = self.tracks[packet.track_index]
        packet = matroska.Packet.copy(
            packet, trackNumber=track.trackEntry.trackNumber)
        packet.compression = track.compression

        if track.codec == "libx265":
            packet.referenceBlocks = None

        if track.type == "video":
            packet.duration = None

        self.mkvfile.mux(packet)

    @property
    def time_base(self):
        return QQ(1, 10**9)

    @property
    def dependencies(self):
        from .attachments import AttachmentRef
        dep = super().dependencies

        if self.attachments:
            for attachment in self.attachments:
                if isinstance(attachment.source, AttachmentRef):
                    dep.add(attachment.source.source)

        return dep

    def trackCols(self):
        from .pyqtgui.qtracklist import cols
        return cols

    def QtDlgExec(self, parent=None):
        from .pyqtgui.qmatroskaconfig import QMatroskaConfigDlg
        dlg = QMatroskaConfigDlg(parent)
        dlg.setOutputFile(self)

        return dlg.exec_()

    def removeDependency(self, dependency):
        super().removeDependency(dependency)

        if self.attachments and isinstance(dependency, BaseReader):
            for attachment in list(self.attachments):
                if isinstance(attachment.source, AttachmentRef):
                    if attachment.source.source is dependency:
                        self.attachments.remove(attachment)
 
    def validate(self):
        exceptions = super().validate()

        if self.attachments is not None:
            exceptions.extend(self.attachments.validate())

        return exceptions

    def createTrack(self, source, filters=None, encoder=None, name=None, language=None):
        existingUIDs = {track.trackUID for track in self.tracks}

        UID = random.randint(1, 2**64 - 1)

        while UID in existingUIDs:
            UID = random.randint(1, 2**64 - 1)

        return self.trackclass(source, filters, encoder, name=None, language=None, trackUID=UID)

    def loadOverhead(self):
        super().loadOverhead()

        try:
            clusterptsfile = open(
                f"{self.config.configstem}-{self.file_index}-clusterpts.dat", "rb")

            self.clusterPtsHist = ClusterPts.fromFile(clusterptsfile)
            clusterptsfile.close()

        except:
            self.clusterPtsHist = ClusterPts([])

    def saveOverhead(self):
        super().saveOverhead()

        if self.clusterPts:
            self.clusterPtsHist.ptsArrays.append(array(self.clusterPts))

            try:
                clusterptsfile = open(
                    f"{self.config.configstem}-{self.file_index}-clusterpts.dat", "wb")
                self.clusterPtsHist.toFile(clusterptsfile)
                clusterptsfile.close()

            except:
                pass
