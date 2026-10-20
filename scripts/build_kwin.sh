#!/usr/bin/env bash
set -euo pipefail
version=${1:-2.2.0}
shift || true
if [[ ! $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo 'Version must be major.minor.patch' >&2
    exit 1
fi
cd "$(dirname "$0")/.."
cmake -S integrations/kwin -B build/kwin -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr "$@"
cmake --build build/kwin
python3 - "$version" <<'PY'
from pathlib import Path
import hashlib
import shutil
import subprocess
import sys

version = sys.argv[1]
kwin = subprocess.check_output(['pacman', '-Q', 'kwin'], text=True).split()[1].rsplit('-', 1)[0]
recipe = Path('build/kwin-package')
recipe.mkdir(parents=True, exist_ok=True)
library = Path('build/kwin/panoptixclick.so')
shutil.copy(library, recipe)
checksum = hashlib.sha256(library.read_bytes()).hexdigest()
(recipe / 'PKGBUILD').write_text(f'''pkgname=panoptix-kwin-click
pkgver={version}
pkgrel=1
pkgdesc='Optional KWin effect for Panoptix capture on click under KDE Wayland'
arch=('x86_64')
url='https://github.com/kannibalk1w1/panoptix'
license=('GPL-2.0-or-later')
depends=('kwin={kwin}' 'qt6-base' 'panoptix>={version}')
options=('!strip')
source=('panoptixclick.so')
sha256sums=('{checksum}')
package() {{
    install -Dm755 "$srcdir/panoptixclick.so" "$pkgdir/usr/lib/qt6/plugins/kwin/effects/plugins/panoptixclick.so"
}}
''')
PY
pkg_output_dir="$PWD/dist"
mkdir -p "$pkg_output_dir"
(cd build/kwin-package && PKGDEST="$pkg_output_dir" makepkg --nodeps --force --cleanbuild --noconfirm)
