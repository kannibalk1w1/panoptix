#!/usr/bin/env bash
set -euo pipefail
version=${1:-2.2.0}
if [[ ! $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo 'Version must be major.minor.patch' >&2
    exit 1
fi
cd "$(dirname "$0")/.."
python_bin=${PANOPTIX_BUILD_PYTHON:-python3}
"$python_bin" -m PyInstaller --clean --noconfirm panoptix-linux.spec
"$python_bin" - "$version" <<'PY'
import hashlib
from pathlib import Path
import shutil
import sys
import tarfile
from PIL import Image

version = sys.argv[1]
bundle = Path('dist') / f'panoptix-{version}-linux-x86_64'
if bundle.exists():
    shutil.rmtree(bundle)
shutil.copytree('dist/PanoptixLinux', bundle)
shutil.copy('packaging/linux/panoptix.desktop', bundle)
shutil.copy('README.md', bundle)
shutil.copytree('integrations/kwin', bundle / 'kwin-click-source')
with Image.open('assets/panoptix.ico') as icon:
    icon.resize((256, 256)).save(bundle / 'panoptix.png')
archive = Path('dist') / f'{bundle.name}.tar.gz'
with tarfile.open(archive, 'w:gz') as output:
    output.add(bundle, arcname=bundle.name)
recipe = Path('build/linux-package')
recipe.mkdir(parents=True, exist_ok=True)
checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
template = Path('packaging/linux/PKGBUILD.in').read_text()
(recipe / 'PKGBUILD').write_text(template.replace('@VERSION@', version).replace('@SHA256@', checksum))
shutil.copy(archive, recipe)
print(f'Built {archive}')
PY
if [[ ${2:-} != --archive-only ]]; then
    pkg_output_dir="$PWD/dist"
    (cd build/linux-package && PKGDEST="$pkg_output_dir" makepkg --nodeps --force --cleanbuild --noconfirm)
fi
