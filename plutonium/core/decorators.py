# ---------------------------------------------------------------------------- #
# ------------------------------------------------------------------ HEADER -- #
"""
@copyright: 2018 Kludgeworks LLC

@description: decorators for Nuke-specific functionality

@author: Ed Whetstone

@applications: NUKE
"""
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# built-in
from functools import wraps
import inspect

# internal
import nuke

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
VERSION = '1.0'
DEBUG_VERSION = '1.0.0'

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------ DECORATORS -- #

# ------------------------------------------------------- Better Defaults -- #
def defaults_factory(arg_name, strategy, original_func):
    """returns a function that replaces a keyword argument with a suitable
    default, determined by strategy"""
    @wraps(original_func)
    def decorated_function(*args, **kwargs):
        arglist = inspect.getcallargs(original_func, *args, **kwargs)
        if arg_name in arglist and not arglist[arg_name]:
            kwargs[arg_name] = strategy[0](*strategy[1], **strategy[2])
        try:
            ret_value = original_func(*args, **kwargs)
        except:
            ret_value = None
        finally:
            return ret_value
    return decorated_function

def all_nodes(func):
    """decorates functions which require all nodes in the current context"""
    return defaults_factory('nodes', (nuke.allNodes, [], {}), func)


def selected_node(func):
    """decorates functions which take a single node argument, replacing
    None default with nuke.selectedNode"""
    return defaults_factory('node', (nuke.selectedNode, [], {}), func)


def selected_nodes(func):
    """decorates functions which take multiple node arguments, replacing
    None default with nuke.selectedNodes"""
    return defaults_factory('nodes', (nuke.selectedNodes, [], {}), func)


def this_node(func):
    """decorates functions (typically in grizmos) which require a group
    node context in order to run. Returns nuke.thisNode() unless
    otherwise provided"""
    return defaults_factory('node', (nuke.thisNode, [], {}), func)

# ----------------------------------------------------------- Memoization -- #
def simple_memo(func):
    """decorates functions which return a non-variable value.  Use a
    closure to store the memo."""
    memo = None

    @wraps(func)
    def decorated_function(*args, **kwargs):
        return memo if memo else func(*args, **kwargs)
    return decorated_function

def memo_args(func):
    """decorates functions which return a variety of non-variable values,
    based on an argument key.  Use a closure to store the memo.
    """
    memo = {}

    @wraps(func)
    def decorated_function(*args):
        if args in memo:
            return memo[args]
        else:
            return_val = func(*args)
            memo[args] = return_val
            return return_val
    return decorated_function
