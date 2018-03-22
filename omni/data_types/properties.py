# ---------------------------------------------------------------------------- #
# ------------------------------------------------------------------ HEADER -- #
"""
@organization: Kludgeworks LLC

@description: a collection of general data types

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
# ------------------------------------------------------ CLASS MECHANISMS -- #
class cached_property(object):
    """
    DESCRIPTOR:
    Allows lazy evaluation of properties.  Uses the same interface as
    regular properties, but only supports the instance.setter method,
    not instance.deleter
    """
    class obj_proxy(object):
        """provides an intermediary object where an attribute can be set
        from inside a property without recursion. Should only be used as
        part of the cached_property class"""
        def __init__(self, attr_name, cacheattr):
            self.__dict__['_cacheattr_'] = cacheattr
            self.__dict__['_attr_name_'] = attr_name

        def __getattr__(self, attr):
            if attr == self._attr_name_:
                return getattr(self._obj_, self._cacheattr_)
            else:
                return getattr(self._obj_, attr)

        def __setattr__(self, attr, value):
            if attr == self._attr_name_:
                setattr(self._obj_, self._cacheattr_, value)
            else:
                setattr(self._obj_, attr, value)

        def __call__(self, obj):
            """because the calling class instance doesn't exist when the
            cached_property is created (during decoration), we need to
            pass in the obj here."""
            self.__dict__['_obj_'] = obj
            return self

    def __init__(self, get_func):
        self.__doc__ = getattr(get_func, '__doc__')
        self.fget = get_func
        # "attr_name" becomes "_attr_name"
        self.attr_name = get_func.__name__
        self.cacheattr = '__'.join(('', self.__class__.__name__,
                                   self.attr_name))
        self.proxy = self.obj_proxy(self.attr_name, self.cacheattr)

    def __get__(self, obj, cls):
        if obj is None:
            return self
        else:
            try:
                value = getattr(obj, self.cacheattr)
            except AttributeError:
                setattr(obj, self.cacheattr, self.fget(obj))
                value = getattr(obj, self.cacheattr)
            return value

    def __set__(self, obj, value):
        self.proxy.__dict__.setdefault('_obj_', obj)
        try:
            self.fset(self.proxy, value)
        except TypeError:
            raise
            raise AttributeError('attr {0} cannot be set'
                                 ''.format(self.attr_name))

    def __delete__(self, obj):
        try:
            delattr(obj, self.cacheattr)
        except AttributeError:
            raise AttributeError('attribute {0} has not been cached yet'
                                 ''.format(self.attr_name))

    def fset(self, obj, value):
        """fset default just sets the passed value to the cached attribute"""
        setattr(obj, self.cacheattr, value)

    def setter(self, set_func):
        self.fset = set_func
        return self

# -------------------------------------------------------------------------- #
# ---------------------------------------------------------- EXAMPLE CODE -- #
def example():
    from general_utils.string_utils import make_title
    print make_title('Cached Properties')
    example_cached_property()


# ----------------------------------------------------- Cached Properties -- #
class ExampleCachedPropertyClass(object):
    def __init__(self):
        self.b = 'B'

    @cached_property
    def a(self):
        """the first time this is run, it should print 'not cached', but
        every subsequent access should just print the value """
        # make sure methods still work
        assert self.some_method() == "result of a method"
        print "not cached"
        # return the initial value
        return 5

    @a.setter
    def a(self, value):
        """this should allow us to directly set the cached value"""
        # the cached_property'ss magic translates self into:
        # cached_property.proxy._obj_
        # so here, self.b actually looks up a.proxy._obj_.b
        print self.b
        # and, because this is the attribute we have cached, it looks up
        # a.proxy._obj_._cache['_a']
        self.a += value

    @cached_property
    def x(self):
        print "not cached"
        return 12

    def some_method(self):
        return "result of a method"

def example_cached_property():
    # let's create a class with two cached properties, 'a' and 'x':
    ex = ExampleCachedPropertyClass()
    # getting the values caches the results
    print ex.a
    print ex.a
    # setting the value overrides the cache, using ex.a's setter.
    ex.a = 1
    print ex.a
    print ex.x
    print ex.x
    # will use ex.x's default setter
    ex.x = 5
    # deleting the attribute will clear the cache:
    del ex.a
    delattr(ex, 'x')
    print ex.a
    print ex.x
