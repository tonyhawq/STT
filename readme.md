# Description
Simple speech-to-text python program for Space Station 13.<br/>
Captures your microphone input, converts it to text, and then sends it in game.<br/>

# Usage
1. Run using the `run.bat` script.<br/>
2. Hold the `activate` key (defaults to mouse4) to record.<br/>
3. Release to transcribe and send in-game.<br/>
Edit the `config.json` file to change keybinds and chat delay in case of space lag.<br/>

# Installation
## Dependencies:
 - Python 3.11 *exact* - can be found at `https://www.python.org/downloads/release/python-3119/`
 - ADD PYTHON TO PATH, and DISABLE PATH LENGTH LIMIT
 - ~5GB storage space (~2.4 for STT model and ~2.4 for python libraries)
 - ~5GB ram free
## Installation:
1. Download all the files to a new folder
2. Run setup.bat

# Plugins
STT allows users to define their own text post-processing scripts to modify the generated transcripts before sending.<br/>
Plugins are toggleable with keybinds or by other plugins.<br/>
See example-config.json for an example of an "angry" plugin. It uppercases all of your text and replaces the final punctuation with "!!!" to change the tone of any message to angry.<br/>
## Plugins pose a security risk if you download from an untrustworthy source.
**Plugins are un-sandboxed and unrestricted. They can cause damage to your system if misused.**<br/>
Make sure you trust anyone you download plugins from!
