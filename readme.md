# Description
Simple speech-to-text python program for Space Station 13.<br/>
Captures your microphone input, converts it to text, and then sends it in game.<br/>
You can add simple filters to the text to add emotion.<br/>
For example, give yourself an accent, or talk on a departmental radio!<br/>

# Installation
## Dependencies:
 - Windows
 - 6GB free space. 2GB can be allocated on a separate drive.
## Installation:
1. Download a release from github
2. Extract the zip to anywhere you like
3. Run setup.bat and wait for the installation to finish
4. Run run.bat
5. Click the settings gear icon to change your settings or for help
6. Press "allow" to download the speech recognition model
## Removal
To remove STT, just delete the folder you put it in! STT is entirely self-contained (except for the .NET runtime, if you choose to install it.)

# Usage
1. Run using the `run.bat` script.<br/>
2. Choose your settings when prompted.<br/>
3. If it's your first time, a popup will appear asking if you want to download from HF hub. This is the actual speech recognition model that you need to use STT, so press "allow"<br/>
4. Hold the `activate` key (defaults to mouse4) to record.<br/>
5. Release to transcribe and send in-game.<br/>
6. Press the settings gear or edit `userconfig.toml` to change keybinds, speech recognition model type, or anything else.<br/>
7. Edit `filters.toml` to create your own filters.<br/>

# Plugins
STT allows users to define their own text post-processing scripts to modify the generated transcripts before sending.<br/>
Plugins are toggleable with keybinds or by other plugins.<br/>
See `examplefilters.toml` for an example of an "angry" plugin. It uppercases all of your text and replaces the final punctuation with "!!!" to change the tone of any message to angry.<br/>
Plugins are not sandboxed and are unrestricted.<br/>

# Extensibility
STT allows you to add your own speech recognition model or add extra post processing effects (including passing transcripts through LLMs!)<br/>
Additionally, since STT is contained in two large files, editing the source is a breeze. Changing chat submission modes is as easy as modifying the submit_chat, submit_say, or submit_automation functions in stt.py.<br/>
Examples of the ASR API can be found in `data/models/parakeetv2.py` (the default ASR model) and `data/models/granite_speech.py`.<br/>
Examples of the filter API can be found in `data/filters`. `qwen_postprocess.py` is the most complicated and makes use of `on_load` hooks and custom arguments, see it for an example of a complicated plugin.<br/>
In the future, STT may support custom transcript sending modes if adding more gets out of hand.<br/>

# Building
This program contains prebuilt dlls for the SS14 integration. To build them from source, clone the repository and run the batch file `build.bat` in the `dotnet` folder.<br/>
To run, run `setup.bat` to download the python dependencies and then run `run.bat`. To use your own python installation, create a venv before running `setup.bat`.
