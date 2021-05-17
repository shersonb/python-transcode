from ..base import EncoderContext
from ..base import EncoderConfig
import regex
import os
import fcntl
from fractions import Fraction as QQ
from ...util import Packet
from collections import OrderedDict
import time
import lzma

x265strparams = {"stats", "tune", "qpfile", "zones", "scaling-list",
                 "lambda-file", "deblock", "preset", "level-idc", "input-csp", "fps", "sar",
                 "deblock", "display-window", "overscan", "videoformat", "range",
                 "colorprim", "transfer", "colormatrix", "master-display", "max-cll",
                 "nalu-file", "dolby-vision-profile", "log-level", "asm", "pools", "numa-pools",
                 "interlace", "analysis-save", "analysis-load", "analysis-reuse-file",
                 "refine-mv-type", "me", "merange", "hme-search", "hme-range"
                 }
x265intparams = {"qp", "bitrate", "pass", "slices", "qpmin", "qpmax", "qpstep", "max-qp-delta",
                 "cbqpoffs", "crqpoffs", "scenecut-window", "vbv-bufsize", "vbv-maxrate",
                 "aq-mode", "qg-size", "min-keyint", "keyint", "scenecut", "selective-sao",
                 "preset", "level-idc", "input-csp", "fps", "sar", "videoformat", "colorprim",
                 "transfer", "colormatrix", "chromaloc", "min-luma", "max-luma", "atc-sei",
                 "pic-struct", "hash", "log2-max-poc-lsb", "log-level", "frame-threads",
                 "interlace", "dup-threshold", "chunk-start", "chunk-end", "ref", "rd", "ctu",
                 "min-cu-size", "limit-refs", "rskip", "rskip-edge-threshold", "scale-factor",
                 "analysis-save-reuse-level", "analysis-load-reuse-level", "refine-intra",
                 "refine-ctu-distortion", "refine-inter", "refine-mv", "rdoq-level", "limit-tu"
                 "tu-intra-depth", "tu-inter-depth", "nr-intra", "nr-inter", "rdpenalty", "me",
                 "max-tu-size", "dynamic-rd", "max-merge", "subme", "merange",
                 "hme-search", "radl", "ctu-info", "rc-lookahead", "gop-lookahead",
                 "lookahead-slices", "lookahead-threads", "b-adapt", "bframes",
                 "bframe-bias", "force-flush"
                 }
x265floatparams = {"crf-min", "crf-max", "qblur", "cplxblur", "vbv-init", "vbv-end",
                   "vbv-end-fr-adj", "aq-strength", "qp-adaptation-range", "crf-max", "qcomp",
                   "ipratio", "pbratio", "scenecut-bias", "hist-threshold", "max_ausize_factor",
                   "level-idc", "fps", "psy-rd", "psy-rdoq", "bitrate"}
x265boolparams = {"lossless", "scenecut-aware-qp", "strict-cbr", "const-vbv", "cutree",
                  "aq-motion", "open-gop", "scenecut", "hist-scenecut", "rc-grain", "high-tier",
                  "signhide", "deblock", "sao", "sao-non-deblock", "limit-sao", "hevc-aq",
                  "deblock", "cll", "hdr10", "hdr10-opt", "dhdr10-info", "dhdr10-opt", "annexb",
                  "repeat-headers", "aud", "hrd", "hrd-concat", "info", "temporal-layers",
                  "vui-hrd-info", "opt-qp-pps", "opt-ref-list-length-pps", "idr-recovery-sei",
                  "multi-pass-opt-rps", "opt-cu-delta-qp", "single-sei", "lowpass-dct", "ssim",
                  "psnr", "asm", "wpp", "pmode", "pme", "copy-pic", "frame-dup", "field",
                  "allow-non-conformance", "uhd-bd", "limit-modes", "rect", "amp", "tskip",
                  "early-skip", "splitrd-skip", "fast-intra", "b-intra", "cu-lossless", "tskip-fast",
                  "rd-refine", "dynamic-refine", "rdoq-level", "ssim-rd", "temporal-mvp",
                  "weightp", "weightb", "analyze-src-pics", "hme", "strong-intra-smoothing",
                  "constrained-intra", "intra-refresh", "b-pyramid", "fades", "slow-firstpass"
                  }

x265colonrationalparams = {"sar", }
x265slashrationalparams = {"fps", }
x265rationalparams = set.union(
    x265colonrationalparams, x265slashrationalparams)
x265params = set.union(x265strparams, x265intparams, x265floatparams,
                       x265boolparams, x265rationalparams)


def _convert_dict(d, stripnones=True):
    for oldkey in list(d.keys()):
        newkey = oldkey.rstrip("_").replace("_", "-")

        if newkey not in x265params:
            raise ValueError(f"Not a valid x265 parameter: {newkey}")

        value = d.pop(oldkey)

        if value is None:
            if not stripnones:
                d[newkey] = None

            continue

        if (isinstance(value, str) and newkey in x265strparams) or \
                (isinstance(value, int) and not isinstance(value, bool) and newkey in x265intparams) or \
                (isinstance(value, float) and newkey in x265floatparams) or \
                (isinstance(value, bool) and newkey in x265boolparams) or \
                (isinstance(value, QQ) and newkey in x265rationalparams):
            d[newkey] = value

        elif newkey in x265rationalparams:
            d[newkey] = QQ(value)

        elif newkey in x265floatparams:
            d[newkey] = float(value)

        elif newkey in x265intparams:
            d[newkey] = int(value)

        elif newkey in x265boolparams:
            d[newkey] = bool(value)

        elif newkey in x265strparams:
            d[newkey] = str(value)


def quote(s):
    return f"{s}".replace("\\", "\\\\").replace(":", "\\:")


class libx265EncoderContext(EncoderContext):
    _stats_backup_amtime = None
    _stats_backup = None

    def open(self):
        self._t0 = time.time()

        if self._pass in (1, 3):
            self._readstats()

        # if self._pass == 1:
            # self._readcutree()

        self._encoder.open()
        self._isopen = True

        try:
            while len(self._packets) == 0:
                self._sendframe()

        except Exception:
            self.stop()
            self.close()
            raise

        packet = self._packets[0]

        configurationVersion = 0b00000001

        general_profile_space = 0b00
        general_tier_flag = 0b1
        general_profile_idc = 0b00001

        general_profile_compatibility_flags = 0b01100000000000000000000000000000
        general_constraint_indicator_flags = 0b100100000000000000000000000000000000000000000000
        general_level_idc = 0b10010110

        min_spatial_segmentation_idc = 0b000000000000
        parallelismType = 0b00
        chromaFormat = 0b01
        bitDepthLumaMinus8 = 0b000
        bitDepthChromaMinus8 = 0b000
        avgFrameRate = 0b0000000000000000

        constantFrameRate = 0b00
        numTemporalLayers = 0b001
        temporalIdNested = 0b1
        lengthSizeMinusOne = 0b11

        data = configurationVersion.to_bytes(1, "big")
        data += (general_profile_space << 6 | general_tier_flag <<
                 5 | general_profile_idc).to_bytes(1, "big")
        data += general_profile_compatibility_flags.to_bytes(4, "big")
        data += general_constraint_indicator_flags.to_bytes(6, "big")
        data += general_level_idc.to_bytes(1, "big")
        data += (0b1111 << 12 | min_spatial_segmentation_idc).to_bytes(2, "big")
        data += (0b111111 << 2 | parallelismType).to_bytes(1, "big")
        data += (0b111111 << 2 | chromaFormat).to_bytes(1, "big")
        data += (0b11111 << 3 | bitDepthLumaMinus8).to_bytes(1, "big")
        data += (0b11111 << 3 | bitDepthChromaMinus8).to_bytes(1, "big")
        data += avgFrameRate.to_bytes(2, "big")
        data += (constantFrameRate << 6 | numTemporalLayers << 3 |
                 temporalIdNested << 2 | lengthSizeMinusOne).to_bytes(1, "big")

        data += int.to_bytes(4, 1, "big")

        pattern = b"(?:\\x00{2,3}\\x01)([\\x00-\\xff]+?)"
        nal1, nal2, nal3, nal4, pktdata = regex.findall(
            b"^" + 5*pattern + b"$", packet.to_bytes())[0]

        NALtypes = [0b100000, 0b100001, 0b100010, 0b100111]

        for naltype, p in zip(NALtypes, (nal1, nal2, nal3, nal4)):
            data += naltype.to_bytes(1, "big")
            data += int.to_bytes(1, 2, "big")
            data += len(p).to_bytes(2, "big")
            data += p

        self._encoder.extradata = data

    def _readstats(self):
        stats = self._stats or "x265_2pass.log"

        if os.path.isfile(stats):
            with open(stats, "rb") as f:
                self._stats_backup = f.read()

            stat = os.stat(stats)
            self._stats_backup_amtime = (stat.st_atime, stat.st_mtime)

    def _restorestats(self):
        stats = self._stats or "x265_2pass.log"

        if self._stats_backup:
            with open(stats, "wb") as f:
                f.write(self._stats_backup)

            os.utime(stats, self._stats_backup_amtime)

    def _backupstats(self, t):
        stats = self._stats or "x265_2pass.log"
        backupstats = f"{stats}-backup-{t.tm_year:4d}.{t.tm_mon:02d}.{t.tm_mday:02d}-{t.tm_hour:02d}.{t.tm_min:02d}.{t.tm_sec:02d}.xz"

        try:
            f = open(stats, "rb")

        except Exception:
            return

        try:
            g = lzma.LZMAFile(backupstats, "wb", preset=9 |
                              lzma.PRESET_EXTREME)

        except Exception:
            f.close()
            return

        try:
            while True:
                data = f.read(65536)

                if len(data) == 0:
                    break

                g.write(data)

        finally:
            f.close()
            g.close()

        stat = os.stat(stats)
        os.utime(backupstats, (stat.st_atime, stat.st_mtime))

    def _backupcutree(self, t):
        stats = self._stats or "x265_2pass.log"
        stats = f"{stats}.cutree"
        backupstats = f"{stats}-backup-{t.tm_year:4d}.{t.tm_mon:02d}.{t.tm_mday:02d}-{t.tm_hour:02d}.{t.tm_min:02d}.{t.tm_sec:02d}"

        # try:
        #shutil.copyfile(stats, backupstats)

        # except:
        # return

        f = open(stats, "rb")
        g = open(backupstats, "wb")

        try:
            while True:
                data = f.read(65536)

                if len(data) == 0:
                    break

                g.write(data)

        finally:
            f.close()
            g.close()

        stat = os.stat(stats)
        os.utime(backupstats, (stat.st_atime, stat.st_mtime))

    def close(self):
        try:
            flag = fcntl.fcntl(self._rfd, fcntl.F_GETFL)

        except OSError:
            pass

        else:
            fcntl.fcntl(self._rfd, fcntl.F_SETFL, flag & ~os.O_NONBLOCK)

        os.close(self._wfd)
        super().close()

        while self.procStats():
            continue

        os.close(self._rfd)

        N = sum(self._pktCount.values())

        if N > 0:
            Size = sum(self._pktSizeSums.values())
            avgqp = sum(self._pktQPSums.values())/N

            for s in "IPB":
                n = self._pktCount[s]
                qpsum = self._pktQPSums[s]
                size = self._pktSizeSums[s]

                if n > 0:
                    print(
                        f"    Frame {s}:{n: 8,d}, Avg QP:{qpsum/n: 5,.2f}  kb/s: {float(self._rate)*size/n/125:,.2f}", file=self._logfile)

                else:
                    print(
                        f"    Frame {s}:{n: 8,d}, Avg QP:  ---  kb/s: ---", file=self._logfile)

            print(f"    Encoded {N: 8,d} frames in {self._t1 - self._t0:,.2f}s ({N/(self._t1 - self._t0):,.2f} fps), Avg QP:{avgqp: 5,.2f}  kb/s: {float(self._rate)*Size/N/125:,.2f}", file=self._logfile)

        else:
            print(
                f"    Encoded {N: 8,d} frames in {self._t1 - self._t0:,.2f}s ({N/(self._t1 - self._t0):,.2f} fps), Avg QP: ---  kb/s: ---", file=self._logfile)

        if self._success:
            t = time.localtime()

            if self._pass in (1, 3):
                self._backupstats(t)

            if self._pass == 1:
                self._backupcutree(t)

        else:
            if self._pass in (1, 3):
                self._restorestats()

            # if self._pass == 1:
                # self._restorecutree()

    def procStats(self):
        n = 0

        while True:
            data = self._rf.read(4096)
            n += len(data)

            if len(data) == 0:
                break

            self._statsbuffer += data

        *lines, self._statsbuffer = self._statsbuffer.split("\n")

        for statsline in lines:
            match = regex.match(self._statspattern, statsline, flags=regex.I)

            if match:
                md = match.groupdict()
                self._pktQPSums[md["pict_type"].upper()] += float(md["qp"])
                self._pktSizeSums[md["pict_type"].upper()
                                  ] += int(md["bits"])//8
                self._pktCount[md["pict_type"].upper()] += 1

        return n

    def __next__(self):
        if not self._isopen and not self._noMoreFrames:
            self.open()

        while len(self._packets) == 0:
            try:
                self._sendframe()

            except StopIteration:
                self.procStats()
                raise

            finally:
                self._t1 = time.time()

        self.procStats()
        packet = self._packets.popleft()

        if packet.is_keyframe:
            pattern = b"(?:\\x00{2,3}\\x01)([\\x00-\\xff]+?)"
            nal1, nal2, nal3, nal4, data = regex.findall(
                b"^" + 5*pattern + b"$", packet.to_bytes())[0]

        else:
            data = packet.to_bytes()[4:]

        self._packetsEncoded += 1
        self._streamSize += len(data) - 4
        self._t1 = time.time()
        packet = Packet(data=len(data).to_bytes(4, "big")+data, pts=packet.pts, duration=packet.duration,
                        keyframe=packet.is_keyframe, time_base=packet.time_base)
        return packet

    def __iter__(self):
        return self

    def __init__(self, framesource,
                 # Pyav encoder context options
                 width, height, sample_aspect_ratio=1, rate=QQ(24000, 1001), pix_fmt="yuv420p", time_base=None,
                 preset=None, tune=None, forced_idr=None,

                 # Quality, rate control and rate distortion options
                 bitrate=None, qp=None, crf=None, lossless=None,


                 # python-transcode
                 notifyencode=None, logfile=None, **x265params):

        self._rate = rate
        _convert_dict(x265params)

        kwargs = dict(width=width, height=height, sample_aspect_ratio=sample_aspect_ratio,
                      rate=rate, pix_fmt=pix_fmt, time_base=time_base)
        options = {}

        if crf:
            options["crf"] = f"{crf:.2f}"
            print(f"        crf={crf:.2f}", file=logfile)

        elif bitrate:
            kwargs["bit_rate"] = int(1000*bitrate)
            print(f"        bitrate={bitrate:,.2f}kbps", file=logfile)

        elif qp:
            x265params["qp"] = qp
            print(f"        qp={qp}", file=logfile)

        elif lossless:
            x265params["lossless"] = True
            print("        lossless", file=logfile)

        if preset:
            options["preset"] = preset
            print(f"        preset={preset}", file=logfile)

        if tune:
            options["tune"] = tune
            print(f"        tune={tune}", file=logfile)

        #print(kwargs, x265params)
        self._rfd, self._wfd = os.pipe()
        self._rf = os.fdopen(self._rfd, "r")
        self._wf = os.fdopen(self._wfd, "w")
        flag = fcntl.fcntl(self._rfd, fcntl.F_GETFL)
        fcntl.fcntl(self._rfd, fcntl.F_SETFL, flag | os.O_NONBLOCK)

        if rate:
            x265params["fps"] = rate

        x265params = OrderedDict(
            [("preset", None), ("tune", None), ("pass", None), ("stats", None)], **x265params)

        x265params["csv"] = f"/dev/fd/{self._wfd}"
        x265params["csv-log-level"] = 1

        L = []

        for key, value in x265params.items():
            if value is True:
                L.append(f"{key}=1")
                print(f"        {key}", file=logfile)

            elif value is False:
                L.append(f"{key}=0")
                print(f"        no-{key}", file=logfile)

            elif isinstance(value, str):
                L.append(f"{key}={quote(value)}")

                if key != "csv":
                    print(f"        {key}={value}", file=logfile)

            elif isinstance(value, QQ):
                if key in x265colonrationalparams:
                    L.append(f"{key}={value.numerator}\\:{value.denominator}")

                if key in x265slashrationalparams:
                    L.append(f"{key}={value.numerator}/{value.denominator}")

                print(
                    f"        {key}={value.numerator}/{value.denominator}", file=logfile)

            elif value is not None:
                L.append(f"{key}={value}")

                if key != "csv-log-level":
                    print(f"        {key}={value}", file=logfile)

        if L:
            options["x265-params"] = ":".join(L)

        if options:
            kwargs["options"] = options

        self._statspattern = r"(?P<encodeorder>\d+),"\
            r"\s+(?P<pict_type>[IBP])-SLICE,"\
            r"\s*(?P<displayorder>\d+),"\
            r"\s*(?P<qp>\d+(?:\.\d+)?),"\
            r"\s*(?P<bits>\d+),"\
            r"\s*(?P<scenecut>[01]),"\

        # if bitrate is None and qp is None and lossless is None:
        #self._statspattern += r"\s*(?P<ratefactor>\d+(?:\.\d+)?),"\
        # r"\s*(?P<bufferfill>\d+(?:\.\d+)?),"\
        # r"\s*(?P<bufferfillfinal>\d+(?:\.\d+)?),"

        # if x265params.get("ssim"):
        #self._statspattern += r"\s*(?P<ssim>\d+(?:\.\d+)?),"\
        # r"\s*(?P<ssimdb>\d+(?:\.\d+)?),"\

        #self._statspattern += r"(?P<latency>\d+),"\
        # r"\s*(?P<refs1>(?:-|[\s\d]+?))\s*,"\
        # r"\s*(?P<refs2>(?:-|[\s\d]+?))\s*,"

        self._statsbuffer = ""
        self._pktCount = {s: 0 for s in "IBP"}
        self._pktSizeSums = {s: 0 for s in "IBP"}
        self._pktQPSums = {s: 0 for s in "IBP"}
        self._pts = {}
        self._pass = x265params.get("pass")
        self._stats = x265params.get("stats")

        super().__init__("libx265", framesource,
                         notifyencode=notifyencode, logfile=logfile, **kwargs)


class libx265Config(EncoderConfig):
    format = None
    codec = "libx265"

    def __init__(self, bitrate=None, qp=None, crf=None, lossless=None,
                 preset="medium", tune=None, forced_idr=None, **kwargs):

        if sum([bitrate is not None, qp is not None, crf is not None, bool(lossless)]) > 1:
            raise ValueError(
                "Must specify no more than one of the following: bitrate, qp, crf, or lossless=True.")

        kwargs.update(bitrate=bitrate, qp=qp, lossless=lossless,
                      preset=preset, tune=tune)
        _convert_dict(kwargs)
        self.x265params = kwargs
        self.forced_idr = forced_idr
        self.crf = crf

    def __reduce__(self):
        return type(self), (), self.__getstate__()

    def __getstate__(self):
        state = OrderedDict()
        if self.bitrate is not None:
            state["bitrate"] = self.bitrate

        if self.crf is not None:
            state["crf"] = self.crf

        if self.qp is not None:
            state["qp"] = self.qp

        if self.lossless is not None:
            state["lossless"] = self.lossless

        if self.forced_idr is not None:
            state["forced_idr"] = self.forced_idr

        state.update(self.x265params)
        return state

    def __setstate__(self, state):
        self.forced_idr = state.get("forced_idr")
        self.crf = state.get("crf")
        self.x265params = {key: value for (key, value) in state.items(
        ) if key in x265params and value is not None}

    def __dir__(self):
        dir = super().__dir__()
        for x265paramname in x265params:
            attrname = x265paramname.replace("-", "_")

            if attrname == "pass":
                attrname = "pass_"

            if attrname not in dir:
                dir.append(attrname)

        dir.sort()
        return dir

    def __getattribute__(self, attr):
        x265paramname = attr.rstrip("_").replace("_", "-")

        if x265paramname in x265params:
            return self.x265params.get(x265paramname)

        return object.__getattribute__(self, attr)

    def __delattr__(self, attr):
        x265paramname = attr.rstrip("_").replace("_", "-")

        if x265paramname in x265params and x265paramname in self.x265params:
            del self.x265params[x265paramname]
            return

        return object.__delattr__(self, attr)

    def __setattr__(self, attr, value):
        x265paramname = attr.rstrip("_").replace("_", "-")

        if value is None and x265paramname in x265params:
            self.x265params[x265paramname] = value

        elif (isinstance(value, str) and x265paramname in x265strparams) or \
                (isinstance(value, int) and not isinstance(value, bool) and x265paramname in x265intparams) or \
                (isinstance(value, float) and x265paramname in x265floatparams) or \
                (isinstance(value, bool) and x265paramname in x265boolparams) or \
                (isinstance(value, QQ) and x265paramname in x265rationalparams):
            self.x265params[x265paramname] = value

        elif x265paramname in x265rationalparams:
            self.x265params[x265paramname] = QQ(value)

        elif x265paramname in x265floatparams:
            self.x265params[x265paramname] = float(value)

        elif x265paramname in x265intparams:
            self.x265params[x265paramname] = int(value)

        elif x265paramname in x265boolparams:
            self.x265params[x265paramname] = bool(value)

        elif x265paramname in x265strparams:
            self.x265params[x265paramname] = str(value)

        return object.__setattr__(self, attr, value)
        # return super().__setattr__(attr, value)

    def create(self, framesource, width, height, sample_aspect_ratio=1,
               rate=None, pix_fmt="yuv420p", time_base=None,
               bitrate=None, qp=None, crf=None, lossless=None,
               pass_=0, slow_firstpass=False, stats=None,
               notifyencode=None, logfile=None, **override):

        if pass_:
            override["pass"] = pass_

            if slow_firstpass is not None:
                override["slow_firstpass"] = slow_firstpass

            if stats:
                override["stats"] = stats

        if bitrate is not None or qp is not None or crf is not None or lossless is not None:
            override.update(bitrate=bitrate, qp=qp, lossless=lossless)

        else:
            crf = self.crf

        _convert_dict(override, stripnones=False)
        x265params = self.x265params.copy()
        x265params.update(override)
        # print("$", dict(framesource=framesource, width=width, height=height, rate=rate, pix_fmt=pix_fmt, time_base=time_base,
        # crf=crf, notifyencode=notifyencode, logfile=logfile, **x265params))
        return libx265EncoderContext(framesource, width, height, sample_aspect_ratio, rate,
                                     pix_fmt, time_base, crf=crf, notifyencode=notifyencode, logfile=logfile,
                                     **x265params)

    def copy(self):
        return type(self)(crf=self.crf, forced_idr=self.forced_idr, **self.x265params)

    @property
    def QtDlgClass(self):
        from .pyqtgui import x265ConfigDlg
        return x265ConfigDlg
