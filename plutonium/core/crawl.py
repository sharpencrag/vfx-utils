# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@copyright: 2018 Kludgeworks LLC

@description: tools related to hierarchical relationships between nodes

@author: Ed Whetstone

@applications: NUKE
"""

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #
# internal
from vfx_utils.plutonium.core import decorators

# domain
import nuke

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------ DECORATORS -- #
def main_tree(func):
    """decorates functions which take node arguments representing the
    main comp tree.  Replaces nodes=None with a list of nuke Nodes."""
    return decorators.defaults_factory('nodes', (main_comp, [], {}), func)

def full_tree(func):
    """decorates functions which require all nodes connected to main
    tree, including those that don't contribute to the image, or are
    connected via expression links.  Replaces nodes=None with a list
    of nuke Nodes."""
    return decorators.defaults_factory('nodes', (full_comp, [], {}), func)

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #

# ------------------------------------------------ Input / Output Helpers -- #
@decorators.selected_node
def direct_outputs(node=None, pipe=None):
    """returns a list of nodes that node outputs to directly
    (not via expressions)
    """
    depend_nodes = node.dependent(nuke.INPUTS)
    if not pipe:
        return [n for n in depend_nodes if n.Class() != 'Viewer']
    else:
        return [n for n in depend_nodes if n.Class() != 'Viewer'
                and n.input(pipe) == node]

@decorators.selected_node
def direct_inputs(node=None):
    """returns a list of nodes output to node directly
    (not via expressions)"""
    depend_nodes = node.dependencies(nuke.INPUTS)
    return [d for d in depend_nodes if d.Class() != 'Viewer']

@decorators.selected_node
def exp_outputs(node=None):
    """returns a list of nodes that node outputs through expressions"""
    depend_nodes = node.dependent(nuke.EXPRESSIONS)
    return [d for d in depend_nodes if d.Class() != 'Viewer']

@decorators.selected_node
def exp_inputs(node=None):
    """returns a list of nodes that this node recieves information from
    through expressions"""
    depend_nodes = node.dependencies(nuke.EXPRESSIONS)
    return depend_nodes

# --------------------------------------------------------- Above / Below -- #
@decorators.selected_nodes
def up(nodes=None, pipe=None):
    """returns a list of nodes one level up from the given node(s)"""
    try:
        list(nodes)
    except:
        nodes = [nodes]
    if not pipe:
        return [in_node for n in nodes for in_node in direct_inputs(n)]
    else:
        return [n.input(pipe) for n in nodes if n.input(pipe)]

@decorators.selected_nodes
def down(nodes=None, pipe=None):
    """returns a list of nodes one level down from the given node(s)"""
    try:
        list(nodes)
    except:
        nodes = [nodes]
    return [out_node for n in list(nodes)
            for out_node in list(direct_outputs(n, pipe=pipe))]

@decorators.selected_nodes
def above(nodes=None, dist_return=False, pipe=None):
    """returns a list of all nodes that are up-chain from the
    given node(s)"""
    try:
        list(nodes)
    except TypeError:
        nodes = [nodes]
    above_nodes = []
    distances = []
    dist = 0
    while len(nodes) > 0:
        new_nodes = up(nodes, pipe=pipe)
        dist += 1
        new = filter(lambda a: a not in above_nodes, new_nodes)
        if len(new) == 0:
            break
        for n in new:
            if n not in above_nodes:
                above_nodes.append(n)
                distances.append(dist)
        nodes = new
    if dist_return:
        above_nodes = zip(above_nodes, distances)
    return above_nodes

@decorators.selected_nodes
def below(nodes=None, dist_return=False, pipe=None):
    """returns a list of all nodes that are up-chain from the
    given node(s)"""
    try:
        list(nodes)
    except:
        nodes = [nodes]
    below_nodes = []
    distances = []
    dist = 0
    while len(nodes) > 0:
        new_nodes = down(nodes, pipe=pipe)
        new = filter(lambda a: a not in below_nodes, new_nodes)
        if len(new) == 0:
            break
        for n in new:
            if n not in below_nodes:
                below_nodes.append(n)
                distances.append(dist)
        nodes = new
        dist += 1
    if dist_return:
        below_nodes = zip(below_nodes, distances)
    return below_nodes

# ------------------------------------------------- Hierarchical Distance -- #
# TODO: this section needs updating
def first_common_descent(nodes=None, pipe=None):
    """returns the first down-chain node common to the given nodes
    (NOT IMPLEMENTED!)
    """
    nodes = nodes if nodes else nuke.selectedNodes()
    node_lists = [below(n, pipe=pipe) for n in nodes]
    if len(node_lists) > 1:
        int_set = set(node_lists[0])
        for nl in node_lists[1:]:
            int_set.intersection_update(nl)
        tup_list = [(len(above(n, pipe=pipe)), n) for n in int_set]
        tup_list.sort()
        if tup_list:
            return tup_list[0][1]
        else:
            return []
    else:
        return []

def dist_between(anode, bnode, pipe=None):
    """returns the connected distance between two nodes"""
    a_node_above = above(anode, pipe=pipe)
    b_node_above = above(bnode, pipe=pipe)
    dist = None
    if anode in b_node_above:
        above_tups = above(bnode, dist_return=True, pipe=pipe)
        above_tups.sort(key=lambda x: x[1])
        for distTup in above_tups:
            if anode == distTup[0]:
                dist = distTup[1]
    elif bnode in a_node_above:
        above_tups = above(anode, dist_return=True, pipe=pipe)
        above_tups.sort(key=lambda x: x[1])
        for distTup in above(anode, dist_return=True, pipe=pipe):
            if bnode == distTup[0]:
                dist = distTup[1]
    else:
        common_desc = first_common_descent((anode, bnode))
        if common_desc:
            distA = dist_between(anode, common_desc, pipe=pipe)
            distB = dist_between(bnode, common_desc, pipe=pipe)
            dist = distA + distB
        else:
            dist = None
    return dist

def nodes_between(anode, bnode, pipe=None):
    """returns the list of nodes connecting two nodes
    (NOT IMPLEMENTED!)
    """
    a_node_above = above(anode, pipe=pipe)
    b_node_above = above(bnode, pipe=pipe)
    nodes_btwn = None
    if anode in b_node_above:
        nodes_btwn = list(set(below(anode, pipe=pipe)) & set(b_node_above))
    elif bnode in a_node_above:
        nodes_btwn = list(set(below(bnode, pipe=pipe)) & set(a_node_above))
    else:
        common_desc = first_common_descent((anode, bnode), pipe=pipe)
        if common_desc:
            nodes_a = nodes_between(anode, common_desc, pipe=pipe)
            nodes_b = nodes_between(bnode, common_desc, pipe=pipe)
            nodes_btwn = nodes_a.extend(nodes_b)
            return nodes_btwn
        else:
            nodes_btwn = None
            return nodes_btwn

# ------------------------------------------------------- Script Specific -- #
def main_comp():
    """returns a list of all nodes in the largest tree in the comp,
    assumed to be the main comp"""
    all_nodes = nuke.allNodes('Write')
    above_nodes = []
    above_nodes = [(above(n), n) for n in all_nodes]
    main_comp = max(above_nodes, key=lambda x: len(x[0]))
    main_comp_nodes = main_comp[0]
    main_comp_nodes.reverse()
    main_comp_nodes.append(main_comp[1])
    return main_comp_nodes

def full_comp():
    """return all the nodes connected to the comp, even if they don't contribute
    to the final output."""
    main_tree_nodes = main_comp()
    all_nodes_ = nuke.allNodes()
    culled_nodes = [n for n in all_nodes_ if n not in main_tree_nodes]
    non_comp_nodes = [n for n in culled_nodes
                      if any((abv in main_tree_nodes)
                             for abv in above(nodes=n))]
    for node in list(non_comp_nodes):
        non_comp_nodes.extend(above(node))
    return list(set(non_comp_nodes))

# ------------------------------------------------------- Sorting Methods -- #
def sorted_hierarchy(nodes):
    """sorts the given nodes by hierarchical order.  Assumes all nodes
    are in the same chain"""
    def sorter(node):
        return len([n for n in above(node) if n in nodes])
    return sorted(nodes, key=sorter)

# ------------------------------------------------------- Group Hierarchy -- #
def parent(node=None):
    return nuke.toNode('.'.join(node.fullName().split('.')[:-1])) or nuke.root()
