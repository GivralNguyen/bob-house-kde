#!/usr/bin/env python3
"""Extract the source uncompressed WMF artwork from Microsoft's ROVER.ACT.

This preserves the vector artwork and converts the small subset of WMF drawing
records used by this character to SVG. It does not execute any Windows code.
"""
import json
import struct
from collections import Counter
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "assets"


def color(data):
    return "#" + data[:3].hex()


def convert(data):
    left, top, right, bottom = struct.unpack_from("<hhhh", data, 6)
    objects = []
    pen = {"stroke": "#000000", "stroke-width": "1"}
    brush = {"fill": "#ffffff"}
    fillrule = "evenodd"
    out = []
    offset = 40
    while offset + 6 <= len(data):
        size, func = struct.unpack_from("<IH", data, offset)
        if size < 3 or offset + size * 2 > len(data):
            raise ValueError(f"Invalid WMF record at {offset}")
        arg = data[offset + 6:offset + size * 2]
        offset += size * 2
        if func == 0:
            break
        if func == 0x2FA:  # CREATEPENINDIRECT
            style, width, _ = struct.unpack_from("<Hhh", arg)
            objects.append(("pen", {"stroke": "none" if style == 5 else color(arg[6:]),
                                    "stroke-width": str(max(1, abs(width)))}))
        elif func == 0x2FC:  # CREATEBRUSHINDIRECT
            style = struct.unpack_from("<H", arg)[0]
            objects.append(("brush", {"fill": "none" if style == 1 else color(arg[2:])}))
        elif func == 0x12D:  # SELECTOBJECT
            index = struct.unpack_from("<H", arg)[0]
            if index < len(objects):
                kind, obj = objects[index]
                if kind == "pen": pen = obj
                else: brush = obj
        elif func == 0x106:
            fillrule = "evenodd" if struct.unpack_from("<H", arg)[0] == 1 else "nonzero"
        elif func in (0x324, 0x325, 0x418, 0x538):
            style = dict(pen, **brush)
            style["fill-rule"] = fillrule
            style["stroke-linejoin"] = "round"
            style["stroke-linecap"] = "round"
            if func == 0x325: style["fill"] = "none"
            attrs = " ".join(f'{k}="{v}"' for k, v in style.items())
            if func in (0x324, 0x325):
                n = struct.unpack_from("<H", arg)[0]
                pts = struct.unpack_from(f"<{2*n}h", arg, 2)
                points = " ".join(f"{pts[j]},{pts[j+1]}" for j in range(0, 2*n, 2))
                tag = "polygon" if func == 0x324 else "polyline"
                out.append(f'<{tag} points="{points}" {attrs}/>')
            elif func == 0x418:
                b, r, t, l = struct.unpack_from("<4h", arg)
                out.append(f'<ellipse cx="{(l+r)/2}" cy="{(t+b)/2}" rx="{abs(r-l)/2}" ry="{abs(b-t)/2}" {attrs}/>')
            else:
                n = struct.unpack_from("<H", arg)[0]
                sizes = struct.unpack_from(f"<{n}H", arg, 2)
                pos = 2 + 2*n
                parts = []
                for count in sizes:
                    pts = struct.unpack_from(f"<{count*2}h", arg, pos); pos += count*4
                    parts.append("M" + " L".join(f"{pts[j]},{pts[j+1]}" for j in range(0,count*2,2)) + " Z")
                out.append(f'<path d="{" ".join(parts)}" {attrs}/>')
        elif func not in (0x104, 0x201, 0x102):
            raise ValueError(f"Unsupported WMF record {func:#x}")
    width, height = right-left, bottom-top
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="{left} {top} {width} {height}">\n' + "\n".join(out) + "\n</svg>\n"
    return svg, [left,top,right,bottom]


def main():
    data = (ASSETS / "ROVER.ACT").read_bytes()
    destination = ASSETS / "rover-parts"
    destination.mkdir(exist_ok=True)
    marker = bytes.fromhex("d7cdc69a")
    offset = 0
    parts = []
    while True:
        offset = data.find(marker, offset)
        if offset < 0: break
        length = struct.unpack_from("<I", data, offset + 28)[0] * 2 + 22
        svg, bounds = convert(data[offset:offset+length])
        name = f"part_{len(parts):03d}.svg"
        (destination / name).write_text(svg)
        parts.append({"file":name,"bounds":bounds,"act_offset":offset,"bytes":length})
        offset += 4
    (destination / "parts.json").write_text(json.dumps(parts, indent=2)+"\n")
    print(f"Extracted {len(parts)} vector parts to {destination}")


if __name__ == "__main__":
    main()
