import zipfile
import re
import os

files_to_package = [
    "config.json",
    "example-config.json",
    "readme.md",
    "requirements.txt",
    "run.bat",
    "setup.bat",
    "stt.py",
    "filters/all_caps.py",
    "filters/excited.py"
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
    if os.path.exists(zip_filename):
        print("Release already exists.")
        exit(1)
    with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr(zinfo_or_arcname="version.number", data=version)
        for file in files_to_package:
            print("Packaging", file)
            zipf.write(file, file)
    print(f"Packaged to \"{zip_filename}\"")

