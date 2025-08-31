import zipfile
import re
import os
from pathlib import Path

class Packageable:
    def __init__(self, path: str = "", ignore: "list[Packageable]" = [], is_dir: bool = False):
        self._path = path
        self._ignore = ignore
        self._is_dir = is_dir
    
    def path(self):
        return self._path

    @staticmethod
    def file(path: str):
        return Packageable(path=path, is_dir=False)
    
    @staticmethod
    def directory(path: str, ignore: "list[Packageable]" = []):
        return Packageable(path=path, ignore=ignore, is_dir=True)

files_to_package: list[Packageable] = [
    Packageable.file("config.json"),
    Packageable.file("example-config.json"),
    Packageable.file("readme.md"),
    Packageable.file("requirements.txt"),
    Packageable.file("run.bat"),
    Packageable.file("setup.bat"),
    Packageable.file("stt.py"),
    Packageable.file("changelog.txt"),
    Packageable.directory("filters", ignore=[Packageable.directory("filters/__pycache__")])
]

def is_ignored(file_path: Path, ignored_dirs: list[Packageable]) -> bool:
    for ig in ignored_dirs:
        try:
            if file_path.resolve().is_relative_to(Path(ig.path()).resolve()):
                return True
        except ValueError:
            continue
    return False

def package_files(files: list[Packageable], zip_path: Path):
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr(zinfo_or_arcname="version.number", data=version)
        for pkg in files:
            if pkg._is_dir:
                base_path = Path(pkg.path()).resolve()
                ignored = pkg._ignore

                for file_path in base_path.rglob("*"):
                    if not is_ignored(file_path, ignored):
                        arcname = file_path.resolve().relative_to(Path.cwd())
                        zipf.write(file_path, arcname)
            else:
                full_path = Path(pkg.path()).resolve()
                if full_path.exists():
                    arcname = full_path.relative_to(Path.cwd())
                    zipf.write(full_path, arcname)

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
    package_files(files_to_package, Path(zip_filename))
    print(f"Packaged to \"{zip_filename}\"")

