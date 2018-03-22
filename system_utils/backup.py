# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@organization: Kludgeworks LLC

@description: back up files and directories

@author: Ed Whetstone

@applications: Any

@notes: WIP

TODO: add zip, gzip options to save_to_backup
TODO: add log_changes slog handler
TODO: need a pass for platform independence

"""
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# built-in
import os

# internal
import vfx_utils.system_utils.sync as sync
import vfx_utils.omni.slog as slog
from vfx_utils.omni.string_utils import ujoin

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
VERSION = '1.0'
DEBUG_VERSION = '1.0.5'

logger = slog.Logger()

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #

def default_backup_loc(directory_path):
    """append the current path with _bak
       input:   my/folder/location
       output:  my/folder/location_bak
    """
    return ujoin(directory_path, 'bak')

def make_backup_dir(directory_path):
    """make a backup folder for the given path"""
    # safe directory create, if it exists, just continue
    if not os.path.isdir(directory_path):
        os.makedirs(directory_path)
        logger.info('created backup directory: {0}'.format(directory_path))
    else:
        logger.info('backup directory already exists at {0}... continuing!'
                    ''.format(directory_path))

def backup_directory(origin, destination=None, timestamp=False, only_newer=False):
    """save a directory to a backup location.  If no destination is provided,
       default to /path/to/directory_bak
    """
    if destination is None:
        destination = default_backup_loc(origin)
    if timestamp:
        destination = ujoin(destination, sync.timestamp())
    logger.info('backing up {0} to {1}', origin, destination)
    make_backup_dir(destination)
    if only_newer:
        synchronizer = sync.Synchronizer(origin, destination)
        synchronizer.sync_all()
    else:
        sync.copytree_verbose(origin, destination)

def version_number_up(filepath, latest_version=0):
    file, extension = filepath.split('.')
    version_number = 'v{}'.format(str(latest_version).zfill(4))
    new_path = '{}_{}.{}'.format(file, version_number, extension)
    while os.path.exists(new_path):
        latest_version += 1
        new_path = version_number_up(filepath, latest_version)
    return new_path

def backup_file(origin_file, destination=None,
                conflict_resolver=version_number_up):
    """backup a single file to a location"""
    if destination is None:
        destination = default_backup_loc(os.path.dirname(origin_file))
    final_file_path = os.path.join(destination, os.path.basename(origin_file))
    final_file_path = conflict_resolver(final_file_path)
    logger.info('backing up {} to {}', origin_file, final_file_path)
    sync.copy2_verbose(origin_file, final_file_path)
