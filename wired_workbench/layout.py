"""Validate user-authored placement plans, not computer vision or hotel control."""
import html
from .core import ModelError, integer

def validate_layout(data):
    errors = []
    if not isinstance(data, dict) or set(data) != {"schema", "target", "width", "height", "inventory", "placements"}:
        return ["Campos exactos requeridos para plano local"]
    if data["schema"] != "wired-layout/1" or data["target"] not in ("habbogz", "habbo.es"):
        errors.append("Formato o destino no admitido")
    if not integer(data["width"], 1, 64) or not integer(data["height"], 1, 64):
        return errors + ["Ancho/alto entre 1 y 64 requeridos"]
    if not isinstance(data["inventory"], list) or len(data["inventory"]) > 512:
        return errors + ["Inventario de hasta 512 objetos requerido"]
    if not isinstance(data["placements"], list) or len(data["placements"]) > 512:
        return errors + ["Hasta 512 ubicaciones permitidas"]
    inventory = {}
    for o in data["inventory"]:
        if not isinstance(o, dict) or set(o) != {"id", "name", "width", "depth", "height"}:
            errors.append("Objeto de inventario inválido"); continue
        if not isinstance(o["id"], str) or not 1 <= len(o["id"]) <= 64 or not isinstance(o["name"], str) or not 1 <= len(o["name"]) <= 100:
            errors.append("ID/nombre de inventario inválido"); continue
        if o["id"] in inventory:
            errors.append("ID de inventario repetido"); continue
        if not all(integer(o[k], 1, 64) for k in ("width", "depth", "height")):
            errors.append("Dimensiones enteras entre 1 y 64 requeridas"); continue
        inventory[o["id"]] = o
    seen, occupied = set(), {}
    for p in data["placements"]:
        if not isinstance(p, dict) or set(p) != {"id", "x", "y", "z", "rotation"}:
            errors.append("Ubicación inválida"); continue
        ident = p["id"]
        if not isinstance(ident, str) or ident not in inventory:
            errors.append("La pieza no pertenece al inventario suministrado"); continue
        if ident in seen:
            errors.append("Pieza usada más de una vez"); continue
        seen.add(ident)
        if not all(integer(p[k], 0, 4096) for k in ("x", "y", "z")) or p["rotation"] not in (0, 90, 180, 270) or type(p["rotation"]) is not int:
            errors.append("Coordenadas o rotación inválidas"); continue
        obj = inventory[ident]
        w, d = obj["width"], obj["depth"]
        if p["rotation"] in (90, 270):
            w, d = d, w
        if p["x"] + w > data["width"] or p["y"] + d > data["height"]:
            errors.append("Objeto fuera del plano: " + ident); continue
        if p["z"] + obj["height"] > 4096:
            errors.append("Altura fuera de rango: " + ident); continue
        for x in range(p["x"], p["x"] + w):
            for y in range(p["y"], p["y"] + d):
                cell = occupied.setdefault((x, y), [])
                for low, high, other in cell:
                    if p["z"] < high and p["z"] + obj["height"] > low:
                        errors.append("Volúmenes superpuestos: " + other + "/" + ident)
                cell.append((p["z"], p["z"] + obj["height"], ident))
    return sorted(set(errors))

def layout_report(data):
    errors = validate_layout(data)
    if errors:
        raise ModelError("; ".join(errors))
    used = {x["id"] for x in data["placements"]}
    return {"abstractLayoutOnly": True, "canApply": False, "nativeCompatibility": "unverified",
            "placed": len(used), "unused": sorted(o["id"] for o in data["inventory"] if o["id"] not in used),
            "warnings": ["Unidades enteras del modelo local, no alturas/rotaciones nativas.",
                         "No verifica puertas, pared, zonas bloqueadas, soporte de apilado ni física del hotel.",
                         "No contiene reconocimiento de imagen ni movimientos de sala."]}

def svg_preview(data):
    layout_report(data)
    # Orthographic schematic. Every text value escaped. No images or remote resources.
    size = 32
    width = max(720, data["width"] * size + 64)
    height = data["height"] * size + 170
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="#101b2b"/>',
             '<g font-family="sans-serif" fill="#f2f6fa">',
             '<text x="24" y="32" font-size="22">Plano local · vista superior</text>',
             '<text x="24" y="57" font-size="13">No conectado al hotel. Alturas y física nativas sin verificar.</text>']
    for y in range(data["height"]):
        for x in range(data["width"]):
            parts.append(f'<rect x="{32+x*size}" y="{80+y*size}" width="32" height="32" fill="#192b40" stroke="#40526a"/>')
    inventory = {o["id"]: o for o in data["inventory"]}
    colors = ["#429fc0", "#d49e4f", "#70b894", "#a389c7"]
    for n, p in enumerate(sorted(data["placements"], key=lambda x: (x["z"], x["id"]))):
        obj = inventory[p["id"]]; w, d = obj["width"], obj["depth"]
        if p["rotation"] in (90, 270): w, d = d, w
        x, y = 32+p["x"]*size, 80+p["y"]*size
        bw, bh = w*size-4, d*size-4
        fit = max(1, (bw-6)//6)
        raw = p["id"]
        label = html.escape(raw if len(raw) <= fit else raw[-fit:])
        parts.append(f'<clipPath id="c{n}"><rect x="{x+2}" y="{y+2}" width="{bw}" height="{bh}"/></clipPath>'
                     f'<rect x="{x+2}" y="{y+2}" width="{bw}" height="{bh}" fill="{colors[n%4]}" stroke="#f2f6fa"/>'
                     f'<text clip-path="url(#c{n})" x="{x+5}" y="{y+19}" font-size="10" fill="#101b2b">{label}</text>')
    parts.append(f'<text x="24" y="{height-34}" font-size="13">Sólo piezas del inventario suministrado. No compra ni crea objetos.</text></g></svg>')
    return "\n".join(parts)
