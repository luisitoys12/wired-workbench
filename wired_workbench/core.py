"""Independent, offline WIRED design model. Not a native hotel format or client."""
from __future__ import annotations
import json
from pathlib import Path

VERSION = "0.1.0-dev"
SCHEMA = "wired-workbench/1"
MAX_BYTES = 1024 * 1024
DOC = "https://help.habbo.com/hc/en-us/articles/360011620099-What-is-Wired-Furni"
CATALOG = {
    "trigger.use": {"role": "trigger", "label": "Usar un objeto", "needs": "object", "params": set()},
    "trigger.step": {"role": "trigger", "label": "Pisar una baldosa", "needs": "object", "params": set()},
    "trigger.keyword": {"role": "trigger", "label": "Decir una palabra", "needs": "none", "params": {"keyword"}},
    "condition.state": {"role": "condition", "label": "Objeto en un estado", "needs": "object", "params": {"state"}},
    "effect.state": {"role": "effect", "label": "Fijar estado de objeto", "needs": "object", "params": {"state"}},
    "effect.message": {"role": "effect", "label": "Mostrar mensaje", "needs": "none", "params": {"text"}},
}
LABELS = {"habbogz": "Habbogz", "habbo.es": "Habbo.es"}

class ModelError(ValueError):
    pass

def integer(value, low, high):
    return type(value) is int and low <= value <= high

def load_file(path):
    p = Path(path)
    with p.open("rb") as f:
        data = f.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ModelError("Archivo mayor que 1 MiB")
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=unique_keys,
                          parse_constant=lambda x: (_ for _ in ()).throw(ModelError("Número JSON no finito")))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as e:
        raise ModelError("JSON UTF-8 inválido o demasiado anidado") from e

def unique_keys(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ModelError("Clave JSON repetida")
        result[k] = v
    return result

def validate(room):
    """Return all safely recoverable issues, without opening URLs or native code."""
    issues = []
    def add(code, path, message):
        issues.append({"code": code, "path": path, "message": message})
    if not isinstance(room, dict):
        return [{"code": "shape", "path": "$", "message": "Se requiere objeto JSON"}]
    extra = set(room) - {"schema", "target", "room", "furniture", "stacks"}
    if extra:
        add("extra", "$", "Campos de nivel superior desconocidos")
    if room.get("schema") != SCHEMA:
        add("schema", "schema", "Formato propio requerido: " + SCHEMA)
    if not isinstance(room.get("target"), str) or room.get("target") not in LABELS:
        add("target", "target", "Destino debe ser habbogz o habbo.es")
    if not isinstance(room.get("room"), str) or not 1 <= len(room["room"]) <= 100:
        add("room", "room", "Identificador de sala de 1 a 100 caracteres")
    furniture, stacks = room.get("furniture"), room.get("stacks")
    if not isinstance(furniture, list) or len(furniture) > 256:
        add("furniture", "furniture", "Lista de hasta 256 objetos requerida")
        furniture = []
    if not isinstance(stacks, list) or len(stacks) > 128:
        add("stacks", "stacks", "Lista de hasta 128 pilas requerida")
        stacks = []
    ids = set()
    for n, obj in enumerate(furniture):
        p = f"furniture[{n}]"
        if not isinstance(obj, dict):
            add("shape", p, "Objeto esperado"); continue
        if set(obj) != {"id", "name", "states", "state"}:
            add("fields", p, "Campos exactos: id, name, states, state")
        ident = obj.get("id")
        if not isinstance(ident, str) or not 1 <= len(ident) <= 64:
            add("id", p, "ID textual de 1 a 64 caracteres"); continue
        if ident in ids:
            add("duplicate", p, "ID de objeto repetido")
        ids.add(ident)
        if not isinstance(obj.get("name"), str) or not 1 <= len(obj["name"]) <= 100:
            add("name", p, "Nombre de 1 a 100 caracteres")
        if not integer(obj.get("states"), 1, 256):
            add("states", p, "Cantidad de estados entre 1 y 256")
        elif not integer(obj.get("state"), 0, obj["states"] - 1):
            add("state", p, "Estado inicial fuera de rango")
    objects = {x["id"]: x for x in furniture if isinstance(x, dict) and isinstance(x.get("id"), str)}
    stack_ids = set()
    for n, stack in enumerate(stacks):
        p = f"stacks[{n}]"
        if not isinstance(stack, dict):
            add("shape", p, "Pila debe ser objeto"); continue
        if set(stack) != {"id", "trigger", "conditions", "effects"}:
            add("fields", p, "Campos exactos: id, trigger, conditions, effects")
        sid = stack.get("id")
        if not isinstance(sid, str) or not 1 <= len(sid) <= 64:
            add("id", p, "ID de pila inválido")
        elif sid in stack_ids:
            add("duplicate", p, "ID de pila repetido")
        else:
            stack_ids.add(sid)
        groups = [("trigger", [stack.get("trigger")])]
        for key in ("conditions", "effects"):
            values = stack.get(key)
            if not isinstance(values, list) or len(values) > 32:
                add("nodes", p + "." + key, "Lista de hasta 32 nodos requerida"); values = []
            if key == "effects" and not values:
                add("effects", p, "La pila necesita al menos un efecto")
            groups.append((key, values))
        for role_key, nodes in groups:
            role = {"trigger": "trigger", "conditions": "condition", "effects": "effect"}[role_key]
            for k, node in enumerate(nodes):
                q = p + "." + role_key + f"[{k}]"
                if not isinstance(node, dict):
                    add("node", q, "Nodo debe ser objeto"); continue
                kind = node.get("kind")
                if not isinstance(kind, str) or kind not in CATALOG:
                    add("unsupported", q, "Concepto no soportado en este modelo local"); continue
                spec = CATALOG[kind]
                if spec["role"] != role:
                    add("role", q, "Concepto en lugar incorrecto de la pila")
                expected = {"kind", "params"} | ({"object"} if spec["needs"] == "object" else set())
                if set(node) != expected:
                    add("fields", q, "Campos no coinciden con el concepto")
                params = node.get("params")
                if not isinstance(params, dict) or set(params) != spec["params"]:
                    add("params", q, "Parámetros desconocidos o ausentes"); continue
                obj = objects.get(node.get("object")) if isinstance(node.get("object"), str) else None
                if spec["needs"] == "object" and obj is None:
                    add("reference", q, "Objeto no pertenece a esta exportación de sala")
                if "state" in params:
                    if not integer(params["state"], 0, 255):
                        add("state", q, "Estado debe ser entero entre 0 y 255")
                    elif obj and integer(obj.get("states"), 1, 256) and params["state"] >= obj["states"]:
                        add("state", q, "Estado no existe en el objeto")
                for key in ("text", "keyword"):
                    if key in params and (not isinstance(params[key], str) or not 1 <= len(params[key]) <= 240):
                        add("text", q, "Texto de 1 a 240 caracteres requerido")
    return issues

def require_valid(room):
    errors = validate(room)
    if errors:
        raise ModelError(json.dumps(errors, ensure_ascii=False))
    return room

def explain(room):
    require_valid(room)
    names = {x["id"]: x["name"] for x in room["furniture"]}
    def desc(node):
        k = node["kind"]; s = CATALOG[k]["label"]
        if "object" in node:
            s += " [" + names[node["object"]] + "]"
        if node["params"]:
            s += " " + json.dumps(node["params"], ensure_ascii=False, sort_keys=True)
        return s
    lines = []
    for stack in room["stacks"]:
        lines.append({"stack": stack["id"], "when": desc(stack["trigger"]),
                      "only_if_all": [desc(x) for x in stack["conditions"]],
                      "then": [desc(x) for x in stack["effects"]]})
    used = {n["object"] for s in room["stacks"] for n in [s["trigger"], *s["conditions"], *s["effects"]] if "object" in n}
    warnings = []
    if any(s["trigger"]["kind"] == "trigger.keyword" for s in room["stacks"]):
        warnings.append("Coincidencia exacta local: mayúsculas y texto deben coincidir. Semántica nativa no verificada.")
    # Multiple writers can produce conflicting results; do not invent native ordering.
    writes = {}
    for s in room["stacks"]:
        for n in s["effects"]:
            if n["kind"] == "effect.state":
                writes.setdefault(n["object"], set()).add(n["params"]["state"])
    for ident, values in writes.items():
        if len(values) > 1:
            warnings.append("Varios estados propuestos para " + ident + ": revisar interacciones y orden nativo.")
    return {"model": SCHEMA, "target": room["target"], "nativeCompatibility": "unverified",
            "canApply": False, "explanation": lines, "warnings": warnings,
            "unusedObjects": sorted(set(names) - used), "source": DOC}

def simulate(room, events):
    """Finite abstract test only. Effects DO NOT emit native events or further triggers."""
    require_valid(room)
    if not isinstance(events, list) or len(events) > 256:
        raise ModelError("Lista de hasta 256 eventos requerida")
    states = {o["id"]: o["state"] for o in room["furniture"]}
    trace, messages = [], []
    for number, event in enumerate(events):
        if not isinstance(event, dict) or event.get("kind") not in ("trigger.use", "trigger.step", "trigger.keyword"):
            raise ModelError("Evento no admitido")
        is_text = event["kind"] == "trigger.keyword"
        if set(event) != {"kind", "text" if is_text else "object"}:
            raise ModelError("Campos de evento inválidos")
        if is_text:
            if not isinstance(event["text"], str) or len(event["text"]) > 240:
                raise ModelError("Texto de evento inválido")
        elif not isinstance(event["object"], str) or event["object"] not in states:
            raise ModelError("Objeto de evento ajeno a sala")
        for stack in room["stacks"]:
            trigger = stack["trigger"]
            match = event["kind"] == trigger["kind"] and (
                event.get("text") == trigger["params"].get("keyword") if is_text else event.get("object") == trigger.get("object"))
            if not match:
                continue
            passed = all(states[c["object"]] == c["params"]["state"] for c in stack["conditions"])
            trace.append({"event": number, "stack": stack["id"], "conditionsPassed": passed})
            if passed:
                for effect in stack["effects"]:
                    if effect["kind"] == "effect.state":
                        states[effect["object"]] = effect["params"]["state"]
                    elif effect["kind"] == "effect.message":
                        messages.append(effect["params"]["text"])
    return {"abstractTestOnly": True, "nativeCompatibility": "unverified", "canApply": False,
            "states": states, "messages": messages, "trace": trace,
            "semantics": "Orden de lista local; sin retrasos, concurrencia, señales ni disparos recursivos"}

def plan(recipe, target, control="control", output="output", guard=False, keyword="hola", text="Bienvenido"):
    if target not in LABELS or recipe not in ("switch-lamp", "pressure-gate", "keyword-message"):
        raise ModelError("Receta o destino desconocido")
    if control == output:
        raise ModelError("Control y salida deben ser distintos")
    furniture = []
    trigger_kind = {"switch-lamp": "trigger.use", "pressure-gate": "trigger.step", "keyword-message": "trigger.keyword"}[recipe]
    trigger = {"kind": trigger_kind, "params": {"keyword": keyword} if recipe == "keyword-message" else {}}
    if recipe != "keyword-message":
        trigger["object"] = control
        furniture.append({"id": control, "name": "Control de ejemplo", "states": 2, "state": 0})
        furniture.append({"id": output, "name": "Salida de ejemplo", "states": 2, "state": 0})
    conditions = []
    if guard:
        if recipe == "keyword-message":
            raise ModelError("La receta de mensaje no incluye condición de objeto")
        conditions.append({"kind": "condition.state", "object": output, "params": {"state": 0}})
    effect = {"kind": "effect.message", "params": {"text": text}} if recipe == "keyword-message" else {"kind": "effect.state", "object": output, "params": {"state": 1}}
    room = {"schema": SCHEMA, "target": target, "room": "design-not-a-live-room", "furniture": furniture,
            "stacks": [{"id": "example-stack", "trigger": trigger, "conditions": conditions, "effects": [effect]}]}
    return require_valid(room)
