# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@organization: Kludgeworks LLC

@description: SLOG, the simple logger!

@author: Ed Whetstone

@applications: all

Simple Logger provides a simple, extensible interface for logging,
similar to the Python standard library 'logging' module.

NOTE: Slog is built with the CPython implementation in mind, and may not
work for other interpreters.  This is due to slog's unique introspective
frame-lookup mechanism, which allows for automatic inheritance of loggers.
"""

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# built-in
import threading
import sys
from itertools import chain
from Queue import Queue
from contextlib import contextmanager
from collections import deque

# internal
from LightingTools.general_utils.inspections import get_mod_trace
from LightingTools.system_utils.directories import safe_make_dir

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #

# ---------------------------------------------------------- Version Data -- #
VERSION = '3.2'
DEBUG_VERSION = '3.2.4'

# -------------------------------------------------- Handlers and Loggers -- #
# this is just a placeholder -- the actual root_logger will be
# set at the bottom of this module
root_logger = None

# ------------------------------------------------------------- Threading -- #
# ------------------- Locks ------------------------------------------------ #
handler_lock = threading.Lock()
handler_ctx_lock = threading.Lock()
root_lock = threading.Lock()

# -------------------------------------------------------- Logging Levels -- #
# don't handle any slog commands
NO_ACTION = -1
# only handle exceptions
EXCEPTION = 0
# errors and exceptions only
ERROR = 1
# exceptions, errors and warnings only
WARNING = 2
# exceptions, errors, warnings, and info
INFO = 3
# exceptions, errors, warnings, info, and debugs
DEBUG = 4
# always handle everything
ALWAYS_HANDLE = 5

# get the name of the level from the integer
LEVEL_LOOKUP = {-1: 'LOG',
                0: 'EXCEPTION',
                1: 'ERROR',
                2: 'WARNING',
                3: 'INFO',
                4: 'DEBUG',
                99: 'NO_ACTION',
                }

# by default, only handle info, warnings, and errors
DEFAULT_VERBOSITY = 3

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- LOGGERS -- #

# ----------------------------------------------------------------- Cache -- #
_logger_cache = {}

# ----------------------------------------------------------- Metaclasses -- #
class LogLookup_Meta(type):
    """Implements the flyweight pattern for Loggers, keeping an instance
    dictionary in the Logger class for lookups.  This inherently makes
    Loggers into name-bound singletons."""
    def __new__(mcs, name, superclasses, kwargs):
        return super(LogLookup_Meta, mcs).__new__(mcs, name,
                                                  superclasses, kwargs)

    def __init__(cls, name, bases, dct):
        super(LogLookup_Meta, cls).__init__(name, bases, dct)

    def __call__(cls, *args, **kwargs):
        if not args:
            try:
                outer_frame = sys._getframe(1)
                mod_name = outer_frame.f_globals['__name__']
                while mod_name == __name__:
                    outer_frame = outer_frame.f_back
                    try:
                        mod_name = outer_frame.f_globals['__name__']
                    except KeyError:
                        mod_name = '__main__'
            except KeyError:
                raise
            else:
                args = (mod_name,)
        return _logger_cache.setdefault(args[0], type.__call__(cls, *args, **kwargs))

# --------------------------------------------------------------- Classes -- #
class Logger(object):
    """Loggers enable a message to be passed to an arbitrary number of
    Handlers, both in the current module and any enclosing modules in the
    frame stack.

       LOGGING WITH A LOGGER:
    In most cases, just establishing a logger at the top of your module
    will be all you need to do to get started.

    # ------------------------ Example Code -------------------------- #
    logger = Logger()
    logger.info('an info message')
    logger.debug('a debug message')
    # ---------------------------------------------------------------- #


       CONFIGURING A LOGGER:
    The attributes established at the bottom of this function can be set
    by the caller after instance creation.  So, for instance:

    # ------------------------ Example Code -------------------------- #
    logger = Logger()
    logger.level = 4
    logger.formatter = my_formatter
    # ---------------------------------------------------------------- #

    Alternatively, you can use the config() method to set the attributes:

    # ------------------------ Example Code -------------------------- #
    logger = Logger()
    logger.config(level=4, formatter=my_formatter)
    # ---------------------------------------------------------------- #

    Ideally, Logger configuration should be set-and-forget, because a
    single logger instance might be called from multiple threads.
    Best-practice is to only create loggers at the module level or when
    you can control instance creation on-the-fly.

       NESTED LOGGING:
    Loggers which do not provide an explicit lookup are automatically
    inherited by enclosing scopes, so, for example:

    # ------------------------ module 'A' code ----------------------- #
    logger = Logger()
    logger.add_handler(handler_a)

    def a_func():
        logger.info('message a')
    # ---------------------------------------------------------------- #

    # ------------------------ module 'B' code ----------------------- #
    import a
    logger = Logger()
    logger.add_handler(handler_b)

    a.a_func()
    # ---------------------------------------------------------------- #

    in this case, when we call a.a_func, both handler_b and handler_a
    will be called with 'message a' at info level.
    """
    __metaclass__ = LogLookup_Meta

    def __init__(self, name):
        """In order to keep the interface as simple and explicit as
        possible, the only argument passed in to Logger constructors is the
        name of the logger that we want to create or access.  If you don't
        provide a name, then the current module's name will be used instead
        (The metaclass handles the naming, you don't have to provide ANY
        argument to a Logger() call).  This is considered good practice.

        """
        # ------------------- DO NOT MODIFY FROM INSTANCE ------------------ #
        # please use add_handler and remove_handler methods to set the
        # handlers for the logger instance.  'name' and 'lookup'
        # attributes should never be changed.
        self.name = name
        self.lookup = name
        self._handlers = dict()
        self.handlers = []
        self._bypass_handlers = dict()
        self.bypass_handlers = []

        # ------------------- Instance Modifications are Okay -------------- #
        # These are the attributes which the caller can edit after
        # instance creation.
        # standalone Loggers do not call the loggers in their enclosing scopes
        self.standalone = False
        # the level determines which log messages trigger handlers
        self.level = DEFAULT_VERBOSITY
        # if the submodule has their own logger, we can choose to override
        # that level with this one.  Subsequently, only the outermost scope
        # with overrides_submodule_level == True will enforce their level
        self.overrides_submodule_level = False
        # we can also explicitly use the level attribute of another Logger
        self.borrow_level_from = None
        # by default, all handlers above a given level are triggered. We can
        # also make this logger only execute on one specific level
        self.level_exclusive = False
        # formatters determine how messages are processed before being passed
        # to handlers
        self.formatter = None

    # ----------------------------------------------------- Configuration -- #
    def config(self, level=DEFAULT_VERBOSITY, overrides_submodule_level=False,
               standalone=False, level_exclusive=False, formatter=None):
        """set the instance attributes for the Logger instance after
        creation"""
        if standalone:
            self.standalone = standalone
        if level:
            self.level = level
        if overrides_submodule_level:
            self.overrides_submodule_level = overrides_submodule_level
        if level_exclusive:
            self.level_exclusive = level_exclusive
        if formatter:
            self.formatter = formatter

    # ----------------------------------------------------- Handlers -- #
    def add_handler(self, handler, _macro=False):
        """add a handler to the Logger instance"""
        try:
            handler.enter_handler()
        except AttributeError:
            pass
        try:
            always_eval = handler.always_evaluate
        except AttributeError:
            always_eval = False
        if not always_eval:
            self._handlers[id(handler)] = handler
        else:
            self._bypass_handlers[id(handler)] = handler
        if not _macro:
            self.handlers = self._handlers.values()
            self.bypass_handlers = self._bypass_handlers.values()

    def remove_handler(self, handler, _macro=False):
        """remove a handler from the logger instance"""
        try:
            handler.exit_handler()
        except AttributeError:
            pass
        try:
            always_eval = handler.always_evaluate
        except AttributeError:
            always_eval = False
        if not always_eval:
            self._handlers.pop(id(handler))
        else:
            self._bypass_handlers.pop(id(handler))
        if not _macro:
            self.handlers = self._handlers.values()
            self.bypass_handlers = self._bypass_handlers.values()

    def add_handlers(self, handlers):
        """MACRO: add an iterable of handlers to the handler list"""
        for handler in handlers:
            self.add_handler(handler, _macro=True)
        self.handlers = self._handlers.values()
        self.bypass_handlers = self._bypass_handlers.values()

    def remove_handlers(self, handlers):
        """MACRO: remove an iterable of handlers from the handler list"""
        for handler in handlers:
            self.remove_handler(handler, _macro=True)
        self.handlers = self._handlers.values()
        self.bypass_handlers = self._bypass_handlers.values()

    @contextmanager
    def use_handlers(self, handlers):
        """Temorarily replace the internal set of handlers for this
        logger with a different set, then return to the original handlers
        """
        # we are accessing shared data, so we lock this down until the original
        # handler list is restored.
        with handler_ctx_lock:
            original_handlers = self.handlers
            for handler in handlers:
                try:
                    handler.enter_handler()
                except AttributeError:
                    pass
            self.handlers = handlers
            yield
            for handler in handlers:
                try:
                    handler.exit_handler()
                except AttributeError:
                    pass
            self.handlers = original_handlers

    # ---------------------------------------------------- Broadcast -- #
    def broadcast(self, message, *args, **kwargs):
        """Pass the message on to the handlers defined in this Logger,
        and all of the loggers from modules which enclose this function.
        EX: if A and B both have loggers, and A imports B, when calling
        B.logger.log(), then both B.logger and A.logger handlers will
        be called.

        broadcast is handled as one really big function in order to
        reduce function-call overhead. We're trying to get every bit of
        performance out of this thing as possible.
        """
        # this is the level of the message, i.e. Debug, Info, Error, etc.
        level = kwargs.pop('level')
        # ------------------- Handle Standalone Loggers --------------- #
        if self.standalone:
            if args:
                message = message.format(*args)
            for handler in chain.from_iterable((self.handlers,
                                                self.bypass_handlers)):
                handler(message, level=level, **kwargs)
            return

        # ------------------- Get Enclosing Module Loggers ------------ #
        # We need to get the frame of the calling function. The first
        # three frames should be:
        # * frame 0: Logger.broadcast
        # * frame 1: Logger.info, debug, etc.
        # * frame 2: Calling function
        frame = sys._getframe(2)
        supermodules = get_mod_trace(frame)
        is_main = (self.lookup == '__main__')
        if not is_main:
            supermodules.append('__main__')

        # because multiple frames will live in the same modules, we need
        # to condense the list down to unique items.
        visited = set()
        visited_add = visited.add
        supermodules = [sm for sm in supermodules if sm not in visited
                        and not visited_add(sm)]
        # get the loggers associated with the modules, if any
        superloggers_all = [_logger_cache[sm] for sm in supermodules
                            if sm in _logger_cache]
        # we only want to handle non-standalone loggers
        superloggers = [sl for sl in superloggers_all if not sl.standalone]

        # ------------------- Broadcast "Always Evaluate" Handlers ---- #
        # "always evaluate" means ALWAYS evaluate.  These handlers will
        # be called no matter what -- although the handlers themselves
        # can choose to ignore a particular message or level.
        bypass_handlers = chain.from_iterable([logger.bypass_handlers
                                               for logger in superloggers])
        bypass_handlers = list(bypass_handlers)
        if bypass_handlers:
            # remove duplicate handlers
            visited = set()
            visited_add = visited.add
            bypass_handlers = [bp for bp in bypass_handlers
                               if bp not in visited and not visited_add(sm)]
            if args:
                message = message.format(*args)
            if self.formatter:
                message = self.formatter(message, level, **kwargs)
            for handler in bypass_handlers:
                handler(message, level=level, **kwargs)

        # ------------------- Get Overriding Level (If Any) ----------- #
        if not self.borrow_level_from:
            level_overriders = [sl for sl in superloggers
                                if sl.overrides_submodule_level]
            if level_overriders:
                overrider = list(level_overriders)[-1]
                logger_level = overrider.level
                level_exclusive = overrider.level_exclusive
            else:
                logger_level = self.level
                level_exclusive = self.level_exclusive
        else:
            try:
                borrowlogger = _logger_cache[self.borrow_level_from]
            except:
                logger_level = self.level
                level_exclusive = self.level_exclusive
            else:
                logger_level = borrowlogger.level
                level_exclusive = borrowlogger.level_exclusive

        # ------------------- Logger Level Filter --------------------- #
        if level_exclusive and level != logger_level:
            return
        elif not level_exclusive and level > logger_level:
            return

        # ------------------- Build Handler Lists --------------------- #
        # get handlers from each module's loggers
        if superloggers:
            superhandlers = chain.from_iterable([superlogger.handlers
                                                 for superlogger in superloggers])
        else:
            superhandlers = self.handlers

        visited = set()
        visited_add = visited.add
        # remove duplicate handlers
        superhandlers = [sh for sh in superhandlers if sh not in visited
                         and not visited_add(sm)]

        # ------------------- Format Message if Not Already ----------- #
        if args and not bypass_handlers:
            message = message.format(*args)
        if not bypass_handlers and self.formatter:
            message = self.formatter(message, level, **kwargs)

        # ------------------- Broadcast ------------------------------- #
        for handler in superhandlers:
            handler(message, level=level, **kwargs)

    # ---------------------------------------------- Handle Messages -- #
    def exception(self, message, *args, **kwargs):
        """log exceptions which are expected to kill the application."""
        kwargs['exc_info'] = sys.exc_info()
        with handler_lock:
            self.broadcast(message, level=0, *args, **kwargs)

    def error(self, message, *args, **kwargs):
        """Indicates an error has definitely occurred, but not
        necessarily that the program will stop running.
        """
        with handler_lock:
            self.broadcast(message, level=1, *args, **kwargs)

    def warning(self, message, *args, **kwargs):
        """log warnings that are useful to know, but won't completely
        stop an application from running
        """
        with handler_lock:
            self.broadcast(message, level=2, *args, **kwargs)

    def info(self, message, *args, **kwargs):
        """log information useful to the user."""
        with handler_lock:
            self.broadcast(message, level=3, *args, **kwargs)

    def debug(self, message, *args, **kwargs):
        """log information useful to programmers for debugging"""
        with handler_lock:
            self.broadcast(message, level=4, *args, **kwargs)

    def write(self, message, *args, **kwargs):
        """straight output"""
        with handler_lock:
            self.broadcast(message, level=-1, *args, **kwargs)

    def __repr__(self):
        return "<slog.Logger for '{0}'>".format(self.lookup)

# -------------------------------------------------------------------------- #
# -------------------------------------------------------------- HANDLERS -- #
class Handler(object):
    """Callable class which allows object-orientation for logging
    handlers. Any callable which provides the same arg signature would
    work just as well, but this template allows for several features,
    such as different methods for each handler type, as well as enter and
    exit operations"""
    def __init__(self, level=None, level_exclusive=False,
                 always_evaluate=False, formatter=None, **kwargs):
        super(Handler, self).__init__(**kwargs)
        self.formatter = formatter
        self.always_evaluate = always_evaluate
        self.level_exclusive = level_exclusive
        self.level = level if level else 100
        self.verb_map = {99: self.no_action,
                         4: self.handle_debug,
                         3: self.handle_info,
                         2: self.handle_warning,
                         1: self.handle_error,
                         0: self.handle_exception,
                         -1: self.handle}

    def __call__(self, message, level=DEFAULT_VERBOSITY, **kwargs):
        """Makes the Handler instance callable.  If the dispatch method
        (info, debug, etc.) is not explicitly overridden in the subclass
        or instance, then handle() is called instead. Optional kwargs can
        be passed in for extra data, and will be ignored by any Handler
        that doesn't require it.
        """
        if not self.always_evaluate:
            if not self.level_exclusive and level > self.level:
                return
            elif self.level_exclusive and level != self.level:
                return
        level_method = self.verb_map[level]
        if self.formatter:
            message = self.formatter(message, level, **kwargs)
        level_method(message, level, **kwargs)

    def handle(self, message, level, *args, **kwargs):
        """All handle methods default to this handler when called, unless
           explicitly overridden in a subclass
        """
        return

    def handle_debug(self, message, level, *args, **kwargs):
        """Handle all debug messages.  Override in subclass to change"""
        self.handle(message, level, *args, **kwargs)

    def handle_info(self, message, level, *args, **kwargs):
        """Handle all info messages.  Override in subclass to change"""
        self.handle(message, level, *args, **kwargs)

    def handle_warning(self, message, level, *args, **kwargs):
        """Handle all warning messages.  Override in subclass to change"""
        self.handle(message, level, *args, **kwargs)

    def handle_error(self, message, level, *args, **kwargs):
        """Handle all error messages.  Override in subclass to change"""
        self.handle(message, level, *args, **kwargs)

    def handle_exception(self, message, level, *args, **kwargs):
        """Handle all error messages.  Override in subclass to change"""
        self.handle(message, level, *args, **kwargs)

    def no_action(self):
        return

    def enter_handler(self):
        """NOT IMPLEMENTED
        This method will be called upon being added to a logger, either
        through the add_handler methods, or passed into a
        Logger.use_handlers context manager.
        """
        return

    def exit_handler(self):
        """NOT IMPLEMENTED
           This method will be called when the handler is dumped by a
           Logger, either through manually switching handlers or by
           exiting a Logger.use_handlers context manager.
        """
        return

    def __repr__(self):
        return "<slog.Handler id {0}>".format(id(self))

# ------------------------------------------------------- Default Handler -- #
class BaseLogHandler(Handler):
    """HANDLER:
    use sys.stdout.write to output to the console
    """
    base_verbosity = 5

    def __init__(self):
        super(BaseLogHandler, self).__init__(level=self.base_verbosity)

    def handle(self, message, level, **kwargs):
        sys.stdout.write('{}'.format(message))

# ----------------------------------------------------- Handler Templates -- #
class DeferredHandler(Handler):
    """HANDLER:
    Cache all logger messages until a particular condition is met.
    Subclasses should include a triggering mechanism.  This handler is
    always evaluated.
    """
    def __init__(self, max_cache_size=None, cache_levels=None, **kwargs):
        """Unlike other handlers, the DeferredHandler requires an
        explicit set of levels to handle, and will handle those levels
        when triggered regardless of the current or enclosing logger
        levels."""
        super(DeferredHandler, self).__init__(always_evaluate=True, **kwargs)
        self.cache_levels = cache_levels or [0, 1, 2, 3, 4, 5]
        self.cache = deque(maxlen=max_cache_size)

    def dump(self):
        """push out all cached messages"""
        for message, level in self.cache:
            level_method = self.verb_map[level]
            level_method(message, level)
        self.cache = []

    def __call__(self, message, level, **kwargs):
        if level in self.cache_levels:
            if self.formatter:
                message = self.formatter(message, level, **kwargs)
            self.cache.append((message, level))

class JustInCaseHandler(DeferredHandler):
    """HANDLER:
    Cache logger messages until the trigger level is exceeded. This handler
    is always evaluated.
    """
    def __init__(self, trigger_level=0, **kwargs):
        """The Just-In-Case handler will trigger whenever a log message
        at or above the trigger level gets passed to the logger"""
        super(JustInCaseHandler, self).__init__(**kwargs)
        self.trigger_level = trigger_level

    def __call__(self, message, level, **kwargs):
        super(JustInCaseHandler, self).__call__(message, level, **kwargs)
        if level <= self.trigger_level:
            self.dump()

# -------------------------------------------------------------------------- #
# ----------------------------------------------------- File Log Handling -- #
def _file_logging_op(q):
    """Queue processing for threaded file logging"""
    while True:
        try:
            # grab the latest log entry
            logpath, log_data = q.get()
        except TypeError:
            # if the queue is passed None, shut down the thread
            return
        _log_it(logpath, log_data)
        q.task_done()

def _log_it(logpath, log_data):
    """write a log to the specified logpath"""
    with open(logpath, 'a+') as log:
        log.writelines(log_data)

class FileLogHandler(Handler):
    """Write log to a file location, using a new thread to handle output.
    The new thread will rejoin the main thread upon exiting, making this
    handler mostly useful for UI-bound applications where you want to
    maintain responsiveness but still write log files.

    Note on threading:
    Every FileLogHandler instance will spin up a new thread upon being
    added to a logger, but will share a job queue with any other
    FileLogHandler which points to the same file.
    """
    def __init__(self, filepath=None, header=None, footer=None, clear_existing=False,
                 join_main=True, *args, **kwargs):
        # super call allows setting of level and handler-mapping
        super(FileLogHandler, self).__init__(*args, **kwargs)
        self.filepath = filepath
        self.logfile = None
        self.header = header
        self.footer = footer
        self.join_main = join_main
        self.clear_existing = clear_existing
        self.formatter = None
        self.op_queue = Queue()

    def handle(self, message, *args, **kwargs):
        """write the message onto the next line of the logfile"""
        path = kwargs.pop('filepath', self.filepath)
        log_queue = get_file_queue(path)
        get_file_thread(path, log_queue)
        log_queue.put((path, message))
        # ------------------- Join Main Thread ----------------------------- #
        if self.join_main:
            log_queue.join()

    def enter_handler(self):
        """write the header to the file if one exists"""
        if not self.filepath:
            return

        # ------------------- Create Directory ----------------------------- #
        safe_make_dir(self.filepath)

        # ------------------- Clear the File, if Requested ----------------- #
        if self.clear_existing:
            open(self.filepath, 'w').close()

        # ------------------- Add Header ----------------------------------- #
        if self.header:
            self.handle(self.header)

    def exit_handler(self):
        """rejoin the main thread, write the footer, and close"""
        if self.footer:
            self.handle(self.footer)
        self.handle(None)
        self.log_queue.join()

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------ FORMATTERS -- #
# formatters are simple functions which take a message, level, and optional
# keyword arguments.  They transform the message either on the logger level or
# on the handler level.

def base_newline_formatter(msg, lvl, **kwargs):
    """return the message in the format:
    LEVELNAME: message\n
    (this formatter DOES append a newline)
    """
    formatted_msg = base_formatter(msg, lvl, **kwargs)
    return '{0}\n'.format(formatted_msg)

def base_formatter(msg, lvl, **kwargs):
    """return the message in the format:
    LEVELNAME: message
    (this formatter does NOT append a newline)
    """
    custom_label = kwargs.get('label', None)
    if custom_label:
        label = custom_label
    else:
        label = LEVEL_LOOKUP[lvl]
    try:
        if "\n" in msg:
            spacer = '\n  {0}'.format(' ' * len(label))
            msg = spacer.join(msg.split('\n'))
    except TypeError:
        pass
    msg = "{0}: {1}".format(label, msg)
    return msg

def context_formatter(ctx):
    def formatted_with_context(msg, _):
        return '{0} > {1}'.format(ctx, msg)
    return formatted_with_context

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #


# ------------------------------------------------------------- Factories -- #
cached_queues = dict()
def get_file_queue(filename):
    return cached_queues.setdefault(filename, Queue(maxsize=0))


cached_threads = dict()

def get_file_thread(filename, queue):
    if filename in cached_threads:
        return cached_threads[filename]
    # ------------------- Spin up Thread ----------------------------------- #
    handler_thread = threading.Thread(target=_file_logging_op,
                                      args=(queue,))
    handler_thread.setDaemon(True)
    handler_thread.start()
    return handler_thread

# ------------------------------------------------------ Context Managers -- #
@contextmanager
def alternate_root(logger):
    with root_lock:
        original_root = root_logger
        _logger_cache['__main__'] = logger
        yield
        _logger_cache['__main__'] = original_root

# --------------------------------------------------------- Log Functions -- #
def write(message, *args, **kwargs):
    """log any entry"""
    root_logger.write(message, *args, **kwargs)

def exception(message, *args, **kwargs):
    """log an exception which is expected to kill the program"""
    root_logger.exception(message, *args, **kwargs)

def error(message, *args, **kwargs):
    """top-level error logging.  Indicates a fatal error has occurred, but
    a crash is not imminent"""
    root_logger.error(message, *args, **kwargs)

def warning(message, *args, **kwargs):
    """log warnings that are useful to know, but won't completely stop
    an application from running"""
    root_logger.warning(message, *args, **kwargs)

def info(message, level=3, *args, **kwargs):
    """log information useful to the user."""
    root_logger.info(message, *args, **kwargs)

def debug(message, level=4, *args, **kwargs):
    """log information useful to programmers for debugging"""
    root_logger.debug(message, *args, **kwargs)


# -------------------------------------------------------------------------- #
# ------------------------------------------------- Global Initialization -- #
# the root logger will always be called last in the stack.
root_logger = Logger('__main__')
base_log_handler = BaseLogHandler()
base_log_handler.formatter = base_newline_formatter
root_logger.add_handler(base_log_handler)


# -------------------------------------------------------------------------- #
# ---------------------------------------------------------- EXAMPLE CODE -- #
def example():
    """basic usage of the slog module"""
    import lit_artist_tools.omni.slog as slog
    logger = slog.Logger()
    logger.error('this is an error message')
    logger.info('this is an info message')
    logger.info('you can also {0} your message', 'format')
    logger.debug('by default this won\'t show up!')

    logger.level = slog.DEBUG

    logger.debug('a previous message was hidden, but this one is shown!')

    logger.level = slog.ERROR

    logger.info('now only error messages will be shown')
    logger.warning('not even warnings show up!')

    # let's reset the logger's level to default.
    logger.level = slog.DEFAULT_VERBOSITY
