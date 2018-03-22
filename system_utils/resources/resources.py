# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@organization: Kludgeworks LLC

@description: Locate resources on a network

@author: Ed Whetstone

@applications: Any

@notes: WIP

TODO: HIGH PRIO complete adjustment for platform neutrality

"""

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# built-in
import os
import re
import glob

# internal
import vfx_utils.omni.slog as slog

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
VERSION = '1.0'
DEBUG_VERSION = '1.1.9'

__all__ = ['ResourceLocator']

logger = slog.Logger()

# -------------------------------------------------------------------------- #
# ---------------------------------------------------- RESOURCE UTILITIES -- #
class ResourceLocator(object):
    """Locates files and folders according to a template. This class
    largely exists to encapsulate and control a set of Branch objects,
    which represent the actual directories (or potential paths to
    directories) on disk."""

    def __init__(self, branch_path):
        """The branch_path should be in the format
        /name_one/name_two/name_three
        the 'names' are not actual directory names, but unique keywords
        by which we can refer to the actual directories.  This helps to
        avoid collisions where multiple directories could have the same
        name but different functions.

        Until a particular branch's value is set, it is represented by
        {name_of_branch} which is handled as a wildcard in various
        functions.  Usually this will be glob-matching.
        See the Branch class for more information.

        Branches can be added to the resource locator after-the-fact by
        using add_branch()"""

        super(ResourceLocator, self).__init__()
        self.branches = {}
        if not branch_path.startswith(os.path.sep):
            raise KeyError('ResourceLocator must be initialized with a '
                           'root directory')
        if branch_path.endswith(os.path.sep):
            branch_path = branch_path[:-1]
        self.branch_path = branch_path[1:]
        self._add_branches(self.branch_path)

    def apply_path(self, path):
        """given a full path, make each directory's name the static value
        of each branch"""
        # NOTE: adjusted for Windows: use a drive letter instead of root
        if not re.match("^[a-zA-Z]:\\", path):
            raise KeyError('applied paths must start with the root')
        if path.endswith(os.path.sep):
            path = path[:-1]
        path = path[1:]
        for section, branch_name in (zip(path.split(os.path.sep),
                                         self.branch_path.split(os.path.sep))):
            self[branch_name] = section

    def add_branch(self, branch_path, **local_values):
        """
        branch_path should be in this format:
        root_name/name_one/name_two
        where root_name is a branch which has already been established.
        """
        if branch_path.startswith(os.path.sep):
            branch_path = branch_path[1:]
        if branch_path.endswith(os.path.sep):
            branch_path = branch_path[:-1]
        path_tokens = branch_path.split(os.path.sep)
        root = path_tokens[0]
        if path_tokens[0] not in self.branches:
            raise KeyError("root must be an existing branch!")
        else:
            root_branch = self.branches[root]
            new_path_split = list(root_branch.path_tokens)
            new_path_split.extend(path_tokens[1:])
            final_branch = os.path.sep.join(new_path_split)
            local_values.update(root_branch.local)
            self._add_branches(final_branch, local_values)

    @property
    def fixed_paths(self):
        fixed_path_dict = dict()
        for branch in self.branches.itervalues():
            if branch._fixed_value:
                fixed_path_dict[branch.name] = branch.value
        return fixed_path_dict

    def _add_branches(self, path, local_values=None):
        local_values = {} if not local_values else local_values
        for path_tokens in left_split(path):
            branch_name = path_tokens[-1]
            if branch_name not in self.branches:
                branch = Branch(self, path_tokens, local_values)
                self.branches[branch_name] = branch

    def __getitem__(self, item):
        """Return the branch(es) associated with the name(s) provided"""
        try:
            return self.branches[item]
        except KeyError:
            try:
                return [self.branches[x] for x in item]
            except KeyError:
                raise KeyError('no branch found for {0}'.format(item))

    def __setitem__(self, item, value):
        """Magic: Assign a value to the branch"""
        try:
            branch = self.branches[item]
        except KeyError:
            branches = self[item]
            for branch, value in zip(branches, value):
                branch.value = value
        else:
            branch.value = value

class Formatter_Descriptor(object):
    def __init__(self):
        self._formatter = None

    def formatter(self, branch):
        def callable_formatter(value):
            if branch._formatter:
                return branch._formatter(branch, value)
        return callable_formatter if branch._formatter else None

    def __get__(self, branch, cls=None):
        if cls is None:
            return self
        return self.formatter(branch)

    def __set__(self, branch, format_func):
        branch._formatter = format_func

class Branch(object):
    """Represents an actual directory on the filesystem, or a potential
    set of directories if the entire path is not set.

    The path for a branch looks for any values set by the
    ResourceLocator, then searches for any values set locally.
    """
    formatter = Formatter_Descriptor()

    def __init__(self, resource_locator, path_tokens, local=None):
        """Branches are bound to a particular resource_locator instance,
        initialized with a unique path of names.  Branch creation will
        almost always be handled by the ResourceLocator's initialization
        or add_branch methods.

        self.validator is an optional function to check the value of the
        branch against.  It will both narrow down the "options" available
        for the branch, and prevent assigning an invalid value to the
        branch

        self.formatter is an optional function which can transform an
        invalid input into the correct format.

        EXAMPLE:
        input: resource_locator['version'] = 3
        (formatter runs... 3 -> v0003)
        translated: <Branch 'version': /path/to/versions/v0003>
        """
        self.resource = resource_locator
        self.path_tokens = path_tokens
        self.name = path_tokens[-1]
        self._fixed_value = None
        self.validator = lambda x: True
        self._formatter = None
        self.local = {} if not local else local
        self.tags = []

    # -------------------------------------------------- Branch Factories -- #
    # these methods allow you to create new branches based on the locals
    # and attributes assigned to this one.

    def clone(self):
        """return a new Branch with validators, formatters, and local
        values identical to this one
        """
        new_branch = Branch(self.resource, self.path_tokens, self.local)
        new_branch._fixed_value = self._fixed_value
        new_branch.validator = self.validator
        new_branch.formatter = self.formatter
        return new_branch

    def given(self, **temp_locals):
        """create a new branch with an updated set of locals"""
        new_branch = self.clone()
        new_locals = dict(self.local)
        new_locals.update(temp_locals)
        new_branch.local = new_locals
        return new_branch

    def apply(self, apply_roots=False, **temp_locals):
        pass

    def given_path(self, path):
        path = path[:-1] if path.endswith(os.path.sep) else path
        path_values = [p for p in path.split(os.path.sep) if p]
        if len(path_values) != len(self.path_tokens):
            msg = ('the given path ({0}) does not match the path template '
                   '({1}).'.format(path, os.path.sep.join(self.path_tokens)))
            raise InvalidPathTemplateException(msg)
        new_locals = dict()
        for name, pathname in zip(self.path_tokens, path_values):
            new_locals[name] = pathname
        new_branch = self.given(**new_locals)
        new_branch._fixed_value = path_values[-1]
        return new_branch

    def apply_path(self, path, apply_roots=False):
        try:
            new_branch = self.given_path(path)
        except InvalidPathTemplateException as e:
            logger.error('an invalid path was passed to the apply method '
                         'for this branch')
            raise e
        else:
            self.resource.branches[new_branch.name] = new_branch
            if apply_roots:
                basedir, basename = os.path.split(path)
                if basedir and len(self.path_tokens) > 1:
                    self.parent.apply_path(basedir, apply_roots=True)

    def branch(self, branch_name):
        return self.resource[branch_name].given(**self.local)

    def hierarchy(self):
        children = self.children
        hierarchy_dict = dict()
        if not self.children:
            return self.files
        for branch in children:
            for option in self.options:
                given_name = {self.name: option}
                hierarchy_dict[option] = branch.given(**given_name).hierarchy()
        return hierarchy_dict
        # attempting python2.6 compatibility
        # return {option: branch.given(**{self.name: option}).hierarchy()
        #         for branch in children for option in self.options}

    @property
    def parent(self):
        """walk up the hierarchy one level, applying this branch's locals
        to the parent branch"""
        try:
            orig_parent = self.resource[self.path_tokens[-2]]
        except IndexError:
            return Branch(self.resource, [''], local=self.local)
        else:
            return orig_parent.given(**self.local)

    @property
    def children(self):
        """walk down the hierarchy one level to any branches that have
        this branch as a parent."""
        return [branch.given(**self.local)
                for key, branch in self.resource.branches.items()
                if len(branch.path_tokens) > 2 and
                branch.path_tokens[-2] == self.name]

    @property
    def _lookups(self):
        lookups = dict(self.resource.fixed_paths)
        lookups.update(self.local)
        return lookups

    def _fill(self):
        tokens = self.path_tokens
        filled_tokens = []
        lookups = self._lookups
        for token in tokens:
            if token == '':
                filled_tokens.append(token)
            elif token in lookups:
                token = lookups[token]
                filled_tokens.append(token)
            else:
                filled_tokens.append("{{{0}}}".format(token))
        return filled_tokens

    @property
    def value(self):
        """return the cached value for this branch"""
        return self._fixed_value or "{{{0}}}".format(self.name)

    @value.setter
    def value(self, val):
        """set the value for the branch.  Run the value through the
        formatter and validator, if present"""
        if self.formatter:
            val = self.formatter(val)
        if not self.validator(val):
            raise ValueError('invalid value for {0}: {1}'
                             ''.format(self.name, val))
        self._fixed_value = val

    def clear_fixed(self):
        self._fixed_value = None

    @property
    def path(self):
        """return the full path for this branch, including any unset
        fields (branches without definite values)
        return will be a string in the format:
        X:/path/to/{indeterminate}/branch
        """
        filled_path = os.path.sep.join(self._fill())
        if os.path.isdir(filled_path):
            return filled_path + os.path.sep
        else:
            return filled_path

    @property
    def paths(self):
        """return all directory paths which lead to this branch"""
        all_directories = glob_search(self.path)
        return [d for d in all_directories if os.path.isdir(d)]

    @property
    def files(self):
        """return all non-directory objects available to this branch"""
        return self._search(local_validator=os.path.isfile)

    @property
    def directories(self):
        """return all directories available to this branch"""
        return self._search(local_validator=os.path.isdir)

    def _valid(self, items):
        return [item for item in items if self.validator(item)]

    def _search(self, local_validator):
        """return all valid items contained in the paths which fulfill this
        branch's constraints"""
        all_items = [(path, os.listdir(path)) for path in self.parent.paths]
        valid_files = []
        for path, items in all_items:
            for item in items:
                joined_path = os.path.join(path, item)
                if local_validator(joined_path):
                    if self.validator(item):
                        valid_files.append(joined_path)
        return valid_files

    def ls(self):
        try:
            return self._valid(os.listdir(self.path))
        except OSError:
            if '{' in self.path:
                raise(OSError('branch "{0}" has variable ancestors: {1}',
                              self.name, self.path))
            raise

    @property
    def options(self):
        option_path = self.parent.path
        if '{' in option_path:
            raise OSError('branch "{0}" has variable ancestors: {1}'
                          ''.format(self.name, self.path))
        return self._valid(self.parent.ls())

    def __getitem__(self, branch_name):
        return self.branch(branch_name)

    def __setitem__(self, branch_name, value):
        branch = self.resource[branch_name].clone()
        branch.value = value
        self.local[branch_name] = branch.value

    def __iter__(self):
        return iter(self.ls)

    def __str__(self):
        return "Branch '{0}': {1}".format(self.name, self.path)

    def __repr__(self):
        return "<{0}>".format(self.__str__())

class InvalidPathTemplateException(Exception):
    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- HELPERS -- #
def left_split(path):
    """given a path, return a list of lists folding left.  For example:
    in: 'root/path/file'
    out: [['root'], ['root', 'path'], ['root', 'path', 'file']]
    """
    path = path.split(os.path.sep)
    return [path[0:(i + 1)] for i in range(len(path))]


# this regex allows us to use a /{name}/ wildcard pattern for unix-style
# path lookups, which usually are /*/ for wildcards.
format_pat = re.compile("\{.*?\}")

def glob_search(path_string):
    """return all paths that resolve the given string in the format:
    /root/path/*/file
    or:
    /root/path/{var}/file
    """
    posix_search = re.sub(format_pat, "*", path_string)
    return glob.glob(posix_search)
