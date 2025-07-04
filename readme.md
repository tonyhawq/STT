# Installation
## Dependencies:
 - Python 3.11 or greater
 - ~5GB storage space (~2.4 for STT model and ~2.4 for python libraries)
## Installation:
1. Create a new virtual environement.<br/>
2. Install python deps from requirements.txt<br/>
3. **(Optional)**:<br/>
    Install `parakeet-tdt-0.6b-v2` - however, the script will automatically install the needed stt model if it cannot find it.<br/>

Setup: (in the folder containing stt.py, requirements.txt, and config.ini)<br/>
```bash
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
```

# Running
Run `run.bat`