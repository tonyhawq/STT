import zipfile
import re
import os
from pathlib import Path

class Packageable:
    def __init__(self, path: str = "", destination: str | None = None, ignore: "list[Packageable]" = [], is_dir: bool = False):
        self._path = path
        if destination is None:
            self.destination = self._path
        else:
            self.destination = destination
        self.ignore = ignore
        self.is_dir = is_dir
    
    def path(self):
        return self._path

    def __eq__(self, other):
        if not isinstance(other, Packageable):
            return False
        return self._path == other._path and self.is_dir == other.is_dir and self.ignore == other.ignore and self.destination == other.destination

    @staticmethod
    def file(path: str, destination: str | None = None):
        return Packageable(path=path, destination=destination, is_dir=False)
    
    @staticmethod
    def directory(path: str, ignore: "list[Packageable]" = []):
        return Packageable(path=path, ignore=ignore, is_dir=True)

files_to_package: list[Packageable] = [
    Packageable.file("config/exampleconfig.toml"),
    Packageable.file("config/examplefilters.toml"),
    Packageable.file("readme.md"),
    Packageable.file("requirements.txt"),
    Packageable.file("debug.bat", destination="data/debug.bat"),
    Packageable.file("run.bat", destination="data/run.bat"),
    Packageable.file("data/gear.png"),
    Packageable.file("data/question_button.png"),
    Packageable.file("setup.bat"),
    Packageable.file("data/stt.py"),
    Packageable.file("data/shared.py"),
    Packageable.file("data/installer.py"),
    Packageable.file("data/changelog.txt"),
    Packageable.directory("embedded"),
    Packageable.directory("filters", ignore=[Packageable.directory("filters/__pycache__")]),
    Packageable.directory("data/models", ignore=[Packageable.directory("data/models/__pycache__")])
]

files_to_package_without_embedded: list[Packageable] = files_to_package.copy()
files_to_package_without_embedded.remove(Packageable.directory("embedded"))

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
            if pkg.is_dir:
                base_path = Path(pkg.path()).resolve()
                ignored = pkg.ignore

                for file_path in base_path.rglob("*"):
                    if not is_ignored(file_path, ignored):
                        arcname = file_path.resolve().relative_to(Path.cwd())
                        zipf.write(file_path, arcname)
            else:
                src_path = Path(pkg.path()).resolve()
                dst_path = Path(pkg.destination).resolve()
                if src_path.exists():
                    arcname = dst_path.relative_to(Path.cwd())
                    zipf.write(filename=src_path, arcname=arcname)

if __name__ == "__main__":
    print("Version?")
    while True:
        version = input()
        if bool(re.fullmatch(r'^\d+\.\d+\.\d+$', version)):
            break
        print("Does not match pattern \"x.x.x\".")
    print(f"Packaging version \"{version}\"")
    zip_filename = f"releases/STT_{version}.zip"
    zip_without_embedded_filename = f"releases/STT_{version}_NOPYTHON.zip"
    if os.path.exists(zip_filename):
        print("Release already exists.")
        exit(1)
    package_files(files_to_package, Path(zip_filename))
    package_files(files_to_package_without_embedded, Path(zip_without_embedded_filename))
    print(f"Packaged to \"{zip_filename}\"")

