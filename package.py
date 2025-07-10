import zipfile
import re
import os

files_to_package = [
    "config.ini",
    "example-config.ini",
    "readme.md",
    "requirements.txt",
    "run.bat",
    "setup.bat",
    "stt.py",
]

if __name__ == "__main__":
    print("Version?")
    while True:
        version = input()
        if bool(re.fullmatch(r'^\d+\.\d+\.\d+$', version)):
            break
        print("Does not match pattern \"x.x.x\".")
    print(f"Packaging version \"{version}\"")
    zip_filename = "releases/STT_"+version+".zip"
    with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file in files_to_package:
            print("Packaging", file)
            zipf.write(file, file)
    print(f"Packaged to \"{zip_filename}\"")

