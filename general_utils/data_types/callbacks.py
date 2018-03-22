# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@organization: Kludgeworks LLC

@description: classes and functions related to creating and maintaining
              callbacks - defined here as callable objects which carry
              their own data to work with.

@author: Ed Whetstone

@applications: Any

@notes: This module uses general_utils.slog as its logging tool.
"""

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #
# internal
import LightingTools.general_utils.slog as slog
from LightingTools.general_utils.debug import about_this_stack

# -------------------------------------------------------------------------- #

VERSION = '1.0'
DEBUG_VERSION = '1.0.1'

logger = slog.Logger()
cb_register = []

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- CLASSES -- #
class Callback(object):
    """basic callback:
    create a callback by providing a callable (func) and a set of arguments
    (args and kwargs) meant to be passed into it when called.
    See the example code in this module for more detail
    """
    def __init__(self, func, register=cb_register, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        # in many UI applications, callbacks have a tendency to disappear
        # when they go out of scope.  By attaching the callback to this
        # module, or another memory location like a list, we can keep
        # its reference count up and prevent garbage collection.
        # on the other side, this also allows easy manual cleanup of
        # callbacks.
        self.register = register
        register.append(cb_register)

    def __call__(self, *args, **kwargs):
        """positional arguments from the caller are appended, and keywords are
        updated. Be careful, because kwargs can be overridden on call!"""
        final_args = self.args + args
        final_kwargs = dict(self.kwargs)
        final_kwargs.update(kwargs)
        try:
            return self.func(*final_args, **self.kwargs)
        except:
            about_this_stack(strategy=logger.error)
            slog.error('Original Traceback:')
            raise

    def __repr__(self):
        return '<Callback for function: {0}>'.format(self.func.__name__)

# -------------------------------------------------------------------------- #
# ---------------------------------------------------------- EXAMPLE CODE -- #
def example():
    """example usage of callback class"""
    # let's say that example_func is a function we want to call later on
    # when triggered by a ui event.  We make a callback which
    # encapsulates the data we want to run:
    cb = Callback(example_func, 'beep!')
    # now, whenever the UI triggers whatever event specified, cb gets
    # called:
    cb()

def example_func(message):
    print "this is a message passed into example_func:"
    print message
