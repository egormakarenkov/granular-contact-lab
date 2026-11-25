"""Assemble a self-contained Windows app from this curated source tree."""
import importlib.metadata
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    if sys.platform!='win32':raise SystemExit('Build the Windows distribution on Windows x64.')
    if not (ROOT/'ui/dist/index.html').exists():raise SystemExit('Build the interface first: cd ui && npm ci && npm run build')
    output=ROOT/'dist'
    target=output/'Granular Lab'
    if target.exists() or (output/'GranularLab').exists():
        raise SystemExit('A build folder already exists. Move it aside before rebuilding; this script does not delete it.')
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--onedir','--windowed','--name','Granular Lab',
        '--distpath',str(output),'--workpath',str(ROOT/'build'/'pyinstaller'),'--specpath',str(ROOT/'build'),
        '--paths',str(ROOT),'--collect-all','osqp','--copy-metadata','osqp',
        '--hidden-import','granular.server','--hidden-import','uvicorn.logging',
        '--hidden-import','uvicorn.loops.asyncio','--hidden-import','uvicorn.protocols.http.h11_impl',
        '--hidden-import','uvicorn.lifespan.off','--exclude-module','pytest','--exclude-module','IPython',
        '--exclude-module','matplotlib',str(ROOT/'portable_launcher.py')]
    subprocess.run(command,cwd=ROOT,check=True)
    for name in ('examples','demo','docs','ui/dist'):
        shutil.copytree(ROOT/name,target/name)
    (target/'granular').mkdir()
    (target/'experiments').mkdir()
    for name in ('granular/__init__.py','granular/physics.py','requirements.txt','requirements-tested.txt','README.md','LICENSE'):
        shutil.copy2(ROOT/name,target/name)
    licenses=target/'docs'/'dependency-licenses'
    licenses.mkdir()
    for dist in importlib.metadata.distributions():
        # Include package license/notice texts, not installation paths or RECORD files.
        name=dist.metadata.get('Name','dependency')
        for file in dist.files or []:
            leaf=Path(str(file)).name.lower()
            if ('.dist-info/' in str(file).replace('\\','/')) and ('license' in leaf or 'notice' in leaf or 'copying' in leaf):
                source=Path(dist.locate_file(file))
                if source.is_file():
                    dst=licenses/name/Path(str(file)).name
                    dst.parent.mkdir(exist_ok=True)
                    shutil.copy2(source,dst)
    python_license=Path(sys.base_prefix)/'LICENSE.txt'
    if python_license.exists():shutil.copy2(python_license,licenses/'Python-LICENSE.txt')
    (target/'START HERE.txt').write_text('Granular Lab - curated synthetic edition\n\nDouble-click Granular Lab.exe. Keep the entire folder together.\nClick Quit in the small solver window before removing a USB drive.\nWindows x64 with Chrome or Edge installed. No Python or Node installation needed.\nExperimental dimensionless normal-contact model. See README.md and docs/MODEL.md.\nExperimental v0.1.0. Project code: MIT license; preserve bundled third-party notices.\n',encoding='utf-8')
    target.rename(output/'GranularLab')
    print(output/'GranularLab')


if __name__=='__main__':main()
