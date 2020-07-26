from .. import basereader
import matroska
import numpy
import av
from fractions import Fraction as QQ
import os
from ...util import Packet

codecs = {
        "V_MPEGH/ISO/HEVC": "hevc",
        "V_MPEG2": "mpeg2video",
        "A_AC3": "ac3",
        "A_DTS": "dts",
        "V_MS/VFW/FOURCC": "vc1",
        "S_TEXT/ASS": "ass",
        "S_VOBSUB": "dvdsub",
        "V_MPEG4/ISO/AVC": "h264",
        "S_HDMV/PGS": "pgssub"
    }

class Track(basereader.Track):
    def __getstate__(self):
        state = super().__getstate__() or OrderedDict()
        state["index"] = self.index
        state["sizes"] = self.sizes
        state["durations"] = self.durations
        return state

    def __setstate__(self, state):
        self.index = state.get("index")
        self.sizes = state.get("sizes")
        self.durations = state.get("durations")
        super().__setstate__(state)

    @property
    def trackEntry(self):
        return self.container.mkvfile.tracks[self.track_index]

    @property
    def name(self):
        return self.trackEntry.name

    @property
    def language(self):
        return self.trackEntry.language

    @property
    def trackNumber(self):
        return self.trackEntry.trackNumber

    @property
    def trackUID(self):
        return self.trackEntry.trackUID

    @property
    def codec(self):
        return codecs.get(self.trackEntry.codecID)

    @property
    def width(self):
        if self.trackEntry.video:
            return self.trackEntry.video.pixelWidth

    @property
    def height(self):
        if self.trackEntry.video:
            return self.trackEntry.video.pixelHeight

    @property
    def bitdepth(self):
        if self.trackEntry.audio:
            return self.trackEntry.audio.bitDepth

    @property
    def rate(self):
        if self.trackEntry.audio:
            return int(self.trackEntry.audio.samplingFrequency)

        if self.trackEntry.video:
            return 10**9/self.defaultDuration

    @property
    def channels(self):
        if self.trackEntry.audio:
            return self.trackEntry.audio.channels

    @property
    def layout(self):
        if self.channels == 1:
            return "mono"

        if self.channels == 2:
            return "stereo"

        if self.channels == 6:
            return "5.1(side)"

        if self.channels == 8:
            return "7.1"

    @property
    def defaultDuration(self):
        if isinstance(self.trackEntry.defaultDuration, int):
            q, r = divmod(self.trackEntry.defaultDuration, 1000)

            if r % 111 in (0, 1):
                """Possible repeating digit. Will assume as such."""
                return 1000*q + r + QQ(r//111, 9)

            return self.trackEntry.defaultDuration

    @property
    def sar(self):
        if self.trackEntry.video:
            return self.dar/QQ(self.trackEntry.video.pixelWidth, self.trackEntry.video.pixelHeight)

    @property
    def dar(self):
        if self.trackEntry.video:
            if self.trackEntry.video.displayWidth and self.trackEntry.video.displayHeight:
                return QQ(self.trackEntry.video.displayWidth, self.trackEntry.video.displayHeight)

            return QQ(self.trackEntry.video.pixelWidth, self.trackEntry.video.pixelHeight)

    @property
    def extradata(self):
        return self.trackEntry.codecPrivate

    @property
    def type(self):
        if self.trackEntry.trackType == 1:
            return "video"

        elif self.trackEntry.trackType == 2:
            return "audio"

        elif self.trackEntry.trackType == 17:
            return "subtitle"

        else:
            raise ValueError(f"Unsupported TrackType: {self.trackEntry.trackType}")

    def iterPackets(self, start=0, whence="pts"):
        if whence == "pts":
            startpts = start
            start = self.keyIndexFromPts(start)

        if whence == "seconds":
            startpts = int(10**9*start)
            start = self.keyIndexFromPts(startpts)

        elif whence == "framenumber":
            startpts = self.pts[start]

        start_pts, startClusterPosition, startBlockPosition = self.index[start]
        packets = self.container.demux(startClusterPosition=startClusterPosition,
                    startBlockPosition=startBlockPosition, trackNumber=self.trackNumber)
        pkts_list = []

        for packet in packets:
            if packet.keyframe:
                if packet.pts > startpts:
                    for pkt in pkts_list:
                        yield pkt

                pkts_list.clear()
                pkts_list.append(packet)

            elif len(pkts_list):
                pkts_list.append(packet)

        for pkt in pkts_list:
            yield pkt

    @property
    def time_base(self):
        return self.container.time_base

class MatroskaReader(basereader.BaseReader):
    trackclass = Track
    extensions = (".mkv", ".mka", ".mks")
    fmtname = "Matroska"

    def _open(self):
        self.mkvfile = matroska.MatroskaFile(self.inputpath, "r")

    def _populatetracks(self):
        self.tracks = []

        while len(self.tracks) < len(self.mkvfile.tracks):
            self.tracks.append(Track())

        for track in self.tracks:
            track.container = self

    def scan(self, notifystart=None, notifyprogress=None, notifyfinish=None):
        progress = 0

        tracksDict = {track.trackNumber: track for track in self.tracks if track.trackEntry.trackType in (1, 2, 17)}
        trackPts = {track.trackNumber: [] for track in self.tracks if track.trackEntry.trackType in (1, 2, 17)}
        trackIndices = {track.trackNumber: [] for track in self.tracks if track.trackEntry.trackType in (1, 2, 17)}

        for cluster in self.mkvfile.segment.iterClusters():
            clusterOffset = cluster.offsetInParent

            for (blockOffset, size, trackNumber, pts, duration, keyframe, invisible,
                    discardable, referencePriority, referenceBlocks) in cluster.scan():
                index = trackIndices[trackNumber]
                trackEntry = tracksDict[trackNumber]
                ptslist = trackPts[trackNumber]

                if trackEntry.codec == "vc1" and (keyframe or not discardable) \
                        and len(index) and index[-1][0] == -1:
                    _, prevClusterOffset, prevBlockOffset = index[-1]
                    index[-1] = (ptslist[-1][0], prevClusterOffset, prevBlockOffset)

                if keyframe or len(index) == 0:
                    if trackEntry.codec == "vc1":
                        index.append((-1, clusterOffset, blockOffset))

                    else:
                        index.append((pts, clusterOffset, blockOffset))

                ptslist.append((pts, size, duration))

        for track in self.tracks:
            if track.trackNumber not in trackIndices:
                continue

            if trackIndices[track.trackNumber][-1][0] == -1:
                del trackIndices[track.trackNumber][-1]

            track.index = numpy.array(sorted(trackIndices[track.trackNumber]))
            track.pts, track.sizes, track.durations = numpy.array(sorted(trackPts[track.trackNumber])).transpose()

    @property
    def chapters(self):
        return self.mkvfile.chapters

    @property
    def attachments(self):
        return self.mkvfile.attachments

    @property
    def tags(self):
        return self.mkvfile.tags

    @property
    def time_base(self):
        return QQ(1, 10**9)

    def demux(self, startClusterPosition=None, startBlockPosition=None, trackNumber=None):
        track_index = [track.trackNumber for track in self.tracks].index(trackNumber)

        for packet in self.mkvfile.demux(startClusterPosition=startClusterPosition,
                    startBlockPosition=startBlockPosition, trackNumber=trackNumber):
            yield Packet(data=packet.data, pts=packet.pts, duration=packet.duration,
                         time_base=self.time_base, keyframe=packet.keyframe,
                         invisible=packet.invisible, discardable=packet.discardable,
                         referenceBlocks=packet.referenceBlocks, track_index=track_index)

