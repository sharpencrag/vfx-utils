# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #

"""
@organization: Kludgeworks LLC

@description: Interfaces to the Maya API callbacks system.  Requires use
              of ApiNodes

@author: Ed Whetstone

@applications: MAYA

NOTE: Requires access to maya.cmds and the Maya Python API
"""

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #
# built-in
from contextlib import contextmanager
from functools import wraps

# internal
from vfx_utils.mirage.api_utils import ApiNode, ApiAttribute, null_obj
import vfx_utils.omni.slog as slog

# domain
from maya import OpenMaya as om
from maya import cmds

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #

# ------------------- Import Control --------------------------------------- #
__all__ = ['DEBUG_VERSION', 'MayaCallback', 'VERSION',
           'any_child_added', 'any_child_removed', 'any_child_reordered',
           'any_dag_changed', 'any_name_changed', 'any_node_added',
           'any_node_removed', 'any_parent_added', 'any_parent_removed',
           'node_name_changed', 'node_about_to_remove',
           'node_attr_added_or_removed', 'node_attr_changed',
           'node_child_added', 'node_child_removed', 'node_child_reordered',
           'node_dag_changed', 'node_parent_added', 'node_parent_removed',
           'added_node_collector', 'removed_node_collector', 'flush']

# ------------------- Version Control -------------------------------------- #
VERSION = '1.0'
DEBUG_VERSION = '1.0.7'

# ------------------- Logging ---------------------------------------------- #
logger = slog.Logger()

# -------------------------------------------------------------------------- #
# --------------------------------------------------- CALLBACK MANAGEMENT -- #
_registered_callbacks = dict()

_per_node_dispatch = {}

_per_attr_dispatch = {}

# -------------------------------------------------------------------------- #
# ------------------------------------------------------ CALLBACK CLASSES -- #
class MayaCallback(object):
    """Wrapper to a single callback, which can be registered (added to a
    dictionary, either the _registered_callbacks dict in this module or
    elsewhere)
    """

    def __init__(self, callback_adder, args=None, kwargs=None):
        # args and kwargs will always be passed to the callback factory,
        # even if they're not needed
        args = args if args else list()
        kwargs = kwargs if kwargs else dict()
        self.args = args
        self.kwargs = kwargs
        # the callback factory for this particular callback type
        self.callback_adder = callback_adder
        # a nice name for the callback's category
        self.callback_type = callback_adder.__name__
        # some callbacks might need to communicate with the outside
        # world.  The payload allows a callback to set arbitrary data
        self.payload = None
        # the id is generated internally by Maya at the time of callback
        # creation.
        self._id = None

    def __repr__(self):
        return "<Maya {} Callback>".format(self.callback_type)

    def register(self, callback_dict=_registered_callbacks):
        self._id = self.callback_adder(*self.args, **self.kwargs)
        callback_dict[self._id] = self

    def deregister(self, callback_dict=_registered_callbacks):
        om.MMessage.removeCallback(self._id)
        callback_dict.pop(self._id)

# -------------------------------------------------------------------------- #
# ---------------------------------------------------- CALLBACK FACTORIES -- #
# The functions in this group are intended to be the most-useful categories
# of callbacks, and generally fit into two categories:
#   * callbacks for events and actions which affect any node or reflect a
#     global event, usually named "any_*"
#   * callbacks registered to only one node, usually named "node_*"


# ------------------------------------------------ Nodes Added or Removed -- #
# aliases for functions to speed up execution a bit
_dgmsg = om.MDGMessage
_nodemsg = om.MNodeMessage

def _node_type_callback(func, callback_adder, node_type, client_data, raw):
    """factory function for callbacks which can optionally be applied to
    a subset of node types.
    """
    func = func if raw else _node_function(func)
    return MayaCallback(callback_adder, (func, node_type, client_data))

def any_node_added(func, node_type='dependNode', client_data=None, raw=False):
    return _node_type_callback(func, _dgmsg.addNodeAddedCallback,
                               node_type, client_data, raw)

def any_node_removed(func, node_type='dependNode', client_data=None,
                     raw=False):
    return _node_type_callback(func, _dgmsg.addNodeRemovedCallback,
                               node_type, client_data, raw)

def node_about_to_remove(func, node=None, node_type='dependNode',
                         client_data=None, raw=False):
    node = node if raw else node.obj
    func = func if raw else _node_function(func)
    return MayaCallback(_nodemsg.addNodePreRemovalCallback,
                        (node, func, node_type, client_data))


# ----------------------------------------------------------- DAG Changes -- #
_dagmsg = om.MDagMessage

def _dag_callback(func, callback_adder, function_translator, node,
                  client_data, raw):
    """factory function for callbacks which affect the DAG specifically"""
    func = func if raw else function_translator(func)
    if node:
        node = node if raw else node.dag_path_object
        args = (node, func, client_data)
    else:
        args = (func, client_data)
    return MayaCallback(callback_adder, args)

# ------------------- Any Dag Changes -------------------------------------- #
def any_dag_changed(func, client_data=None, raw=False):
    return _dag_callback(func, _dagmsg.addAllDagChangesCallback,
                         _dag_msg_change_function, None, client_data, raw)

def node_dag_changed(func, node, client_data=None, raw=False):
    return _dag_callback(func, _dagmsg.addAllDagChangesDagPathCallback,
                         _dag_msg_change_function, node, client_data, raw)

# ------------------- Child / Parent Added or removed ---------------------- #
def any_child_added(func, client_data=None, raw=False):
    return _dag_callback(func, _dagmsg.addChildAddedCallback,
                         _dag_nodes_change_function, None, client_data, raw)

def node_child_added(func, node, client_data=None, raw=False):
    return _dag_callback(func, _dagmsg.addChildAddedDagPathCallback,
                         _dag_nodes_change_function, node, client_data, raw)

def any_child_removed(func, client_data=None, raw=False):
    return _dag_callback(func, _dagmsg.addChildRemovedCallback,
                         _dag_nodes_change_function, None, client_data, raw)

def node_child_removed(func, node, client_data=None, raw=False):
    return _dag_callback(func, _dagmsg.addChildRemovedDagPathCallback,
                         _dag_nodes_change_function, node, client_data, raw)

def any_parent_added(func, client_data=None, raw=False):
    return _dag_callback(func, _dagmsg.addParentAddedCallback,
                         _dag_nodes_change_function, None, client_data, raw)

def node_parent_added(func, node, client_data=None, raw=False):
    return _dag_callback(func, _dagmsg.addParentAddedDagPathCallback,
                         _dag_nodes_change_function, node, client_data, raw)

def any_parent_removed(func, client_data=None, raw=False):
    return _dag_callback(func, _dagmsg.addParentRemovedCallback,
                         _dag_nodes_change_function, None, client_data, raw)

def node_parent_removed(func, node, client_data=None, raw=False):
    return _dag_callback(func, _dagmsg.addParentRemovedDagPathCallback,
                         _dag_nodes_change_function, node, client_data, raw)

def any_child_reordered(func, client_data=None, raw=False):
    return _dag_callback(func, _dagmsg.addChildReorderedCallback,
                         _dag_nodes_change_function, None, client_data, raw)

def node_child_reordered(func, node, client_data=None, raw=False):
    return _dag_callback(func, _dagmsg.addChildReorderedDagPathCallback,
                         _dag_nodes_change_function, node, client_data, raw)

# ----------------------------------------------------- Attribute Changes -- #
def _attr_change_callback(func, callback_adder, node, client_data, raw):
    """factory function for callbacks related to attribute changes on a
    specific node.  If "raw" is False, then it's assumed that the callback
    was passed with an ApiNode, and we grab the MObject from there
    """
    if not raw:
        node = node.obj
        func = _attr_change_function(func)
    return MayaCallback(callback_adder, (node, func, client_data))

def node_attr_changed(func, node=None, client_data=None, raw=False):
    return _attr_change_callback(func, _nodemsg.addAttributeChangedCallback,
                                 node, client_data, raw)

def node_attr_added_or_removed(func, node=None, client_data=None, raw=False):
    return _attr_change_callback(func, _nodemsg.addAttributeAddedOrRemovedCallback,
                                 node, client_data, raw)

# -------------------------------------------------------- Naming Changes -- #
def any_name_changed(func, client_data=None, raw=False):
    func = func if raw else _name_change_function(func)
    return MayaCallback(_nodemsg.addNameChangedCallback,
                        (null_obj, func, client_data))

def node_name_changed(func, node=None, client_data=None, raw=False):
    func = func if raw else _name_change_function(func)
    node = node if raw else node.obj
    return MayaCallback(_nodemsg.addNameChangedCallback,
                        (node, func, client_data))

# -------------------------------------------------------------------------- #
# -------------------------------------------------- CALLBACK TRANSLATORS -- #
# Maya callbacks use the data types provided by the OpenMaya API.  We
# want to use our friendlier data types!  These translators allow us to
# automatically take the return values of maya's callbacks and provide
# Python-friendly objects such as ApiNodes.

# -------------------------------------------------------- Node Functions -- #
def _node_function(func):
    @wraps(func)
    def translated_function(mobject, client_data):
        return func(ApiNode.from_mobject(om.MObject(mobject)), client_data)
    return translated_function

# --------------------------------------------------- Attribute Functions -- #
def _attr_change_function(func):
    @wraps(func)
    def translated_function(msg, plug, other_plug=None, client_data=None):
        changed_attr = ApiAttribute(plug)
        # change_types = _node_attr_message_to_strings(msg)
        return func(changed_attr, msg, client_data)
    return translated_function

# -------------------------------------------------------- Name Functions -- #
def _name_change_function(func):
    @wraps(func)
    def translated_function(obj, previous_name, client_data):
        return func(ApiNode(om.MObject(obj)), previous_name, client_data)
    return translated_function

# --------------------------------------------------------- DAG Functions -- #
def _dag_msg_change_function(func):
    @wraps(func)
    def translated_function(msg, child, parent, client_data):
        return func(msg, ApiNode(child.node()), ApiNode(parent.node()),
                    client_data)
    return translated_function

def _dag_nodes_change_function(func):
    @wraps(func)
    def translated_function(child, parent, client_data):
        return func(ApiNode(child.node()),
                    ApiNode(parent.node()), client_data)
    return translated_function


# -------------------------------------------------------------------------- #
# ---------------------------------------------------- TRANSLATOR HELPERS -- #
def node_attr_message_to_strings(msg):
    return [change_type for enum_val, change_type
            in ApiNodeMessage.AttributeMessage.iteritems() if enum_val & msg]

def dag_message_to_string(msg):
    return ApiDagMessage.DagMessage[msg]

# -------------------------------------------------------------------------- #
# ------------------------------------------- Macros and Context Managers -- #
@contextmanager
def temp_callback(callback_factory, *args, **kwargs):
    """temporarily create and register a callback, then deregister"""
    callback_dict = kwargs.pop('callback_dict', _registered_callbacks)
    callback = callback_factory(*args, **kwargs)
    callback.register(callback_dict)
    try:
        yield
    except:
        raise
    finally:
        callback.deregister(callback_dict)

@contextmanager
def _node_add_remove_collector(nodes, cb_type, node_type='dependNode',
                               callback_dict=_registered_callbacks):
    temp_nodes = []

    def cbk(node, client_data):
        temp_nodes.append(ApiNode.from_mobject(om.MObject(node)))
    with temp_callback(cb_type, cbk, callback_dict=_registered_callbacks,
                       node_type=node_type, raw=True):
        yield
    nodes.extend(temp_nodes)

@contextmanager
def added_node_collector(nodes, node_type='dependNode'):
    """Allows you to collect any nodes which are created or otherwise
    added to the DG as ApiNodes.  Pass in a mutable sequence (preferably
    a list) which can be appended, and when the context __exit__s, the
    list will be populated with ApiNodes. This collector is extremely useful
    when importing nodes to a maya scene. """
    with _node_add_remove_collector(nodes, any_node_added, node_type=node_type):
        yield

@contextmanager
def removed_node_collector(nodes, node_type='dependNode'):
    """Allows you to collect any nodes which are deleted or otherwise
    removed from the DG as ApiNodes"""
    with _node_add_remove_collector(nodes, any_node_removed,
                                    node_type=node_type):
        yield

# -------------------------------------------------------------------------- #
# ---------------------------------------------- MESSAGE CLASS INTERFACES -- #
class ApiMessage(object):
    def __getattr__(self, attr):
        return getattr(self.MessageClass, attr)

class ApiNodeMessage(ApiMessage):
    """interface to OpenMaya.MNodeMessage attributes"""
    MessageClass = _nodemsg
    AttributeMessage = {1: "kConnectionMade",
                        2: "kConnectionBroken",
                        4: "kAttributeEval",
                        8: "kAttributeSet",
                        16: "kAttributeLocked",
                        32: "kAttributeUnlocked",
                        64: "kAttributeAdded",
                        128: "kAttributeRemoved",
                        256: "kAttributeRenamed",
                        512: "kAttributeKeyable",
                        1024: "kAttributeUnkeyable",
                        2048: "kIncomingDirection",
                        4096: "kAttributeArrayAdded",
                        8192: "kAttributeArrayRemoved",
                        16384: "kOtherPlugSet",
                        32768: "kLast"}

class ApiDagMessage(ApiMessage):
    MessageClass = om.MDagMessage
    DagMessage = {-1: 'kInvalidMsg',
                  0: 'kParentAdded',
                  1: 'kParentRemoved',
                  2: 'kChildAdded',
                  3: 'kChildRemoved',
                  4: 'kChildReordered',
                  5: 'kInstanceAdded',
                  6: 'kInstanceRemoved',
                  7: 'kLast'}

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #
def flush(callback_dict=_registered_callbacks):
    callback_dict = callback_dict if callback_dict else _registered_callbacks
    for _id in dict(callback_dict):
        try:
            om.MMessage.removeCallback(_id)
        except:
            pass
        try:
            callback_dict.pop(_id)
        except:
            pass

# -------------------------------------------------------------------------- #
# ---------------------------------------------------------- EXAMPLE CODE -- #
def example():
    from lit_artist_tools.omni.string_utils import make_title
    print make_title('Adding and Removing Nodes')
    example_add_remove()

    print make_title('Attribute Changes')
    example_attrs()

    print make_title('Node Collection')
    example_node_collection()

    print make_title('Node Renaming')
    example_name_changes()

    print make_title('Dag Changes')
    example_dag_changes()

def example_add_remove():
    # ------------------- Callback ----------------------------------- #
    def cbk(node, client_data):
        print "{}: {}".format(client_data, node.name)

    # ------------------- Node Added --------------------------------- #
    call_add = any_node_added(cbk, node_type='spotLight',
                              client_data='node added')
    call_add.register()
    light = ApiNode.from_cmd('shadingNode', 'spotLight', asLight=True)
    ramp = ApiNode.from_cmd('shadingNode', 'ramp', asTexture=True)
    call_add.deregister()

    # ------------------- Node Removed ------------------------------- #
    call_rem = any_node_removed(cbk, node_type='ramp',
                                client_data='node removed')
    call_rem.register()
    light.delete()
    ramp.delete()
    call_rem.deregister()

def example_attrs():
    # ------------------- Callback ----------------------------------- #
    def cbk(attr, msg, client_data):
        print "attr {} changed!".format(attr.full_name)
        print 'changes: {}'.format(node_attr_message_to_strings(msg))

    # ------------------- Setup -------------------------------------- #
    light = ApiNode.from_cmd('shadingNode', 'spotLight', asLight=True)

    # ------------------- Attribute Changes -------------------------- #
    call_attr = node_attr_changed(cbk, light.shape)
    call_attr.register()
    light['intensity'] = 0
    call_attr.deregister()

    # ------------------- Attribute Added or Removed ----------------- #
    add_attr = node_attr_added_or_removed(cbk, light)
    add_attr.register()
    cmds.addAttr(light.name, longName='some_attr', dataType='string')
    add_attr.deregister()

    # ------------------- Tear Down ---------------------------------- #
    light.delete()

def example_node_collection():
    nodes_add = []
    with added_node_collector(nodes_add, node_type='transform'):
        light = cmds.shadingNode('spotLight', asLight=True)
    print 'added nodes: {}'.format(nodes_add)

    nodes_del = []
    with removed_node_collector(nodes_del, node_type='transform'):
        cmds.delete(light)
    print 'removed nodes: {}'.format(nodes_del)

def example_dag_changes():
    # ------------------- Callbacks ---------------------------------- #
    def any_cbk(msg, parent, child, client_data):
        print "action: {}".format(dag_message_to_string(msg))
        print "parent: {}".format(parent)
        print "child: {}".format(child)

    def child_added_cbk(parent, child, client_data):
        print "{} has adopted {}".format(parent.name, child.name)

    # ------------------- Setup -------------------------------------- #
    light = ApiNode.from_cmd('shadingNode', 'spotLight', asLight=True)
    locator = ApiNode.from_cmd('spaceLocator')
    locator_2 = ApiNode.from_cmd('spaceLocator')

    # ------------------- Any Dag Changes ---------------------------- #
    call_dag = node_dag_changed(any_cbk, light)
    call_dag.register()
    light.parent = locator
    call_dag.deregister()

    # ------------------- Child Added -------------------------------- #
    call_child_add = any_child_added(child_added_cbk)
    call_child_add.register()
    locator_2.parent = light
    call_child_add.deregister()

    # ------------------- Tear Down ---------------------------------- #
    locator_2.delete()
    light.delete()
    locator.delete()

def example_name_changes():
    # ------------------- Callback ----------------------------------- #
    def cbk(node, old_name, client_data):
        print "old name: {}".format(old_name)
        print "new name: {}".format(node.short_name)

    # ------------------- Setup -------------------------------------- #
    light = ApiNode.from_cmd('shadingNode', 'spotLight', asLight=True)

    # ------------------- Naming Changes ----------------------------- #
    call_name = any_name_changed(cbk)
    call_name.register()
    light.name = 'testNode2'
    call_name.deregister()

    # ------------------- Tear Down ---------------------------------- #
    light.delete()
