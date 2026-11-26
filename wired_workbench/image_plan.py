"""Image to placement plan. Offline: reads a PNG/PPM and the pieces the user declares.

Produces a wired-layout/1 plan. It never places anything in a hotel, never buys or
creates items, and does not claim the plan is valid for a real room: the user
places the pieces. Only 1x1 pieces, integer grid, top view.
"""
import struct
import zlib
from .core import ModelError, integer
from .layout import validate_layout

MAX_SIDE = 4096
MAX_PIXELS = 16_000_000
MAX_CELLS = 64 * 64

def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else (b if pb <= pc else c)

def decode_png(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ModelError("No es un PNG")
    pos, ihdr, plte, trns, idat = 8, None, None, None, []
    while pos + 8 <= len(data):
        n, typ = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if len(body) != n:
            raise ModelError("PNG truncado")
        pos += 12 + n
        if typ == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif typ == b"PLTE":
            plte = body
        elif typ == b"tRNS":
            trns = body
        elif typ == b"IDAT":
            idat.append(body)
        elif typ == b"IEND":
            break
    if not ihdr or not idat:
        raise ModelError("PNG incompleto")
    w, h, depth, ctype, _, _, interlace = ihdr
    if depth != 8 or interlace != 0 or ctype not in (0, 2, 3, 4, 6):
        raise ModelError("PNG no admitido: use 8 bits, sin entrelazado")
    if not (1 <= w <= MAX_SIDE and 1 <= h <= MAX_SIDE and w * h <= MAX_PIXELS):
        raise ModelError("Imagen demasiado grande")
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    stride = w * ch
    d = zlib.decompressobj()
    raw = d.decompress(b"".join(idat), (stride + 1) * h + 1)
    if len(raw) != (stride + 1) * h:
        raise ModelError("Datos PNG con tamaño inesperado")
    rows, prev = [], bytearray(stride)
    for y in range(h):
        f = raw[y * (stride + 1)]
        cur = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        if f == 1:
            for i in range(ch, stride): cur[i] = (cur[i] + cur[i - ch]) & 255
        elif f == 2:
            for i in range(stride): cur[i] = (cur[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride): cur[i] = (cur[i] + ((cur[i - ch] if i >= ch else 0) + prev[i]) // 2) & 255
        elif f == 4:
            for i in range(stride):
                cur[i] = (cur[i] + _paeth(cur[i - ch] if i >= ch else 0, prev[i], prev[i - ch] if i >= ch else 0)) & 255
        elif f != 0:
            raise ModelError("Filtro PNG inválido")
        rows.append(cur); prev = cur
    px = []
    for cur in rows:
        line = []
        for x in range(w):
            if ctype == 0: g = cur[x]; line.append((g, g, g, 255))
            elif ctype == 2: line.append((cur[3*x], cur[3*x+1], cur[3*x+2], 255))
            elif ctype == 4: g = cur[2*x]; line.append((g, g, g, cur[2*x+1]))
            elif ctype == 6: line.append(tuple(cur[4*x:4*x+4]))
            else:
                i = cur[x]
                if not plte or 3*i+2 >= len(plte): raise ModelError("Paleta PNG inválida")
                a = trns[i] if trns and i < len(trns) else 255
                line.append((plte[3*i], plte[3*i+1], plte[3*i+2], a))
        px.append(line)
    return w, h, px

def decode_ppm(data):
    parts, i = [], 0
    while len(parts) < 4 and i < len(data):
        while i < len(data) and data[i:i+1].isspace(): i += 1
        if data[i:i+1] == b"#":
            while i < len(data) and data[i:i+1] != b"\n": i += 1
            continue
        j = i
        while j < len(data) and not data[j:j+1].isspace(): j += 1
        parts.append(data[i:j]); i = j
    if len(parts) < 4 or parts[0] != b"P6" or parts[3] != b"255":
        raise ModelError("PPM P6 de 8 bits requerido")
    w, h = int(parts[1]), int(parts[2]); body = data[i + 1:]
    if not (1 <= w <= MAX_SIDE and 1 <= h <= MAX_SIDE and w * h <= MAX_PIXELS) or len(body) < w * h * 3:
        raise ModelError("PPM inválido o demasiado grande")
    return w, h, [[(body[(y*w+x)*3], body[(y*w+x)*3+1], body[(y*w+x)*3+2], 255) for x in range(w)] for y in range(h)]

def decode_image(data):
    return decode_png(data) if data[:4] == b"\x89PNG" else decode_ppm(data)

def _hex(c):
    if not isinstance(c, str) or len(c) != 7 or c[0] != "#":
        raise ModelError("Color #rrggbb requerido")
    try: return tuple(int(c[i:i+2], 16) for i in (1, 3, 5))
    except ValueError: raise ModelError("Color #rrggbb requerido")

def _cells(w, h, px, cols, rows):
    out = []
    for cy in range(rows):
        y0, y1 = cy * h // rows, max(cy * h // rows + 1, (cy + 1) * h // rows)
        line = []
        for cx in range(cols):
            x0, x1 = cx * w // cols, max(cx * w // cols + 1, (cx + 1) * w // cols)
            r = g = b = a = n = 0
            for y in range(y0, min(y1, h)):
                for x in range(x0, min(x1, w)):
                    p = px[y][x]; r += p[0]; g += p[1]; b += p[2]; a += p[3]; n += 1
            line.append((r // n, g // n, b // n, a // n))
        out.append(line)
    return out

def plan_from_image(data, spec):
    """spec: {target, width, height, kinds:[{name,color}], pieces:[{id,name,kind}], alphaMin?}"""
    if not isinstance(spec, dict) or set(spec) - {"target", "width", "height", "kinds", "pieces", "alphaMin"}:
        raise ModelError("Especificación inválida")
    cols, rows = spec.get("width"), spec.get("height")
    if not integer(cols, 1, 64) or not integer(rows, 1, 64) or cols * rows > MAX_CELLS:
        raise ModelError("Ancho/alto entre 1 y 64 requeridos")
    kinds = spec.get("kinds"); pieces = spec.get("pieces")
    if not isinstance(kinds, list) or not 1 <= len(kinds) <= 32 or not isinstance(pieces, list) or len(pieces) > 512:
        raise ModelError("Tipos (1-32) y piezas (hasta 512) requeridos")
    palette = {}
    for k in kinds:
        if not isinstance(k, dict) or set(k) != {"name", "color"} or not isinstance(k["name"], str) or not 1 <= len(k["name"]) <= 60 or k["name"] in palette:
            raise ModelError("Tipo inválido o repetido")
        palette[k["name"]] = _hex(k["color"])
    stock, inventory, seen = {n: [] for n in palette}, [], set()
    for p in pieces:
        if not isinstance(p, dict) or set(p) != {"id", "name", "kind"} or p["kind"] not in palette or not isinstance(p["id"], str) \
                or not 1 <= len(p["id"]) <= 64 or p["id"] in seen or not isinstance(p["name"], str) or not 1 <= len(p["name"]) <= 100:
            raise ModelError("Pieza inválida, repetida o de tipo desconocido")
        seen.add(p["id"]); stock[p["kind"]].append(p["id"])
        inventory.append({"id": p["id"], "name": p["name"], "width": 1, "depth": 1, "height": 1})
    amin = spec.get("alphaMin", 128)
    if not integer(amin, 1, 255): raise ModelError("alphaMin entre 1 y 255")
    w, h, px = decode_image(data)
    grid = _cells(w, h, px, cols, rows)
    need = {n: 0 for n in palette}; placements = []; empty = 0; short = {}
    for y, line in enumerate(grid):
        for x, c in enumerate(line):
            if c[3] < amin: empty += 1; continue
            name = min(palette, key=lambda n: sum((c[i] - palette[n][i]) ** 2 for i in range(3)))
            need[name] += 1
            if stock[name]:
                placements.append({"id": stock[name].pop(0), "x": x, "y": y, "z": 0, "rotation": 0})
            else:
                short[name] = short.get(name, 0) + 1
    layout = {"schema": "wired-layout/1", "target": spec.get("target", "habbo.es"), "width": cols, "height": rows,
              "inventory": inventory, "placements": placements}
    errors = validate_layout(layout)
    if errors: raise ModelError("; ".join(errors))
    return {"layout": layout, "report": {
        "abstractPlanOnly": True, "canApply": False, "nativeCompatibility": "unverified",
        "imageSize": [w, h], "cells": cols * rows, "emptyCells": empty, "pieceNeeds": need,
        "shortage": short, "complete": not short,
        "warnings": ["Plano de vista superior con piezas 1x1: el usuario coloca los muebles.",
                     "Nada se coloca ni se compra. Colores y piezas son los que usted declara.",
                     "Sin verificar contra puertas, alturas ni inventario real del hotel."]}}
