from collections.abc import Mapping, Sequence
from types import MappingProxyType


def _proxy(item):
    if isinstance(item, Mapping):
        return RecursiveMappingProxyType(item)
    if isinstance(item, Sequence):
        return _proxied_sequence(item)
    return item


def _proxied_sequence(value: list) -> tuple:
    return tuple(_proxy(item) for item in value)


class RecursiveMappingProxyType(MappingProxyType):
    """
    Like MappingProxyType, but it also recursively proxies values
    that are Mappings (dicts) or Sequences (lists, tuples).
    """

    def __getitem__(self, key):
        return _proxy(super().__getitem__(key))

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            return default
