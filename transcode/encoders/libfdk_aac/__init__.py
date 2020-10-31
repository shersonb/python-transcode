from ..base import EncoderContext
from ..base import EncoderConfig


class libfdk_aacConfig(EncoderConfig):
    format = "s16"
    codec = "libfdk_aac"

    def __init__(self, bitrate=None, **options):
        super().__init__("libfdk_aac", bitrate, **options)

    def create(self, framesource, rate=None, time_base=None,
               notifyencode=None, logfile=None, **override):
        if "format" in override:
            del override["format"]

        print((framesource, dict(rate=rate, format=self.format, time_base=time_base,
                                 notifyencode=notifyencode, logfile=logfile), override))

        return super().create(framesource, rate=rate, format=self.format, time_base=time_base,
                              notifyencode=notifyencode, logfile=logfile, **override)

    def __reduce__(self):
        return type(self), (), self.__getstate__()
