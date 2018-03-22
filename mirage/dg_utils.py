# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@organization: Kludgeworks LLC

@description: Utilities for working with the Maya DAG

@author: Ed Whetstone

@applications: MAYA
"""

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #
# built-in
from itertools import chain

# internal
import vfx_utils.omni.slog as slog
from vfx_utils.omni.data_types import TreeDict, TreeNode
import vfx_utils.mirage.api_utils as api
from vfx_utils.mirage.api_utils import msplit
from vfx_utils.mirage.maya_callbacks.watchers import SceneWatcher

# domain
import maya.OpenMaya as om

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
DAGNODE = TreeNode('__dagnode__', repr_='DAGNODE')

logger = slog.Logger()
logger.level = 3

cb_logger = slog.Logger('DAG_Crawler_Callbacks')
cb_logger.formatter = lambda msg, lvl, **_: "DAG_CRAWLER: {0}".format(msg)
cb_logger.level = 3

# -------------------------------------------------------------------------- #
# --------------------------------------------------------- DAG TRAVERSAL -- #
def dag_generator():
    iterator = om.MItDag(om.MItDag.kDepthFirst)
    current_item_getter = iterator.currentItem
    next_ = iterator.next
    while not iterator.isDone():
        yield current_item_getter()
        next_()
    raise StopIteration

# -------------------------------------------------------------------------- #
# ----------------------------------------------------------- DAG CRAWLER -- #
class DagCrawler(object):
    """the dag crawler is a model of the maya dag, represented with
    ApiNodes in a nested TreeDict. See the data_types module for more
    information on TreeDicts and TreeNodes"""

    def __init__(self, *args, **kwargs):
        self.key_type = DAGNODE
        self.tree = TreeDict(*args, **kwargs)
        self.path_dict = dict()

    def populate(self, nodes=None):
        """Create a dict representing the full dag path for all objects
        in the scene. by default this includes all DAG nodes. Subclasses
        can create their own populate functions."""
        tree = self.tree = TreeDict()
        if nodes is None:
            nodes = dg_iter(iterator_type='dag').to_api_nodes()
        else:
            nodes = list(nodes)
            node_chain = list(chain(*[([node]
                                       + node.ancestors
                                       + node.descendants)
                                      for node in nodes]))
            nodes = list(set(node_chain))
            nodes = [node for node in nodes if node.parent]

        # build path tree
        for api_node in nodes:
            path = self._api_node_to_path(api_node)
            self._save_path(api_node, path)
            path.append(self.key_type)
            tree.set_at_path(path, api_node)

    def _save_path(self, api_node, path):
        """cache the given api node's name path"""
        self.path_dict[api_node] = tuple(path)

    def _clear_saved_path(self, api_node):
        cb_logger.debug('clearing saved path for {}', api_node)
        self.path_dict.pop(api_node)

    def repath(self, api_node, old_path, new_path, repath_descendants=False):
        """Do the necessary work to remove an old path and replace it with
        a new one.  If necessary, also repath all the descendants of the
        given node"""
        self.tree.repath(old_path, new_path)
        self._clear_saved_path(api_node)
        self._save_path(api_node, new_path)
        if repath_descendants:
            descendants = api_node.descendants
            for node in descendants:
                new_desc_path = self._api_node_to_path(node)
                self._clear_saved_path(node)
                self._save_path(node, new_desc_path)

    def _branch_at_split(self, split_path):
        """get the TreeNode represented by the path"""
        return self.tree.get_at_path(split_path)

    def _api_node_to_path(self, api_node, use_cache=False):
        """return a path given an api node.  If use_cache is True,
        attempt to return the cached version of the path"""
        if use_cache:
            try:
                return self.path_dict[api_node]
            except:
                pass
        path = msplit(api_node.long_name)[1:]
        return path

    def _api_node_to_node_path(self, api_node, use_cache=False):
        """return the node hierarchy leading to this node"""
        path = self._api_node_to_path(api_node, use_cache=use_cache)
        path.append(self.key_type)
        return path

    def _path_to_api_node(self, split_path):
        """given a name path, return the node at the end of it"""
        return self.tree.get_at_path(split_path)

    def branch_at_node(self, api_node):
        """return the TreeNode represented by the given api_node"""
        path = self._api_node_to_path(api_node)
        return self._branch_at_split(path)

    def name_to_node(self, node_name):
        """given the name of a node, return the api_node representation"""
        if node_name.startswith('|'):
            split_path = msplit(node_name[1:])
        else:
            split_path = msplit(node_name)
        return self._path_to_api_node(split_path + [self.key_type])

    def add_node(self, api_node):
        """add a node to the DagCrawler model"""
        path = self._api_node_to_path(api_node)
        self._save_path(api_node, path)
        path.append(self.key_type)
        self.tree.set_at_path(path, api_node)

    def remove_node(self, api_node):
        """remove a node from the DagCrawler model"""
        if api_node in self.path_dict:
            path = self._api_node_to_path(api_node, use_cache=True)
            try:
                self.tree.pop_at_path(path)
            except KeyError:
                path = self._api_node_to_path(api_node, use_cache=False)
                self.tree.pop_at_path(path)
            for node in [api_node] + api_node.descendants:
                self._clear_saved_path(node)
        else:
            cb_logger.debug('{} has already been removed', api_node)

    def api_node_path(self, split_path):
        """given a list of names representing a hierarchy, return the
        api_node representations of those names"""
        lookups = self._left_fold(split_path)
        nodes = []
        for lookup in lookups:
            branch = self.branch(lookup)
            nodes.append(branch[self.key_type])
        return nodes

    # ------------------------------------------------------ Helpers -- #
    @staticmethod
    def _left_fold(split_path):
        """fold the given path left:
        >> _left_fold([a, b, c])
        >> [a], [a, b], [a, b, c]
        """
        return [split_path[0:i + 1] for i in range(len(split_path))]

    def _recurse_key_to_key(self, top_dict, sub_dict):
        for key, mixed_dict in sub_dict.items():
            node = mixed_dict.pop(self.key_type)
            top_dict[node] = {}
            self._recurse_key_to_key(top_dict[node], mixed_dict)
        return top_dict

    def key_dict(self):
        """flatten a nested dictionary by key values"""
        new_dict = {}
        return self._recurse_key_to_key(new_dict, self.tree)


class LiveDagCrawler(DagCrawler):
    """The "live" version of the DagCrawler registers its own set of callbacks
    to keep itself up to date when the DAG model changes in Maya.  This class
    is meant to be pretty hands-off, so the only "public" function is "freeze",
    which kills all the callbacks"""

    def __init__(self, scene_watcher=None, *args, **kwargs):
        super(LiveDagCrawler, self).__init__(*args, **kwargs)
        self.populate()
        self._watcher = scene_watcher if scene_watcher else SceneWatcher()
        self.update_callbacks = []
        self._add_hooks()

    def _updated(self):
        for callback in self.update_callbacks:
            callback()

    def _add_hooks(self):
        logger.debug('initializing callbacks for LiveDagCrawler')
        self._watcher.hook('any_node_added',
                           node_type='dagNode').append(self._node_added)
        self._watcher.hook('any_node_removed',
                           node_type='dagNode').append(self._node_removed)
        self._watcher.hook('any_child_added').append(self._child_added)
        self._watcher.hook('any_name_changed').append(self._node_renamed)

    def _node_added(self, api_node, _):
        cb_logger.debug("callback triggered - node added: {}", api_node)
        cb_logger.debug("adding node to tree...")
        self.add_node(api_node)

    def _node_removed(self, api_node, _):
        cb_logger.debug("callback triggered - node removed: {}", api_node)
        cb_logger.debug("removing node from tree...")
        self.remove_node(api_node)

    def _child_added(self, child, *_):
        if child.is_valid:
            cb_logger.debug("callback triggered - child added: {}", child)
            cb_logger.debug("re-pathing node tree...")
            old_path = self._api_node_to_path(child, use_cache=True)
            new_path = self._api_node_to_path(child, use_cache=False)
            self.repath(child, old_path, new_path, repath_descendants=True)

    def _node_renamed(self, api_node, old_name, _):
        if api_node in self.path_dict:
            cb_logger.debug("callback triggered - node renamed: {}", api_node)
            cb_logger.debug("re-pathing node tree...")
            new_path = self._api_node_to_path(api_node)
            old_path = new_path[:-1] + [old_name]
            self.repath(api_node, old_path, new_path, repath_descendants=True)

    def freeze(self):
        self._watcher.flush()

    def __del__(self):
        try:
            self._watcher.flush()
        except:
            raise

# -------------------------------------------------------------------------- #
# -------------------------------------------------------------------- LS -- #
class dg_iter(object):
    """class for iterating over nodes, either in the Dependency Graph or
    the DAG.  Performance is close to cmds.ls, and exceeds it in certain
    custom plugin-type lookups. """

    # defines the kinds of iteration possible with the class
    iterators = {'depend': (om.MItDependencyNodes, 'thisNode'),
                 'dag': (om.MItDag, 'currentItem')}

    def __init__(self, iterator_type='depend',
                 plugin_types=[om.MFn.kPluginDependNode],
                 maya_types=None):
        # if no maya type filters are provided, just get all dependency nodes
        maya_types = maya_types or ['dependencyNode']
        self.it, self._get_method = dg_iter.iterators[iterator_type]
        self.plugin_search = plugin_types[0]
        self.filter, self.plugin_types = self._build_filter(maya_types)

    def walk(self, it):
        """do the work of moving through maya's provided iterator classes"""

        # determine interface beforehand. in large scenes, removing
        # the dot increases execution speed by up to 20%
        done = it.isDone

        # MItDag and MItDependNodes have two different methods for getting the
        # current node, thisNode and currentItem.  We use getattr to grab the
        # correct method
        current_item = getattr(it, self._get_method)
        advance_item = it.next
        # get all objects in the main loop
        while not done():
            n = current_item()
            yield n
            advance_item()
        raise StopIteration

    def iterate(self):
        """generator for dependency nodes"""
        # determine iterator type
        main_it = self.it(self.filter)
        # walk through two iterators, one set to the maya type filters,
        # and another for types associated with plugins
        for n in self.walk(main_it):
            yield n
        filters = self.plugin_types
        if filters:
            plugin_it = self.it(self._to_filter(self.plugin_search))
            for n in self.walk(plugin_it):
                if api.type_of(n) in filters:
                    yield n

    def to_api_nodes(self):
        for obj in self.iterate():
            yield api.ApiNode(obj)
        raise StopIteration

    def to_msel(self):
        return api.msel_from_iter(self.iterate())

    def to_strings(self):
        return api.msel_to_strings(self.to_msel())

    def _build_filter(self, filters):
        it_filter = om.MIteratorType()
        types = om.MIntArray()
        _filters = list(filters)
        for filter_ in list(_filters):

            enumerated = api.fn_type_string_to_int(filter_)
            if enumerated:
                types.append(enumerated)
                _filters.remove(filter_)
            else:
                pass
        it_filter.setFilterList(types)
        return (it_filter, _filters)

    def _to_filter(self, enumerated):
        it_filter = om.MIteratorType()
        types = om.MIntArray()
        types.append(enumerated)
        it_filter.setFilterList(types)
        return it_filter

    def __iter__(self):
        return self.iterate()

# selection helpers
# TODO: this is weird, and needs to be moved

def selection():
    sel_list = om.MSelectionList()
    om.MGlobal.getActiveSelectionList(sel_list)
    return sel_list

def selection_iter():
    return iterate_msel_list(selection())

# mselectionlist helpers
# TODO: move this somewhere better

def iterate_msel_list(sel_list):
    iterator = om.MItSelectionList(sel_list)
    while not iterator.isDone():
        obj = om.MObject()
        iterator.getDependNode(obj)
        yield obj
        iterator.next()
