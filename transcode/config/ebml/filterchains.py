from ebml.base import EBMLInteger, EBMLString, EBMLProperty, EBMLList
import ebml.serialization
from ...filters.base import FilterChain
from ...filters.concatenate import Concatenate


class SrcStart(EBMLInteger):
    ebmlID = b"\x41\x03"


class ZoneElement(ebml.serialization.Object):
    ebmlID = b"\x41\x02"
    __ebmlchildren__ = (
        EBMLProperty("srcStart", SrcStart),
        EBMLProperty("options", (ebml.serialization.State,
                                 ebml.serialization.StateDict), optional=True),
    )

    @classmethod
    def _createConstructorElement(cls, constructor, environ, refs):
        return None

    def _getConstructor(self, environ):
        return environ.get("zoneclass")

    @classmethod
    def _createArgsElement(cls, args, environ, refs):
        return SrcStart(*args)

    def _constructArgs(self, environ, refs):
        return (self.srcStart,)

    def _saveState(self, state, environ, refs):
        if isinstance(state, dict):
            self.options = ebml.serialization.StateDict.fromObj(
                state, environ, refs)

        else:
            self.options = ebml.serialization.State.fromObj(
                state, environ, refs)

    def _restoreState(self, obj, environ, refs):
        if self.options:
            obj.__setstate__(self.options.toObj(environ, refs))


class Zones(ebml.serialization.List):
    ebmlID = b"\x41\x04"
    _typesByID = {ZoneElement.ebmlID: ZoneElement}


class FilterName(EBMLString):
    ebmlID = b"\x41\x05"


class FilterElement(ebml.serialization.Object):
    ebmlID = b"\x31\xbc\xac"
    __ebmlchildren__ = (
        EBMLProperty("objID", ebml.serialization.ObjID, optional=True),
        EBMLProperty("source", ebml.serialization.Ref, optional=True),
        EBMLProperty("constructor", ebml.serialization.Constructor),
        EBMLProperty("options", (ebml.serialization.State,
                                 ebml.serialization.StateDict), optional=True),
        EBMLProperty("name", FilterName, optional=True),
        EBMLProperty("zones", Zones, optional=True)
    )

    @classmethod
    def _createArgsElement(cls, args, environ, refs):
        return ()

    def _constructArgs(self, environ, refs):
        return ()

    def _saveState(self, state, environ, refs):
        if "prev" in state:
            prev = state.pop("prev")
            self.source = ebml.serialization.Ref(refs[id(prev)])

        if "source" in state:
            source = state.pop("source")
            self.source = ebml.serialization.Ref(refs[id(source)])

        if "name" in state:
            self.name = state.pop("name")

        if isinstance(state, dict):
            self.options = ebml.serialization.StateDict.fromObj(
                state, environ, refs)

        else:
            self.options = ebml.serialization.State.fromObj(
                state, environ, refs)

    def _restoreState(self, obj, environ, refs):
        if self.options:
            state = self.options.toObj(environ, refs)

        else:
            state = {}

        if self.source is not None:
            state.update(source=refs[self.source])

        if self.name is not None:
            state.update(name=self.name)

        obj.__setstate__(state)

    def _restoreItems(self, obj, environ, refs):
        if hasattr(obj, "zoneclass"):
            environ["zoneclass"] = obj.zoneclass

        elif "zoneclass" in environ:
            del environ["zoneclass"]

        if self.zones:
            obj.clear()
            zones = self.zones.toObj(environ, refs)
            obj.extend(zones)

    def _saveItems(self, items, environ, refs):
        self.zones = Zones(items=[], parent=self)

        for zone in items:
            zone = ZoneElement.fromObj(zone, environ, refs)
            self.zones.append(zone)


class Filters(EBMLList):
    itemclass = FilterElement


class FilterChainElement(ebml.serialization.Object):
    ebmlID = b"\x22\xad\xc9"
    constructor = FilterChain
    _typeMap = {object: FilterElement}
    _typesByID = {FilterElement.ebmlID: FilterElement}
    __ebmlchildren__ = (
        EBMLProperty("objID", ebml.serialization.ObjID, optional=True),
        EBMLProperty("source", ebml.serialization.Ref, optional=True),
        EBMLProperty("filters", Filters, optional=True),
        EBMLProperty("name", FilterName, optional=True),
    )

    @classmethod
    def _createElement(cls, constructor, args, environ, refs):
        return cls()

    def _constructArgs(self, environ, refs):
        return ()

    def _restoreState(self, obj, environ, refs):
        source = refs.get(self.source)
        obj.__setstate__({"source": source, "name": self.name})

    def _restoreItems(self, obj, environ, refs):
        if self.filters:
            obj.clear()
            filters = [filter.toObj(environ, refs) for filter in self.filters]
            obj.extend(filters)

    def _saveState(self, state, environ, refs):
        if isinstance(state, dict) and id(state.get("source")) in refs:
            self.source = ebml.serialization.Ref(refs[id(state.get("source"))])

    def _saveItems(self, items, environ, refs):
        self.filters = Filters(items=[])

        for filter in items:
            filter = FilterElement.fromObj(filter, environ, refs)
            self.filters.append(filter)


class Refs(EBMLList):
    itemclass = ebml.serialization.Ref


class ConcatenateElement(ebml.serialization.Object):
    ebmlID = b"\x2a\xcf\xc0"
    constructor = Concatenate
    _typeMap = {object: FilterElement}
    _typesByID = {FilterElement.ebmlID: FilterElement}
    __ebmlchildren__ = (
        EBMLProperty("objID", ebml.serialization.ObjID, optional=True),
        EBMLProperty("options", (ebml.serialization.State,
                                 ebml.serialization.StateDict), optional=True),
        EBMLProperty("name", FilterName, optional=True),
        EBMLProperty("segments", Refs, optional=True),
    )

    @classmethod
    def _createElement(cls, constructor, args, environ, refs):
        return cls()

    def _constructArgs(self, environ, refs):
        return ()

    def _restoreState(self, obj, environ, refs):
        if self.options:
            state = self.options.toObj(environ, refs)

        else:
            state = {}

        if self.name:
            state.update(name=self.name)

        obj.__setstate__(state)

    def _restoreItems(self, obj, environ, refs):
        if self.segments:
            obj.clear()
            segments = [refs[ref] for ref in self.segments]
            obj.extend(segments)

    def _saveState(self, state, environ, refs):
        if isinstance(state, dict):
            if "name" in state:
                self.name = state.pop("name")

            self.options = ebml.serialization.StateDict.fromObj(
                state, environ, refs)

        else:
            self.options = ebml.serialization.State.fromObj(
                state, environ, refs)

    def _saveItems(self, items, environ, refs):
        self.segments = Refs(items=[])

        for segment in items:
            segment = ebml.serialization.Ref(refs[id(segment)])
            self.segments.append(segment)


class FilterChains(ebml.serialization.List):
    ebmlID = b"\x25\x7b\xcc"
    _typeMap = {FilterChain: FilterChainElement,
                Concatenate: ConcatenateElement, object: FilterElement}
    _typesByID = {FilterChainElement.ebmlID: FilterChainElement,
                  FilterElement.ebmlID: FilterElement, ConcatenateElement.ebmlID: ConcatenateElement}

    @classmethod
    def _fromObj(cls, obj, environ, refs):
        items = list(obj)
        reductions = [item.__reduce__() for item in items]
        childElements = []

        for child, (constructor, args, *more) in zip(items, reductions):
            objcls = cls._typeMap.get(object)
            ebmlcls = cls._typeMap.get(type(child), objcls)
            ref = ebmlcls._createRef(refs)
            childElement = ebmlcls._createElement(
                constructor, args, environ, refs)
            childElement.objID = refs[id(child)] = ref
            childElements.append(childElement)

        for childElement, (constructor, args, *more) in zip(childElements, reductions):
            if len(more) == 1:
                state, = more
                subitems = dictitems = None

            elif len(more) == 2:
                state, subitems = more
                dictitems = None

            elif len(more) == 3:
                state, subitems, dictitems = more

            if state:
                childElement._saveState(state, environ, refs)

            if subitems:
                childElement._saveItems(subitems, environ, refs)

            if dictitems:
                childElement._saveDict(dictitems, environ, refs)

        return cls(items=childElements)

    def _restoreItems(self, obj, environ, refs):
        if self.items:
            for item in self.items:
                if hasattr(item, "toObj"):
                    child = item._createObj(environ, refs)

                    if item.objID:
                        refs[item.objID] = child

                    obj.append(child)

                else:
                    obj.append(item.data)

            for child, item in zip(obj, self.items):
                try:
                    item._restoreState(child, environ, refs)

                except NotImplementedError:
                    pass

                try:
                    item._restoreItems(child, environ, refs)

                except NotImplementedError:
                    pass

                try:
                    item._restoreDict(child, environ, refs)

                except NotImplementedError:
                    pass
