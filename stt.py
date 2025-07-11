import tkinter as tk
import configparser
import threading
import pynput
import string
import pyaudio
import time
import wave
import typing
import pyperclip
import keyboard
import mouse
import os
import io
import re
import requests
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
        message = f"Full stacktrace available at current.log and {filename} for exception {type(exception)}:\n{exception}"
        messagebox.showwarning("Exception encountered", message=message)
    except:
        print("FATAL ERROR.")
        quit()

def _thread_ctx(func: typing.Callable, context: str, args: list = []):
    try:
        global thread_context
        thread_context.value = context
        verbose_print("calling", func, "with", args)
        func(*args)
    except Exception as e:
        root.after(0, _global_exception_handler, e, context + ''.join(traceback.format_tb(e.__traceback__)))
        
_to_filter_functions = ["_thread_ctx", "run", "_bootstrap_inner", "_bootstrap", "mainloop", "__call__", "callit"]

def filtered_traceback() -> str:
    stack = traceback.extract_stack()
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


audio = pyaudio.PyAudio()

path_to_model = ""
asr_model = None
config = configparser.ConfigParser()
config.read("config.ini")

class Box:
    def __init__(self, value):
        self.value = value

class ControlButton:
    def __init__(self, control: str, is_mouse: bool):
        self.control = control
        self._is_mouse = is_mouse
        self._is_pressed = False
        self.lock = threading.Lock()

    def press(self):
        with self.lock:
            self._is_pressed = True
    
    def release(self):
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

activate_button: ControlButton
reject_button: ControlButton
radio_button: ControlButton
autosend = False
use_say = False
allow_version_checking = False
chat_delay = 0
chat_key = ""
radio_key = ""

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

if True:
    activate_name = config.get("Input", "activate")
    reject_name = config.get("Input", "reject")
    autosend_str = config.get("Input", "autosend")
    radio_str = config.get("Input", "radio_modifier")
    use_say_str = config.get("Output", "use_say")
    chat_delay_str = config.get("Output", "chat_delay")
    chat_key = config.get("Output", "chat_key")
    radio_key = config.get("Output", "radio_key")
    path_to_model = config.get("Meta", "path_to_model")
    verbose = True if config.get("Meta", "verbose") == "true" else False
    allow_version_checking = False if config.get("Meta", "disable_version_checking") == "true" else True
    if os.path.exists("dbg.lock"):
        verbose = True
    if path_to_model.startswith('"') and path_to_model.endswith('"'):
        path_to_model = path_to_model[1:-1]
    autosend = (autosend_str == "true")
    use_say = (use_say_str == "true")
    chat_delay = float(chat_delay_str)
    activate_button = ControlButton(activate_name, is_mousebutton(activate_name))
    reject_button = ControlButton(reject_name, is_mousebutton(reject_name))
    radio_button = ControlButton(radio_str, is_mousebutton(radio_str))
    verbose_print(f"Configured radio key is {radio_str}")
    if not is_input(activate_name):
        raise RuntimeError(f"Activate keybind {activate_name} is not an input.")
    if not is_input(reject_name):
        raise RuntimeError(f"Reject keybind {reject_name} is not an input.")
    if not is_input(radio_str):
        raise RuntimeError(f"Reject keybind {radio_str} is not an input.")

if allow_version_checking:
    current = current_version()
    latest = latest_version()
    if version_greater(latest, current):
        spawn_thread(messagebox.showinfo, ["New Version Available", f"New version available! You are on {current}, but latest version is {latest}!\nDisable version checking in the config.ini file."])

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
    control = radio_button.control.removesuffix("_l").removesuffix("_r")
    if radio_button.is_key():
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

blockable_keys = ['w', 'a', 's', 'd', 'space']
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

def submit_chat(transcript: str, radio: bool):
    pyperclip.copy(transcript)
    key_to_press = radio_key if radio else chat_key
    controller.press(key_to_press)
    controller.release(key_to_press)
    time.sleep(chat_delay)
    with controller.pressed(pynput.keyboard.Key.ctrl):
        controller.press('v')
        controller.release('v')
    time.sleep(0.1)
    controller.press(pynput.keyboard.Key.enter)
    controller.release(pynput.keyboard.Key.enter)
    time.sleep(0.1)

def submit_say(transcript: str, radio: bool):
    if radio:
        pyperclip.copy(f"Say \"; {transcript}\"")
    else:
        pyperclip.copy(f"Say \"{transcript}\"")
    controller.press(pynput.keyboard.Key.tab)
    controller.release(pynput.keyboard.Key.tab)
    with controller.pressed(pynput.keyboard.Key.ctrl):
        controller.press('v')
        controller.release('v')
    controller.press(pynput.keyboard.Key.enter)
    controller.release(pynput.keyboard.Key.enter)
    controller.press(pynput.keyboard.Key.tab)
    controller.release(pynput.keyboard.Key.tab)

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
    hook = keyboard.hook(key_filter, True)
    radio = IS_RADIO
    if radio:
        label_background.config_and_apply(bg="light blue")(lambda obj: obj.config(bg="white"), 1)
    if use_say:
        submit_say(transcript, radio)
    else:
        submit_chat(transcript, radio)
    keyboard.unhook(hook)
    for key, value in pressed_keys.items():
        if value:
            keyboard.press(key)
        else:
            keyboard.release(key)

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
            if not activate_button.is_pressed():
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

def on_activate_press():
    verbose_print("Activate pressed")
    if activate_button.is_pressed():
        return
    activate_button.press()
    spawn_thread(on_activate_press_handler)

def on_activate_release():
    verbose_print("Activate released")
    activate_button.release()
    spawn_thread(on_activate_release_handler)

def on_reject_press():
    verbose_print("Reject press")
    if reject_button.is_pressed():
        return
    reject_button.press()
    spawn_thread(on_reject_press_handler)

def on_reject_release():
    verbose_print("Reject release")
    reject_button.release()
    spawn_thread(on_reject_release_handler)

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

def on_radio_press():
    spawn_thread(on_radio_press_handler)

def on_radio_release():
    global was_radio_pressed
    was_radio_pressed = False
    

def on_click(x: int, y: int, button: pynput.mouse.Button, pressed: bool):
    if activate_button.is_mouse() and activate_button.control == button.name:
        on_activate_press() if pressed else on_activate_release()
    if reject_button.is_mouse() and reject_button.control == button.name:
        on_reject_press() if pressed else on_reject_release()
    if radio_button.is_mouse() and radio_button.control == button.name:
        on_radio_press() if pressed else on_radio_release()

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
    if activate_button.is_key() and activate_button.control == key:
        on_activate_press()
    if reject_button.is_key() and reject_button.control == key:
        on_reject_press()
    if radio_button.is_key() and radio_button.control == key:
        on_radio_press()

def on_key_release(key_raw: pynput.keyboard.Key | pynput.keyboard.KeyCode | None):
    key = key_press_key_to_string(key_raw)
    if activate_button.is_key() and activate_button.control == key:
        on_activate_release()
    if reject_button.is_key() and reject_button.control == key:
        on_reject_release()
    if radio_button.is_key() and radio_button.control == key:
        on_radio_release()

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

def init():
    wheel = "-"
    loading_finished = Box(False)
    can_spin = Box(False)
    loading_text = Box("Goaning stations...")
    label.config(text=loading_text.value)
    spawn_thread(load_model, args=[loading_finished, can_spin, loading_text])
    while not loading_finished.value:
        while can_spin.value and not loading_finished.value:
            wheel = advance_wheel(wheel)
            label.config(text=loading_text.value+" "+wheel)
            time.sleep(0.5)
        time.sleep(0.5)
    spawn_thread(mouse_listener)
    spawn_thread(keyboard_listener)
    label.config(text="Waiting...")

root.after(0, spawn_thread, init)

root.mainloop()
