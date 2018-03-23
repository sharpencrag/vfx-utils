# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@copyright: 2018 Kludgeworks LLC

@description: defines classes which store data on various problem types

@author: Ed Whetstone

@applications: NUKE
"""

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# built-in
import sys
from functools import wraps

# internal
from vfx_utils.plutonium.core import sel
from vfx_utils.plutonium.core import filters
from vfx_utils.plutonium.core import crawl
from vfx_utils.plutonium.core.decorators import defaults_factory
from vfx_utils.plutonium.core.decorators import all_nodes

# domain
import nuke
from nukescripts.misc import declone

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #

# ------------------- Resolutions ------------------------------------------ #
RENDER_RES = 'RENDER_RES'

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------ DECORATORS -- #
def culled_comp(func):
    """decorates Gremlin search functions to replace None default with
    non-white-listed nodes in the main comp"""
    @wraps(func)
    def cull_from_white_list_main():
        nodes = crawl.main_comp()
        white_list_nodes = WhiteList.search()
        return [n for n in nodes if n not in white_list_nodes]
    return defaults_factory('nodes', (cull_from_white_list_main, [], {}), func)

def white_list_culled(func):
    """decorates Gremlin search functions to replace None default with
    non-white-listed nodes"""
    def cull_from_white_list_all():
        nodes = nuke.allNodes()
        white_list_nodes = WhiteList.search()
        return [n for n in nodes if n not in white_list_nodes]
    return defaults_factory('nodes', (cull_from_white_list_all, [], {}), func)

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- CLASSES -- #
class WhiteList(object):
    """stores the list of nodes where Gremlins aren't allowed"""

    # Class Variable: Store a list of nodes to use for the whitelist,
    # accessible to multiple calls within the sniffer.
    cached_white_list = []
    EXCLUDED_NODES = ('BackdropNode', 'Dot', 'StickyNote')

    def __init__(self):
        self.nodes = []
        self.dirty = False
        self.update()

    def update(self):
        self.nodes = self.search()
        self.dirty = False

    @staticmethod
    def cache(cls, nodes):
        cls.cached_white_list = nodes

    @staticmethod
    @crawl.main_tree
    def search(nodes=None):
        return [n for n in nodes if 'white_list' in n.knobs()
                and n['white_list'].value() is True]


# -------------------------------------------------- Gremlin Base Classes -- #
class Gremlin(object):
    """base class for all issue types"""
    def __init__(self):
        super(Gremlin, self).__init__()
        self.name = 'no name set'
        self.status = 'no status set'
        # all subclasses will have a description and category
        self.description = None
        self.category = None
        self.priority = 0
        self.fixit = False
        self.fix_description = None
        # after a fix is applied, and the data model is stale
        self.dirty = False
        # boolean for whether the issue is present or not, regardless of
        # quantities
        self.triggered = False
        # presence of nodes determines if the gremlin is a node-type
        # for the widgetizer
        self.nodes = None

    # ------------------- Search For issue --------------------------- #
    @staticmethod
    def search(self):
        raise NotImplementedError('search is meant to be overridden in'
                                  'subclasses!')

    # ------------------- Fix Issue ---------------------------------- #
    @staticmethod
    def fix(self):
        pass

    # ------------------- Update Gremlin ----------------------------- #
    def update(self):
        pass


class NodeGremlin(Gremlin):
    """base class for all issues relating to specific nodes"""
    def __init__(self):
        super(NodeGremlin, self).__init__()
        self.nodes = []
        self.fixit = False

    def update(self):
        self.nodes = self.search()
        self.status = '{0} nodes found'.format(str(len(self.nodes)))
        if self.nodes:
            self.triggered = True
        self.dirty = False

    def select(self):
        sel.replace(self.nodes)


class InfoGremlin(Gremlin):
    """base class for all issues which aren't related to any
    specific nodes"""
    def __init__(self):
        super(InfoGremlin, self).__init__()
        self.triggered = False


# -------------------------------------------------------------- Gremlins -- #
class ChannelCount(InfoGremlin):
    """checks to see if the channel count is over acceptable limits"""
    def __init__(self):
        super(ChannelCount, self).__init__()
        self.update()
        self.name = 'Channel Count'
        self.category = 'Functionality'
        self.priority = 1
        self.description = ('NUKE allows up to 1,024 channels to be used in '
                            'a single comp.  Once you go over that limit, '
                            'things start to break.')

    # ------------------- Search For issue --------------------------- #
    @staticmethod
    def search(self):
        channel_count = len(nuke.root().channels())
        return channel_count

    def update(self):
        overrun = 1024 - self.search()
        if self.search() < 0:
            self.triggered = True
            self.status = ('Channel Count is Over-Limit by {0}'.format(overrun))
        else:
            self.triggered = False
            self.status = ('Channel Count is OK!')


class NonUnPremulted(NodeGremlin):
    """checks for color manipulations without unpremults"""
    def __init__(self):
        super(NonUnPremulted, self).__init__()
        self.update()
        self.name = 'color changes without unpremults'
        self.category = 'Functionality'
        self.priority = 2
        self.description = ('When grading or color-correcting, if your image '
                            'has an alpha channel, you must unpremult by the '
                            'alpha in order to avoid edging')
        self.fixit = True
        self.fix_description = ('set the "unpremult by" knob to "rgba.alpha" ')

    # ------------------- Search For issue --------------------------- #

    @staticmethod
    @culled_comp
    def search(nodes=None):
        color_nodes = filters.color_changes(nodes=nodes)
        affected_nodes = [n for n in color_nodes if
                          n['unpremult'].value() == 'none'
                          and 'rgba.alpha' in n.channels()]
        return affected_nodes

    # ------------------- Fix Issue ---------------------------------- #
    @staticmethod
    def fix(self, nodes=None):
        for n in nodes:
            n['unpremult'].setValue('rgba.alpha')
            sys.stdout.write('Premult Applied to: {0}\n'
                             ''.format(n['name'].value()))


class ErrorNodes(NodeGremlin):
    """checks for nodes which report errors"""
    def __init__(self):
        super(ErrorNodes, self).__init__()
        self.update()
        self.name = 'nodes with errors'
        self.priority = 1
        self.category = 'Functionality'
        self.description = ('When NUKE runs into an unexpected problem, '
                            'nodes throw errors instead of evaluating the '
                            'image.')

    # ------------------- Search For issue --------------------------- #
    @staticmethod
    @culled_comp
    def search(nodes=None):
        return [n for n in nodes if n.hasError()]


class ArchivedReads(NodeGremlin):
    """checks for Reads without a live folder in their paths"""
    # TODO: once we have a sense of our file structures, we should work on
    # making a fix for this gremlin
    def __init__(self):
        super(ArchivedReads, self).__init__()
        self.update()
        self.name = 'archived read nodes'
        self.priority = 2
        self.category = 'RFX'
        self.description = ('our preferred workflow is to use live folders '
                            'wherever possible.')

    # ------------------- Search For issue --------------------------- #
    @staticmethod
    @culled_comp
    def search(nodes=None):
        return [n for n in nodes if n.Class() == 'Read'
                and 'live' not in n['file'].value()]


class DeadEnds(NodeGremlin):
    """checks for nodes that don't contribute to the final image"""
    def __init__(self):
        super(DeadEnds, self).__init__()
        self.update()
        self.name = 'dead end nodes'
        self.priority = 2
        self.category = 'Organization'
        self.description = ('these nodes don\'t contribute to your '
                            'comp, but are still hooked up.')

    # ------------------- Search For issue --------------------------- #
    @staticmethod
    @culled_comp
    def search(nodes=None):
        branches = [n for n in crawl.full_comp() if n not in nodes]
        # dead end is defined as a node which has zero outputs but at least one
        # input
        return [n for n in branches if
                not any([(n in crawl.above(b)) for b in branches])
                and n.inputs() > 0]


class AlphaChecked(NodeGremlin):
    """checks for merges where 'output alpha' is checked, and both inputs have
    an alpha channel
    """
    def __init__(self):
        super(AlphaChecked, self).__init__()
        self.update()
        self.name = 'merges with alpha checked'
        self.priority = 2
        self.category = 'Functionality'
        self.description = ('These Merges have alpha output turned on, which '
                            'means their alphas will double up, causing edging '
                            'problems')
        self.fixit = True
        self.fix_description = ('to keep only the B-channel alpha, change the '
                                'Merge\'s output to rgb only')

    # ------------------- Search For issue --------------------------- #
    @staticmethod
    @culled_comp
    def search(nodes=None):
        nodes = filters.by_class_list(keys=('Merge', 'Merge2'), nodes=nodes)
        rgba_merges = [(n, n.inputs()) for n in nodes
                       if n['output'].value() == 'rgba'
                       and n['operation'].value() not in ('over', 'under')]
        return [n[0] for n in rgba_merges if n[1] == 2
                and 'rgba.alpha' in n[0].input(1).channels()]

    # ------------------- Fix Issue ---------------------------------- #
    @staticmethod
    def fix(self, nodes=None):
        for n in nodes:
            n['output'].setValue('rgb')


class UnReformatted(NodeGremlin):
    """checks for double-res Reads without the requisite Reformat node"""
    # TODO: add the fix feature. fix is passing for now.
    def __init__(self):
        super(UnReformatted, self).__init__()
        self.update()
        self.name = 'double-res Reads without Reformats'
        self.priority = 1
        self.category = 'Functionality'
        self.description = ('These Reads have a non-standard resolution, and '
                            'need to be reformatted to work correctly')
        self.fixit = True
        self.fix_description = ('Add a reformat node directly under the Read')

    # ------------------- Search For issue --------------------------- #
    @staticmethod
    @culled_comp
    def search(nodes=None):
        reformats = filters.by_class(key='Reformat', nodes=nodes)
        reads = list(filters.by_class(key='Read', nodes=nodes))
        for reformat in reformats:
            currentNode = (reformat,)
            while currentNode:
                one_ups = crawl.up(currentNode)
                currentNode = one_ups
                for one_up in one_ups:
                    if one_up.Class() == 'Read':
                        if one_up in reads:
                            reads.remove(one_up)
                        currentNode = []
                    elif one_up.inputs() > 1:
                        currentNode = []
                    else:
                        currentNode = one_up

        return [r for r in reads if r.format().name() != RENDER_RES]

    # ------------------- Fix Issue ---------------------------------- #
    @staticmethod
    def fix(self, nodes=None):
        # TODO: use nodes library instead of long method
        # TODO: use a selection context manager
        cur_sel = nuke.selectedNodes()
        for n in nodes:
            sel.replace(n)
            reformat_node = nuke.createNode('Reformat')
            reformat_node['format'].setValue(RENDER_RES)
            reformat_node['label'].setValue("Render Res")
            reformat_node['filter'].setValue("Impulse")
            sys.stdout.write('reformatting ' + n.name())
        sel.replace(cur_sel)


class MultipleWrites(InfoGremlin):
    """checks for multiple write nodes enabled in comp"""
    # TODO: this one doesn't work with main_tree either.  will need to figure
    # out a better approach.
    def __init__(self):
        super(MultipleWrites, self).__init__()
        self.update()
        self.name = 'multiple writes enabled'
        self.priority = 2
        self.category = 'Functionality'
        self.description = ('Our render dispatcher supports multiple writes, '
                            'but it\'s best to leave a single write enabled '
                            'when saving your file')

    # ------------------- Search For issue --------------------------- #
    @staticmethod
    @all_nodes
    def search(nodes=None):
        writes = [w for w in filters.by_class(nodes=nodes, key='Write')
                  if not w['disable'].value()]
        if len(writes) > 1:
            return True
        else:
            return False

    def update(self):
        self.triggered = self.search()
        if self.triggered:
            self.status = 'Multiple Writes Found!'
        else:
            self.status = 'Looks Good!'


class CloneNodes(NodeGremlin):
    """search for cloned nodes"""
    def __init__(self):
        super(CloneNodes, self).__init__()
        self.update()
        self.name = 'cloned nodes'
        self.priority = 1
        self.category = 'Functionality'
        self.description = ('Clone nodes are nothing but trouble.')
        self.fixit = True
        self.fix_description = ('De-clone nodes')

    # ------------------- Search For issue --------------------------- #
    @staticmethod
    @culled_comp
    def search(nodes=None):
        return [n for n in nodes if n.clones()]

    # ------------------- Fix Issue ---------------------------------- #
    @staticmethod
    def fix(self, nodes=None):
        for n in nodes:
            declone(n)


class NoStereoVariable(NodeGremlin):
    """search for reads without the %v variable"""
    # TODO: need to add the fix code, currently passing
    def __init__(self):
        super(NoStereoVariable, self).__init__()
        self.update()
        self.name = 'Reads without %v'
        self.priority = 1
        self.category = 'Stereo'
        self.description = ('These reads are not enabled for stereo')
        self.fixit = True
        self.fix_description = ('Replace the l or r in the file path with %v')

    # ------------------- Search For issue --------------------------- #
    @staticmethod
    @culled_comp
    def search(nodes=None):
        return [n for n in nodes if n.Class() == 'Read'
                and '%v' not in n['file'].value()]

    # ------------------- Fix Issue ---------------------------------- #
    @staticmethod
    def fix(self, nodes=None):
        import re
        for n in nodes:
            filename = n['file'].value()
            stereo_filename = ''
            try:
                stereo_filename = re.sub('([\._/])[lr]([\./])',
                                         r'\1%v\2', filename)
            except:
                raise
            n['file'].setValue(stereo_filename)
            sys.stdout.write('per-eye variable applied to {0}'.format(n.name()))


class NonStereoShapes(NodeGremlin):
    """checks for shape nodes without proper offset controls"""
    def __init__(self):
        super(NonStereoShapes, self).__init__()
        self.update()
        self.name = 'Shape Nodes that aren\'t stereo-ready'
        self.priority = 2
        self.category = 'Stereo'
        self.description = ('These nodes are not properly set up for stereo')

    # ------------------- Search For issue --------------------------- #
    @staticmethod
    @culled_comp
    def search(nodes=None):
        shapes = filters.shapes(nodes=nodes)
        stereo_shapes = filters.stereo_status(nodes=shapes)
        return [s for s in shapes if s not in stereo_shapes]


class RedundantReads(NodeGremlin):
    """checks for read nodes that duplicate file paths"""
    def __init__(self):
        super(RedundantReads, self).__init__()
        self.update()
        self.name = 'Redundant Reads'
        self.priority = 2
        self.category = 'Organization'
        self.description = ('These nodes point to the same path as other Reads')

    @staticmethod
    @culled_comp
    def search(nodes=None):
        return filters.redundant_reads(nodes=nodes)


class UnlabeledBackdrops(NodeGremlin):
    """checks for BackdropNodes which are unlabeled"""
    def __init__(self):
        super(UnlabeledBackdrops, self).__init__()
        self.update()
        self.name = 'Unlabeled Backdrops'
        self.priority = 2
        self.category = 'Organization'
        self.description = ('Backdrops are great organizational tools, but '
                            'make sure they are clearly labeled!')

    # ------------------- Search For issue --------------------------- #
    @staticmethod
    @all_nodes
    def search(nodes=None):
        nodes = filters.by_class(key='BackdropNode', nodes=nodes)
        return [n for n in nodes if not n['label'].value()]


class FloatingNodes(NodeGremlin):
    """checks for nodes which don't contribute to the main comp in any way"""
    def __init__(self):
        super(FloatingNodes, self).__init__()
        self.update()
        self.name = 'Floating Nodes'
        self.priority = 2
        self.category = 'Organization'
        self.description = ('These nodes aren\'t connected to the main comp')

    # ------------------- Search For issue --------------------------- #
    @staticmethod
    @white_list_culled
    def search(nodes=None):
        # accepts nodes arg, does not use it for compatibility
        main_comp_nodes = crawl.full_comp()
        return [n for n in nuke.allNodes() if n in nodes
                and n not in main_comp_nodes
                and n.Class() != 'BackdropNode']
