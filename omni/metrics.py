# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@organization: Kludgeworks LLC 2018

@description: A collection of modules for logging and interpreting tool
              metrics

@author: Ed Whetstone

@applications: any

@notes:  In most cases, you'll want to decorate existing functions,
         using the following decorators:

         * @collector_instance.usage_logging
             * log only usage
         * @collector_instance.feature_logging('feature_name')
             * log a specific feature

         Or, you can explicitly call log_usage() or log_feature()

         see the example code below for more information.
"""

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# built-in
from functools import wraps
import time

# internal
import vfx_utils.omni.slog as slog
from vfx_utils.omni.string_utils import datestamp, timestamp
from vfx_utils.system_utils.directories import safe_make_dir

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #

# --------------------------------------------------- Version Information -- #
VERSION = '2.0'
DEBUG_VERSION = '2.0.0'

# --------------------------------------------------------------- Logging -- #
# -- Metric Logging -------------------------------------------------------- #
metric_logger = slog.Logger('__metrics__')
metric_logger.standalone = True
log_handler = slog.FileLogHandler()
log_handler.always_evaluate = True
metric_logger.add_handler(log_handler)

# -- Regular Logging ------------------------------------------------------- #
logger = slog.Logger()

# -------------------------------------------------------------------------- #
# --------------------------------------------- USAGE AND FEATURE LOGGING -- #

class MetricCollector(object):
    """provides decorators and convenience functions for logging metrics on
    applications and features"""
    def __init__(self, app_name):
        """resource is a ResourceLocator instance with an 'app_log' branch.
        subclasses will need to provide self.app_log_path either as a property
        or a static attribute in order to provide a location to save logs"""
        self.app_name = app_name
        self.app_log_path = None
        self.join_threads = False
        super(MetricCollector, self).__init__()

    def usage_logging(self, func):
        """
        DECORATOR:
        Log the usage of this function. In the app_usage log, this will be
        represented by a row formatted like this:
        usage: 03.06.05 PM
        """
        @wraps(func)
        def inner_func(*args, **kwargs):
            self.log_usage()
            return func(*args, **kwargs)
        return inner_func

    def feature_logging(self, feature):
        """
        DECORATOR:
        Log a feature into the application log, in the format:
        <feature name>: 03.06.05 PM
        Due to the way threading works, if the __main__ thread exits before
        the log queue is finished, not all features will be logged.  If a feature
        is important to log, be sure to set the keyword "join" to True.
        """
        def outer_wrap(func):
            @wraps(func)
            def inner_func(*args, **kwargs):
                self.log_feature(feature)
                return func(*args, **kwargs)
            return inner_func
        return outer_wrap

    def log_usage(self):
        """
        Log an application usage, in the format:
        usage: 03.06.05 PM

        Threading:
        usage logging always joins the main thread, to prevent __main__ from
        exiting before the usage is logged.
        """
        self.log_feature('usage')

    def log_feature(self, message):
        """
        Log a feature to the application log:
        some_feature: 04.02.05 PM

        Threading:
        For standalone and command-line tools, you might want to force feature logs
        to join in order to prevent the main thread from exiting early.  For apps
        running from inside of Maya or NUKE, you might disable thread joining for
        responsiveness in those applications.
        """
        safe_make_dir(self.app_log_path)
        log_time = "{} {}".format(datestamp('.'), timestamp('.'))
        log_data = '{0}.{1}: {2}\n'.format(self.app_name, message, log_time)
        metric_logger.write(log_data, filepath=self.app_log_path,
                            join_main=self.join_threads)


# -------------------------------------------------------------------------- #
# ---------------------------------------------------------- EXAMPLE CODE -- #
def example():
    metric_collector = MetricCollector('example_app')
    metric_collector.app_log_path = 'path/to/your/example/logfile.txt'

    @metric_collector.usage_logging
    def example_metrics():
        """let's log a function!"""
        # both of the example features of this code are logged.
        # let's run example_feature 10 times, and see what happens.
        for i in range(10):
            example_feature()
        # and let's run the other feature.
        # example_feature_2() will throw an error, which will be logged as well.
        example_feature_2()

    @metric_collector.feature_logging('some_feature')
    def example_feature():
        """this function represents some feature of the software"""
        print 'a feature of this application has been run!  Check the log!'

    def example_feature_2():
        # let's manually log a feature, insteady of letting the decorator
        # handle it.
        metric_collector.log_feature('some_other_feature')
        print "another feature has been logged!"

    example_metrics()
