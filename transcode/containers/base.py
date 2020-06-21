import transcode.util
import av
import threading
import time
import os
import sys

class BaseReader(object):
    pass

class BaseTrackReader(object):
    def frameIndexFromPts(self, pts, dir="+"):
        return transcode.util.search(self.pts, pts, dir)

    def keyIndexFromPts(self, pts, dir="-"):
        k = self.frameIndexFromPts(pts)
        pts = self.pts[k]
        return transcode.util.search(self.index[:, 0], pts, dir)

    @property
    def framecount(self):
        return len(self.pts)

    def iterFrames(self, start=0, end=None, whence="pts"):
        if whence == "framenumber":
            startindex = start
            startpts = self.pts[start]
            endindex = end and min(end, len(self.pts))

            try:
                endpts = end and self.pts[endindex]

            except IndexError:
                endpts = None

        elif whence == "pts":
            startindex = self.frameIndexFromPts(start)
            startpts = self.pts[startindex]

            try:
                endindex = end and self.frameIndexFromPts(end)
                endpts = end and self.pts[endindex]

            except IndexError:
                endindex = None
                endpts = None

        key_index = self.keyIndexFromPts(startpts)
        key_pts = self.index[key_index, 0]
        index = self.frameIndexFromPts(key_pts)

        packets = self.iterPackets(key_pts)

        decoder = av.CodecContext.create(self.codec, "r")

        iterpts = iter(self.pts[index:])

        try:
            if self.extradata:
                decoder.extradata = self.extradata

            framesdelivered = 0

            for packet in packets:
                avpacket = av.Packet(packet.data)
                avpacket.pts = packet.pts
                avpacket.time_base = self.time_base

                for frame, pts in zip(decoder.decode(avpacket), iterpts):
                    if pts < startpts:
                        continue

                    if endpts is not None and pts >= endpts:
                        raise StopIteration

                    framesdelivered += 1
                    frame.pts = pts
                    yield frame


            for frame in zip(decoder.decode(), iterpts):
                if pts < startpts:
                    continue

                if endpts is not None and pts >= endpts:
                    raise StopIteration

                framesdelivered += 1
                frame.pts = pts
                yield frame

        finally:
            decoder.close()

    @property
    def duration(self):
        return (self.pts[-1] + self.durations[-1])*self.time_base

    @property
    def avgfps(self):
        return self.framecount/self.duration

class BaseWriter(object):
    def __init__(self, outputfile, tracks=[], targetsize=None, configname="./"):
        self._configname = configname
        self.outputfile = outputfile
        self.tracks = tracks
        self.targetsize = targetsize

        for track in tracks:
            track.container = self

        self._stop = threading.Event()
        self._unpaused = threading.Event()
        self._muxing_started = threading.Event()

    @property
    def workingdir(self):
        if self.configname is not None:
            dir, name = os.path.split(self.configname)
            return os.path.abspath(dir)

    @property
    def configname(self):
        return self._configname

    @configname.setter
    def configname(self, value):
        oldpath = self.fulloutputfile
        self._configname = value
        self.outputfile = oldpath

    @property
    def outputfile(self):
        return self._outputfile

    @property
    def fulloutputfile(self):
        if self.workingdir is not None:
            return os.path.join(self.workingdir, self.outputfile)
        return self.outputfile

    @outputfile.setter
    def outputfile(self, value):
        if value == None:
            self._outputfile = None
            return
        if self.workingdir is not None:
            abspath = os.path.abspath(os.path.join(self.workingdir, value))
            relpath = os.path.relpath(abspath, self.workingdir)
            if relpath.startswith("../"):
                self._outputfile = abspath
            else:
                self._outputfile = relpath
        else:
            self._outputfile = value

    def multiplex(self, *iterators):
        iterators = list(iterators)
        packets = [None]*len(iterators)

        while any([iterator is not None for iterator in iterators]):
            for k, iterator in enumerate(iterators):
                if iterator is None:
                    continue

                if packets[k] is None:
                    self._unpaused.wait()

                    if self._stop.isSet():
                        break

                    try:
                        packets[k] = next(iterator)

                    except StopIteration:
                        iterators[k] = None

            ready_to_mux = [packet for packet in packets if packet is not None]

            if len(ready_to_mux) == 0:
                break

            packet = min(ready_to_mux, key=lambda packet: packet.pts)
            k = packets.index(packet)
            packets[k] = None
            yield packet

        for packet in ready_to_mux:
            if packet is not None:
                yield packet

    def createTranscodeThread(self, pass_=0, encoderoverrides=[], logfile=None, notifymux=None,
                 notifyfinish=None, notifyerror=None, notifyvencode=None, autostart=True):
        return threading.Thread(target=self.transcode, args=(pass_, encoderoverrides, logfile,
                                                notifymux, notifyfinish, notifyerror, notifyvencode))

    def transcode(self, pass_=0, encoderoverrides=[], logfile=None, notifymux=None,
                 notifyfinish=None, notifyerror=None, notifyvencode=None):
        self._unpaused.set()

        try:
            if self._muxing_started.isSet():
                raise RuntimeError("Muxer thread has already run.")

            if logfile is not None:
                strftime = time.strftime("%A, %B %-d, %Y, %-I:%M:%S %P %Z")
                print(f"--- Transcode started: {strftime} ---", file=logfile)
                logfile.flush()

            self._muxing_started.set()
            self._transcode(pass_, encoderoverrides, logfile, notifymux,
                 notifyfinish, notifyerror, notifyvencode)

        except:
            cls, exc, tb = sys.exc_info()
            print(traceback.format_exception(cls, exc, tb), file=sys.stderr)

            if logfile is not None:
                print(traceback.format_exception(cls, exc, tb), file=logfile)
                strftime = time.strftime("%A, %B %-d, %Y, %-I:%M:%S %P %Z")
                print(f"--- Transcode failed: {strftime} ---", file=logfile)

            if callable(notifyerror):
                notifyerror(exc, tb)

            raise

        else:
            if logfile is not None:
                strftime = time.strftime("%A, %B %-d, %Y, %-I:%M:%S %P %Z")

                if self._stop.isSet():
                    print(f"--- Transcode cancelled: {strftime} ---", file=logfile)

                else:
                    print(f"--- Transcode completed: {strftime} ---", file=logfile)

        finally:
            self._muxing_started.clear()
            self._stop.clear()

    def _transcode(self, pass_=0, encoderoverrides=[], logfile=None, notifymux=None,
                 notifyfinish=None, notifyerror=None, notifyvencode=None):

        self.open(logfile)
        iterators = self.prepare(pass_, encoderoverrides, logfile, notifyvencode)

        try:
            for packet in self.multiplex(*packets):
                self._mux(packet)

                if callable(notifymux):
                    notifymux(packet)

        finally:
            self.wrapup(logfile)

    def wrapup(self, logfile=None):
        pass

    def open(self, logfile=None):
        try:
            self._open()

        except:
            if logfile is not None:
                print(f"FAILED to open {self.fulloutputfile}", file=logfile)

            raise

        else:
            if logfile is not None:
                print(f"Output file: {self.fulloutputfile}", file=logfile)

    def _open(self):
        raise NotImplementedError

    def prepare(self, pass_=0, encoderoverrides=[], logfile=None, notifyvencode=None):
        if logfile is not None:
            if self.targetsize is not None and pass_ != 1:
                print(f"Target file size: {transcode.util.h(self.targetsize)}", file=logfile)

            if pass_:
                print(f"Pass: {pass_:d}", file=logfile)

            logfile.flush()

        return self._prepare(pass_, encoderoverrides, logfile, notifyvencode)

    def _prepare(self, pass_, encoderoverrides=[], logfile=None, notifyvencode=None):
        vencoder_override = dict()

        if self.targetsize is not None and pass_ != 1:
            bitrate = self.bitrateFromTargetSize()
            vencoder_override.update(bit_rate=1000*bitrate)

        if pass_ == 1:
            vencoder_override.update(crf=22)

        if pass_:
            stats = f"{self.nameroot}-{self.vtrack.stream_index:d}-{self.vtrack.encoder_config.codec_name}-multipass.log"
            vencoder_override.update(pass_=pass_, stats=stats)

        iterators = []

        for k, (track, encoder_override) in enumerate(zip_longest(self.tracks, encoder_overrides)):
            if track is self.vtrack:
                if encoder_override is not None:
                    encoder_override.update(vencoder_override)

                else:
                    encoder_override = vencoder_override

                iterators.append(track.iterPackets(duration=self.duration, notifyencode=notifyvencode, logfile=logfile, **encoder_override))

            else:
                iterators.append(track.iterPackets(duration=self.duration, logfile=logfile, **encoder_override))

        return iterators

    def bitrateFromTargetSize(self):
        overhead = 65536
        overheadbitrate = 0

        for track in self.tracks:
            (overheaddelta, overheadbitratedelta) = track.getOverhead()

            overhead += overheaddelta

            if track.bitrate is not None and track is not self.vtrack:
                overheadbitrate += overheadbitratedelta

        targetsize = self.targetsize - overhead
        bitrate = targetsize/self.duration/125 - overheadbitrate
        

        return 

class BaseTrackWriter(object):
    def __init__(self, source, encoder=None, filters=None, container=None):
        self.source = source
        self.encoder = encoder
        self.filters = filters
        self.container = container

    @property
    def type(self):
        return self.source.type

    @property
    def width(self):
        if self.encoder and self.filters:
            return self.filters.width

        return self.source.width

    @property
    def height(self):
        if self.encoder and self.filters:
            return self.filters.height

        return self.source.height

    @property
    def sar(self):
        if self.encoder and self.filters:
            return self.filters.sar

        return self.source.sar

    @property
    def dar(self):
        if self.encoder and self.filters:
            return self.filters.dar

        return self.source.dar

    @property
    def defaultDuration(self):
        if self.encoder:
            if self.type == "audio":
                pass
            elif self.filters:
                return self.filters.defaultDuration

        return self.source.defaultDuration

    @property
    def duration(self):
        if self.encoder and self.filters:
            return self.filters.duration

        return self.source.duration

    @property
    def avgfps(self):
        return self.framecount/self.duration
