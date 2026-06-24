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

T = typing.TypeVar("T")

thread_context = threading.local()

DATA_PATH = "data/"
CONFIG_PATH = "config/"

VERBOSE = False

def verbose_print(*args, **kwargs):
    if VERBOSE:
        print(*args, **kwargs)

CONFIG_FILENAME = CONFIG_PATH + "userconfig.toml"
CONFIG_BACKUP_FILENAME = CONFIG_PATH + "exampleconfig.toml"
FILTERCONFIG_FILENAME = CONFIG_PATH + "filters.toml"
FILTERCONFIG_BACKUP_FILENAME = CONFIG_PATH + "examplefilters.toml"

def diagnose_entry(func: typing.Callable):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print(f"FUNCTION ENTRY {func.__name__} ({func}) entered")
        had_error = False
        try:
            return func(*args, **kwargs)
        except Exception as e:
            had_error = True
            print(f" FUNCTION ENTRY {func.__name__} ({func}) exception {type(e).__name__} {e}")
            raise
        finally:
            print(f" FUNCTION EXIT {func.__name__} ({func}){' WITH EXCEPTION' if had_error else ''}")
    return wrapper

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

def showwarning_at(title: str, message: str, x: int | None, y: int | None) -> tuple[int, int]:
    global _warningbox_xvel
    global _warningbox_yvel
    unique_title = f"{title} : {uuid.uuid4()}"
    def show_box():
        messagebox.showwarning(unique_title, message)
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
    print(f"shared.record_exception called with ({type(e).__name__}) {e}")
    if context is None:
        context = f"No context given for exception ({type(e).__name__}): {e}\n" + exception_to_filtered_traceback(e, context)
    filename = DATA_PATH + "logs/" + str(time.time()) + ".log"
    with io.open(DATA_PATH + "current.log", "w") as log:
        log.write(context)
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with io.open(filename, "w") as log:
        log.write(context)
    return filename

@diagnose_entry
def _global_exception_handler(exception: Exception, context: str = "No context available."):
    try:
        filename = record_exception(exception, context)
        message = f"Encountered an exception: ({type(exception).__name__}) {exception}\nFull stacktrace available at \"current.log\" and \"{filename}\"."
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
                MBOX_POS = showwarning_at(title="Exception encountered", message=message, x = None, y = None)
            else:
                MBOX_POS = showwarning_at(title="Exception encountered", message=message, x = MBOX_POS[0], y = MBOX_POS[1])
            MBOX_COUNT += 1
            if MBOX_COUNT > max_mbox_count:
                CAN_SHOW_MBOX = False
                errorstr = f"FATAL: encountered {MBOX_COUNT} exceptions within {max_mbox_reset_time} second{'' if max_mbox_reset_time == 1 else 's'}, terminating program early."
                print(errorstr)
                quit_error(errorstr)
            _set_mbox_time()
        queue_deferred(show_mbox)
    except Exception as e:
        errorstr = f"FATAL: error encountered while processing {type(exception).__name__} ({exception}): {type(e).__name__}: {e}"
        print(errorstr)
        quit_error(errorstr)

ReportExceptionHook = typing.Callable[[Exception, str | None], typing.Any]

_exception_hooks: dict[str, ReportExceptionHook] = {}

@diagnose_entry
def add_exception_hook(name: str, func: ReportExceptionHook):
    if _exception_hooks.get(name) is not None:
        raise RuntimeError(f"Couldn't add exception hook {name}, {name} is already registered")
    _exception_hooks[name] = func

@diagnose_entry
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
def report_exception(e: Exception, context: str | None = None):
    print(f"Called shared.report_exception: ({type(e).__name__}) {e} with context {context}")
    context = exception_to_filtered_traceback(e, context=context)
    for name, hook in _exception_hooks.items():
        print(f" Calling hook {name} ({hook}) for shared.report_exception")
        try:
            hook(e, context)
        except ReportExceptionCancellationError as e2:
            print(f"HOOK CANCELLED EXCEPTION REPORTING: {e2}")
            return
        except Exception as e2:
            quit_error(f"An exception was encountered in exception hook {name} ({hook})", e2)
    main_thread_async(_global_exception_handler, e, context)

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
        verbose_print("calling", func, "with", args)
        func(*args, **kwargs)
    except Exception as e:
        report_exception(e, context)
        
_to_filter_functions = ["_thread_ctx", "run", "_bootstrap_inner", "_bootstrap", "mainloop", "__call__", "callit", "spawn_thread"]

def exception_to_filtered_traceback(e: Exception, context: str | None = None) -> str:
    filtered = []
    if not context is None:
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
                print(f"Encountered an exception while running {func}: ({type(e).__name__}) {e}")
                try:
                    print("reporting")
                    report_exception(e, context=_try_get_thread_context())
                except Exception as e2:
                    print(f"reporting failed {e2}")
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

@diagnose_entry
def spawn_thread(func: typing.Callable, *args, **kwargs):
    context = _try_get_thread_context(showerror=False)
    if context is None:
        context = ""
    stack = context + filtered_traceback()
    @functools.wraps(func)
    def wrapped_thread_ctx():
        _thread_ctx(func, stack, *args, **kwargs)
    thread = threading.Thread(target=wrapped_thread_ctx, daemon=True)
    thread.start()

def quit() -> typing.Any:
    raise RuntimeError("Default shared.quit called. Was shared.begin called before this point?")

def quit_error(text: str, source: Exception | None = None) -> typing.Any:
    raise RuntimeError(f"shared.quit_error called with text {text}. Was shared.begin called before this point?")

def main_thread_sync(_: typing.Callable[..., T], *args, **kwargs) -> T:
    raise RuntimeError("Attempted to call shared.main_thread_sync before shared.begin was called.")

def main_thread_async(_: typing.Callable, *args, **kwargs):
    raise RuntimeError("Attempted to call shared.main_thread_async before shared.begin was called.")

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
        print("Checkpoints:")
        starting_checkpoint = self.checkpoints[0]
        for i, point in enumerate(self.checkpoints):
            if i == 0:
                continue
            name = point[0]
            end = point[1]
            start = self.checkpoints[i - 1][1]
            if name.startswith("@"):
                continue
            print(f"{name}: {((end - start) * 1000):.2f}ms")
        final_checkpoint = self.checkpoints[len(self.checkpoints) - 1]
        print(f"TOTAL ---\n  {((final_checkpoint[1] - starting_checkpoint[1]) * 1000):.2f}ms")

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

    def ask_allow_or_deny(self, text: str) -> bool:
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
        def create_buttons():
            nonlocal allow
            nonlocal deny
            allow = tk.Button(self.window, text="Allow", command=on_allow)
            deny = tk.Button(self.window, text="Deny", command=on_deny)
            allow.pack(padx=10, pady=10, side=tk.LEFT)
            deny.pack(padx=10, pady=10, side=tk.LEFT)
            self.on_force_geometry_change()
        main_thread_sync(create_buttons)
        button_pressed.wait()
        def destroy_buttons():
            if allow is not None:
                allow.destroy()
            if deny is not None:
                deny.destroy()
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
            raise RuntimeError(f"action_options for filter \"{self.filter_name}\" is missing \"{option}\" (a string value)! Add it in {FILTERCONFIG_FILENAME}!")
        if not isinstance(option, str):
            raise RuntimeError(f"action_options for filter \"{self.filter_name}\" has a {type(option).__name__} instead of a string. Fix this in {FILTERCONFIG_FILENAME}!")
        return option

    def get_option_bool(self, option_name: str) -> bool:
        if self.action_options is None:
            raise self._missing_action_options()
        option = self.action_options.get(option_name)
        if option is None:
            raise RuntimeError(f"action_options for filter \"{self.filter_name}\" is missing \"{option}\" (a boolean value)! Add it in {FILTERCONFIG_FILENAME}!")
        if not isinstance(option, bool):
            raise RuntimeError(f"action_options for filter \"{self.filter_name}\" has a {type(option).__name__} instead of a boolean. Fix this in {FILTERCONFIG_FILENAME}!")
        return option
    
    def get_option_number(self, option_name: str) -> float:
        if self.action_options is None:
            raise self._missing_action_options()
        option = self.action_options.get(option_name)
        if option is None:
            raise RuntimeError(f"action_options for filter \"{self.filter_name}\" is missing \"{option}\" (a number value)! Add it in {FILTERCONFIG_FILENAME}!")
        if not isinstance(option, (int, float)) or isinstance(option, bool):
            raise RuntimeError(f"action_options for filter \"{self.filter_name}\" has a {type(option).__name__} instead of a number. Fix this in {FILTERCONFIG_FILENAME}!")
        return option

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
        print("Loading pytorch...")
        self.settext("Loading pytorch...")
        import torch
        import torch.version
        print("Initialized.")
        print("torch version:", torch.__version__)
        print("cuda available:", torch.cuda.is_available())
        print("cuda version:", torch.version.cuda)
        if not torch.cuda.is_available() and not self.allow_cpu:
            self.settext("Waiting for user input...")
            why_no_cuda = "Something went wrong."
            try:
                torch.cuda.current_device()
            except Exception as e:
                print(type(e).__name__)
                print(e)
                why_no_cuda = f"{e}"
            def download_pytorch() -> bool | None:
                return messagebox.askyesnocancel("STT Loaded to CPU", f"PyTorch was loaded to your CPU because CUDA wasn't available: {why_no_cuda}\nThis will lead to degraded performance.\nPress YES to download pytorch for GPU, press NO to ignore, and press CANCEL to close STT.\nDisable this warning in the config by changing warn_on_cpu to false.")
            choice = main_thread_sync(download_pytorch)
            if choice is None:
                self.quit()
                raise ModelInitCancelledError()
            if choice:
                self.cancel_init("A reboot of STT is required to finish the pytorch download.")
                self.run_pytorch_downloader()
                raise ModelInitCancelledError()

    def run_pytorch_downloader(self):
        def worker():
            self.settext("Waiting for PyTorch version to be selected...")
            window = tk.Toplevel()
            def window_close_hook():
                window.destroy()
                self.quit()
            window.protocol("WM_DELETE_WINDOW", window_close_hook)
            window.title("STT PyTorch Cuda Installer")
            window.geometry("700x500")
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
                self.tk_config(install_button, state="disabled")
                def worker():
                    try:
                        if cuda_tag is None or torch_version is None:
                            return
                        cmd = [sys.executable, "-m", "pip", "install",
                                f"torch=={torch_version}+{cuda_tag}", "--force-reinstall", "lightning<2.4.0", "fsspec==2024.12.0", "numpy==1.26.4", "--extra-index-url", suggested_cuda_URL()]
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
                                messagebox.showinfo("Success", "PyTorch installer completed.")
                                self.quit()
                        else:
                            def finished():
                                messagebox.showinfo("Failed", f"PyTorch installer failed with code {code}!\nIf you want to install PyTorch yourself, run the command in the log.\nYou can also try googling PyTorch CUDA install!")
                                self.quit()
                        self.mainthread(finished)
                    except Exception as e:
                        def errbox():
                            messagebox.showwarning("An error occurred", f"An error occurred while trying to install CUDA: {e}")
                        errbox()
                spawn_thread(worker)
                        
            def write_log(text: str):
                def worker():
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
            write_log(" -- CUDA install log --")
            try:
                write_log("Detecting installed GPU...")
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                    capture_output=True, text=True, check=True
                )
                gpu_name = result.stdout.splitlines()[0].strip()
                write_log(f"Found GPU {gpu_name}")
                write_log("Detecting installed drivers...")
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                    capture_output=True, text=True, check=True
                )
                driver_str = result.stdout.splitlines()[0].strip()
                driver_version = float(re.findall(r"^\d+\.\d+", driver_str)[0])
                write_log(f"Found driver version {driver_version}")
                gpu_var.set(gpu_name)
                driver_var.set(driver_str)
                if driver_version >= 525.60:
                    cuda_tag = "cu126"
                    torch_version = "2.12.0"
                    recommendation_var.set("CUDA 12.6 (PyTorch v2.12.0)")
                elif driver_version >= 450.80:
                    cuda_tag = "cu118"
                    torch_version = "2.2.2"
                    recommendation_var.set("CUDA 11.8 (PyTorch v2.2.2)")
                else:
                    raise RuntimeError("No CUDA version available.")
            except Exception as e:
                write_log(f"No NVIDIA GPU detected.")
                gpu_var.set("No NVIDIA GPU detected")
                driver_var.set("N/A")
                recommendation_var.set("CPU Only")
                self.tk_config(install_button, state="disabled")
            finally:
                write_log(f"PyTorch install URL:")
                write_log(f"  {suggested_cuda_URL()}")
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