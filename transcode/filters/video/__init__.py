filters = {}


def scan():
    import os
    import importlib
    from transcode.filters.video.base import BaseVideoFilter
    from transcode.filters.video.zoned import ZonedFilter

    _path = os.path.split(__file__)[0]
    filters.clear()

    for _module in os.listdir(_path):
        if (_module[0] in "_."
                or _module in ("base.py", "zoned.py", "filterchain.py")):
            continue

        if (os.path.isfile(os.path.join(_path, _module))
                and _module.lower().endswith(".py")):
            _module = importlib.import_module(f"{__name__}.{_module[:-3]}")

        elif (os.path.isdir(os.path.join(_path, _module))
              and os.path.isfile(
                  os.path.join(_path, _module, "__init__.py"))):
            _module = importlib.import_module(f"{__name__}.{_module}")

        else:
            continue

        for _key in dir(_module):
            _cls = getattr(_module, _key)

            if (isinstance(_cls, type)
                    and issubclass(_cls, (BaseVideoFilter, ZonedFilter))
                    and _cls not in (BaseVideoFilter, ZonedFilter)):
                filters[f"{_cls.__module__}.{_cls.__name__}"] = _cls


scan()
