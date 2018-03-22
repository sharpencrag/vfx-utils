# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@organization: Kludgeworks LLC

@description: a collection of data types associated with dictionaries

@author: Ed Whetstone

@applications: any

@notes: WIP
"""

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# built-in
from collections import defaultdict, OrderedDict

# internal
from LightingTools.general_utils.data_types import FlyWeight_Meta

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #

# --------------------------------------------------- Version Information -- #
VERSION = '1.1'
DEBUG_VERSION = '1.0.4'

__all__ = ['TreeNode', 'TreeDict', 'OrderedTreeDict', 'DefaultTree',
           'COLUMNS', 'MultiColumnTree', 'OrderedMultiColumnTree',
           'allocated_dict']

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- CLASSES -- #
class TreeNode(object):
    """A very basic object which can be used as a dictionary key with a
    minimum of overhead.  This allows unambiguous type-checking to make
    sure a dictionary key is ONLY a dictionary key. """
    __metaclass__ = FlyWeight_Meta

    def __init__(self, type_='__node__', repr_='NODE'):
        super(TreeNode, self).__init__()
        self.type_ = type_
        self.repr_ = repr_

    def __repr__(self):
        return "<{0}>".format(self.repr_)

class TreeDictBase(object):
    """simple autovivifying dictionary with some convenience methods for
    moving around data within the tree"""
    def __init__(self, *args, **kwargs):
        super(TreeDictBase, self).__init__(*args, **kwargs)

    def __getitem__(self, key):
        if key in self:
            return super(TreeDictBase, self).__getitem__(key)
        else:
            dict_inst = type(self)()
            super(TreeDictBase, self).__setitem__(key, dict_inst)
            return dict_inst

    def get_at_path(self, split_path):
        branch = self
        for token in split_path:
            branch = branch[token]
        return branch

    def set_at_path(self, split_path, value):
        branch = self.get_at_path(split_path[:-1])
        branch[split_path[-1]] = value

    def pop_at_path(self, split_path):
        return self.get_at_path(split_path[:-1]).pop(split_path[-1])

    def repath(self, old_path, new_path):
        self.set_at_path(new_path, self.pop_at_path(old_path))

class TreeDict(TreeDictBase, dict):
    """Autovivifying dictionary type"""
    def __init__(self, *args, **kwargs):
        super(TreeDict, self).__init__()

class OrderedTreeDict(TreeDictBase, OrderedDict):
    """Autovivifying OrderedDict type"""
    def __init__(self, *args, **kwargs):
        super(OrderedTreeDict, self).__init__()

    def __str__(self):
        return 'OrderedTreeDict({0})'.format(str(dict(self)))

    def __repr__(self):
        return str(dict(self))


# ----------------------------------------------------- MultiColumn Trees -- #
COLUMNS = TreeNode('__columns__', 'COLUMNS')

class MultiColumnTreeBase(object):
    """Representation for tree types with multiple columns. Useful in
    UI creation and storage of tabular data"""
    def __init__(self, *args, **kwargs):
        super(MultiColumnTreeBase, self).__init__(*args, **kwargs)

    def set_columns_at_path(self, path, columns):
        """move a set of columns to the given path"""
        self.get_at_path(path)[COLUMNS] = columns

    def append_column_at_path(self, path, column):
        columns = self.get_at_path(path).setdefault(COLUMNS, [])
        columns.append(column)

class MultiColumnTree(MultiColumnTreeBase, OrderedTreeDict):
    def __init__(self, *args, **kwargs):
        super(MultiColumnTree, self).__init__(*args, **kwargs)

class OrderedMultiColumnTree(MultiColumnTreeBase, OrderedTreeDict):
    def __init__(self, *args, **kwargs):
        super(OrderedMultiColumnTree, self).__init__(*args, **kwargs)


# ----------------------------------------------------- DefaultDict types -- #
def DefaultTree():
    """a tree of defaultdicts whose members are all automatically also
    all defaultdicts"""
    return defaultdict(DefaultTree)

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FACTORIES -- #
def allocated_dict(length):
    """a defaultdict with members that are all lists of pre-allocated length.
    useful for creating tabular data in a dictionary form for databases, or
    in cases where an underlying API provides lengths of arrays"""
    _pre = [None] * length

    def preallocated():
        return list(_pre)
    return defaultdict(preallocated)

# -------------------------------------------------------------------------- #
# ---------------------------------------------------------- EXAMPLE CODE -- #
def example():
    from general_utils import string_utils
    print string_utils.make_title('TreeDict')
    example_treedict()
    print string_utils.make_title('MultiColumnTree')
    example_multicolumntree()
    print string_utils.make_title('Preallocated Dict')
    example_alloc()

def example_treedict():
    from pprint import pprint
    t = TreeDict()
    t['this']['is']['a']['test'] = 1
    t['this']['is']['another']['test'] = 2
    t['this']['is']['still']['another'] = 3
    t['this']['is']['getting']['redundant'] = 4
    pprint(t)

def example_multicolumntree():
    from pprint import pprint
    mt = MultiColumnTree()
    mt.set_columns_at_path(['a'], [1, 2, 3])
    mt['b']
    mt['c']
    mt.set_columns_at_path(['a', 'd'], [4, 5, 6])
    pprint(mt)

def example_alloc():
    from pprint import pprint
    data = allocated_dict(3)
    for letter in 'abc':
        for i in range(3):
            data[letter][i] = i
    pprint(data)
