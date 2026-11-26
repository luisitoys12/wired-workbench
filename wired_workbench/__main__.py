import argparse
import json
import sys
from pathlib import Path
from .core import VERSION, CATALOG, ModelError, load_file, validate, explain, simulate, plan
from .layout import validate_layout, layout_report, svg_preview
from .image_plan import plan_from_image

def main(argv=None):
    parser = argparse.ArgumentParser(description="WIRED Workbench: diseño local y ejecutor nativo opt-in acotado")
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("catalog")
    sub.add_parser("capabilities")
    for name in ("validate", "explain", "layout-check", "layout-svg"):
        p = sub.add_parser(name); p.add_argument("file")
    p = sub.add_parser("image-plan", help="Offline: PNG/PPM + declared pieces -> layout plan"); p.add_argument("image"); p.add_argument("spec"); p.add_argument("--layout-out")
    p = sub.add_parser("simulate"); p.add_argument("file"); p.add_argument("events")
    p = sub.add_parser("plan"); p.add_argument("recipe", choices=["switch-lamp", "pressure-gate", "keyword-message"])
    p.add_argument("--target", choices=["habbogz", "habbo.es"], required=True)
    p.add_argument("--guard", action="store_true")
    p = sub.add_parser("native-classic-apply", help="Opt-in acceptance-room editor executor")
    p.add_argument("file")
    p.add_argument("--executor", nargs="+", required=True)
    p = sub.add_parser("native-duck-discover", help="Opt-in: plan duck recipe from real inspection, then apply")
    p.add_argument("--room-id", type=int, required=True)
    p.add_argument("--owner-id", type=int, required=True)
    p.add_argument("--executor", nargs="+", required=True)
    args = parser.parse_args(argv)
    try:
        command = args.command
        if command == "native-classic-apply":
            from .native import NativeExecutor, apply_classic
            with NativeExecutor(args.executor) as executor:
                result = apply_classic(load_file(args.file), executor)
        elif command == "native-duck-discover":
            from .native import NativeExecutor
            from .duck_planner import discover_and_apply
            with NativeExecutor(args.executor) as executor:
                result = discover_and_apply(executor, expected_room_id=args.room_id, expected_owner_id=args.owner_id)
        elif command == "catalog":
            result = {k: {**v, "params": sorted(v["params"]), "evidence": "conceptual-only", "nativeCompatibility": "unverified"} for k, v in CATALOG.items()}
        elif command == "capabilities":
            result = {
                "version": VERSION,
                "defaultMode": "offline",
                "nativeExecution": "explicit-local-executor-only",
                "targets": {
                    "habbogz": {
                        "generalRoomReader": False,
                        "generalGameCreation": False,
                        "preparedRecipeConfiguration": "verified-with-separate-scoped-executor",
                        "verifiedRecipe": "duck-classic-four-boxes",
                        "verificationDate": "2026-11-23",
                        "identityAndPrivacyGrounding": "operator-verified-manifest-not-independent-adapter-discovery",
                        "teleportRequiresLocalCompatibility": True,
                        "roomAndFurnitureCreation": False,
                        "currentCooperativeClose": "local-tests-only-not-hotel-tested"
                    },
                    "habbo.es": {"readNativeRoom": False, "applyWired": False, "moveFurniture": False}
                },
                "configurationEvidence": "native-reopen-plus-distinct-repeat-change-and-server-read",
                "gameplay": "separately-tested-not-driven-by-coordinator",
                "portableInstaller": False,
                "imageRecognition": False,
                "imageToLayoutPlan": "offline-top-view-1x1-user-declared-pieces-no-placement",
                "githubPublished": False
            }
        elif command == "image-plan":
            res = plan_from_image(Path(args.image).read_bytes(), load_file(args.spec))
            if args.layout_out: Path(args.layout_out).write_text(json.dumps(res["layout"], ensure_ascii=False, indent=2))
            result = res["report"] if args.layout_out else res
        elif command == "plan":
            result = plan(args.recipe, args.target, guard=args.guard)
        else:
            room = load_file(args.file)
            if command == "validate":
                errors = validate(room); result = {"validAbstractModel": not errors, "issues": errors, "nativeCompatibility": "unverified", "canApply": False}
                print(json.dumps(result, ensure_ascii=False, indent=2)); return 1 if errors else 0
            elif command == "explain": result = explain(room)
            elif command == "simulate": result = simulate(room, load_file(args.events))
            elif command == "layout-check": result = layout_report(room)
            elif command == "layout-svg":
                print(svg_preview(room)); return 0
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
    except (ModelError, OSError, ValueError) as e:
        print(json.dumps({"error": str(e), "canApply": False}, ensure_ascii=False), file=sys.stderr); return 2

if __name__ == "__main__":
    raise SystemExit(main())
