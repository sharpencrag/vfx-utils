# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@organization: Kludgeworks LLC

@description: tools related to string manipulation, regex matching, etc.

@author: Ed Whetstone

@applications: all

TODO: we probably want to refactor most of this into a string_matching module.
"""
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# built-in
from difflib import SequenceMatcher
import time
import re

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #

LINE = '_' * 79

SHORT_LINE = '_' * 40

DASH_LINE = '-' * 79
SHORT_DASH_LINE = '-' * 40

SPACED_LINE = ' - ' * 26

EQ_LINE = '=' * 79

# -------------------------------------------------------------------------- #
# -------------------------------------------------------- REGEX MATCHING -- #
matches_numbers = re.compile('\d+')
ends_with_digit = re.compile(r'(?:[^\d]*(\d+)[^\d]*)+')

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #

# ----------------------------------------------------------- Line Macros -- #
def line(token='_', width=79):
    return token * width

# ------------------------------------------------- Simple String Formats -- #

def align_right(text, width=40, fill=' '):
    """Pad the given text with whitespace, aligning it to the right
       to the given width (in characters)
    """
    return (fill * max(0, (width - len(text)))) + text

def label_data(label, data, width=26):
    """Return a right-aligned label followed by a colon and left-aligned
    jdata.
    """
    return '{0}: {1}'.format(align_right(label, width=width), data)


def make_title(text, width=40, line_token='_'):
    """Underline, right-align, and newline the given text and return it
    """
    return njoin('', align_right(text, width=width),
                 line(token=line_token, width=width), '')


# ------------------------------------------------- Convenience Functions -- #
def datestamp(sep='_'):
    """return a nicely-formatted date for building directories"""
    return time.strftime('%m{0}%d{0}%Y'.format(sep))

def timestamp(sep='_'):
    """return a nicely-formatted time for building directories"""
    return time.strftime('%I{0}%M%p'.format(sep))

# -------------------------------------------------------------------------- #
# ------------------------------------------------------- STRING MATCHING -- #

# ------------------- Matching Helpers ------------------------------------- #
def culled_string_list(string_list=[], match_to='', strategy=None):
    """Base function for a variety of ways to cull string lists.
       strategy is a function which returns True or False
    """
    return [m for m in string_list if strategy(match_to, m)]

def fuzzy_ratio(string_one, string_two):
    return SequenceMatcher(None, string_one, string_two).ratio()

def fuzzy_substring_ratio(string_one, string_two, threshold=0.6):
    """Fuzzy match two strings with substring matching"""
    string_one = string_one.lower()
    string_two = string_two.lower()
    if string_one == string_two:
        return 1.0
    search_dist = len(string_one)
    try:
        return max(fuzzy_ratio(string_one, chunk)
                   for chunk in chunks(string_two, search_dist))
    except ValueError:
        return 0.0

# ------------------- Match Functions -------------------------------------- #
def fuzzy_match(string_one, string_two, threshold=0.6):
    """anchored fuzzy string matching!"""
    # assume string_one is the search term
    # always search without case
    string_one = string_one.lower()
    string_two = string_two.lower()
    if string_one in string_two:
        return True
    else:
        # only match as many characters as the shortest provided
        dist = min((len(string_one), len(string_two)))
        ratio = fuzzy_ratio(string_one[:dist], string_two[:dist])
        return True if ratio > threshold else False

def partial_match(string_one, string_two, threshold=0.6):
    """Fuzzy match two strings with substring matching"""
    string_one = string_one.lower()
    string_two = string_two.lower()
    if string_one in string_two:
        return True
    else:
        search_dist = len(string_one)
        return any(fuzzy_match(string_one, chunk)
                   for chunk in chunks(string_two, search_dist))

def substring_match(string_one, string_two):
    """Return True if the shorter string is found in the longer string"""
    if string_one == string_two:
        return True
    elif len(string_one) == len(string_two):
        return False
    substring = min((string_one, string_two))
    match_to = max((string_one, string_two))
    if substring in match_to:
        return True
    return False

def nonconsecutive_match(needles, haystack, anchored=False,
                         empty_returns_true=True):
    """checks if each character of "needle" can be found in order (but not
    necessarily consecutivly) in haystack.
    For example, "mm" can be found in "matchmove", but not "move2d"
    "m2" can be found in "move2d", but not "matchmove"
    >>> nonconsecutive_match("m2", "move2d")
    True
    >>> nonconsecutive_match("m2", "matchmove")
    False
    Anchored ensures the first letter matches
    >>> nonconsecutive_match("atch", "matchmove", anchored=False)
    True
    >>> nonconsecutive_match("atch", "matchmove", anchored=True)
    False
    """

    # ------------------- Low-Hanging Fruit -------------------------------- #
    if needles == haystack:
        return True

    if len(haystack) == 0 and needles:
        # "a" is not in ""
        return False

    elif len(needles) == 0 and haystack:
        # "" is in "blah"
        return empty_returns_true

    # Turn haystack into list of characters
    haystack = [letter for letter in str(haystack)]

    # ------------------- Anchored Search ---------------------------------- #
    if anchored:
        if needles[0] != haystack[0]:
            return False
        else:
            # First letter matches, remove it for further matches
            needles = needles[1:]
            del haystack[0]

    # ------------------- Continue Unanchored ------------------------------ #
    for needle in needles:
        try:
            needle_pos = haystack.index(needle)
        except ValueError:
            return False
        else:
            # Dont find string in same pos or backwards again
            del haystack[:needle_pos + 1]
    return True

def exact_match(string_one, string_two):
    return string_one == string_two


# ------------------- String Parsing --------------------------------------- #
def chunks(string_one, dist):
    """Generator:
    yield a sequence of partial strings of given length
    >> chunks('stringy', 3)
    >> Result: 'str', 'tri', 'rin', 'ing', 'ngy'
    """
    chunks = len(string_one) - dist
    for i in xrange(chunks):
        yield string_one[i:(i + dist)]

# ------------------- Basic Join ------------------------------------------- #
def ujoin(*args):
    """Join positional args using underscores"""
    return '_'.join(args)

def njoin(*args):
    """Join positional args using newlines"""
    return '\n'.join(args)

def djoin(*args):
    """Join positional args using dots"""
    return '.'.join(args)

def wjoin(*args):
    """Join positional args using whitespace"""
    return ' '.join(args)


# ------------------- Numerical Manipulation ------------------------------- #
def increment(string_val):
    """look for the last sequence of number(s) in a string and increment"""
    search = ends_with_digit.search(string_val)
    if search:
        next = str(int(search.group(1)) + 1)
        start, end = search.span(1)
        string_val = ''.join([string_val[:max(end - len(next), start)],
                             next, string_val[end:]])
    else:
        string_val = ''.join([string_val, '1'])
    return string_val

# -------------------------------------------------------------------------- #
# ---------------------------------------------------------- EXAMPLE CODE -- #
def example():
    example_lines()
    example_pretty_printing()
    example_joins()
    # TODO: write example code for string matching
    # example_string_matching()

def example_lines():
    print "Lines, stored as globals:"
    print "LINE:"
    print LINE
    print "SHORT_LINE:"
    print SHORT_LINE
    print "DASH_LINE:"
    print DASH_LINE
    print "SHORT_DASH_LINE:"
    print SHORT_DASH_LINE
    print "SPACED_LINE:"
    print SPACED_LINE
    print "\n"

def example_pretty_printing():
    print "pretty printing:"
    print make_title('Titled Text')
    print align_right('right-aligned text')
    print label_data('label', 'data')
    print label_data('other label', 'data')
    print "\n"

def example_joins():
    print "simple joining:"
    print "data = ('some', 'text', 'here')"
    data = ('some', 'text', 'here')
    # note that because these functions require positional arguments,
    # iterables must be passed with star-args
    for func in [ujoin, wjoin, djoin, njoin]:
        print func(*data)
    print "\n"
