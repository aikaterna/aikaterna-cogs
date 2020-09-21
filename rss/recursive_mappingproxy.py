from collections.abc import Mapping, Sequence


def _proxy(item):
    if isinstance(item, Mapping):
        return RecursiveMappingProxyType(item)
    if isinstance(item, Sequence):
        return _proxied_sequence(item)
    return item


def _proxied_sequence(value: list) -> tuple:
    return tuple(_proxy(item) for item in value)


class RecursiveMappingProxyType(Mapping):
    """
    Like MappingProxyType, but it also recursively proxies values
    that are Mappings (dicts) or Sequences (lists, tuples).
    """
    def __init__(self, data: dict):
        self.__data = data

    def __getitem__(self, key):
        return _proxy(self.__data[key])

    def __len__(self):
        return len(self.__data)

    def __iter__(self):
        return iter(self.__data)

    def __contains__(self, key):
        return key in self.__data
