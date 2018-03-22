# ---------------------------------------------------------------------------- #
# ------------------------------------------------------------------ HEADER -- #
"""
@organization: Kludgworks LLC

@description: Inspections provides interfaces to the inspect python module,
              with enhancements for speed and efficiency.

@author: Ed Whetstone

@applications: Any

"""
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #
# built-in
import inspect
import sys
from collections import namedtuple
from itertools import izip

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #

# ---------------------------------------------------------- Enumerations -- #
FRAME = 0
FUNC_NAME = 1
MOD_NAME = 2
LOCALS = 3
FILE_NAME = 4
LINE_NO = 5
FUNC_OBJ = 6
MOD_OBJ = 7
INST_OBJ = 8
ARGSPEC = 9


# --------------------------------------------------------- Bitwise Flags -- #
CO_VARARGS = inspect.CO_VARARGS
CO_VARKEYWORDS = inspect.CO_VARKEYWORDS

# ------------------------------------------------------- Data Structures -- #
StackInfo = namedtuple('StackInfo', ['frame', 'func_name', 'mod_name',
                                     'locals', 'file_name', 'line_no',
                                     'func_obj', 'mod_obj', 'inst_obj',
                                     'argspec'])

# My version of ArgSpec is slightly different from the one provided by
# Python's inspect.getargspec() - I skip the defaults param and just use
# a dictionary to map defaults to the kwargs directly. There are
# convenience functions in this module to make use of this
# ArgSpec via an interface.
ArgSpec = namedtuple('ArgSpec', ['args', 'kwargs', 'var_args', 'var_kwargs'])

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------ STACK INFO -- #
def get_stack(frame):
    """Return all frames in the stack and some related info, starting
    with the given frame and working downwards to the console."""

    # All of the shenanigans in the code below is necessary in order to
    # optimize the stack lookup.  We avoid for-loops and list appending
    # by pre-allocating the size of the lists we'll be using.

    # make a copy of the frame object for the first round of traversal.
    _frame = frame
    # this is the number of returned values per-frame.  It corresponds
    # to the enumeration created above
    num_elements = 10

    # ------------------- Determine Stack Depth ---------------------------- #
    # because the frame stack already exists in memory, walking through
    # it is essentially free.  This allows us to quickly determine the
    # depth of the stack and pre-allocate our lists accordingly.
    i = 0
    while _frame:
        i += 1
        _frame = _frame.f_back

    # ------------------- Build Info List ---------------------------------- #
    # The final return value for the stack is a list of lists, which can
    # be converted to a StackInfo object for a nicer interface. We defer
    # the conversion in order to maximize efficiency.
    info = [None] * num_elements
    for j in xrange(num_elements):
        info[j] = [None] * i
    i = 0
    while frame:
        # ------------------- Frame & Code Obj Attributes ------------------ #
        code_obj = frame.f_code
        func_name = code_obj.co_name
        locals_ = frame.f_locals
        var_names = code_obj.co_varnames
        arg_count = code_obj.co_argcount
        defaults = ()
        self_obj = None
        mod_name = None
        info[FRAME][i] = frame
        info[LINE_NO][i] = frame.f_lineno
        info[FILE_NAME][i] = code_obj.co_filename
        info[FUNC_NAME][i] = func_name
        info[LOCALS][i] = locals_

        # ------------------- Lookups -------------------------------------- #
        try:
            mod_name = frame.f_globals['__name__']
            info[MOD_NAME][i] = mod_name
        except:
            pass
        try:
            info[MOD_OBJ][i] = sys.modules[mod_name]
        except:
            pass
        if var_names:
            first_arg = var_names[0]
            if first_arg in ('self', 'cls', 'klass'):
                self_obj = locals_[first_arg]
                try:
                    func_obj = getattr(self_obj, func_name)
                    info[FUNC_OBJ][i] = func_obj
                except AttributeError:
                    self_obj = None
                info[INST_OBJ][i] = self_obj
        if not self_obj:
            try:
                func_obj = frame.f_globals[func_name]
                info[FUNC_OBJ][i] = func_obj
            except:
                pass
        try:
            # this is used below, in Arg Values
            defaults = func_obj.func_defaults
        except:
            pass

        # ------------------- Arg Values ----------------------------------- #
        kwargs = {}
        var_args = ()
        var_kwargs = ()
        pos_args = ()
        if code_obj.co_flags & CO_VARARGS:
            var_args = var_names[arg_count]
        if code_obj.co_flags & CO_VARKEYWORDS:
            var_kwargs = var_names[arg_count + 1]
        if defaults:
            num_defaults = len(defaults)
            pos_args = var_names[:(arg_count - num_defaults)]
            kwargs = dict(izip(var_names[num_defaults:], defaults))
        else:
            pos_args = var_names[:arg_count]

        arg_collection = (pos_args, kwargs, var_args, var_kwargs)

        info[ARGSPEC][i] = arg_collection

        # ------------------- Continue Loop -------------------------------- #
        i += 1
        frame = frame.f_back
    return info

def get_mod_trace(frame):
    """Return the name of each module enclosing this frame.  This
    function is used in the slog module for blazing-fast Logger lookup.
    See slog for more details.
    """
    _frame = frame
    # this is the number of returned values per-frame.  It corresponds
    # to the enumeration created above, and only includes the first
    # three entries.
    # ------------------- Determine Stack Depth ---------------------------- #
    frame_count = 0
    while _frame:
        frame_count += 1
        _frame = _frame.f_back
    mods = [None] * frame_count
    # ------------------- Build Info List ---------------------------------- #
    i = 0
    while frame:
        # ------------------- Frame & Code Obj Attributes ------------------ #
        try:
            mods[i] = frame.f_globals['__name__']
        except:
            pass
        # ------------------- Continue Loop -------------------------------- #
        i += 1
        frame = frame.f_back
    return mods


# -------------------------------------------------------------------------- #
# ----------------------------------------------------- FRAME INFORMATION -- #
# These functions are largely for convenience -- they aren't as efficient
# as retrieving the entire stack's information at once using get_stack or
# get_trace.

# ------------------------------------------------------------- Iterators -- #
def walk_frames(frame):
    while frame:
        yield frame
        frame = frame.f_back

def walk_stack_info(stack):
    """given a StackInfo object with iterable members, return each frame
    as its own StackInfo object
    """
    for info in izip(*(it for it in stack)):
        yield StackInfo(*info)

# ---------------------------------------------------------------- Macros -- #
def inspect_stack(frame, inspections):
    for frm in walk_frames(frame):
        for inspection in inspections:
            return inspection(frm)

# ------------------------------------------------------ Frame Attributes -- #
def line_no(frame):
    return frame.f_lineno

# ------------------------------------------------ Code Object Attributes -- #
def func_name(frame):
    return frame.f_code.co_name

def file_name(frame):
    return frame.f_code.co_filename

def func_line_no(frame):
    return frame.f_code.co_firstlineno

# -------------------------------------------------------- Globals Lookup -- #
def frame_to_func(frame):
    return frame.f_globals[frame.f_code.co_name]

def module_name(frame):
    return frame.f_globals['__name__']

# ------------------------------------------------------ Object Retrieval -- #
def mod_obj(mod_name):
    try:
        return sys.modules[mod_name]
    except KeyError:
        return None

# -------------------------------------------------------------------------- #
# ---------------------------------------------------------- EXAMPLE CODE -- #
class E(object):
    def test(self, test=3, *args):
        return get_stack(inspect.currentframe())

def example():
    e = E()
    e.test()
