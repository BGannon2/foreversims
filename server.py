"""Local HTTP server for the Forever simulators (browser interface + JSON API)."""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import threading
import webbrowser
from concurrent.futures import ProcessPoolExecutor
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, quote

from sim import DATA, ASSUMPTIONS, TALENT_DATA, CONSUMABLE_DATA, preset, simulate, validate
from gear_data import CATALOG, PHASE6_BIS
from all_specs import public_specs, public_racials, simulate_spec, CLASS_RACES, ITEMS
from engine_data import default_consumables, default_buffs, DEFAULT_BUILDS, BUFF_GROUPS, SET_EFFECTS, SET_NO_COMBAT_EFFECT, SET_PROVISIONAL
import engine as engine_module

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
SETTING_DATA = json.loads((ROOT / "settings.json").read_text(encoding="utf-8"))
ALL_TALENTS = json.loads((ROOT / "forever_talents_all.json").read_text(encoding="utf-8"))
PHASE12_BIS = json.loads((ROOT / "phase12_bis_all.json").read_text(encoding="utf-8"))
ENCHANT_DATA = json.loads((ROOT / "enchants.json").read_text(encoding="utf-8"))
EXTRA_ITEMS = json.loads((ROOT / "extra_items.json").read_text(encoding="utf-8")) if (ROOT / "extra_items.json").is_file() else {"items": []}
MAX_BODY = 1_000_000
mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/json", ".json")
BENCHMARK_CACHE = None
AOE_BENCHMARK_CACHE = None
AOE_TARGET_COUNTS = (2, 3, 4, 5)

# Intended default configuration (shared by the UI, the benchmarks and the tests).
DEFAULTS = {"duration": 120, "iterations": 300, "benchmark_iterations": 300, "seed": 42, "benchmark_seed": 917, "armor": 3731, "targets": 1, "boss_type": "none", "talent_points": 51}
DEBUFFS = [x["key"] for x in SETTING_DATA["debuffs"]]


def default_request(spec, race=None, **overrides):
    """The saved default profile for a shared-engine spec (what the UI loads)."""
    profile = PHASE12_BIS["profiles"][spec["id"]]
    request = {"spec": spec["id"], "race": race or ("Human" if "Human" in spec["races"] else spec["races"][0]),
               "duration": DEFAULTS["duration"], "iterations": DEFAULTS["iterations"], "seed": DEFAULTS["seed"], "armor": DEFAULTS["armor"], "targets": DEFAULTS["targets"], "boss_type": DEFAULTS["boss_type"],
               "gear": [x["id"] for x in profile["gear"]], "gear_slots": [{"slot": x["slot"], "id": x["id"]} for x in profile["gear"]],
               "talents": DEFAULT_BUILDS[spec["id"]], "buffs": default_buffs(spec), "debuffs": DEBUFFS, "consumables": default_consumables(spec)}
    request.update(overrides)
    return request


def default_benchmarks():
    global BENCHMARK_CACHE
    if BENCHMARK_CACHE is not None: return BENCHMARK_CACHE
    snapshot = ROOT / "benchmarks.json"
    if snapshot.is_file():
        BENCHMARK_CACHE = json.loads(snapshot.read_text(encoding="utf-8")); return BENCHMARK_CACHE
    BENCHMARK_CACHE = build_benchmarks()
    return BENCHMARK_CACHE


def _bench_task(task):
    """Runs in a worker process (module-level so it's importable/picklable for spawn on
    Windows). task is ("spec", request_dict) or ("paladin", profile_dict)."""
    kind, payload = task
    return simulate_spec(payload) if kind == "spec" else simulate(payload)


def _run_bench_tasks(tasks, parallel=True):
    """Runs each (kind, payload) task and returns results in the same order. Each task is an
    independent, CPU-bound pure-Python simulation with no shared state, so this parallelizes
    almost linearly across cores via ProcessPoolExecutor. Falls back to sequential (parallel=
    False, or a single task) to avoid process-pool startup overhead for tiny runs."""
    if not parallel or len(tasks) < 2:
        return [_bench_task(t) for t in tasks]
    with ProcessPoolExecutor(max_workers=min(len(tasks), os.cpu_count() or 4)) as pool:
        return list(pool.map(_bench_task, tasks, chunksize=1))


def build_aoe_benchmarks(iterations=None, target_counts=AOE_TARGET_COUNTS, parallel=True):
    """Same shape and race matrix as build_benchmarks (every race per spec, not just one
    representative race), but a row per (spec, race, target count) instead of a row per
    (spec, race). Used by the AoE comparison page; abilities with no AoE component (most
    single-target rotations) simply show the same DPS/TPS at every target count."""
    iterations = iterations or DEFAULTS["benchmark_iterations"]
    tasks, meta = [], []
    for spec in public_specs():
        for race in CLASS_RACES[spec["class_name"]]:
            for targets in target_counts:
                tasks.append(("spec", default_request(spec, race, iterations=iterations, seed=DEFAULTS["benchmark_seed"], targets=targets)))
                meta.append({"id": spec["id"], "race": race, "class_name": spec["class_name"], "name": spec["name"], "role": spec["role"], "targets": targets,
                             "url": f"/all-specs.html?spec={spec['id']}&race={quote(race)}"})
    for spec_id in ("protection", "retribution"):
        for race in CLASS_RACES["Paladin"]:
            for targets in target_counts:
                profile = preset(spec_id); profile["race"] = race; profile["iterations"] = iterations; profile["seed"] = DEFAULTS["benchmark_seed"]
                profile["encounter"]["targets"] = float(targets)
                tasks.append(("paladin", profile))
                role = "tank" if spec_id == "protection" else "dps"
                meta.append({"id": f"paladin-{spec_id}", "race": race, "class_name": "Paladin", "name": spec_id.title(), "role": role, "targets": targets,
                             "url": f"/paladin.html?spec={spec_id}&race={quote(race)}"})
    results = _run_bench_tasks(tasks, parallel=parallel)
    rows = [{**m, "dps": r["metrics"]["dps"]["mean"], "tps": r["metrics"]["tps"]["mean"]} for m, r in zip(meta, results)]
    return {"duration": DEFAULTS["duration"], "iterations": iterations, "encounter": "Patchwerk, level 63, 3731 armor",
            "target_counts": list(target_counts), "world_buffs": False, "talents": "saved default 51-point builds", "rows": rows}


def default_aoe_benchmarks():
    global AOE_BENCHMARK_CACHE
    if AOE_BENCHMARK_CACHE is not None: return AOE_BENCHMARK_CACHE
    snapshot = ROOT / "aoe_benchmarks.json"
    if snapshot.is_file():
        AOE_BENCHMARK_CACHE = json.loads(snapshot.read_text(encoding="utf-8")); return AOE_BENCHMARK_CACHE
    AOE_BENCHMARK_CACHE = build_aoe_benchmarks()
    return AOE_BENCHMARK_CACHE


def build_benchmarks(iterations=None, parallel=True):
    iterations = iterations or DEFAULTS["benchmark_iterations"]
    tasks, meta = [], []
    for spec in public_specs():
        for race in CLASS_RACES[spec["class_name"]]:
            tasks.append(("spec", default_request(spec, race, iterations=iterations, seed=DEFAULTS["benchmark_seed"])))
            meta.append({"id": spec["id"], "race": race, "class_name": spec["class_name"], "name": spec["name"], "role": spec["role"],
                         "url": f"/all-specs.html?spec={spec['id']}&race={quote(race)}"})
    for spec_id in ("protection", "retribution"):
        for race in CLASS_RACES["Paladin"]:
            profile = preset(spec_id); profile["race"] = race; profile["iterations"] = iterations; profile["seed"] = DEFAULTS["benchmark_seed"]
            tasks.append(("paladin", profile))
            role = "tank" if spec_id == "protection" else "dps"
            meta.append({"id": f"paladin-{spec_id}", "race": race, "class_name": "Paladin", "name": spec_id.title(), "role": role,
                         "url": f"/paladin.html?spec={spec_id}&race={quote(race)}"})
    results = _run_bench_tasks(tasks, parallel=parallel)
    rows = [{**m, "dps": r["metrics"]["dps"]["mean"], "tps": r["metrics"]["tps"]["mean"], "dtps": r["metrics"]["dtps"]["mean"],
             "total_damage": sum(r["ability_damage"].values())} for m, r in zip(meta, results)]
    return {"duration": DEFAULTS["duration"], "iterations": iterations, "encounter": "Patchwerk, level 63, 3731 armor", "world_buffs": False,
            "talents": "saved default 51-point builds", "rows": rows, "race_source": "https://www.wowhead.com/forever/guide/new-race-class-combinations"}


class Handler(BaseHTTPRequestHandler):
    server_version = "ForeverSims/2.0"

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def send_json(self, value, status=HTTPStatus.OK):
        body = json.dumps(value, separators=(",", ":"), allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            return self.send_json({"ok": True, "data_version": DATA["version"], "engine": "event-driven-2"})
        if path == "/api/bootstrap":
            return self.send_json({
                "presets": {name: preset(name) for name in ("protection", "retribution")},
                "sources": DATA["sources"], "source_status": DATA["status"],
                "assumptions": ASSUMPTIONS, "excluded": DATA["excluded"],
                "gear_catalog": {key: CATALOG[key] for key in ("version", "source", "license", "scope")},
                "phase6_bis": PHASE6_BIS, "talent_data": TALENT_DATA, "consumable_data": CONSUMABLE_DATA,
                "setting_data": SETTING_DATA, "races": CLASS_RACES["Paladin"], "racials": public_racials(), "defaults": DEFAULTS,
            })
        if path == "/api/items":
            return self.send_json({"version": CATALOG["version"], "items": CATALOG["items"] + EXTRA_ITEMS["items"]})
        if path == "/api/specs":
            return self.send_json({"specs": public_specs()})
        if path == "/api/benchmarks":
            return self.send_json(default_benchmarks())
        if path == "/api/aoe-benchmarks":
            return self.send_json(default_aoe_benchmarks())
        if path == "/api/spec-bootstrap":
            return self.send_json({
                "specs": public_specs(), "talents": ALL_TALENTS, "gear": PHASE12_BIS, "consumables": CONSUMABLE_DATA,
                "settings": SETTING_DATA, "enchants": ENCHANT_DATA, "racials": public_racials(), "defaults": DEFAULTS, "buff_groups": BUFF_GROUPS,
                "set_effects": SET_EFFECTS, "set_no_combat_effect": sorted(SET_NO_COMBAT_EFFECT), "set_provisional": SET_PROVISIONAL, "set_patterns": [p for _, p in engine_module.SET_PATTERNS],
            })
        target = "index.html" if path in ("", "/") else path.lstrip("/")
        candidate = (WEB / target).resolve()
        try:
            candidate.relative_to(WEB.resolve())
        except ValueError:
            return self.send_error(HTTPStatus.NOT_FOUND)
        if not candidate.is_file():
            return self.send_error(HTTPStatus.NOT_FOUND)
        body = candidate.read_bytes()
        ctype = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"): ctype += "; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        route = urlparse(self.path).path
        if route == "/api/feedback":
            # Local stand-in for the Cloudflare Worker endpoint: append to feedback.local.jsonl.
            try:
                size = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(size)) if 0 < size <= MAX_BODY else {}
                if len(str(payload.get("message", "")).strip()) < 5:
                    return self.send_json({"error": "Please write a few words of feedback."}, HTTPStatus.BAD_REQUEST)
                with (ROOT / "feedback.local.jsonl").open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"received": self.log_date_time_string(), **payload}) + "\n")
                return self.send_json({"ok": True, "local": True})
            except (ValueError, json.JSONDecodeError) as exc:
                return self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        if route not in ("/api/simulate", "/api/simulate-spec"):
            return self.send_error(HTTPStatus.NOT_FOUND)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > MAX_BODY:
                raise ValueError("Request body must be between 1 byte and 1 MB.")
            payload = json.loads(self.rfile.read(size))
            if route == "/api/simulate-spec":
                result = simulate_spec(payload)
            else:
                profile = payload.get("profile") if isinstance(payload, dict) else None
                result = simulate(validate(profile))
            self.send_json(result)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            print(f"Simulation error: {exc!r}")
            self.send_json({"error": "Simulation failed."}, HTTPStatus.INTERNAL_SERVER_ERROR)


def create_server(host="0.0.0.0", port=8765):
    return ThreadingHTTPServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    server = create_server(args.host, args.port)
    url = f"http://{'127.0.0.1' if args.host == '0.0.0.0' else args.host}:{server.server_port}/"
    print(f"Forever Sims is running locally at {url}")
    if args.host == "0.0.0.0":
        print(f"It is also available to other devices on this network on port {server.server_port}.")
    print("Press Ctrl+C to stop the server.")
    if not args.no_browser:
        threading.Timer(0.45, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
