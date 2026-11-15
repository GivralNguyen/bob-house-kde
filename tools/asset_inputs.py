#!/usr/bin/env python3
"""Validate staged Bob asset files before publishing a completed download."""
from __future__ import annotations
import json
import math
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
ROOM_IDS = ('69', '64', '44', '37', '41', '39', '43', '66', '67', '71')
WMF_MAGIC = bytes.fromhex('d7cdc69a')


def local_file(root, relative):
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f'Missing or external local input: {relative}')
    return path


def picture_id(value):
    if type(value) is not int or not 0 <= value <= 65535:
        raise ValueError(f'Invalid picture ID: {value!r}')
    return value


def validate(source):
    """Validate the entire input set before creating any destination files."""
    source = Path(source).expanduser().resolve(strict=True)
    # Accept either an assets directory or a project containing one.
    if not (source / 'ROVER.ACT').is_file() and (source / 'assets').is_dir():
        source = (source / 'assets').resolve()
    actor = local_file(source, 'ROVER.ACT')
    if actor.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('ROVER.ACT exceeds the supported input size')
    raw = actor.read_bytes()
    if len(raw) < 18 or raw[:4] != b'LP\x01\x00':
        raise ValueError('Expected a Bob ACT version 1 file')
    start, end = struct.unpack_from('<II', raw, 10)
    if not 0 < start < end <= len(raw):
        raise ValueError('Invalid ACT resource bounds')
    data_path = local_file(source, 'rooms/source/data.json')
    if data_path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('Room metadata exceeds the supported input size')
    data = json.loads(data_path.read_text())
    ids = set()
    for key in ROOM_IDS:
        room = data['rooms'][key]
        ids.add(picture_id(room['background']))
        if not isinstance(room['objects'], list) or len(room['objects']) > 1000:
            raise ValueError(f'Invalid object list in room {key}')
        for obj in room['objects']:
            ids.add(picture_id(obj['image']))
            if not isinstance(obj['app'], str):
                raise ValueError(f'Invalid app label in room {key}')
            for field in ('x', 'y', 'w', 'h'):
                value = obj[field]
                if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 100000:
                    raise ValueError(f'Invalid {field} coordinate in room {key}')
            if obj['w'] <= 0 or obj['h'] <= 0:
                raise ValueError(f'Invalid object size in room {key}')
    files = {'ROVER.ACT': actor, 'rooms/source/data.json': data_path}
    for pic in sorted(ids):
        if not isinstance(data['pictures'][str(pic)]['name'], str):
            raise ValueError(f'Missing picture name: {pic}')
        relative = f'rooms/source/{pic}.wmf'
        path = local_file(source, relative)
        if path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError(f'WMF exceeds supported input size: {pic}')
        raw = path.read_bytes()
        if len(raw) < 40 or raw[:4] != WMF_MAGIC:
            raise ValueError(f'Expected a placeable WMF: {relative}')
        left, top, right, bottom = struct.unpack_from('<4h', raw, 6)
        if right <= left or bottom <= top:
            raise ValueError(f'Invalid WMF bounds: {relative}')
        files[relative] = path
    return files

