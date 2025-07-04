# Description
Simple speech-to-text python program for Space Station 13.<br/>
Captures your microphone input, converts it to text, and then sends it in game.<br/>

# Usage
1. Run using the `run.bat` script.<br/>
2. Hold the `activate` key (defaults to mouse4) to record.<br/>
3. Release to transcribe and send in-game.<br/>
Edit the `config.ini` file to change keybinds and chat delay in case of space lag.<br/>

# Installation
## Dependencies:
 - Python 3.11 or greater
 - ~5GB storage space (~2.4 for STT model and ~2.4 for python libraries)
## Installation:
1. Create a new virtual environement.<br/>
2. Install python deps from requirements.txt<br/>
3. **(Optional)**:<br/>
    Install `parakeet-tdt-0.6b-v2` - however, the script will automatically install the needed stt model if it cannot find it.<br/>

## Simple Setup:<br/>
Download all files and run this script:
```bash
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
```