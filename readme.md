# Description
Simple speech-to-text python program for Space Station 13.<br/>
Captures your microphone input, converts it to text, and then sends it in game.<br/>
You can add simple filters to the text to add emotion.<br/>

# Installation
## Dependencies:
 - Python 3.11 *exact* - can be found at `https://www.python.org/downloads/release/python-3119/` OR in the folder "embedded" that comes with STT
 - ADD PYTHON TO PATH, and DISABLE PATH LENGTH LIMIT
 - ~5GB storage space (~2.4 for STT model and ~2.4 for python libraries)
## Installation:
1. Download all the files to a new folder
2. Run setup.bat

# Usage
1. Run using the `run.bat` script.<br/>
2. Hold the `activate` key (defaults to mouse4) to record.<br/>
3. Release to transcribe and send in-game.<br/>
Edit `userconfig.toml` to change keybinds.<br/>

# Plugins
STT allows users to define their own text post-processing scripts to modify the generated transcripts before sending.<br/>
Plugins are toggleable with keybinds or by other plugins.<br/>
See examplefilters.toml for an example of an "angry" plugin. It uppercases all of your text and replaces the final punctuation with "!!!" to change the tone of any message to angry.<br/>
**Plugins are un-sandboxed and unrestricted. They can cause damage to your system if misused.**<br/>
