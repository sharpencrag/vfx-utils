# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@organization: Kludgeworks LLC

@description: a collection of general data types

@author: Ed Whetstone

@applications: any

@notes: WIP
"""

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

class Inheritish(object):
    """WORK IN PROGRESS, DO NOT USE"""
    def __init__(self):
        pass

    def __getattr__(self, attr):
        if attr not in self.__dict__:
            return getattr(self.node, attr)

    def __setattr__(self, attr, value):
        if attr not in self.__dict__:
            setattr(self.node, attr, value)
