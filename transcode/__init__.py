from . import containers
from . import filters
from . import encoders
from . import config
import os


def open(file, mode="r"):
    stem, ext = os.path.splitext(file)

    if mode == "r":
        reader = containers.readers_by_ext[ext.lower()]
        return reader[0](file)

    elif mode == "w":
        writer = containers.writers_by_ext[ext.lower()]
        return writer[0](file)

    else:
        raise ValueError(f"Unknown mode: {mode}")
