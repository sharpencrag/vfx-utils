# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@organization: Kludgeworks LLC

@description: Functions and classes dedicated to live-object inspection and
              runtime debugging.

@author: Ed Whetstone

@applications: Any

"""

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #
# built-in
from functools import wraps
import time
import sys
from collections import deque

# internal
import vfx_utils.omni.slog as slog
from vfx_utils.omni.string_utils import align_right
import vfx_utils.omni.inspections as inspections

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #

# ------------------- Version Info ----------------------------------------- #
VERSION = '1.1'
DEBUG_VERSION = '1.0.6'

# ------------------- Logging ---------------------------------------------- #
logger = slog.Logger('DEBUG_TOOL')
logger.level = 5

# ------------------- Enumerations ----------------------------------------- #
FRAME = inspections.FRAME
FUNC_NAME = inspections.FUNC_NAME
MOD_NAME = inspections.MOD_NAME
LOCALS = inspections.LOCALS
FILE_NAME = inspections.FILE_NAME
LINE_NO = inspections.LINE_NO
FUNC_OBJ = inspections.FUNC_OBJ
MOD_OBJ = inspections.MOD_OBJ
INST_OBJ = inspections.INST_OBJ
ARGSPEC = inspections.ARGSPEC

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------ DECORATORS -- #
def timed(func):
    """use this decorator to (temporarily) test how long individual
    function calls take to run. """
    @wraps(func)
    def _timed(*args, **kwargs):
        ts = time.time()
        result = func(*args, **kwargs)
        te = time.time()
        logger.debug('{} ({}, {}) \n>>>>> {:2.6f} sec'
                     ''.format(func.__name__, args, kwargs, (te - ts)))
        return result
    return _timed

# -------------------------------------------------------------------------- #
# --------------------------------------------------------- DEBUG CLASSES -- #
class StackParser(object):
    def __init__(self, frame):
        """StackParser instances allow for collection of useful, readable
        information about a particular function stack.  By default, the
        stack information refers to the top of the stack (whichever frame
        is passed into the StackParser constructor).
        """
        self.frame = frame
        self.stack = [deque(lst) for lst in inspections.get_stack(frame)]

    @property
    def locals(self):
        """Return the locals for the first frame on the stack"""
        return self.stack[LOCALS][0]

    def func_in_mod(self):
        """Return 'function_name in module_name' as a string"""
        return 'Function {0} in {1}'.format(self.stack[FUNC_NAME][0],
                                            self.stack[MOD_NAME][0])

    def sig(self):
        """Return the signature of the function, including any
        default values"""
        func_name = self.stack[FUNC_NAME][0]
        argnames = self.stack[ARGSPEC][0][0]
        arg_str = '' if not argnames else ','.join(argnames)
        kwargs = self.stack[ARGSPEC][0][1]
        if kwargs:
            kwarg_strs = ['='.join([str(item[0]), str(item[1])])
                          for item in kwargs.items()]
            kwargs_str = ', '.join(kwarg_strs)
        else:
            kwargs_str = ''
        varargs = self.stack[ARGSPEC][0][2]
        varargs_str = '' if not varargs else '*{}'.format(varargs)
        varkwargs = self.stack[ARGSPEC][0][3]
        varkwargs_str = '' if not varkwargs else '**{}'.format(varkwargs)
        sig_fmt = "Sig: {0}({1})"
        sig_vars = [var for var in (arg_str, kwargs_str, varargs_str,
                                    varkwargs_str) if var]
        sig = sig_fmt.format(func_name, ', '.join(sig_vars))
        return sig

    def args(self):
        """Return the arguments included in the function signature, and
        their current values, with respect to the current frame.  Note
        that if the function mutates these values or re-uses the variable
        name, this will not necessarily reflect the variables' value at
        time of function call."""
        argnames = self.stack[ARGSPEC][0][0]
        if argnames:
            arglist = ['{0} = {1}'.format(arg, str(self.locals[arg]))
                       for arg in argnames]
            return '\n'.join(arglist)
        else:
            return None

    def kwargs(self):
        """Return the keyword arguments included in the function
        signature, and their current values, with respect to the current
        frame. Note that if the function mutates these values or re-uses
        the keyword variable names, this will not necessarily reflect the
        values as passed-in to the function"""
        kwargs = self.stack[ARGSPEC][0][1]
        if kwargs:
            kwarglist = ['{0} = {1}'.format(name, self.locals[name])
                         for name in kwargs]
            return '\n'.join(kwarglist)
        else:
            return None

    def varargs(self):
        """Return the variable args (star-args) and their tuple
        representation, if any."""
        vararg_name = self.stack[ARGSPEC][0][2]
        if vararg_name:
            return "*{0} = {1}".format(vararg_name, self.locals[vararg_name])
        else:
            return None

    def varkwargs(self):
        """Return the variable keyword-args, (double-star-args) and their
        dictionary representation, if any."""
        varkwarg_name = self.stack[ARGSPEC][0][3]
        if varkwarg_name:
            return "**{0} = {1}".format(varkwarg_name, self.locals[varkwarg_name])
        else:
            return None

    def trace(self):
        """Return the list of functions which culminate in this function:
        some_function() > another_function() > this_function()"""
        funcs = list(self.stack[FUNC_NAME])
        insts = self.stack[INST_OBJ]
        for i, (inst, func) in enumerate(reversed(zip(insts, funcs))):
            if inst:
                try:
                    name = inst.__class__.__name__
                except AttributeError:
                    name = inst.__name__
                funcs[i] = '{0}.{1}()'.format(name, func)
            else:
                if not func.startswith('<'):
                    funcs[i] = '{0}()'.format(func)
                else:
                    funcs[i] = 'CONSOLE'
        return '{0}: {1}'.format('Trace', ' > '.join(funcs))

# -------------------------------------------------------------------------- #
# ---------------------------------------------------------- DEBUG MACROS -- #
def _parse_top_level(stack_parser, strategy=logger.debug):
    """apply strategy() to the top level of the given stack_parser,
    returning a newline-separated collection of useful messages about
    the given frame."""
    line = '# {0} #'.format('-' * 75)
    msg_collection = [line, stack_parser.func_in_mod(),
                      stack_parser.trace(), stack_parser.sig()]
    args = stack_parser.args()
    kwargs = stack_parser.kwargs()
    varargs = stack_parser.varargs()
    varkwargs = stack_parser.varkwargs()
    for item in ('args', 'kwargs', 'varargs', 'varkwargs'):
        value = locals()[item]
        if value:
            msg_collection.append('{0}:'.format(align_right(item, fill='.')))
            msg_collection.append(value)
    msg_collection.append(line)
    msg = '\n'.join(msg_collection)
    strategy(msg)

def about_this_function(indirection=1, strategy=logger.debug):
    """collect and apply strategy() to the given frame (usually the
    calling frame).  By default this just logs a debug message.
    """
    frame = sys._getframe(indirection)
    stack_parser = StackParser(frame)
    _parse_top_level(stack_parser, strategy)

def about_this_stack(indirection=1, strategy=logger.debug):
    """collect and apply strategy() to the given frame and every frame
    above it, usually starting with the calling frame.  By default this
    logs a debug message.
    """
    frame = sys._getframe(indirection)
    stack_parser = StackParser(frame)
    msg_collection = []
    while True:
        try:
            _parse_top_level(stack_parser, strategy=msg_collection.append)
            [stk.popleft() for stk in stack_parser.stack]
        except IndexError:
            break
    strategy('\n'.join(msg_collection))

# -------------------------------------------------------------------------- #
# ---------------------------------------------------------- EXAMPLE CODE -- #
def example():
    from omni.string_utils import make_title
    print make_title('Timed Functions')
    example_timed()
    print make_title('Function Inspection')
    example_func_inspect('testing')
    print make_title('Stack Inspection')
    example_stack_inspect()

@timed
def example_timed():
    from time import sleep
    sleep(1)

def example_func_inspect(some_arg, some_kwarg='thing'):
    about_this_function()

def example_stack_inspect():
    example_trace_1()

def example_trace_1():
    """calls example_2, which then calls example_3, which calls the
    debugger info function
    """
    example_trace_2('foo')

def example_trace_2(some_arg, some_kwarg='bar'):
    about_this_stack()
