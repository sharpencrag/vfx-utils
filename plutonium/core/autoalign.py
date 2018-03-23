# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@organization: Kludgeworks LLC

@description: the brain behind the auto-align system

@author: Ed Whetstone

@applications: NUKE
"""
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# built-in
import functools
from collections import Counter

# internal
from vfx_utils.plutonium.core import crawl
from vfx_utils.plutonium.core import move
from vfx_utils.plutonium.core import pos
from vfx_utils.plutonium.core import utils
from vfx_utils.plutonium.core import decorators

import vfx_utils.omni.slog as slog
import vfx_utils.omni.metrics as metrics

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
VERSION = '2.1'
DEBUG_VERSION = '2.1.1'

APP_NAME = 'nuke_autoalign'

logger = slog.Logger()

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------ DECORATORS -- #
def alignable_node(func):
    """returns a function which replaces the selected node with an
    AlignableNode.  Assumes node as a keyword argument"""
    @functools.wraps(func)
    def decorated(node=None, *args, **kwargs):
        if isinstance(node, AlignableNode):
            return func(node=node, *args, **kwargs)
        else:
            return func(node=AlignableNode(node), *args, **kwargs)
    return decorated

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- CLASSES -- #
class AlignableNode(object):
    def __init__(self, node):
        super(AlignableNode, self).__init__()
        self.node = node
        self.name = node.name()
        self.corner = pos.xy(node)
        self.center = pos.center(node)
        self.node_class = node.Class()
        self.join = False

    @property
    def inputs(self):
        return crawl.direct_inputs(self.node)

    @property
    def outputs(self):
        return crawl.direct_outputs(self.node)

class Node_Alignment(object):
    def __init__(self, node):
        super(Node_Alignment, self).__init__()
        self.anode = AlignableNode(node)
        self.node = self.anode.node
        self.ancillaries = sorted(self.anode.inputs + self.anode.outputs,
                                  key=lambda x: x.name())
        self.wells = gravity_wells(self.ancillaries)
        self._sort_wells()

    def _sort_wells(self):
        all_centers = [pos.center(a) for a in self.ancillaries]
        self.wells.sort(key=lambda x: (wells_score(x, all_centers)))

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #

# ------------------------------------------------------ Alignment Macros -- #
@metrics.feature_logging(APP_NAME, 'cycle wells')
@decorators.selected_node
def cycle_wells(node=None):
    """align the node to the next available gravity well"""
    alignment = Node_Alignment(node)
    node_center = alignment.anode.center
    wells = alignment.wells
    all_centers = [pos.center(n) for n in alignment.ancillaries]
    wells.sort(key=lambda x: wells_score(x, all_centers))
    if wells:
        if node_center in wells:
            try:
                final_well = wells[wells.index(node_center) + 1]
            except IndexError:
                final_well = wells[0]
        else:
            final_well = wells[0]
        move.center_to(node, *final_well)
    else:
        pass

@decorators.selected_node
def preferred(node=None):
    """attempts to align the nodes in the way a user might expect to"""
    alignment = Node_Alignment(node)
    node_center = alignment.anode.center
    wells = alignment.wells
    if wells:
        if node_center in wells:
            pass
        else:
            wells.sort(key=lambda x: preferred_score(x, alignment))
            move.center_to(node, *wells[0])
    else:
        group_center = pos.average_centered(alignment.ancillaries)
        if len(alignment.ancillaries) < 2:
            alignment.ancillaries.append(node)
        bbox = pos.group_bounding_box(alignment.ancillaries)
        if bbox[2] - bbox[0] > bbox[3] - bbox[1]:
            move.center_to(node, node_center[0], group_center[1])
        else:
            move.center_to(node, group_center[0], node_center[1])

@metrics.usage_logging(APP_NAME)
@decorators.selected_nodes
def align_selected(nodes=None):
    """align nodes based on current selection"""
    if len(nodes) == 1:
        node = nodes[0]
        cur_pos = (node.xpos(), node.ypos())
        with utils.Undoable_Action():
            preferred(node=node)
            if cur_pos == (node.xpos(), node.ypos()):
                cycle_wells(node=node)
    else:
        common_axis = find_common_axis(nodes)
        if common_axis:
            axis, position = common_axis
            if position == 'aligned':
                move.space_out_nodes(axis=axis, nodes=nodes)
            else:
                with utils.Undoable_Action():
                    for n in nodes:
                        move.center_to(n, **{axis: position})
        else:
            root_node = max(nodes, key=pre_aligned_score)
            root_pos = pos.center(root_node)
            bbox = pos.group_bounding_box(nodes)
            if bbox[2] - bbox[0] > bbox[3] - bbox[1]:
                mover = 'y'
                axis = 1
            else:
                mover = 'x'
                axis = 0
            with utils.Undoable_Action():
                for n in nodes:
                    move.center_to(n, **{mover: root_pos[axis]})

# ------------------------------------------------------------- Utilities -- #
def pre_aligned_score(node):
    """returns a score based on how many inputs and outputs a node is
    already aligned to in the graph
    """
    alignment = Node_Alignment(node)

    ancillaries = alignment.ancillaries
    tot = len([a for a in ancillaries if pos.is_aligned(a, node)])
    return tot
    # well = alignment.anode.center


def find_common_axis(nodes=None):
    """return the axis along which the given nodes are already aligned,
    if any.
    """
    centers = [pos.center(n) for n in nodes]
    x_counter = Counter([c[0] for c in centers])
    y_counter = Counter([c[1] for c in centers])
    common_x = x_counter.most_common(2)
    common_y = y_counter.most_common(2)
    if common_x[0][1] > common_y[0][1]:
        if common_x[0][1] == len(nodes):
            return ('y', 'aligned')
        elif common_x[0][1] != common_x[1][1]:
            return ('x', common_x[0][0])
        else:
            return None
    elif common_y[0][1] > common_x[0][1]:
        if common_y[0][1] == len(nodes):
            return ('x', 'aligned')
        elif common_y[0][1] != common_y[1][1]:
            return ('y', common_y[0][0])
        else:
            return None
    else:
        return None

def preferred_score(given_well, alignment):
    """combine distance from the given node to the gravity well, and the
    node's current alignment status for a preference score
    """
    node_center = alignment.anode.center
    distance = pos._2d_distance(node_center, given_well)
    x, y = given_well
    num_aligned_nodes = len([n for n in alignment.ancillaries
                             if x == pos.center(n)[0]
                             or y == pos.center(n)[1]])
    final_score = distance / num_aligned_nodes
    return final_score

def wells_score(given_well, all_centers):
    """return the number of gravity wells that the current node belongs
    to, if any
    """
    score = len(all_centers)
    x, y = given_well
    for wx, wy in all_centers:
        if x == wx or y == wy:
            score -= 1
    return score

def gravity_wells(nodes):
    """return all possible alignments for a set of nodes"""
    node_centers = [pos.center(n) for n in nodes]
    wells = [(x[0], y[1]) for x in node_centers for y in node_centers
             if (x[0], y[1]) not in node_centers]
    # If there are no wells, then the ancillaries are all in a line.
    unique_wells = list(set(wells))
    return sorted(unique_wells, key=lambda x: wells.index(x))
