# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@organization: Kludgworks LLC

@description: tools for synchronizing files from one directory to another

@author: Ed Whetstone

@applications: all

Note:

Throughout this module, we use the terms 'origin' and 'destination' to
refer to the directories we want to copy from and to, respectively.
The built-in module filecmp.dircmp refers to 'left' and 'right'
in the same way, and other third-party tools will use 'source' and
'destination'.

TODO: this tool could benefit from threading
TODO: update logger commands for lazy formatting
TODO: lift directory walk options to separate module?
TODO: add formatting options to copytree
TODO: needs a good PEP-8-ing

"""
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# built-in
from __future__ import print_function
import os
import shutil
import time
import getpass

# internal
import vfx_utils.omni.slog as slog
from vfx_utils.omni.data_types import cached_property
from vfx_utils.omni.string_utils import LINE, EQ_LINE, DASH_LINE

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
# ------------------- Version Info ----------------------------------------- #
VERSION = '2.2'
DEBUG_VERSION = '2.2.1'

# ------------------- Logging ---------------------------------------------- #
logger = slog.Logger()

# ------------------- Pretty Printing -------------------------------------- #
# when displaying error messages, use the X_LINE
X_LINE = ('Xx' * 25)

# ------------------- File Filtering --------------------------------------- #
IGNORE_FILES = ['lock_file.txt', 'snapshot.txt']

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- CLASSES -- #

# ------------------------------------------------------ Context Managers -- #
class LockedDirectoryCtx(object):
    """provides a context manager for locking and unlocking a directory.
    In practice, this means making a small text file in the directory to
    claim ownership, or checking to see if another user has done the
    same.

    USAGE:
    lock_these = ['/lock/this/dir', 'lock/that/dir']
    with LockedDirectoryCtx(lock_these) as my_lock:
        if my_lock:
            ... lock succeeded, do things ...
        else:
            ... lock failed, do things...
            # use my_lock.locking_user to report what user is currently
            # occupying the folder
            # my_lock.lock_failed is a boolean indicating success or
            # failure of the lock process
    """

    def __init__(self, directories_to_lock):
        super(LockedDirectoryCtx, self).__init__()
        self.directories = directories_to_lock
        self.user = getpass.getuser()
        self.locking_user = self.user
        self.locks = []
        self.locked = False
        self.lock_failed = False

    def __enter__(self):
        logger.debug(LINE)
        logger.debug("submitting locks...")
        for directory in self.directories:
            file_lock_path = os.path.join(directory, 'lock_file.txt')
            if os.path.isfile(file_lock_path):
                self.locked = False
                with open(file_lock_path) as lock_file:
                    self.locking_user = lock_file.readline()
                logger.debug('the directory {0}\nis currently locked by '
                             '{1}', directory, self.locking_user)
                logger.debug(LINE)
                break
            else:
                try:
                    lock_file = open(file_lock_path, 'w')
                except Exception as e:
                    logger.debug("locking failed!!")
                    logger.debug(X_LINE)
                    logger.debug(e)
                    self.lock_failed = True
                    self.locked = False
                    break
                else:
                    with lock_file:
                        lock_file.write(self.user)
                    self.locked = True
                    self.locks.append(file_lock_path)
                    logger.debug("lock submitted!")
        return self

    def __exit__(self, *args, **kwargs):
        logger.debug(LINE)
        logger.debug("releasing locks...")
        if not self.locks:
            logger.debug("no locks to release, continuing...")
            logger.debug(LINE)
        for lock in self.locks:
            try:
                os.remove(lock)
            except Exception as e:
                logger.debug("release failed!")
                logger.debug(X_LINE)
                logger.debug(e)
            else:
                logger.debug("lock released successfully")
        logger.debug('\n')

    def __nonzero__(self):
        return self.locked

# ---------------------------------------------------- Comparison Objects -- #
class Comparison(object):
    """comparison objects allow you to retrieve flat lists of files which
    can be compared in two ways:
        * files which are newer in one directory compared to another
        * files which exist in one directory but not another

    the comparison interface is modeled after the built-in dircmp object,
    so the actual data is accessed through properties on this object.

    future development will include filter functions and ignore patterns.
    """
    # ------------------- Constants and Mappings --------------------------- #
    ORIGIN = 0
    DESTINATION = 1

    MODE_MAP = {'origin': ORIGIN,
                'destination': DESTINATION}

    def __init__(self, origin, destination, recursive=True):
        super(Comparison, self).__init__()
        self.origin = origin
        self.destination = destination
        self.origin_depth = len(self.origin.split(os.path.sep))
        self.destination_depth = len(self.destination.split(os.path.sep))
        self.recursive = recursive
        self.ignore = IGNORE_FILES
        self._full_item_lists
        # instance caches
        self._flat_walk_cache = {}

    def _truncate(self, item, base):
        base_depth = getattr(self, '{}_depth'.format(base))
        return os.path.join(*item.split(os.path.sep)[base_depth:])

    def _detruncate(self, item, base):
        return os.path.join(getattr(self, base), item)

    def _flat_walk(self, directory):
        """return a flat list of all returned files and directories
           from os.walk
        """
        # check for cache
        cached_result = self._flat_walk_cache.get(directory)
        if cached_result is not None:
            return cached_result

        flat_walked_files = []
        for path, subdirs, files in os.walk(directory):
            files.extend(subdirs)
            for name in files:
                flat_walked_files.append(os.path.join(path, name))
        self._flat_walk_cache[directory] = flat_walked_files
        return flat_walked_files

    def _full_item_lists(self, filters=[]):
        """Base function to allow comparison of files and folders.
        Filters are function objects which return True or False, given a
        file or directory path.  For instance, filters=[os.isfile] will
        only return paths which point to files.

        I'm using the word 'item' to describe a path which can represent
        either a directory or a file.
        """
        filters = list(filters)
        filters.append(self._ignore)
        in_origin = self._flat_walk(self.origin)
        origin_items = self._filtered_items(in_origin, filters)
        in_destination = self._flat_walk(self.destination)
        destination_items = self._filtered_items(in_destination, filters)
        return origin_items, destination_items

    @staticmethod
    def _filtered_items(item_iter, filters):
        """helper - apply filters to item_iter with short-circuit for
        maximum efficiency.
        """
        return [item for item in item_iter
                if all(filter_(item) for filter_ in filters)]

    def _ignore(self, item):
        """check the item against the ignore list to see if it's included
        """
        return not any(name == item for name in self.ignore)

    def _truncated_file_list(self, filters=[]):
        """get the file list with the paths trimmed:
        /path/to/some/file.txt -> file.txt
        """
        all_files = self._full_item_lists(filters=filters)
        origin_files, destination_files = all_files
        origin_files_truncated = [self._truncate(item, 'origin')
                                  for item in origin_files]
        destination_files_truncated = [self._truncate(item, 'destination')
                                       for item in destination_files]
        return origin_files_truncated, destination_files_truncated

    @cached_property
    def same_files(self):
        """return all files that are the same in both directories"""
        origin_files, dest_files = self._truncated_file_list(filters=[os.path.isfile])
        same_files = [f for f in origin_files if f in dest_files]
        ret_files = []
        for same_file in same_files:
            o_file = self._detruncate(same_file, 'origin')
            d_file = self._detruncate(same_file, 'destination')
            mdiff = (os.path.getmtime(o_file) - os.path.getmtime(d_file))
            if abs(mdiff) < .000001:
                ret_files.append(same_file)

        self._same_files_cache = ret_files
        return ret_files

    def _new_in_x(self, orig_or_dest):
        """Return a list of files that exist in one directory, but not
        in another"""
        # we compare /origin/path/to/file.txt and /dest/path/to/file.txt
        # in their truncated versions, i.e. file.txt and file.txt
        trunc_files = self._truncated_file_list()
        in_x = self.MODE_MAP[orig_or_dest]
        not_in_x = 1 - in_x
        new_files = [f for f in trunc_files[in_x]
                     if f not in trunc_files[not_in_x]]
        # when we return the files, we detruncate them by adding the
        # correct path back to the head of the filename
        ret_files = [self._detruncate(f, orig_or_dest) for f in new_files]
        self._new_in_origin_cache = ret_files

        return ret_files

    @cached_property
    def new_in_origin(self):
        """Return a list of files that exist in the origin, but not
        in the destination."""
        return self._new_in_x('origin')

    @cached_property
    def new_in_destination(self):
        """return a list of files that exist in the destination, but not
        in the origin."""
        return self._new_in_x('destination')

    @cached_property
    def newer_files(self):
        """return a list of files that exist in both origin and destination,
        but only the filepath of the most-recently-modified file"""
        origin_files, dest_files = self._truncated_file_list(filters=[os.path.isfile])
        same_files = (f for f in origin_files if f in dest_files)
        ret_files = []
        for same_file in same_files:
            o_file = self._detruncate(same_file, 'origin')
            d_file = self._detruncate(same_file, 'destination')
            file_mod_time = [(f, os.path.getmtime(f)) for f in (o_file, d_file)]
            if abs(file_mod_time[0][1] - file_mod_time[1][1]) > .000001:
                ret_files.append(max((o_file, d_file), key=os.path.getmtime))
        return ret_files

    @cached_property
    def newer_in_origin(self):
        """return files that exist in both directories, but are different.
        returns only files that are newest in the origin directory"""
        return [f for f in self.newer_files if f.startswith(self.origin)]

    @cached_property
    def newer_in_destination(self):
        """return files that exist in both directories, but are different.
        returns only files that are newest in the destination directory."""
        return [f for f in self.newer_files if f.startswith(self.destination)]

# ---------------------------------------------------------- Sync Objects -- #
class Synchronizer(object):
    """class for convenient synchronization between directories. For the
    cleanest possible results, we're using one-way sync between an origin
    and destination directory.  All files flow origin -> destination.
    If you need two-way sync, this can be achieved by making two
    Synchronizer objects, one for each direction.

    Usage:
    syncer = Synchronizer('/path/to/origin', '/path/to/destination')
    syncer.sync_new_files()
    """

    def __init__(self, origin, destination):
        super(Synchronizer, self).__init__()
        self.origin = origin
        self.destination = destination
        # the Comparison object tells us which files to move, when.
        self._cmp = Comparison(origin, destination)
        # maintain a log of all files and directories copied.
        self.log = {'user': getpass.getuser(),
                    'updated_files': [],
                    'new_files:': [],
                    'new_directories': [],
                    'failed_transfers': []}

    @staticmethod
    def _safe_make_dir(path):
        if not os.path.isdir(path):
            os.makedirs(path)

    def sync_all(self, formatter=None):
        """sync both new and updated files"""
        self._safe_make_dir(self.destination)
        self.sync_new_files(formatter=formatter)
        self.sync_updated_files(formatter=formatter)

    def sync_new_files(self, formatter=None):
        """sync only files that exist in the origin and not the destination"""
        self._safe_make_dir(self.destination)
        new_files = self._cmp.new_in_origin
        logger.info('moving {} new items...', len(new_files))
        for filepath in new_files:
            subdir_path = self._cmp._truncate(filepath, 'origin')
            new_filepath = self._cmp._detruncate(subdir_path, 'destination')
            if os.path.isdir(filepath):
                logger.info('New Directory: {}'.format(filepath))
                if not os.path.isdir(new_filepath):
                    os.makedirs(new_filepath)
            elif os.path.isfile(filepath):
                copy2_verbose(filepath, new_filepath, formatter=formatter,
                              message='New File:')
            else:
                logger.warning("unable to resolve file: {}".format(filepath))
                logger.info(DASH_LINE)

    def sync_updated_files(self, formatter=None):
        """sync only files which exist in both origin and destination, but have
           been updated in the origin
        """
        newer_files = self._cmp.newer_in_origin
        logger.info('overwriting {} items...'.format(len(newer_files)))
        for filepath in newer_files:
            subdir_path = filepath[(len(self.origin) + 1):]
            new_filepath = os.path.join(self.destination, subdir_path)
            if os.path.isfile(filepath):
                self.log['updated_files'].append(new_filepath)
                copy2_verbose(filepath, new_filepath, formatter=formatter,
                              message='Overwrite File:')
            else:
                self.log['failed_transfers'].append(new_filepath)
                logger.warning("unable to resolve file: {}".format(filepath))
                logger.info(DASH_LINE)

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #

# -------------------------------------------------------------- Copy Ops -- #
def copytree_verbose(origin, destination, ignore_func=None):
    """A verbose copytree.  NOTE: symlinks are not followed."""
    logger.info(EQ_LINE)
    if not os.path.exists(destination):
        os.makedirs(destination)
        logger.info("making destination directory: {}".format(destination))
        shutil.copystat(origin, destination)
    dir_ls = os.listdir(origin)
    logger.info("Copying Directory: {}".format(origin))
    logger.info("Destination: {}".format(destination))
    if ignore_func is not None:
        dir_ls = [f for f in dir_ls if not ignore_func(f)]
    for item in dir_ls:
        origin_item = os.path.join(origin, item)
        destination_item = os.path.join(destination, item)
        if os.path.isdir(origin_item):
            copytree_verbose(origin_item, destination_item,
                             ignore_func=ignore_func)
        elif os.path.isfile(origin_item):
            logger.info("    Copying File: {}".format(item))
            shutil.copy2(origin_item, destination_item)
        else:
            logger.warning("    unable to resolve file: {}".format(item))

def copy2_verbose(origin, destination, formatter=None, message='Copying File:'):
    """A verbose copy2 function interface"""
    logger.info("{0} {1}".format(message, origin))
    if formatter:
        destination = formatter(destination)
        while os.path.exists(destination):
            destination = formatter(destination)
    shutil.copy2(origin, destination)


# --------------------------------------------------------------- Helpers -- #
def timestamp():
    """return a nicely-formatted timestamp in the format:
    Month_Day_Year_Hour_Minute_(AM|PM).  There is another version of this
    function in the string_utils package, but I'm keeping this here for
    legacy purposes.
    """
    # maintaining windows compatibility!
    try:
        return time.strftime("%m_%d_%Y_%-I_%M%p", time.localtime())
    except ValueError:
        return time.strftime("%m_%d_%Y_%I_%M%p", time.localtime())

def after_branch(filepath, basepath):
    """split up filepath based on the os.path.sep, and then return the
    section of the path that extends beyond basepath
    """
    base_split = basepath.split(os.path.sep)
    file_split = filepath.split(os.path.sep)
    return os.path.join(*file_split[len(base_split):])
