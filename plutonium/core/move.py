# ---------------------------------------------------------------------------- #
# ------------------------------------------------------------------ HEADER -- #
"""
@copyright: 2018 Kludgeworks LLC

@description: move nodes around on the DAG

@author: Ed Whetstone

@applications: NUKE
"""

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #
# built-in
from Queue import Queue
from threading import Thread
import operator

# internal
from vfx_utils.plutonium.core import pos
from vfx_utils.plutonium.core import decorators

import vfx_utils.omni.slog as slog

# domain
import nuke

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
VERSION = '1.2'
DEBUG_VERSION = '1.2.6'

align_offset = 20
node_offset = 40

exec_ = nuke.executeInMainThreadWithResult

# --------------------------------------------------------------- Logging -- #
logger = slog.Logger()

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- THREADING -- #
class NodeMoverThread(Thread):
    """Move nodes on the DAG using a thread and queue"""
    def __init__(self):
        super(NodeMoverThread, self).__init__()
        self.steps = 8
        self.sequential = False
        self.queue = Queue()
        self.setDaemon(True)

    def run(self):
        while True:
            nodes, (dest_x, dest_y) = self.queue.get()
            for node in nodes:
                origin_x, origin_y = node.xpos(), node.ypos()
                nudge_x = (dest_x - origin_x) / self.steps
                nudge_y = (dest_y - origin_y) / self.steps
                for i in range(self.steps):
                    move_args = (node, nudge_x, nudge_y)
                    exec_(self._nudge, args=move_args)
                # force the node to be in the final position,
                # compensating for errors in float division
                force_args = (node, dest_x, dest_y)
                exec_(self._setpos, args=force_args)
                self.queue.task_done()

    @staticmethod
    def _nudge(node, x, y):
        node['xpos'].setValue(node['xpos'].getValue() + x)
        node['ypos'].setValue(node['ypos'].getValue() + y)

    @staticmethod
    def _setpos(node, x, y):
        node.setXYpos(x, y)

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- CLASSES -- #
class MovementGroup(object):
    """Enable movement of an entire group of nodes relative to other groups or
    single nodes"""
    dir_slugs = {'left': (('top-right', 'top-left'), (operator.sub, 1, 0)),
                 'right': (('top-left', 'top-right'), (operator.add, 1, 0)),
                 'above': (('bottom-left', 'top-left'), (operator.sub, 0, 1)),
                 'under': (('top-left', 'bottom-left'), (operator.add, 0, 1))}

    def __init__(self, nodes):
        self.nodes = nodes
        self.pos = pos.PositionGroup(nodes)

    def nudge(self, x=0, y=0):
        nudge_group(self.nodes, x, y)

    def _to(self, start_pos, dest_pos):
        diff_x = dest_pos[0] - start_pos[0]
        diff_y = dest_pos[1] - start_pos[1]
        self.nudge(diff_x, diff_y)

    def _with_respect_to(self, other, direction, offset=align_offset):
        """for now, assume that other is another MovementGroup"""
        dir_slugs, offsets = self.dir_slugs[direction]
        offset_operator, x_mask, y_mask = offsets
        offset_x = offset_operator(0, (x_mask * offset))
        offset_y = offset_operator(0, (y_mask * offset))
        this_corner = self.pos.corners[dir_slugs[0]]
        other_corner = other.pos.corners[dir_slugs[1]]
        self._to(this_corner, other_corner)
        self.nudge(x=offset_x, y=offset_y)

    def to(self, x, y):
        self._to(self.pos.corners['top-left'], (x, y))

    def center_to(self, x, y):
        self._to(self.pos.center, (x, y))

    def left(self, other, offset=align_offset):
        self._with_respect_to(other, 'left', offset=offset)

    def right(self, other, offset=align_offset):
        self._with_respect_to(other, 'right', offset=offset)

    def under(self, other, offset=align_offset):
        self._with_respect_to(other, 'under', offset=offset)

    def above(self, other, offset=align_offset):
        self._with_respect_to(other, 'above', offset=offset)

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #

# ------------------------------------------------------ General Movement -- #
@decorators.selected_node
def nudge(node=None, x=0, y=0):
    """move a node relative to its current position"""
    cur_x, cur_y = pos.xy(node)
    node.setXYpos(int(cur_x + x), int(cur_y + y))

@decorators.selected_nodes
def nudge_group(nodes=None, x=0, y=0):
    """nudge multiple nodes at once"""
    for node in nodes:
        nudge(node, x, y)

@decorators.selected_node
def to(node=None, x=None, y=None):
    """move the upper-left corner of the node to the specified coordinates"""
    if x is not None:
        node['xpos'].setValue(x)
    if y is not None:
        node['ypos'].setValue(y)

@decorators.selected_node
def center_to(node=None, x=None, y=None):
    """move the center of the node to the specified coordinates"""
    cen_x, cen_y = pos.center(node)
    move_by_x = x - cen_x if x else 0
    move_by_y = y - cen_y if y else 0
    nudge(node, move_by_x, move_by_y)

@decorators.selected_nodes
def space_out_nodes(nodes=None, axis='x'):
    """space out nodes along the given axis"""
    axes = ('x', 'y')
    axis_index = axes.index(axis)
    constrained_axis = 1 - axis_index
    min_node = pos.xmost_node(nodes=nodes, axis=axis, min_max=min)
    max_node = pos.xmost_node(nodes=nodes, axis=axis, min_max=max)
    min_pos = pos.center(min_node)
    max_pos = pos.center(max_node)
    min_on_axis = min_pos[axis_index]
    max_on_axis = max_pos[axis_index]
    constrained = min_pos[constrained_axis]
    interval = int(max_on_axis - min_on_axis) / (len(nodes) - 1)
    nodes.sort(key=lambda x: x['{}pos'.format(axis)].value())
    # nodes.pop()
    for i, node in enumerate(nodes):
        npos = [0, 0]
        npos[constrained_axis] = constrained
        npos[axis_index] = min_on_axis + (i * interval)
        center_to(node=node, x=npos[0], y=npos[1])

# ------------------------------------------------------------- Alignment -- #
def align(node_one, node_two, axis='x'):
    """match center position on x or y axis"""
    match = 'ypos' if axis == 'x' else 'xpos'
    offset_axis = 'y' if axis == 'x' else 'x'
    n_one_offset = _node_offset(node_one, offset_axis)
    n_two_offset = _node_offset(node_two, offset_axis)
    match_pos = node_two[match].value() + n_two_offset - n_one_offset
    node_one[match].setValue(match_pos)

def align_no_collide(node_one, node_two, axis='x'):
    """match position on x or y, with a collision check"""
    # not fully implemented
    # TODO: flesh out the check and placement options
    align(node_one, node_two, axis)
    if pos.collides(node_one, node_two):
        resolve = under if axis == 'y' else right
        resolve(node_one, node_two)

def to_relative(node_one, node_two, x=0, y=0):
    """base function for moving nodes relative to each other. node_one is
    always relative to node_two
    """
    cen_x, cen_y = pos.center(node_two)
    center_to(node_one, cen_x, cen_y)
    axis = 'x' if x else 'y'
    node_offset = _node_offsets(node_one, node_two, axis)
    if x < 0 or y < 0:
        node_offset = -node_offset
    if x:
        x += node_offset
    elif y:
        y += node_offset
    nudge(node_one, x, y)

# ----------------------------------------------------- Alignment Macros -- #
def above(node_one, node_two, offset=align_offset):
    """node_one gets placed above node_two"""
    to_relative(node_one, node_two, y=-offset)

def under(node_one, node_two, offset=align_offset):
    """node_one gets placed under node_two"""
    to_relative(node_one, node_two, y=offset)

def left(node_one, node_two, offset=align_offset):
    """node_one gets placed to the left of node_two"""
    to_relative(node_one, node_two, x=-offset)

def right(node_one, node_two, offset=align_offset):
    """node_one gets placed to the right of node_two"""
    to_relative(node_one, node_two, x=offset)

# ----------------------------------------------- Alignment w.r.t Inputs -- #
@decorators.selected_node
def align_to_input(node=None, axis='x', inp=0):
    """align a node to its nth input. caller determines orientation"""
    node_two = node.input(inp)
    align(node, node_two, axis)

@decorators.selected_node
def align_to_inputs(node=None, order=(0, 1)):
    """aligns x axis then y axis, to the inputs provided in order"""
    axes = ('y', 'x')
    alignments = ((node, axes[i], order[i]) for i in range(2))
    for a in alignments:
        align_to_input(*a)

def stack(nodes=None):
    """stack a set of nodes by hierarchy.
    (NOT IMPLEMENTED!)
    """
    raise NotImplementedError('this code has not been implemented yet')

# ----------------------------------------------------- Alignment Helpers -- #
def _node_offsets(node_one, node_two, axis='x'):
    """helper function to get the amount of buffer necessary between
    two nodes"""
    return sum(_node_offset(n, axis) for n in (node_one, node_two))

def _node_offset(node, axis='x'):
    """determine the halfway-mark for a node, horizontally or vertically"""
    strategy = pos.true_width if axis == 'x' else pos.true_height
    return strategy(node) / 2

# -------------------------------------------------------- Node Expansion -- #
@decorators.selected_nodes
def expand_contract(direction, expand_or_contract, amt=.1, nodes=None):
    """expands a set of nodes in a given direction.
    direction can be left, right, up, down, topleft, topright, botleft,
    botright, xaxis, yaxis, or center."""

    # TODO: needs a good pep-8-ing and probably a good refactoring
    if direction in ('left', 'right', 'up', 'down'):
        graphNodes = [n for n in nodes if n.Class() != 'BackdropNode']
        backdropNodes = [n for n in nodes if n.Class() == 'BackdropNode']

        # get the bounding box
        xmin, ymin, xmax, ymax = pos.group_bounding_box(nodes)

        # ------------------- Direction of Movement ----------------------- #
        if expand_or_contract == 'expand':
            amt = 1 + amt
        else:
            amt = 1 - amt
        if direction == 'down':
            total = ymax - ymin
            target = (total * amt) - total
            offsetter = 1
            anchor = ymin

        if direction == 'up':
            total = ymax - ymin
            target = -1 * ((total * amt) - total)
            offsetter = 1
            anchor = ymax

        if direction == 'left':
            total = xmax - xmin
            target = -1 * ((total * amt) - total)
            offsetter = 0
            anchor = xmax

        if direction == 'right':
            total = xmax - xmin
            target = (total * amt) - total
            offsetter = 0
            anchor = xmin
        # If the destination is the same as the origin, skip evaluation
        if total == 0:
            return

        # ------------------- Move Nodes ---------------------------------- #
        for n in graphNodes:
            offAxis = pos.center(n)[offsetter]
            offset = abs(offAxis - anchor)
            offsetRatio = float(offset) / float(total)
            offsetBy = target * offsetRatio
            n[('xpos', 'ypos')[offsetter]].setValue(
                int(n[('xpos', 'ypos')[offsetter]].getValue() + offsetBy))

        # ------------------- Handle Backdrops ---------------------------- #
        for bn in backdropNodes:
            if direction == 'down' or direction == 'up':
                offsetTop = abs(bn['ypos'].getValue() - anchor)
                otRatio = offsetTop / total
                offsetBottom = abs((bn['ypos'].getValue()
                                    + bn['bdheight'].getValue()) - anchor)
                obRatio = offsetBottom / total

                offsetTopBy = target * otRatio
                offsetBottomBy = (target * obRatio) - offsetTopBy

                bn['ypos'].setValue(int(bn['ypos'].getValue() + offsetTopBy))
                bn['bdheight'].setValue(
                    int(bn['bdheight'].getValue() + offsetBottomBy))

            if direction == 'left' or direction == 'right':
                offsetLeft = abs(bn['xpos'].getValue() - anchor)
                olRatio = offsetLeft / total
                offsetRight = abs((bn['xpos'].getValue()
                                   + bn['bdwidth'].getValue()) - anchor)
                orRatio = offsetRight / total
                offsetLeftBy = target * olRatio
                offsetRightBy = (target * orRatio) - offsetLeftBy
                bn['xpos'].setValue(int(bn['xpos'].getValue()
                                        + offsetLeftBy))
                bn['bdwidth'].setValue(int(bn['bdwidth'].getValue()
                                           + offsetRightBy))

    # ------------------- Macros ------------------------------------------ #
    elif direction == 'yaxis':
        expand_contract('up', expand_or_contract, (float(amt) / 2.0), nodes)
        expand_contract('down', expand_or_contract, (float(amt) / 2.0), nodes)
    elif direction == 'xaxis':
        expand_contract('left', expand_or_contract, (float(amt) / 2.0), nodes)
        expand_contract('right', expand_or_contract, (float(amt) / 2.0), nodes)
    elif direction == 'botright':
        expand_contract('left', expand_or_contract, amt, nodes)
        expand_contract('up', expand_or_contract, amt, nodes)
    elif direction == 'botleft':
        expand_contract('right', expand_or_contract, amt, nodes)
        expand_contract('up', expand_or_contract, amt, nodes)
    elif direction == 'topleft':
        expand_contract('right', expand_or_contract, amt, nodes)
        expand_contract('down', expand_or_contract, amt, nodes)
    elif direction == 'topleft':
        expand_contract('right', expand_or_contract, amt, nodes)
        expand_contract('down', expand_or_contract, amt, nodes)
    elif direction == 'topright':
        expand_contract('left', expand_or_contract, amt, nodes)
        expand_contract('down', expand_or_contract, amt, nodes)
    elif direction == 'center':
        expand_contract('left', expand_or_contract, (float(amt) / 2.0), nodes)
        expand_contract('right', expand_or_contract, (float(amt) / 2.0), nodes)
        expand_contract('up', expand_or_contract, (float(amt) / 2.0), nodes)
        expand_contract('down', expand_or_contract, (float(amt) / 2.0), nodes)
    else:
        pass
