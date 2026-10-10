import importlib.metadata
import shutil
import sys
from pathlib import Path

out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
for name in ['PySide6','PySide6-Essentials','PySide6-Addons','shiboken6','gdstk','shapely','numpy','opencv-python-headless','klayout']:
    dist=importlib.metadata.distribution(name);dest=out/name;dest.mkdir(exist_ok=True)
    for file in dist.files or []:
        if 'license' in str(file).lower() or 'copyright' in str(file).lower() or Path(file).name.lower().startswith('notice'):
            path=Path(dist.locate_file(file))
            if path.is_file():
                target=dest/str(file).replace('..','_').replace('/','_').replace('\\','_')
                shutil.copyfile(path,target)
    (dest/'METADATA.txt').write_text(dist.read_text('METADATA') or '',encoding='utf-8')
