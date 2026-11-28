import typing
import tkinter as tk
import tkinter.ttk as ttk
import threading
import sys
import subprocess
import time
import os
import io
from tkinter import messagebox
import traceback
import functools
import types
import ctypes
import ctypes.wintypes
import uuid
import re
import tomllib
import inspect
import STTlogger
import builtins
import argparse

ARGS = argparse.Namespace()

T = typing.TypeVar("T")
P = typing.ParamSpec("P")

thread_context = threading.local()

DATA_PATH = "data/"
CONFIG_PATH = "config/"
TEMP_PATH = "temp/"

def open_logger():
    filenames = [f"{DATA_PATH}current.log", f"{DATA_PATH}logs/{time.time()}.log"]
    persist = False
    try:
        persistence_file = DATA_PATH + "persist.txt"
        print(f"Trying to open persistence file {persistence_file}")
        with open(persistence_file, "r") as f:
            filenames.clear()
            for line in f:
                filenames.append(line.strip())
            persist = True
        os.remove(persistence_file)
        print(f"Removing persistence file")
    except Exception as e:
        print(f"Couldn't open: ({type(e).__name__}) {e}")
    print(f"Opening logger with files: {filenames}, persist: {persist}")
    return STTlogger.SimpleSTTLogger(filenames, persist=persist)

logger = open_logger()

VERBOSE = False

def print(message: str, *, source: str | None = None, fast: bool = False):
    if source:
        builtins.print(f"({source}) {message}")
    else:
        builtins.print(message)
    if fast:
        logger.logFast(message, source=source)
    else:
        logger.log(message, source=source)

def verbose_print(message: str, *, source: str | None = None, fast: bool = False):
    if VERBOSE:
        print(message, source=source, fast=fast)

CONFIG_FILENAME = CONFIG_PATH + "userconfig.toml"
CONFIG_BACKUP_FILENAME = CONFIG_PATH + "exampleconfig.toml"
FILTERCONFIG_FILENAME = CONFIG_PATH + "filters.toml"
FILTERCONFIG_BACKUP_FILENAME = CONFIG_PATH + "examplefilters.toml"

TEMP_CONFIG_FILENAME = TEMP_PATH + "config.toml"
TEMP_FILTERCONFIG_FILENAME = TEMP_PATH + "filters.toml"

def diagnose_entry(func=None, *, args=False, simple=False, only_verbose=False):
    _show_args = args
    _print_func = print
    if only_verbose:
        _print_func = verbose_print
    def decorator(func: typing.Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            caller = inspect.stack()[1]
            if _show_args:
                if simple:
                    _print_func(f"Called {func.__name__} from {caller.function} with args {args} kwargs {kwargs}")
                else:
                    _print_func(f"FUNCTION ENTRY {func.__name__} ({func}) entered\n  ARGS:")
                    for arg in args:
                        _print_func(f"  :({arg})")
                    for k, v in kwargs.items():
                        _print_func(f"  ({k}):({v})")
            else:
                if simple:
                    _print_func(f"Called {func.__name__} from {caller.function}")
                else:
                    _print_func(f"FUNCTION ENTRY {func.__name__} ({func}) entered at {caller.filename}:{caller.lineno} in {caller.function}")
            had_error = False
            try:
                return func(*args, **kwargs)
            except Exception as e:
                had_error = True
                _print_func(f" FUNCTION ENTRY {func.__name__} ({func}) exception {type(e).__name__} {e}")
                raise
            finally:
                if simple:
                    _print_func(f" {func.__name__} exited")
                else:
                    _print_func(f" FUNCTION EXIT {func.__name__} ({func}){' WITH EXCEPTION' if had_error else ''}")
        return wrapper
    if func is not None:
        return decorator(func)
    else:
        return decorator

def get_model_path():
    print("get_model_path called. this function is really slow and sucks.")
    with open(CONFIG_FILENAME, "rb") as cfgf:
        cfg = tomllib.load(cfgf)
        meta = cfg.get("meta")
        backupstr = f"Look at \"{CONFIG_BACKUP_FILENAME}\" to see what the config file should look like."
        if meta is None:
            raise RuntimeError(f"Config file \"{CONFIG_FILENAME}\" is missing the section \"meta\". {backupstr}")
        if type(meta) is not dict:
            raise RuntimeError(f"Section \"meta\" is not a dictionary. {backupstr}")
        model_path = meta.get("path_to_model")
        if model_path is None:
            raise RuntimeError(f"Config file \"{CONFIG_FILENAME}\" is missing \"path_to_model\" in the \"meta\" section. {backupstr}")
        if type(model_path) is not str:
            raise RuntimeError(f"\"path_to_model\" is not a string. {backupstr}")
        return model_path

DEFAULT_WINDOW_WIDTH = 300
DEFAULT_WINDOW_HEIGHT = 100

MBOX_POS: None | tuple[int, int] = None
LAST_MBOX_TIME = 0
MBOX_COUNT = 0
CAN_SHOW_MBOX = True
max_mbox_count = 20
max_mbox_reset_time = 1

_warningbox_xvel = 0
_warningbox_yvel = 0

class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.DWORD),
        ("rcMonitor", ctypes.wintypes.RECT),
        ("rcWork", ctypes.wintypes.RECT),
        ("dwFlags", ctypes.wintypes.DWORD),
    ]

def showwarning_at(title: str, message: str, x: int | None, y: int | None, ack: "ExceptionAcknowledgedHook | None" = None) -> tuple[int, int]:
    global _warningbox_xvel
    global _warningbox_yvel
    unique_title = f"{title} : {uuid.uuid4()}"
    def show_box():
        messagebox.showwarning(unique_title, message)
        if ack:
            spawn_thread(ack, None)
    main_thread_async(show_box)
    hwnd = None
    for _ in range(500):
        hwnd = ctypes.windll.user32.FindWindowW("#32770", unique_title)
        if hwnd:
            break
        time.sleep(0.01)
    if hwnd is None:
        print(f"Couldn't find warning box {unique_title}!")
        return (0, 0)
    
    rect = ctypes.wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))

    if x is None or y is None:
        _warningbox_xvel = 10
        _warningbox_yvel = 10
        return (rect.left, rect.top)

    width = rect.right - rect.left
    height = rect.bottom - rect.top

    ctypes.windll.user32.MoveWindow(
        hwnd,
        x,
        y,
        width,
        height,
        True,
    )
    
    monitor = ctypes.windll.user32.MonitorFromWindow(
        hwnd,
        2  # MONITOR_DEFAULTTONEAREST
    )
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(info)
    ctypes.windll.user32.GetMonitorInfoW(
        monitor,
        ctypes.byref(info)
    )
    left = typing.cast(int, info.rcMonitor.left)
    top = typing.cast(int, info.rcMonitor.top)
    right = typing.cast(int, info.rcMonitor.right)
    bottom = typing.cast(int, info.rcMonitor.bottom)

    x += _warningbox_xvel
    y += _warningbox_yvel
    if x + width >= right:
        x = right - width
        _warningbox_xvel = -abs(_warningbox_xvel)
    elif x <= left:
        x = left
        _warningbox_xvel = abs(_warningbox_xvel)
    if y + height >= bottom:
        y = bottom - height
        _warningbox_yvel = -abs(_warningbox_yvel)
    elif y <= top:
        y = top
        _warningbox_yvel = abs(_warningbox_yvel)
    return (x, y)

def _mbox_time_elapsed():
    return time.time() - LAST_MBOX_TIME

def _set_mbox_time():
    global LAST_MBOX_TIME
    LAST_MBOX_TIME = time.time()

@diagnose_entry
def record_exception(e: Exception, context: str | None = None) -> str:
    print(f"shared.record_exception called with ({type(e).__name__}) {e}", source="record_exception")
    if context is None:
        context = f"No context given for exception ({type(e).__name__}): {e}\n" + exception_to_filtered_traceback(e, context)
    base_stacktrace_file = DATA_PATH + "current.stacktrace.log"
    second_stacktrace_file = DATA_PATH + "logs/" + str(time.time()) + ".log"
    print(f"  recording exception to {base_stacktrace_file} and {second_stacktrace_file}", source="record_exception")
    logger.log(f"Got exception:\n{context}", source="EXCEPTION")
    with io.open(base_stacktrace_file, "w") as logfile:
        logfile.write(context)
    os.makedirs(os.path.dirname(second_stacktrace_file), exist_ok=True)
    with io.open(second_stacktrace_file, "w") as logfile:
        logfile.write(context)
    return second_stacktrace_file

ExceptionAcknowledgedHook = typing.Callable[[typing.Literal["CANCELLED"] | None], typing.Any]

@diagnose_entry
def _global_exception_handler(exception: Exception, context: str = "No context available.", acknowledgement_hook: ExceptionAcknowledgedHook | None = None):
    try:
        filename = record_exception(exception, context)
        message = f"Encountered an exception: ({type(exception).__name__}) {exception}\nFull stacktrace available at \"{DATA_PATH}current.stacktrace.log\" and \"{DATA_PATH}/logs/{filename}\"."
        def show_mbox():
            global MBOX_POS
            global CAN_SHOW_MBOX
            global MBOX_COUNT
            if not CAN_SHOW_MBOX:
                return
            if _mbox_time_elapsed() > max_mbox_reset_time:
                MBOX_COUNT = 0
            if _mbox_time_elapsed() > 5:
                MBOX_POS = None
            if MBOX_POS is None:
                MBOX_POS = showwarning_at(title="Exception encountered", message=message, x = None, y = None, ack=acknowledgement_hook)
            else:
                MBOX_POS = showwarning_at(title="Exception encountered", message=message, x = MBOX_POS[0], y = MBOX_POS[1], ack=acknowledgement_hook)
            MBOX_COUNT += 1
            if MBOX_COUNT > max_mbox_count:
                CAN_SHOW_MBOX = False
                errorstr = f"FATAL: encountered {MBOX_COUNT} exceptions within {max_mbox_reset_time} second{'' if max_mbox_reset_time == 1 else 's'}, terminating program early."
                print(f"TOO MANY ERRORBOXES: {errorstr}", source="GEH")
                quit_error(errorstr)
            _set_mbox_time()
        queue_deferred(show_mbox)
    except Exception as e:
        errorstr = f"FATAL: error encountered while processing {type(exception).__name__} ({exception}): {type(e).__name__}: {e}"
        print(f"GEH encountered an error: {errorstr}", source="GEH")
        quit_error(errorstr)

ReportExceptionHook = typing.Callable[[Exception, str | None], typing.Any]

_exception_hooks: dict[str, ReportExceptionHook] = {}

@diagnose_entry(args=True, only_verbose=True)
def add_exception_hook(name: str, func: ReportExceptionHook):
    if _exception_hooks.get(name) is not None:
        raise RuntimeError(f"Couldn't add exception hook {name}, {name} is already registered")
    _exception_hooks[name] = func

@diagnose_entry(args=True, only_verbose=True)
def remove_exception_hook(name: str):
    if _exception_hooks.get(name) is None:
        raise RuntimeError(f"Couldn't remove exception hook {name}, {name} isn't registered.")
    _exception_hooks.pop(name)

class ReportExceptionCancellationError(RuntimeError):
    pass

@diagnose_entry
def CancelExceptionReporting():
    raise ReportExceptionCancellationError("shared.CancelExceptionReporting was called.")

@diagnose_entry
def report_exception(e: Exception, context: str | None = None, acknowledgement_hook: ExceptionAcknowledgedHook | None = None):
    logger.flush()
    try:
        print(f"Called shared.report_exception: ({type(e).__name__}) {e} with context {context}", source="report_exception")
        context = exception_to_filtered_traceback(e, context=context)
        exception_hook_count = len(_exception_hooks)
        if exception_hook_count > 0:
            print(f"  Executing {exception_hook_count} exception hooks", source="report_exception")
        for name, hook in _exception_hooks.items():
            print(f" Calling hook {name} ({hook})", source="report_exception")
            try:
                hook(e, context)
            except ReportExceptionCancellationError as e2:
                print(f"HOOK CANCELLED EXCEPTION REPORTING: {e2}", source="report_exception")
                if acknowledgement_hook:
                    print(f"Calling acknowledgement hook ({acknowledgement_hook}) with CANCELLED meta", source="report_exception")
                    spawn_thread(acknowledgement_hook, "CANCELLED")
                return
            except Exception as e2:
                quit_error(f"An exception was encountered in exception hook {name} ({hook})", e2)
        print(f"GEH called", source="report_exception")
        main_thread_async(_global_exception_handler, e, context, acknowledgement_hook)
    except Exception as e:
        quit_error(f"Encountered an exception ({type(e).__name__}) {e}", e)

def _try_get_thread_context(*, showerror: bool = True) -> str | None:
    try:
        return thread_context.value
    except Exception as e:
        if showerror:
            print(f"Couldn't get thread context for thread {threading.current_thread()}: ({type(e).__name__}) {e}")
        return None

def _thread_ctx(func: typing.Callable, context: str, *args, **kwargs):
    try:
        global thread_context
        thread_context.value = context
        verbose_print(f"calling {func} with {args}")
        func(*args, **kwargs)
    except Exception as e:
        report_exception(e, context)
        
_to_filter_functions = ["_thread_ctx", "run", "_bootstrap_inner", "_bootstrap", "mainloop", "__call__", "callit", "spawn_thread"]

def exception_to_filtered_traceback(e: Exception, context: str | None = None) -> str:
    filtered = []
    if context is not None:
        filtered.append(f"Context for exception {type(e).__name__}: {e}:")
        filtered.append(context)
    filtered.append(f"Traceback for exception {type(e).__name__}: {e} (most recent call last):")
    cause = e
    indent = -1
    while not (cause is None):
        indent = indent + 1
        filtered.append(filtered_traceback(cause.__traceback__, indent=indent))
        if not cause.__cause__ is None:
            cause = cause.__cause__
            filtered.append(f"The above exception was directly caused by the following:")
            filtered.append(f"Traceback for exception {type(cause).__name__}: {cause} (most recent call last):")
        elif not (cause.__context__ is None) and not cause.__suppress_context__:
            cause = cause.__context__
            filtered.append(f"During handling of the above exception, another exception occurred:")
            filtered.append(f"Traceback for exception {type(cause).__name__}: {cause} (most recent call last):")
        else:
            cause = None
    return '\n'.join(filtered)

def must_recover(allowed_exceptions: tuple[typing.Type[BaseException]] = tuple([])):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except allowed_exceptions:
                raise
            except Exception as e:
                print(f"Encountered an exception while running {func}: ({type(e).__name__}) {e}", source="MUST RECOVER")
                try:
                    print("  attempting to report it...", source="MUST RECOVER")
                    report_exception(e, context=_try_get_thread_context())
                except Exception as e2:
                    print(f"reporting failed with ({type(e2).__name__}) {e2}", source="MUST RECOVER")
            return None
        return wrapper
    return decorator

_deferred_queue: list[typing.Callable] = []
_deferred_queue_access = threading.RLock()
_deferred_queue_begin = threading.Event()

def _deferred_queue_worker():
    global _deferred_queue
    while True:
        _deferred_queue_begin.wait()
        owned_funcs = []
        with _deferred_queue_access:
            _deferred_queue_begin.clear()
            owned_funcs = _deferred_queue
            _deferred_queue = []
        for func in owned_funcs:
            func()

@diagnose_entry
def queue_deferred(func: typing.Callable, *args, **kwargs):
    with _deferred_queue_access:
        @functools.wraps(func)
        def wrapper():
            try:
                func(*args, **kwargs)
            except Exception as e:
                _global_exception_handler(e, "Exception encountered in deferred queue.")
        _deferred_queue.append(wrapper)
        _deferred_queue_begin.set()

def filtered_traceback(parent_frame: types.TracebackType | None = None, indent: int|None = None) -> str:
    stack: traceback.StackSummary
    if indent is None:
        indent = 0
    indent_str = "  " * indent
    if parent_frame is None:
        stack = traceback.extract_stack()
    else:
        stack = traceback.extract_tb(parent_frame)
    filtered = ""
    was_filtered = False
    for frame in stack:
        if frame.name == "filtered_traceback":
            continue
        if frame.name in _to_filter_functions:
            if was_filtered:
                filtered += " -> "
            else:
                filtered += indent_str
                filtered += "In "
            filtered += frame.name
            was_filtered = True
        else:
            if was_filtered:
                filtered += " ->\n"
            filtered += f"{indent_str}{frame.name} in file {frame.filename}, line {frame.lineno}\n  {frame.line}\n"
            was_filtered = False
    filtered = filtered.removesuffix('\n') + '\n'
    return filtered

@diagnose_entry(args=True, only_verbose=True)
def spawn_thread(func: typing.Callable[P, T], *args: P.args, **kwargs: P.kwargs):
    context = _try_get_thread_context(showerror=False)
    if context is None:
        context = ""
    stack = context + filtered_traceback()
    @functools.wraps(func)
    def wrapped_thread_ctx():
        _thread_ctx(func, stack, *args, **kwargs)
    thread = threading.Thread(target=wrapped_thread_ctx, daemon=True)
    thread.start()

def reboot():
    print(f"REBOOT CALLED: {''.join(traceback.format_stack())}  WITH CONTEXT: {_try_get_thread_context()}")
    try:
        with open(DATA_PATH + "persist.txt", "w") as f:
            f.write('\n'.join(map(lambda file: file.name, logger.files)))
        logger.close()
    except:
        pass
    os.execv(sys.executable, [sys.executable] + sys.argv)

def quit() -> typing.Any:
    print(f"DEFAULT shared.quit called!")
    for i in range(5):
        print(f"THIS IS A CATASTROPHIC ERROR!!")
    os._exit(1)

def quit_error(text: str, source: Exception | None = None) -> typing.Any:
    print(f"DEFAULT shared.quit_error called with text {text}! ({type(source).__name__}) {source}")
    for i in range(5):
        print(f"THIS IS A CATASTROPHIC ERROR!!")
    os._exit(1)

def main_thread_sync(_: typing.Callable[..., T], *args, **kwargs) -> T:
    raise RuntimeError("Attempted to call shared.main_thread_sync before shared.begin was called.")

def main_thread_async(_: typing.Callable, *args, **kwargs):
    raise RuntimeError("Attempted to call shared.main_thread_async before shared.begin was called.")

def PluginNoAction(input: str) -> str:
    return input

@diagnose_entry
def begin(
        quit_func: typing.Callable[[], typing.Any],
        quit_error_func: typing.Callable[[str, Exception | None], typing.Any],
        main_thread_async_func,
        main_thread_sync_func
        ):
    global quit
    global quit_error
    global main_thread_sync
    global main_thread_async
    quit = quit_func
    def qerrwrapper(text: str, source: Exception | None = None):
        quit_error_func(text, source)
    quit_error = qerrwrapper
    main_thread_async = main_thread_async_func
    main_thread_sync = main_thread_sync_func
    spawn_thread(_deferred_queue_worker)

class Checkpoint:
    def __init__(self):
        self.checkpoints = [("@start", time.monotonic())]
    
    def checkpoint(self, name: str):
        self.checkpoints.append((name, time.monotonic()))

    def ignore(self):
        self.checkpoints.append(("@ignore", time.monotonic()))

    def end(self):
        self.checkpoints.append(("@end", time.monotonic()))

    def print(self):
        print("Checkpoints:", source="CHECKPOINTS")
        starting_checkpoint = self.checkpoints[0]
        for i, point in enumerate(self.checkpoints):
            if i == 0:
                continue
            name = point[0]
            end = point[1]
            start = self.checkpoints[i - 1][1]
            if name.startswith("@"):
                continue
            print(f"{name}: {((end - start) * 1000):.2f}ms", source="CHECKPOINTS")
        final_checkpoint = self.checkpoints[len(self.checkpoints) - 1]
        print(f"TOTAL ---\n  {((final_checkpoint[1] - starting_checkpoint[1]) * 1000):.2f}ms", source="CHECKPOINTS")

class TranscriptionCancelledError(RuntimeError):
    pass

class ModelInitCancelledError(RuntimeError):
    pass

class SharedLoadingState:
    def __init__(self, window: tk.Tk, settext: typing.Callable[[str], typing.Any]):
        self.window = window
        self.settext = settext

    def tk_config(self, widget: tk.BaseWidget, *args, **kwargs):
        def worker():
            widget.configure(*args, **kwargs)
        self.mainthread(worker)

    def fix_window_size(self):
        def worker():
            self.window.minsize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        main_thread_sync(worker)
    
    def queue_mainthread(self, func: typing.Callable[..., typing.Any], *args, **kwargs):
        @functools.wraps(func)
        def wrapper():
            func(*args, **kwargs)
        self.window.after(0, wrapper)

    def mainthread(self, func: typing.Callable[..., T], *args, **kwargs) -> T:
        if threading.current_thread() is threading.main_thread():
            return func(*args, **kwargs)
        value = None
        exception = None
        complete = threading.Event()
        @functools.wraps(func)
        def wrapper():
            nonlocal value
            nonlocal exception
            try:
                value = func(*args, **kwargs)
            except BaseException as e:
                exception = e
            finally:
                complete.set()
        self.window.after(0, wrapper)
        complete.wait()
        if exception is not None:
            raise exception
        return typing.cast(T, value)

    def ask_allow_or_deny(self, text: str, extra_info: str | None = None) -> bool:
        self.settext(text)
        def _resize_window_first():
            if self.window.winfo_width() < 500:
                self.window.minsize(500, self.window.winfo_height())
        main_thread_async(_resize_window_first)
        allowed = False
        button_pressed = threading.Event()
        def on_allow():
            nonlocal allowed
            allowed = True
            button_pressed.set()
        def on_deny():
            nonlocal allowed
            allowed = False
            button_pressed.set()
        allow = None
        deny = None
        what = None
        def create_buttons():
            nonlocal allow
            nonlocal deny
            nonlocal what
            allow = tk.Button(self.window, text="Allow", command=on_allow)
            deny = tk.Button(self.window, text="Deny", command=on_deny)
            allow.pack(padx=10, pady=10, side=tk.LEFT)
            deny.pack(padx=10, pady=10, side=tk.LEFT)
            if extra_info is not None:
                what = tk.Button(self.window, text="What?", command=lambda: spawn_thread(lambda: messagebox.showinfo("What?", extra_info)))
                what.pack(padx=10, pady=10, side=tk.LEFT)
            self.on_force_geometry_change()
        main_thread_sync(create_buttons)
        button_pressed.wait()
        def destroy_buttons():
            if allow is not None:
                allow.destroy()
            if deny is not None:
                deny.destroy()
            if what is not None:
                what.destroy()
            self.on_force_geometry_change()
        main_thread_sync(destroy_buttons)
        return allowed

    def on_force_geometry_change(self):
        def worker():
            self.window.update_idletasks()
            self.window.geometry(f"{self.window.winfo_reqwidth()}x{self.window.winfo_reqheight()}")
        main_thread_sync(worker)

class PluginLoadingState(SharedLoadingState):
    def __init__(self,
                 window: tk.Tk,
                 settext: typing.Callable[[str], typing.Any],
                 quit: typing.Callable[[], typing.Any],
                 cancel_init: typing.Callable[[str], typing.Any],
                 show_spinner: typing.Callable[[], typing.Any],
                 hide_spinner: typing.Callable[[], typing.Any],
                 filter_name: str,
                 action_options: dict | None
                 ):
        super().__init__(window, settext)
        self.settext = settext
        self.quit = quit
        self.cancel_init = cancel_init
        self.show_spinner = show_spinner
        self.hide_spinner = hide_spinner
        self.filter_name = filter_name
        self.action_options = action_options
    
    def _missing_action_options(self) -> RuntimeError:
        return RuntimeError(f"No action_options were provided for the filter \"{self.filter_name}\"!")    

    def get_option_str(self, option_name: str) -> str:
        if self.action_options is None:
            raise self._missing_action_options()
        option = self.action_options.get(option_name)
        if option is None:
            raise RuntimeError(f"action_options for filter \"{self.filter_name}\" is missing \"{option_name}\" (a string value)! Add it in {FILTERCONFIG_FILENAME}!")
        if not isinstance(option, str):
            raise RuntimeError(f"action_options for filter \"{self.filter_name}\" has a {type(option).__name__} as \"{option_name}\" instead of a string. Fix this in {FILTERCONFIG_FILENAME}!")
        return option

    def get_option_bool(self, option_name: str) -> bool:
        if self.action_options is None:
            raise self._missing_action_options()
        option = self.action_options.get(option_name)
        if option is None:
            raise RuntimeError(f"action_options for filter \"{self.filter_name}\" is missing \"{option_name}\" (a boolean value)! Add it in {FILTERCONFIG_FILENAME}!")
        if not isinstance(option, bool):
            raise RuntimeError(f"action_options for filter \"{self.filter_name}\" has a {type(option).__name__} as \"{option_name}\" instead of a boolean. Fix this in {FILTERCONFIG_FILENAME}!")
        return option
    
    def get_option_number(self, option_name: str) -> float:
        if self.action_options is None:
            raise self._missing_action_options()
        option = self.action_options.get(option_name)
        if option is None:
            raise RuntimeError(f"action_options for filter \"{self.filter_name}\" is missing \"{option_name}\" (a number value)! Add it in {FILTERCONFIG_FILENAME}!")
        if not isinstance(option, (int, float)) or isinstance(option, bool):
            raise RuntimeError(f"action_options for filter \"{self.filter_name}\" has a {type(option).__name__} as \"{option_name}\" instead of a number. Fix this in {FILTERCONFIG_FILENAME}!")
        return option

    def get_option_str_or(self, option_name: str, default: str) -> str:
        try:
            return self.get_option_str(option_name)
        except:
            pass
        return default
    
    def get_option_bool_or(self, option_name: str, default: bool) -> bool:
        try:
            return self.get_option_bool(option_name)
        except:
            pass
        return default
    
    def get_option_number_or(self, option_name: str, default: float) -> float:
        try:
            return self.get_option_number(option_name)
        except:
            pass
        return default

_tracked_toplevels: list[tk.Toplevel] = []

def TopLevelCentered(*args, w: int, h: int, **kwargs) -> tk.Toplevel:
    win = TopLevel(*args, **kwargs)
    x_offset = (win.winfo_screenwidth() // 2) - (w // 2)
    y_offset = (win.winfo_screenheight() // 2) - (h // 2)
    win.geometry(f"{w}x{h}+{x_offset}+{y_offset}")
    return win

def TopLevel(*args, **kwargs) -> tk.Toplevel:
    win = tk.Toplevel(*args, **kwargs)
    _tracked_toplevels.append(win)
    def _destroy_wrapper(destroy=win.destroy):
        destroy()
        _tracked_toplevels.remove(win)
    win.destroy = _destroy_wrapper
    return win

def resize_TopLevel(win: tk.Toplevel, w: int, h: int) -> None:
    win.update_idletasks()
    old_width = win.winfo_width()
    old_height = win.winfo_height()
    old_x = win.winfo_x()
    old_y = win.winfo_y()
    center_x = old_x + old_width // 2
    center_y = old_y + old_height // 2
    new_x = center_x - w // 2
    new_y = center_y - h // 2
    win.geometry(f"{w}x{h}+{new_x}+{new_y}")

class CUDAError(RuntimeError):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class CUDANotFoundError(RuntimeError):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class CUDANotSupportedError(RuntimeError):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class MajorMinorVersion:
    def __init__(self, major: int, minor: int):
        self.major = major
        self.minor = minor

    @classmethod
    def from_str(cls, version: str) -> "MajorMinorVersion":
        listed = version.split(".")
        if len(listed) != 2:
            raise RuntimeError(f"Attempted to create a MajorMinorVersion from a string that did not have a major and minor version ({version})")
        return MajorMinorVersion(int(listed[0]), int(listed[1]))

    def __repr__(self):
        return f"MajorMinorVersion({self.major}, {self.minor})"

    def __str__(self):
        return f"{self.major}.{self.minor}"

class CudaVersion:
    def __init__(self, major: int, minor: int, tag: str, pytorch_version: str, sm_major: int, sm_minor: int):
        self.major = major
        self.minor = minor
        self.tag = tag
        self.pytorch_version = pytorch_version
        self.sm_major = sm_major
        self.sm_minor = sm_minor
    
    def __str__(self):
        return f"CUDA {self.major}.{self.minor} requires SM {self.sm_major}.{self.sm_minor}, has tag {self.tag} and version {self.pytorch_version}"

class ModelLoadingState(SharedLoadingState):
    def __init__(self,
                 window: tk.Tk,
                 settext: typing.Callable[[str], typing.Any],
                 quit: typing.Callable[[], typing.Any],
                 cancel_init: typing.Callable[[str], typing.Any],
                 show_spinner: typing.Callable[[], typing.Any],
                 hide_spinner: typing.Callable[[], typing.Any],
                 model_dir: str,
                 prompt: str,
                 model_keywords: list[str],
                 allow_cpu: bool
                 ):
        super().__init__(window, settext)
        self.quit = quit
        self.cancel_init = cancel_init
        self.model_dir = model_dir
        self.allow_cpu = allow_cpu
        self.show_spinner = show_spinner
        self.hide_spinner = hide_spinner
        self.model_keywords = model_keywords
        self.prompt = prompt
        self.checkpoints = Checkpoint()

    def show_cpu_warning(self):
        def confirm_cpu():
            messagebox.showwarning("STT Loaded to CPU", "The speech-to-text model was loaded to your CPU.\nDisable this warning in the config by changing warn_on_cpu to false.")
        main_thread_sync(confirm_cpu)

    def load_and_check_torch(self):
        print("Loading pytorch...", source="TORCHLOAD")
        self.settext("Loading pytorch...")
        try:
            import torch
            import torch.version
            if ARGS.run_torch_download:
                raise ModuleNotFoundError("Forced torch loading failure due to --run-torch-download being set.")
        except ModuleNotFoundError as e:
            print(f"Couldn't import torch and torch.version: {e}", source="TORCHLOAD")
            def _show_info():
                messagebox.showinfo("Torch not found", "PyTorch was not found! Use this installer or run setup.bat again.")
            main_thread_async(_show_info)
            time.sleep(0.5)
            self.run_pytorch_downloader()
            raise ModelInitCancelledError()
        print("Initialized.")
        print(f"torch version: {torch.__version__}", source="TORCHLOAD")
        print(f"cuda available: {torch.cuda.is_available()}", source="TORCHLOAD")
        print(f"cuda version: {torch.version.cuda}", source="TORCHLOAD")
        print(f"Torch threads: {torch.get_num_threads()}", source="TORCHLOAD")
        print(f"Torch interop: {torch.get_num_interop_threads()}", source="TORCHLOAD")
        print(f"Python threads: {len(threading.enumerate())}", source="TORCHLOAD")
        if not torch.cuda.is_available() and not self.allow_cpu:
            self.settext("Waiting for user input...")
            why_no_cuda = "Something went wrong."
            try:
                torch.cuda.current_device()
            except Exception as e:
                print(f"Encountered an exception while checking cuda device: {type(e).__name__} {e}", source="TORCHLOAD")
                why_no_cuda = f"{e}"
            def download_pytorch() -> bool | None:
                return messagebox.askyesno("STT Loaded to CPU", f"PyTorch was loaded to your CPU because CUDA wasn't available: {why_no_cuda}\nThis will lead to degraded performance.\nPress YES to download pytorch for GPU or press NO to ignore.\nDisable this warning in the settings by changing warn_on_cpu to false.")
            choice = main_thread_sync(download_pytorch)
            if choice is None:
                self.quit()
                raise ModelInitCancelledError()
            if choice:
                self.cancel_init("A reboot of STT is required to finish the pytorch download. After pytorch is finished downloading, reboot STT. Don't do it before the installation completes.")
                self.run_pytorch_downloader()
                raise ModelInitCancelledError()

    def run_pytorch_downloader(self):
        def worker():
            self.settext("Waiting for PyTorch version to be selected...")
            window = TopLevelCentered(w=700, h=500)
            CAN_QUIT_QUIETLY = True
            def window_close_hook():
                if CAN_QUIT_QUIETLY:
                    window.destroy()
                    self.quit()
                else:
                    messagebox.showwarning("Installation in progress", "The installation is still in progress. It may look frozen at times. Wait for the popup telling you the download is finished!")
            window.protocol("WM_DELETE_WINDOW", window_close_hook)
            window.focus_force()
            window.title("STT PyTorch Cuda Installer")
            setattr(window, "gpu_var", tk.StringVar(window, value="Detecting..."))
            setattr(window, "driver_var", tk.StringVar(window, value="Detecting..."))
            setattr(window, "recommendation_var", tk.StringVar(window, value="Detecting..."))
            gpu_var = getattr(window, "gpu_var")
            driver_var = getattr(window, "driver_var")
            recommendation_var = getattr(window, "recommendation_var")

            ttk.Label(window, text="GPU:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
            ttk.Label(window, textvariable=gpu_var).grid(row=0, column=1, sticky="w")

            ttk.Label(window, text="CUDA Version:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
            ttk.Label(window, textvariable=driver_var).grid(row=1, column=1, sticky="w")

            ttk.Label(window, text="Recommended PyTorch Build:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
            ttk.Label(window, textvariable=recommendation_var).grid(row=2, column=1, sticky="w")
            cuda_tag = None
            torch_version = None

            def suggested_cuda_URL() -> str:
                if cuda_tag is None:
                    return "https://download.pytorch.org/whl/cpu"
                return f"https://download.pytorch.org/whl/{cuda_tag}"

            def install_pytorch():
                nonlocal CAN_QUIT_QUIETLY
                self.tk_config(install_button, state="disabled")
                def worker():
                    nonlocal CAN_QUIT_QUIETLY
                    CAN_QUIT_QUIETLY = False
                    try:
                        if cuda_tag is None or torch_version is None:
                            try:
                                import torch
                            except ModuleNotFoundError:
                                messagebox.showerror("Torch not found", "Torch was not installed. Run setup.bat again to fix this.")
                                return
                            messagebox.showerror("No CUDA available", "Can't find a matching version of PyTorch. STT will now use your CPU, not your GPU. This is much slower.")
                            try:
                                import tomlkit
                                with open(CONFIG_FILENAME, "r", encoding="utf-8") as f:
                                    config = tomlkit.parse(f.read())
                                config["meta"]["warn_on_cpu"] = False
                                with open(CONFIG_FILENAME, "w", encoding="utf-8") as f:
                                    f.write(tomlkit.dumps(config))
                            except Exception as e:
                                report_exception(e)
                                pass
                            messagebox.showinfo("Restart required", "Please restart STT. Note that you are using CPU inference, which is much slower.")
                            return
                        PINNED_TORCHAUDIO_VERSIONS = {
                            "2.12.0": "2.11.0",
                            "2.2.2": "2.2.2"
                        }
                        PINNED_NUMPY_VERSION = "1.26.4"
                        cmd = [sys.executable, "-m", "pip", "install",
                                f"torch=={torch_version}+{cuda_tag}",
                                "--force-reinstall",
                                "lightning<2.4.0",
                                f"torchaudio=={PINNED_TORCHAUDIO_VERSIONS.get(torch_version, '2.11.0')}",
                                "fsspec==2024.12.0",
                                "pyarrow<26",
                                f"numpy=={PINNED_NUMPY_VERSION}",
                                "--extra-index-url",
                                suggested_cuda_URL()
                                ]
                        write_log("Running: ")
                        write_log(" ".join(cmd))
                        process = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True
                        )
                        self.settext("Downloading PyTorch...")
                        if process.stdout is None:
                            raise RuntimeError("While running pytorch installer, stdout was None.")
                        for line in process.stdout:
                            write_log(line.rstrip())
                        code = process.wait()
                        if code == 0:
                            def finished():
                                nonlocal CAN_QUIT_QUIETLY
                                CAN_QUIT_QUIETLY = True
                                self.hide_spinner()
                                self.settext("Install complete!")
                                messagebox.showinfo("Success", "PyTorch installer completed.")
                                reboot()
                                self.quit()
                        else:
                            def finished():
                                nonlocal CAN_QUIT_QUIETLY
                                CAN_QUIT_QUIETLY = True
                                self.hide_spinner()
                                self.settext("Install failed!")
                                messagebox.showinfo("Failed", f"PyTorch installer failed with code {code}!\nIf you want to install PyTorch yourself, run the command in the log.\nYou can also try googling PyTorch CUDA install!")
                                self.quit()
                        self.mainthread(finished)
                    except Exception as e:
                        CAN_QUIT_QUIETLY = True
                        self.hide_spinner()
                        self.settext("Install failed!")
                        messagebox.showwarning("An error occurred", f"An error occurred while trying to install CUDA: {e}")
                def driver():
                    global CAN_QUIT_QUIETLY
                    try:
                        worker()
                    except:
                        raise
                    finally:
                        CAN_QUIT_QUIETLY = True
                spawn_thread(driver)
                        
            def write_log(text: str):
                def worker():
                    print(text, source="CUDA WORKER")
                    log.insert(tk.END, text + "\n")
                    log.see(tk.END)
                main_thread_sync(worker)
                
            install_button = ttk.Button(
                window,
                text="Install PyTorch",
                command=install_pytorch
            )
            install_button.grid(row=3, column=0, columnspan=2, pady=10)
            log = tk.Text(window)
            log.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
            window.grid_rowconfigure(4, weight=1)
            window.grid_columnconfigure(1, weight=1)
            window.attributes('-topmost', True)
            window.after_idle(window.attributes, '-topmost', False)
            window.update_idletasks()
            write_log(" -- CUDA install log --")
            USED_NVIDIA_SMI_PATH = ""
            try:
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                    capture_output=True, text=True, check=True
                )
                USED_NVIDIA_SMI_PATH = "nvidia-smi"
            except FileNotFoundError as e:
                fallback_path = r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"
                write_log(f"Couldn't find nvidia-smi on path, checking {fallback_path}")
                result = subprocess.run(
                    [fallback_path, "--query-gpu=name", "--format=csv,noheader"],
                    capture_output=True, text=True, check=True
                )
                USED_NVIDIA_SMI_PATH = fallback_path
            except Exception as e:
                write_log(f"No NVIDIA GPU detected. ({type(e).__name__}) {e}")
                gpu_var.set("No NVIDIA GPU detected")
                driver_var.set("N/A")
                recommendation_var.set("CPU Only")
                self.tk_config(install_button, state="enabled")
                return
            gpu_name = result.stdout.splitlines()[0].strip()
            cuda_version: MajorMinorVersion | None = None
            try:
                write_log(f"Found GPU {gpu_name}")
                write_log("Detecting NVIDIA driver CUDA support...")
                result = subprocess.run(
                    [USED_NVIDIA_SMI_PATH],
                    capture_output=True, text=True, check=True
                )
                match = re.search(r"CUDA (?:UMD )?Version:\s+(\d+\.\d+)", result.stdout)
                print(f"nvidia-smi output:", source="NVIDIA-SMI")
                for line in result.stdout.splitlines():
                    print(line, source="NVIDIA-SMI")
                if not match:
                    raise CUDANotFoundError("Unable to determine CUDA version from nvidia-smi.")
                cuda_version = MajorMinorVersion.from_str(match.group(1))
                write_log(f"Driver supports CUDA {cuda_version}")
                gpu_var.set(gpu_name)
                driver_var.set(match.group(1))
                pytorch_cuda_versions = [
                    CudaVersion(13, 2, "cu132", "2.12.0", 7, 5),
                    CudaVersion(13, 0, "cu130", "2.12.0", 7, 5),
                    CudaVersion(12, 8, "cu128", "2.11.0", 7, 5),
                    CudaVersion(12, 6, "cu126", "2.12.0", 5, 0),
                    CudaVersion(11, 8, "cu118", "2.2.0",  5, 0),
                ]
                cuda_tag = None
                GPUSM = MajorMinorVersion(0,0)
                import pynvml
                print(f"Performing NVML check to determine GPU SM", source="NVML")
                try:
                    pynvml.nvmlInit()
                    device_count = pynvml.nvmlDeviceGetCount()
                    print(f"Found {device_count} devices", source="NVML")
                    for i in range(device_count):
                        handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                        name = pynvml.nvmlDeviceGetName(handle)
                        if isinstance(name, bytes):
                            name = name.decode("utf-8")
                        print(f"Device {i} handle {handle} has name {name}", source="NVML")
                        if name.strip().lower() == gpu_name.strip().lower():
                            major, minor = pynvml.nvmlDeviceGetCudaComputeCapability(handle)
                            print(f"Device {i} handle {handle} matches GPU name {gpu_name}; SM {major}.{minor}", source="NVML")
                            GPUSM.major = major
                            GPUSM.minor = minor
                            break
                    else:
                        raise ValueError(f"GPU '{gpu_name}' not found.")
                except:
                    write_log(f"Couldn't determine GPU SM version, using 7.5")
                    GPUSM.major = 7
                    GPUSM.minor = 5
                finally:
                    pynvml.nvmlShutdown()
                print(f"Finished NVML check.", source="NVML")
                selected_cuda_version_major_minor = MajorMinorVersion(0,0)
                for possible_version in pytorch_cuda_versions:
                    if cuda_version.major < possible_version.major:
                        print(f"Not choosing cuda version {possible_version} because major version was too low {cuda_version.major} vs {possible_version.major}.", source="CUDA")
                        continue
                    if cuda_version.major == possible_version.major and cuda_version.minor < possible_version.minor:
                        print(f"Not choosing cuda version {possible_version} because minor version was too low {cuda_version.minor} vs {possible_version.minor}.", source="CUDA")
                        continue
                    print(f"Candidate cuda version {possible_version.tag} found, checking SM against gpu {gpu_name}", source="CUDA")
                    if GPUSM.major < possible_version.sm_major:
                        print(f"Not choosing cuda version {possible_version} because GPUSM {GPUSM} did not meet required SM: {possible_version.sm_major}.{possible_version.sm_minor}")
                        write_log(f"Couldn't choose cuda {possible_version.major}.{possible_version.minor} because GPU SM {GPUSM} did not meet the required SM: {possible_version.sm_major}.{possible_version.sm_minor}")
                        continue
                    if GPUSM.minor == possible_version.sm_minor and GPUSM.major < possible_version.sm_major:
                        print(f"Not choosing cuda version {possible_version} because GPUSM {GPUSM} did not meet required SM: {possible_version.sm_major}.{possible_version.sm_minor}")
                        write_log(f"Couldn't choose cuda {possible_version.major}.{possible_version.minor} because GPU SM {GPUSM} did not meet the required SM: {possible_version.sm_major}.{possible_version.sm_minor}")
                        continue
                    cuda_tag = possible_version.tag
                    torch_version = possible_version.pytorch_version
                    selected_cuda_version_major_minor.major = possible_version.major
                    selected_cuda_version_major_minor.minor = possible_version.minor
                    write_log(f"Chose CUDA {selected_cuda_version_major_minor} ({cuda_tag}) with pytorch version {torch_version}.")
                    break
                if cuda_tag is None:
                    raise CUDANotSupportedError(
                        f"No supported PyTorch CUDA build for CUDA {cuda_version}"
                    )
                recommendation_var.set(
                    f"CUDA {selected_cuda_version_major_minor} (PyTorch v{torch_version})"
                )
            except CUDANotFoundError as e:
                gpu_var.set(gpu_name)
                write_log(f"CUDA detection failed: {e}")
                if messagebox.askyesno("Use CUDA 12.8?", f"Would you like to use CUDA 12.8? If your GPU ({gpu_name}) is at least a 10xx or higher, you can probably run CUDA 12.8."):
                    write_log(f"User selected CUDA 12.8 as fallback.")
                    driver_var.set("Unknown (user-selected 12.8)")
                    cuda_version = MajorMinorVersion(12, 8)
                    cuda_tag = "cu128"
                    torch_version = "2.11.0"
                    recommendation_var.set(
                        f"CUDA 12.8 (PyTorch v{torch_version})"
                    )
                else:
                    write_log(f"User selected CPU as fallback.")
                    gpu_var.set("CPU")
                    cuda_tag = None
                    recommendation_var.set(
                        f"CPU (PyTorch v{torch_version})"
                    )
            except CUDANotSupportedError as e:
                gpu_var.set(gpu_name)
                write_log(f"No supported PyTorch version found for cuda version {cuda_version}. The minimum supported cuda version is 11.8.")
                try:
                    result = subprocess.run(
                        [USED_NVIDIA_SMI_PATH, "--query-gpu=driver_version", "--format=csv,noheader"],
                        capture_output=True, text=True, check=True
                    )
                    driver_version = result.stdout.strip().splitlines()[0]
                    version_tuple = tuple(map(int, driver_version.split(".")))
                    is_compatible = version_tuple >= (522, 6)
                    if not is_compatible:
                        messagebox.showwarning("Driver out of date", f"Your GPU driver is out of date. To run Speech To Text, update to at least driver version 522.06. Your GPU driver version is {driver_version}")
                except Exception as e:
                    write_log(f"Got error while checking GPU driver version: ({type(e).__name__}) {e}")
                driver_var.set(f"{cuda_version}")
                cuda_version = None
                cuda_tag = None
                recommendation_var.set(
                    f"CPU (PyTorch v{torch_version})"
                )
            except Exception as e:
                write_log(f"CUDA detection warning: ({type(e).__name__}) {e}")
                write_log("Assuming CUDA 12.8 as fallback.")

                gpu_var.set(gpu_name)
                driver_var.set(f"{'Unknown' if cuda_version is None else str(cuda_version)} (assuming CUDA 12.8)")

                cuda_version = MajorMinorVersion(12, 8)
                cuda_tag = "cu128"
                torch_version = "2.11.0"

                recommendation_var.set(
                    f"CUDA 12.8 (PyTorch v{torch_version})"
                )
            finally:
                write_log(f"PyTorch install URL:")
                write_log(f"  {suggested_cuda_URL()}")
                if cuda_tag is None:
                    write_log(f"For manual install, cd into STT, run \"venv\\scripts\\activate\", then install your pytorch version. Make sure to include --force-reinstall.")
        self.mainthread(worker)

class SimpleASRModel:
    def __init__(self, state: ModelLoadingState):
        self.state = state
    
    def transcribe(self, file: str) -> str:
        raise NotImplementedError()
    
    def supports_prompting(self) -> bool:
        return False
    
    def default_prompt(self) -> str:
        raise NotImplementedError()

    def set_prompt(self, prompt: str):
        raise NotImplementedError()

class Timer:
    def __init__(self):
        self.start = time.monotonic()
    
    def time(self) -> float:
        return time.monotonic() - self.start
    
    def reset(self) -> float:
        duration = time.monotonic() - self.start
        self.start = time.monotonic()
        return duration
    
    def resetms(self) -> float:
        return self.reset() * 1000
    
    def resetmstrnc(self) -> str:
        return f"{self.resetms():.2f}"
    
    def timems(self) -> float:
        return self.time() * 1000
    
    def timemstrnc(self) -> str:
        return f"{self.timems():.2f}"

def profile(func: typing.Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> typing.Tuple[T, float]:
    timer = Timer()
    val = func(*args, **kwargs)
    return (val, timer.time())

def a_or_an(val: str) -> typing.Literal["a"]|typing.Literal["an"]:
    if val.startswith(("a","e","i","o","u")):
        return "an"
    return "a"