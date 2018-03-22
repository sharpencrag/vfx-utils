# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@organization: Kludgeworks LLC

@description: a collection of data types associated with lists

@author: Ed Whetstone

@applications: any

@notes: WIP

"""
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #

# --------------------------------------------------- Version Information -- #
VERSION = '1.1'
DEBUG_VERSION = '1.0.4'


# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #
def allocated_list(length):
    """there are some situations where a pre-allocated list of specified
    size is much faster than appending to a list multiple times."""
    return [None] * length
