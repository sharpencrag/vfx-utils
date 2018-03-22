# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@organization: Kludgeworks LLC

@description: Watchers allow you to quickly and easily register callbacks
              for events both globally in Maya, and on individual nodes.

@author: ewhetstone

@applications: Maya

"""
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# built-in
from collections import defaultdict

# rfx / pipe

# internal
import vfx_utils.omni.slog as slog
import vfx_utils.mirage.maya_callbacks as maya_callbacks

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
VERSION = '1.2'
DEBUG_VERSION = '1.2.1'

logger = slog.Logger()

__all__ = ['CallbackWatcher', 'SceneWatcher', 'NodeWatcher']
# -------------------------------------------------------------------------- #
# -------------------------------------------------------------- WATCHERS -- #

_watchers = list()

class CallbackWatcher(object):
    """Watches the scene for changes.  Maintains a set of 'hooks' that
    allow multiple callbacks to be triggered for scene-wide events.
    """
    ALLOWED_CALLBACKS = []

    def __init__(self, node=None):
        super(CallbackWatcher, self).__init__()
        self.hooks = defaultdict(list)
        self.cb_register = dict()
        self.node = node
        _watchers.append(self)

    def __getitem__(self, item):
        return self.hook(item)

    def register_maya_callback(self, callback_type, lookup_name, node=None,
                               *args, **kwargs):
        # create a single callback which will in turn call each function
        # associated with a given hook
        def callback(*inner_args, **inner_kwargs):
            for hooked_func in self.hooks[lookup_name]:
                hooked_func(*inner_args, **inner_kwargs)

        # each callback_type has its own function signature and
        # requirements. Grab the factory function from the maya_callbacks
        # module in order to register the new callback for this callback_type
        callback_creator = getattr(maya_callbacks, callback_type)

        # if a node was passed to this function, assume we'll need a node
        # argument in the function signature.
        if node:
            maya_caller = callback_creator(callback, node, *args, **kwargs)
        else:
            maya_caller = callback_creator(callback, *args, **kwargs)

        # register the callback to this Watcher, so we can flush watchers
        # independently of each other
        maya_caller.register(self.cb_register)

    def flush(self):
        logger.debug('flushing callbacks on {}', self)
        maya_callbacks.flush(self.cb_register)
        self.hooks = defaultdict(list)

    def hook(self, hook_name, *args, **kwargs):
        if args or kwargs:
            lookup_name = (hook_name, tuple(args), tuple(kwargs.items()))
        else:
            lookup_name = hook_name
        if hook_name in self.ALLOWED_CALLBACKS:
            if hook_name in self.hooks:
                return self.hooks[lookup_name]
            else:
                self.register_maya_callback(hook_name, lookup_name, self.node,
                                            *args, **kwargs)
                return self.hooks.setdefault(lookup_name, list())
        else:
            raise TypeError('the chosen callback type ({}) is not allowed by '
                            '{}s'.format(self.__class__))

class SceneWatcher(CallbackWatcher):
    ALLOWED_CALLBACKS = ['any_child_added', 'any_child_removed',
                         'any_child_reordered', 'any_dag_changed',
                         'any_name_changed', 'any_node_added',
                         'any_node_removed', 'any_parent_added',
                         'any_parent_removed']

    def __init__(self):
        super(SceneWatcher, self).__init__()

class NodeWatcher(CallbackWatcher):
    ALLOWED_CALLBACKS = ['node_about_to_remove', 'node_attr_added_or_removed',
                         'node_attr_changed', 'node_child_added',
                         'node_child_removed', 'node_child_reordered',
                         'node_dag_changed', 'node_parent_added',
                         'node_parent_removed', 'removed_node_collector']

    def __init__(self, node):
        super(NodeWatcher, self).__init__(node=node)

def example():
    from mirage.api_utils import ApiNode

    # ------------------- Setup -------------------------------------- #
    node = ApiNode.from_cmd('spaceLocator')

    # ------------------- Callbacks ----------------------------------- #
    def any_cbk(*args):
        print "node added"
        print args
    scene_watcher = SceneWatcher()
    scene_watcher['any_node_added'].append(any_cbk)
    print scene_watcher.hooks

    def nparent_cbk(*args):
        print "node reparented"
        print args
    node_watcher = NodeWatcher(node)
    node_watcher['node_child_added'].append(nparent_cbk)

    # ------------------- Test --------------------------------------- #
    node_2 = ApiNode.from_cmd('spaceLocator')
    node_2.parent = node

    # ------------------- Clean up ----------------------------------- #
    scene_watcher.flush()
    node_watcher.flush()
    node_2.delete()
    node.delete()
