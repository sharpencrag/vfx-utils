# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@copyright: 2018 Kludgeworks LLC

@description: Nuke node creation and menu items in SuperTab form

@author: Ed Whetstone

@applications: NUKE

"""
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# internal
import vfx_utils.omni.slog as slog
import vfx_utils.omni.metrics as metrics
from vfx_utils.plutonium.core.menus import MenuTree, NUKE_MENU_ITEMS
from vfx_utils.cutie.gadgets.supertab import (SuperTab,
                                                     SuperAction,
                                                     SuperActionGroup)

# domain
import nuke

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #

# ------------------- Version Information ---------------------------- #
VERSION = '1.0'
DEBUG_VERSION = '1.0.0'

# ------------------- Logging and Metrics ---------------------------- #
APP_NAME = 'nuke_supertab'
logger = slog.Logger()

# ------------------- UI Globals ------------------------------------- #
nuke_supertab_ui = None

# ------------------- Item Caches ------------------------------------ #
item_groups = dict()

# -------------------------------------------------------------------------- #
# ------------------------------------------------------- MENU COLLECTION -- #
root_menu = nuke.menu('Nuke')

def _uniquify(item_list, key):
    """from a list of menu items, return an in-order list of only unique
    items. """
    seen = set()
    return [seen.add(key(item)) or item
            for item in item_list if key(item) not in seen]

def _unique_name(item_proxy):
    """return the name-gathering function from the given item proxy"""
    return item_proxy.name

def _get_items_from_tree(tree):
    items = []
    for key, value in tree.iteritems():
        if isinstance(key, str):
            items.extend(_get_items_from_tree(value))
        elif key == NUKE_MENU_ITEMS:
            items.extend(value)
    items = _uniquify(items, key=_unique_name)
    return [item for item in items if item.name != '']

def node_listing():
    menu_tree = MenuTree.from_name('Nodes')
    return _get_items_from_tree(menu_tree)

def example():
    print node_listing()

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- ACTIONS -- #
class NukeMenuAction(SuperAction):
    def __init__(self, item_proxy):
        super(NukeMenuAction, self).__init__()
        self.callback = item_proxy.menu_item.invoke
        self.display_name = item_proxy.name
        self.searchable_name = self.display_name
        path = item_proxy.path
        try:
            self.tag = path[-1].name
        except IndexError:
            self.tag = ''

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------------ MAIN -- #
def run():
    metrics.log_usage(APP_NAME)
    # return
    global nuke_supertab_ui
    if nuke_supertab_ui is not None:
        nuke_supertab_ui.show()
        nuke_supertab_ui.raise_()
        return
    node_item_proxies = item_groups.setdefault('nip', node_listing())
    node_action_group = SuperActionGroup('Nodes', node_item_proxies,
                                         action_type=NukeMenuAction)
    nuke_supertab_ui = SuperTab([node_action_group])
    nuke_supertab_ui.show()
