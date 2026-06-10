import sys
print(sys.path)
print("Starting...")
try:
    print("Importing utilities...")
    import threading
    import pynput
    import string
    import pyaudio
    import time
    import wave
    import tomllib
    import tomlkit
    import typing
    import pyperclip
    import keyboard
    import ctypes
    import os
    import io
    import requests
    import psutil
    import uuid
    import subprocess
    import functools
    import math
    import types
    import pynput._util.win32
    import importlib.util
    import pywinauto
    import ctypes.wintypes
    from enum import Enum
    import traceback
    import re
    print("Importing gui...")
    import tkinter as tk
    from tkinter import messagebox
    import tkinter.ttk as ttk
    print("Importing STT architecture...")
    from huggingface_hub import hf_hub_download
except ImportError as e:
    print("An error occurred on startup!")
    print("-" * 30)
    print(f"{type(e).__name__}: \"{e}\"")
    print("-" * 30)
    print("This likely happened because of outdated dependencies.")
    print("To resolve, run setup.bat again!")
    print("-" * 30)
    try:
        messagebox.showerror("Imports failure", f"STT failed to load due to missing imports. This is likely caused by outdated dependencies. To resolve, run setup.bat again!\n\n{e}") #type: ignore
    except Exception as e:
        pass
    sys.exit(-1)

FINAL_FATAL_MESSAGE: str | None = None

def quit_normal():
    root.destroy()

def quit_with_errorbox(message):
    global FINAL_FATAL_MESSAGE
    FINAL_FATAL_MESSAGE = message
    root.destroy()

print("Finished importing libraries.")

T = typing.TypeVar('T')
U = typing.TypeVar('U')
V = typing.TypeVar('V')

DATA_PATH = "data/"
CONFIG_PATH = "config/"

CONFIG_FILENAME = CONFIG_PATH + "userconfig.toml"
CONFIG_BACKUP_FILENAME = CONFIG_PATH + "exampleconfig.toml"
FILTERCONFIG_FILENAME = CONFIG_PATH + "filters.toml"
FILTERCONFIG_BACKUP_FILENAME = CONFIG_PATH + "examplefilters.toml"

root = tk.Tk()
root.config(bg="white")
root.title("Speech To Text")
root.attributes("-topmost", True)
DEFAULT_WINDOW_WIDTH = 300
DEFAULT_WINDOW_HEIGHT = 100
root.minsize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
label_frame = tk.Frame(root, width = DEFAULT_WINDOW_WIDTH, height = DEFAULT_WINDOW_HEIGHT, bg="white")
label_frame.pack_propagate(False)
label_frame.pack(padx=0, pady=0)
label = tk.Label(label_frame, text="Pre-Init", bg="white", justify="center", font=("Arial", 12))
label.pack(expand=True)

_registered_tk_hooks: dict[str, list[typing.Callable]] = {}

def register_tkhook(name: str, func: typing.Callable):
    hooks = _registered_tk_hooks.get(name, None)
    if hooks is not None:
        hooks.append(func)
    else:
        hooks = [func]
        _registered_tk_hooks[name] = hooks
        def _internal_tkhook(event):
            for hook in hooks:
                hook(event)
        root.bind(name, _internal_tkhook)
        

def on_resize(event):
    if event.widget != root:
        return
    # This a tk hook, so it's on the main thread
    label_frame.config(width=event.width, height=max(100, label_frame.winfo_height()))

def thook_update_label_wrap(event):
    label.config(wraplength=event.width - 10)

label_frame.bind("<Configure>", thook_update_label_wrap)
register_tkhook("<Configure>", on_resize)

_skip_model_loading = False
thread_context = threading.local()
verbose = False

class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.DWORD),
        ("rcMonitor", ctypes.wintypes.RECT),
        ("rcWork", ctypes.wintypes.RECT),
        ("dwFlags", ctypes.wintypes.DWORD),
    ]

_warningbox_xvel = 0
_warningbox_yvel = 0

def showwarning_at(title: str, message: str, x: int | None, y: int | None) -> tuple[int, int]:
    global _warningbox_xvel
    global _warningbox_yvel
    unique_title = f"{title} : {uuid.uuid4()}"
    @main_thread
    def show_box():
        messagebox.showwarning(unique_title, message)
    spawn_thread(show_box)
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

def main_thread(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if threading.current_thread() is threading.main_thread():
            return func(*args, **kwargs)
        result = Box[typing.Any](None)
        error = Box[Exception | None](None)
        event = threading.Event()
        def sync():
            try:
                result.value = func(*args, **kwargs)
            except Exception as e:
                error.value = e
            finally:
                event.set()
        root.after(0, sync)
        event.wait()
        if error.has_value():
            raise error.value # type: ignore
        else:
            return result.value
    return wrapper

def main_thread_async(func):
    def wrapper(*args, **kwargs):
        if threading.current_thread() is threading.main_thread():
            func(*args, **kwargs)
            return
        def afterwrapper():
            func(*args, **kwargs)
        root.after(0, afterwrapper)
    return wrapper

def verbose_print(*args, **kwargs):
    if verbose:
        print(*args, **kwargs)

MBOX_POS: None | tuple[int, int] = None
LAST_MBOX_TIME = 0
MBOX_COUNT = 0
CAN_SHOW_MBOX = True
max_mbox_count = 20
max_mbox_reset_time = 1

def _mbox_time_elapsed():
    return time.time() - LAST_MBOX_TIME

def _set_mbox_time():
    global LAST_MBOX_TIME
    LAST_MBOX_TIME = time.time()

def _global_exception_handler(exception: Exception, context: str = "No context available."):
    try:
        filename = DATA_PATH + "logs/" + str(time.time()) + ".log"
        with io.open(DATA_PATH + "current.log", "w") as log:
            log.write(context)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with io.open(filename, "w") as log:
            log.write(context)
        message = f"{type(exception).__name__}:\n{exception}\nFull stacktrace available at \"current.log\" and \"{filename}\"."
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
                quit_with_errorbox(errorstr)
            _set_mbox_time()
        queue_deferred(show_mbox)
    except Exception as e:
        errorstr = f"FATAL: error encountered while processing {type(exception).__name__} ({exception}): {type(e).__name__}: {e}"
        print(errorstr)
        quit_with_errorbox(errorstr)

def _report_exception(e: Exception, context: str | None = None):
    root.after(0, _global_exception_handler, e, exception_to_filtered_traceback(e, context=context))

def _thread_ctx(func: typing.Callable, context: str, *args, **kwargs):
    try:
        global thread_context
        thread_context.value = context
        verbose_print("calling", func, "with", args)
        func(*args, **kwargs)
    except Exception as e:
        _report_exception(e, context)
        
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

def queue_deferred(func: typing.Callable, *args, **kwargs):
    with _deferred_queue_access:
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

def spawn_thread(func: typing.Callable, *args, **kwargs):
    context = ""
    try:
        context = thread_context.value
    except:
        pass
    stack = context + filtered_traceback()
    def wrapped_thread_ctx():
        _thread_ctx(func, stack, *args, **kwargs)
    thread = threading.Thread(target=wrapped_thread_ctx, daemon=True)
    thread.start()
    
spawn_thread(_deferred_queue_worker)

@main_thread
def on_force_geometry_change():
    root.update_idletasks()
    root.geometry(f"{root.winfo_reqwidth()}x{root.winfo_reqheight()}")

class Configurable():
    def __init__(self, obj):
        self.obj = obj
        self.m_dirtied_by = 0
    
    def dirtied_by(self):
        return self.m_dirtied_by
    
    @main_thread
    def config(self, **kwargs):
        self.obj.config(**kwargs) # type: ignore
        self.m_dirtied_by = time.time()
        return self.m_dirtied_by

    @main_thread
    def config_and_apply(self, **kwargs) -> typing.Callable[[typing.Callable[[typing.Any], None], float], None]:
        dirtied_by = self.config(**kwargs)
        def apply(callable, after):
            def callable_wrapper():
                time.sleep(after)
                if dirtied_by != self.dirtied_by():
                    return
                callable(self.obj)
            spawn_thread(callable_wrapper)
        return apply

@main_thread_async
def tk_config(obj, **kwargs):
    obj.config(**kwargs)

class ApplyableAction:
    def __init__(self, name: str, manager: "FilterManager"):
        self.manager = manager
        self.name = name
        self.enabled_by: dict[str, bool] = {}
        self.action: typing.Callable[[str], str] = ApplyableAction.DefaultAction

    @staticmethod
    def DefaultAction(input):
        raise RuntimeError(f"Attempted to call an ApplyableAction which does not have an action bound.\nGiven input string was: \"{input}\"")

    def __repr__(self):
        return "ApplyableAction." + self.name

    def on_enable(self, source: "Filter"):
        pass

    def on_disable(self):
        pass

    def transform(self, input: str) -> str:
        try:
            return self.action(input)
        except Exception as e:
            raise RuntimeError(f"An error occurred while transforming {input} in {self.name}: {str(e)}") from e

class TransformAction(ApplyableAction):
    def __init__(self, manager: "FilterManager", script_filename):
        super().__init__(os.path.splitext(os.path.basename(script_filename))[0] + "." + str(uuid.uuid4()), manager)
        spec = importlib.util.spec_from_file_location(os.path.splitext(os.path.basename(script_filename))[0], script_filename)
        if spec is None:
            raise ImportError(f"Could not load spec for {script_filename}")
        if spec.loader is None:
            raise ImportError(f"Could not find loader for {script_filename} {spec}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not hasattr(module, "process"):
            raise ImportError(f"Plugin {script_filename} does not have a process() function.")
        self.action = module.process
    
    def __repr__(self):
        return "TransformAction." + self.name

class InceptionAction(ApplyableAction):
    def __init__(self, manager: "FilterManager", filter_to_apply: str):
        super().__init__(filter_to_apply + ".applier."+ str(uuid.uuid4()), manager)
        self.action = InceptionAction.noop
        self.filter = filter_to_apply
    
    def on_enable(self, source: "Filter"):
        self.manager.enable_filter(self.filter, self.name)

    def on_disable(self):
        self.manager.disable_filter(self.filter, self.name)

    def __repr__(self):
        return "InceptionAction." + self.name
    
    @staticmethod
    def noop(input):
        return input

class SelfishAction(InceptionAction):
    def __init__(self, manager: "FilterManager", filter_to_apply: str):
        super().__init__(manager, filter_to_apply)
    
    def on_enable(self, source: "Filter"):
        self.manager.disable_filter(self.filter, self.name)
        self.manager.force_disable_filter(self.filter)
    
    def __repr__(self):
        return "SelfishAction." + self.name

class FilterActivation:
    def __init__(self, keybind: str, toggle: bool, suppresses: bool | None = None):
        self.keybind = keybind
        self.toggle = toggle
        self.suppresses = suppresses if suppresses is not None else False

class Filter:
    def __init__(self, name: str, title: str, manager: "FilterManager", actions: list[ApplyableAction], group: str, exclusive: bool, activated_by: FilterActivation | None, background: str|None="green", text_color: str|None="black"):
        self.background = "green" if background is None else background
        self.text_color = "black" if text_color is None else text_color
        self.name = name
        self.group = group
        self.exclusive = exclusive
        self.title = title
        self.manager = manager
        self.actions = actions
        self.activation_details: FilterActivation | None = activated_by
        self.enabled_by: dict[str, bool] = {}
        self.manager.register(self)
        self.display: "SizedLabel | None" = None

    def on_enable(self):
        to_delete = []
        for name, filter in self.manager.enabled_filters.items():
            if (filter is not self) and (filter.exclusive or self.exclusive) and filter.group == self.group:
                to_delete.append(name)
        for name in to_delete:
            self.manager.force_disable_filter(name)

    def on_disable(self):
        pass

    def __str__(self):
        return "Filter." + self.name

class SizedLabel:
    def __init__(self, parent, width, height, *args, **kwargs):
        self.frame = tk.Frame(parent, width=width, height=height, bg="white")
        self.label = tk.Label(self.frame, *args, **kwargs)
        self.label.pack(padx=0, pady=0, fill="both", expand=True)
    
    def destroy(self):
        self.frame.destroy()

    def grid(self, *args, **kwargs):
        self.frame.grid(*args, **kwargs)

class ExpandableColumnFlow:
    def __init__(self, parent, columns):
        self.lock = threading.Lock()
        self.parent_widget = parent
        self.columns = columns
        self.flat: list[SizedLabel] = []
        self._generate_grid()
        register_tkhook("<Configure>", self.root_resize_hook)

    def _generate_grid(self):
        self.grid = tk.Frame(self.parent_widget)
        for col in range(self.columns):
            self.grid.grid_columnconfigure(col, minsize=root.winfo_width() // self.columns)
        self.grid.pack()

    def root_resize_hook(self, event):
        if event.widget != root:
            return
        for col in range(self.columns):
            self.grid.grid_columnconfigure(col, minsize=event.width // self.columns)

    @main_thread
    def get_height(self):
        return math.ceil(len(self.flat) / self.columns) * 25

    @main_thread
    def delete_button(self, widget: SizedLabel):
        index: int | None = None
        for i, other_widget in enumerate(self.flat):
            if other_widget == widget:
                index = i
                break
        if index is None:
            raise RuntimeError("No such widget exists.")
        self.flat.pop(index).destroy()
        for i in range(index, len(self.flat)):
            to_move = self.flat[i]
            to_move.grid(row=math.floor(i / self.columns), column=i % self.columns)
        if not self.flat:
            # this is just the worst hack
            self.grid.destroy()
            self._generate_grid()
        root.update_idletasks()
        on_force_geometry_change()
        
    @main_thread
    def add_button(self) -> SizedLabel:
        widget = SizedLabel(self.grid, None, 25, anchor="center")
        row = math.floor(len(self.flat) / self.columns)
        column = len(self.flat) % self.columns
        widget.grid(row=row, column=column, sticky="nsew")
        widget.label.config(background="green")
        self.flat.append(widget)
        root.update_idletasks()
        on_force_geometry_change()
        return widget

DISPLAYED_MODIFIERS = ExpandableColumnFlow(root, 3)#

class FilterManager:
    def __init__(self, display: ExpandableColumnFlow):
        self.enabled_actions: dict[str, ApplyableAction] = {}
        self.registered_filters: dict[str, Filter] = {}
        self.enabled_filters: dict[str, Filter] = {}
        self.display = display

    def register(self, filter: Filter):
        if filter.name in self.registered_filters:
            print(self.registered_filters)
            raise RuntimeError(f"Attempted to register {filter.name} while {filter.name} is already registered.")
        self.registered_filters[filter.name] = filter

    def is_enabling(self, name: str, source: str):
        if not name in self.registered_filters:
            raise RuntimeError(f"Attempted to know whether filter {name} is activated while {name} does not exist.")
        filter = self.registered_filters[name]
        return source in filter.enabled_by

    def enable_filter(self, name: str, source: str):
        if not name in self.registered_filters:
            raise RuntimeError(f"Attempted to enable filter {name} while {name} does not exist.")
        filter = self.registered_filters[name]
        if len(filter.enabled_by) == 0:
            filter.on_enable()
            with self.display.lock:
                filter.display = self.display.add_button()
                tk_config(filter.display.label, text=filter.title, background=filter.background, foreground=filter.text_color)
            filter.enabled_by[source] = True
        self.enabled_filters[filter.name] = filter
        for action in filter.actions:
            self.enable_action(action, source=filter)

    def disable_filter(self, name: str, source: str):
        if not name in self.registered_filters:
            raise RuntimeError(f"Attempted to disable filter {name} while {name} does not exist.")
        filter = self.registered_filters[name]
        if len(filter.enabled_by) == 0:
            return
        filter.enabled_by.pop(source, None)
        if len(filter.enabled_by) > 0:
            return
        filter.on_disable()
        self.enabled_filters.pop(filter.name, None)
        if not (filter.display is None):
            with self.display.lock:
                self.display.delete_button(filter.display)
                filter.display = None
        for action in filter.actions:
            self.disable_action(action, source=filter)

    def enable_action(self, action: ApplyableAction, source: Filter):
        action.enabled_by[source.name] = True
        if action.name in self.enabled_actions:
            return
        self.enabled_actions[action.name] = action
        action.on_enable(source)
    
    def disable_action(self, action: ApplyableAction, source: Filter):
        action.enabled_by.pop(source.name, None)
        if len(action.enabled_by) == 0:
            self.enabled_actions.pop(action.name, None)
            action.on_disable()
    
    def force_disable_filter(self, name: str):
        filter = self.registered_filters[name]
        filter.enabled_by = {"FilterManager.force": True}
        self.disable_filter(name, "FilterManager.force")
        
    def force_disable_action(self, action: ApplyableAction):
        action.enabled_by.clear()
        self.enabled_actions.pop(action.name, None)
        action.on_disable()

    def transform_input(self, input: str) -> str:
        for action in self.enabled_actions.values():
            input = action.transform(input)
            if not isinstance(input, str):
                raise RuntimeError(f"Malformed plugin {action.name}: returned {type(input)} instead of str.")
        return input

audio = pyaudio.PyAudio()

path_to_model = ""
asr_model = None

class Box(typing.Generic[T]):
    def __init__(self, value: T):
        self.value: T = value

    def has_value(self):
        return self.value is not None

class MouseButton:
    def __init__(self, button: str):
        self.button = button
    
    def __repr__(self):
        return f"MouseButton({self.button})"

    def __str__(self):
        return f"MouseButton({self.button})"
    
    def __hash__(self) -> int:
        return self.button.__hash__()
    
    def __eq__(self, other) -> bool:
        return self.button == other.button

    def is_mouse(self):
        return True
    
    def is_keyboard(self):
        return False
    
class KeyButton:
    def __init__(self, scancode: int):
        self.scancode: int = scancode

    def __repr__(self):
        return "scancode: " + str(self.scancode)

    def __hash__(self) -> int:
        return self.scancode

    def __eq__(self, other) -> bool:
        return self.scancode == other.scancode
    
    def is_mouse(self):
        return False
    
    def is_keyboard(self):
        return True

class Pressable:
    def __init__(self, control: KeyButton | MouseButton):
        if isinstance(control, KeyButton):
            self.control = control
            return
        elif isinstance(control, MouseButton):
            self.control = control
            return
        raise RuntimeError(f"Attempted to create Pressable with a control of type {type(control).__name__}, expected {KeyButton.__name__} or {MouseButton.__name__}")

    def __repr__(self):
        return f"Pressable({self.control.__repr__()})"

    def __str__(self):
        return f"Pressable({self.control.__str__()})"

    @staticmethod
    def _mouse_button_from_str(val: str, custom_mappings: dict[str, str] = {"lmb": "left", "rmb": "right", "mmb": "middle"}) -> str:
        val = custom_mappings.get(val, val)
        getattr(pynput.mouse.Button, val)
        return val

    _special_name_to_scancode: dict[str, tuple[int, ...]] = {
        'numpad 0': (82,),
        'numpad 1': (79,),
        'numpad 2': (80,),
        'numpad 3': (81,),
        'numpad 4': (75,),
        'numpad 5': (76,),
        'numpad 6': (77,),
        'numpad 7': (71,),
        'numpad 8': (72,),
        'numpad 9': (73,),
    }

    @staticmethod
    def _str_to_scancode(val: str) -> tuple[int, ...]:
        val = val.strip()
        if val.startswith('<') and val.endswith('>'):
            try:
                return (int(val.removeprefix('<').removesuffix('>')),)
            except ValueError as e:
                raise RuntimeError(f"Invalid scancode {val}, expected number inside of angle brackets, got {val.removeprefix('<').removesuffix('>')}.") from e
        if val in Pressable._special_name_to_scancode:
            print(f"val \"{val}\"in pressable")
            scancodes = Pressable._special_name_to_scancode[val]
        else:
            scancodes = keyboard.key_to_scan_codes(val)
        translated = []
        for code in scancodes:
            translated.append(translate_special_scancode(val, code))
        return tuple(translated)

    @staticmethod
    def parse_hotkey(hotkey: str) -> "list[list[Pressable]]":
        # allows ctrl + p + x
        values = hotkey.split("+")
        pressables: list[list[Pressable]] = []
        had_unbound = False
        for value in values:
            try:
                if value.strip().lower() in ("unbound", "unset"):
                    print(f"Parsing hotkey {hotkey} found \"{value}\" which matches an unbinding")
                    had_unbound = True
                    continue
                if had_unbound:
                    print(f"Combination hotkey {hotkey} had an unbinding")
                    pressables.clear()
                    break
                codes = Pressable._str_to_scancode(value)
                aliases = []
                for scancode in codes:
                    aliases.append(Pressable(KeyButton(scancode)))
                pressables.append(aliases)
            except ValueError:
                try:
                    pressables.append([Pressable(MouseButton(Pressable._mouse_button_from_str(value.strip())))])
                except AttributeError as notmouse:
                    raise RuntimeError(f"Invalid key/mousebutton \"{value}\" in hotkey \"{hotkey}\"") from notmouse
        return pressables

    def __hash__(self) -> int:
        return self.control.__hash__()
    
    def __eq__(self, other) -> bool:
        return self.control == other.control

    def is_mouse(self):
        return self.control.is_mouse()
    
    def is_keyboard(self):
        return self.control.is_keyboard()

class ControlButton:
    def __init__(self, control: Pressable, action: typing.Callable, suppression_logic: typing.Callable[[], bool] | bool = False):
        self.control = control
        if isinstance(suppression_logic, bool):
            if suppression_logic:
                self.should_suppress = _literal_true
            else:
                self.should_suppress = _literal_false
        else:
            self.should_suppress = suppression_logic
        self._is_pressed = False
        self.actions = [action]
        self.release_actions: list[typing.Callable] = []
        self.lock = threading.Lock()

    def add_press(self, action: typing.Callable):
        self.actions.append(action)

    def add_release(self, action: typing.Callable):
        self.release_actions.append(action)

    def press(self):
        if not self._is_pressed:
            for action in self.actions:
                spawn_thread(action)
        with self.lock:
            self._is_pressed = True
    
    def release(self):
        if self._is_pressed:
            for release_action in self.release_actions:
                spawn_thread(release_action)
        with self.lock:
            self._is_pressed = False

    def __str__(self):
        return "ControlButton " + str(self.control)

    def is_key(self):
        return not self.is_mouse()

    def is_mouse(self):
        return self.control.is_mouse()

    def is_pressed(self):
        with self.lock:
            return self._is_pressed
        
class Control:
    def __init__(self, controlled_by: list[ControlButton], press: typing.Callable[[], None], release: typing.Callable[[], None]):
        self.controlled_by = controlled_by
        self.press = press
        self.release = release
        self.pressed = False
        self.pressed_by = 0
        self.press_lock = threading.RLock()
        def press_hook():
            with self.press_lock:
                self._check_press()
                self.pressed_by += 1
        def release_hook():
            with self.press_lock:
                self.pressed_by -= 1
                self._check_release()
        self.press_hook = press_hook
        self.release_hook = release_hook

    def _check_press(self):
        if self.pressed_by == 0:
            self.press()

    def _check_release(self):
        if self.pressed_by == 0:
            self.release()

    def is_pressed(self) -> bool:
        with self.press_lock:
            for control in self.controlled_by:
                if control.is_pressed():
                    return True
        return False
        
autosend = False
use_say = False
use_hwnd = False
hwnd_automation_id: int = 0
allow_version_checking = True
allow_cpu_asr = True
chat_delay = 0
chat_key = ""

def is_key(value: str) -> bool:
    special_keys = [k.name for k in pynput.keyboard.Key]
    return (value in special_keys) or (value in list(string.printable))

def is_mousebutton(value: str) -> bool:
    buttons = [k.name for k in pynput.mouse.Button]
    return value in buttons

def is_input(value: str) -> bool:
    return is_key(value) or is_mousebutton(value)

def fix_version_file():
    version = "0.0.0"
    if not os.path.exists("version.number"):
        with open("version.number", "w") as file:
            file.write(version)
        return
    with open("version.number", "r") as file:
        version = file.read(-1).strip()
    if bool(re.fullmatch(r'^\d+\.\d+\.\d+$', version)):
        # valid
        return
    spawn_thread(messagebox.showwarning, "STT Version File Error", message=f"An invalid version was detected inside of the version file, expected x.x.x, got \"{version}\"")
    os.remove("version.number")
    return fix_version_file()

def current_version():
    fix_version_file()
    version = "0.0.0"
    with open("version.number", "r") as file:
        version = file.read(-1).strip()
    return version

def synchronized_with(lock):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with lock:
                return func(*args, **kwargs)
        return wrapper
    return decorator

class Changelog:
    def __init__(self, version: str, name: str, headline: str, critical_updates: list[str] | None, date: str, categories: dict[str, list[str]]):
        self.name = name
        self.version = version
        self.date = date
        self.critical_updates = critical_updates
        self.headline = headline
        self.categories = categories
    
    @staticmethod
    @main_thread
    def show_logs(logs: list["Changelog"]):
        window = tk.Toplevel()
        window.title(f"Changelog")
        window.geometry(f"600x900+{window.winfo_screenwidth() // 2 - 600 // 2}+{window.winfo_screenheight() // 2 - 900 // 2}")
        text = tk.Text(window, wrap="word")
        text.pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(window, command=text.yview)
        scrollbar.pack(side="right", fill="y")
        text.config(yscrollcommand=scrollbar.set)
        text.tag_configure("header", font=("TkDefaultFont", 20, "bold"))
        text.tag_configure("bold", font=("TkDefaultFont", 15, "bold"))
        line = 1
        for log in logs:
            if line != 1:
                text.insert(f"{line}.0", f"{'-' * 15}\n")
                line = line + 1
            text.insert(f"{line}.0", f"Version: {log.version}\n", "header")
            line = line + 1
            text.insert(f"{line}.0", f"Date: {log.date}\n")
            line = line + 1
            text.insert(f"{line}.0", "Headline:\n", "header")
            line = line + 1
            text.insert(f"{line}.0", f"{log.headline}\n", "bold")
            line = line + 1
            if log.critical_updates is not None:
                text.insert(f"{line}.0", "Critical updates:\n", "bold")
                line = line + 1
                for update in log.critical_updates:
                    text.insert(f"{line}.0", f"  - {update}\n")
                    line = line + 1
            for name, bullets in log.categories.items():
                text.insert(f"{line}.0", f"{name}:\n", "bold")
                line = line + 1
                for bullet in bullets:
                    text.insert(f"{line}.0", f"  - {bullet}\n")
                    line = line + 1
        text.config(state="disabled")
        
    @staticmethod
    def parse(input: str, version: str) -> "Changelog":
        input = input.replace("\t", "  ").replace("\r\n", "\n").replace("\r", "\n")
        print(f"parsing changelog for version {version}")
        version_idx = input.find(f"Version: {version}")
        if version_idx == -1:
            raise RuntimeError(f"Changelog does not have {version} entry.")
        header_idx = input.find("---------------------------------------------------------------------------------------------------", version_idx)
        if header_idx == -1:
            header_idx = len(input)
        index = version_idx
        matches = re.findall(r" {2}(.*?)\:\n((?: {4}\-\s+.*(?:\n|$))+)", input[index:header_idx])
        categories: dict[str, list[str]] = {}
        for section_name, bullet_block in matches:
            categories[section_name] = list(re.findall(r" {4}\-\s+(.*)(?:\n|$)", bullet_block))
        name = ", ".join(typing.cast(list[str], categories.get("Name", [])))
        headline = ", ".join(typing.cast(list[str], categories.get("Headline", [])))
        categories.pop("Name", None)
        categories.pop("Headline", None)
        critical_updates = categories.pop("Critical", None)
        return Changelog(version=version, date=str(re.findall(r"Date: (.*?)\n", input[index:header_idx])[0]), name=name, headline=headline, critical_updates=critical_updates, categories=categories)

def show_changelogs_after(current: str):
    @main_thread
    def create_window() -> typing.Tuple[tk.Toplevel, tk.Text]:
        window = tk.Toplevel()
        window.title(f"Changelog")
        window.geometry(f"600x600+{window.winfo_screenwidth() // 2 - 600 // 2}+{window.winfo_screenheight() // 2 - 600 // 2}")
        status_label = tk.Label(window, text="Loading changelog...", justify="center", font=("Arial", 10))
        status_label.pack(pady=(20, 10))
        progress = ttk.Progressbar(window, mode="indeterminate", length=500)
        progress.pack(pady=10)
        progress.start(10)
        text_log = tk.Text(window, wrap="word")
        text_log.pack(fill="both", expand=True)
        text_log.config(state="disabled")
        return (window, text_log)
    window, text_log = create_window()
    @main_thread
    def dblprint(val: str):
        text_log.config(state="normal")
        text_log.insert(tk.END, val + "\n")
        text_log.see(tk.END)
        text_log.config(state="disabled")
        print(val)
    url = "https://api.github.com/repos/tonyhawq/STT/releases"
    dblprint(f"Getting releases from {url}...")
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    releases = response.json()
    logs = []
    for release in releases:
        dblprint(f"Scanning {release['tag_name']} for changelog...")
        version = release['tag_name']
        if not version_greater(version, current):
            continue
        dblprint(f"Getting assets...")
        for asset in release.get("assets", []):
            if asset["name"] == "changelog.txt":
                changelog_url = asset["browser_download_url"]
                dblprint(f"Got url for changelog at {changelog_url}, downloading...")
                try:
                    raw_log_response = requests.get(changelog_url)
                    raw_log_response.raise_for_status()
                    raw_log = raw_log_response.text
                    dblprint(f"Parsing {release['tag_name']}...")
                    logs.append(Changelog.parse(raw_log, version))
                except Exception as e:
                    dblprint(f"Encountered an exception: {e}")
    @main_thread
    def destroy_window():
        window.destroy()
    destroy_window()
    Changelog.show_logs(logs)

def show_version_info(text: str, changelog: Changelog, version: str):
    res = messagebox.askyesno("New Version Available", text, type=messagebox.YESNO) #type: ignore
    if res:
        show_changelogs_after(version)
        
def fetch_changelog() -> Changelog:
    url = "https://api.github.com/repos/tonyhawq/STT/releases/latest"
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    response = response.json()
    changelog_url = None
    release_version = response.get('tag_name', 'error')
    for asset in response.get("assets", []):
        if asset["name"] == "changelog.txt":
            changelog_url = asset["browser_download_url"]
            break
    if changelog_url is None:
        raise RuntimeError(f"No file with name changelog.txt found for release {release_version}")
    raw_log_response = requests.get(changelog_url, timeout=5)
    raw_log_response.raise_for_status()
    raw_log = raw_log_response.text
    print(raw_log)
    return Changelog.parse(raw_log, release_version)

def latest_version() -> str:
    url = "https://api.github.com/repos/tonyhawq/STT/releases/latest"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
    except:
        print("No internet connection.")
        return "0.0.0"
    if response.status_code != 200:
        messagebox.showwarning("STT Response Error", message=f"Could not fetch latest version from github, got {response.status_code}")
        return "0.0.0"
    latest = response.json()["tag_name"]
    return latest

def version_greater(v1: str, v2: str) -> bool:
    t1 = tuple(map(int, v1.split(".")))
    t2 = tuple(map(int, v2.split(".")))
    return t1 > t2

kblock = threading.RLock()

class VirtualNamedInput:
    def __init__(self, name: str):
        self.name = name
        self.is_pressed = False

    def aliases(self) -> list[Pressable]:
        return flatten_simple_hotkey(self.name)

    @synchronized_with(kblock)    
    def press(self):
        self.is_pressed = True
    
    @synchronized_with(kblock)
    def release(self):
        self.is_pressed = False

INPUTS_BY_PRESSABLE: dict[Pressable, list[VirtualNamedInput]] = {}
# Exists to replace keyboard.is_pressed()
# keyboard.is_pressed() does not update when a synthetic key is passed
# so would break often
# Now INPUTS_BY_PRESSABLE and INPUTS_BY_NAME are interlinked
# You can lookup a VirtualNamedInput (an input with a name and is_pressed state)
# By name (w, a, shift, alt)
# When a pressable that is associated with that key is pressed, it looks up what VirtualNamedInputs are actually associated with that key
# and presses/releases them
INPUTS_BY_NAME: dict[str, VirtualNamedInput] = {}
CONTROLS: dict[str, Control] = {}
CONTROLBUTTONS_BY_KEY: dict[Pressable, ControlButton] = {}

def populate_named_inputs():
    inputs_to_name = list(string.ascii_lowercase)
    inputs_to_name += ["menu", "shift", "alt", "ctrl", "space", "left", "right", "up", "down", "tab"]
    for name in inputs_to_name:
        virtual = VirtualNamedInput(name)
        for alias in virtual.aliases():
            INPUTS_BY_PRESSABLE.setdefault(alias, []).append(virtual)
        INPUTS_BY_NAME[name] = virtual

class ConfigError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

# Raised when the final object is not of expected type
class ConfigTypeError(ConfigError):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

# Raised when traversing the tree failed
class ConfigTraversalError(ConfigError):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class KeyCombinationControl:
    def __init__(self, bind: "list[list[Pressable]]", press: typing.Callable, release: typing.Callable, _suppress: bool = False):
        self.keys = bind
        self.press_action = press
        self.release_action = release
        self._currently_pressed: dict[int, None] = {}
        self._pressed_count = 0
        self._press_threshold = len(bind)
        self.suppression_logic: bool | typing.Callable[[], bool] = _suppress
        if _suppress:
            def should_suppress():
                return self._pressed_count == self._press_threshold
            self.suppression_logic = should_suppress

    def _check_press(self):
        if self._pressed_count == self._press_threshold:
            self.press_action()
    
    def _check_depress(self):
        if self._pressed_count == self._press_threshold:
            self.release_action()

    def to_callbacks(self):
        callbacks: list[tuple[list[Pressable], typing.Callable[[], None], typing.Callable[[], None]]] = []
        for i, key in enumerate(self.keys):
            def child_press(k=i):
                if k in self._currently_pressed:
                    return
                self._currently_pressed[k] = None
                self._pressed_count += 1
                self._check_press()
            def child_release(k=i):
                print("release")
                if self._currently_pressed.pop(k, True) is None:
                    self._check_depress()
                    self._pressed_count -= 1
            callbacks.append((key, child_press, child_release))
        return callbacks

def _literal_true():
    return True

def _literal_false():
    return False

def _set_simple_control(aliases: list[Pressable], name: str, action: typing.Callable[[], None], release: typing.Callable[[], None] | None = None, _suppress: bool | typing.Callable[[], bool] = False):
    if name in CONTROLS:
        raise RuntimeError(f"Attempted to create duplicate control \"{name}\", a control already exists with this name.")
    collected: list[ControlButton] = []
    def _void():
        return None
    control = Control(controlled_by=[], press=action, release=_void if release is None else release)
    for alias in aliases:
        if alias in CONTROLBUTTONS_BY_KEY:
            button = CONTROLBUTTONS_BY_KEY[alias]
            collected.append(button)
            button.add_press(control.press_hook)
            button.add_release(control.release_hook)
            # because suppression is always an OR operation
            # a literal true value will mean should_suppress always is true
            # and a literal false has no effect
            if isinstance(_suppress, bool):
                if _suppress:
                    button.should_suppress = _literal_true
            elif button.should_suppress is not _literal_true:
                if button.should_suppress is _literal_false:
                    button.should_suppress = _suppress
                else:
                    def supression_wrapper(func=_suppress, last_func=button.should_suppress):
                        return func() or last_func()
                    button.should_suppress = supression_wrapper
        else:
            button = ControlButton(alias, action=control.press_hook, suppression_logic=_suppress)
            button.add_release(control.release_hook)
            CONTROLBUTTONS_BY_KEY[alias] = button
            collected.append(button)
    control.controlled_by = collected
    CONTROLS[name] = control
    

def set_control(hotkey: str, name: str, action: typing.Callable, release: typing.Callable | None = None, _suppress: bool = False):
    buttons = Pressable.parse_hotkey(hotkey)
    print(f"making control with hotkey {buttons} and name {name}")
    if len(buttons) < 1:
        raise RuntimeError(f"Invalid hotkey \"{hotkey}\", it contains no values.")
    if len(buttons) == 1:
        _set_simple_control(buttons[0], name, action, release, _suppress=_suppress)
        return
    control = KeyCombinationControl(buttons, press=action, release=(lambda: ...) if release is None else release, _suppress=_suppress)
    callbacks = control.to_callbacks()
    for cb in callbacks:
        binds = cb[0]
        _set_simple_control(binds, f"{name}@{str(binds)}", cb[1], cb[2], _suppress=control.suppression_logic)

FILTERS: FilterManager = FilterManager(DISPLAYED_MODIFIERS)

say_sleep_ms = 0

CONFIGOBJ_METADATA: dict[int, list[str]] = {}

def get_cfgsrc(obj) -> list[str]:
    val = CONFIGOBJ_METADATA.get(id(obj))
    if val is None:
        CONFIGOBJ_METADATA[id(obj)] = []
    return CONFIGOBJ_METADATA[id(obj)]

def config_make_cfgsrc_ctx(obj, key: str) -> str:
    src = get_cfgsrc(obj).copy()
    src.append(key)
    for i, val in enumerate(src):
        src[i] = f"\"{val}\""
    return " -> ".join(src)

def config_has_key(cfgobj: dict, key: str) -> bool:
    return cfgobj.get(key) is not None

def config_get_string(cfgobj: dict, key: str) -> str:
    val = cfgobj.get(key)
    if val is None:
        raise ConfigError(f"Couldn't get key {config_make_cfgsrc_ctx(val, key)}")
    if type(val) is not str:
        raise ConfigTypeError(f"Expected {config_make_cfgsrc_ctx(val, key)} to be str, was {type(val).__name__}")
    get_cfgsrc(val).extend(get_cfgsrc(cfgobj))
    get_cfgsrc(val).append(key)
    return val

def config_get_bool(cfgobj: dict, key: str) -> bool:
    val = cfgobj.get(key)
    if val is None:
        raise ConfigError(f"Couldn't get key {config_make_cfgsrc_ctx(val, key)}")
    if type(val) is not bool:
        raise ConfigTypeError(f"Expected {config_make_cfgsrc_ctx(val, key)} to be bool, was {type(val).__name__}")
    get_cfgsrc(val).extend(get_cfgsrc(cfgobj))
    get_cfgsrc(val).append(key)
    return val

def config_get_number(cfgobj: dict, key: str) -> float:
    val = cfgobj.get(key)
    if val is None:
        raise ConfigError(f"Couldn't get key {config_make_cfgsrc_ctx(val, key)}")
    if type(val) is not int and type(val) is not float:
        raise ConfigTypeError(f"Expected {config_make_cfgsrc_ctx(val, key)} to be int or float, was {type(val).__name__}")
    get_cfgsrc(val).extend(get_cfgsrc(cfgobj))
    get_cfgsrc(val).append(key)
    return float(val)

def config_get_list(cfgobj: dict, key: str) -> list:
    val = cfgobj.get(key)
    if val is None:
        raise ConfigError(f"Couldn't get key {config_make_cfgsrc_ctx(val, key)}")
    if type(val) is not list:
        raise ConfigTypeError(f"Expected {config_make_cfgsrc_ctx(val, key)} to be a list, was {type(val).__name__}")
    get_cfgsrc(val).extend(get_cfgsrc(cfgobj))
    get_cfgsrc(val).append(key)
    return val

def config_get_dict(cfgobj: dict, key: str) -> dict:
    val = cfgobj.get(key)
    if val is None:
        raise ConfigError(f"Couldn't get key {config_make_cfgsrc_ctx(val, key)}")
    if type(val) is not dict:
        raise ConfigTypeError(f"Expected {config_make_cfgsrc_ctx(val, key)} to be a dict, was {type(val).__name__}")
    get_cfgsrc(val).extend(get_cfgsrc(cfgobj))
    get_cfgsrc(val).append(key)
    return val

def load_configdict_from_filename(filename: str, backup: str) -> dict:
    config: dict
    try:
        with io.open(filename, "rb") as config_file:
            config = tomllib.load(config_file)
    except IOError:
        with io.open(filename, "w") as config_file:
            try:
                with io.open(backup, "r") as backup_file:
                    config_file.write(backup_file.read())
            except IOError:
                quit_with_errorbox(f"FATAL: Couldn't load {filename} and couldn't load the backup file {backup}.")
        with io.open(filename, "rb") as config_file:
            config = tomllib.load(config_file)
    return config

def _load_filters_from_config():
    print(f"Loading filters from config file {FILTERCONFIG_FILENAME}")
    config = load_configdict_from_filename(FILTERCONFIG_FILENAME, FILTERCONFIG_BACKUP_FILENAME)
    for name, filter in config.items():
        if type(filter) is not dict:
            raise ConfigTypeError(f"Section {name} isn't a dictionary. Did you mean to write\n[{name}] ?")
        get_cfgsrc(filter).extend(get_cfgsrc(config))
        get_cfgsrc(filter).append(name)
        has_single = config_has_key(filter, "action")
        has_double = config_has_key(filter, "actions")
        if has_single and has_double:
            raise ConfigError(f"Attempted to create a filter with both an \"action\" and with \"actions\". Only define one of them in filter \"{name}\"")
        if not has_single and not has_double:
            raise ConfigError(f"Attempted to create a filter which lacked both an \"action\" and an \"actions\" field in filter \"{name}\"")
        title = config_get_string(filter, "title")
        parsed_actions: list[ApplyableAction] = []
        if has_single:
            parsed_actions.append(TransformAction(FILTERS, config_get_string(filter, "action")))
        elif has_double:
            actions = config_get_list(filter, "actions")
            for action_name in actions:
                if type(action_name) is not str:
                    raise ConfigTypeError(f"Action {action_name} is not a string; instead is {type(action_name).__name__}")
                action = config_get_dict(filter, action_name)
                typ = config_get_string(action, "type")
                if typ == "script":
                    filename = config_get_string(action, "script")
                    parsed_actions.append(TransformAction(FILTERS, filename))
                elif typ == "filter":
                    filter_to_apply = config_get_string(action, "name")
                    mode = None
                    if config_has_key(action, "mode"):
                        mode = config_get_string(action, "mode")
                    if mode is None or mode == "enable":
                        parsed_actions.append(InceptionAction(FILTERS, filter_to_apply))
                    elif mode == "disable":
                        parsed_actions.append(SelfishAction(FILTERS, filter_to_apply))
                    else:
                        raise ConfigError(f"Attempted to create an action of type \"{typ}\" with an invalid mode of \"{mode}\", expected \"enable\" or \"disable\" for action {config_make_cfgsrc_ctx(action, action_name)}")
                else:
                    raise ConfigError(f"Attempted to create an action of type \"{typ}\". Expected \"script\" or \"type\" for action {config_make_cfgsrc_ctx(action, action_name)}")
        activation = FilterActivation("unbound", True, True)
        if config_has_key(filter, "bind"):
            activation.keybind = config_get_string(filter, "bind")
        if config_has_key(filter, "toggle"):
            activation.toggle = config_get_bool(filter, "toggle")
        if config_has_key(filter, "suppress"):
            activation.suppresses = config_get_bool(filter, "suppress")
        group = "default"
        exclusive = False
        color = None
        text_color = None
        if config_has_key(filter, "group"):
            group = config_get_string(filter, "group")
        if config_has_key(filter, "exclusive"):
            exclusive = config_get_bool(filter, "exclusive")
        if config_has_key(filter, "color"):
            color = config_get_string(filter, "color")
        if config_has_key(filter, "text_color"):
            text_color = config_get_string(filter, "text_color")
        Filter(name, title, FILTERS, parsed_actions,
               group,
               exclusive,
               activation,
               background=color,
               text_color=text_color)

def load_settings_from_config():
    print(f"Loading from config file {CONFIG_FILENAME}")
    config = load_configdict_from_filename(CONFIG_FILENAME, CONFIG_BACKUP_FILENAME)
    print(config)
    output = config_get_dict(config, "output")
    say_settings = config_get_dict(output, "say_settings")
    chat_settings = config_get_dict(output, "chat_settings")
    hwnd_settings = config_get_dict(output, "hwnd_settings")
    input = config_get_dict(config, "input")
    meta = config_get_dict(config, "meta")

    global allow_version_checking
    allow_version_checking = config_get_bool(meta, "enable_version_checking")
    global allow_cpu_asr
    allow_cpu_asr = not config_get_bool(meta, "warn_on_cpu")
    suppress_activate = config_get_bool(input, "activate_globally_blocked")
    set_control(config_get_string(input, "activate"), "activate", on_activate_press_handler, release=on_activate_release_handler, _suppress=suppress_activate)
    set_control(config_get_string(input, "reject"), "reject", on_reject_press_handler, release=on_reject_release_handler)
    set_control(config_get_string(input, "radio_modifier"), "radio", on_radio_press_handler, release=on_radio_release_handler)
    default_blocked_keys = config_get_list(input, "blocked_keys")
    for key in default_blocked_keys:
        if type(key) is not str:
            raise ConfigTypeError(f"Expected blocked_keys to be a list of strings, got {type(key).__name__}")
    setup_default_blocked_keys(default_blocked_keys)
    global DEFAULT_WINDOW_WIDTH
    global DEFAULT_WINDOW_HEIGHT
    global _skip_model_loading
    _skip_model_loading = config_get_bool(meta, "skip_model_load") if config_has_key(meta, "skip_model_load") else False
    DEFAULT_WINDOW_WIDTH = int(config_get_number(meta, "window_width"))
    DEFAULT_WINDOW_HEIGHT = int(config_get_number(meta, "window_height"))
    @main_thread
    def resize_label_frame():
        label_frame.config(width=DEFAULT_WINDOW_WIDTH, height=DEFAULT_WINDOW_HEIGHT)
        root.minsize(width=DEFAULT_WINDOW_WIDTH, height=DEFAULT_WINDOW_HEIGHT)
        on_force_geometry_change()
    resize_label_frame()

    global path_to_model
    path_to_model = config_get_string(meta, "path_to_model")
    global autosend
    autosend = config_get_bool(input, "autosend")
    global use_say
    global use_hwnd
    global hwnd_automation_id
    output_method = config_get_string(output, "output_method")
    if output_method == "say":
        use_say = True
        use_hwnd = False
        global say_sleep_ms
        say_sleep_ms = config_get_number(say_settings, "delay_ms") / 1000
    elif output_method == "chat":
        use_say = False
        use_hwnd = False
        global chat_key
        global chat_delay
        chat_key = config_get_string(chat_settings, "chat_key")
        chat_delay = config_get_number(chat_settings, "chat_delay")
    elif output_method == "hwnd":
        use_say = False
        use_hwnd = True
        hwnd_automation_id = int(config_get_number(hwnd_settings, "automation_id"))
    else:
        raise ConfigError(f"Output method should be either \"say\" or \"chat\", was \"{output_method}\"")
    _load_filters_from_config()
    
background = Configurable(label_frame)
label_background = Configurable(label)

class State(Enum):
    READY = 1
    RECORDING = 2
    PROCESSING = 3
    ACCEPTING = 4

state = State.READY
STOP_RECORDING = False
CANCEL_PROCESS = False
RECORDING_START_TIME = time.time()
RECORDING_STREAM: pyaudio.Stream | None
RECORDING_FRAMES = []
STATUS_LOCK = threading.Lock()
TRANSCRIBED = ""
IS_RADIO = False
controller = pynput.keyboard.Controller()

def is_pressing_radio() -> bool:
    control = CONTROLS["radio"]
    return control.is_pressed()

def _finalize_process():
    verbose_print("Finalizing.")
    global state
    with STATUS_LOCK:
        tk_config(label_background, bg="white")
        global STOP_RECORDING
        global CANCEL_PROCESS
        state = State.READY
        if CANCEL_PROCESS:
            colorize("red", 1)
        STOP_RECORDING = False
        CANCEL_PROCESS = False
        if not (RECORDING_STREAM is None):
            RECORDING_STREAM.stop_stream()
            RECORDING_STREAM.close()
        tk_config(label, text="Waiting...")
    try:
        os.remove("output.wav")
    except:
        print("Exception while removing output file.")

def record():
    global state
    global STOP_RECORDING
    global RECORDING_STREAM
    while True:
        data = RECORDING_STREAM.read(512) # type: ignore
        RECORDING_FRAMES.append(data)
        if STOP_RECORDING:
            break
    if (time.time() - RECORDING_START_TIME < 0.2) or CANCEL_PROCESS:
        _finalize_process()
        return
    with STATUS_LOCK:
        RECORDING_STREAM.stop_stream() # type: ignore
        RECORDING_STREAM.close() # type: ignore
        RECORDING_STREAM = None
        file = wave.open("output.wav", "wb")
        file.setnchannels(1)
        file.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
        file.setframerate(16000)
        file.writeframes(b''.join(RECORDING_FRAMES))
        file.close()
        STOP_RECORDING = False
        state = State.PROCESSING
    global TRANSCRIBED
    tk_config(label, text="Transcribing...")
    TRANSCRIBED = str(asr_model.transcribe(["output.wav"])[0].text) # type: ignore
    if CANCEL_PROCESS:
        _finalize_process()
        return
    tk_config(label, text=TRANSCRIBED)
    with STATUS_LOCK:
        state = State.ACCEPTING
    if autosend:
        submit()

def begin_recording():
    global CANCEL_PROCESS
    CANCEL_PROCESS = False
    global state
    global STATUS_LOCK
    global RECORDING_STREAM
    global RECORDING_FRAMES
    global STOP_RECORDING
    global RECORDING_START_TIME
    global IS_RADIO
    if state != State.READY:
        return
    tk_config(label, text="Recording...")
    with STATUS_LOCK:
        IS_RADIO = False
        RECORDING_START_TIME = time.time()
        STOP_RECORDING = False
        state = State.RECORDING
        RECORDING_STREAM = audio.open(format=pyaudio.paInt16, rate=16000, channels=1, input=True, frames_per_buffer=512)
        RECORDING_FRAMES = []
    spawn_thread(record)

def end_recording():
    if state != State.RECORDING:
        return
    global STATUS_LOCK
    global STOP_RECORDING
    with STATUS_LOCK:
        STOP_RECORDING = True

@main_thread
def colorize(val: str, time: float):
    def _recolor(obj):
        obj.config(bg="white")
    background.config_and_apply(bg=val)(_recolor, time)

def submit_chat(transcript: str):
    pyperclip.copy(transcript)
    controller.press(chat_key)
    controller.release(chat_key)
    time.sleep(chat_delay)
    with controller.pressed(pynput.keyboard.Key.ctrl):
        controller.press('v')
        controller.release('v')
    time.sleep(0.1)
    controller.press(pynput.keyboard.Key.enter)
    controller.release(pynput.keyboard.Key.enter)
    time.sleep(0.1)

def submit_say(transcript: str):
    doublequote = '"'
    singlequote = "'"
    pyperclip.copy(f"Say \"{transcript.replace(doublequote, singlequote)}\"")
    press_and_release_key("tab")
    time.sleep(say_sleep_ms)
    press_key("ctrl")
    press_and_release_key("v")
    release_key("ctrl")
    press_and_release_key("enter")
    press_and_release_key("tab")
    time.sleep(say_sleep_ms)

WM_SETTEXT = 0x000C
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
VK_RETURN = 0x0D
WM_GETTEXT = 0x000D

_editboxtextbuf = ctypes.create_unicode_buffer(128)

def get_editbox_textbuf(hwnd) -> str:
    ctypes.windll.user32.SendMessageW(
        hwnd,
        WM_GETTEXT,
        len(_editboxtextbuf),
        _editboxtextbuf
    )
    return _editboxtextbuf.value

SHOULD_LOOK_FOR_AUTOMATION_HWND = True
FOUND_NEW_AUTOMATION_HWND = threading.Event()
class AutomationTextEdit:
    def __init__(self, textedit: pywinauto.application.WindowSpecification, hwnd: int, pid: int):
        self.textedit = textedit
        self.hwnd = hwnd
        self.pid = pid
        self.top_window_hwnd = pywinauto.Application(backend="uia").connect(process=self.pid).top_window().handle
AUTOMATION_TEXTEDIT: AutomationTextEdit | None = None

class ProcessNotFoundError(RuntimeError):
    pass

def _get_dreamseeker_pid() -> int:
    for proc in psutil.process_iter(["pid", "name"]):
        if proc.info["name"] and proc.info["name"].lower() == "dreamseeker.exe":
            return proc.info["pid"]
    raise ProcessNotFoundError("Couldn't find dreamseeker.exe")

def _find_dreamseeker_window(pid: int | None = None) -> pywinauto.WindowSpecification:
    if pid is None:
        print("Locating dreamseeker pid...")
        pid = _get_dreamseeker_pid()
    print(f"finding chat entry bar from automation_id {hwnd_automation_id}")
    return pywinauto.Application(backend="uia").connect(process=pid).top_window()

def _get_dreamseeker_editbox_hwnd():
    global AUTOMATION_TEXTEDIT
    pid = _get_dreamseeker_pid()
    tedit = _find_dreamseeker_window(pid).child_window(
        auto_id=str(hwnd_automation_id),
        control_type="Edit"
    )
    AUTOMATION_TEXTEDIT = AutomationTextEdit(tedit, tedit.handle, pid) # type: ignore

def _fallback_get_dreamseeker_editbox_hwnd():
    print("_fallback_get_dreamseeker_editbox_hwnd called")
    try:
        _fallback_get_dreamseeker_editbox_hwnd_raw_impl()
    except Exception as e:
        _global_exception_handler(e)
        pass

def _get_dreamseeker_all_editboxes(pid: int | None = None):
    if pid is None:
        pid = _get_dreamseeker_pid()
    return pywinauto.Application(backend="uia").connect(process=pid).top_window().descendants(control_type="Edit")

def set_config_hwnd_automation_id(auto_id: int):
    try:
        with open(CONFIG_FILENAME, "r", encoding="utf-8") as f:
            config = tomlkit.parse(f.read())

        config["output"]["hwnd_settings"]["automation_id"] = int(auto_id)

        with open(CONFIG_FILENAME, "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(config))
    except Exception as e:
        _global_exception_handler(e, "setting config file")

CURRENT_HIGHLIGHT: tk.Toplevel | None = None
RUN_HIGHLIGHTS = True

def highlight_autogui_elem(elem):
    global CURRENT_HIGHLIGHT
    if CURRENT_HIGHLIGHT is None:
        CURRENT_HIGHLIGHT = tk.Toplevel()
        CURRENT_HIGHLIGHT.overrideredirect(True)
        CURRENT_HIGHLIGHT.attributes("-topmost", True)
        CURRENT_HIGHLIGHT.attributes("-alpha", 0.1)
                
    rect = elem.rectangle()
    CURRENT_HIGHLIGHT.geometry(f"{rect.width()}x{rect.height()}+{rect.left}+{rect.top}")

def _tk_highlight_flasher_worker():
    alpha_state = False
    while RUN_HIGHLIGHTS:
        time.sleep(0.5)
        if CURRENT_HIGHLIGHT is None:
            continue
        alpha_state = not alpha_state
        if alpha_state:
            CURRENT_HIGHLIGHT.attributes("-alpha", 0.5)
        else:
            CURRENT_HIGHLIGHT.attributes("-alpha", 0.1)
    if CURRENT_HIGHLIGHT is not None:
        CURRENT_HIGHLIGHT.destroy()

def stop_current_highlight():
    global CURRENT_HIGHLIGHT
    if CURRENT_HIGHLIGHT is None:
        return
    CURRENT_HIGHLIGHT.destroy()
    CURRENT_HIGHLIGHT = None

def stop_all_highlights():
    global RUN_HIGHLIGHTS
    RUN_HIGHLIGHTS = False

spawn_thread(_tk_highlight_flasher_worker)

def ask_and_change_automation_id(auto_id: int):
    def worker():
        if messagebox.askyesno("STT Change config?", "Would you like to set this chat box as your default?"):
            set_config_hwnd_automation_id(auto_id)
    spawn_thread(worker)

def ask_for_auto_chatbox():
    bar = ShittyLoadingBar("Locating chat box", "Scanning dreamseeker for available edit boxes...", lambda b: ...)
    pid = _get_dreamseeker_pid()
    edits = _get_dreamseeker_all_editboxes(pid)
    if len(edits) == 1:
        edit_obj = edits[0]
        highlight_autogui_elem(edit_obj)
        bar.end()
        if messagebox.askyesno("Autodetected chat box", "Is this the correct chat box?"):
            stop_current_highlight()
            FOUND_NEW_AUTOMATION_HWND.set()
            global AUTOMATION_TEXTEDIT
            AUTOMATION_TEXTEDIT = AutomationTextEdit(edit_obj, edit_obj.handle, pid)
            ask_and_change_automation_id(edit_obj.automation_id())
            return
        stop_current_highlight()
    else:
        bar.end()

class ShittyLoadingBar:
    def __init__(self, title: str, text: str, destroy_callback: typing.Callable[["ShittyLoadingBar"], typing.Any], w: int | None = None, h: int | None = None):
        self.window = tk.Toplevel()
        self.window.title(title)
        if w is None:
            w = 450
        if h is None:
            h = 150
        self.window.geometry(f"{w}x{h}")
        self.window.resizable(True, True)

        def _this_destroy_callback(obj = self):
            destroy_callback(obj)
        
        self.window.protocol("WM_DELETE_WINDOW", _this_destroy_callback)
        status_label = tk.Label(self.window, text=text, justify="center", font=("Arial", 10))
        status_label.pack(pady=(20, 10))
        progress = ttk.Progressbar(self.window, mode="indeterminate", length=350)
        progress.pack(pady=10)
        progress.start(10)

    def end(self):
        self.window.destroy()

def _fallback_get_dreamseeker_editbox_hwnd_raw_impl() -> bool:
    if not messagebox.askyesno("Can't find chat bar", "Can't find the SS13 chat bar. Would you like to pick a new chat bar?"):
        print("user denied finding a new chatbox")
        return False
    global SHOULD_LOOK_FOR_AUTOMATION_HWND
    SHOULD_LOOK_FOR_AUTOMATION_HWND = False
    
    try:
        ask_for_auto_chatbox()
    except Exception:
        stop_current_highlight()
    if FOUND_NEW_AUTOMATION_HWND.is_set():
        return False
    is_window_open = True
    window = tk.Toplevel()
    window_close_event = threading.Event()
    def window_close_hook():
        global SHOULD_LOOK_FOR_AUTOMATION_HWND
        nonlocal is_window_open
        is_window_open = False
        window.destroy()
        window_close_event.set()
        if not FOUND_NEW_AUTOMATION_HWND.is_set():
            SHOULD_LOOK_FOR_AUTOMATION_HWND = True
            FOUND_NEW_AUTOMATION_HWND.set()
    window.protocol("WM_DELETE_WINDOW", window_close_hook)
    window.title("STT Chat Bar Selector")
    window.attributes("-topmost", True)
    window.geometry("700x500")
    header = tk.Frame(window)
    header.pack(fill="x", padx=8, pady=6)

    progress = ttk.Progressbar(window, mode="indeterminate")
    progress.pack(fill="x", padx=8, pady=(0, 6))
    progress.pack_forget()  # hidden initially
    
    is_refreshing = False

    rows = []

    def rebuild_with_edits(edits: list):
        for i, edit in enumerate(edits):
            row = tk.Frame(scroll_frame, bd=1, relief="solid")
            row.pack(fill="x", pady=2)
            
            name_label = tk.Label(row, text=f"ID {edit.automation_id()}", anchor="w")
            name_label.pack(side="left", fill="x", expand=True, padx=6)

            def _highlight_wrap(edit_obj=edit):
                try:
                    highlight_autogui_elem(edit_obj)
                except Exception as e:
                    print(f"Encountered exception while highlighting edit obj: {e}")
                    window.after(0, refresh)

            def select(edit_obj):
                auto_id = int(edit_obj.automation_id())
                if hwnd_automation_id != auto_id:
                    ask_and_change_automation_id(auto_id)
                FOUND_NEW_AUTOMATION_HWND.set()
                global AUTOMATION_TEXTEDIT
                AUTOMATION_TEXTEDIT = AutomationTextEdit(edit_obj, edit_obj.handle, _get_dreamseeker_pid())
                window_close_hook()

            def _select_wrap(edit_obj=edit):
                try:
                    select(edit_obj)
                except Exception as e:
                    print(f"Encountered exception while selecting edit obj: {e}")
                    window.after(0, refresh)
            
            def copy_id(edit_obj=edit):
                try:
                    pyperclip.copy(str(edit_obj.automation_id()))
                except Exception as e:
                    print(f"Encountered exception while copying id of edit obj: {e}")
                    window.after(0, refresh)
            
            tk.Button(row, text="Highlight", command=_highlight_wrap).pack(side="right", padx=4)
            tk.Button(row, text="Copy ID", command=copy_id).pack(side="right", padx=4)
            tk.Button(row, text="Select", command=_select_wrap).pack(side="right", padx=4)

            rows.append(row)

    def show_progressbar():
        progress.pack(fill="x", padx=8, pady=(0, 6))
        progress.start(10)
    
    def hide_progressbar():
        progress.stop()
        progress.pack_forget()

    def refresh():
        nonlocal is_refreshing
        nonlocal rows
        if is_refreshing:
            return
        is_refreshing = True
        for w in rows:
            w.destroy()
        rows.clear()
        def get_editboxes():
            try:
                edits = _get_dreamseeker_all_editboxes()
                window.after(0, hide_progressbar)
                window.after(0, rebuild_with_edits, edits)
            except ProcessNotFoundError as e:
                messagebox.showwarning("STT Couldn't refresh", "Couldn't find dreamseeker.exe. Is SS13 running?")
                window.after(0, hide_progressbar)    
            except Exception as e:
                messagebox.showwarning("STT Couldn't refresh", f"Encountered an exception while trying to refresh available text inputs: {e}")
                window.after(0, hide_progressbar)
            finally:
                nonlocal is_refreshing
                is_refreshing = False
        show_progressbar()
        spawn_thread(get_editboxes)

    tk.Label(header, text="Available text inputs:", font=("Segoe UI", 10, "bold")).pack(side="left")
    tk.Button(header, text="Refresh", command=refresh).pack(side="right")
    container = tk.Frame(window)
    container.pack(fill="both", expand=True, padx=8, pady=6)

    canvas = tk.Canvas(container, highlightthickness=0)
    scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
    scroll_frame = tk.Frame(canvas)
    scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    refresh()
    return False

class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("hwndActive", ctypes.wintypes.HWND),
        ("hwndFocus", ctypes.wintypes.HWND),
        ("hwndCapture", ctypes.wintypes.HWND),
        ("hwndMenuOwner", ctypes.wintypes.HWND),
        ("hwndMoveSize", ctypes.wintypes.HWND),
        ("hwndCaret", ctypes.wintypes.HWND),
        ("rcCaret", ctypes.wintypes.RECT),
    ]

def attach_and_focus(hwnd: ctypes.wintypes.HWND):
    current_tid = ctypes.windll.kernel32.GetCurrentThreadId()
    target_tid = ctypes.windll.user32.GetWindowThreadProcessId(
        hwnd,
        None
    )
    ctypes.windll.user32.AttachThreadInput(
        current_tid,
        target_tid,
        True
    )
    ctypes.windll.user32.SetFocus(hwnd)
    ctypes.windll.user32.AttachThreadInput(
        current_tid,
        target_tid,
        False
    )

def anyashex(val) -> str:
    try:
        return hex(int(str(val)))
    except Exception as e:
        return str(e)

def submit_automation(transcript: str):
    if AUTOMATION_TEXTEDIT is None:
        raise RuntimeError("Attempted to call submit_automation while AUTOMATION_TEXTEDIT is None.")
    doublequote = '"'
    singlequote = "'"
    madestr = f"Say \"{transcript.replace(doublequote, singlequote)}\""
    ctypes.windll.user32.SendMessageW(
        AUTOMATION_TEXTEDIT.hwnd,
        WM_SETTEXT,
        0,
        madestr
    )
    parent: ctypes.wintypes.HWND = ctypes.windll.user32.GetParent(AUTOMATION_TEXTEDIT.hwnd)
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(info)
    ctypes.windll.user32.GetGUIThreadInfo(
        0,  # foreground thread
        ctypes.byref(info)
    )
    hwnd_to_focus = info.hwndFocus
    if hwnd_to_focus == AUTOMATION_TEXTEDIT.hwnd:
        print(f"Foreground window was {anyashex(hwnd_to_focus)} which is the chat box. Switching focus to dreamseeker.exe...")
        hwnd_to_focus = typing.cast(ctypes.wintypes.HWND, AUTOMATION_TEXTEDIT.top_window_hwnd)
    print(f"Attaching to {anyashex(parent)} : window to refocus is {anyashex(hwnd_to_focus)}")
    attach_and_focus(parent)
    ctypes.windll.user32.PostMessageW(parent, WM_KEYDOWN, VK_RETURN, 0)
    ctypes.windll.user32.PostMessageW(parent, WM_KEYUP, VK_RETURN, 0)
    start = time.monotonic_ns()
    interval = 1 / 30 * 1000 * 1000 * 1000 # 1 frame at 30fps
    while len(get_editbox_textbuf(AUTOMATION_TEXTEDIT.hwnd)) > 0:
        if time.monotonic_ns() - start > interval:
            print(f"Submission couldn't complete within one 30fps frame {transcript}")
            if ctypes.windll.user32.GetFocus() != parent:
                print("Submission unfocused parent")
                attach_and_focus(parent)
            ctypes.windll.user32.PostMessageW(parent, WM_KEYDOWN, VK_RETURN, 0)
            ctypes.windll.user32.PostMessageW(parent, WM_KEYUP, VK_RETURN, 0)
            start = time.monotonic_ns()
        continue
    attach_and_focus(hwnd_to_focus)

class ModifyableVirtualNamedInput(VirtualNamedInput):
    def __init__(self, name: str):
        super().__init__(name)
        self.was_modified = False
    
    def __repr__(self):
        return f"ModifyableVirtualNamedInput({self.name} was modified: {self.was_modified} press state: {self.is_pressed})"

    def press(self):
        super().press()
        self.was_modified = True
    
    def release(self):
        super().release()
        self.was_modified = True
    
# Currently blocked keys. Usually empty.
BLOCKED_KEYS: dict[Pressable, ModifyableVirtualNamedInput] = {}
# Default blocked keys. Should not modify. Filled in setup_default_blocked_keys()
DEFAULT_BLOCKED_KEYS: dict[Pressable, ModifyableVirtualNamedInput] = {}
# a dict of pressable -> MVNI. When a pressable is touched it touches the MVNI. MVNIs are shared between pressables, so keys with aliases (ctrl -> left control, right control)
# are handled correctly.
BLOCKED_KEYS_PRESS_RECORD: dict[Pressable, ModifyableVirtualNamedInput] = {}
# The actual list of MVNIs. Has no duplicates.
BLOCKED_KEYS_MASTERLIST: list[ModifyableVirtualNamedInput] = []

def flatten_simple_hotkey(hotkey) -> list[Pressable]:
    parsed = Pressable.parse_hotkey(hotkey)
    if len(parsed) != 1:
        raise RuntimeError(f"Attempted to flatten hotkey which was either a combination or had no values, len(parsed) was {len(parsed)}")
    added: set[Pressable] = set()
    for alias in parsed[0]:
        added.add(alias)
    return list(added)

def setup_default_blocked_keys(blockable_keys: list[str]):
    print(f"Setting up default_blocked_keys with {blockable_keys}")
    for key in blockable_keys:
        print(f"  blocking {key}")
        name = ModifyableVirtualNamedInput(key)
        aliases = flatten_simple_hotkey(key)
        for alias in aliases:
            DEFAULT_BLOCKED_KEYS[alias] = name
            print(f"  Adding {alias} with name {name.name} to blocked binds when in gameplay")
    print(f"Default blocked keys is: ")
    for key, value in DEFAULT_BLOCKED_KEYS.items():
        print(f"  {key}: {value}")

def must_recover(allowed_exceptions: tuple[typing.Type[BaseException]] = tuple([])):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except allowed_exceptions:
                raise
            except Exception as e:
                try:
                    _report_exception(e, context=thread_context.value)
                except:
                    _report_exception(e, "No context available for exception.")
        return wrapper
    return decorator

@synchronized_with(kblock)
def is_pressed(key: str):
    return INPUTS_BY_NAME[key].is_pressed

@synchronized_with(kblock)
def _perform_keyboard_action(action: typing.Callable, *args, **kwargs):
    action(*args, **kwargs)

def press_key(key: str):
    _perform_keyboard_action(keyboard.send, key, True, False)

def press_and_release_key(key: str):
    _perform_keyboard_action(keyboard.send, key, True, True)

def release_key(key: str):
    _perform_keyboard_action(keyboard.send, key, False, True)

def block_problematic_inputs():
    print("Blocking input...")
    with kblock:
        global BLOCKED_KEYS_MASTERLIST
        BLOCKED_KEYS_MASTERLIST = []
        global BLOCKED_KEYS
        global BLOCKED_KEYS_PRESS_RECORD
        BLOCKED_KEYS = DEFAULT_BLOCKED_KEYS
        BLOCKED_KEYS_PRESS_RECORD = {}
        for source, key in BLOCKED_KEYS.items():
            try:
                pressed = ModifyableVirtualNamedInput(key.name)
                BLOCKED_KEYS_MASTERLIST.append(pressed)
                if source.is_keyboard() and is_pressed(key.name):
                    print(f" {key.name} is_pressed")
                    pressed.press()
                    # fuck it special case
                    if key.name == "alt":
                        release_key("alt")
                parsed = flatten_simple_hotkey(key.name)
                for pressable in parsed:
                    BLOCKED_KEYS_PRESS_RECORD[pressable] = pressed
            except Exception as e:
                quit_with_errorbox(f"FATAL: couldn't block the key \"{key.name}\"\nTry removing it from the blocked keys in userconfig.toml\n({e})")


def unblock_problematic_inputs():
    print("Unblocking input...")
    masterlist = []
    with kblock:
        global BLOCKED_KEYS
        global BLOCKED_KEYS_MASTERLIST
        global BLOCKED_KEYS_PRESS_RECORD
        BLOCKED_KEYS = {}
        masterlist = BLOCKED_KEYS_MASTERLIST
        BLOCKED_KEYS_PRESS_RECORD = {}
        BLOCKED_KEYS_MASTERLIST = []
        for name in masterlist:
            try:
                if name.was_modified:
                    print(f"- {name} was modified")
                    if name.is_pressed:
                        press_key(name.name)
                    else:
                        release_key(name.name)
            except Exception as e:
                quit_with_errorbox(f"FATAL: couldn't unblock the key \"{name}\"\nTry removing it from the blocked keys in userconfig.toml\n({e})")
                    
def submit():
    global state
    if state != State.ACCEPTING:
        raise RuntimeError()
    global TRANSCRIBED
    with STATUS_LOCK:
        transcript = TRANSCRIBED
    _finalize_process()
    tk_config(label, text=transcript)
    print("--- Submitting transcript")
    colorize("green", 1)
    block_problematic_inputs()
    success = threading.Event()
    def perform_submission():
        nonlocal transcript
        global IS_RADIO
        try:
            radio = IS_RADIO
            if radio:
                label_background.config_and_apply(bg="light blue")(lambda obj: obj.config(bg="white"), 1)
                transcript = "; " + transcript
            if use_say:
                submit_say(transcript)
            elif use_hwnd:
                submit_automation(transcript)
            else:
                submit_chat(transcript)
        except:
            raise
        finally:
            unblock_problematic_inputs()
            IS_RADIO = False
            set_radio_colors()
        success.set()
    spawn_thread(perform_submission)
    def wait_and_unblock():
        time.sleep(5)
        if success.is_set():
            return
        unblock_problematic_inputs()
        extramessage = ""
        if use_hwnd:
            extramessage = "\nUsing the HWND output system WILL NOT WORK if you press one of the chat bar buttons!\nMake sure you don't have Say, Whisper, Me, or OOC pressed or this WILL happen!"
        messagebox.showwarning("Excessive output delay!", f"Sumbitting the transcript took longer than 5 seconds, aborting.{extramessage}")
    spawn_thread(wait_and_unblock)

def reject():
    global state
    if state == State.READY:
        return
    global STOP_RECORDING
    global CANCEL_PROCESS
    if state == State.RECORDING:
        with STATUS_LOCK:
            STOP_RECORDING = True
            CANCEL_PROCESS = True
    elif state == State.ACCEPTING:
        _finalize_process()
        colorize("red", 1)
    elif state == State.PROCESSING:
        with STATUS_LOCK:
            CANCEL_PROCESS = True
    else:
        pass

def on_activate_press_handler():
    with STATUS_LOCK:
        pass
    if state == State.READY:
        print("Activate press handler beginning recording")
        begin_recording()
        if is_pressing_radio():
            global IS_RADIO
            IS_RADIO = True
        set_radio_colors()
        return
    if state == State.ACCEPTING:
        print("Activate press handler accepting")
        press = False
        start_time = time.time()
        while time.time() < (start_time + 0.5):
            if not CONTROLS["activate"].is_pressed():
                print("Released within 0.5 seconds")
                press = True
                break
            time.sleep(0.01)
        if press:
            print("Pressed, submitting")
            submit()
            return
        print("Rejecting")
        reject()
        begin_recording()
        return

def on_activate_release_handler():
    if state == State.RECORDING:
        end_recording()

def on_reject_press_handler():
    reject()

def on_reject_release_handler():
    pass

@main_thread
def set_radio_colors():
    if IS_RADIO:
        label_background.config(bg="light blue")
    else:
        label_background.config(bg="white")

was_radio_pressed = False

def on_radio_press_handler():
    global was_radio_pressed
    if was_radio_pressed:
        return
    was_radio_pressed = True
    with STATUS_LOCK:
        verbose_print("radio press")
        if state == State.READY:
            verbose_print("Could not change IS_RADIO state")
            return
        global IS_RADIO
        IS_RADIO = not IS_RADIO
        set_radio_colors()

def on_radio_release_handler():
    global was_radio_pressed
    was_radio_pressed = False

_glob_mouse_listener: pynput.mouse.Listener = None # type: ignore

@must_recover((pynput._util.win32.SystemHook.SuppressException,))
def on_click(x: int, y: int, button: pynput.mouse.Button, pressed: bool, dummy):
    bind = Pressable(MouseButton(button.name))
    allow_through = True
    with kblock:
        if bind in BLOCKED_KEYS:
            allow_through = False
    if bind in CONTROLBUTTONS_BY_KEY:
        control = CONTROLBUTTONS_BY_KEY[bind]
        if control.is_mouse():
            control.press() if pressed else control.release()
            if control.should_suppress():
                allow_through = False
    if not allow_through:
        _glob_mouse_listener.suppress_event() # type: ignore

_special_scancode_map: dict[int, dict[str, int]] = {
    75: {"left": 75, "4": 80081350, "numpad 4": 80081350},
    77: {"right": 77, "6": 80081351, "numpad 6": 80081351},
    72: {"up": 72, "8": 80081352, "numpad 8": 80081352},
    80: {"down": 80, "2": 80081353, "numpad 2": 80081353},
    71: {"home": 71, "7": 80081354, "numpad 7": 80081354},
    79: {"end": 79, "1": 80081355, "numpad 1": 80081355},
    81: {"page down": 75, "3": 80081356, "numpad 3": 80081356},
    73: {"page up": 73, "9": 80081357, "numpad 9": 80081357},
}

def translate_special_scancode(name: str, scancode: int) -> int:
    mapped = _special_scancode_map.get(scancode, None)
    if mapped is None:
        return scancode
    specialmapped = mapped.get(name, None)
    if specialmapped is None:
        return scancode
    return specialmapped

@must_recover()
@synchronized_with(kblock)
def on_key(event: keyboard.KeyboardEvent) -> bool:
    if event.name is not None:
        bind = Pressable(KeyButton(translate_special_scancode(event.name, event.scan_code)))
    else:
        bind = Pressable(KeyButton(event.scan_code))
    if bind in INPUTS_BY_PRESSABLE:
        if event.event_type == "down":
            for virtual in INPUTS_BY_PRESSABLE[bind]:
                virtual.press()
        else:
            for virtual in INPUTS_BY_PRESSABLE[bind]:
                virtual.release()
    allow_through = True
    if bind in BLOCKED_KEYS:
        allow_through = False
        if event.event_type == "down":
            BLOCKED_KEYS_PRESS_RECORD[bind].press()
            print(f" BKPR pressing {bind}")
        else:
            BLOCKED_KEYS_PRESS_RECORD[bind].release()
            print(f" BKPR releasing {bind}")
    if bind in CONTROLBUTTONS_BY_KEY:
        control = CONTROLBUTTONS_BY_KEY[bind]
        if control.is_key():
            control.press() if event.event_type == "down" else control.release()
            if control.should_suppress():
                return False
    return allow_through

def mouse_listener():
    global _glob_mouse_listener
    with pynput.mouse.Listener(on_click=on_click) as _glob_mouse_listener: # type: ignore
        _glob_mouse_listener.join()

def keyboard_listener():
    keyboard.hook(on_key, suppress=True)
    
class ObjectWithTextAttributeWhichIsAString:
    def __init__(self, val: str):
        self.text = val

class FakeASRModel:
    def __init__(self):
        self._transcription_index = 0

    def transcribe(self, args: list[str]) -> tuple[ObjectWithTextAttributeWhichIsAString]:
        self._transcription_index += 1
        return (ObjectWithTextAttributeWhichIsAString(f"Skipped model loading msg({self._transcription_index})"),)

def _lazy_get_dreamseeker_hwnd():
    if use_hwnd:
        _get_dreamseeker_editbox_hwnd()

def skip_model_load(loading_text: Box[str], final: Box[bool]):
    _load_model_get_hwnd(loading_text)
    global asr_model
    asr_model = FakeASRModel()
    final.value = True

EARLY_GIVEUP_INIT = False

@main_thread
def _download_pytorch_cuda():
    tk_config(label, text="Waiting for PyTorch version to be selected...")
    window = tk.Toplevel()
    def window_close_hook():
        window.destroy()
        quit_normal()
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
        tk_config(install_button, state="disabled")
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
                tk_config(label, text="Downloading PyTorch...")
                if process.stdout is None:
                    raise RuntimeError("While running pytorch installer, stdout was None.")
                for line in process.stdout:
                    write_log(line.rstrip())
                code = process.wait()
                if code == 0:
                    @main_thread
                    def finished():
                        messagebox.showinfo("Success", "PyTorch installer completed.")
                        quit_normal()
                    finished()
                else:
                    @main_thread
                    def finished():
                        messagebox.showinfo("Failed", f"PyTorch installer failed with code {code}!\nIf you want to install PyTorch yourself, run the command in the log.\nYou can also try googling PyTorch CUDA install!")
                        quit_normal()
            except Exception as e:
                @main_thread_async
                def errbox():
                    messagebox.showwarning("An error occurred", f"An error occurred while trying to install CUDA: {e}")
                errbox()
        spawn_thread(worker)
                 
    @main_thread
    def write_log(text: str):
        log.insert(tk.END, text + "\n")
        log.see(tk.END)

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
        tk_config(install_button, state="disabled")
    finally:
        write_log(f"PyTorch install URL:")
        write_log(f"  {suggested_cuda_URL()}")

def _load_model_get_hwnd(loading_text: Box[str]):
    loading_text.value = "Locating dreamseeker.exe"
    hwnd_ok = True
    hwnd_bad_reason: pywinauto.ElementNotFoundError | ProcessNotFoundError | None = None 
    try:
        print("lazy locaing dreamseeker.exe")
        _lazy_get_dreamseeker_hwnd()
    except pywinauto.ElementNotFoundError as e:
        hwnd_ok = False
        hwnd_bad_reason = e
    except ProcessNotFoundError as e:
        hwnd_ok = False
        hwnd_bad_reason = e
    if not hwnd_ok:
        if type(hwnd_bad_reason) is ProcessNotFoundError:
            loading_text.value = "Waiting for dreamseeker.exe..."
            while True:
                time.sleep(1)
                try:
                    _get_dreamseeker_pid()
                except ProcessNotFoundError:
                    continue
                break
        print("Couldn't locate dreamseeker.exe and associated chat box")
        should_fallback = False
        fallback_tried = False
        start = time.time()
        while True:
            if not should_fallback:
                try:
                    if time.time() - start > 5:
                        wind = _find_dreamseeker_window()
                        if wind.texts()[0] != "BYOND: Your Game Is Starting":
                            should_fallback = True
                            start = time.time()
                except Exception:
                    pass
            elif should_fallback and not fallback_tried and time.time() - start > 5:
                spawn_thread(_fallback_get_dreamseeker_editbox_hwnd)
                fallback_tried = True
            if SHOULD_LOOK_FOR_AUTOMATION_HWND:
                try:
                    loading_text.value += " (locating)"
                    _lazy_get_dreamseeker_hwnd()
                    break
                except pywinauto.ElementNotFoundError as e:
                    loading_text.value = "Looking for the chat box..."
                    time.sleep(1)
                except ProcessNotFoundError as e:
                    loading_text.value = "Waiting for SS13 to be launched..."
                    time.sleep(1)
            else:
                loading_text.value = "Waiting for new chat box to be selected..."
                FOUND_NEW_AUTOMATION_HWND.wait()
                if not SHOULD_LOOK_FOR_AUTOMATION_HWND:
                    break
                loading_text.value = "Using default chat box..."

def load_model(final: Box[bool], can_spin: Box, loading_text: Box[str]):
    if _skip_model_loading:
        can_spin.value = True
        return skip_model_load(loading_text, final)
    model_filename = "parakeet-tdt-0.6b-v2.nemo"
    model_path = path_to_model + model_filename
    if not os.path.exists(model_path):
        tk_config(label, text=f"Could not find \"{model_path}\". Allow fetching from \"https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2\"?")
        @main_thread_async
        def _resize_window_first():
            if root.winfo_width() < 500:
                root.minsize(500, root.winfo_height())
        _resize_window_first()
        allowed = False
        def on_allow():
            nonlocal allowed
            allowed = True
        def on_deny():
            quit_normal()
        allow = None
        deny = None
        @main_thread
        def create_buttons():
            nonlocal allow
            nonlocal deny
            allow = tk.Button(root, text="Allow", command=on_allow)
            deny = tk.Button(root, text="Deny", command=on_deny)
            allow.pack(padx=10, pady=10, side=tk.LEFT)
            deny.pack(padx=10, pady=10, side=tk.LEFT)
            on_force_geometry_change()
        create_buttons()
        while not allowed:
            time.sleep(0.5)
        @main_thread
        def destroy_buttons():
            if allow is not None:
                allow.destroy()
            if deny is not None:
                deny.destroy()
            on_force_geometry_change()
        destroy_buttons()
        can_spin.value = True
        loading_text.value = "Downloading parakeet-tdt-0.6b-v2.nemo..."
        hf_hub_download(
            repo_id="nvidia/parakeet-tdt-0.6b-v2",
            filename="parakeet-tdt-0.6b-v2.nemo",
            local_dir=path_to_model,
            local_dir_use_symlinks=False
            )
        @main_thread
        def _fix_window_size():
            root.minsize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        _fix_window_size()
    can_spin.value = True

    print("Initializing pytorch...")
    loading_text.value = "Initializing pytorch..."
    import torch
    import torch.version
    print("Initialized.")
    print("torch version:", torch.__version__)
    print("cuda available:", torch.cuda.is_available())
    print("cuda version:", torch.version.cuda)
    if not torch.cuda.is_available() and not allow_cpu_asr:
        loading_text.value = "Waiting for user input..."
        why_no_cuda = "Something went wrong."
        try:
            torch.cuda.current_device()
        except Exception as e:
            print(type(e).__name__)
            print(e)
            why_no_cuda = f"{e}"
        @main_thread
        def download_pytorch() -> bool | None:
            return messagebox.askyesnocancel("STT Loaded to CPU", f"PyTorch was loaded to your CPU because CUDA wasn't available: {why_no_cuda}\nThis will lead to degraded performance.\nPress YES to download pytorch for GPU, press NO to ignore, and press CANCEL to close STT.\nDisable this warning in the config by changing warn_on_cpu to false.")
        choice = download_pytorch()
        if choice is None:
            quit_normal()
        if choice:
            global EARLY_GIVEUP_INIT
            EARLY_GIVEUP_INIT = True
            final.value = True
            spawn_thread(_download_pytorch_cuda)
            return
    print("Initalizing nemo...")
    loading_text.value = "Initalizing nemo..."
    import nemo.collections.asr as nemo_asr
    print("Initialized.")

    global asr_model
    loading_text.value = "Loading " + model_filename + "..."
    asr_model = nemo_asr.models.ASRModel.restore_from(model_path) # type: ignore
    device = next(asr_model.parameters()).device # type: ignore
    print(f"Model device: {device}")
    if device.type == "cpu" and not allow_cpu_asr:
        @main_thread_async
        def confirm_cpu():
            messagebox.showwarning("STT Loaded to CPU", "The speech-to-text model was loaded to your CPU.\nDisable this warning in the config by changing warn_on_cpu to false.")
        confirm_cpu()
    _load_model_get_hwnd(loading_text)
    final.value = True

def advance_wheel(wheel: str) -> str:
    if wheel == "-":
        return "\\"
    if wheel == "\\":
        return "|"
    if wheel == "|":
        return "/"
    if wheel == "/":
        return "-"
    return "-"

class FilterActivationCallback:
    def __init__(self, filter: Filter):
        self.filter = filter
        self.pressed = False

    def get_activation_details(self) -> FilterActivation:
        if self.filter.activation_details is None:
            raise RuntimeError(f"Attempted to get the activation_details of a callback for filter {self.filter.name} which did not have an activation.")
        return self.filter.activation_details

    def on_press(self):
        print(f"Pressed FilterActivationCallback for {self.filter.title}")
        was_pressed = self.pressed
        self.pressed = True
        if self.get_activation_details().toggle:
            if not was_pressed:
                if self.filter.manager.is_enabling(self.filter.name, "keypress"):
                    self.filter.manager.disable_filter(self.filter.name, "keypress")
                else:
                    self.filter.manager.enable_filter(self.filter.name, "keypress")
        else:
            if not was_pressed:
                self.filter.manager.enable_filter(self.filter.name, "keypress")

    def on_release(self):
        print(f"Released FilterActivationCallback for {self.filter.title}")
        was_pressed = self.pressed
        self.pressed = False
        if self.get_activation_details().toggle:
            pass
        else:
            if was_pressed:
                self.filter.manager.disable_filter(self.filter.name, "keypress")

def init():
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 6) # hide console
    wheel = "-"
    loading_finished = Box(False)
    can_spin = Box(False)
    loading_text = Box("Goaning stations...")
    tk_config(label, text=loading_text.value)
    populate_named_inputs()
    load_settings_from_config()
    free_ram = psutil.virtual_memory().available
    required_ram = 5 * 1024**3 # 5GB
    print(f"Current free ram is {free_ram}B or {free_ram / 1000 / 1000 / 1000}GB")
    if free_ram < required_ram:
        spawn_thread(messagebox.showerror, "Low system memory",
                     f"There is low system memory available. STT requires {required_ram//(1024**2)}MB available, but only {free_ram//(1024**2)}MB are available. The program may run slowly or crash, please free up resources before continuing!")
    if allow_version_checking:
        try:
            current = current_version()
            latest = latest_version()
            if version_greater(latest, current):
                changelog = fetch_changelog()
                text = f"Check out the changelog?\nNew version available! You are on {current}, but latest version is {latest}!\nDisable version checking in the config file. (meta -> enable_version_checking)\nPress Yes to view the changelog."
                if changelog.critical_updates is not None:
                    text = f"A critical update is available for version {latest}! Critical: {changelog.critical_updates}!\nDisable version checking in the config file. (meta -> enable_version_checking)"
                spawn_thread(show_version_info, text, changelog, current)
        except Exception as e:
            spawn_thread(messagebox.showerror, "An error has occurred", f"Encountered {type(e).__name__} {e} while checking version.")
    spawn_thread(load_model, loading_finished, can_spin, loading_text)
    while not loading_finished.value:
        while can_spin.value and not loading_finished.value:
            wheel = advance_wheel(wheel)
            tk_config(label, text=loading_text.value + " " + wheel)
            time.sleep(0.5)
        time.sleep(0.5)
    if EARLY_GIVEUP_INIT:
        return
    for registered_filter in FILTERS.registered_filters.values():
        if registered_filter.activation_details is None or len(Pressable.parse_hotkey(registered_filter.activation_details.keybind)) == 0:
            registered_filter.activation_details = None
            continue
        callback = FilterActivationCallback(registered_filter)
        set_control(registered_filter.activation_details.keybind,
                    registered_filter.name + ".keybind",
                    callback.on_press,
                    callback.on_release,
                    _suppress=registered_filter.activation_details.suppresses)
    spawn_thread(mouse_listener)
    spawn_thread(keyboard_listener)

    tk_config(label, text="Waiting...")

root.after(0, spawn_thread, init)

root.mainloop()

if FINAL_FATAL_MESSAGE is not None:
    ctypes.windll.user32.MessageBoxW(
        None,
        FINAL_FATAL_MESSAGE,
        "STT Fatal error",
        0x10  # MB_ICONERROR
    )