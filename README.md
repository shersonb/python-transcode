# python-transcode
Transcoder for Python is a python module that can be used to process multimedia content. Includes a Qt5 gui.

## Container support
* Matroska (read/write via python-matroska module)
* Advanced Substation Alpha (read via ass module)

On the to-do list: raw ac3 and dts

Further containers can be supported by placing a module in the transcode/container directory, subclassing
the following classes:

* Read support:
    * transcode.container.basereader.BaseReader
    * transcode.container.basereader.Track

* Write support:
    * transcode.container.basewriter.BaseWriter
    * transcode.container.basewriter.Track

Opening a file for reading, with container automatically selected, **including a full scan**:

```python

import transcode

f = transcode.open("input.mkv", "r")
f.scan()
```

Creating an output file configuration, with container automatically selected:

```python

import transcode

g = transcode.open("output.mkv", "w")
```

Adding a video track from "input.mkv" to "output.mkv", resizing, and encoding with libx265, and an audio track (copy only):

```python

from transcode.filters.video.cropandresize import Resize
from transcode.filters.base import FilterChain
from transcode.encoders.libx265 import libx265Config
resize = Resize(720, 480)
libx265 = libx265Config(crf=22)
g.addTrack(f.tracks[0], encoder=libx265, filters=FilterChain([resize]))
g.addTrack(f.tracks[1])
```

Note: "output.mkv" is not opened for writing until ```g.transcode()``` is called.

## Encoder support
* libx265 (via PyAV)
* ac3 (via PyAV)
* libfdk_aac (via PyAV)

Transcoder aims to be able to encode using any encoder, including those supported by ffmpeg via PyAV. However, custom modules must be written in order to properly construct the necessary extra codec data that certain codecs require.

## Decoder support
Decoding through PyAV/ffmpeg has been tested on the following codecs:

* libx264
* libx265
* mpeg2video
* vc1
* ac3
* dts

Transcoder should theoretically be able to decode any stream supported by PyAV/ffmpeg, however, no
further codecs have been tested at this time.

## Contributing
Pull requests are welcome, especially to add container and codec support. For major changes, please open an issue first to discuss what you would like to change.

## License
[MIT](https://choosealicense.com/licenses/mit/)

