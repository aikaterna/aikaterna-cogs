from collections import ChainMap
from string import Template


class QuietTemplate(Template):
    """
    A subclass of string.Template that is less verbose on a missing key
    https://github.com/python/cpython/blob/919f0bc8c904d3aa13eedb2dd1fe9c6b0555a591/Lib/string.py#L123
    """

    def quiet_safe_substitute(self, mapping={}, /, **kws):
        if mapping is {}:
            mapping = kws
        elif kws:
            mapping = ChainMap(kws, mapping)
        # Helper function for .sub()
        def convert(mo):
            named = mo.group('named') or mo.group('braced')
            if named is not None:
                try:
                    return str(mapping[named])
                except KeyError:
                    # return None instead of the tag name so that
                    # invalid tags are not present in the feed output
                    return None
            if mo.group('escaped') is not None:
                return self.delimiter
            if mo.group('invalid') is not None:
                return mo.group()
            raise ValueError('Unrecognized named group in pattern', self.pattern)
        return self.pattern.sub(convert, self.template)
