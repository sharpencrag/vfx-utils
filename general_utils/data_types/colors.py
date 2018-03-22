# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@organization: Kludgeworks LLC

@description: resources for color manipulation.

@notes: THIS CODE IS STILL IN DEVELOPMENT.  A lot of work still needs to
        be done for perceptual color spaces like CIE-LAB and LUV.  The
        "gamma" options are also not mathematically accurate (yet)

@author: Ed Whetstone

@applications: Any
"""
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# built-in
from __future__ import division
from colorsys import hsv_to_rgb, rgb_to_hsv
import operator

# domain

# third-party

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
VERSION = '0.1'
DEBUG_VERSION = '0.1.4'

palette = {}

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- CLASSES -- #
class Color(object):
    def __init__(self, rgb=(0, 0, 0), name=None, palette=palette):
        self.transform_gamma = 1
        self.rgb = rgb
        self._cache = {}
        self.palette = palette
        if name:
            palette[name] = self

    # ----------------------------------------------------------- Methods -- #

    # ------------------- Mutations ---------------------------------------- #
    def clamp(self):
        self.rgb = tuple([(max(min(ch, 1), 0)) for ch in self.rgb])

    def normalize(self):
        max_val = max(self.rgb)
        self.rgb = tuple([(ch / max_val) for ch in self.rgb])
        self.clamp()

    # ------------------- Returns New Instances ---------------------------- #
    def clone(self):
        return Color(self.rgb)

    def tints(self, steps=8):
        return interpolate(self, WHITE, gamma=(1 / self.transform_gamma),
                           steps=steps)

    def shades(self, steps=8):
        return interpolate(self, BLACK, gamma=(1 / self.transform_gamma),
                           steps=steps)

    # -------------------------------------------------------- Properties -- #
    @property
    def rgb_int(self):
        return tuple(rgb_float_to_int(self.rgb))

    @rgb_int.setter
    def rgb_int(self, rgb):
        self.rgb = rgb_int_to_float(rgb)

    @property
    def rgb(self):
        return self._rgb

    @rgb.setter
    def rgb(self, rgb):
        self._rgb = tuple(rgb)
        self._cache = {}

    @property
    def rgb_css(self):
        return 'rgb{}'.format(tuple(self.rgb_int))

    @property
    def hsv(self):
        return self._cache.setdefault('hsv', rgb_to_hsv(*self.rgb))

    @hsv.setter
    def hsv(self, hsv):
        self.rgb = hsv_to_rgb(*hsv)

    @property
    def hue(self):
        return self.hsv[0]

    @hue.setter
    def hue(self, hue):
        _, sat, val = self.hsv
        self.hsv = (hue, sat, val)

    @property
    def saturation(self):
        return self.hsv[1]

    @saturation.setter
    def saturation(self, sat):
        hue, _, val = self.hsv
        self.hsv = (hue, sat, val)

    @property
    def hex(self):
        return self._cache.setdefault('hex', rgb_to_hex(self.rgb))

    @hex.setter
    def hex(self, hexa):
        self.rgb = hex_to_rgb(hexa)

    @property
    def hex_css(self):
        return '#{}'.format(self.hex)

    @property
    def luminance(self):
        red, green, blue = self.rgb
        red = 0.212656 * red
        green = 0.715158 * green
        blue = 0.0721856 * blue
        return red + green + blue

    @property
    def tile_color(self):
        """convenience method for getting an integer appropriate for use
        with the tile colors in NUKE
        """
        return int((self.hex + 'ff'), base=16)

    # ------------------------------------------------------ Constructors -- #
    @classmethod
    def from_rgb_float(cls, rgb, name=None):
        instance = cls(name=name)
        instance.rgb = rgb
        return instance

    @classmethod
    def from_rgb_int(cls, rgb, name=None):
        rgb_float = rgb_int_to_float(rgb)
        return cls.from_rgb_float(rgb_float, name)

    @classmethod
    def from_hsv(cls, hsv, name=None):
        rgb = hsv_to_rgb(hsv)
        return cls.from_rgb_float(rgb, name)

    @classmethod
    def from_hex(cls, hexa, name=None):
        return cls.from_rgb_float(hex_to_rgb(hexa))

    # ------------------------------------------------------------- Magic -- #
    def __repr__(self):
        return "<Color rgb({})>".format(self.rgb)

    # ------------------- Arithmetic --------------------------------------- #
    # all arithmetic operations are handled using RGB

    def _arithmetic(self, other, op):
        try:
            new_rgb = [op(ch1, ch2) for ch1, ch2 in zip(self, other)]
        except TypeError:
            try:
                new_rgb = [op(ch, other) for ch in self]
            except TypeError:
                raise
        return Color(new_rgb)

    def __add__(self, other):
        return self._arithmetic(other, operator.add)

    def __sub__(self, other):
        return self._arithmetic(other, operator.sub)

    def __mul__(self, other):
        return self._arithmetic(other, operator.mul)

    def __truediv__(self, other):
        return self._arithmetic(other, operator.truediv)

    def __floordiv__(self, other):
        return self._arithmetic(other, operator.floordiv)

    def __pow__(self, other):
        return self._arithmetic(other, operator.pow)

    # ------------------------------------------ Iteration And Membership -- #
    def __iter__(self):
        return iter(self.rgb)


# --------------------------------------------------------- Global Colors -- #
BLACK = Color((0, 0, 0), 'BLACK')
WHITE = Color((1, 1, 1), 'WHITE')
MID_GRAY = Color((.5, .5, .5), 'MID_GRAY')
RED = Color((1, 0, 0), 'RED')
ORANGE = Color((1, .5, 0), 'ORANGE')
YELLOW = Color((1, 1, 0), 'YELLOW')
YELLOW_GREEN = Color((.5, 1, 0), 'YELLOW_GREEN')
GREEN = Color((0, 1, 0), 'GREEN')
CYAN = Color((0, 1, 1), 'CYAN')
BLUE = Color((0, 0, 1), 'BLUE')
MAGENTA = Color((1, 0, 1), 'MAGENTA')


# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #
def interpolate(color_one, color_two, steps=8, via='rgb', gamma=1):
    # valid values for via are 'rgb' and 'hsv'
    colors = [None] * steps
    channels_one = getattr(color_one, via)
    channels_two = getattr(color_two, via)
    diff = [(ch2 - ch1) for ch1, ch2 in zip(channels_one, channels_two)]
    # this is not a valid use of gamma, really.  The "gamma" value ends up
    # being a bias towards one end of the range or another
    gamma_lut = [((i / (steps - 1)) ** gamma) for i in range(steps)]
    colors[0] = color_one.clone()
    for i in range(1, (steps - 1)):
        new_values = [channels_one[j] + (diff_ch * gamma_lut[i])
                      for j, diff_ch, in zip(range(3), diff)]
        next_color = Color()
        setattr(next_color, via, new_values)
        colors[i] = next_color
    colors[-1] = color_two.clone()
    return colors


# -- RGB Conversion -------------------------------------------------------- #
def rgb_float_to_int(rgb):
    return [int(ch * 255.999) for ch in rgb]

def rgb_int_to_float(rgb):
    return [(float(ch) / 255.0) for ch in rgb]


# -- Hexadecimel Conversion ------------------------------------------------ #
_NUMERALS = '0123456789abcdefABCDEF'
_HEXDICT = {v: int(v, 16) for v in (x + y for x in _NUMERALS
                                    for y in _NUMERALS)}

LOWERCASE, UPPERCASE = 'x', 'X'

def hex_to_rgb(hexa):
    rgb = (_HEXDICT[hexa[0:2]],
           _HEXDICT[hexa[2:4]],
           _HEXDICT[hexa[4:6]])
    return rgb_int_to_float(rgb)

def rgb_to_hex(rgb, lettercase=LOWERCASE):
    rgb = rgb_float_to_int(rgb)
    return format(rgb[0] << 16 | rgb[1] << 8 | rgb[2], '06' + lettercase)


# -------------------------------------------------------------------------- #
# ---------------------------------------------------------- EXAMPLE CODE -- #
def example():
    from PySide import QtGui
    import sys
    steps = 75
    color_one = RED
    color_two = CYAN
    rgb_gradient = interpolate(color_one, color_two, steps=steps, via='rgb')
    hsv_gradient = interpolate(color_one, color_two, steps=steps, via='hsv')
    qapp = QtGui.QApplication([])
    frame = QtGui.QFrame()
    main_layout = QtGui.QVBoxLayout()
    frame.setLayout(main_layout)
    for gradient in (rgb_gradient, hsv_gradient):
        layout = QtGui.QHBoxLayout()
        layout.setSpacing(0)
        main_layout.addLayout(layout)
        for i in range(steps):
            but = QtGui.QPushButton()
            layout.addWidget(but)
            but.setFixedWidth(10)
            but.setFixedHeight(40)
            style = 'background-color: {};\nborder: 0px solid black;'.format(gradient[i].rgb_css)
            but.setStyleSheet(style)
    frame.show()
    sys.exit(qapp.exec_())

# example()
