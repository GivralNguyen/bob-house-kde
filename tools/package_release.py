#!/usr/bin/env python3
"""Build a source-only archive, even when assets have been downloaded."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
# Deliberately explicit: newly added sources must be reviewed before inclusion.
SOURCE_FILES = ['.gitignore', 'LICENSE', 'README.md', 'README.txt', 'THIRD_PARTY_NOTICES.txt', 'VERSION', 'action_handler.py', 'asset-downloads.json', 'build.py', 'companion_dialogs.py', 'dialogs.py', 'install.sh', 'install_kde.py', 'launcher.py', 'plasma/org.bobhouse.desktop/contents/config/main.xml', 'plasma/org.bobhouse.desktop/contents/ui/Preview.qml', 'plasma/org.bobhouse.desktop/contents/ui/RetroButton.qml', 'plasma/org.bobhouse.desktop/contents/ui/RoomScene.qml', 'plasma/org.bobhouse.desktop/contents/ui/Rover.js', 'plasma/org.bobhouse.desktop/contents/ui/SpeechChoice.qml', 'plasma/org.bobhouse.desktop/contents/ui/config.qml', 'plasma/org.bobhouse.desktop/contents/ui/main.qml', 'plasma/org.bobhouse.desktop/metadata.json', 'plasma/org.bobhouse.desktop/tools/build_data.py', 'restore-wallpaper.sh', 'rover.py', 'tests/test_download_assets.py', 'tests/test_installer.py', 'tools/asset_inputs.py', 'tools/build_rooms.py', 'tools/check_qt.py', 'tools/dependencies.sh', 'tools/download_assets.py', 'tools/export_rover_poses.py', 'tools/extract_rover_timeline.py', 'tools/extract_rover_vectors.py', 'tools/package_release.py', 'tools/preview.py', 'tools/robert-license.txt', 'tools/verify_local.py']


def release_files():
    files = []
    for name in SOURCE_FILES:
        path = ROOT / name
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT) or not path.is_file():
            raise ValueError(f'Missing or external source file: {name}')
        if name.startswith(('assets/', 'previews/', 'dist/')) or path.name == 'Data.js':
            raise ValueError(f'Asset in source allowlist: {name}')
        files.append(path)
    return files


if __name__ == '__main__':
    version = (ROOT / 'VERSION').read_text().strip()
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version):
        raise ValueError('Expected a numeric release version')
    files = release_files()
    target = ROOT / 'dist' / f'bob-house-kde-{version}-source.zip'
    target.parent.mkdir(exist_ok=True)
    with ZipFile(target, 'w', ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, 'bob-house-kde/' + path.relative_to(ROOT).as_posix())
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix('.zip.sha256').write_text(f'{digest}  {target.name}\n')
    manifest = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    target.with_suffix('.manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'{target}\n{len(files)} source files; {target.stat().st_size / 1024:.1f} KiB\nSHA-256: {digest}')
