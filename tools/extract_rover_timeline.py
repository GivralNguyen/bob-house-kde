#!/usr/bin/env python3
"""Decode the source Microsoft Bob ACT pose layouts and animation commands.

Format interpretation follows Ash Wolf's MIT-licensed robert.js (2018):
https://github.com/Treeki/robert.js/blob/master/robert.js
See robert-license.txt in this directory for the upstream license.
This only decodes animation data; it never executes the Windows program.
"""
from pathlib import Path
import json
import struct


def word(data, offset):
    return struct.unpack_from("<H", data, offset)[0]


def dword(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def blobs(data, base, index_start, index_end):
    offsets = struct.unpack_from("<" + "I" * ((index_end - index_start) // 4), data, index_start)
    return [data[base + left:base + right] for left, right in zip(offsets, offsets[1:])]


def groups(data, base, index_start, index_end):
    if index_start == index_end:
        return {}
    count = dword(data, index_start)
    entry = index_start + 4 + count * 6
    result = {}
    for i in range(count):
        group_id, size, first = struct.unpack_from("<HHH", data, index_start + 4 + i * 6)
        result[group_id] = []
        for j in range(size):
            offset, length = struct.unpack_from("<IH", data, entry)
            result[group_id].append(data[base + offset:base + offset + length])
            entry += 6
    assert entry == index_end
    return result


def decode(path):
    source = Path(path).read_bytes()
    assert source[:2] == b"LP" and word(source, 2) == 1, "Expected Bob ACT version 1"
    start, end = struct.unpack_from("<II", source, 10)
    data = source[start:end]
    width, height = struct.unpack_from("<hh", data, 8)
    payload_base, payload_index, riff_base, riff_index, anim_base, anim_index, string_base, string_index = (
        struct.unpack_from("<IIIIIIII", data, 0x26))
    payloads = blobs(data, payload_base, payload_index, riff_base)
    poses = {}
    images = []
    for i, payload in enumerate(payloads):
        if payload[:4] == b"\xd7\xcd\xc6\x9a":
            images.append(i)
            continue
        count = word(payload, 2)
        assert len(payload) == 4 + count * 10
        poses[i] = [list(struct.unpack_from("<Hhhhh", payload, 4 + j * 10)) for j in range(count)]
    animations = {}
    for group_id, sequences in groups(data, anim_base, anim_index, string_base).items():
        animations[group_id] = []
        for sequence in sequences:
            count = word(sequence, 2)
            commands = [list(struct.unpack_from("<HHH", sequence, 4 + j * 6)) for j in range(count)]
            assert len(sequence) == 4 + count * 6
            assert all(command[0] in (0, 1, 2) for command in commands)
            animations[group_id].append(commands)
    return {
        "source": "Microsoft Bob ROVER.ACT",
        "format_reference": "https://github.com/Treeki/robert.js",
        "width": width, "height": height,
        "command_format": {"0": "show pose ID for duration in milliseconds",
                           "1": "jump to command index with probability value/32768",
                           "2": "play source sound ID"},
        "pose_format": ["image_id", "left", "top", "right", "bottom"],
        "sound_count": len(blobs(data, riff_base, riff_index, anim_base)),
        "image_ids": images,
        "poses": poses,
        "animations": animations,
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    timeline = decode(root / "assets/ROVER.ACT")
    target = root / "assets/rover-timeline.json"
    target.write_text(json.dumps(timeline, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Decoded {len(timeline['image_ids'])} vector parts, {len(timeline['poses'])} poses, "
          f"{len(timeline['animations'])} animation groups to {target}")
