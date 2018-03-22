# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@organization: Kludgeworks LLC

@description: utilities for accessing nodes using the Open Maya api.

@author: Ed Whetstone

@applications: MAYA

TODO: Need to add specific controls for kMatrix data types in ApiAttribute
TODO: Consider a new methodology with ApiAttribute, using asMObject()
TODO: Need a robust check of plug caching and fn_dag caching to see if
      there is any benefit to these methods
TODO: Need an always-serializable ApiAttribute return
TODO: Need to test array-attribute controls
"""

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# built-in
import re
from contextlib import contextmanager

# internal
import vfx_utils.omni.slog as slog
from vfx_utils.omni.data_types import cached_property, allocated_list

# third-party
from PySide2.QtCore import QFile

# domain
import maya.cmds as cmds
import maya.OpenMaya as om
import maya.OpenMayaAnim as oma

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #

# ------------------- Version Information ---------------------------------- #
VERSION = '4.0'
DEBUG_VERSION = '4.1.12'

# ------------------- Logging ---------------------------------------------- #
logger = slog.Logger()

# ------------------- Null Object ------------------------------------------ #
# for reasons unknown, the kNullObj attribute returns a bare property object,
# whose getter must then be called to return the actual null object. Hence
# the weird syntax below
null_obj = om.MObject.kNullObj.fget()

# ------------------- Caches ----------------------------------------------- #
# cache of all types enumerated in MFn::Type
_fn_type_dict = dict()
# cache of MFnData::Type
_fn_data_type_dict = dict()
# cache of MFnNumericData::Type
_fn_numeric_data_type_dict = dict()
# cache of MFnUnitData::Type
_fn_unit_type_dict = dict()

# ------------------- Regexes ---------------------------------------------- #
# for checking to see if a string is a UUID
uuid_check = re.compile('[A-Z0-9]{8}-.+')

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------ SINGLETONS -- #
# Constraining instance creation of the MFn* and MSelectionList classes
# speeds up OpenMaya quite a lot.  Here we're also aliasing some common
# functions to increase performance even more.

# ------------------- Function Sets ---------------------------------------- #
_fn_dag = om.MFnDagNode()
_cur_fn_dag = None
_fn_dag_set_obj = _fn_dag.setObject
_fn_dg = om.MFnDependencyNode()
_cur_fn_dg = None
_fn_dg_set_obj = _fn_dg.setObject
_fn_attr = om.MFnAttribute()
_fn_attr_set_obj = _fn_attr.setObject
_fn_numeric_attr = om.MFnNumericAttribute()
_fn_numeric_attr_set_obj = _fn_numeric_attr.setObject
_fn_enum_attr = om.MFnEnumAttribute()
_fn_enum_attr_set_obj = om.MFnEnumAttribute.setObject
_fn_typed_attr = om.MFnTypedAttribute()
_fn_typed_attr_set_obj = _fn_typed_attr.setObject
_fn_unit_attr = om.MFnUnitAttribute()
_fn_unit_attr_set_obj = _fn_unit_attr.setObject

_fn_anim_curve = oma.MFnAnimCurve
_fn_anim_curve_set_obj = _fn_anim_curve.setObject

_at_frame = om.MTime

_fn_set_list = om.MGlobal.getFunctionSetList

# ------------------- Selection Lists -------------------------------------- #
_tmp_sel_list = om.MSelectionList()
_tmp_sel_list_add = _tmp_sel_list.add
_tmp_sel_list_clear = _tmp_sel_list.clear

# ------------------- Arrays ----------------------------------------------- #
_mplug_array = om.MPlugArray()
_mplug_array_clear = _mplug_array.clear
_mplug_array_len = _mplug_array.length

# ------------------- Global Modifiers ------------------------------------- #
_m_global = om.MGlobal
is_selected = _m_global.isSelected

# -------------------------------------------------------------------------- #
# --------------------------------------------------- MAYA API CONVERSION -- #
class ApiNode(object):
    """The ApiNode is an adapter to various node functions available in
    the Maya Python Api."""

    def __init__(self, obj):
        """Set up the instance attributes for this node. Many attributes
        are handled as cached, lazily-evaluated properties.  See the
        cached_property decorator to learn more."""
        # obj must be an OpenMaya MObject
        self.obj = obj
        self._shape = None
        self._uuid = None
        self._dag_path = None
        self._plugs = {}
        self._attrs = {}

    # --------------------------------------- Alternate Constructors -- #
    @classmethod
    def from_cmd(cls, cmd, *args, **kwargs):
        """Alternate constructor.  Use a command found in the maya.cmds
        module to construct the node."""
        node_string = getattr(cmds, cmd)(*args, **kwargs)
        if isinstance(node_string, list):
            node_string = node_string[0]
        return cls.from_string(node_string)

    @classmethod
    def from_string(cls, object_name):
        """Alternate constructor.  Use a string representation to build
        the ApiNode"""
        api_node = cls(mobj_from_string(object_name))
        # because we already know the name of the node, we can go ahead
        # and assign its lazily-cached attribute
        api_node._name = object_name
        return api_node

    @classmethod
    def from_mobject(cls, mobject):
        """Alternate constructor. Use an MObject to construct the
        ApiNode"""
        return cls(mobject)

    @classmethod
    def from_ambiguous(cls, mobject_string_or_apinode):
        """Alternate constructor.  Use either a string, MObject, ApiNode,
        or uuid to create the ApiNode"""
        if isinstance(mobject_string_or_apinode, cls):
            return mobject_string_or_apinode
        else:
            return cls(mobj_from_any(mobject_string_or_apinode))

    @classmethod
    def from_uuid(cls, uuid_as_string):
        """Alternate constructor. Use a string-representation of a uuid
        to construct a new ApiNode"""
        mobject = mobj_from_uuid(uuid_as_string)
        return cls(mobject)

    # --------------------------------------- METHODS AND PROPERTIES -- #
    # -------------- Plugs and Attributes ----------------------------- #
    def plug(self, plug_name):
        """retrieve the plug with the given name."""
        try:
            _plug = self._plugs.setdefault(plug_name, self.fn_dg.findPlug(plug_name))
        except RuntimeError:
            error_msg = ('the given node {0} does not have an attribute '
                         'called {1}'.format(self.name, plug_name))
            raise AttributeError(error_msg)
        return _plug

    def attr(self, attr_name, extend_to_shape=True):
        """create an ApiAttribute for the given attribute name. Result is
        cached to instance dict - see self._attrs"""
        # see if attr object is cached
        try:
            return self._attrs[attr_name]
        except:
            pass
        # the shenanigans below are necessary in order to check against
        # a bunch of different potential failure states.
        _attr = None
        try:
            _attr = ApiAttribute(self.plug(attr_name))
        except AttributeError:
            error_msg = ('the given node {0} does not have an attribute '
                         'called {1}'.format(self.name, attr_name))
            if extend_to_shape:
                try:
                    _attr = ApiAttribute(self.shape.plug(attr_name))
                except TypeError:
                    raise AttributeError(error_msg)
                except RuntimeError:
                    if self.api_type == self.parent.api_type:
                        raise AttributeError(error_msg)
                    try:
                        _attr = ApiAttribute(self.parent.plug(attr_name))
                    except AttributeError:
                        raise AttributeError(error_msg)
            else:
                raise AttributeError(error_msg)
        # assuming that one of the checks above allowed an attribute object
        # to be created, cache and return the new object
        self._attrs[attr_name] = _attr
        return _attr

    @property
    def all_plugs(self):
        """list all top-level plugs on this ApiNode"""
        _fn_dg_set_obj(self.obj)
        attr_objs = [_fn_dg.attribute(i) for i in range(_fn_dg.attributeCount())]
        plugs = [om.MPlug(self.obj, attr) for attr in attr_objs]
        # we ignore children because they are accounted for by the parents
        return [plug for plug in plugs if not plug.isChild()]

    def list_attributes(self, extend_to_shape=True):
        """get a list of all attributes on this node as ApiAttributes."""
        plugs = self.all_plugs
        if extend_to_shape:
            try:
                shape = self.shape
            except TypeError:
                pass
            else:
                if shape and shape != self:
                    plugs.extend(shape.all_plugs)
        return [ApiAttribute(plug) for plug in plugs]

    def has_attribute(self, attribute_as_string):
        return attribute_as_string in cmds.listAttr(self.name)

    @property
    def all_connected_plugs(self):
        """list all plugs on this ApiNode with external connections"""
        _mplug_array_clear()
        try:
            self.fn_dg.getConnections(_mplug_array)
        # maya throws an error if no connections are found.
        # Unfortunately this will hide any other exceptions, so we tread
        # VERY carefully.
        except RuntimeError:
            return []
        else:
            num_plugs = _mplug_array_len()
            plugs = allocated_list(num_plugs)
            for i in range(num_plugs):
                # making a copy of the plug object prevents maya crash
                plugs[i] = om.MPlug(_mplug_array[i])
            return plugs

    def list_connections(self, mode='destination', extend_to_shape=True):
        """get a list of all connections on this node as ApiAttributes"""
        plugs = self.all_connected_plugs
        if extend_to_shape:
            try:
                shape = self.shape
            except TypeError:
                pass
            else:
                if shape and shape != self:
                    plugs.extend(shape.all_connected_plugs)
        if mode == 'destination':
            return [ApiAttribute(plug) for plug in plugs
                    if plug.isDestination()]
        elif mode == 'source':
            return [ApiAttribute(plug) for plug in plugs if plug.isSource()]
        elif mode == 'all':
            return [ApiAttribute(plug) for plug in plugs]

    @property
    def inputs(self):
        return self.list_connections(mode='destination')

    @property
    def input_connections(self):
        return [(inp.value, inp) for inp in self.inputs]

    @property
    def outputs(self):
        return self.list_connections(mode='source')

    @property
    def output_connections(self):
        return [(outp.value, outp) for outp in self.outputs]

    def _pprint_cons(self, cons):
        con_repr = '\n'.join(['{} >> {}'.format(con1.full_name, con2.full_name)
                             for con1, con2 in cons])
        logger.info(con_repr)

    def pprint_inputs(self):
        self._pprint_cons(self.input_connections)

    def pprint_outputs(self):
        self._pprint_cons(self.output_connections)

    @property
    def shading_group(self):
        """attempt to get the shading group of the api_node. Errors out
        on any incompatible types"""
        try:
            dests = [a.api_node for a in self['instObjGroups'][0].destinations]
        except:
            raise TypeError
        else:
            for dest in dests:
                if dest.api_type == 'kShadingEngine':
                    return dest

    # ------------------- UUIDs and Naming ---------------------------- #
    def new_uuid(self):
        """assign a new uuid to this node."""
        new_uuid = om.MUuid()
        new_uuid.generate()
        self.fn_dg.setUuid(new_uuid)
        # clears the previously-cached version of the uuid attribute
        # it will be re-cached when accessed again
        delattr(self, 'uuid')

    @property
    def name(self):
        """unicode representation of the node's name"""
        return self.fn_dg.name()

    @name.setter
    def name(self, new_name):
        """set the name of the node"""
        with dg_modifier() as modifier:
            modifier.renameNode(self.obj, new_name)

    @property
    def long_name(self):
        """return the full path name for dag nodes, or just the name of
        the dg node"""
        try:
            return self.fn_dag.fullPathName()
        except TypeError:
            return self.name

    @property
    def short_name(self):
        """return the short name of the node, not guaranteed to be unique"""
        return msplit(self.long_name)[-1]

    # ------------------- Function Sets ------------------------------- #
    @property
    def fn_dag(self):
        """return the DAG function set for this node"""
        global _cur_fn_dag
        obj = self.obj
        if _cur_fn_dag is obj:
            return _fn_dag
        try:
            _fn_dag_set_obj(obj)
        except RuntimeError:
            raise TypeError('A RuntimeError was caught in fn_dag.  This could '
                            'be caused by trying to get a fn_dag from a '
                            'non-dag object:\n{}'.format(self.name))
        except:
            # any other weirdness, just raise the error...
            raise
        else:
            _cur_fn_dag = obj
            return _fn_dag

    @property
    def fn_dg(self):
        """return the DG function set for this node"""
        global _cur_fn_dg
        obj = self.obj
        if _cur_fn_dg is obj:
            return _fn_dg
        _fn_dg_set_obj(obj)
        _cur_fn_dg = obj
        return _fn_dg

    # ------------------- Statuses ------------------------------------ #
    @property
    def is_alive(self):
        return self.handle.isAlive()

    @property
    def is_valid(self):
        return self.handle.isValid()

    @property
    def is_selected(self):
        return is_selected(self.obj)

    # ------------------- Locking ------------------------------------- #
    @property
    def locked(self):
        return bool(self.fn_dg.isLocked())

    @locked.setter
    def locked(self, lock_status):
        self.fn_dg.setLocked(lock_status)

    def lock(self):
        self.locked = False

    def unlock(self):
        self.locked = True

    # ------------------- Hierarchy ----------------------------------- #
    @property
    def is_dag(self):
        return self.obj.hasFn(om.MFn.kDagNode)

    @property
    def parent(self):
        if self.fn_dag.parentCount() > 0:
            parent_mobj = self.fn_dag.parent(0)
            return ApiNode.from_mobject(parent_mobj)
        else:
            return None

    @parent.setter
    def parent(self, api_node):
        with dag_modifier() as modify_stack:
            try:
                modify_stack.reparentNode(self.obj, api_node.obj)
            except:
                if api_node is None:
                    modify_stack.reparentNode(self.obj)
                else:
                    logger.debug('An error was raised while attempting to '
                                 'reparent {0}'.format(self.name))
                    raise

    def adopt(self, api_node):
        api_node.parent = self

    @property
    def children(self):
        children = []
        for i in range(self.fn_dag.childCount()):
            children.append(self.fn_dag.child(i))
        return [ApiNode.from_mobject(child) for child in children]

    @property
    def descendants(self):
        return [ApiNode.from_mobject(n) for n in descendants_of(self.obj)]

    @property
    def ancestors(self):
        return [ApiNode.from_mobject(n) for n in ancestors_of(self.obj)]

    @property
    def dag_path_object(self):
        if self._dag_path:
            return self._dag_path
        dag_path = om.MDagPath()
        try:
            self.fn_dag.getPath(dag_path)
        except RuntimeError:
            # if the node is not DAG, then this will fire
            raise TypeError('RuntimeError caught while trying to get '
                            'the dag path of {0}.  The node might not '
                            'be a DAG object'.format(self.name))
        else:
            return dag_path

    @property
    def shape(self):
        # TODO: refactor?
        if self._shape:
            return self._shape
        try:
            dag_path = self.dag_path_object
        except TypeError:
            raise TypeError('TypeError caught while trying to get the '
                            'shape of {0}.  The node might not be a DAG '
                            'object, or might not have a Shape'
                            ''.format(self.name))
        else:
            try:
                dag_path.extendToShape()
            except:
                self._has_shape = False
                self._shape = None
                return None
            else:
                node = dag_path.node()
                if node == self.obj:
                    self._has_shape = False
                    return self
                else:
                    self._has_shape = True
                    self._shape = ApiNode.from_mobject(dag_path.node())
                    return self._shape

    # ------------------------------------------------ Node Deletion -- #
    def delete(self):
        """interface to the safest method of node deletion, using the
        cmds module"""
        cmds.delete(self.long_name)

    # ----------------------------------------- Icons and UI Helpers -- #
    @cached_property
    def icon_path(self):
        """return the path to the QT-accessible icon in Maya for the node
        associated with this node"""
        try:
            shape = self.shape
        except TypeError:
            shape = self
        if shape is None:
            shape_type = "kTransform"
        else:
            shape_type = shape.api_type
        out_icon_name = ':/out_{}{}.png'.format(shape_type[1:2].lower(),
                                                shape_type[2:])
        test_file = QFile(out_icon_name)
        return out_icon_name if test_file.exists() else ':/out_default.png'

    # -------------------------------------------- Cached Properties -- #
    @cached_property
    def mhash(self):
        return self.handle.hashCode()

    @cached_property
    def handle(self):
        return om.MObjectHandle(self.obj)

    @cached_property
    def type_name(self):
        return self.fn_dg.typeName()

    @cached_property
    def inherited_types(self):
        """return a list of inherited types"""
        try:
            return cmds.nodeType(self.name, inherited=True)
        except RuntimeError:
            # in the case that we're testing the World Node, maya gets
            # confused because the World has no name
            try:
                return [self.type_name]
            except:
                logger.debug('Error caught attempting to get the list '
                             'of inherited types of {}'.format(self))
                raise

    @cached_property
    def api_type(self):
        return self.obj.apiTypeStr()

    @cached_property
    def uuid(self):
        uuid = self.fn_dg.uuid().asString()
        return uuid

    # ----------------------------------------------------- Magic Methods -- #
    def __hash__(self):
        return hash(self.mhash)

    def __eq__(self, other):
        try:
            return self.uuid == other.uuid
        except AttributeError:
            return False
        else:
            return False

    # ------------------- Get and Set Maya Attributes ---------------------- #
    def __getitem__(self, attr_name):
        try:
            return self.attr(attr_name)
        except AttributeError:
            msg = ('An error was reported trying to get the attribute {0} on '
                   'the node {1}, attempting to use the shape or transform ',
                   'nodes to acquire the attribute'
                   ''.format(attr_name, self.name))
            raise AttributeError(msg)

    def __setitem__(self, attr_name, value):
        self.attr(attr_name).value = value

    def __repr__(self):
        return '<ApiNode {} {}>'.format(self.api_type, self.name)

# ------------------------------------------------------------------------ #
# ---------------------------------------------------------- WORLD NODE -- #
class WorldNode(object):
    """The WorldNode is a convenience class for retrieving the top-most
    node of the DAG.  It's never directly instantiated."""
    root = None
    root_path = None

    def __init__(self):
        raise NotImplementedError('WorldNode is meant to be used as a simple '
                                  'cache for the root mobject, not directly '
                                  'instantiated.')

    @classmethod
    def get_root(cls):
        """retrieve the top node from the DAG"""
        root = cls.root
        if root:
            return root
        else:
            blank_dag_it = om.MItDag()
            root = blank_dag_it.root()
            cls.root = root
            return root

    @classmethod
    def get_root_path(cls):
        """retrieve the path to the root object"""
        root_path = cls.root_path
        if root_path:
            return root_path
        else:
            blank_dag_it = om.MItDag()
            root_path = om.MDagPath()
            blank_dag_it.getPath(root_path)
            cls.root_path = root_path
            return root_path


# -------------------------------------------------------------------------- #
# ----------------------------------------------------- ATTRIBUTE CONTROL -- #
# define the getters and setters for base data types in attributes
getset_bool = (om.MPlug.asBool, om.MPlug.setBool)
getset_int = (om.MPlug.asInt, om.MPlug.setInt)
getset_float = (om.MPlug.asFloat, om.MPlug.setFloat)
getset_double = (om.MPlug.asDouble, om.MPlug.setDouble)
getset_string = (om.MPlug.asString, om.MPlug.setString)
getset_char = (om.MPlug.asChar, om.MPlug.setChar)

class ApiAttribute(object):
    """ApiAttribute is an interface class to maya attributes."""
    # --------------------------------------------- Class Attributes -- #
    getter_setters = {'kBoolean': getset_bool,
                      'kByte': getset_int,
                      'kInt': getset_int,
                      'k3Int': getset_int,
                      'kInt64': getset_int,
                      'kShort': getset_int,
                      'kEnumAttribute': getset_int,
                      'kFloat': getset_float,
                      'k2Float': getset_float,
                      'k3Float': getset_float,
                      'kUnitAttribute': getset_float,
                      'kDistance': getset_double,
                      'kDouble': getset_double,
                      'k2Double': getset_double,
                      'k3Double': getset_double,
                      'k4Double': getset_double,
                      'kString': getset_string,
                      'kChar': getset_char,
                      }

    # ----------------------------------------------------- Methods -- #

    def __init__(self, plug):
        """A new ApiAttribute instance requires a plug object to
        initialize. Use the alternate constructors to work from other
        starting places.
        """
        # ------------------- Instance Attrs ------------------------- #
        self.plug = plug
        self.attribute = plug.attribute()
        self.full_name = str(plug.name())
        # TODO: make the short name a cachable lazy property
        self.name = ''.join(self.full_name.split('.')[1:])
        self.attr_type = attr_type(self.attribute)
        self.is_array = plug.isArray()
        self.is_compound = plug.isCompound()
        self.data_type = data_type(self.attribute, self.attr_type)
        # ------------------- Instance Getters and Setters ----------- #
        self.getter_setters = dict(ApiAttribute.getter_setters)
        self.getter_setters.update(self.instance_getter_setters)
        getset = self.getter_setters.get(self.data_type,
                                         (self._get_unhandled,
                                          self._set_unhandled))
        self.getter, self.setter = getset
        # ------------------- Caches --------------------------------- #
        self._apinode = None

    @property
    def instance_getter_setters(self):
        """the dictionary of attribute getters and setters specific to
        this particular instance
        """
        return {'kMessageAttribute': (self._get_message, self._set_message),
                'kAngle': (self._get_angle, self._set_angle),
                'kMatrix': (self._get_matrix, self._set_unhandled)}

    # -------------------------------------- Alternate Constructors -- #
    @classmethod
    def from_string(cls, string_attribute):
        """Alternate Constructor. Use a string objectName.attributeName
        to create a new ApiAttribute
        """
        try:
            name, attr = string_attribute.split('.')
        except ValueError:
            msg = ('An error was reported while parsing the string {0}. '
                   'This could be caused by bad formatting'
                   ''.format(string_attribute))
            raise ValueError(msg)
        else:
            mobject = mobj_from_string(name)
            return cls.from_mobj_and_attr(mobject, attr)

    @classmethod
    def from_mobj_and_attr(cls, mobject, attr):
        """Alternate Constructor. Use an mobject and a string attribute
        to create the new ApiAttribute
        """
        _fn_dg_set_obj(mobject)
        try:
            plug = _fn_dg.findPlug(attr)
        except RuntimeError:
            msg = ('An error was thrown attempting to get the ApiAttribute '
                   'for {0}.{1}'.format(name_of(mobject), attr))
            raise AttributeError(msg)
        return cls(plug)

    @classmethod
    def from_apinode_and_string(cls, api_node, attr):
        """Alternate Constructor. Given an ApiNode and an attribute
        string, return the ApiAttribute. This is the constructor used by
        the ApiNode['attributeKey'] pattern.
        """
        instance = cls(api_node.plug(attr))
        instance._apinode = api_node
        return instance

    # -------------------------------------------------- Properties -- #
    # -- Connection Properties --------------------------------------- #
    @property
    def connected(self):
        return self.plug.isConnected()

    @property
    def source(self):
        return ApiAttribute(self.plug.source())

    @property
    def destinations(self):
        _mplug_array_clear()
        self.plug.destinations(_mplug_array)
        num_plugs = _mplug_array_len()
        dest_array = allocated_list(num_plugs)
        for i in range(num_plugs):
            dest_array[i] = ApiAttribute(_mplug_array[i])
        return dest_array

    @cached_property
    def short_name(self):
        return str(self.plug.partialName())

    @property
    def fn_attr(self):
        _fn_attr_set_obj(self.attribute)
        return _fn_attr

    @property
    def is_writable(self):
        return self.fn_attr.isWritable()

    @property
    def api_node(self):
        if self._apinode:
            return self._apinode
        else:
            node = self.plug.node()
            self._apinode = ApiNode(node)
            return self._apinode

    def _recurse_serialize(self, value):
        """this is a bit of a stopgap measure, to allow values to be
        returned as maya-friendly strings instead of ApiAttributes"""
        if isinstance(value, ApiAttribute):
            return 'connection: {}'.format(value.full_name)
        elif isinstance(value, list):
            ret_list = []
            for item in value:
                ret_list.append(self._recurse_serialize(item))
            return ret_list
        else:
            return value

    @property
    def serial_value(self):
        """this is a bit of a stopgap measure, to allow complex value
        types to be returned as maya-friendly strings instead of
        as ApiAttributes"""
        return self._recurse_serialize(self.value)

    @property
    def value(self):
        """return the value or list of values associated with the plug"""

        # ------------------- Handle Connected Attrs ----------------- #
        if self.plug.isDestination():
            _mplug_array_clear()
            self.plug.connectedTo(_mplug_array, True, False)
            return ApiAttribute(om.MPlug(_mplug_array[0]))

        # ------------------- Handle Arrays -------------------------- #
        elif self.is_array and self.data_type not in self.getter_setters:
            all_element_values = []
            element_indexes = om.MIntArray()
            self.plug.getExistingArrayAttributeIndices(element_indexes)
            for i in element_indexes:
                try:
                    element_plug = self.plug.elementByLogicalIndex(i)
                except RuntimeError:
                    logger.exception('The element you\'re attempting to '
                                     'access is not available')
                    raise
                else:
                    new_att = ApiAttribute(element_plug)
                    all_element_values.append(new_att.value)
            return all_element_values

        # ------------------- Handle Compounds ----------------------- #
        elif self.is_compound:
            compound_len = self.plug.numChildren()
            all_element_values = allocated_list(compound_len)
            # compound attributes aren't necessarily all of the same
            # type.  If the compound attr doesn't have a specific type,
            # we must recurse:
            for i in range(compound_len):
                child_plug = self.plug.child(i)
                new_att = ApiAttribute(child_plug)
                all_element_values[i] = new_att.value
            return all_element_values

        # ------------------- Handle All Other Attrs ----------------- #
        try:
            return self.getter(self.plug)
        except RuntimeError:
            # if none of the above works, log a warning and move on.
            raise
            logger.error('An error was caught trying to get the value of {0}',
                         self.full_name)
            pass

    @value.setter
    def value(self, value):

        # -- Handle Array Attrs -------------------------------------- #
        if self.is_array:
            raise TypeError('Array attributes like {0} cannot be assigned '
                            'to directly. use ApiAttribute.add() and '
                            'clear_array()'.format(self.name))

        # -- Handle Compound Attrs ----------------------------------- #
        if self.is_compound:
            try:
                enumerated_value = tuple(enumerate(value))
            except TypeError:
                raise TypeError('compound attribute {0} must be assigned '
                                'to with an iterable'.format(self.name))
            if self.data_type == 'kCompoundAttribute':
                for i, ithvalue in enumerated_value:
                    attr = ApiAttribute(self.plug.child(i))
                    attr.value = ithvalue
            else:
                for i, ithvalue in enumerated_value:
                    try:
                        self.setter(self.plug.child(i), ithvalue)
                    except:
                        if i >= self.plug.numChildren():
                            raise ValueError('Too many values passed in'
                                             'to {0}'.format(self.name))
                        else:
                            raise

        # -- Handle Single Attrs ------------------------------------- #
        else:
            try:
                self.setter(self.plug, value)
            except:
                # -- Handle Connected Attrs -------------------------- #
                if self.plug.isDestination():
                    raise TypeError('Attribute {0} is connected to another '
                                    'attribute, and cannot be set directly. '
                                    'Use ApiAttribute.disconnect() and '
                                    'connect().'.format(self.name))
                else:
                    try:
                        self.connect_from(value)
                    except:
                        raise

    @property
    def recursive_value(self):
        value = self.value
        if isinstance(value, self.__class__):
            return value.recursive_value
        else:
            return value

    # ----------------------------------------- Getters and Setters -- #
    def _get_message(self, plug):
        """return the node(s) which are connected to this message plug"""
        if plug.isArray():
            all_elements = []
            for i in range(plug.numElements()):
                element_plug = plug.elementByLogicalIndex(i)
                msg_plug = self._get_message(element_plug)
                all_elements.append(ApiAttribute(msg_plug))
            return all_elements
        elif plug.isCompound():
            all_plugs = []
            for i in range(plug.numChildren()):
                # recursive call
                child_plug = om.MPlug(plug.child(i))
                all_plugs.append(ApiAttribute(self._get_message(child_plug)))
            return [ApiAttribute(plg) for plg in all_plugs]
        elif plug.isDestination():
            _mplug_array_clear()
            plug.connectedTo(_mplug_array, True, False)
            return ApiAttribute(om.MPlug(_mplug_array[0]))
        elif '.message' in self.full_name:
            return ApiNode.from_mobject(om.MObject(plug.node()))
        else:
            return None

    def _set_message(self, plug, api_node):
        """assigns the message plug of the given api_node to the given
        attribute
        """
        raise NotImplementedError('no setter has been created for this '
                                  'attribute type')

    def _get_matrix(self, plug):
        if self.is_array:
            plug = plug.elementByLogicalIndex(0)
        matrix = om.MFnMatrixData(plug.asMObject()).matrix()
        return [[matrix(i, j) for i in range(4)] for j in range(4)]

    def _get_angle(self, plug):
        m_angle_obj = plug.asMAngle()
        return float(m_angle_obj.asDegrees())

    def _set_angle(self, plug, value):
        m_angle_obj = om.MAngle()
        m_angle_obj.setUnit(om.MAngle.kDegrees)
        m_angle_obj.setValue(value)
        plug.setMAngle(m_angle_obj)

    def _get_unhandled(self, plug):
        """in case the system does not know how to handle the given
        datatype, use cmds.getAttr to resolve.
        """
        try:
            return cmds.getAttr(self.full_name, silent=True)
        except RuntimeError:
            logger.debug('An error was reported while attempting to get '
                         'the value of {0}, using the cmds.getAttr '
                         'command'.format(self.full_name))
            return None

    def _set_unhandled(self, plug, value):
        """in case the system does not know how to handle the given
        datatype, use cmds.setAttr to resolve.
        """
        try:
            data_type = cmds.getAttr(self.full_name, typ=True)
        except RuntimeError:
            raise
        else:
            try:
                cmds.setAttr(self.full_name, value, typ=data_type)
            except RuntimeError:
                msg = ('cmds.setAttr({0}, {1}, typ={2})'
                       ''.format(self.full_name, value, data_type))
                raise RuntimeError('An error was reported while setting the '
                                   'value of {0} while attempting:\n'
                                   '"{1}"'.format(self.full_name, msg))

    # ------------------------------------------------- Connections -- #
    # TODO: implement force connection

    def connect_to(self, api_attr, force=True):
        """connect the plugs from this ApiAttribute (source) to another
        (destination).  If 'force' is True, then any existing connections
        will be removed first.
        """
        make_connection(self.plug, api_attr.plug)

    def connect_from(self, api_attr, force=True):
        """connect from another api_attr (source) to this ApiAttribute
        (destination).  If 'force' is True, then any existing connections
        will be removed first.
        """
        make_connection(api_attr.plug, self.plug)

    def disconnect(self):
        """break all connections on the given attribute"""
        break_all_connections(self.plug)

    # ---------------------------------------------- Status Control -- #
    def lock(self):
        self.plug.setLocked(True)

    def unlock(self):
        self.plug.setLocked(False)

    # ----------------------------------------------- Magic Methods -- #
    def __repr__(self):
        return '<ApiAttribute {0}>'.format(self.full_name)

    def __hash__(self):
        return hash('{}{}'.format(self.api_node.uuid, self.full_name))

    def __getitem__(self, item):
        """dictionary-style lookup treats array and compound attributes
        the same, by either providing a name for compound attrs, or an
        index for the attribute"""
        if self.is_array:
            return ApiAttribute(self.plug.elementByLogicalIndex(item))
        elif self.is_compound:
            try:
                return ApiAttribute(om.MPlug(self.plug.child(item)))
            except NotImplementedError:
                # assume the "item" is a string representing a name
                for i in range(self.plug.numChildren()):
                    child_plug = self.plug.child(i)
                    if child_plug.name().endswith(item):
                        return ApiAttribute(child_plug)
        raise TypeError('Attribute {} is not compatible with indexing'
                        ''.format(self.full_name))

    def __setitem__(self, item, value):
        self[item].value = value

    def __iadd__(self, value):
        self.value = self.value + value

# -------------------------------------------------------------------------- #
# ----------------------------------------------- FUNCTIONS AND UTILITIES -- #

# -------------------------------------------------------- Modifier Stack -- #
@contextmanager
def dg_modifier():
    modifier = om.MDGModifier()
    yield modifier
    modifier.doIt()

@contextmanager
def dag_modifier():
    modifier = om.MDagModifier()
    yield modifier
    modifier.doIt()

# ----------------------------------------------------- Attribute control -- #
def make_connection(source_plug, dest_plug, force=True):
    """connect a source plug to a destination plug, with an option to
    force the connection if one already exists"""
    with dg_modifier() as modifier:
        plug_connected = dest_plug.isDestination()
        if force and plug_connected:
            break_all_connections(dest_plug)
        elif not force and plug_connected:
            raise RuntimeError('The plug {0} is already connected'
                               ''.format(dest_plug.name()))
        modifier.connect(source_plug, dest_plug)

def break_all_connections(plug):
    """break all of the connections on a given plug"""
    if plug.isDestination():
        with dg_modifier() as modifier:
            source_plugs = om.MPlugArray()
            plug.connectedTo(source_plugs, True, False)
            source_plug = om.MPlug(source_plugs[0])
            modifier.disconnect(source_plug, plug)

def delete_attr(mobj, attr_as_mobj):
    """remove an attribute from the given mobject"""
    with dg_modifier() as modifier:
        modifier.removeAttribute(mobj, attr_as_mobj)

# ----------------------------------------------------- MObject Factories -- #
def mobj_from_any(object_name_or_uuid):
    """Create an MObject if the provided argument isn't one already.
    Compatible with MObjects, maya object string representations, and
    uuid strings
    """
    try:
        return om.MObject(object_name_or_uuid)
    except TypeError:
        try:
            return mobj_from_uuid(object_name_or_uuid)
        except RuntimeError:
            return mobj_from_string(object_name_or_uuid)

def mobj_from_string(object_name=None):
    """get an MObject from a maya string representation"""
    # clear the selection list
    _tmp_sel_list_clear()
    try:
        # converting between strings and mobjects requires pushing the
        # string repr into a selection list, then getting the MObject
        _tmp_sel_list_add(object_name)
    except:
        if object_name == '':
            # if we're passing in a root node, for example, the node
            # represented by:
            # "|group1|light1".split('|')[0]
            return WorldNode.get_root()
        else:
            raise ValueError('An exception was caught while trying to convert a '
                             'string to an MObject.  The specified node ({0}) '
                             'might not exist.'.format(object_name))
    # create an empty MObject
    obj = om.MObject()
    # populate the MObject with the first DependNode on the stack
    _tmp_sel_list.getDependNode(0, obj)
    return obj

def mobj_from_uuid(object_uuid):
    """get an MObject from a uuid as a string"""
    _tmp_sel_list_clear()
    muuid = om.MUuid(object_uuid)
    _tmp_sel_list_add(muuid)
    obj = om.MObject()
    _tmp_sel_list.getDependNode(0, obj)
    return obj

def msel_from_iter(iterator):
    """create an MSelectionList populated by an iterator"""
    msel = om.MSelectionList()
    # removing dot-access shaves precious microseconds
    add = msel.add
    for obj in iterator:
        add(obj)
    return msel

def msel_to_strings(msel):
    """get the string representations of every node in an MSelectionList"""
    strings = []
    msel.getSelectionStrings(strings)
    return strings

# ----------------------------------------------------------------- UUIDs -- #
def is_uuid(uuid):
    """verify that the given string matches a potential uuid"""
    return re.match(uuid_check, uuid)

def uuid_from_mobj(mobj):
    """given an mobject, return the uuid"""
    _fn_dg_set_obj(mobj)
    return _fn_dg.uuid().asString()

def new_uuid():
    """return a new, random uuid"""
    new_uuid = om.MUuid()
    new_uuid.generate()
    return new_uuid.asString()

def uuid_from_node_string(node_string):
    """given a string representation of a node, return the uuid"""
    mobj = mobj_from_string(node_string)
    return uuid_from_mobj(mobj)

def uuid_to_mobj(uuid):
    """given a uuid string, return the mobject"""
    raise NotImplementedError('not yet implemented')

def uuid_to_node_string(uuid):
    """given a uuid, return the name of the node as a string"""
    raise NotImplementedError('not yet implemented')

# ------------------------------------------------------------- DAG Paths -- #
def m_dag_path(object_or_name):
    if isinstance(object_or_name, om.MObject):
        return object_or_name
    else:
        sel_list = _tmp_sel_list
        sel_list.clear()
        try:
            sel_list.add(object_or_name)
        except:
            return WorldNode.get_root_path()
        else:
            dag_path = om.MDagPath()
            sel_list.getDagPath(0, dag_path)
            return dag_path

# ---------------------------------------------------------------- Hashes -- #
def maya_hash(obj):
    """get the hash of the given MObject"""
    handle = om.MObjectHandle(obj)
    return handle.hashCode()

def hash_match(match_one, match_two):
    """check to see if two mobjects have matching hashes"""
    return maya_hash(match_one) == maya_hash(match_two)

# -------------------------------------------------------------------------- #
# ---------------------------------------------------------- CMDS HELPERS -- #
# These functions are API-based versions of actions commonly undertaken using
# the maya.cmds module

# ------------------------------------------------------------- Hierarchy -- #
def parent_of(obj):
    """get the parent MObject from the given MObject"""
    _fn_dag_set_obj(obj)
    if _fn_dag.parentCount() > 0:
        parent_mobj = _fn_dag.parent(0)
        return parent_mobj
    else:
        return None

def ancestors_of(obj, node_filter=[]):
    """get the ancestor MObjects of the MObject provided"""
    # parent_of handles mobject conversion if necessary
    has_parents = True
    parent = obj
    parent_stack = []
    while has_parents:
        parent = parent_of(parent)
        if parent and parent not in node_filter:
            parent_stack.append(parent)
            has_parents = True
        else:
            has_parents = False
    return parent_stack

def shared_ancestors(objs):
    """get the ancestors common to the MObjects provided"""
    already_visited = set()
    for obj in objs:
        ancestors = ancestors_of(obj, node_filter=already_visited)
        already_visited.update(ancestors)
    return list(already_visited)

def children_of(obj):
    """get the children of the given MObject"""
    return list(iter_children(obj))

def descendants_of(obj):
    child_stack = [obj]
    for child in child_stack:
        children = children_of(child)
        child_stack.extend(children)
    # we don't want the original node
    return child_stack[1:]

def iter_children(obj):
    """"provide an iterator over the child objects of the given MObject"""
    _fn_dag_set_obj(obj)
    for i in range(_fn_dag.childCount()):
        yield _fn_dag.child(i)

def shape_of(transformobj):
    """return the shape node of a given MObject, assuming it's a
    transform node
    """
    dag_path = om.MDagPath()
    _fn_dag_set_obj(transformobj)
    _fn_dag.getPath(dag_path)
    try:
        dag_path.extendToShape()
    except:
        return None
    return dag_path.node()

def select_by_uuid(uuid=None):
    """Controlling the selection or deselection of a Maya node."""
    try:
        cmds.select(cmds.ls(uuid)[0])
    except IndexError:
        cmds.select(clear=True)

# -------------------------------------------- Naming and String Controls -- #
def name_of(obj):
    """Return the name of the given MObject, without ever raising an
    exception. In the case of an invalid node or a bad object definition,
    name_of will return 'unknown'
    """
    if obj is None:
        return ''
    try:
        _fn_dag_set_obj(obj)
    except:
        try:
            _fn_dg_set_obj(obj)
        except:
            return 'unknown'
        else:
            return _fn_dg.name()
    else:
        return _fn_dag.fullPathName()

def short_name(obj):
    return om.MFnDependencyNode(obj).name()

def mjoin(string_iterable):
    return '|'.join(string_iterable)

def msplit(maya_string_name):
    return maya_string_name.split('|')

def name_paths(maya_string_name):
    return left_fold_names(msplit(maya_string_name))

def left_fold_names(seq):
    return (mjoin(s) for s in left_fold_seq(seq))

def left_fold_seq(seq):
    return (seq[0:i] for i, _ in enumerate(seq, start=1))

# -------------------------------------------------------------------------- #
# ------------------------------------------------------ TYPES AND TYPING -- #
def type_of(obj):
    _fn_dg_set_obj(obj)
    return _fn_dg.typeName()

def shape_type(transform):
    try:
        shape_node = shape_of(transform)
    except:
        shape_node = transform
    if shape_node:
        return type_of(shape_node)
    else:
        return None

def is_group(transform):
    if type_of(transform) == u'transform' and not shape_of(transform):
        return True
    else:
        return False

def _om_enum_to_dict(enum):
    """convert an OpenMaya enumerator to a dict"""
    items = (reversed(item) for item in enum.__dict__.iteritems()
             if item[0].startswith('k'))
    return dict(items)

def fn_type_dict():
    """return a dictionary representing every entry in the OpenMaya.MFn
    enumeration (represented here by a globally-defined dictionary)
    """
    if not _fn_type_dict:
        _fn_type_dict.update(_om_enum_to_dict(om.MFn))
    return _fn_type_dict

def data_type_dict():
    """return a dictionary representing every entry in the
    OpenMaya.MFnData enumeration
    """
    if not _fn_data_type_dict:
        _fn_data_type_dict.update(_om_enum_to_dict(om.MFnData))
    return _fn_data_type_dict

def numeric_type_dict():
    """return a dictionary representing every entry in the
    OpenMaya.MFnNumericData enumeration
    """
    if not _fn_numeric_data_type_dict:
        _fn_numeric_data_type_dict.update(_om_enum_to_dict(om.MFnNumericData))
    return _fn_numeric_data_type_dict

def unit_type_dict():
    """return a dictionary representing every entry in the
    OpenMaya.MFnNumericData enumeration
    """
    if not _fn_unit_type_dict:
        _fn_unit_type_dict.update(_om_enum_to_dict(om.MFnUnitAttribute))
    return _fn_unit_type_dict

def fn_type_string_to_int(type_as_string):
    """return the MFn.kWhatever integer if it exists"""
    # type_as_string is the ascii representation of the
    # maya object.  If it doesn't convert, returns
    # kInvalid, which maps to 0
    look_for = ''.join(('k', type_as_string[0].upper(), type_as_string[1:]))
    try:
        return getattr(om.MFn, look_for)
    except:
        return om.MFn.kInvalid

# ------------------------------------------------------ Attribute Typing -- #
def attr_type(attribute):
    """retrieve the attribute type and compound status"""
    # weird API pattern, start with empty list and populate
    fn_set_list = []
    _fn_set_list(attribute, fn_set_list)
    try:
        attr_type = fn_set_list[2]
    except IndexError:
        logger.debug('Function Set List is: {0}'.format(fn_set_list))
        raise AttributeError('An error was raised attempting to get the '
                             'attribute type: {}'.format(attribute))
    else:
        return attr_type

def data_type(attribute, attr_type):
    """retrieve the data type of the attribute"""
    if attr_type == 'kNumericAttribute':
        _fn_numeric_attr_set_obj(attribute)
        return numeric_type_dict()[_fn_numeric_attr.unitType()]
    elif attr_type == 'kTypedAttribute':
        _fn_typed_attr_set_obj(attribute)
        return data_type_dict()[_fn_typed_attr.attrType()]
    elif attr_type == 'kUnitAttribute':
        _fn_unit_attr_set_obj(attribute)
        return unit_type_dict()[_fn_unit_attr.unitType()]
    else:
        return attr_type

# ------------------------------------------------- Helpers and Utilities -- #
def selected_node():
    return ApiNode.from_string(cmds.ls(sl=True)[0])

def selected_nodes():
    return [ApiNode.from_string(n) for n in cmds.ls(sl=True)]

# -------------------------------------------------------------------------- #
# ---------------------------------------------------------- EXAMPLE CODE -- #
def example():
    example_creating_api_nodes()
    example_api_attributes()
    example_attr_connections()
    example_hierarchy()

def example_creating_api_nodes():
    """runs through creating ApiNodes and accessing ApiAttributes"""
    from mirage.api_utils import ApiNode
    from omni.string_utils import make_title, label_data

    # ----------------------------------- ApiNode and ApiAttributes -- #
    print make_title('ApiNodes')

    # ------------------- Setup -------------------------------------- #
    # the command to create a new spotLight is 'shadingNode'
    new_node = cmds.shadingNode('spotLight', asLight=True)
    print label_data('new node string', new_node)

    # ------------------- ApiNodes ----------------------------------- #
    # because cmds returns strings to represent nodes, use the
    # from_string constructor in the ApiNode:
    api_node = ApiNode.from_string(new_node)
    # now we have an ApiNode!  Congrats!
    # ApiNodes provide an interface to all kinds of cool stuff under the
    # hood, like accessing attribute values.
    print label_data('new ApiNode', api_node)

    # ------------------- Other Constructors ------------------------- #
    # you can also construct an ApiNode from a maya cmds call directly:
    # from_string and from_cmd are referred to as alternate constructors
    api_node_2 = ApiNode.from_cmd('shadingNode', 'spotLight', asLight=True)
    print label_data('ApiNode from_cmd', api_node_2)

    # ------------------- Tear Down ---------------------------------- #
    # delete the node to clean up
    api_node.delete()
    api_node_2.delete()
    # cmds.delete(new_node)
    # by the way, the ApiNode object still exists, but is not valid:
    print label_data('is alive after delete', api_node.is_alive)
    print label_data('is valid after delete', api_node.is_valid)

def example_api_attributes():
    """runs through accessing and setting ApiAttributes"""
    from mirage.api_utils import ApiNode
    from omni.string_utils import make_title, label_data

    # ----------------------------------- ApiNode and ApiAttributes -- #
    print make_title('ApiAttributes')

    # ------------------- Setup -------------------------------------- #
    # the command to create a new spotLight is 'shadingNode'
    light = ApiNode.from_cmd('shadingNode', 'spotLight', asLight=True)
    cmds.refresh(force=True)

    # ------------------- ApiAttributes ------------------------------ #
    # using __getitem__ (like a dictionary lookup), we can grab an
    # ApiAttribute from our ApiNode:
    api_att = light['color']
    print label_data('color ApiAttribute', api_att)
    # get the value of the ApiAttribute:
    att_value = api_att.value
    print label_data('color value default', att_value)
    # set the value of the color
    light['color'].value = [0, 1, 0]
    new_att_value = light['color'].value
    print label_data('new color value', new_att_value)

    # ------------------- Compound and Array Attributes -------------- #
    # Array attributes can be accessed, but not set directly.
    print label_data('light xformMatrix', light['xformMatrix'].value)

    # ------------------- Tear Down ---------------------------------- #
    light.delete()

def example_attr_connections():
    from mirage.api_utils import ApiNode
    from omni.string_utils import make_title, label_data
    print make_title('Connecting Attributes')

    # ------------------- Setup -------------------------------------- #
    # start by creating a spotLight and a ramp, which we'll connect
    # to the light's color attribute.
    light_string = cmds.shadingNode('spotLight', asLight=True)
    ramp_string = cmds.shadingNode('ramp', asTexture=True)
    lightnode = ApiNode.from_string(light_string)
    rampnode = ApiNode.from_string(ramp_string)

    # ------------------- Connecting Attributes ---------------------- #
    # connect the attributes:
    rampnode['outColor'].connect_to(lightnode['color'])
    # getting the value of the ApiAttribute now returns another
    # ApiAttribute!
    att_value = lightnode['color'].value
    print label_data('connected attribute', att_value)
    # to see which attributes are connected from other nodes:
    print label_data('all connections', lightnode.list_connections())

    # ------------------- Disconnecting ------------------------------ #
    # break the connections
    lightnode['color'].disconnect()
    new_att_value = lightnode['color'].value
    print label_data('value after disconnect()', new_att_value)

    # ------------------- Tear Down ---------------------------------- #
    # clean up
    lightnode.delete()
    rampnode.delete()

def example_hierarchy():
    """how to use the ApiNode for accessing and manipulating the DAG"""
    from mirage.api_utils import ApiNode
    from omni.string_utils import make_title, label_data
    print make_title('Working with the DAG hierarchy')

    # ------------------- Setup -------------------------------------- #
    # we start out making a locator and a light
    locator = ApiNode.from_cmd('spaceLocator')
    light = ApiNode.from_cmd('shadingNode', 'spotLight', asLight=True)

    # ------------------- Parenting with ApiNode --------------------- #
    # the locator will currently have no children:
    print label_data("locator's children", locator.children)
    # let's parent the light under the locator
    light.parent = locator
    print label_data("after spotLight parented", locator.children)
    print label_data("spotLight's parent", light.parent)

    # let's move the locator and confirm that the spotlight is moved:
    print label_data("spotlight worldMatrix", light['worldMatrix'].value)
    locator['translate'] = [5, 5, 5]
    print label_data("after moving locator", light['worldMatrix'].value)
    # to parent a node to the world (thereby un-parenting it from the
    # locator), set the parent to None.
    light.parent = None
    print label_data("parent after un-parenting", light.parent)

    # ------------------- Cleanup ------------------------------------ #
    light.delete()
    locator.delete()
