#region imports
from AlgorithmImports import *
#endregion

class Stats:
    def __init__(self):
        self._stats = {}

    def __setattr__(self, key, value):
        if key == '_stats':
            super().__setattr__(key, value)
        else:
            self._stats[key] = value

    def __getattr__(self, key):
        return self._stats.get(key, None)

    def __delattr__(self, key):
        if key in self._stats:
            del self._stats[key]
        else:
            raise AttributeError(f"No such attribute: {key}")
