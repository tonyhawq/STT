# Description
Simple speech-to-text python program for Space Station 13.<br/>
Captures your microphone input, converts it to text, and then sends it in game.<br/>
You can add simple filters to the text to add emotion.<br/>

# Installation
## Dependencies:
 - Windows
 - 4GB free hard drive space, with an additional that can be on a separate drive
## Installation:
1. Download a release from github
2. Extract the zip to anywhere you like
3. Run setup.bat and wait for the installation to finish
4. Run run.bat
5. Click the settings gear icon to change your settings or for help
6. Press "allow" to download the ASR model

# Usage
1. Run using the `run.bat` script.<br/>
2. If it's your first time, a popup will appear asking if you want to download from HF hub. This is the actual ASR model that you need to use STT, so press "allow"<br/>
3. Hold the `activate` key (defaults to mouse4) to record.<br/>
4. Release to transcribe and send in-game.<br/>
5. Press the settings gear or edit `userconfig.toml` to change keybinds, ASR model type, or anything else.<br/>
6. Edit `filters.toml` to create your own filters.<br/>

# Plugins
STT allows users to define their own text post-processing scripts to modify the generated transcripts before sending.<br/>
Plugins are toggleable with keybinds or by other plugins.<br/>
See examplefilters.toml for an example of an "angry" plugin. It uppercases all of your text and replaces the final punctuation with "!!!" to change the tone of any message to angry.<br/>
**Plugins are un-sandboxed and unrestricted. They can cause damage to your system if misused.**<br/>
