# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@copyright: 2018 Kludgeworks LLC

@description: the brain behind the auto-align system

@author: Ed Whetstone

@applications: NUKE
"""
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #
import nuke

from vfx_utils.omni.data_types import TreeDict, TreeNode

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
VERSION = '1.0'
DEBUG_VERSION = '1.0.0'
MENU_ITEMS = TreeNode('__NukeMenuItems__', 'MenuItems')
MENU = TreeNode('__NukeMenu__', 'Menu')

# -------------------------------------------------------------------------- #
# ---------------------------------------------------------- Menu Proxies -- #
# the default nuke.Menu and nuke.MenuItem class reprs are not very
# descriptive, and do not have any interface for retrieving the chain
# of menus which lead to their position in the tree.

# this proxy preserves attribute access (although not item-lookup or
# directory access)

class MenuProxy(object):
    def __init__(self, menu, parent):
        super(MenuProxy, self).__init__()
        self.name = menu.name()
        self.parent = parent
        self.menu_item = menu
        self.icon = menu.icon()

    @property
    def path(self):
        walk = self
        _path = []
        while walk.parent:
            _path.append(walk.parent)
            walk = walk.parent
        return tuple(reversed(_path))

    def __repr__(self):
        proxy_repr = "<Proxy({0}) for {1}>"
        return proxy_repr.format(type(self.menu_item).__name__,
                                 self.menu_item.name())

class MenuItemProxy(MenuProxy):
    def __init__(self, menu, parent):
        super(MenuItemProxy, self).__init__(menu, parent)

# -------------------------------------------------------------------------- #
# ------------------------------------------------------ Menu Collections -- #
class MenuTree(TreeDict):
    def __init__(self):
        super(MenuTree, self).__init__()

    def populate(self, root_menu):
        for item in root_menu.items():
            self.push_item(item)

    def push_item(self, item, branch=None):
        branch = branch if branch is not None else self
        if isinstance(item, nuke.Menu):
            new_branch = branch[item.name()]
            new_branch[MENU] = MenuProxy(item, branch[MENU])
            for sub_item in item.items():
                self.push_item(sub_item, new_branch)
        elif isinstance(item, nuke.MenuItem) and not item.name().startswith('@'):
            branch.setdefault(MENU_ITEMS, [])
            branch[MENU_ITEMS].append(MenuItemProxy(item, branch[MENU]))

    @classmethod
    def from_name(cls, name):
        menu = nuke.menu(name)
        inst = cls()
        inst.populate(menu)
        return inst

    @classmethod
    def from_menu(cls, menu):
        inst = cls()
        inst.populate(menu)
        return inst

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- Utilities -- #
def menu(menu_name):
    return nuke.menu(menu_name)

# -------------------------------------------------------------------------- #
# ---------------------------------------------------------- EXAMPLE CODE -- #
def example():
    from pprint import pprint
    m = menu('Nodes')
    mt = MenuTree(m)
    mt.populate(m)
    pprint(mt['Views']['Stereo'], indent=2)
    return mt
