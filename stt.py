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
import random
import math
import types
import importlib.util
from tkinter import ttk
from tkinter import messagebox
from enum import Enum
from huggingface_hub import hf_hub_download
import traceback

root = tk.Tk()
root.title("Speech To Text")
root.attributes("-topmost", True)
root.geometry("300x100")
label = tk.Label(root, text="Pre-Init", wraplength=290, justify="left", font=("Arial", 12))
label.pack(expand=True)
default_width = 300
default_height = 100

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
    filtered.append(f"Traceback for exception {type(e).__name__}: {e} (most recent call first):")
    cause = e
    while not (cause is None):
        filtered.append(filtered_traceback(cause.__traceback__))
        filtered.append(f"{type(cause).__name__}: {cause}")
        if not cause.__cause__ is None:
            cause = cause.__cause__
            filtered.append(f"The above exception was the direct cause of the following:")
            filtered.append(f"Traceback for exception {type(cause).__name__}: {cause} (most recent call first):")
        elif not (cause.__context__ is None) and not cause.__suppress_context__:
            cause = cause.__context__
            filtered.append(f"During handling of the above exception, another exception occurred:")
            filtered.append(f"Traceback for exception {type(cause).__name__}: {cause} (most recent call first):")
        else:
            cause = None
    return '\n'.join(filtered)
    

def filtered_traceback(parent_frame: types.TracebackType | None = None) -> str:
    stack: traceback.StackSummary
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
                filtered += "In "
            filtered += frame.name
            was_filtered = True
        else:
            if was_filtered:
                filtered += " ->\n"
            filtered += f"File {frame.filename}, line {frame.lineno}, in {frame.name}\n  {frame.line}\n"
            was_filtered = False
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

    def on_enable(self):
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
    
    def on_enable(self):
        self.manager.enable_filter(self.filter, self.name)

    def on_disable(self):
        self.manager.disable_filter(self.filter, self.name)

    def __repr__(self):
        return "InceptionAction." + self.name
    
    @staticmethod
    def noop(input):
        return input

class FilterActivation:
    def __init__(self, keybind: str, toggle: bool):
        self.keybind = keybind
        self.toggle = toggle

class Filter:
    def __init__(self, name: str, title: str, manager: "FilterManager", actions: list[ApplyableAction], activated_by: FilterActivation | None, background: str|None="green", text_color: str|None="black"):
        self.background = "green" if background is None else background
        self.text_color = "black" if text_color is None else text_color
        self.name = name
        self.title = title
        self.manager = manager
        self.actions = actions
        self.activation_details: FilterActivation | None = activated_by
        self.enabled_by: dict[str, bool] = {}
        self.manager.register(self)
        self.display: ttk.Label | None = None
        
    def __str__(self):
        return "Filter." + self.name

class ExpandableColumnFlow:
    def __init__(self, parent, columns):
        self.grid = tk.Frame(parent)
        for col in range(columns):
            self.grid.grid_columnconfigure(col, minsize=100)
        self.grid.grid_rowconfigure(0, minsize=25)
        self.grid.pack()
        self.columns = columns
        self.flat = []

    def get_height(self):
        return self.grid.winfo_reqheight() if len(self.flat) > 0 else 0

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
        root.geometry(f"{root.winfo_width()}x{root.winfo_height() - height_before + height_after}")

    def add_button(self):
        height_before = self.get_height()
        widget = ttk.Label(self.grid, anchor="center")
        widget.grid(row=math.floor(len(self.flat) / self.columns), column=len(self.flat) % self.columns, sticky="nsew")
        widget.config(background="green")
        self.flat.append(widget)
        height_after = self.get_height()
        root.geometry(f"{root.winfo_width()}x{root.winfo_height() - height_before + height_after}")
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
        self.enabled_filters.pop(filter.name, None)
        if len(filter.enabled_by) > 0:
            return
        if not (filter.display is None):
            self.display.delete_button(filter.display)
            filter.display = None
        for action in filter.actions:
            self.disable_action(action, source=filter)

    def enable_action(self, action: ApplyableAction, source: Filter):
        action.enabled_by[source.name] = True
        if action.name in self.enabled_actions:
            return
        self.enabled_actions[action.name] = action
        action.on_enable()
    
    def disable_action(self, action: ApplyableAction, source: Filter):
        action.enabled_by.pop(source.name, None)
        if len(action.enabled_by) == 0:
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

class Box:
    def __init__(self, value):
        self.value = value

class ControlButton:
    def __init__(self, control: str, is_mouse: bool, action: typing.Callable):
        self.control = control
        self._is_mouse = is_mouse
        self._is_pressed = False
        self.action = action
        self.lock = threading.Lock()
    
    def set_release_action(self, action: typing.Callable | None):
        self.release_action = action

    def press(self):
        if not self._is_pressed:
            spawn_thread(self.action)
        with self.lock:
            self._is_pressed = True
    
    def release(self):
        if self._is_pressed:
            if not self.release_action is None:
                spawn_thread(self.release_action)
        with self.lock:
            self._is_pressed = False

    def __str__(self):
        return "ControlButton " + ("mouse button " if self.is_mouse() else "") + self.control

    def is_key(self):
        return not self.is_mouse()

    def is_mouse(self):
        return self._is_mouse

    def is_pressed(self):
        with self.lock:
            return self._is_pressed

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

CONTROLS: dict[str, ControlButton] = {}
CONTROLS_BY_KEY: dict[str, ControlButton] = {}
WORD_REPLACEMENTS: dict[str, str] = {}

T = typing.TypeVar('T')
U = typing.TypeVar('U')
V = typing.TypeVar('V')

class ConfigError(Exception):
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
            raise ConfigError(f"Could not get value of option {names[-1]}, {name} was not a dictionary in tree {pretty_print_configobject(derived, expected=f'dictionary, got {type(derived.decay()).__name__}')}. (See example config.json!)")
        derived = typing.cast(ConfigObject[dict], derived)
        if not name in derived.decay():
            likely_type = dict
            if name == names[-1]:
                likely_type = expected_type
            raise ConfigError(f"Could not get value of option {names[-1]}, {name} was not found in tree {pretty_print_configobject(derived, doublequote(name) + f' (a {likely_type.__name__} value)')}. (See example config.json!)")
        derived = derived[name]
    if not derived.isinstance(expected_type):
        raise ConfigError(f"Option {names[-1]} was not a {expected_type.__name__}, but a {type(derived).__name__} in tree {pretty_print_configobject(derived, expected_type.__name__)}")
    if expected_type is list or expected_type is dict:
        return derived
    return derived.decay()

def config_has_property(obj: ConfigObject, names: list[str], expected_type: typing.Type[T]) -> bool:
    try:
        config_get_property(obj, names, expected_type)
        return True
    except:
        return False

def config_get_optional_property(obj: ConfigObject, names: list[str], expected_type: typing.Type[T]) -> T|None:
    try:
        return config_get_property(obj, names, expected_type)
    except:
        return None
        

def set_control(control: str, name: str, action: typing.Callable, release: typing.Callable | None = None):
    if control in CONTROLS_BY_KEY:
        raise RuntimeError(f"Mutliple controls using the same key is not implemented yet. Attempted to set {name} to be called when {control} is pressed, but there already exists a control which is bound to {control}.")
    control_button = ControlButton(control, is_mousebutton(control), action)
    control_button.set_release_action(release)
    CONTROLS_BY_KEY[control] = control_button
    CONTROLS[name] = control_button

FILTERS: FilterManager = FilterManager(DISPLAYED_MODIFIERS)

def load_settings_from_config():
    config: ConfigObject
    with io.open("config.json") as config_file:
        config = ConfigObject(json.loads(config_file.read(-1)))
    global verbose
    verbose = config_get_property(config, ["meta", "verbose"], bool)
    global allow_version_checking
    allow_version_checking = config_get_property(config, ["meta", "enable_version_checking"], bool)
    set_control(config_get_property(config, ["input", "activate"], str), "activate", on_activate_press_handler, release=on_activate_release_handler)
    set_control(config_get_property(config, ["input", "reject"], str), "reject", on_reject_press_handler, release=on_reject_release_handler)
    set_control(config_get_property(config, ["input", "radio_modifier"], str), "radio", on_radio_press_handler, release=on_radio_release_handler)
    global default_width
    global default_height
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
                    parsed_actions.append(InceptionAction(FILTERS, filter_to_apply))
        activation = None
        if config_has_property(filter, ["key_combination"], str):
            activation = FilterActivation(config_get_property(filter, ["key_combination"], str), config_get_property(filter, ["toggle"], bool))
        Filter(name, title, FILTERS, parsed_actions, activation,
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
    control = CONTROLS["radio"].control.removesuffix("_l").removesuffix("_r")
    if CONTROLS["radio"].is_key():
        if keyboard.is_pressed(control):
            return True
        return False
    if mouse.is_pressed(button=control):
        return True
    return False

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

blockable_keys = ['w', 'a', 's', 'd', 'alt', 'space']
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

def on_click(x: int, y: int, button: pynput.mouse.Button, pressed: bool):
    if button.name in CONTROLS_BY_KEY:
        control = CONTROLS_BY_KEY[button.name]
        if control.is_mouse():
            control.press() if pressed else control.release()

def key_press_key_to_string(key: pynput.keyboard.Key | pynput.keyboard.KeyCode | None) -> str:
    if key is None:
        return ""
    if isinstance(key, pynput.keyboard.Key):
        return key.name
    if key.char is None:
        return ""
    return key.char

def on_key_press(key_raw: pynput.keyboard.Key | pynput.keyboard.KeyCode | None):
    key = key_press_key_to_string(key_raw)
    if key in CONTROLS_BY_KEY:
        control = CONTROLS_BY_KEY[key]
        if control.is_key():
            control.press()

def on_key_release(key_raw: pynput.keyboard.Key | pynput.keyboard.KeyCode | None):
    key = key_press_key_to_string(key_raw)
    if key in CONTROLS_BY_KEY:
        control = CONTROLS_BY_KEY[key]
        if control.is_key():
            control.release()

def mouse_listener():
    with pynput.mouse.Listener(on_click=on_click) as listener:
        listener.join()

def keyboard_listener():
    with pynput.keyboard.Listener(on_press=on_key_press, on_release=on_key_release) as listener:
        listener.join()

def load_model(final: Box, can_spin: Box, loading_text: Box):
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
            spawn_thread(messagebox.showinfo, ["New Version Available", f"New version available! You are on {current}, but latest version is {latest}!\nDisable version checking in the config.ini file."])
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
        set_control(registered_filter.activation_details.keybind, registered_filter.name + ".keybind", callback.on_press, callback.on_release)
    spawn_thread(mouse_listener)
    spawn_thread(keyboard_listener)

    label.config(text="Waiting...")

root.after(0, spawn_thread, init)

root.mainloop()
