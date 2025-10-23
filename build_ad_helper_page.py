#!/usr/bin/env python3
"""
Build static Ability Draft helper page (cross-hero combos only).

Inputs:
  - cache/ability_high_skill.json      (sole source of truth)
  - cache/ability_pairs.json           (combos)     [optional]

Output:
  - dist/ad_helper.html
"""
import json
from pathlib import Path

INFILE_HS    = Path("cache/ability_high_skill.json")
INFILE_PAIRS = Path("cache/ability_pairs.json")

OUTDIR  = Path("dist")
OUTFILE = OUTDIR / "ad_helper.html"


def _load(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_high_skill_map():
    """
    Returns the 'data' dict (best-effort). If the file structure varies,
    this is resilient and will fall back to the root.
    Expected shapes supported:
      { "data": { "<Hero>": { ... } } }
      { "<Hero>": { ... } }
    """
    if not INFILE_HS.exists():
        raise SystemExit(f"Missing {INFILE_HS}. This file is now the only source of truth.")
    try:
        doc = _load(INFILE_HS)
        if isinstance(doc, dict) and "data" in doc and isinstance(doc["data"], dict):
            return doc["data"]
        # fallback: maybe the root is already the hero map
        return doc if isinstance(doc, dict) else {}
    except Exception as e:
        raise SystemExit(f"Failed to parse {INFILE_HS}: {e}")


def load_pairs():
    if not INFILE_PAIRS.exists():
        return []
    try:
        doc = _load(INFILE_PAIRS)
        pairs = doc.get("pairs", [])
        return pairs if isinstance(pairs, list) else []
    except Exception:
        return []


def _get(d, *keys, default=None):
    """Safe get that tries multiple keys (first hit wins)."""
    for k in keys:
        if isinstance(d, dict) and k in d:
            return d[k]
    return default


def build_compact_from_hs(hs_map: dict) -> dict:
    """
    Transform the HS map into the 'compact' DATA structure expected by the page.

    For each hero (key = hero name), we try to read:
      hero_id        from any of: hero_id, id
      hero_img       from any of: hero_img, portrait, img, image
      body_winrate   from any of: body_winrate, win_pct, hero_win_pct
      abilities[]: list of entries where we try:
        id           from: id, ability_id
        name         from: name, ability_name
        img          from: img, image, icon
        win_pct      from: win_pct, hero_win_pct, ability_win_pct
    """
    compact = {}

    # hs_map is expected: { "Abaddon": { ... }, "Ursa": { ... }, ... }
    for hero_name in sorted(hs_map.keys(), key=lambda s: s.lower()):
        hrow = hs_map.get(hero_name) or {}

        hero_id = _get(hrow, "hero_id", "id")
        hero_img = _get(hrow, "hero_img", "portrait", "img", "image")
        body_winrate = _get(hrow, "body_winrate", "win_pct", "hero_win_pct")

        # abilities might be under "abilities", "spells", etc.
        abilities_src = _get(hrow, "abilities", "spells", "skills", default=[]) or []
        abilities = []
        if isinstance(abilities_src, dict):
            # Sometimes keyed by ability name → convert to list
            abilities_src = list(abilities_src.values())
        if isinstance(abilities_src, list):
            for a in abilities_src:
                if not isinstance(a, dict):
                    continue
                ability_name = _get(a, "ability_name", "name")
                if not ability_name:
                    continue
                abilities.append({
                    "id": _get(a, "ability_id", "id"),
                    "name": ability_name,
                    "img": _get(a, "img", "image", "icon"),
                    "win_pct": _get(a, "win_pct", "hero_win_pct", "ability_win_pct"),
                })

        compact[hero_name] = {
            "hero_id": hero_id,
            "hero_img": hero_img,
            "body_winrate": body_winrate,
            "abilities": abilities,
        }

    return compact


def mk_html(compact: dict, hs_map: dict, pairs: list) -> str:
    data_json  = json.dumps(compact, ensure_ascii=False)
    hs_json    = json.dumps(hs_map, ensure_ascii=False)
    pairs_json = json.dumps(pairs, ensure_ascii=False)

    # NOTE: doubled braces are intentional for f-string safety.
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Ability Draft Helper (static)</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{ --bg:#0f1115; --card:#151923; --muted:#9aa3b2; --text:#e7ecf3; --accent:#7aa2f7; --pill:#1f2633; }}
  html,body {{ margin:0; padding:0; background:var(--bg); color:var(--text); font:14px/1.4 system-ui,-apple-system,Segoe UI,Roboto,Arial; }}
  .wrap {{ max-width:1100px; margin:24px auto; padding:0 16px; }}
  h1 {{ font-size:20px; margin:0 0 12px; }}
  h2 {{ font-size:16px; margin:14px 0 8px; color:var(--muted); }}
  .card {{ background:var(--card); border-radius:14px; padding:14px; box-shadow:0 2px 8px rgba(0,0,0,.25); }}
  .row {{ display:flex; gap:12px; flex-wrap:wrap; }}
  .col {{ flex:1 1 100%; min-width:300px; }}
  .control {{ position:relative; }}
  input[type=text] {{ width:100%; padding:10px 12px; border-radius:10px; border:1px solid #2a3142; background:#0f1320; color:var(--text); }}
  button {{ padding:8px 12px; border-radius:10px; border:1px solid #2a3142; background:#0f1320; color:var(--text); cursor:pointer; }}
  .pills {{ display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; }}
  .pill {{ background:var(--pill); border:1px solid #2a3142; padding:6px 10px; border-radius:100px; display:flex; align-items:center; gap:8px; }}
  .pill b {{ font-weight:600; }}
  .pill button {{ border:none; background:transparent; color:var(--muted); padding:0 2px; font-size:16px; line-height:1; }}
  .muted {{ color:var(--muted); }}
  table {{ width:100%; border-collapse:collapse; margin-top:10px; }}
  th, td {{ padding:8px 10px; border-bottom:1px solid #2a3142; text-align:left; vertical-align:middle; }}
  th {{ position:sticky; top:0; background:var(--card); z-index:1; user-select:none; cursor:pointer; }}
  th.sort-asc::after {{ content:" \\25B2"; }}
  th.sort-desc::after {{ content:" \\25BC"; }}
  .img {{ width:28px; height:28px; border-radius:6px; background:#0f1320; display:inline-block; vertical-align:middle; }}
  .badge {{ display:inline-block; padding:2px 6px; border:1px solid #2a3142; border-radius:8px; margin-right:4px; }}
  .k {{ font-variant-numeric: tabular-nums; }}
  .small {{ font-size:12px; }}
  .footer {{ margin-top:16px; color:var(--muted); font-size:12px; }}
  .dropdown {{ position:absolute; left:0; right:0; top:100%; margin-top:6px; background:#0f1320; border:1px solid #2a3142; border-radius:10px; max-height:240px; overflow:auto; z-index:5; display:none; }}
  .dropdown .opt {{ padding:8px 10px; border-bottom:1px solid #1c2435; }}
  .dropdown .opt:last-child {{ border-bottom:none; }}
  .dropdown .opt:hover, .dropdown .opt.active {{ background:#131a2a; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Ability Draft Helper</h1>
  <div class="row">
    <div class="col card">
      <div class="muted small">Pick up to 12 heroes from your AD lobby.</div>
      <div class="control" style="margin-top:8px;">
        <input id="heroInput" type="text" placeholder="Type a hero (e.g., Ursa, Lion, Queen of Pain)" autocomplete="off" spellcheck="false">
        <div id="dd" class="dropdown"></div>
      </div>
      <div style="display:flex; gap:8px; margin-top:8px;">
        <button id="addBtn">Add</button>
        <button id="clearBtn" title="Clear all">Clear</button>
      </div>
      <div class="pills" id="selPills"></div>
      <div class="muted small" id="selHint"></div>
    </div>
  </div>

  <div class="card" style="margin-top:12px;">
    <h2>Abilities</h2>
    <table id="tblAbilities">
      <thead>
        <tr>
          <th data-key="ability">Ability</th>
          <th data-key="from">From Heroes</th>
          <th data-key="pick">Pick #</th>
          <th data-key="win">Win %</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
    <div class="footer" id="countAbilities"></div>
  </div>

  <div class="card" style="margin-top:12px;">
    <h2>Ability Combos</h2>
    <table id="tblPairs">
      <thead>
        <tr>
          <th data-key="a1">Ability 1</th>
          <th data-key="a2">Ability 2</th>
          <th data-key="syn">Synergy</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
    <div class="footer" id="countPairs"></div>
  </div>
</div>

<script>
const DATA  = {data_json};
const HS    = {hs_json};
const PAIRS = {pairs_json};

const HEROES = Object.keys(DATA).sort((a,b)=>a.localeCompare(b));
const MAX = 12;

const $ = (id)=>document.getElementById(id);
const heroInput = $("heroInput");
const dd = $("dd");
const addBtn = $("addBtn");
const clearBtn = $("clearBtn");
const pills = $("selPills");
const hint = $("selHint");

const tblA = $("tblAbilities");
const tbodyA = tblA.querySelector("tbody");
const theadA = tblA.querySelector("thead");
const countA = $("countAbilities");

const tblP = $("tblPairs");
const tbodyP = tblP.querySelector("tbody");
const theadP = tblP.querySelector("thead");
const countP = $("countPairs");

const sel = new Set();

// --- Canonicalize names (normalize punctuation/spacing)
function canon(s) {{
  return String(s || "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\\u2018\\u2019]/g, "'")
    .replace(/[\\u201C\\u201D]/g, '"')
    .replace(/[\\u2013\\u2014]/g, "-")
    .replace(/[._]/g, " ")
    .replace(/[^\\w\\s'-]/g, " ")
    .replace(/\\s+/g, " ")
    .trim();
}}

// Ability owners for current selection: canon(ability) -> Set(canon(hero))
let abilityOwners = new Map();

// --- Autocomplete (names only) with prefix matching + proper arrow selection
let ddItems = [], ddIndex = -1;

function filterHeroes(q) {{
  q = q.trim().toLowerCase();
  if (!q) return HEROES.slice(0, 50);
  return HEROES.filter(h => h.toLowerCase().startsWith(q)).slice(0, 50);
}}

function renderDD() {{
  dd.innerHTML = ddItems.map((h,i)=>`<div class="opt${{i===ddIndex?' active':''}}" data-v="${{escapeAttr(h)}}">${{escapeHtml(h)}}</div>`).join("");
  dd.style.display = ddItems.length ? "block" : "none";
}}

function openDD(items) {{
  ddItems = items || [];
  if (!ddItems.length) {{
    ddIndex = -1;
  }} else if (ddIndex < 0) {{
    ddIndex = 0;
  }} else if (ddIndex >= ddItems.length) {{
    ddIndex = ddItems.length - 1;
  }}
  renderDD();
}}

function closeDD() {{
  dd.style.display = "none";
  ddItems = [];
  ddIndex = -1;
}}

dd.addEventListener("mousedown", (e)=>{{ 
  const opt = e.target.closest(".opt"); 
  if (!opt) return; 
  heroInput.value = opt.dataset.v; 
  addBtn.click(); 
  closeDD(); 
}});

dd.addEventListener("mousemove", (e)=>{{
  const opt = e.target.closest(".opt"); 
  if (!opt) return;
  const idx = Array.prototype.indexOf.call(dd.children, opt);
  if (idx >= 0 && idx !== ddIndex) {{ ddIndex = idx; renderDD(); }}
}});

heroInput.addEventListener("input", ()=>openDD(filterHeroes(heroInput.value)));

heroInput.addEventListener("keydown", (e)=>{{
  if (dd.style.display === "block") {{
    if (e.key === "ArrowDown") {{
      e.preventDefault();
      if (ddItems.length) {{ ddIndex = Math.min(ddIndex + 1, ddItems.length - 1); renderDD(); }}
      return;
    }} else if (e.key === "ArrowUp") {{
      e.preventDefault();
      if (ddItems.length) {{ ddIndex = Math.max(ddIndex - 1, 0); renderDD(); }}
      return;
    }} else if (e.key === "Enter") {{
      e.preventDefault();
      if (ddIndex >= 0) {{ heroInput.value = ddItems[ddIndex]; addBtn.click(); closeDD(); }}
      return;
    }} else if (e.key === "Escape") {{
      closeDD();
      return;
    }}
  }}
  // Enter with dropdown closed = add current text if exact hero
  if (e.key === "Enter" && dd.style.display !== "block") {{
    addBtn.click();
  }}
}});

document.addEventListener("click",(e)=>{{ if(!e.target.closest(".control")) closeDD(); }});

// --- Selection
addBtn.onclick = () => {{ 
  const name = heroInput.value.trim(); 
  if (!name) return; 
  if (!DATA[name]) {{ alert("Unknown hero."); return; }} 
  if (sel.has(name)) {{ heroInput.value=""; return; }} 
  if (sel.size >= MAX) {{ alert("You already picked 12 heroes."); return; }} 
  sel.add(name); 
  heroInput.value=""; 
  closeDD(); 
  render(); 
}};
clearBtn.onclick = () => {{ sel.clear(); render(); }};

// --- Collect Abilities (for selected heroes)
function collectAbilities() {{
  const map = new Map();
  for (const h of sel) {{
    const H = DATA[h];
    // Model row (with HS if available)
    const hsModel = HS[h] || null;
    map.set("MODEL::"+h, {{
      kind: "model",
      ability: "Model — " + h,
      from: [h],
      pick: (hsModel && typeof hsModel.pick_num==="number") ? hsModel.pick_num : null,
      win:  (hsModel && typeof hsModel.win_pct ==="number") ? hsModel.win_pct
            : (typeof H.body_winrate==="number" ? H.body_winrate : null),
      img: H.hero_img || null
    }});
    // Abilities
    for (const a of (H.abilities||[])) {{
      const key = a.name;
      if (!map.has(key)) map.set(key, {{ kind:"ability", ability:a.name, from:[], pick:null, win:null, img:a.img||null }});
      const row = map.get(key);
      row.from.push(h);
      // win% (best across selected heroes)
      if (typeof a.win_pct === "number") row.win = (row.win==null) ? a.win_pct : Math.max(row.win, a.win_pct);
      // HS Pick #
      const hs = HS[a.name];
      if (hs && typeof hs.pick_num === "number") row.pick = hs.pick_num;
    }}
  }}
  return [...map.values()];
}}

// --- Pairs: show cross-hero only (ability↔ability OR hero↔ability across different selected heroes)
function collectPairs(selectedAbilityNames) {{
  if (!PAIRS || !Array.isArray(PAIRS)) return [];

  const selectedHeroes = new Set([...sel].map(canon));
  const selectedAbilities = new Set(selectedAbilityNames.map(canon));

  const rows = [];

  for (const p of PAIRS) {{
    const a1raw = p.a1, a2raw = p.a2;
    if (!a1raw || !a2raw) continue;

    const a1n = canon(a1raw), a2n = canon(a2raw);
    if (a1n === a2n) continue; // skip reflexive/self

    const o1 = abilityOwners.get(a1n); // Set(canon(hero)) if a1 is an ability name
    const o2 = abilityOwners.get(a2n); // Set(canon(hero)) if a2 is an ability name

    const a1IsAbility = !!o1;
    const a2IsAbility = !!o2;
    const a1IsHero    = selectedHeroes.has(a1n);
    const a2IsHero    = selectedHeroes.has(a2n);

    let ok = false;

    if (a1IsAbility && a2IsAbility) {{
      // both abilities must be in current selection and owned by DIFFERENT selected heroes
      if (selectedAbilities.has(a1n) && selectedAbilities.has(a2n)) {{
        outer:
        for (const h1 of (o1 || [])) {{
          if (!selectedHeroes.has(h1)) continue;
          for (const h2 of (o2 || [])) {{
            if (!selectedHeroes.has(h2)) continue;
            if (h1 !== h2) {{ ok = true; break outer; }}
          }}
        }}
      }}
    }} else if (a1IsHero && a2IsAbility) {{
      // hero + ability, require different hero
      if (selectedAbilities.has(a2n)) {{
        for (const h2 of (o2 || [])) {{
          if (!selectedHeroes.has(h2)) continue;
          if (h2 !== a1n) {{ ok = true; break; }}
        }}
      }}
    }} else if (a2IsHero && a1IsAbility) {{
      if (selectedAbilities.has(a1n)) {{
        for (const h1 of (o1 || [])) {{
          if (!selectedHeroes.has(h1)) continue;
          if (h1 !== a2n) {{ ok = true; break; }}
        }}
      }}
    }} else {{
      // hero-hero or tokens not in selection context → ignore
      ok = false;
    }}

    if (!ok) continue;

    rows.push({{
      a1: a1raw,
      a2: a2raw,
      a1_img: p.a1_img || null,
      a2_img: p.a2_img || null,
      syn: (typeof p.synergy === "number") ? p.synergy : null
    }});
  }}

  return rows;
}}

// --- Sorting Abilities
let sortAKey = "pick";  // default HS Pick #
let sortADir = "asc";
function setSortA(th) {{
  const key = th.dataset.key; if(!key) return;
  if (sortAKey === key) sortADir = (sortADir==="asc")?"desc":"asc"; else {{ sortAKey=key; sortADir=(key==="ability"||key==="from")?"asc":"asc"; }}
  theadA.querySelectorAll("th").forEach(el=>el.classList.remove("sort-asc","sort-desc"));
  th.classList.add(sortADir==="asc"?"sort-asc":"sort-desc");
  renderAbilities();
}}
theadA.addEventListener("click",(e)=>{{ const th=e.target.closest("th"); if(th) setSortA(th); }});

// --- Sorting Pairs
let sortPKey = "syn"; // default by Synergy
let sortPDir = "desc";
function setSortP(th) {{
  const key = th.dataset.key; if(!key) return;
  if (sortPKey === key) sortPDir = (sortPDir==="asc")?"desc":"asc"; else {{ sortPKey=key; sortPDir=(key==="a1"||key==="a2")?"asc":"desc"; }}
  theadP.querySelectorAll("th").forEach(el=>el.classList.remove("sort-asc","sort-desc"));
  th.classList.add(sortPDir==="asc"?"sort-asc":"sort-desc");
  renderPairs();
}}
theadP.addEventListener("click",(e)=>{{ const th=e.target.closest("th"); if(th) setSortP(th); }});

// --- Render
function render() {{
  // pills
  pills.innerHTML = "";
  [...sel].sort((a,b)=>a.localeCompare(b)).forEach(h=>{{
    const el=document.createElement("div"); el.className="pill";
    el.innerHTML=`<b>${{escapeHtml(h)}}</b> <button title="Remove" aria-label="Remove" onclick="removeHero('${{escapeAttr(h)}}')">✕</button>`;
    pills.appendChild(el);
  }});
  hint.textContent = `${{sel.size}} / ${{MAX}} selected`;

  // set sort indicators
  theadA.querySelectorAll("th").forEach(el=>el.classList.remove("sort-asc","sort-desc"));
  const tha = theadA.querySelector(`th[data-key="${{sortAKey}}"]`); if (tha) tha.classList.add(sortADir==="asc"?"sort-asc":"sort-desc");
  theadP.querySelectorAll("th").forEach(el=>el.classList.remove("sort-asc","sort-desc"));
  const thp = theadP.querySelector(`th[data-key="${{sortPKey}}"]`); if (thp) thp.classList.add(sortPDir==="asc"?"sort-asc":"sort-desc");

  renderAbilities();
  renderPairs();
}}
window.removeHero = (h)=>{{ sel.delete(h); render(); }};

let cachedAbilities = [];
function renderAbilities() {{
  const rows = collectAbilities();
  cachedAbilities = rows; // keep for pair filtering

  // rebuild owners with canonical keys
  abilityOwners = new Map();
  for (const r of rows) {{
    if (r.kind === "ability") {{
      const aKey = canon(r.ability);
      const owners = new Set();
      for (const h of (r.from || [])) owners.add(canon(h));
      abilityOwners.set(aKey, owners);
    }}
  }}

  const cmp = (a,b)=>{{
    let av=a[sortAKey], bv=b[sortAKey];
    if (sortAKey==="ability") {{ av=String(av||""); bv=String(bv||""); return sortADir==="asc"? av.localeCompare(bv): bv.localeCompare(av); }}
    if (sortAKey==="from") {{ av=(a.from||[]).length; bv=(b.from||[]).length; return sortADir==="asc"? av-bv : bv-av; }}
    const na=(typeof av==="number")?av:Infinity, nb=(typeof bv==="number")?bv:Infinity, d=na-nb;
    return sortADir==="asc"? d : -d;
  }};
  rows.sort(cmp);

  tbodyA.innerHTML = rows.map(r=>rowAbilityHtml(r)).join("");
  countA.textContent = `${{rows.length}} rows`;
}}

function renderPairs() {{
  const selectedNames = cachedAbilities.filter(r=>r.kind==="ability").map(r=>r.ability);
  const rows = collectPairs(selectedNames);

  const cmp = (a,b)=>{{
    if (sortPKey==="a1" || sortPKey==="a2") {{
      const av=String(a[sortPKey]||""), bv=String(b[sortPKey]||"");
      return sortPDir==="asc"? av.localeCompare(bv) : bv.localeCompare(av);
    }}
    const na=(typeof a.syn==="number")?a.syn:-Infinity;
    const nb=(typeof b.syn==="number")?b.syn:-Infinity;
    const d=na-nb;
    return sortPDir==="asc"? d : -d;
  }};
  rows.sort(cmp);

  tbodyP.innerHTML = rows.map(r=>rowPairHtml(r)).join("");
  countP.textContent = `${{rows.length}} combos`;
}}

function rowAbilityHtml(r) {{
  const heroList=(r.from||[]).map(h=>`<span class="badge">${{escapeHtml(h)}}</span>`).join(" ");
  return `<tr>
    <td>${{r.img?`<img class="img" src="${{escapeAttr(r.img)}}" alt=""> `:""}}<b>${{escapeHtml(r.ability)}}</b></td>
    <td>${{heroList}}</td>
    <td class="k">${{fmtNum(r.pick)}}</td>
    <td class="k">${{fmtPct(r.win)}}</td>
  </tr>`;
}}
function rowPairHtml(r) {{
  const img = (src) => src ? `<img class="img" src="${{escapeAttr(src)}}" alt=""> ` : "";
  return `<tr>
    <td>${{img(r.a1_img)}}<b>${{escapeHtml(r.a1)}}</b></td>
    <td>${{img(r.a2_img)}}<b>${{escapeHtml(r.a2)}}</b></td>
    <td class="k">${{fmtNum(r.syn)}}</td>
  </tr>`;
}}
function fmtNum(v) {{ return (typeof v === "number") ? v.toFixed(2) : "<span class='muted'>—</span>"; }}
function fmtPct(v) {{ return (typeof v === "number") ? v.toFixed(2) + "%" : "<span class='muted'>—</span>"; }}
function escapeHtml(s) {{ return String(s).replace(/[&<>"']/g, m => ({{'&':'&amp;','<':'&lt;','&gt;':'&gt;','"':'&quot;',"'":"&#39;"}})[m]); }}
function escapeAttr(s) {{ return String(s).replace(/["']/g, m => (m=='"'?'&quot;':'&#39;')); }}

// boot
render();
</script>
</body>
</html>
"""


def main():
    hs_map  = load_high_skill_map()
    pairs   = load_pairs()
    compact = build_compact_from_hs(hs_map)
    html = mk_html(compact, hs_map, pairs)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    OUTFILE.write_text(html, encoding="utf-8")
    print(f"Wrote {OUTFILE}")


if __name__ == "__main__":
    main()

