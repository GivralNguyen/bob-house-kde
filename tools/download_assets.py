#!/usr/bin/env python3
"""Fetch pinned Bob assets from the documented third-party hosts."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

try:
    from .asset_inputs import validate
except ImportError:
    from asset_inputs import validate

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'asset-downloads.json'
HOSTS = {'tmafe.com', 'www.tmafe.com', 'tmafemirror.org', 'wuffs.org'}


def check_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in HOSTS or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError(f'Unexpected download host or protocol: {url}')


def load_manifest(path=MANIFEST):
    entries = json.loads(Path(path).read_text())['files']
    seen = set()
    for entry in entries:
        name = entry['path']
        p = PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or '\\' in name or name in seen:
            raise ValueError(f'Unsafe or duplicate destination: {name}')
        if name not in ('ROVER.ACT', 'rooms/source/data.json') and not re.fullmatch(r'rooms/source/[0-9]+\.wmf', name):
            raise ValueError(f'Unexpected asset destination: {name}')
        if not re.fullmatch(r'[0-9a-f]{64}', entry['sha256']) or type(entry['size']) is not int or not 0 < entry['size'] <= 16*1024*1024:
            raise ValueError(f'Invalid checksum/size: {name}')
        check_url(entry['url'])
        seen.add(name)
    if not {'ROVER.ACT', 'rooms/source/data.json'} <= seen:
        raise ValueError('Manifest must include Rover and room metadata')
    return entries


def fetch(entry, target):
    request = Request(entry['url'], headers={'User-Agent': 'Bob-House-KDE/0.3.0 asset setup'})
    with urlopen(request, timeout=30) as response:
        check_url(response.geturl())
        payload = response.read(entry['size'] + 1)
    if len(payload) != entry['size'] or hashlib.sha256(payload).hexdigest() != entry['sha256']:
        raise ValueError(f"Size/checksum mismatch: {entry['path']}; upstream may have changed. No assets installed.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)


def download(destination=ROOT / 'assets', manifest=MANIFEST):
    destination = Path(destination)
    entries = load_manifest(manifest)
    if destination.exists():
        # Idempotent reruns check every pinned input rather than trusting existence.
        for entry in entries:
            path = destination / entry['path']
            if not path.resolve().is_relative_to(destination.resolve()) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
                raise ValueError(f'Existing assets differ or are incomplete. Move {destination} aside and retry.')
        validate(destination)
        print('Existing assets match all pinned checksums; no downloads needed.')
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.bob-download-', dir=destination.parent) as directory:
        staged = Path(directory) / 'assets'
        staged.mkdir()
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(fetch, entry, staged / entry['path']) for entry in entries]
            for future in futures:
                future.result()
        validate(staged)
        (staged / 'NOTICE.txt').write_text(
            'Microsoft Bob artwork and data, fetched from third-party hosts.\n'
            'Downloaded separately during setup; runtime files are generated locally.\n'
            'See asset-downloads.json and THIRD_PARTY_NOTICES.txt in the project root.\n')
        staged.rename(destination)
    print(f'Downloaded and verified {len(entries)} files. Next: python3 build.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list', action='store_true', help='List URLs and checksums without downloading')
    args = parser.parse_args()
    try:
        if args.list:
            for entry in load_manifest():
                print(f"{entry['sha256']}  {entry['url']}")
        else:
            download()
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f'Asset download failed: {error}\n')


if __name__ == '__main__':
    main()
