from av import AudioFrame, VideoFrame, AudioLayout, AudioFormat
import numpy

_aformat_dtypes = {
    'dbl': '<f8',
    'dblp': '<f8',
    'flt': '<f4',
    'fltp': '<f4',
    's16': '<i2',
    's16p': '<i2',
    's32': '<i4',
    's32p': '<i4',
    'u8': 'u1',
    'u8p': 'u1',
}

_aformats = {
    '<f8': 'dblp',
    '<f4': 'fltp',
    '<i2': 's16p',
    '<i4': 's32p',
    'u1': 'u8p',
}


def _AFrameToNDArray(frame):
    """
    A reimplementation of frame.to_ndarray that overcomes the segmentation
    fault that occurs with 8-channel audio frames, and returns an array with
    shape (frame.samples, nb_channels).
    """

    try:
        dtype = numpy.dtype(_aformat_dtypes[frame.format.name])
    except KeyError:
        raise ValueError(
            ("Conversion from {!r} format to numpy array is not"
                " supported.").format(frame.format.name))

    nb_channels = len(frame.layout.channels)

    if frame.format.is_planar:
        count = frame.samples
    else:
        count = frame.samples * nb_channels

    # convert and return data
    arrays = []

    for i, x in enumerate(frame.planes):
        if i >= nb_channels:
            break

        arrays.append(numpy.frombuffer(x, dtype=dtype, count=count))

    if frame.format.is_planar:
        return numpy.vstack(arrays).transpose()

    array = numpy.vstack(arrays)
    return array.reshape(frame.samples, nb_channels)


def _VFrameToNDArray(frame):
    A = frame.to_ndarray()
    H = frame.height
    W = frame.width

    if frame.format.name in ('yuv420p', 'yuvj420p'):
        Y = A[:H]
        UV = A[H:].reshape(H*W//2)
        U = UV[:H*W//4].reshape(H//2, W//2)
        V = UV[H*W//4:].reshape(H//2, W//2)
        return (Y, U, V)

    elif frame.format.name == "yuyv422":
        Y = A[:, :, 0]
        U = A[:, ::2, 1]
        V = A[:, 1::2, 1]
        return (Y, U, V)

    return A


def toNDArray(frame):
    if isinstance(frame, AudioFrame):
        return _AFrameToNDArray(frame)

    elif isinstance(frame, VideoFrame):
        return _VFrameToNDArray(frame)

    else:
        raise TypeError(
            "Expected AudioFrame or VideoFrame, got"
            f" {frame.__class__.__name__} instead.")


def toAFrame(array, layout=None):
    """
    Construct a frame from a numpy array.
    """

    assert array.ndim == 1 or (
        array.ndim == 2 and 1 <= array.shape[1] <= 8), "Arrays with"\
        " nb_channels > 8 unsupported"

    if layout is None:
        if array.ndim <= 1 or array.shape[1] == 1:
            layout = "mono"

        elif array.shape[1] == 2:
            layout = "stereo"

        elif array.shape[1] == 3:
            layout = "2.1"

        elif array.shape[1] == 4:
            layout = "4.0"

        elif array.shape[1] == 5:
            layout = "4.1"

        elif array.shape[1] == 6:
            layout = "5.1(side)"

        elif array.shape[1] == 7:
            layout = "6.1"

        elif array.shape[1] == 8:
            layout = "7.1"

    nb_channels = len(AudioLayout(layout).channels)
    samples = array.shape[0]
    assert array.shape[1] == nb_channels, f"Layout {layout} requires"\
        f" {nb_channels}, not {array.shape[1]}."

    # map numpy type to avcodec type

    try:
        format = _aformats[array.dtype.str]
    except KeyError:
        raise ValueError(
            f'Conversion from numpy array with dtype `{array.dtype.str}`"\
                " is not yet supported')

    if AudioFormat(format).is_planar:
        array = array.transpose().copy("c")
    else:
        array = array.reshape(1, samples*nb_channels).copy("c")

    frame = AudioFrame(format=format, layout=layout, samples=samples)

    for i, plane in enumerate(frame.planes):
        if i >= nb_channels:
            break

        plane.update(array[i, :])

    return frame


def _YUVtoVFrame(Y, U, V, format=None):
    assert Y.ndim == 2, "Y.ndim must be 2."
    assert U.ndim == 2, "U.ndim must be 2."
    assert V.ndim == 2, "V.ndim must be 2."
    assert Y.shape[0] % 2 == 0, "Y.shape[0] must be even."
    assert Y.shape[1] % 2 == 0, "Y.shape[1] must be even."
    assert U.shape == V.shape, "V.shape must be equal to U.shape."

    H, W = Y.shape
    h, w = U.shape

    if 2*h == H and 2*w == W:
        if format is None:
            format = "yuv420p"

        A = numpy.concatenate(
            (Y.reshape(H*W), U.reshape(h*w),
             V.reshape(h*w))).reshape(3*H//2, W)
        return VideoFrame.from_ndarray(A, format=format)

    elif h == H and 2*w == W:
        if format is None:
            format = "yuyv422"

        UV = numpy.concatenate(
            (U, V), axis=1).reshape(
                -1, 2, w).swapaxes(1, 2).reshape(-1, W)
        A = numpy.moveaxis((Y, UV), 0, 2)
        return VideoFrame.from_ndarray(A, format=format)


def toVFrame(array, format=None):
    if isinstance(array, tuple) and len(array) == 3:
        return _YUVtoVFrame(*array, format=format)

    if format is not None:
        if array.ndim >= 3 and array.shape[2] == 4:
            format = "rgba"

        elif array.ndim >= 3 and array.shape[2] == 3:
            format = "rgb24"

        elif array.ndim >= 3 and array.shape[2] == 1:
            format = "gray8"

    return VideoFrame.from_ndarray(array)


def aconvert(frame, format):
    if frame.format.name == format:
        return frame

    A = toNDArray(frame)
    dtype = numpy.dtype(_aformat_dtypes[format])

    if format in ("fltp", "dblp", "flt", "dbl"):
        if A.dtype in (numpy.int8, numpy.uint8):
            A = A/2**7

        elif A.dtype in (numpy.int16, numpy.uint16):
            A = A/2**15

        elif A.dtype in (numpy.int32, numpy.uint32):
            A = A/2**31

        elif A.dtype in (numpy.int64, numpy.uint64):
            A = A/2**63

        A = numpy.array(A, dtype=dtype)

    elif format in ("s16", "s16p"):
        if A.dtype in (numpy.float32, numpy.float64):
            A = A*2**15

        elif A.dtype in (numpy.int32, numpy.uint32):
            A = A/2**16

        elif A.dtype in (numpy.int8, numpy.uint8):
            A = A*2**8

        A = numpy.array(A.clip(min=-2**15, max=2**15 - 1), dtype=dtype)

    elif format in ("s32", "s32p"):
        if A.dtype in (numpy.float32, numpy.float64):
            A = A*2**31

        elif A.dtype in (numpy.int16, numpy.uint16):
            A = A*2**16

        elif A.dtype in (numpy.int8, numpy.uint8):
            A = A*2**24

        A = numpy.array(A.clip(min=-2**31, max=2**31 - 1), dtype=dtype)

    elif format in ("u8", "u8p"):
        if A.dtype in (numpy.float32, numpy.float64):
            A = A*2**7

        elif A.dtype in (numpy.int16, numpy.uint16):
            A = A/2**8

        elif A.dtype in (numpy.int32, numpy.uint32):
            A = A/2**24

        A = numpy.array(A.clip(min=0, max=2**8 - 1), dtype=dtype)

    newframe = toAFrame(A, layout=frame.layout.name)
    newframe.pts = frame.pts
    newframe.rate = frame.rate
    newframe.time_base = frame.time_base
    return newframe
