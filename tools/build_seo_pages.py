"""Generate the crawlable landing pages and sitemap for foreversims.com.

The simulators themselves are JavaScript apps behind query strings (/all-specs?spec=...), which
gives search engines one thin page for 23 specs. This writes a static, text-rich page per spec
under web/sims/ (title, H1, current default-setup results, rotation, default talents, links into
the sim), a /sims/ hub, the homepage's static spec links, and web/sitemap.xml. Everything comes
from data already in the repo, so re-running it after a data change keeps the pages current:

    python tools/build_seo_pages.py
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forever.all_specs import public_specs  # noqa: E402
from forever.engine_data import DEFAULT_BUILDS, SPEC_ABOUT  # noqa: E402

SITE = "https://foreversims.com"
WEB = ROOT / "web"
SIMS = WEB / "sims"
CLASS_ORDER = ["Warrior", "Paladin", "Hunter", "Rogue", "Priest", "Shaman", "Mage", "Warlock", "Druid"]
ROLE_WORD = {"dps": "DPS", "tank": "Tank"}

PALADIN = [
    {"id": "paladin-protection", "class_name": "Paladin", "name": "Protection", "role": "tank", "sim_url": "/paladin?spec=protection",
     "about": {"dps": "Seal of Fury with Judgement on cooldown, Holy Shield, Consecration, Holy Strike and Avenger's Shield where talented; the sim models Seal of Fury's self-absorb shield, Reckoning charges and Redoubt.",
               "tps": "Righteous Fury multiplies Holy damage threat, and Holy damage is most of a Protection Paladin's damage, so spell power and Holy damage drive threat."}},
    {"id": "paladin-retribution", "class_name": "Paladin", "name": "Retribution", "role": "dps", "sim_url": "/paladin?spec=retribution",
     "about": {"dps": "Twists Seal of Righteousness and Seal of Command through Twist of Light's echo, Judgement on cooldown, Holy Strike, Consecration, and Exorcism or Holy Wrath against Undead and Demons.",
               "tps": "Without Righteous Fury, Retribution's threat follows its damage roughly one to one."}},
]


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def slug(spec: dict) -> str:
    """Keyword-first URL: 'fury-warrior', 'feral-tank-druid', 'protection-paladin'."""
    return re.sub(r"[^a-z0-9]+", "-", f"{spec['name']} {spec['class_name']}".lower()).strip("-")


def specs() -> list[dict]:
    out = []
    for s in public_specs():
        out.append({**s, "sim_url": f"/all-specs?spec={s['id']}", "about": SPEC_ABOUT.get(s["id"], {})})
    out += PALADIN
    return sorted(out, key=lambda s: (CLASS_ORDER.index(s["class_name"]), s["name"]))


def talent_names() -> dict:
    names = {}
    shared = json.loads((ROOT / "data" / "forever_talents_all.json").read_text(encoding="utf-8"))
    for cls, trees in shared["classes"].items():
        for tree in trees:
            for t in tree["talents"]:
                names[str(t["id"])] = (tree["name"], t["name"], len(t["ranks"]), t["row"])
    pal = json.loads((ROOT / "data" / "paladin_talents.json").read_text(encoding="utf-8"))
    for tree in pal["trees"]:
        for t in tree["talents"]:
            names[str(t["id"])] = (tree["name"], t["name"], len(t["ranks"]), t["row"])
    return names


def default_build(spec: dict) -> dict:
    if spec["class_name"] == "Paladin":
        from forever import sim
        return sim.PROTECTION_BUILD if spec["name"] == "Protection" else sim.RETRIBUTION_BUILD
    return DEFAULT_BUILDS.get(spec["id"], {})


def head(title: str, description: str, path: str, extra: str = "") -> str:
    url = SITE + path
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)}</title><meta name="description" content="{esc(description)}"><link rel="canonical" href="{url}">'
            f'<meta name="theme-color" content="#08061a"><meta property="og:type" content="website"><meta property="og:site_name" content="Forever Sims">'
            f'<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description)}"><meta property="og:url" content="{url}">'
            f'<meta property="og:image" content="{SITE}/og-image.jpg"><meta name="twitter:card" content="summary_large_image">'
            f'<link rel="icon" href="/logo.svg"><link rel="stylesheet" href="/seo.css?v=1">{extra}</head>')


def ld(obj) -> str:
    return f'<script type="application/ld+json">{json.dumps(obj, separators=(",", ":"))}</script>'


def nav() -> str:
    return ('<header class="seo-top"><a class="seo-brand" href="/">Forever Sims</a><nav><a href="/sims/">All simulators</a>'
            '<a href="/dps-comparison">DPS comparison</a><a href="/tank-comparison">Tank comparison</a></nav></header>')


def footer(build: str, version: str) -> str:
    return (f'<footer class="seo-foot"><p>Forever Sims {esc(version)} · Forever client data build {esc(build)} · '
            'Results are Alpha: Classic Anniversary gear with World of Warcraft: Forever talents, abilities and item changes. '
            'Not affiliated with Blizzard Entertainment.</p></footer>')


def results_table(spec: dict, rows: list[dict]) -> str:
    mine = [r for r in rows if r["id"] == spec["id"] and r["targets"] == 1]
    if not mine:
        return ""
    tank = spec["role"] == "tank"
    mine.sort(key=lambda r: -(r["tps"] if tank else r["dps"]))
    body = "".join(f'<tr><td>{esc(r["race"])}</td><td>{r["dps"]:,.0f}</td>' + (f'<td>{r["tps"]:,.0f}</td>' if tank else "") + "</tr>" for r in mine)
    head_cells = "<th>Race</th><th>DPS</th>" + ("<th>TPS</th>" if tank else "")
    return (f'<section><h2>Current {esc(spec["name"])} {esc(spec["class_name"])} {"threat and DPS" if tank else "DPS"} by race</h2>'
            f'<p>Default setup: level 60, Classic Anniversary Phase 1–2 gear, default talents, full raid buffs and consumables, '
            f'one level-63 target (3,731 armor), 120 seconds, 300 iterations. Open the sim to change gear, talents, race or encounter.</p>'
            f'<table class="seo-table"><thead><tr>{head_cells}</tr></thead><tbody>{body}</tbody></table></section>')


def talents_block(spec: dict, names: dict) -> str:
    build = default_build(spec)
    trees: dict[str, list] = {}
    for tid, rank in build.items():
        if str(tid) in names and rank:
            tree, name, ranks, row = names[str(tid)]
            trees.setdefault(tree, []).append((row, name, rank, ranks))
    if not trees:
        return ""
    parts = []
    for tree, items in sorted(trees.items(), key=lambda kv: -sum(i[2] for i in kv[1])):
        lis = "".join(f"<li>{esc(n)} {r}/{m}</li>" for _, n, r, m in sorted(items))
        parts.append(f'<div><h3>{esc(tree)} ({sum(i[2] for i in items)})</h3><ul>{lis}</ul></div>')
    return f'<section><h2>Default talents</h2><p>The 51-point build the sim starts from. Every talent can be changed in the simulator.</p><div class="seo-trees">{"".join(parts)}</div></section>'


def spec_page(spec: dict, all_specs: list[dict], rows: list[dict], names: dict, build: str, version: str) -> str:
    cls, name, role = spec["class_name"], spec["name"], ROLE_WORD[spec["role"]]
    full = f"{name} {cls}"
    kind = "tank" if spec["role"] == "tank" else "DPS"
    title = f"{full} Simulator – WoW Forever {kind.title() if kind == 'tank' else kind} Sim | Forever Sims"
    desc = (f"Free {full} simulator for World of Warcraft: Forever. Sim your {'threat and damage' if kind == 'tank' else 'DPS'} with Forever talents, "
            f"Classic Anniversary gear, raid buffs and consumables. Runs in your browser.")
    path = f"/sims/{slug(spec)}"
    about = spec.get("about", {})
    siblings = [s for s in all_specs if s["class_name"] == cls and s["id"] != spec["id"]]
    sib = "".join(f'<li><a href="/sims/{slug(s)}">{esc(s["name"])} {esc(cls)} simulator</a></li>' for s in siblings)
    data = [
        {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": f"{full} Simulator (WoW Forever)", "url": SITE + path,
         "applicationCategory": "GameApplication", "operatingSystem": "Web browser", "isAccessibleForFree": True,
         "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
         "description": desc, "about": {"@type": "VideoGame", "name": "World of Warcraft: Forever"}},
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Forever Sims", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Simulators", "item": SITE + "/sims/"},
            {"@type": "ListItem", "position": 3, "name": f"{full} Simulator", "item": SITE + path}]},
    ]
    body = (f'<body class="seo-page">{nav()}<main class="seo-main">'
            f'<p class="seo-crumbs"><a href="/">Forever Sims</a> › <a href="/sims/">Simulators</a> › {esc(full)}</p>'
            f'<h1><img src="/spec-icons/{"paladin-" + spec["id"].split("-", 1)[1] if cls == "Paladin" else spec["id"]}.jpg" alt="" width="40" height="40">{esc(full)} Simulator</h1>'
            f'<p class="seo-lead">A free {role.lower() if role == "Tank" else "DPS"} simulator for <strong>{esc(full)}s in World of Warcraft: Forever</strong>. '
            f'It models Forever\'s talent trees, reworked abilities and racials on top of Classic Anniversary gear, and runs thousands of fights in your browser. '
            f'Nothing to install and no sign-up.</p>'
            f'<p><a class="seo-cta" href="{esc(spec["sim_url"])}">Open the {esc(full)} sim</a></p>'
            + results_table(spec, rows)
            + (f'<section><h2>Rotation</h2><p>{esc(about["dps"])}</p></section>' if about.get("dps") else "")
            + (f'<section><h2>Threat</h2><p>{esc(about["tps"])}</p></section>' if about.get("tps") else "")
            + talents_block(spec, names)
            + (f'<section><h2>Other {esc(cls)} simulators</h2><ul>{sib}</ul></section>' if sib else "")
            + '<section><h2>Compare every spec</h2><p>See how every WoW Forever spec and race stacks up in the '
              '<a href="/dps-comparison">DPS comparison</a> and <a href="/tank-comparison">tank comparison</a>, or browse '
              '<a href="/sims/">all simulators</a>.</p></section>'
            + f'</main>{footer(build, version)}</body></html>')
    return head(title, desc, path, "".join(ld(d) for d in data)) + body


def hub_page(all_specs: list[dict], build: str, version: str) -> str:
    title = "WoW Forever Simulators for Every Class and Spec | Forever Sims"
    desc = "Free DPS and tank simulators for every World of Warcraft: Forever class and spec: Warrior, Paladin, Hunter, Rogue, Priest, Shaman, Mage, Warlock and Druid."
    groups = []
    for cls in CLASS_ORDER:
        items = [s for s in all_specs if s["class_name"] == cls]
        if items:
            lis = "".join(f'<li><a href="/sims/{slug(s)}">{esc(s["name"])} {esc(cls)} simulator</a> <small>{ROLE_WORD[s["role"]]}</small></li>' for s in items)
            groups.append(f'<section><h2>{esc(cls)}</h2><ul>{lis}</ul></section>')
    data = {"@context": "https://schema.org", "@type": "ItemList", "name": "WoW Forever simulators", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "url": f"{SITE}/sims/{slug(s)}", "name": f"{s['name']} {s['class_name']} Simulator"} for i, s in enumerate(all_specs)]}
    body = (f'<body class="seo-page">{nav()}<main class="seo-main"><h1>WoW Forever Simulators</h1>'
            '<p class="seo-lead">Pick your class and spec. Every simulator runs in your browser with World of Warcraft: Forever talents, '
            'abilities and racials, Classic Anniversary gear, and full raid buffs and consumables by default.</p>'
            f'<div class="seo-hub">{"".join(groups)}</div></main>{footer(build, version)}</body></html>')
    return head(title, desc, "/sims/", ld(data)) + body


def home_links(all_specs: list[dict]) -> str:
    groups = []
    for cls in CLASS_ORDER:
        items = [s for s in all_specs if s["class_name"] == cls]
        if items:
            links = "".join(f'<a href="/sims/{slug(s)}">{esc(s["name"])} {esc(cls)} sim</a>' for s in items)
            groups.append(f"<div><h3>{esc(cls)}</h3>{links}</div>")
    return f'<nav class="home-seo-links" aria-label="Simulator guides"><h2>Simulator guides by spec</h2><div>{"".join(groups)}</div></nav>'


def main():
    from tools.wago_audit import BUILD
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    all_specs = specs()
    rows = json.loads((ROOT / "data" / "benchmarks.json").read_text(encoding="utf-8"))["rows"]
    names = talent_names()
    SIMS.mkdir(exist_ok=True)
    for s in all_specs:
        (SIMS / f"{slug(s)}.html").write_text(spec_page(s, all_specs, rows, names, BUILD, version), encoding="utf-8")
    (SIMS / "index.html").write_text(hub_page(all_specs, BUILD, version), encoding="utf-8")
    index = WEB / "index.html"
    page = index.read_text(encoding="utf-8")
    page = re.sub(r"<!--seo-links-->.*?<!--/seo-links-->", f"<!--seo-links-->{home_links(all_specs)}<!--/seo-links-->", page, flags=re.S)
    index.write_text(page, encoding="utf-8")
    today = dt.date.today().isoformat()
    urls = ["/", "/sims/", "/all-specs", "/paladin", "/dps-comparison", "/tank-comparison"] + [f"/sims/{slug(s)}" for s in all_specs]
    sitemap = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
               + "".join(f"  <url><loc>{SITE}{u}</loc><lastmod>{today}</lastmod></url>\n" for u in urls) + "</urlset>\n")
    (WEB / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    print(f"wrote {len(all_specs)} spec pages, the /sims/ hub and web/sitemap.xml ({len(urls)} URLs)")


if __name__ == "__main__":
    main()
