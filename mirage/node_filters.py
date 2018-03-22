# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@organization: Kludgeworks LLC

@description: generic approach to filtering nodes based on rule sets

@author: Ed Whetstone

@applications: Maya

@description: A collection of general-purpose node filtering utilities.

@notes: We try to optimize the application of rules by creating chains
        of generators, passing each node through a series of rule checks
        with short-circuit logic where applicable.  All results are
        trivially cached for speed when adding and removing rules on the
        fly.  When a flush is needed, a reset function is provided.

"""

# -------------------------------------------------------------------------- #
# --------------------------------------------------- IMPORTS AND GLOBALS -- #
# -- IMPORTS ---------------------------------------------------------- #

# Built-In

from collections import defaultdict
import re
import operator

# Domain

# Third-Party

# Pipe Code

# Internal
from vfx_utils.mirage import dg_utils
from vfx_utils.omni.data_types import TreeNode

# -- GLOBALS ---------------------------------------------------------- #
_cache = defaultdict(dict)
_node_cache = dict()

NODES = TreeNode(type_='__nodes__', repr_='NODES')
NAMES = TreeNode(type_='__names__', repr_='NAMES')
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- CLASSES -- #
class NodeGenerator(object):
    def __iter__(self):
        return dg_utils.dg_iter().to_api_nodes()

# ------------------------------------------------------ NodeFilter Class -- #
class NodeFilter(object):
    """top-level representation of a node filter.  Any NodeFilter will
    only have a single RuleOperation determining nodes that fit the
    filter.  In order to use multiple rules, RuleOperations should be
    composed using the Intersection, Union, and Difference operations
    provided below"""
    def __init__(self, rule_op=None):
        super(NodeFilter, self).__init__()
        self.rule_op = rule_op
        self.node_generator = NodeGenerator()

    def refresh(self):
        """reset the node list, but not any other caches"""
        self.node_generator = NodeGenerator()

    @property
    def _nodes(self):
        try:
            for node in _node_cache[NODES]:
                yield node
        except KeyError:
            cached_nodes = []
            _node_cache[NODES] = cached_nodes
            for node in self.node_generator:
                cached_nodes.append(node)
                yield node

    @property
    def node_list(self):
        return [n for n in self._nodes if self.rule_op(n)]

# ---------------------------------------------------------- Rule Classes -- #
class RuleOperation(object):
    """This class provides an interface for a lot of different
    types of objects which take an ApiNode and return a boolean --
    anything from a simple pass/fail test with one rule, to a complex
    combination of checks against multiple rules. The results of a
    RuleOperation's pass-check are automatically cached when used as a
    callable."""
    def __init__(self, rules=None):
        """we establish the rules attribute for the convenience of the
        Interesection, Union, and Difference types below. Single rules
        will override init anyways"""
        self.rules = rules if rules else []

    def passes(self, node):
        """boolean operation, should return True if the given node should
        pass the filter (be included in the final list)"""
        raise NotImplementedError

    def __call__(self, node):
        """Rule-ops should be evaluated by being called directly. This
        allows us to keep the interface for subclasses simple and enables
        caching the results"""
        pass_dict = _cache[self]
        try:
            return pass_dict[node]
        except KeyError:
            return pass_dict.setdefault(node, self.passes(node))

class RuleIntersection(RuleOperation):
    """Represents a set of rules which must ALL be True for a node to
    pass the filter"""
    def passes(self, node):
        # print "testing node {}".format(node)
        return all(rule(node) for rule in self.rules)

class RuleUnion(RuleOperation):
    """Represents a set of rules where ANY must be True for a node to
    pass the filter"""
    def passes(self, node):
        return any(rule(node) for rule in self.rules)

class RuleDifference(RuleOperation):
    """Represents an A minus B set operation. ONLY operates on the first
    two rules provided to the RuleOperation init"""
    def __init__(self, rule_a, rule_b):
        super(RuleDifference, self).__init__([rule_a, rule_b])

    def passes(self, node):
        return self.rules[0](node) and not self.rules[1](node)

# ---------------------------------------------------------- NAMING RULES -- #
class NameRule(RuleOperation):
    """passes if the name of the node matches the given string according
    to the operator passed into the instance.  By default, NameRule just
    checks equality of a string"""
    def __init__(self, match='', operator=operator.eq, long_name=False):
        """the match, operator, and long_name flag can be set after the
        fact in tools that might have a toggle functionality"""
        self.operator = operator
        # because maya works with unicode, we make sure that we can do
        # proper comparisons
        self.match = match
        self.long_name = long_name

    def passes(self, node):
        """Generic node name pass check.  See the NameRule factories
        below for implementation"""
        try:
            name = _cache[NAMES][node]
        except:
            if self.long_name:
                name = node.long_name
            else:
                name = node.short_name
        return self.operator(name, self.match)

def NameContains(contains):
    """passes if the name contains the given string"""
    return NameRule(contains, operator=operator.contains)

def NameStartsWith(starts_with):
    """passes if the name starts with the given string"""
    # object names should always be unicode
    return NameRule(starts_with, operator=unicode.startswith)

def NameEndsWith(ends_with):
    """passes if the name ends with the given string"""
    # object names should always be unicode
    return NameRule(ends_with, operator=unicode.endswith)

def _regex_match(node_name, regex):
    # we have to switch the order of arguments for compatibility
    return bool(re.match(regex, node_name))

def NameMatchesRegex(regex):
    """passes if the node's name matches the given regex"""
    return NameRule(re.compile(regex), operator=_regex_match)

# ---------------------------------------------------------- TYPING RULES -- #
class NodeTypeIs(RuleOperation):
    """passes if the type of the node matches the given type"""
    def __init__(self, node_type):
        self.node_type = node_type

    def passes(self, node):
        """safest way to type-check is to include all inherited types"""
        return self.node_type in node.inherited_types

# -------------------------------------------------------------------------- #
# ----------------------------------------------- FUNCTIONS AND UTILITIES -- #
def reset():
    global _cache
    global _node_cache
    _cache = defaultdict(dict)
    _node_cache = dict()

# -------------------------------------------------------------------------- #
# ---------------------------------------------------------- EXAMPLE CODE -- #
def example():
    from vfx_utils.omni import string_utils
    # we want to make a rule that looks for nodes with "default", "List",
    # and "Render" in their names.  This should be two nodes:
    # defaultRenderList and defaultRenderingUtilityList

    # start by creating three rules, one for each word to search:
    rule_op_a = NameContains('default')
    rule_op_b = NameContains('List')
    rule_op_c = NameContains('Render')

    # combine the three rules using an intersection (AND)
    rule_op_and_1 = RuleIntersection([rule_op_a, rule_op_b, rule_op_c])

    # we also want to get frontCameraShape

    # only find 'camera' objects
    rule_op_d = NodeTypeIs('camera')

    # make sure the node's name starts with front
    rule_op_e = NameStartsWith('front')

    # AND combination
    rule_op_and_2 = RuleIntersection([rule_op_d, rule_op_e])

    # let's remove defaultRenderingUtilityList from our selection

    # find any node with "ing" in the name.  We could use a NameContains
    # for this, but we'll test out regex matching instead
    rule_op_f = NameMatchesRegex('.*ing.*')

    # combine the two overall rules with a union, an OR operation
    rule_op_or = RuleUnion([rule_op_and_1, rule_op_and_2])

    # we want to subtract the results of rule_op_f, so we create a
    # RuleDifference, an EXCEPT operation
    rule_op_diff = RuleDifference(rule_op_or, rule_op_f)

    # create the filter object we want to use
    nfilter = NodeFilter(rule_op_diff)

    print string_utils.make_title('Testing node filters')
    print "we should see two nodes below:"
    # in a blank Maya scene, we should see
    for node in nfilter.node_list:
        print node
