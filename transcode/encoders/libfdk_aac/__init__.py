from ..base import EncoderContext
from ..base import EncoderConfig


rates = [96000, 88200, 64000, 48000, 44100, 32000,
         24000, 22050, 16000, 12000, 11025, 8000]
layouts = [None, "mono", "stereo", "3.0", "4.0", "5.0", "5.1"]


class libfdk_aacEncoderContext(EncoderContext):
    def __init__(self, framesource, bitrate=640, rate=48000, layout="5.1",
                 notifyencode=None, logfile=None, **kwargs):
        super().__init__(
            "libfdk_aac", framesource, bit_rate=int(bitrate*1000),
            rate=rate, layout=layout, format="s16",
            notifyencode=notifyencode, logfile=logfile, **kwargs)

    def open(self):
        self._encoder.open()
        self._isopen = True

        t = 2

        if self._encoder.rate in rates:
            r = rates.index(self._encoder.rate)

        else:
            r = 15

        if self._encoder.layout.name in layouts:
            la = layouts.index(self._encoder.layout.name)

        else:
            la = 0

        if r == 15:
            data = (t << 35 | r << 31
                    | self._encoder.rate << 7
                    | la << 3).to_bytes(5, "big")

        else:
            data = (t << 11 | r << 7 | la << 3).to_bytes(2, "big")

        if self._encoder.layout.name == "7.1(wide)":
            data += (0b000001 << 66
                     | r << 62
                     | 0b001100 << 56
                     | 0b00000101 << 48
                     | 0b00000001 << 32
                     | 0b00001000 << 24
                     | 0b11001000 << 16).to_bytes(9, "big")

        elif self._encoder.layout.name == "7.1":
            data += (0b000001 << 66
                     | r << 62
                     | 0b001000 << 56
                     | 0b00001001 << 48
                     | 0b00000001 << 32
                     | 0b00001000 << 24
                     | 0b11001000 << 16).to_bytes(9, "big")

        self._encoder.extradata = data


class libfdk_aacConfig(EncoderConfig):
    format = "s16"
    codec = "libfdk_aac"

    def __init__(self, bitrate=None, **options):
        super().__init__("libfdk_aac", bitrate, **options)

    def create(self, framesource, rate, time_base, layout, bitrate=None,
               notifyencode=None, logfile=None, **override):
        if "format" in override:
            del override["format"]

        if bitrate is not None:
            override.update(bitrate=bitrate)

        else:
            override.update(bitrate=self.bitrate)

        return libfdk_aacEncoderContext(
            framesource, rate=rate, layout=layout, time_base=time_base,
            notifyencode=notifyencode, logfile=logfile, **override)

    def __reduce__(self):
        return type(self), (), self.__getstate__()
