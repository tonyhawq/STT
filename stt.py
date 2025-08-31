import tkinter as tk
import threading
import pynput
import string
import pyaudio
import time
import wave
import json
import typing
import pyperclip
import keyboard
import mouse
import os
import io
import re
import requests
import uuid
import functools
import math
import types
import importlib.util
from tkinter import ttk
from tkinter import messagebox
from enum import Enum
from huggingface_hub import hf_hub_download
import traceback
import re

T = typing.TypeVar('T')
U = typing.TypeVar('U')
V = typing.TypeVar('V')

root = tk.Tk()
root.title("Speech To Text")
root.attributes("-topmost", True)
root.geometry("300x100")
label = tk.Label(root, text="Pre-Init", wraplength=290, justify="left", font=("Arial", 12))
label.pack(expand=True)
default_width = 300
default_height = 100

_skip_model_loading = False
thread_context = threading.local()
verbose = False

def verbose_print(*args, **kwargs):
    if verbose:
        print(*args, **kwargs)

def _global_exception_handler(exception: Exception, context: str = "No context available."):
    try:
        filename = "logs/" + str(time.time()) + ".log"
        with io.open("current.log", "w") as log:
            log.write(context)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with io.open(filename, "w") as log:
            log.write(context)
        message = f"{type(exception).__name__}:\n{exception}\nFull stacktrace available at \"current.log\" and \"{filename}\"."
        messagebox.showwarning("Exception encountered", message=message)
    except Exception as e:
        print(f"Fatal error encountered while processing {type(exception).__name__} ({exception}): {type(e).__name__}: {e}")
        quit()

def _thread_ctx(func: typing.Callable, context: str, args: list = []):
    try:
        global thread_context
        thread_context.value = context
        verbose_print("calling", func, "with", args)
        func(*args)
    except Exception as e:
        root.after(0, _global_exception_handler, e, exception_to_filtered_traceback(e, context=context))
        
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

def spawn_thread(func: typing.Callable, args: list = []):
    context = ""
    try:
        context = thread_context.value
    except:
        pass
    stack = context + filtered_traceback()
    thread = threading.Thread(target=_thread_ctx, args=(func, stack, args), daemon=True)
    thread.start()

class Configurable():
    def __init__(self, obj):
        self.obj = obj
        self.m_dirtied_by = 0
    
    def dirtied_by(self):
        return self.m_dirtied_by
    
    def config(self, **kwargs):
        self.obj.config(**kwargs) # type: ignore
        self.m_dirtied_by = time.time()
        return self.m_dirtied_by

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
        return "SelifshAction." + self.name

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
        self.display: ttk.Label | None = None
    
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

def main_thread():
    def decorator(func):
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
    return decorator

@main_thread()
def set_window_geometry(width, height):
    root.update_idletasks()
    if width is None:
        width = root.winfo_width()
    if height is None:
        height = root.winfo_height()
    root.geometry(f"{math.floor(width)}x{math.floor(height)}")

class ExpandableColumnFlow:
    def __init__(self, parent, columns):
        self.lock = threading.Lock()
        self.grid = tk.Frame(parent)
        for col in range(columns):
            self.grid.grid_columnconfigure(col, minsize=100)
        self.grid.grid_rowconfigure(0, minsize=25)
        self.grid.pack()
        self.columns = columns
        self.flat = []

    @main_thread()
    def get_height(self):
        return math.floor(len(self.flat) / self.columns) * 25

    @main_thread()
    def delete_button(self, widget: ttk.Label):
        index: int | None = None
        height_before = self.get_height()
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
        height_after = self.get_height()
        set_window_geometry(None, root.winfo_height() - height_before + height_after)
        
    @main_thread()
    def add_button(self):
        height_before = self.get_height()
        widget = ttk.Label(self.grid, anchor="center")
        widget.grid(row=math.floor(len(self.flat) / self.columns), column=len(self.flat) % self.columns, sticky="nsew")
        widget.config(background="green")
        self.flat.append(widget)
        height_after = self.get_height()
        set_window_geometry(None, root.winfo_height() - height_before + height_after)
        return widget

DISPLAYED_MODIFIERS = ExpandableColumnFlow(root, 3)

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
                filter.display.config(text=filter.title, background=filter.background, foreground=filter.text_color)
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
                raise RuntimeError(f"Malformed plugin {action.name}: returned {type(result)} instead of str.")
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
        return f"mouse {self.button}"

    def __str__(self):
        return f"mouse {self.button}"
    
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
    def _mouse_button_from_str(val: str) -> str:
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
        for value in values:
            try:
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
            def should_suppress():
                return suppression_logic
            self.should_suppress = should_suppress
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
        def press_hook():
            self._check_press()
            self.pressed_by += 1
        def release_hook():
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
        for control in self.controlled_by:
            if control.is_pressed():
                return True
        return False
        
autosend = False
use_say = False
allow_version_checking = True
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
    messagebox.showwarning("STT Version File Error", message=f"An invalid version was detected inside of the version file, expected x.x.x, got \"{version}\"")
    os.remove("version.number")
    return fix_version_file()

def current_version():
    fix_version_file()
    version = "0.0.0"
    with open("version.number", "r") as file:
        version = file.read(-1).strip()
    return version

class Changelog:
    def __init__(self, version: str, name: str, headline: str, critical_updates: list[str] | None, date: str, categories: dict[str, list[str]]):
        self.name = name
        self.version = version
        self.date = date
        self.critical_updates = critical_updates
        self.headline = headline
        self.categories = categories
    
    @main_thread()
    def show(self):
        window = tk.Toplevel()
        window.title(f"Changelog for {self.name}")
        window.geometry(f"600x900+{window.winfo_screenwidth() // 2 - 600 // 2}+{window.winfo_screenheight() // 2 - 900 // 2}")
        text = tk.Text(window, wrap="word")
        text.pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(window, command=text.yview)
        scrollbar.pack(side="right", fill="y")
        text.config(yscrollcommand=scrollbar.set)
        text.tag_configure("header", font=("TkDefaultFont", 20, "bold"))
        text.tag_configure("bold", font=("TkDefaultFont", 15, "bold"))
        text.insert("1.0", f"Version: {self.version}\n", "header")
        text.insert("2.0", f"Date: {self.date}\n")
        text.insert("3.0", "Headline:\n", "header")
        text.insert("4.0", f"{self.headline}\n", "bold")
        line = 5
        if self.critical_updates is not None:
            text.insert("5.0", "Critical updates:\n", "bold")
            line = line + 1
            for update in self.critical_updates:
                text.insert(f"{line}.0", f"  - {update}\n")
                line = line + 1
        for name, bullets in self.categories.items():
            text.insert(f"{line}.0", f"{name}:\n", "bold")
            line = line + 1
            for bullet in bullets:
                text.insert(f"{line}.0", f"  - {bullet}\n")
                line = line + 1
        text.config(state="disabled")
        
    @staticmethod
    def parse(input: str, version: str) -> "Changelog":
        version_idx = input.find(f"Version: {version}")
        header_idx = input.find("---------------------------------------------------------------------------------------------------", version_idx)
        if header_idx == -1:
            header_idx = len(input)
        index = version_idx
        matches = re.findall(r" {2}(.*?)\:\n((?: {4}\-\s+.*(?:\n|$))+)", input[index:header_idx])
        categories: dict[str, list[str]] = {}
        for section_name, bullet_block in matches:
            categories[section_name] = list(re.findall(r" {4}\-\s+(.*)(?:\n|$)", bullet_block))
        name = ", ".join(typing.cast(list[str], categories.get("Name")))
        headline = ", ".join(typing.cast(list[str], categories.get("Headline")))
        categories.pop("Name")
        categories.pop("Headline")
        critical_updates = categories.pop("Critical", None)
        return Changelog(version=version, date=str(re.findall(r"Date: (.*?)\n", input[index:header_idx])[0]), name=name, headline=headline, critical_updates=critical_updates, categories=categories)

def show_version_info(text: str, changelog: Changelog):
    res = messagebox.showinfo("New Version Available", text, type=messagebox.OKCANCEL) #type: ignore
    if res == messagebox.OK:
        changelog.show()

def fetch_changelog() -> Changelog:
    url = "https://api.github.com/repos/tonyhawq/STT/releases/latest"
    response = requests.get(url, timeout=1).json()
    changelog_url = None
    release_version = response.get('tag_name', 'error')
    for asset in response.get("assets", []):
        if asset["name"] == "changelog.txt":
            changelog_url = asset["browser_download_url"]
            break
    if changelog_url is None:
        raise RuntimeError(f"No file with name changelog.txt found for release {release_version}")
    raw_log = requests.get(changelog_url, timeout=1).text
    return Changelog.parse(raw_log, release_version)

def latest_version():
    url = "https://api.github.com/repos/tonyhawq/STT/releases/latest"
    try:
        response = requests.get(url, timeout=1)
    except:
        print("No internet connection.")
        return "0.0.0"
    if response.status_code != 200:
        messagebox.showwarning("STT Response Error", message=f"Could not fetch latest version from github, got {response.status_code}")
        return False
    latest = response.json()["tag_name"]
    return latest

def version_greater(v1, v2):
    t1 = tuple(map(int, v1.split(".")))
    t2 = tuple(map(int, v2.split(".")))
    return t1 > t2

CONTROLS: dict[str, Control] = {}
CONTROLBUTTONS_BY_KEY: dict[Pressable, ControlButton] = {}
WORD_REPLACEMENTS: dict[str, str] = {}

class ConfigError(Exception):
    def __init__(self, message):
        super().__init__(message)

# Raised when the final object is not of expected type
class ConfigTypeError(ConfigError):
    def __init__(self, message):
        super().__init__(message)

# Raised when traversing the tree failed
class ConfigTraversalError(ConfigError):
    def __init__(self, message):
        super().__init__(message)

def strip_generics_from(tval):
    origin = getattr(tval, '__origin__', None)
    if origin is None:
        return tval
    return origin

class ConfigObject(typing.Generic[T]):
    def __init__(self, value: T, parent:"ConfigObject|None" = None, key:str|None = None):
        if isinstance(value, ConfigObject):
            raise RuntimeError()
        self._value: T = value
        self._parent = parent
        self._key = key
    
    def __getattr__(self, attr):
        return getattr(self._value, attr)
    
    def __setattr__(self, attr, val):
        if attr.startswith("_"):
            super().__setattr__(attr, val)
        else:
            setattr(self._value, attr, val)

    def __getitem__(self, key):
        return ConfigObject(self._value[key], parent=self, key=key) # type: ignore

    @typing.overload
    def __iter__(self: "ConfigObject[list[V]]") -> typing.Iterator["ConfigObject[V]"]:
        ...
    
    @typing.overload
    def __iter__(self: "ConfigObject[dict[V, U]]") -> typing.Iterator["typing.Tuple[V, ConfigObject[U]]"]:
        ...

    def __iter__(self) -> object:
        if self.isinstance(dict):
            for key, val in self._value.items(): #type: ignore
                yield key, ConfigObject(val, self, key)
            return
        elif self.isinstance(list):
            for k, item in enumerate(self._value): #type: ignore
                yield ConfigObject(item, self, str(k))
            return
        raise RuntimeError("Attempted to call __iter__ on non-list/dict ConfigObject")
    
    def __len__(self):
        return len(self._value) #type: ignore

    def isinstance(self, type):
        return isinstance(self._value, type)
    
    def decay_fully(self):
        val = self
        while isinstance(val, ConfigObject):
            val = self.decay()
        return val

    def decay(self):
        return self._value

@typing.overload
def config_get_property(obj: ConfigObject, names: list[str], expected_type: typing.Type[list[T]]) -> ConfigObject[list[T]]:
    ...

@typing.overload
def config_get_property(obj: ConfigObject, names: list[str], expected_type: typing.Type[dict[T, U]]) -> ConfigObject[dict[T, U]]:
    ...

@typing.overload
def config_get_property(obj: ConfigObject, names: list[str], expected_type: typing.Type[T]) -> T:
    ...

def pretty_print_configobject(bottom: ConfigObject, expected: str):
    chain: list[ConfigObject] = []
    current = bottom
    while not current is None:
        chain.append(current)
        current = current._parent
    chain.reverse()
    out = []
    is_dict = True
    def is_last(i):
        return i == len(chain) - 1
    for i, obj in enumerate(chain):
        indent = " " * (i * 2)
        key = ('root' if obj._parent is None else '???') if obj._key is None else str(obj._key)
        if is_dict:
            out.append(f"\n{indent}\"{key}\": ")
        else:
            out.append(f"\n{indent}[{key}]: ")
        is_dict = obj.isinstance(dict)
        if obj.isinstance(list):
            out.append("[")
        elif obj.isinstance(dict):
            out.append("{")
        else:
            out.append(str(obj._value))
        if is_last(i):
            out.append(f"\n{indent}{'  '}Expected {expected}\n")
    chain.reverse()
    for j, obj in enumerate(chain):
        i = len(chain) - j
        indent = " " * (i * 2)
        out.append(indent)
        if obj.isinstance(list):
            out.append("]\n")
        elif obj.isinstance(dict):
            out.append("}\n")
        else:
            out.append("\n")
    return "".join(out)

def doublequote(val: str) -> str:
    return f"\"{val}\""

def config_get_property(obj, names, expected_type) -> object:
    derived = obj
    expected_type = strip_generics_from(expected_type)
    for name in names:
        if not derived.isinstance(dict):
            raise ConfigTraversalError(f"Could not get value of option {names[-1]}, {name} was not a dictionary in tree {pretty_print_configobject(derived, expected=f'dictionary, got {type(derived.decay()).__name__}')}. (See example config.json!)")
        derived = typing.cast(ConfigObject[dict], derived)
        if not name in derived.decay():
            likely_type = dict
            if name == names[-1]:
                likely_type = expected_type
            raise ConfigTraversalError(f"Could not get value of option {names[-1]}, {name} was not found in tree {pretty_print_configobject(derived, doublequote(name) + f' (a {likely_type.__name__} value)')}. (See example config.json!)")
        derived = derived[name]
    if not derived.isinstance(expected_type):
        raise ConfigTypeError(f"Option {names[-1]} was not a {expected_type.__name__}, but a {type(derived).__name__} in tree {pretty_print_configobject(derived, expected_type.__name__)}")
    if expected_type is list or expected_type is dict:
        return derived
    return derived.decay()

def config_has_property(obj: ConfigObject, names: list[str], expected_type: typing.Type[T]) -> bool:
    try:
        config_get_property(obj, names, expected_type)
        return True
    except ConfigTraversalError:
        return False

@typing.overload
def config_get_optional_property(obj: ConfigObject, names: list[str], expected_type: typing.Type[T], option: None = None) -> None:
    ...

@typing.overload
def config_get_optional_property(obj: ConfigObject, names: list[str], expected_type: typing.Type[T], option: T) -> T:
    ...

def config_get_optional_property(obj: ConfigObject, names: list[str], expected_type: typing.Type[T], option: T | None = None) -> T|None:
    try:
        return config_get_property(obj, names, expected_type)
    except ConfigTraversalError:
        return option

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
                print("should suppress", self._pressed_count == self._press_threshold)
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
            button.add_press(control.press_hook)
            button.add_release(control.release_hook)
            if isinstance(_suppress, bool):
                if _suppress:
                    button.should_suppress = _literal_true
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

def load_settings_from_config():
    print(f"Loading from config...")
    config: ConfigObject
    with io.open("config.json") as config_file:
        config = ConfigObject(json.loads(config_file.read(-1)))
    global verbose
    verbose = config_get_property(config, ["meta", "verbose"], bool)
    global allow_version_checking
    allow_version_checking = config_get_property(config, ["meta", "enable_version_checking"], bool)
    suppress_activate = config_get_optional_property(config, ["input", "activate_globally_blocked"], bool)
    if suppress_activate is None:
        suppress_activate = False
    set_control(config_get_property(config, ["input", "activate"], str), "activate", on_activate_press_handler, release=on_activate_release_handler, _suppress=suppress_activate)
    set_control(config_get_property(config, ["input", "reject"], str), "reject", on_reject_press_handler, release=on_reject_release_handler)
    set_control(config_get_property(config, ["input", "radio_modifier"], str), "radio", on_radio_press_handler, release=on_radio_release_handler)
    global default_width
    global default_height
    global _skip_model_loading
    _skip_model_loading = config_get_property(config, ["skip_model_load"], bool) if config_has_property(config, ["skip_model_load"], bool) else False
    default_width = config_get_property(config, ["meta", "window_width"], int)
    default_height = config_get_property(config, ["meta", "window_height"], int)
    root.geometry(str(int(default_width)) + "x" + str(int(default_height)))
    global path_to_model
    path_to_model = config_get_property(config, ["meta", "path_to_model"], str)
    global autosend
    autosend = config_get_property(config, ["input", "autosend"], bool)
    global use_say
    use_say_or_chat = config_get_property(config, ["output", "use_say_or_chat"], str)
    if use_say_or_chat == "say":
        use_say = True
    elif use_say_or_chat == "chat":
        use_say = False
        global chat_key
        global chat_delay
        chat_key = config_get_property(config, ["output", "chat_settings", "chat_key"], str)
        chat_delay = config_get_property(config, ["output", "chat_settings", "chat_delay"], float)
    else:
        raise RuntimeError("Expected either \"say\" or \"chat\" as option for \"use_say_or_chat\" in \"output\"")
    global WORD_REPLACEMENTS
    WORD_REPLACEMENTS = config_get_property(config, ["output", "word_replacements"], dict[str, str]).decay()
    filters = config_get_property(config, ["filters"], dict[str, dict])
    for name, filter in filters:
        has_single = config_has_property(filter, ["action"], str)
        has_double = config_has_property(filter, ["actions"], list)
        if has_single and has_double:
            raise ConfigError(f"Attempted to create a filter with both an \"action\" and with \"actions\". Only define one of them in tree {pretty_print_configobject(config_get_property(filter, ['actions'], list), 'action, got actions.')}")
        if not has_single and not has_double:
            raise ConfigError(f"Attempted to create a filter which lacked both an \"action\" and an \"actions\" field in tree {pretty_print_configobject(config_get_property(filter, ['actions'], list), 'actions or action')}")
        title = config_get_property(filter, ["title"], str)
        parsed_actions: list[ApplyableAction] = []
        if has_single:
            parsed_actions.append(TransformAction(FILTERS, config_get_property(filter, ["action"], str)))
        elif has_double:
            actions = config_get_property(filter, ["actions"], list)
            for action in actions:
                type = config_get_property(action, ["type"], str)
                if type == "script":
                    filename = config_get_property(action, ["script"], str)
                    parsed_actions.append(TransformAction(FILTERS, filename))
                elif type == "filter":
                    filter_to_apply = config_get_property(action, ["name"], str)
                    mode = config_get_optional_property(action, ["mode"], str)
                    if mode is None or mode == "enable":
                        parsed_actions.append(InceptionAction(FILTERS, filter_to_apply))
                    elif mode == "disable":
                        parsed_actions.append(SelfishAction(FILTERS, filter_to_apply))
                    else:
                        raise ConfigError(f"Attempted to create an action of type \"{type}\" with an invalid \"mode\" of \"{mode}\", expected \"enable\" or \"disable\" in tree {pretty_print_configobject(action, '')}")
        activation = None
        if config_has_property(filter, ["key_combination"], str) and config_get_property(filter, ["key_combination"], str).lower() != "unset":
            activation = FilterActivation(config_get_property(filter, ["key_combination"], str),
                                          config_get_property(filter, ["toggle"], bool), 
                                          config_get_optional_property(filter, ["suppress"], bool))
        Filter(name, title, FILTERS, parsed_actions,
               config_get_optional_property(filter, ["group"], str, "default"),
               config_get_optional_property(filter, ["exclusive"], bool, False),
               activation,
               background=config_get_optional_property(filter, ["color"], str),
               text_color=config_get_optional_property(filter, ["text_color"], str))
    
    

background = Configurable(root)
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
        global STOP_RECORDING
        global CANCEL_PROCESS
        state = State.READY
        STOP_RECORDING = False
        CANCEL_PROCESS = False
        if not (RECORDING_STREAM is None):
            RECORDING_STREAM.stop_stream()
            RECORDING_STREAM.close()
        label.config(text="Waiting...")
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
    label.config(text="Transcribing...")
    TRANSCRIBED = str(asr_model.transcribe(["output.wav"])[0].text) # type: ignore
    if CANCEL_PROCESS:
        _finalize_process()
        return
    label.config(text=TRANSCRIBED)
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
    label.config(text="Recording...")
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

def colorize(val: str, time: float):
    def _recolor(obj):
        obj.config(bg="white")
    background.config_and_apply(bg=val)(_recolor, time)

blockable_keys = ['w', 'a', 's', 'd', 'f', 'e', 'x', 'alt', 'space']
pressed_keys = {}

def key_filter(event: keyboard.KeyboardEvent):
    if not (event.name in blockable_keys):
        return True
    if event.event_type == 'down':
        verbose_print("Keypress blocked", event.name)
        pressed_keys[event.name] = True
    else:
        verbose_print("Depress blocked", event.name)
        pressed_keys[event.name] = False
    return False

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
    pyperclip.copy(f"Say \"{transcript}\"")
    time.sleep(0.05)
    controller.press(pynput.keyboard.Key.tab)
    controller.release(pynput.keyboard.Key.tab)
    time.sleep(0.05)
    with controller.pressed(pynput.keyboard.Key.ctrl):
        controller.press('v')
        controller.release('v')
    controller.press(pynput.keyboard.Key.enter)
    controller.release(pynput.keyboard.Key.enter)
    controller.press(pynput.keyboard.Key.tab)
    controller.release(pynput.keyboard.Key.tab)
    time.sleep(0.05)

def perform_transformations(transcript: str) -> str:
    for word, replacement in WORD_REPLACEMENTS.items():
        transcript = transcript.replace(word, replacement)
    return FILTERS.transform_input(transcript)

def submit():
    global state
    if state != State.ACCEPTING:
        raise RuntimeError()
    global TRANSCRIBED
    with STATUS_LOCK:
        transcript = TRANSCRIBED
    _finalize_process()
    label.configure(text=transcript)
    print("Submitting transcript")
    colorize("green", 1)
    global pressed_keys
    pressed_keys = {}
    for key in blockable_keys:
        if keyboard.is_pressed(key):
            pressed_keys[key] = True
    # fuck it special case
    if "alt" in pressed_keys:
        controller.release(pynput.keyboard.Key.alt_l)
    hook = keyboard.hook(key_filter, True)
    global IS_RADIO
    try:
        radio = IS_RADIO
        if radio:
            label_background.config_and_apply(bg="light blue")(lambda obj: obj.config(bg="white"), 1)
            transcript = "; " + transcript
        if use_say:
            submit_say(perform_transformations(transcript))
        else:
            submit_chat(perform_transformations(transcript))
    except:
        keyboard.unhook(hook)
        raise
    keyboard.unhook(hook)
    for key, value in pressed_keys.items():
        if value:
            keyboard.press(key)
        else:
            keyboard.release(key)
    IS_RADIO = False
    set_radio_colors()

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
        return
    if state == State.ACCEPTING:
        _finalize_process()
        colorize("red", 1)
        return
    if state == State.PROCESSING:
        with STATUS_LOCK:
            CANCEL_PROCESS = True

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

def set_radio_colors():
    if IS_RADIO:
        label.config(bg="light blue")
    else:
        label.config(bg="white") 

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

def on_click(x: int, y: int, button: pynput.mouse.Button, pressed: bool):
    bind = Pressable(MouseButton(button.name))
    if bind in CONTROLBUTTONS_BY_KEY:
        control = CONTROLBUTTONS_BY_KEY[bind]
        if control.is_mouse():
            control.press() if pressed else control.release()
            if control.should_suppress():
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
    print(f"Mapping for {scancode} is {mapped}")
    if mapped is None:
        return scancode
    specialmapped = mapped.get(name, None)
    print(f"Mapping for {name} is {specialmapped}")
    if specialmapped is None:
        return scancode
    return specialmapped

def on_key(event: keyboard.KeyboardEvent) -> bool:
    if event.name is not None:
        bind = Pressable(KeyButton(translate_special_scancode(event.name, event.scan_code)))
    else:
        bind = Pressable(KeyButton(event.scan_code))
    if bind in CONTROLBUTTONS_BY_KEY:
        control = CONTROLBUTTONS_BY_KEY[bind]
        if control.is_key():
            control.press() if event.event_type == "down" else control.release()
            if control.should_suppress():
                return False
    return True

def mouse_listener():
    global _glob_mouse_listener
    with pynput.mouse.Listener(on_click=on_click) as _glob_mouse_listener:
        _glob_mouse_listener.join()

def keyboard_listener():
    keyboard.hook(on_key, suppress=True)
    
def skip_model_load(final: Box):
    final.value = True

def load_model(final: Box, can_spin: Box, loading_text: Box):
    if _skip_model_loading:
        return skip_model_load(final)
    model_filename = "parakeet-tdt-0.6b-v2.nemo"
    model_path = path_to_model + model_filename
    if not os.path.exists(model_path):
        label.config(text=f"Could not find \"{model_path}\". Allow fetching from \"https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2\"?")
        allowed = False
        def on_allow():
            nonlocal allowed
            allowed = True
        def on_deny():
            root.quit()
        width = root.winfo_width()
        height = root.winfo_height()
        allow = tk.Button(root, text="Allow", command=on_allow)
        deny = tk.Button(root, text="Deny", command=on_deny)
        allow.pack(padx=10, pady=10, side=tk.LEFT)
        deny.pack(padx=10, pady=10, side=tk.LEFT)
        root.geometry(f"{width}x{height + 100}")
        while not allowed:
            time.sleep(0.5)
        allow.destroy()
        deny.destroy()
        root.geometry(f"{width}x{height}")
        can_spin.value = True
        loading_text.value = "Downloading parakeet-tdt-0.6b-v2.nemo..."
        hf_hub_download(
            repo_id="nvidia/parakeet-tdt-0.6b-v2",
            filename="parakeet-tdt-0.6b-v2.nemo",
            local_dir=path_to_model,
            local_dir_use_symlinks=False
            )
    can_spin.value = True
    print("Initalizing nemo...")
    loading_text.value = "Initalizing nemo..."
    import nemo.collections.asr as nemo_asr
    print("Initalized.")
    global asr_model
    loading_text.value = "Loading " + model_filename + "..."
    asr_model = nemo_asr.models.ASRModel.restore_from(model_path) # type: ignore
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
                print(f"And wasn't pressed {self.filter.title}")
                if self.filter.manager.is_enabling(self.filter.name, "keypress"):
                    print(f"So disabling {self.filter.title}")
                    self.filter.manager.disable_filter(self.filter.name, "keypress")
                else:
                    print(f"So enabling {self.filter.title}")
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
    wheel = "-"
    loading_finished = Box(False)
    can_spin = Box(False)
    loading_text = Box("Goaning stations...")
    label.config(text=loading_text.value)
    load_settings_from_config()
    if allow_version_checking:
        current = current_version()
        latest = latest_version()
        if version_greater(latest, current):
            changelog = fetch_changelog()
            text = f"New version available! You are on {current}, but latest version is {latest}!\nDisable version checking in the config.ini file.\nPress OK to view the changelog."
            if changelog.critical_updates is not None:
                text = f"A critical update is available for version {latest}! Critical: {changelog.critical_updates}!\nDisable version checking in the config.ini file."
            spawn_thread(show_version_info, [text, changelog])
    spawn_thread(load_model, args=[loading_finished, can_spin, loading_text])
    while not loading_finished.value:
        while can_spin.value and not loading_finished.value:
            wheel = advance_wheel(wheel)
            label.config(text=loading_text.value+" "+wheel)
            time.sleep(0.5)
        time.sleep(0.5)
    for registered_filter in FILTERS.registered_filters.values():
        if registered_filter.activation_details is None:
            continue
        callback = FilterActivationCallback(registered_filter)
        set_control(registered_filter.activation_details.keybind,
                    registered_filter.name + ".keybind",
                    callback.on_press,
                    callback.on_release,
                    _suppress=registered_filter.activation_details.suppresses)
    spawn_thread(mouse_listener)
    spawn_thread(keyboard_listener)

    label.config(text="Waiting...")

root.after(0, spawn_thread, init)

root.mainloop()
