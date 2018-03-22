# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@organization: Kludgeworks LLC

@description: set of simple response objects

@author: Ed Whetstone

@applications: any

@notes: See example code for use-cases

"""

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #

# ---------------------------------------------------------- Version Info -- #
VERSION = '1.0'
DEBUG_VERSION = '1.0.1'

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- CLASSES -- #
class BoolResponse(object):
    """A very basic response which is evaluated like a boolean. In practice,
    this is a convenient wrapper to other kinds of objects so that they can
    have a True/False evaluator"""
    def __init__(self, boolean, payload=None):
        # -- Set up Instance Attributes ------------------------------ #
        self.bool = boolean
        # payload is an optional argument which allows data to be passed
        # from the response object
        self.payload = payload

    def __repr__(self):
        return '<BoolResponse object: {0}>'.format(self.bool)

    def __str__(self):
        return str(self.bool)

    def __nonzero__(self):
        return self.bool

    def __eq__(self, other):
        return self is other or self.bool == other


class BoolMessage(BoolResponse):
    """Adds a message attribute to the basic boolean response"""
    def __init__(self, boolean, message=None, payload=None):
        super(BoolMessage, self).__init__(boolean, payload)
        # -- Validate Message ---------------------------------------- #
        if message is None:
            raise Exception('a message must be supplied to BoolMessage!')

        # -- Set up Instance Attributes ------------------------------ #
        self.message = message

    def __repr__(self):
        return '<BoolMessage object: {0}, \"{1}\">'.format(self.bool, self.message)

    def __str__(self):
        return self.message


# -------------------------------------------------------------------------- #
# ---------------------------------------------------------- EXAMPLE CODE -- #
def example():
    from LightingTools.general_utils.string_utils import make_title
    print make_title('Boolean Responses')
    example_bool_response()
    example_bool_message_response()

def example_bool_response():
    true_response = BoolResponse(True, payload='payload if true')
    false_response = BoolResponse(False, payload='payload if false')
    if true_response:
        print true_response
    if not false_response:
        print false_response

def example_bool_message_response():
    true_response = BoolMessage(True, message='this was a great success!')
    false_response = BoolMessage(False, message='this was a terrible failure!')
    if true_response:
        print true_response
    if not false_response:
        print false_response
