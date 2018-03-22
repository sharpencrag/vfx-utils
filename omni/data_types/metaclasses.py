# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@organization: Kludgeworks LLC

@description: a collection of general-purpose metaclasses

@author: Ed Whetstone

@applications: any

@notes: WIP
"""

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #

# --------------------------------------------------- Version Information -- #
VERSION = '1.1'
DEBUG_VERSION = '1.0.4'

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- CLASSES -- #
class FlyWeight_Meta(type):
    """Implements the flyweight pattern using a metaclass.  An instance
    cache will be added to every class which points to this metaclass,
    and if the passed arguments are the same as a cached object, that
    object will be returned."""
    def __new__(mcs, name, superclasses, kwargs):
        return super(FlyWeight_Meta, mcs).__new__(mcs, name, superclasses,
                                                  kwargs)

    def __init__(cls, name, bases, dct):
        cls.__inst_cache = {}
        super(FlyWeight_Meta, cls).__init__(name, bases, dct)

    def __call__(cls, *args, **kwargs):
        lookup = (args, tuple(kwargs.items()))
        cache = cls.__inst_cache
        return cache.setdefault(lookup, type.__call__(cls, *args, **kwargs))
