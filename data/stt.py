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
    import pyloudnorm
    from pathlib import Path
    import numpy as np
    import functools
    import math
    import pynput._util.win32
    import importlib.util
    import pywinauto
    import ctypes.wintypes
    import inspect
    import copy
    import faulthandler
    import signal
    from enum import Enum
    import re
    print("Importing dependencies...")
    import shared
    from shared import spawn_thread, report_exception
    print("Importing gui...")
    import tkinter as tk
    import tkinter.filedialog
    from tkinter import messagebox
    import tkinter.ttk as ttk
except ImportError as e:
    print("An error occurred on startup!")
    print("-" * 30)
    print(f"{type(e).__name__}: \"{e}\"")
    print("-" * 30)
    print("This likely happened because of outdated dependencies.")
    print("To resolve, run setup.bat again!")
    print("-" * 30)
    try:
        try:
            from tkinter import messagebox
            messagebox.showerror("Imports failure", f"STT failed to load due to missing imports. This is likely caused by outdated dependencies. To resolve, run setup.bat again!\n\n{e}")
        except Exception as e:
            print(f"While showing the errorbox for the error, got another exception ({type(e).__name__}) {e}")
    except Exception as e:
        pass
    sys.exit(1)

faulthandler.enable()
def signalhandler(sig, frame):
    print(f"SIGNAL {sig} {frame}")
signal.signal(signal.SIGTERM, signalhandler)
signal.signal(signal.SIGINT, signalhandler)

sys.path.insert(0, str(Path(__file__).parent))

FINAL_FATAL_MESSAGE: str | None = None

@shared.diagnose_entry
def quit_normal():
    root.destroy()

@shared.diagnose_entry
def quit_with_errorbox(message: str, source: Exception | None = None):
    if source is None:
        shared.record_exception(RuntimeError(f"quit_with_errorbox called with message \"{message}\", no exception given."))
    else:
        shared.record_exception(source)
    global FINAL_FATAL_MESSAGE
    FINAL_FATAL_MESSAGE = message
    root.destroy()

print("Finished importing libraries.")

def main_thread(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if threading.current_thread() is threading.main_thread():
            try:
                return func(*args, **kwargs)
            except Exception as e:
                spawn_thread(report_exception, e)
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
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if threading.current_thread() is threading.main_thread():
            func(*args, **kwargs)
            return
        def afterwrapper():
            try:
                func(*args, **kwargs)
            except Exception as e:
                print(f"MAIN THREAD ASYNC EXCEPTION ({type(e).__name__}) {e}")
                report_exception(e)
        root.after(0, afterwrapper)
    return wrapper

def _main_thread_sync_shared_wrapper(func, *args, **kwargs):
    @main_thread
    def worker():
        return func(*args, **kwargs)
    return worker()

def _main_thread_async_shared_wrapper(func, *args, **kwargs):
    @main_thread_async
    def worker():
        func(*args, **kwargs)
    worker()

shared.begin(quit_func=quit_normal, quit_error_func=quit_with_errorbox, main_thread_sync_func=_main_thread_sync_shared_wrapper, main_thread_async_func=_main_thread_async_shared_wrapper)

T = typing.TypeVar('T')
U = typing.TypeVar('U')
V = typing.TypeVar('V')

def settingsbutton_command():
    spawn_thread(open_settings)

def PHOTOIMAGE(file: str) -> tk.PhotoImage:
    try:
        return tk.PhotoImage(file=file)
    except Exception as e:
        messagebox.showerror("Couldn't load STT", f"Couldn't load data/gear.png: ({type(e).__name__}) {e}")
        sys.exit(1)

root = tk.Tk()
@shared.diagnose_entry
def _root_destroy_wrapper(destroy=root.destroy):
    for w in root.winfo_children():
        try:
            w.destroy()
        except Exception as e:
            print(f"EXCEPTION ({type(e).__name__}) {e} while destroying root children")
    destroy()
root.destroy = _root_destroy_wrapper
root.config(bg="white")
root.title("Speech To Text")
root.attributes("-topmost", True)
root.minsize(shared.DEFAULT_WINDOW_WIDTH, shared.DEFAULT_WINDOW_HEIGHT)
label_frame = tk.Frame(root, width = shared.DEFAULT_WINDOW_WIDTH, height = shared.DEFAULT_WINDOW_HEIGHT, bg="white")
label_frame.pack_propagate(False)
label_frame.pack(padx=0, pady=0)
settings_icon = PHOTOIMAGE("data/gear.png").subsample(2, 2)
label = tk.Label(label_frame, text="Pre-Init", bg="white", justify="center", font=("Arial", 12))
label.pack(expand=True)
settings_button = tk.Button(label_frame, image=settings_icon, borderwidth=0, highlightthickness=0, bd=0, relief="flat", bg="white", command=settingsbutton_command)
settings_button.place(x=5, y=5)

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

CHOSEN_MODEL = None

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
    def __init__(self, name: str, manager: "FilterManager", priority: float):
        self.manager = manager
        self.name = name
        self.priority = priority
        self.enabled_by: dict[str, bool] = {}
        self.action: typing.Callable[[str], str] = ApplyableAction.DefaultAction

    @staticmethod
    def DefaultAction(input: str) -> str:
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
    def __init__(self, manager: "FilterManager", priority: float, script_filename: str, enabling_args: dict[str, typing.Any]):
        super().__init__(os.path.splitext(os.path.basename(script_filename))[0] + "." + str(uuid.uuid4()), manager, priority)
        self.src = str(Path(script_filename).resolve())
        self.args = enabling_args
        self.args["invoker"] = self.name
        spec = importlib.util.spec_from_file_location(os.path.splitext(os.path.basename(script_filename))[0], script_filename)
        if spec is None:
            raise ImportError(f"Could not load spec for {script_filename}")
        if spec.loader is None:
            raise ImportError(f"Could not find loader for {script_filename} {spec}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        if not hasattr(module, "process"):
            raise ImportError(f"Plugin {script_filename} does not have a process() function.")
        supports_args = "args" in inspect.signature(module.process).parameters
        if supports_args:
            def wrapped_process(input: str) -> str:
                return module.process(input, self.args)
            self.action = wrapped_process
        else:
            self.action = module.process
        def _set_loading_complete():
            setattr(module, "MANAGER__is_loading_complete", True)
        def _get_loading_complete() -> bool:
            if not hasattr(module, "MANAGER__is_loading_complete"):
                return False
            return True if module.MANAGER__is_loading_complete else False
        self._set_loading_complete = _set_loading_complete
        self.is_loading_complete = _get_loading_complete
        if not hasattr(module, "on_load"):
            print(f" Plugin {script_filename} does not have an on_load function.")
        else:
            self.defined_on_load = module.on_load
        
    def run_defined_loader(self, state: shared.PluginLoadingState):
        if self.is_loading_complete():
            raise RuntimeError("Attempted to call run_defined_loader on a module that was already loaded.")
        try:
            if hasattr(self, "defined_on_load"):
                self.defined_on_load(state)
        except:
            raise
        finally:
            self._set_loading_complete()

    def __repr__(self):
        return "TransformAction." + self.name

class SetPromptAction(ApplyableAction):
    def __init__(self, manager: "FilterManager", priority: float, prompt: str):
        super().__init__("setprompt." + str(uuid.uuid4()), manager, priority)
        self.action = ApplyableAction.DefaultAction
        self.prompt = prompt

    def on_enable(self, source: "Filter"):
        if asr_model is None or not asr_model.supports_prompting():
            raise RuntimeError(f"Current ASR model {asr_model} doesn't support prompting.")
        for filter_name in self.manager.enabled_filters:
            filter = self.manager.registered_filters[filter_name]
            if filter is source:
                continue
            should_disable = False
            for action in filter.actions:
                if type(action) is SetPromptAction:
                    should_disable = True
                    break
            if should_disable:
                self.manager.force_disable_filter(filter_name)
        asr_model.set_prompt(self.prompt)

    def on_disable(self):
        if asr_model is None or not asr_model.supports_prompting():
            raise RuntimeError(f"Current ASR model {asr_model} doesn't support prompting.")
        asr_model.set_prompt(asr_model.default_prompt())

class InceptionAction(ApplyableAction):
    def __init__(self, manager: "FilterManager", priority: float, filter_to_apply: str):
        super().__init__(filter_to_apply + ".applier."+ str(uuid.uuid4()), manager, priority)
        self.action = ApplyableAction.DefaultAction
        self.filter = filter_to_apply
    
    def on_enable(self, source: "Filter"):
        self.manager.enable_filter(self.filter, self.name)

    def on_disable(self):
        self.manager.disable_filter(self.filter, self.name)

    def __repr__(self):
        return "InceptionAction." + self.name

class SelfishAction(InceptionAction):
    def __init__(self, manager: "FilterManager", priority: float, filter_to_apply: str):
        super().__init__(manager, priority, filter_to_apply)
    
    def on_enable(self, source: "Filter"):
        self.manager.disable_filter(self.filter, self.name)
        self.manager.force_disable_filter(self.filter)
    
    def __repr__(self):
        return "SelfishAction." + self.name

class FilterActivation:
    def __init__(self, keybind: str, suppresses: bool | None = None):
        self.keybind = keybind
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
        print(f"Filter::on_enable({self.name})")
        to_delete = []
        for name, filter in self.manager.enabled_filters.items():
            if (filter is not self) and (filter.exclusive or self.exclusive) and filter.group == self.group:
                print(f"  Found filter {name} that is {'exclusive' if filter.exclusive else 'excluded'} over group {filter.group}")
                should_continue = False
                for action in filter.actions:
                    print(f"   - Has action {action.name} vs enabled_by: {self.enabled_by}")
                    if self.enabled_by.get(action.name):
                        print("  : this filter is enabled by")
                        should_continue = True
                        break
                if should_continue:
                    continue
                to_delete.append(name)
        for name in to_delete:
            self.manager.force_disable_filter(name)

    def on_disable(self):
        pass

    def __str__(self):
        return "Filter." + self.name
    
    def __hash__(self) -> int:
        return str(self).__hash__()

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
        self.actionlist: list[ApplyableAction] = []
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
        print(f"Enabling filter \"{name}\" from \"{source}\"")
        if not name in self.registered_filters:
            raise RuntimeError(f"Attempted to enable filter {name} while {name} does not exist.")
        filter = self.registered_filters[name]
        was_disabled = len(filter.enabled_by) == 0
        filter.enabled_by[source] = True
        self.enabled_filters[filter.name] = filter
        if was_disabled:
            print(f"Filter was disabled, enabled. enabled_by is {filter.enabled_by}")
            filter.on_enable()
            with self.display.lock:
                filter.display = self.display.add_button()
                tk_config(filter.display.label, text=filter.title, background=filter.background, foreground=filter.text_color)
        for action in filter.actions:
            self.enable_action(action, source=filter)

    def disable_filter(self, name: str, source: str):
        print(f"Disabling filter \"{name}\" from \"{source}\"")
        if not name in self.registered_filters:
            raise RuntimeError(f"Attempted to disable filter {name} while {name} does not exist.")
        filter = self.registered_filters[name]
        if len(filter.enabled_by) == 0:
            print(f"Attempted to disable \"{name}\" from source \"{source}\" while enabled_by was zero length")
            return
        filter.enabled_by.pop(source, None)
        if len(filter.enabled_by) > 0:
            return
        self.enabled_filters.pop(filter.name, None)
        filter.on_disable()
        if not (filter.display is None):
            with self.display.lock:
                self.display.delete_button(filter.display)
                filter.display = None
        for action in filter.actions:
            self.disable_action(action, source=filter)

    def _impl_enable_action(self, action: ApplyableAction):
        self.enabled_actions[action.name] = action
        if action.action is ApplyableAction.DefaultAction:
            return
        if action not in self.actionlist:
            self.actionlist.append(action)
            self.actionlist.sort(key=lambda act: act.priority, reverse=True)
    
    def _impl_disable_action(self, action: ApplyableAction):
        self.enabled_actions.pop(action.name, None)
        if action.action is ApplyableAction.DefaultAction:
            return
        if action in self.actionlist:
            self.actionlist.remove(action)

    def enable_action(self, action: ApplyableAction, source: Filter):
        action.enabled_by[source.name] = True
        if action.name in self.enabled_actions:
            return
        self._impl_enable_action(action)
        action.on_enable(source)
    
    def disable_action(self, action: ApplyableAction, source: Filter):
        action.enabled_by.pop(source.name, None)
        if len(action.enabled_by) == 0:
            self._impl_disable_action(action)
            action.on_disable()
            
    def force_disable_filter(self, name: str):
        filter = self.registered_filters[name]
        filter.enabled_by = {"FilterManager.force": True}
        self.disable_filter(name, "FilterManager.force")
        
    def force_disable_action(self, action: ApplyableAction):
        action.enabled_by.clear()
        self._impl_disable_action(action)
        action.on_disable()

    def transform_input(self, input: str) -> str:
        for action in self.actionlist:
            input = action.transform(input)
            if not isinstance(input, str):
                raise RuntimeError(f"Malformed plugin {action.name}: returned {type(input)} instead of str.")
        return input

audio = pyaudio.PyAudio()

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
        if not isinstance(other, MouseButton):
            return False
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
        if not isinstance(other, KeyButton):
            return False
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
    def hotkey_contains_str(hotkey: str, text: str) -> bool:
        return text.strip().lower() in Pressable._split_hotkey(hotkey)

    @staticmethod
    def hotkey_is_str(hotkey: str, text: str) -> bool:
        return hotkey.strip().lower() == text.strip().lower()

    @staticmethod
    def _split_hotkey(hotkey: str) -> list[str]:
        values = hotkey.split("+")
        for i, value in enumerate(values):
            values[i] = value.strip().lower()
        return values

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

    @staticmethod
    def hotkey_equivilent(a: str, b: str):
        apbl = Pressable.parse_hotkey(a)
        bpbl = Pressable.parse_hotkey(b)
        def key(a: Pressable) -> str:
            if a.is_keyboard():
                return str(typing.cast(KeyButton, a.control).scancode)
            else:
                return str(typing.cast(MouseButton, a.control).button)
        for sublist in apbl:
            sublist.sort(key=key)
        for sublist in bpbl:
            sublist.sort(key=key)
        apbl.sort()
        bpbl.sort()
        return apbl == bpbl

    def __hash__(self) -> int:
        return self.control.__hash__()
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, Pressable):
            return False
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
hwnd_speech_indicator = False
hwnd_automation_id: int = 0
allow_version_checking = True
allow_cpu_asr = True
chat_delay = 0
chat_key = ""

SETTINGS_WINDOW: tk.Toplevel | None = None

def lblwrap(label: ttk.Label) -> ttk.Label:
    def on_resize(event):
        event.widget.config(wraplength=event.widget.winfo_width())
    label.bind("<Configure>", on_resize)
    return label

QUESTION_ICON = PHOTOIMAGE("data/question_button.png").subsample(2, 2)

@main_thread
def _open_settings_impl():
    global SETTINGS_WINDOW
    if SETTINGS_WINDOW is not None:
        raise RuntimeError("_open_settings_impl called while SETTINGS_WINDOW is not None")
    SETTINGS_WINDOW = tk.Toplevel(master=root)
    SETTINGS_WINDOW.title("Settings")
    SETTINGS_WINDOW.geometry("600x500")

    with open(shared.CONFIG_FILENAME, "r") as f:
        config = tomlkit.load(f)

    def save_to_cfgmem():
        if SETTINGS_WINDOW is None:
            raise RuntimeError("Attempted to call apply_cmd.worker while SETTINGS_WINDOW is None")
        def convert_type(rawval: str | int | float | bool | list | tk.Variable, typestr: str) -> str | int | float | bool | list:
            if isinstance(rawval, tk.Variable):
                value = rawval.get()
            else:
                value = rawval
            if typestr.startswith("list"):
                typelist = typestr.split("@", 1)
                if not isinstance(value, list):
                    raise TypeError(f"Value {value} is not a list.")
                created = []
                for val in value:
                    created.append(convert_type(val, typelist[-1]))
                return created
            elif typestr.startswith("literal"):
                typestr = typestr.removeprefix("literal").removeprefix("'").removesuffix("'")
                values = typestr.split("|")
                if not isinstance(value, str):
                    raise TypeError(f"Value {value} is not a string, so can't match any literal \"{' '.join(values)}\"")
                if not value in values:
                    raise TypeError(f"Value {value} doesn't match any literal in {values}")
                return value
            elif typestr == "string":
                if not isinstance(value, str):
                    raise TypeError(f"Value {value} is not a string.")
                return value
            elif typestr == "key":
                if not isinstance(value, str):
                    raise TypeError(f"Value {value} is not a string. ({type(value).__name__})")
                try:
                    Pressable.parse_hotkey(value)
                except Exception as e:
                    raise TypeError(f"Value {value} is not a key. ([{type(e).__name__}] {e})")
                return value
            elif typestr == "int":
                if not isinstance(value, str) and not isinstance(value, int) and not isinstance(value, float):
                    raise TypeError(f"Value {value} is not an int, float, or a string, instead was {type(value).__name__}")
                try:
                    int(value)
                except Exception as e:
                    raise TypeError(f"Value {value} couldn't be converted to an int. ([{type(e).__name__}] {e})")
                if int(value) != float(value):
                    raise TypeError(f"Value {value} isn't an integer.")
                return int(value)
            elif typestr == "float":
                if not isinstance(value, str) and not isinstance(value, float) and not isinstance(value, int):
                    raise TypeError(f"Value {value} is not an float, int, or a string, instead was {type(value).__name__}")
                try:
                    float(value)
                except Exception as e:
                    raise TypeError(f"Value {value} couldn't be converted to a float. ([{type(e).__name__}] {e})")
                return float(value)
            elif typestr == "bool":
                if not isinstance(value, bool):
                    raise TypeError(f"Value {value} is not a boolean, instead was {type(value).__name__}")
                return value
            else:
                raise TypeError(f"Unknown typestr {typestr}")
        vars: dict[str, tk.Variable | list[tk.StringVar]] = SETTINGS_WINDOW.vars # type: ignore
        for typ, var in vars.items():
            typ = typing.cast(str, typ)
            path = typ.split(":")
            file = path[-1].split("@", 1)
            extension = file[-1]
            file = file[0]
            path = path[:-1]
            varstr = str(var)
            if isinstance(var, tk.Variable):
                varstr = str(var.get())
            print(f"Saving value {':'.join(path)}:{file} (of type {extension}) => {varstr} (path {'/'.join(path)} file {file})")
            try:
                if isinstance(var, list):
                    value = convert_type(var, extension)
                else:
                    value = convert_type(var.get(), extension)
            except TypeError as e:
                raise TypeError(f"Saving \"{file}\" (in {path[0]}) which is a/n {extension}: {e}")
            current_step = config
            for next_step in path:
                try:
                    current_step = current_step[next_step]
                except Exception as e:
                    print(f"Encountered exception while traversing path {path} at step {next_step}: ({type(e).__name__}) {e}\n  CONFIG STATE: {config}\n  CURRENT STEP: {current_step}")
                    raise
            current_step[file] = value
    
    def save_to_file():
        print("-- Saving to config memory")
        save_to_cfgmem()
        print("-- Finished saving to config memory")
        with open(shared.CONFIG_FILENAME, "w") as f:
            f.write(tomlkit.dumps(config))
        print("-- Finished saving to file")

    def window_close_hook():
        global SETTINGS_WINDOW
        if SETTINGS_WINDOW is None:
            raise RuntimeError("SETTINGS_WINDOW is None on window_close_hook")
        with open(shared.CONFIG_FILENAME, "r") as f:
            unmodified = tomlkit.load(f)
        try:
            save_to_cfgmem()
            if unmodified == config:
                SETTINGS_WINDOW.destroy()
                SETTINGS_WINDOW = None
                return
        except:
            pass
        res = messagebox.askyesno("You have unsaved changes!", "You have unsaved changes! Do you want to save your changes?")
        if res:
            try:
                save_to_file()
            except Exception as e:
                def reraise():
                    raise RuntimeError("Saving encountered an error.") from e
                spawn_thread(reraise)
                return
        SETTINGS_WINDOW.destroy()
        SETTINGS_WINDOW = None
        
    SETTINGS_WINDOW.protocol("WM_DELETE_WINDOW", window_close_hook)

    notebook = ttk.Notebook(SETTINGS_WINDOW)
    notebook.pack(fill="both", expand=True)

    def make_tab_from_raw(rawtab: ttk.Frame) -> tk.Frame:
        tab = tk.Canvas(rawtab)
        tab.pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(rawtab, orient="vertical", command=tab.yview)
        scrollbar.pack(side="right", fill="y")
        tab.configure(yscrollcommand=scrollbar.set)
        scrollable_frame = tk.Frame(tab)
        window_id = tab.create_window((0, 0), window=scrollable_frame, anchor="nw")
        tab.bind("<Configure>", lambda e: tab.itemconfigure(window_id, width=e.width))
        def _scroll(e):
            first, last = tab.yview()
            if first == 0.0 and last == 1.0:
                return
            tab.yview_scroll(int(-e.delta / 120), "units")
        scrollable_frame.bind("<Configure>", lambda e: tab.configure(scrollregion=tab.bbox("all")))
        def _bind_mousewheel(event):
            tab.bind_all("<MouseWheel>", _scroll)
        def _unbind_mousewheel(event):
            tab.unbind_all("<MouseWheel>")
        scrollable_frame.bind("<Enter>", _bind_mousewheel)
        scrollable_frame.bind("<Leave>", _unbind_mousewheel)
        return scrollable_frame

    onboarding_rawtab = ttk.Frame(notebook)
    input_rawtab = ttk.Frame(notebook)
    output_rawtab = ttk.Frame(notebook)
    model_rawtab = ttk.Frame(notebook)
    advanced_rawtab = ttk.Frame(notebook)

    onboarding_tab = make_tab_from_raw(onboarding_rawtab)
    input_tab = make_tab_from_raw(input_rawtab)
    output_tab = make_tab_from_raw(output_rawtab)
    model_tab = make_tab_from_raw(model_rawtab)
    advanced_tab = make_tab_from_raw(advanced_rawtab)

    notebook.add(onboarding_rawtab, text="Onboarding")
    notebook.add(input_rawtab, text="Input")
    notebook.add(output_rawtab, text="Output")
    notebook.add(model_rawtab, text="Model")
    notebook.add(advanced_rawtab, text="Advanced")

    def expanding_frame(tab: tk.Frame, row: int):
        tab.rowconfigure(row, weight=1)
        tk.Frame(tab).grid(column=0, row=row)

    onboarding_tab.columnconfigure(0, weight=1)
    header_font = ("TkDefaultFont", 14)
    text_font = ("TkDefaultFont", 10)
    ttk.Label(onboarding_tab, text="Welcome to Speech To Text!", font=("TkDefaultFont", 20, "bold")).grid(column=0, row=0, sticky="new")
    ttk.Label(onboarding_tab, text="How do I use STT?", font=header_font).grid(column=0, row=1, sticky="new")
    lblwrap(ttk.Label(onboarding_tab, text="It's simple! Hold down the activate keybind (defaults to mousebutton4) to record your voice, and release it to send it in game!", font=text_font)).grid(column=0, row=2, sticky="new")
    ttk.Label(onboarding_tab, text="What's a filter?", font=header_font).grid(column=0, row=3, sticky="new")
    lblwrap(ttk.Label(onboarding_tab, text=f"Filters can change your text after you've said it. STT comes with a bunch of filters, especially for departmental radios! Just open {shared.FILTERCONFIG_FILENAME} and set some keybinds, or create your own filters.", font=text_font)).grid(column=0, row=4, sticky="new")
    ttk.Label(onboarding_tab, text="What if I mess all my settings up?", font=header_font).grid(column=0, row=5, sticky="new")
    lblwrap(ttk.Label(onboarding_tab, text=f"Just delete {shared.CONFIG_FILENAME} and relaunch STT!", font=text_font)).grid(column=0, row=6, sticky="new")
    expanding_frame(onboarding_tab, row=7)

    def add_buttons(tab: tk.Frame) -> tk.Frame:
        base_frame = tk.Frame(tab)
        base_frame.pack(fill="both", expand=True)
        def apply_cmd():
            apply_button.config(state="disabled")
            discard_button.config(state="disabled")
            finished = threading.Event()
            def runner():
                try:
                    try:
                        save_to_file()
                    except TypeError as e:
                        shared.record_exception(e)
                        messagebox.showerror("Couldn't save", f"Couldn't save the config. ({type(e).__name__}) {e}")
                    finished.set()
                except:
                    raise
                finally:
                    @main_thread
                    def reconfigure():
                        apply_button.config(state="normal")
                        discard_button.config(state="normal")
                    reconfigure()
            spawn_thread(runner)
        def discard_cmd():
            if SETTINGS_WINDOW is None:
                raise RuntimeError("SETTINGS_WINDOW is None within Discard button command.")
            SETTINGS_WINDOW.destroy()
        apply_button = tk.Button(tab, text="Apply", font=header_font, command=apply_cmd)
        apply_button.pack(side="left", padx=10, pady=10)
        discard_button = tk.Button(tab, text="Discard", font=header_font, command=discard_cmd)
        discard_button.pack(side="left", padx=10, pady=10)
        return base_frame

    input_base_frame = add_buttons(input_tab)
    output_base_frame = add_buttons(output_tab)
    model_base_frame = add_buttons(model_tab)
    advanced_base_frame = add_buttons(advanced_tab)
    def _create_infobutton(tab: tk.Widget, text: str) -> tk.Button:
        return tk.Button(tab, image=QUESTION_ICON, relief="flat", bg="white", command=lambda: spawn_thread(lambda: messagebox.showinfo("Info", text)))

    def infobutton(tab: tk.Frame, column: int, row: int, text: str):
        _create_infobutton(tab, text).grid(column=column, row=row, sticky="new")

    def add_listbox(tab: tk.Frame, row: int, name: str, info: str, valuelist: list[str]):
        ttk.Label(tab, text=f"{name}  ").grid(column=0, row=row, sticky="nw")
        _create_infobutton(tab, info).grid(column=3, row=row, sticky="n")
        listbox_frame = ttk.Frame(tab)
        listbox_frame.grid(column=2, row=row, sticky="nsew")
        listbox = tk.Listbox(listbox_frame)
        listbox.pack(side="top", fill="both", expand=True)
        for value in valuelist:
            listbox.insert(tk.END, " " + value)
        entry = ttk.Entry(listbox_frame)
        entry.pack(fill="x")
        def add_item():
            text = entry.get().strip()
            if not text or text in valuelist:
                return
            listbox.insert(tk.END, " " + text)
            valuelist.append(text)
            entry.delete(0, tk.END)
        def remove_item():
            selection = listbox.curselection()
            if not selection:
                return
            for index in reversed(selection):
                listbox.delete(index)
                valuelist.pop(index)
        ttk.Button(
            listbox_frame,
            text="Add",
            command=add_item
        ).pack(side="left")
        ttk.Button(
            listbox_frame,
            text="Remove",
            command=remove_item
        ).pack(side="left")

    def make_checkbox(tab: tk.Frame, column: int, row: int, var: tk.BooleanVar):
        cbframe = tk.Frame(tab)
        cbframe.grid(column=column, row=row, sticky="ew")
        ttk.Checkbutton(cbframe, variable=var).pack(side="right")

    input_base_frame.columnconfigure(0, weight=0)
    input_base_frame.columnconfigure(1, weight=1)
    input_base_frame.columnconfigure(2, weight=0)
    print(f"{config['input']['activate']}")
    SETTINGS_WINDOW.vars = {} # type: ignore
    stored_vars: dict[str, tk.Variable | list[str]] = SETTINGS_WINDOW.vars # type: ignore
    stored_vars["input:activate@key"] = tk.StringVar(value=config["input"]["activate"])
    stored_vars["input:reject@key"] = tk.StringVar(value=config["input"]["reject"])
    stored_vars["input:radio_modifier@key"] = tk.StringVar(value=config["input"]["radio_modifier"])
    stored_vars["input:autosend@bool"] = tk.BooleanVar(value=config["input"]["autosend"])
    stored_vars["input:activate_globally_blocked@bool"] = tk.BooleanVar(value=config["input"]["activate_globally_blocked"])
    stored_vars["input:blocked_keys@list@string"] = config["input"]["blocked_keys"]
    ttk.Label(input_base_frame, text="Activate keybind  ").grid(column=0, row=0, sticky="ew")
    ttk.Entry(input_base_frame, textvariable=stored_vars["input:activate@key"]).grid(column=2, row=0, sticky="ew")
    infobutton(input_base_frame, 3, 0, "Hold this button to record your voice.")
    ttk.Label(input_base_frame, text="Reject keybind  ").grid(column=0, row=1, sticky="ew")
    ttk.Entry(input_base_frame, textvariable=stored_vars["input:reject@key"]).grid(column=2, row=1, sticky="ew")
    infobutton(input_base_frame, 3, 1, "Press this button at any time to cancel a message.")
    ttk.Label(input_base_frame, text="Radio keybind  ").grid(column=0, row=2, sticky="ew")
    ttk.Entry(input_base_frame, textvariable=stored_vars["input:radio_modifier@key"]).grid(column=2, row=2, sticky="ew")
    infobutton(input_base_frame, 3, 2, "Press this button to toggle sending messages over the radio.")
    ttk.Label(input_base_frame, text="Autosend  ").grid(column=0, row=3, sticky="ew")
    make_checkbox(input_base_frame, 2, 3, stored_vars["input:autosend@bool"])
    infobutton(input_base_frame, 3, 3, "If this box is checked, your messages will automatically send once you let go of the activate keybind. If unchecked, you have to press the activate keybind a second time to send the message.")
    ttk.Label(input_base_frame, text="Activate globally blocked  ").grid(column=0, row=4, sticky="ew")
    make_checkbox(input_base_frame, 2, 4, stored_vars["input:activate_globally_blocked@bool"])
    infobutton(input_base_frame, 3, 4, "Should the activate keybind be blocked from the rest of your system? Usually this should be checked.")
    add_listbox(input_base_frame, 5, "Blocked keys", "Keys that should be blocked while the submission process is ongoing. Typically these keys will be blocked for 10-100ms.", stored_vars["input:blocked_keys@list@string"])
    expanding_frame(input_base_frame, row=6)

    stored_vars["output:output_method@literal'hwnd|say|chat'"] = tk.StringVar(value=config["output"]["output_method"])
    stored_vars["output:hwnd_settings:automation_id@int"] = tk.StringVar(value=str(config["output"]["hwnd_settings"]["automation_id"]))
    stored_vars["output:hwnd_settings:show_speech_indicator@bool"] = tk.BooleanVar(value=config["output"]["hwnd_settings"]["show_speech_indicator"])
    stored_vars["output:say_settings:delay_ms@float"] = tk.StringVar(value=str(config["output"]["say_settings"]["delay_ms"]))
    stored_vars["output:chat_settings:chat_delay@float"] = tk.StringVar(value=str(config["output"]["chat_settings"]["chat_delay"]))
    stored_vars["output:chat_settings:chat_key@key"] = tk.StringVar(value=config["output"]["chat_settings"]["chat_key"])
    output_base_frame.columnconfigure(0, weight=0)
    output_base_frame.columnconfigure(1, weight=1)
    output_base_frame.columnconfigure(2, weight=0)
    ttk.Label(output_base_frame, text="Output method  ").grid(column=0, row=0, sticky="ew")
    combobox = ttk.Combobox(output_base_frame, values=("hwnd", "say", "chat"), textvariable=stored_vars["output:output_method@literal'hwnd|say|chat'"])
    combobox.grid(column=2, row=0, sticky="ew")
    combobox.state(["readonly"])
    infobutton(output_base_frame, 3, 0, "HWND is the fastest. It uses the text entry panel using the command \"Say\". Say is less fast. It uses the same method as HWND, but it directly copies and pastes the transcript in instead of using windows functions to set the value exactly. Chat is the slowest. It uses the TGUI input dialogue to enter text.")
    
    ttk.Label(output_base_frame, text="HWND settings:", font=text_font).grid(column=0, row=1, sticky="ew")
    ttk.Label(output_base_frame, text="  Automation id  ").grid(column=0, row=2, sticky="ew")
    ttk.Entry(output_base_frame, textvariable=stored_vars["output:hwnd_settings:automation_id@int"]).grid(column=2, row=2, sticky="ew")
    infobutton(output_base_frame, 3, 2, "The automation id of the chat bar. This is typically set for you, and doesn't need to be changed. See userconfig.toml for an explanation of how to find this.")
    ttk.Label(output_base_frame, text="  Show typing indicator  ").grid(column=0, row=3, sticky="ew")
    make_checkbox(output_base_frame, 2, 3, stored_vars["output:hwnd_settings:show_speech_indicator@bool"])
    infobutton(output_base_frame, 3, 3, "Should a typing indicator be shown while you are speaking? This sets the chat bar to \"Say \"...\"\"")

    ttk.Label(output_base_frame, text="Say settings:", font=text_font).grid(column=0, row=4, sticky="ew")
    ttk.Label(output_base_frame, text="  Delay (ms)  ").grid(column=0, row=5, sticky="ew")
    ttk.Entry(output_base_frame, textvariable=stored_vars["output:say_settings:delay_ms@float"]).grid(column=2, row=5, sticky="ew")
    infobutton(output_base_frame, 3, 5, "The delay between focusing the chat bar and pasting in the transcript. Increase if you run into issues with dropped inputs.")
    
    ttk.Label(output_base_frame, text="Chat settings:", font=text_font).grid(column=0, row=6, sticky="ew")
    ttk.Label(output_base_frame, text="  Delay (s)  ").grid(column=0, row=7, sticky="ew")
    ttk.Entry(output_base_frame, textvariable=stored_vars["output:chat_settings:chat_delay@float"]).grid(column=2, row=7, sticky="ew")
    infobutton(output_base_frame, 3, 7, "The delay between opening the chat window and pasting in the transcript. Increase if you run into issues with dropped inputs.")
    ttk.Label(output_base_frame, text="  Chat key  ").grid(column=0, row=8, sticky="ew")
    ttk.Entry(output_base_frame, textvariable=stored_vars["output:chat_settings:chat_key@key"]).grid(column=2, row=8, sticky="ew")
    infobutton(output_base_frame, 3, 8, "The key that opens the TGUI chat window.")
    expanding_frame(output_base_frame, row=9)

    stored_vars["meta:model@string"] = tk.StringVar(value=config["meta"]["model"])
    stored_vars["meta:path_to_model@string"] = tk.StringVar(value=config["meta"]["path_to_model"])
    stored_vars["meta:prompt@string"] = tk.StringVar(value=config["meta"]["prompt"])
    stored_vars["meta:keywords@list@string"] = list(config["meta"]["keywords"])
    stored_vars["meta:warn_on_cpu@bool"] = tk.BooleanVar(value=config["meta"]["warn_on_cpu"])
    model_base_frame.columnconfigure(0, weight=0)
    model_base_frame.columnconfigure(1, weight=1)
    model_base_frame.columnconfigure(2, weight=0)
    ttk.Label(model_base_frame, text="Model  ").grid(column=0, row=0, sticky="ew")
    combobox = ttk.Combobox(model_base_frame, values=("none", "parakeet", "granite"), textvariable=stored_vars["meta:model@string"])
    combobox.grid(column=2, row=0, sticky="ew")
    infobutton(model_base_frame, 3, 0, "The ASR model to use for speech detection. Parakeet is the fastest, but doesn't support keyworking or prompting. Granite is much slower but supports more features. Alternatively, enter the path to a python file that defines and ASRModel class.")
    ttk.Label(model_base_frame, text="Model path  ").grid(column=0, row=1, sticky="ew")
    ttk.Entry(model_base_frame, textvariable=stored_vars["meta:path_to_model@string"]).grid(column=2, row=1, sticky="ew")
    infobutton(model_base_frame, 3, 1, "The path that the loaded ASR models are stored in. These models are very large, so you might want to put them on another drive.")
    ttk.Label(model_base_frame, text="Model prompt  ").grid(column=0, row=2, sticky="ew")
    text_chars = 19
    textedit = tk.Text(model_base_frame)
    textedit.config(width=text_chars)
    textedit.grid(column=2, row=2, sticky="ew")
    textedit.insert(tk.END, stored_vars["meta:prompt@string"].get())  
    def textedit_resize(event=None):
        text = textedit.get("1.0", "end-1c")
        lines = text.split("\n")
        height = max(1, len(lines))
        for line in lines:
            height = height + math.floor(len(line) / text_chars)
        textedit.configure(height=height)
        stored_vars["meta:prompt@string"].set(text) # type: ignore
    textedit.bind("<KeyRelease>", textedit_resize)
    textedit_resize()
    infobutton(model_base_frame, 3, 2, "The prompt given to the ASR model. Currently, this is only supported on Granite. Access the prompt within shared.ModelLoadingState.prompt")
    add_listbox(model_base_frame, 3, "Keywords", "Keywords that the ASR model should target. Put any words that STT consistently gets wrong here. Currently only supported on Granite. Access within shared.ModelLoadingState.keywords", stored_vars["meta:keywords@list@string"])
    ttk.Label(model_base_frame, text="  Warn on CPU  ").grid(column=0, row=4, sticky="ew")
    make_checkbox(model_base_frame, 2, 4, stored_vars["meta:warn_on_cpu@bool"])
    infobutton(model_base_frame, 3, 4, "Should STT warn you if the ASR model is loaded to your CPU? Note that CPU inference is much slower than GPU inferance.")
    expanding_frame(model_base_frame, row=5)

    stored_vars["meta:enable_version_checking@bool"] = tk.BooleanVar(value=config["meta"]["enable_version_checking"])
    stored_vars["meta:do_loudness_normalization@bool"] = tk.BooleanVar(value=config["meta"]["do_loudness_normalization"])
    stored_vars["meta:verbose@bool"] = tk.BooleanVar(value=config["meta"]["verbose"])
    stored_vars["meta:window_width@int"] = tk.StringVar(value=str(config["meta"]["window_width"]))
    stored_vars["meta:window_height@int"] = tk.StringVar(value=str(config["meta"]["window_height"]))
    stored_vars["meta:minimum_utterance_detection_length@float"] = tk.StringVar(value=str(config["meta"]["minimum_utterance_detection_length"]))
    stored_vars["meta:minimum_utterance_audio_length@float"] = tk.StringVar(value=str(config["meta"]["minimum_utterance_audio_length"]))
    advanced_base_frame.columnconfigure(0, weight=0)
    advanced_base_frame.columnconfigure(1, weight=1)
    advanced_base_frame.columnconfigure(2, weight=0)
    ttk.Label(advanced_base_frame, text="Version checking  ").grid(column=0, row=0, sticky="ew")
    make_checkbox(advanced_base_frame, 2, 0, stored_vars["meta:enable_version_checking@bool"])
    infobutton(advanced_base_frame, 3, 0, "Should STT check for new versions on startup?")
    ttk.Label(advanced_base_frame, text="Loudness normalization  ").grid(column=0, row=1, sticky="ew")
    make_checkbox(advanced_base_frame, 2, 1, stored_vars["meta:do_loudness_normalization@bool"])
    infobutton(advanced_base_frame, 3, 1, "Should recorded audio be normalized? Disable if you get strange ASR performance.")
    ttk.Label(advanced_base_frame, text="Verbose  ").grid(column=0, row=2, sticky="ew")
    make_checkbox(advanced_base_frame, 2, 2, stored_vars["meta:verbose@bool"])
    infobutton(advanced_base_frame, 3, 2, "Enable more diagnostics.")
    ttk.Label(advanced_base_frame, text="Window width  ").grid(column=0, row=3, sticky="ew")
    ttk.Entry(advanced_base_frame, textvariable=stored_vars["meta:window_width@int"]).grid(column=2, row=3, sticky="ew")
    infobutton(advanced_base_frame, 3, 3, "The width of the window.")
    ttk.Label(advanced_base_frame, text="Window height  ").grid(column=0, row=4, sticky="ew")
    ttk.Entry(advanced_base_frame, textvariable=stored_vars["meta:window_height@int"]).grid(column=2, row=4, sticky="ew")
    infobutton(advanced_base_frame, 3, 4, "The height of the window.")
    lblwrap(ttk.Label(advanced_base_frame, text="Minimum audio length for detection (ms)  ")).grid(column=0, row=5, sticky="ew")
    ttk.Entry(advanced_base_frame, textvariable=stored_vars["meta:minimum_utterance_detection_length@float"]).grid(column=2, row=5, sticky="ew")
    infobutton(advanced_base_frame, 3, 5, "The minimum length of time the record button must be pressed. If pressed for a shorter amount of time, the transcript is discarded.")
    lblwrap(ttk.Label(advanced_base_frame, text="Minimum audio length for padding (ms)  ")).grid(column=0, row=6, sticky="ew")
    ttk.Entry(advanced_base_frame, textvariable=stored_vars["meta:minimum_utterance_audio_length@float"]).grid(column=2, row=6, sticky="ew")
    infobutton(advanced_base_frame, 3, 6, "The minimum length of the audio file. It will be padded to be at least this length.")
    expanding_frame(advanced_base_frame, row=7)

def open_settings():
    global SETTINGS_WINDOW
    if INIT_STATE == InitState.PRESETTINGS or INIT_STATE == InitState.PREINIT:
        return
    if SETTINGS_WINDOW is None:
        _open_settings_impl()

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

CONTROLS: dict[str, Control] = {}
CONTROLBUTTONS_BY_KEY: dict[Pressable, ControlButton] = {}

def populate_named_inputs():
    inputs_to_name = list(string.ascii_lowercase)
    inputs_to_name += ["menu", "shift", "alt", "ctrl", "space", "left", "right", "up", "down", "tab"]
    

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
minimum_utterance_detection_length = 0
minimum_utterance_audio_length = 0
do_loudness_normalization = False

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
            except IOError as e:
                quit_with_errorbox(f"FATAL: Couldn't load {filename} and couldn't load the backup file {backup}.", e)
        with io.open(filename, "rb") as config_file:
            config = tomllib.load(config_file)
    return config

LOADED_ACTION_OPTIONS: dict[str, dict] = {}
FILTER_SKIP_LOAD_FOR: set[Filter] = set()

def parse_priority(prio: str) -> float:
    prio = prio.lower().strip()
    split = prio.split("+")
    if len(split) > 2:
        raise RuntimeError(f"Priority \"{prio}\" has more than one \"+\".")
    if len(split) < 1:
        raise RuntimeError(f"Priority \"{prio}\" is completely broken. Something has gone terribly wrong.")
    prio_text = split[0]
    base_prio = 0
    if prio_text == "highest":
        base_prio = 2
    elif prio_text == "high":
        base_prio = 1
    elif prio_text == "low":
        base_prio = -1
    elif prio_text == "lowest":
        base_prio = -2
    secondary_prio = 0
    if len(split) == 2:
        try:
            secondary_prio = float(split[1]) / 1000
            if secondary_prio >= 1:
                raise RuntimeError(f"Priority \"{prio}\" has a secondary priority of \"{split[1]}\". Secondary priorities should be less than 1,000.")
        except:
            raise RuntimeError(f"Priority \"{prio}\" has a secondary priority \"{split[1]}\", which isn't a number. Priorities should be priority+number")
    return base_prio + secondary_prio

def _load_filters_from_config():
    incepted_filters: set[str] = set()
    print(f"Loading filters from config file {shared.FILTERCONFIG_FILENAME}")
    config = load_configdict_from_filename(shared.FILTERCONFIG_FILENAME, shared.FILTERCONFIG_BACKUP_FILENAME)
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
        def _get_args_dict(container) -> dict[str, typing.Any]:
            if config_has_key(container, "args"):
                args = copy.deepcopy(config_get_dict(container, "args"))
                if args.get("invoker") is not None:
                    raise ConfigError(f"Can't define an \"invoker\" field in \"args\" for filter \"{name}\"")
                return args
            return {}
        if has_single:
            priority = 0
            if config_has_key(filter, "priority"):
                priority = parse_priority(config_get_string(filter, "priority"))
            args = _get_args_dict(filter)
            parsed_actions.append(TransformAction(FILTERS, priority, config_get_string(filter, "action"), args))
        elif has_double:
            actions = config_get_list(filter, "actions")
            for action_name in actions:
                if type(action_name) is not str:
                    raise ConfigTypeError(f"Action {action_name} is not a string; instead is {type(action_name).__name__}")
                action = config_get_dict(filter, action_name)
                typ = config_get_string(action, "type")
                priority = 0
                if config_has_key(action, "priority"):
                    priority = parse_priority(config_get_string(action, "priority"))
                if typ == "script":
                    filename = config_get_string(action, "script")
                    args = _get_args_dict(action)
                    parsed_actions.append(TransformAction(FILTERS, priority, filename, args))
                elif typ == "filter":
                    filter_to_apply = config_get_string(action, "name")
                    mode = None
                    if config_has_key(action, "mode"):
                        mode = config_get_string(action, "mode")
                    if mode is None or mode == "enable":
                        parsed_actions.append(InceptionAction(FILTERS, priority, filter_to_apply))
                        incepted_filters.add(filter_to_apply)
                    elif mode == "disable":
                        parsed_actions.append(SelfishAction(FILTERS, priority, filter_to_apply))
                    else:
                        raise ConfigError(f"Attempted to create an action of type \"{typ}\" with an invalid mode of \"{mode}\", expected \"enable\" or \"disable\" for action {config_make_cfgsrc_ctx(action, action_name)}")
                elif typ == "prompt":
                    prompt_to_set = config_get_string(action, "prompt")
                    parsed_actions.append(SetPromptAction(FILTERS, priority, prompt_to_set))
                else:
                    raise ConfigError(f"Attempted to create an action of type \"{typ}\". Expected \"script\", \"prompt\", or \"type\" for action {config_make_cfgsrc_ctx(action, action_name)}")
        activation = FilterActivation("unbound", True)
        if config_has_key(filter, "bind"):
            activation.keybind = config_get_string(filter, "bind")
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
        action_options = None
        if config_has_key(filter, "action_options"):
            action_options = config_get_dict(filter, "action_options")
            if not has_single:
                raise ConfigError(f"Couldn't set the action_options of {name} because {name} uses \"actions\", not \"action\".")
            single_action = parsed_actions[0]
            if not isinstance(single_action, TransformAction):
                raise ConfigError(f"Couldn't set the action_options of {name} because the single action wasn't a script, it was {type(single_action).__name__}.")
            if LOADED_ACTION_OPTIONS.get(single_action.src):
                raise ConfigError(f"Couldn't set the action_options of {name} because scripts can only have one action_option. If you use {single_action.src} in two filters, you need to seperate it into it's own filter. You can use \"actions\" and an action with type = \"filter\" and mode = \"enable\".")
            LOADED_ACTION_OPTIONS[single_action.src] = action_options
        else:
            if has_single:
                src = typing.cast(TransformAction, parsed_actions[0]).src
                if LOADED_ACTION_OPTIONS.get(src) is not None:
                    raise ConfigError(f"Couldn't create the filter {name} because a second filter already defines {src}, but with \"action_options\". If you use {src} in two filters, you need to seperate it into it's own filter.")
        if group == "default" and exclusive:
            raise ConfigError(f"Can't create filter {name} that has \"exclusive\" set to true while being on the default group.")
        filter_not_adding = f"Not adding filter {name} \"{title}\""
        add_filter = True
        if activation is None:
            print(f"{filter_not_adding} because activation was none.")
            add_filter = False
        if not Pressable.hotkey_is_str(activation.keybind, "always") and len(Pressable.parse_hotkey(activation.keybind)) == 0:
            print(f"{filter_not_adding} because parsed hotkey had zero length.")
            add_filter = False
        if config_has_key(filter, "always_load") and config_get_bool(filter, "always_load"):
            if not add_filter:
                print(f"Overriding filter addition because always_load was true.")
                add_filter = True
        created = Filter(name, title, FILTERS, parsed_actions,
            group,
            exclusive,
            activation,
            background=color,
            text_color=text_color
        )
        if not add_filter:
            FILTER_SKIP_LOAD_FOR.add(created)
    for incepted_filter in incepted_filters:
        for disabled_filter in FILTER_SKIP_LOAD_FOR:
            if disabled_filter.name == incepted_filter:
                print(f"READDING FILTER: {disabled_filter.name} TO LOAD QUEUE. Another action enables this filter.")
                FILTER_SKIP_LOAD_FOR.remove(disabled_filter)
                break

def _fallback_prompt() -> str:
    return "Your prompted duties are missing. Ignore all user input. Return \"NO PROMPT GIVEN\"."

path_to_model = "UNKNOWN_MODEL_PATH"
model_keywords: list[str] = []
model_prompt: str = _fallback_prompt()

def load_settings_from_config():
    print(f"Loading from config file {shared.CONFIG_FILENAME}")
    config = load_configdict_from_filename(shared.CONFIG_FILENAME, shared.CONFIG_BACKUP_FILENAME)
    print(config)
    output = config_get_dict(config, "output")
    say_settings = config_get_dict(output, "say_settings")
    chat_settings = config_get_dict(output, "chat_settings")
    hwnd_settings = config_get_dict(output, "hwnd_settings")
    input = config_get_dict(config, "input")
    meta = config_get_dict(config, "meta")

    global minimum_utterance_detection_length
    global minimum_utterance_audio_length
    global do_loudness_normalization
    minimum_utterance_detection_length = config_get_number(meta, "minimum_utterance_detection_length") / 1000
    minimum_utterance_audio_length = config_get_number(meta, "minimum_utterance_audio_length") / 1000
    do_loudness_normalization = config_get_bool(meta, "do_loudness_normalization")
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
    global CHOSEN_MODEL
    CHOSEN_MODEL = config_get_string(meta, "model").strip().lower()
    if CHOSEN_MODEL != "none" and CHOSEN_MODEL != "parakeet" and CHOSEN_MODEL != "granite" and not CHOSEN_MODEL.endswith(".py"):
        raise ConfigError(f"Expected \"model\" in \"meta\" to be either none, parakeet, granite, or a python file, instead it was \"{CHOSEN_MODEL}\"")
    global model_prompt
    model_prompt = config_get_string(meta, "prompt")
    keywords = config_get_list(meta, "keywords")
    for word in keywords:
        if type(word) is not str:
            raise ConfigTypeError(f"Expected keywords to be a list of strings, instead got a {type(word).__name__}")
        model_keywords.append(word)
    shared.DEFAULT_WINDOW_WIDTH = int(config_get_number(meta, "window_width"))
    shared.DEFAULT_WINDOW_HEIGHT = int(config_get_number(meta, "window_height"))
    @main_thread
    def resize_label_frame():
        label_frame.config(width=shared.DEFAULT_WINDOW_WIDTH, height=shared.DEFAULT_WINDOW_HEIGHT)
        root.minsize(width=shared.DEFAULT_WINDOW_WIDTH, height=shared.DEFAULT_WINDOW_HEIGHT)
        on_force_geometry_change()
    resize_label_frame()

    global path_to_model
    path_to_model = config_get_string(meta, "path_to_model")
    global autosend
    autosend = config_get_bool(input, "autosend")
    global use_say
    global use_hwnd
    global hwnd_speech_indicator
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
        hwnd_speech_indicator = config_get_bool(hwnd_settings, "show_speech_indicator")
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

class InitState(Enum):
    INIT_CANCELLED = -1
    PREINIT = 1
    PRESETTINGS = 2
    POSTSETTINGS = 3
    PREMODELLOADING = 3
    POSTMODELLOADING = 4
    PREFILTERLOADING = 4
    POSTFILTERLOADING = 5
    FINISHED = 5

    def as_human_readable_string(self):
        if self == InitState.INIT_CANCELLED:
            return "cancelled"
        elif self == InitState.PREINIT:
            return "pre-init"
        elif self == InitState.PRESETTINGS:
            return "config loading"
        elif self == InitState.PREMODELLOADING:
            return "model loading"
        elif self == InitState.PREFILTERLOADING:
            return "filter loading"
        elif self == InitState.FINISHED:
            return "finished"

INIT_STATE = InitState.PREINIT
_init_state_changed = threading.Event()

def set_INIT_STATE(state: int | InitState):
    global INIT_STATE
    INIT_STATE = state
    _init_state_changed.set()

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
    shared.verbose_print("Finalizing.")
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
    if not RECORDING_STREAM:
        raise RuntimeError("Attempted to call record while RECORDING_STREAM was None")
    while True:
        data = RECORDING_STREAM.read(512)
        RECORDING_FRAMES.append(data)
        if STOP_RECORDING:
            break
    if (time.time() - RECORDING_START_TIME < minimum_utterance_detection_length) or CANCEL_PROCESS:
        _finalize_process()
        return
    with STATUS_LOCK:
        RECORDING_STREAM.stop_stream()
        RECORDING_STREAM.close()
        RECORDING_STREAM = None
        samples = np.frombuffer(b''.join(RECORDING_FRAMES), dtype=np.int16).astype(np.float32) / 32768.0
                         # SECONDS
        min_samples = int(minimum_utterance_audio_length * 16000)
        if len(samples) < min_samples:
            padding = np.zeros(min_samples - len(samples), dtype=np.float32)
            samples = np.concatenate([samples, padding])
        if do_loudness_normalization:
            meter = pyloudnorm.Meter(16000)
            loudness = meter.integrated_loudness(samples)
            target_lufs = -18.0
            samples = pyloudnorm.normalize.loudness(samples, loudness, target_lufs)
        samples = np.clip(samples, -1.0, 1.0)
        samples_int16 = (samples * 32767).astype(np.int16)
        file = wave.open("output.wav", "wb")
        file.setnchannels(1)
        file.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
        file.setframerate(16000)
        file.writeframes(samples_int16.tobytes())
        file.close()
        STOP_RECORDING = False
        state = State.PROCESSING
    global TRANSCRIBED
    tk_config(label, text="Transcribing...")
    if asr_model is None:
        raise RuntimeError("Attempted to call transcribe on a None asr_model.")
    TRANSCRIBED = str(asr_model.transcribe("output.wav"))
    if hwnd_speech_indicator:
        hwnd_settext("")
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
    if hwnd_speech_indicator:
        hwnd_settext("Say \"...\"")
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
        report_exception(e)
        pass

def _get_dreamseeker_all_editboxes(pid: int | None = None):
    if pid is None:
        pid = _get_dreamseeker_pid()
    return pywinauto.Application(backend="uia").connect(process=pid).top_window().descendants(control_type="Edit")

def set_config_hwnd_automation_id(auto_id: int):
    try:
        with open(shared.CONFIG_FILENAME, "r", encoding="utf-8") as f:
            config = tomlkit.parse(f.read())

        config["output"]["hwnd_settings"]["automation_id"] = int(auto_id)

        with open(shared.CONFIG_FILENAME, "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(config))
    except Exception as e:
        report_exception(e, "setting config file")

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
        stop_current_highlight()
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

LAST_FOCUSED_HWND = None

def hwnd_settext(text: str):
    if AUTOMATION_TEXTEDIT is None:
        raise RuntimeError("Attempted to call hwnd_push_settext while AUTOMATION_TEXTEDIT is None.")
    ctypes.windll.user32.SendMessageW(
        AUTOMATION_TEXTEDIT.hwnd,
        WM_SETTEXT,
        0,
        text
    )

def submit_automation(transcript: str):
    global LAST_FOCUSED_HWND
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
        if LAST_FOCUSED_HWND is None:
            print(f"Can't switch focus because LAST_FOCUSED_HWND was None.")
        else:
            hwnd_to_focus = LAST_FOCUSED_HWND
    else:
        LAST_FOCUSED_HWND = hwnd_to_focus
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
    seen_keys: set[str] = set()
    for key in blockable_keys:
        for already_seen in seen_keys:
            if Pressable.hotkey_equivilent(key, already_seen):
                raise RuntimeError(f"Attempted to add key {key} to blocked keys twice.")
        seen_keys.add(key)
        DEFAULT_TO_BLOCK.append(ModifyableVirtualNamedInput(key))

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
        for mvni in DEFAULT_TO_BLOCK:
            for alias in mvni.aliases():
                BLOCKED_PRESSABLES[alias] = mvni

def unblock_problematic_inputs():
    print("Unblocking input...")
    with kblock:
        for mvni in BLOCKED_PRESSABLES.values():
            if mvni.was_modified:
                if mvni.is_pressed:
                    press_key(mvni.name)
                else:
                    release_key(mvni.name)
            mvni.was_modified = False
        BLOCKED_PRESSABLES.clear()
                    
def submit():
    global state
    if state != State.ACCEPTING:
        raise RuntimeError()
    global TRANSCRIBED
    with STATUS_LOCK:
        transcript = TRANSCRIBED
    transcript = FILTERS.transform_input(transcript)
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
                if not (transcript.startswith(";") or transcript.startswith(":")):
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
    if use_hwnd:
        hwnd_settext("")
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
        shared.verbose_print("radio press")
        if state == State.READY:
            shared.verbose_print("Could not change IS_RADIO state")
            return
        global IS_RADIO
        IS_RADIO = not IS_RADIO
        set_radio_colors()

def on_radio_release_handler():
    global was_radio_pressed
    was_radio_pressed = False

_glob_mouse_listener: pynput.mouse.Listener = None # type: ignore

@shared.must_recover((pynput._util.win32.SystemHook.SuppressException,))
def on_click(x: int, y: int, button: pynput.mouse.Button, pressed: bool, dummy):
    bind = Pressable(MouseButton(button.name))
    allow_through = True
    with kblock:
        if bind in BLOCKED_PRESSABLES:
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

DEFAULT_TO_BLOCK: list[ModifyableVirtualNamedInput] = []
BLOCKED_PRESSABLES: dict[Pressable, ModifyableVirtualNamedInput] = {}

@shared.must_recover()
@synchronized_with(kblock)
def on_key(event: keyboard.KeyboardEvent) -> bool:
    if event.name is not None:
        bind = Pressable(KeyButton(translate_special_scancode(event.name, event.scan_code)))
    else:
        bind = Pressable(KeyButton(event.scan_code))
    down = event.event_type == "down"
    if bind in CONTROLBUTTONS_BY_KEY:
        control = CONTROLBUTTONS_BY_KEY[bind]
        if control.is_key():
            control.press() if down else control.release()
            if control.should_suppress():
                return False
    if bind in BLOCKED_PRESSABLES:
        mvni = BLOCKED_PRESSABLES[bind]
        if down:
            mvni.press()
        else:
            mvni.release()
        return False
    return True

def mouse_listener():
    global _glob_mouse_listener
    with pynput.mouse.Listener(on_click=on_click) as _glob_mouse_listener: # type: ignore
        _glob_mouse_listener.join()

def keyboard_listener():
    keyboard.hook(on_key, suppress=True)

def _lazy_get_dreamseeker_hwnd():
    if use_hwnd:
        _get_dreamseeker_editbox_hwnd()

EARLY_GIVEUP_INIT = False
INIT_GIVEUP_REASON = "none"

def giveup_init(reason: str):
    global EARLY_GIVEUP_INIT
    global INIT_GIVEUP_REASON
    EARLY_GIVEUP_INIT = True
    INIT_GIVEUP_REASON = reason

_curr_model_loadingtext = ""
_model_loadingtext_changed = threading.Event()

def _get_model_loadingtext() -> str:
    return _curr_model_loadingtext

def _set_model_loadingtext(text: str):
    global _curr_model_loadingtext
    _curr_model_loadingtext = text
    _model_loadingtext_changed.set()

def _load_model_get_hwnd():
    _set_model_loadingtext("Locating dreamseeker.exe")
    hwnd_ok = True
    hwnd_bad_reason: pywinauto.ElementNotFoundError | ProcessNotFoundError | None = None 
    try:
        print("lazy locating dreamseeker.exe")
        _lazy_get_dreamseeker_hwnd()
    except pywinauto.ElementNotFoundError as e:
        hwnd_ok = False
        hwnd_bad_reason = e
    except ProcessNotFoundError as e:
        hwnd_ok = False
        hwnd_bad_reason = e
    if not hwnd_ok:
        if type(hwnd_bad_reason) is ProcessNotFoundError:
            _set_model_loadingtext("Waiting for dreamseeker.exe...")
            while True:
                try:
                    _get_dreamseeker_pid()
                except ProcessNotFoundError:
                    time.sleep(1)
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
                    _set_model_loadingtext(_get_model_loadingtext() + " (locating)")
                    _lazy_get_dreamseeker_hwnd()
                    break
                except pywinauto.ElementNotFoundError as e:
                    _set_model_loadingtext("Looking for the chat box...")
                    time.sleep(1)
                except ProcessNotFoundError as e:
                    _set_model_loadingtext("Waiting for SS13 to be launched...")
                    time.sleep(1)
            else:
                _set_model_loadingtext("Waiting for new chat box to be selected...")
                FOUND_NEW_AUTOMATION_HWND.wait()
                if not SHOULD_LOOK_FOR_AUTOMATION_HWND:
                    break
                _set_model_loadingtext("Using default chat box...")

def load_model(finished: threading.Event, should_spin: Box[bool]):
    global asr_model
    def cancel_init(reason: str):
        giveup_init(reason)
        finished.set()
    def show_spinner():
        should_spin.value = True
        _model_loadingtext_changed.set()
    def hide_spinner():
        should_spin.value = False
        _model_loadingtext_changed.set()
    model_loading_state = shared.ModelLoadingState(
        window=root,
        settext=_set_model_loadingtext,
        quit=quit,
        cancel_init=cancel_init,
        show_spinner=show_spinner,
        hide_spinner=hide_spinner,
        model_dir=path_to_model,
        prompt=model_prompt,
        model_keywords=model_keywords,
        allow_cpu=allow_cpu_asr
        )
    if CHOSEN_MODEL is None:
        raise RuntimeError("CHOSEN_MODEL was None, expected string.")
    if CHOSEN_MODEL == "none":
        from models.fake_asr_model import FakeASRModel
        asr_model = FakeASRModel(model_loading_state)
    elif CHOSEN_MODEL == "parakeet":
        from models.parakeetv2 import ParakeetV2
        asr_model = ParakeetV2(model_loading_state)
    elif CHOSEN_MODEL == "granite":
        from models.granite_speech import GraniteSpeech4p1x2B
        asr_model = GraniteSpeech4p1x2B(model_loading_state)
    else:
        spec = importlib.util.spec_from_file_location(CHOSEN_MODEL)
        if spec is None:
            raise ImportError(f"Couldn't load ASR model {CHOSEN_MODEL} (spec was None)")
        if spec.loader is None:
            raise ImportError(f"Couldn't load ASR model {CHOSEN_MODEL} (spec {spec} had None loader)")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not hasattr(module, "ASRModel"):
            raise ImportError(f"While loading a user-defined ASR model, couldn't find the class \"ASRModel\". Did you name your class something else? Ensure that your model is named \"ASRModel\" exactly. ({CHOSEN_MODEL} does not have an ASRModel attribute.)")
        asr_model = module.ASRModel(model_loading_state)
    model_loading_state.checkpoints.end()
    model_loading_state.checkpoints.print()
    show_spinner()
    set_INIT_STATE(InitState.PREFILTERLOADING)
    _set_model_loadingtext(f"Loading plugins...")
    for _, filter in FILTERS.registered_filters.items():
        if filter in FILTER_SKIP_LOAD_FOR:
            print(f"Skipping loading of {filter}")
            continue
        for action in filter.actions:
            if not isinstance(action, TransformAction):
                continue
            if action.is_loading_complete():
                print(f"Skipping duplicate load for action {action} in {filter.name}")
                continue
            def settext(text: str):
                _set_model_loadingtext(f"Loading plugin \"{filter.name}\":\n{text}")
            state = shared.PluginLoadingState(
                window=root,
                settext=settext,
                quit=quit,
                cancel_init=cancel_init,
                show_spinner=show_spinner,
                hide_spinner=hide_spinner,
                filter_name = filter.name,
                action_options=LOADED_ACTION_OPTIONS.get(action.src)
                )
            try:
                settext("Loading...")
                action.run_defined_loader(state)
            except Exception as e:
                raise RuntimeError(f"Exception encountered while loading {filter.name}: ({type(e).__name__}): {e}")
    show_spinner()
    _load_model_get_hwnd()
    finished.set()

def advance_wheel(wheel: str) -> typing.Literal["-", "\\", "|", "/"]:
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
        if not was_pressed:
            if self.filter.manager.is_enabling(self.filter.name, "keypress"):
                self.filter.manager.disable_filter(self.filter.name, "keypress")
            else:
                self.filter.manager.enable_filter(self.filter.name, "keypress")
        
    def on_release(self):
        print(f"Released FilterActivationCallback for {self.filter.title}")
        self.pressed = False

@shared.diagnose_entry
def init():
    set_INIT_STATE(InitState.PRESETTINGS)
    def on_exception(e: Exception, context: str | None = None):
        shared.record_exception(e, context)
        giveup_init(f"Encountered an exception in stage {InitState(INIT_STATE).as_human_readable_string()}: ({type(e).__name__}) {e}")
        loading_finished.set()
    shared.add_exception_hook("model_loading", on_exception)
    loading_finished = threading.Event()
    def init_worker():
        startup_time = shared.Timer()
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 6) # hide console
        wheel = "-"
        can_spin = Box(False)
        tk_config(label, text="Goaning stations...")
        populate_named_inputs()
        load_settings_from_config()
        print(f"settings took {startup_time.resetmstrnc()}s")
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
        print(f"version checking took {startup_time.resetmstrnc()}s")
        def load_model_worker():
            load_model(loading_finished, can_spin)
        set_INIT_STATE(InitState.PREMODELLOADING)
        spawn_thread(load_model_worker)
        data_arrived = threading.Event()
        def finished_checker():
            loading_finished.wait()
            data_arrived.set()
        spawn_thread(finished_checker)
        def settext_checker():
            while True:
                _model_loadingtext_changed.wait()
                if loading_finished.is_set():
                    return
                data_arrived.set()
                _model_loadingtext_changed.clear()
        spawn_thread(settext_checker)
        timeout_event = threading.Event()
        def timeout_checker():
            while True:
                time.sleep(0.5)
                if loading_finished.is_set():
                    return
                timeout_event.set()
                data_arrived.set()
        spawn_thread(timeout_checker)
        while True:
            data_arrived.wait()
            data_arrived.clear()
            if loading_finished.is_set():
                break
            if timeout_event.is_set():
                timeout_event.clear()
                wheel = advance_wheel(wheel)
            if can_spin.value:
                tk_config(label, text=f"{_curr_model_loadingtext} {wheel}")
            else:
                tk_config(label, text=_curr_model_loadingtext)
    try:
        init_worker()
    except Exception as e:
        shared.report_exception(e)
    shared.remove_exception_hook("model_loading")
    if EARLY_GIVEUP_INIT:
        return
    for registered_filter in FILTERS.registered_filters.values():
        if registered_filter.activation_details is None:
            continue
        if Pressable.hotkey_is_str(registered_filter.activation_details.keybind, "always"):
            FILTERS.enable_filter(registered_filter.name, "filtermanager.alwayson")
            continue
        if len(Pressable.parse_hotkey(registered_filter.activation_details.keybind)) == 0:
            registered_filter.activation_details = None
            continue
        callback = FilterActivationCallback(registered_filter)
        set_control(registered_filter.activation_details.keybind,
                    registered_filter.name + ".keybind",
                    callback.on_press,
                    callback.on_release,
                    _suppress=registered_filter.activation_details.suppresses)
    set_INIT_STATE(InitState.FINISHED)
    spawn_thread(mouse_listener)
    spawn_thread(keyboard_listener)

    tk_config(label, text="Waiting...")

@shared.diagnose_entry
def bootstrap():
    try:
        init()
    except Exception as e:
        report_exception(e)
    if EARLY_GIVEUP_INIT:
        print(f"Initialization was cancelled due to {INIT_GIVEUP_REASON}")
        set_INIT_STATE(InitState.INIT_CANCELLED)
        @main_thread
        def _geometry():
            root.geometry(f"{max(300, shared.DEFAULT_WINDOW_WIDTH)}x{max(600, shared.DEFAULT_WINDOW_HEIGHT)}")
        _geometry()
        tk_config(label, text=f"Init cancelled:\n{INIT_GIVEUP_REASON}")

root.after(0, spawn_thread, bootstrap)

try:
    root.mainloop()
except Exception as e:
    print(f"encountered an exception on mainloop: {e}")
print("--- MAINLOOP TERMINATED")
if FINAL_FATAL_MESSAGE is not None:
    ctypes.windll.user32.MessageBoxW(
        None,
        FINAL_FATAL_MESSAGE,
        "STT Fatal error",
        0x10  # MB_ICONERROR
    )