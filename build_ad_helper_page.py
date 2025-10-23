#!/usr/bin/env python3
"""
Build static Ability Draft helper page (categorized abilities).

Inputs:
  - cache/ability_high_skill.json  (single source of truth; contains ability + hero entries)
  - cache/ability_roles.json       (manual labels: carry/support/both)   [optional]
  - cache/ability_pairs.json       (combos)                              [optional]

Output:
  - dist/ad_helper.html
"""
import json
from pathlib import Path

INFILE_HS     = Path("cache/ability_high_skill.json")
INFILE_ROLES  = Path("cache/ability_roles.json")
INFILE_PAIRS  = Path("cache/ability_pairs.json")

OUTDIR  = Path("dist")
OUTFILE = OUTDIR / "ad_helper.html"

# ---------- IO ----------

def _load(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def load_high_skill():
    """
    Returns:
      by_hero_compact: { Hero: {hero_id, hero_img, body_winrate, abilities:[{id,name,img,win_pct, [pick_num]}] } }
      hs_raw:          raw "data" dict from ability_high_skill.json
    """
    if not INFILE_HS.exists():
        raise SystemExit(f"Missing {INFILE_HS}. Run the HS scraper first.")
    doc = _load(INFILE_HS)
    data = doc.get("data", {}) if isinstance(doc, dict) else {}
    if not isinstance(data, dict):
        data = {}

    # Build by-hero compact block from hero objects inside HS
    by_hero = {}
    for k, v in data.items():
        if isinstance(v, dict) and "abilities" in v:
            by_hero[k] = v

    # Convert to page-expected shape and also append hero model as a draftable "ability"
    compact = {}
    for h, hrow in by_hero.items():
        abil_list = []
        for a in hrow.get("abilities", []):
            abil_list.append({
                "id": a.get("ability_id"),
                "name": a.get("ability_name"),
                "img": a.get("img"),
                "win_pct": a.get("win_pct"),
            })

        # Also expose the hero model itself as an "ability" so it can be labeled & shown
        hs_entry = data.get(h, {}) if isinstance(data.get(h, {}), dict) else {}
        model_row = {
            "id": None,
            "name": h,
            "img": hrow.get("hero_img"),
            "win_pct": hrow.get("win_pct") or hrow.get("body_winrate") or hs_entry.get("win_pct"),
            "pick_num": hs_entry.get("pick_num"),
        }
        if all(a.get("name") != h for a in abil_list):
            abil_list.append(model_row)

        compact[h] = {
            "hero_id": hrow.get("hero_id"),
            "hero_img": hrow.get("hero_img"),
            "body_winrate": hrow.get("win_pct") or hrow.get("body_winrate"),
            "abilities": abil_list,
        }

    return compact, data  # by-hero compact, and raw HS "data" dict

def load_roles():
    if not INFILE_ROLES.exists():
        return {}
    try:
        doc = _load(INFILE_ROLES)
        labels = doc.get("labels", {})
        return labels if isinstance(labels, dict) else {}
    except Exception:
        return {}

def load_pairs():
    if not INFILE_PAIRS.exists():
        return []
    try:
        doc = _load(INFILE_PAIRS)
        pairs = doc.get("pairs", [])
        return pairs if isinstance(pairs, list) else []
    except Exception:
        return []

# ---------- HTML ----------

def mk_html(by_hero: dict, hs_raw: dict, roles: dict, pairs: list) -> str:
    # Compact payload (same shape as before for DATA)
    heroes = sorted(by_hero.keys(), key=lambda s: s.lower())

    compact = {}
    for h in heroes:
        hrow = by_hero[h]
        compact[h] = {
            "hero_id": hrow.get("hero_id"),
            "hero_img": hrow.get("hero_img"),
            "body_winrate": hrow.get("body_winrate"),
            "abilities": [
                {
                    "id": a.get("id"),
                    "name": a.get("name"),
                    "img": a.get("img"),
                    "win_pct": a.get("win_pct"),
                    "pick_num": a.get("pick_num"),  # present for hero models we appended
                }
                for a in hrow.get("abilities", [])
                if isinstance(a, dict)
            ],
        }

    # ability -> {win_pct, pick_num} map from HS for ANY entry with pick_num (abilities or hero models)
    ability_stats = {}
    for k, v in (hs_raw or {}).items():
        if isinstance(v, dict) and "pick_num" in v:
            ability_stats[k] = {
                "win_pct": v.get("win_pct"),
                "pick_num": v.get("pick_num"),
            }

    data_json   = json.dumps(compact, ensure_ascii=False)
    hs_json     = json.dumps(ability_stats, ensure_ascii=False)
    roles_json  = json.dumps(roles or {}, ensure_ascii=False)
    pairs_json  = json.dumps(pairs or [], ensure_ascii=False)

    TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Ability Draft Helper (static)</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root { --bg:#0f1115; --card:#151923; --muted:#9aa3b2; --text:#e7ecf3; --accent:#7aa2f7; --pill:#1f2633; }
  html,body { margin:0; padding:0; background:var(--bg); color:var(--text); font:14px/1.4 system-ui,-apple-system,Segoe UI,Roboto,Arial; }
  .wrap { max-width:1300px; margin:24px auto; padding:0 16px; }
  h1 { font-size:20px; margin:0 0 12px; }
  h2 { font-size:16px; margin:14px 0 8px; color:var(--muted); }
  .card { background:var(--card); border-radius:14px; padding:14px; box-shadow:0 2px 8px rgba(0,0,0,.25); }
  .row { display:flex; gap:12px; flex-wrap:wrap; }
  .col { flex:1 1 100%; min-width:300px; }
  .col-third { flex:1 1 calc(33.333% - 8px); min-width:320px; }
  .control { position:relative; }
  input[type=text] { width:100%; padding:10px 12px; border-radius:10px; border:1px solid #2a3142; background:#0f1320; color:var(--text); }
  button { padding:8px 12px; border-radius:10px; border:1px solid #2a3142; background:#0f1320; color:var(--text); cursor:pointer; }
  .pills { display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; }
  .pill { background:var(--pill); border:1px solid #2a3142; padding:6px 10px; border-radius:100px; display:flex; align-items:center; gap:8px; }
  .pill b { font-weight:600; }
  .pill button { border:none; background:transparent; color:var(--muted); padding:0 2px; font-size:16px; line-height:1; }
  .muted { color:var(--muted); }
  table { width:100%; border-collapse:collapse; margin-top:10px; }
  th, td { padding:8px 10px; border-bottom:1px solid #2a3142; text-align:left; vertical-align:middle; }
  th { position:sticky; top:0; background:var(--card); z-index:1; user-select:none; cursor:pointer; }
  th.sort-asc::after { content:" \\25B2"; }
  th.sort-desc::after { content:" \\25BC"; }
  .img { width:28px; height:28px; border-radius:6px; background:#0f1320; display:inline-block; vertical-align:middle; }
  .badge { display:inline-block; padding:2px 6px; border:1px solid #2a3142; border-radius:8px; margin-right:4px; white-space:nowrap; max-width:160px; overflow:hidden; text-overflow:ellipsis; }
  .k { font-variant-numeric: tabular-nums; }
  .small { font-size:12px; }
  .footer { margin-top:8px; color:var(--muted); font-size:12px; }
  .dropdown { position:absolute; left:0; right:0; top:100%; margin-top:6px; background:#0f1320; border:1px solid #2a3142; border-radius:10px; max-height:240px; overflow:auto; z-index:5; display:none; }
  .dropdown .opt { padding:8px 10px; border-bottom:1px solid #1c2435; }
  .dropdown .opt:last-child { border-bottom:none; }
  .dropdown .opt:hover, .dropdown .opt.active { background:#131a2a; }
  .triplet { display:flex; gap:12px; flex-wrap:wrap; }
  th[data-key="pick"], th[data-key="win"], td.k { white-space:nowrap; }
  /* remove overlay button style */
  .cell-ability { position: relative; }
  .icon-wrap { position: relative; display:inline-block; width:28px; height:28px; vertical-align:middle; margin-right:4px; }
  .icon-wrap .img { position:absolute; inset:0; width:100%; height:100%; border-radius:6px; }
  .icon-wrap .delBtn { position:absolute; inset:0; display:none; border:none; border-radius:6px; background: rgba(220,53,69,0); cursor:pointer; }
  .icon-wrap:hover .delBtn { display:block; background: rgba(220,53,69,0.35); }
  .icon-wrap .delBtn::before { content: "✕"; display:block; width:100%; height:100%; text-align:center; line-height:28px; font-weight:800; color:#fff; text-shadow: 0 1px 2px rgba(0,0,0,.6); }
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
    <h2 style="display:flex; align-items:center; justify-content:space-between;">
      <span>Abilities</span>
      <button id="restoreBtn" class="small" title="Show all hidden abilities">Restore removed</button>
    </h2>
    <div class="triplet">
      <div class="col-third">
        <div class="muted small">Carry</div>
        <table id="tblCarry">
          <thead><tr>
            <th data-key="ability">Ability</th>
            <th data-key="good">Goodness</th>
            <th data-key="pick">Pick #</th>
            <th data-key="win">Win %</th>
          </tr></thead>
          <tbody></tbody>
        </table>
        <div class="footer" id="countCarry"></div>
      </div>
      <div class="col-third">
        <div class="muted small">Both</div>
        <table id="tblBoth">
          <thead><tr>
            <th data-key="ability">Ability</th>
            <th data-key="good">Goodness</th>
            <th data-key="pick">Pick #</th>
            <th data-key="win">Win %</th>
          </tr></thead>
          <tbody></tbody>
        </table>
        <div class="footer" id="countBoth"></div>
      </div>
      <div class="col-third">
        <div class="muted small">Support</div>
        <table id="tblSupport">
          <thead><tr>
            <th data-key="ability">Ability</th>
            <th data-key="good">Goodness</th>
            <th data-key="pick">Pick #</th>
            <th data-key="win">Win %</th>
          </tr></thead>
          <tbody></tbody>
        </table>
        <div class="footer" id="countSupport"></div>
      </div>
    </div>
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
const DATA   = <<DATA_JSON>>;   // by-hero compact (from HS)
const HS     = <<HS_JSON>>;     // ability/hero -> {win_pct, pick_num}
const ROLES  = <<ROLES_JSON>>;  // ability -> "carry" | "support" | "both"
const PAIRS  = <<PAIRS_JSON>>;

const HEROES = Object.keys(DATA).sort((a,b)=>a.localeCompare(b));
const MAX = 12;

const $ = (id)=>document.getElementById(id);
const heroInput = $("heroInput");
const dd = $("dd");
const addBtn = $("addBtn");
const clearBtn = $("clearBtn");
const pills = $("selPills");
const hint = $("selHint");

// Carry table
const tblC = $("tblCarry"), theadC = tblC.querySelector("thead"), tbodyC = tblC.querySelector("tbody"), countC = $("countCarry");
// Both table
const tblB = $("tblBoth"),  theadB = tblB.querySelector("thead"), tbodyB = tblB.querySelector("tbody"), countB = $("countBoth");
// Support table
const tblS = $("tblSupport"), theadS = tblS.querySelector("thead"), tbodyS = tblS.querySelector("tbody"), countS = $("countSupport");

// Combos
const tblP = $("tblPairs");
const tbodyP = tblP.querySelector("tbody");
const theadP = tblP.querySelector("thead");
const countP = $("countPairs");

// In-memory hidden abilities (reset on reload)
try { localStorage.removeItem("ad_hidden_abilities"); } catch (e) {}
const hidden = new Set();
function hideAbility(name){ hidden.add(canon(name)); renderTables(); }
function unhideAll(){ hidden.clear(); renderTables(); }
$("restoreBtn").onclick = unhideAll;

// --- Canonicalize names
function canon(s) {
  return String(s || "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u2018\u2019]/g, "'")
    .replace(/[\u201C\u201D]/g, '"')
    .replace(/[\u2013\u2014]/g, "-")
    .replace(/[._]/g, " ")
    .replace(/[^\w\s'-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

// Abbreviate long hero names with tooltip (kept if you later re-add badges)
function abbreviateHero(h) {
  const s = String(h || "").trim();
  if (s.length <= 12) return s;
  const parts = s.split(/\s+/);
  if (parts.length === 1) return s.slice(0, 11) + "…";
  const first = parts[0];
  const restInitials = parts.slice(1).map(p => (p ? p[0] + "." : "")).join(" ");
  let out = `${first} ${restInitials}`;
  if (out.length <= 12) return out;
  return first.slice(0, 9) + "…";
}

// Ability owners for current selection: canon(ability) -> Set(canon(hero))
let abilityOwners = new Map();

// --- Autocomplete
let ddItems = [], ddIndex = -1;
function filterHeroes(q) {
  q = q.trim().toLowerCase();
  if (!q) return HEROES.slice(0, 50);
  return HEROES.filter(h => h.toLowerCase().startsWith(q)).slice(0, 50);
}
function renderDD() {
  dd.innerHTML = ddItems.map((h,i)=>`<div class="opt${i===ddIndex?' active':''}" data-v="${escapeAttr(h)}">${escapeHtml(h)}</div>`).join("");
  dd.style.display = ddItems.length ? "block" : "none";
}
function openDD(items) {
  ddItems = items || [];
  if (!ddItems.length) ddIndex = -1;
  else if (ddIndex < 0) ddIndex = 0;
  else if (ddIndex >= ddItems.length) ddIndex = ddItems.length - 1;
  renderDD();
}
function closeDD(){ dd.style.display = "none"; ddItems = []; ddIndex = -1; }

dd.addEventListener("mousedown", (e)=>{
  const opt = e.target.closest(".opt"); 
  if (!opt) return; 
  heroInput.value = opt.dataset.v; 
  addBtn.click(); 
  closeDD(); 
});
dd.addEventListener("mousemove", (e)=>{
  const opt = e.target.closest(".opt"); 
  if (!opt) return;
  const idx = Array.prototype.indexOf.call(dd.children, opt);
  if (idx >= 0 && idx !== ddIndex) { ddIndex = idx; renderDD(); }
});
heroInput.addEventListener("input", ()=>openDD(filterHeroes(heroInput.value)));
heroInput.addEventListener("keydown", (e)=>{
  if (dd.style.display === "block") {
    if (e.key === "ArrowDown") { e.preventDefault(); if (ddItems.length) { ddIndex = Math.min(ddIndex + 1, ddItems.length - 1); renderDD(); } return; }
    if (e.key === "ArrowUp")   { e.preventDefault(); if (ddItems.length) { ddIndex = Math.max(ddIndex - 1, 0); renderDD(); } return; }
    if (e.key === "Enter")     { e.preventDefault(); if (ddIndex >= 0) { heroInput.value = ddItems[ddIndex]; addBtn.click(); closeDD(); } return; }
    if (e.key === "Escape")    { closeDD(); return; }
  }
  if (e.key === "Enter" && dd.style.display !== "block") addBtn.click();
});
document.addEventListener("click",(e)=>{ if(!e.target.closest(".control")) closeDD(); });

// --- Selection
const sel = new Set();
addBtn.onclick = () => { 
  const name = heroInput.value.trim(); 
  if (!name) return; 
  if (!DATA[name]) { alert("Unknown hero."); return; } 
  if (sel.has(name)) { heroInput.value=""; return; } 
  if (sel.size >= MAX) { alert("You already picked 12 heroes."); return; } 
  sel.add(name); 
  heroInput.value=""; 
  closeDD(); 
  render(); 
};
clearBtn.onclick = () => { sel.clear(); render(); };

// --- Collect Abilities (for selected heroes), attach roles and pick
function collectAbilities() {
  const map = new Map();
  for (const h of sel) {
    const H = DATA[h];
    const hsModel = HS[h] || null;

    // Model row in selection context (not in the 3 tables)
    map.set("MODEL::"+h, {
      kind: "model",
      ability: "Model — " + h,
      from: [h],
      pick: (hsModel && typeof hsModel.pick_num==="number") ? hsModel.pick_num : null,
      win:  (typeof H.body_winrate==="number") ? H.body_winrate :
            (hsModel && typeof hsModel.win_pct==="number" ? hsModel.win_pct : null),
      img: H.hero_img || null,
      role: null,
    });

    // Abilities (including hero model we appended on the Python side)
    for (const a of (H.abilities||[])) {
      const key = a.name;
      if (!map.has(key)) map.set(key, { kind:"ability", ability:a.name, from:[], pick:null, win:null, img:a.img||null, role:null });
      const row = map.get(key);
      row.from.push(h);
      // win% (best across selected heroes)
      if (typeof a.win_pct === "number") row.win = (row.win==null) ? a.win_pct : Math.max(row.win, a.win_pct);
      // HS Pick # (prefer HS table, fallback to embedded a.pick_num if present)
      const hs = HS[a.name];
      if (hs && typeof hs.pick_num === "number") row.pick = hs.pick_num;
      else if (typeof a.pick_num === "number") row.pick = a.pick_num;
      // role
      const r = ROLES[a.name];
      row.role = (r==="carry"||r==="support"||r==="both") ? r : row.role;
    }
  }
  return [...map.values()];
}

// --- Pairs (cross-hero only)
function collectPairs(selectedAbilityNames) {
  if (!PAIRS || !Array.isArray(PAIRS)) return [];
  const selectedHeroes = new Set([...sel].map(canon));
  const selectedAbilities = new Set(selectedAbilityNames.map(canon));
  const rows = [];
  for (const p of PAIRS) {
    const a1raw = p.a1, a2raw = p.a2; if (!a1raw || !a2raw) continue;
    const a1n = canon(a1raw), a2n = canon(a2raw); if (a1n === a2n) continue;
    const o1 = abilityOwners.get(a1n), o2 = abilityOwners.get(a2n);
    const a1IsAbility = !!o1, a2IsAbility = !!o2;
    const a1IsHero = selectedHeroes.has(a1n), a2IsHero = selectedHeroes.has(a2n);
    let ok = false;
    if (a1IsAbility && a2IsAbility) {
      if (selectedAbilities.has(a1n) && selectedAbilities.has(a2n)) {
        outer: for (const h1 of (o1 || [])) { if (!selectedHeroes.has(h1)) continue;
          for (const h2 of (o2 || [])) { if (!selectedHeroes.has(h2)) continue;
            if (h1 !== h2) { ok = true; break outer; } } }
      }
    } else if (a1IsHero && a2IsAbility) {
      if (selectedAbilities.has(a2n)) { for (const h2 of (o2 || [])) { if (!selectedHeroes.has(h2)) continue; if (h2 !== a1n) { ok = true; break; } } }
    } else if (a2IsHero && a1IsAbility) {
      if (selectedAbilities.has(a1n)) { for (const h1 of (o1 || [])) { if (!selectedHeroes.has(h1)) continue; if (h1 !== a2n) { ok = true; break; } } }
    }
    if (!ok) continue;
    rows.push({ a1:a1raw, a2:a2raw, a1_img:p.a1_img||null, a2_img:p.a2_img||null, syn:(typeof p.synergy==="number")?p.synergy:null });
  }
  return rows;
}

// --- Sorting helpers
function makeSortState(defaultKey, defaultDir){ return { key:defaultKey, dir:defaultDir }; }
// Default sort by Goodness (10 best at top)
const sortC = makeSortState("good", "desc");
const sortB = makeSortState("good", "desc");
const sortS = makeSortState("good", "desc");
let sortPKey = "syn", sortPDir = "desc";

function bindSort(thead, state, renderFn){
  thead.addEventListener("click",(e)=>{
    const th=e.target.closest("th"); if(!th) return;
    const k=th.dataset.key; if(!k) return;
    if (state.key===k) state.dir = (state.dir==="asc")?"desc":"asc";
    else { state.key=k; state.dir=(k==="ability")?"asc":"desc"; }
    thead.querySelectorAll("th").forEach(el=>el.classList.remove("sort-asc","sort-desc"));
    th.classList.add(state.dir==="asc"?"sort-asc":"sort-desc");
    renderFn();
  });
}
bindSort(tblC.querySelector("thead"), sortC, renderTables);
bindSort(tblB.querySelector("thead"), sortB, renderTables);
bindSort(tblS.querySelector("thead"), sortS, renderTables);
theadP.addEventListener("click",(e)=>{ const th=e.target.closest("th"); if(!th) return;
  const k=th.dataset.key; if(!k) return;
  if (sortPKey===k) sortPDir = (sortPDir==="asc")?"desc":"asc";
  else { sortPKey=k; sortPDir=(k==="a1"||k==="a2")?"asc":"desc"; }
  theadP.querySelectorAll("th").forEach(el=>el.classList.remove("sort-asc","sort-desc"));
  th.classList.add(sortPDir==="asc"?"sort-asc":"sort-desc");
  renderPairs();
});

// --- Render
function render(){
  // pills
  pills.innerHTML = "";
  [...sel].sort((a,b)=>a.localeCompare(b)).forEach(h=>{
    const el=document.createElement("div"); el.className="pill";
    el.innerHTML=`<b>${escapeHtml(h)}</b> <button title="Remove" aria-label="Remove" onclick="removeHero('${escapeAttr(h)}')">✕</button>`;
    pills.appendChild(el);
  });
  hint.textContent = `${sel.size} / ${MAX} selected`;
  renderTables();
  renderPairs();
}
window.removeHero = (h)=>{ sel.delete(h); render(); };

// clicks on overlay delete button
[tbodyC, tbodyB, tbodyS].forEach(tb=>{
  tb.addEventListener("click", (e)=>{
    const btn = e.target.closest(".delBtn");
    if (!btn) return;
    const ability = btn.dataset.ability;
    if (ability) hideAbility(ability);
  });
});

let cachedAbilities = [];
function renderTables(){
  const rows = collectAbilities();
  cachedAbilities = rows;

  // rebuild owners with canonical keys
  abilityOwners = new Map();
  for (const r of rows) {
    if (r.kind === "ability") {
      const aKey = canon(r.ability);
      const owners = new Set();
      for (const h of (r.from || [])) owners.add(canon(h));
      abilityOwners.set(aKey, owners);
    }
  }

  // split by role (skip hidden)
  const all = [];
  const carry = [], both = [], support = [];
  for (const r of rows) {
    if (r.kind !== "ability") continue; // keep models out of the 3 tables
    if (hidden.has(canon(r.ability))) continue;
    all.push(r);
    if (r.role === "carry") carry.push(r);
    else if (r.role === "both") both.push(r);
    else if (r.role === "support") support.push(r);
  }

  // --- compute Goodness (scale 1..10; 10 best)
  // raw = pick_num * (100 - win_pct); lower raw is better
  function rawScore(row){
    const p = row.pick, w = row.win;
    if (typeof p !== "number" || typeof w !== "number") return null;
    return p * (100 - w);
  }
  const scores = all.map(rawScore).filter(v=>typeof v==="number" && isFinite(v));
  const rmin = Math.min(...scores), rmax = Math.max(...scores);
  function scaled(row){
    const r = rawScore(row);
    if (r==null || !isFinite(r)) return null;
    if (!(scores.length)) return null;
    if (rmax === rmin) return 10; // everything identical → 10
    // map raw in [rmin..rmax] to [10..1]
    const t = 1 + 9 * (rmax - r) / (rmax - rmin);
    return Math.max(1, Math.min(10, t));
  }
  for (const r of all) r.good = scaled(r);

  // sorters
  const cmp = (state)=>(a,b)=>{
    const key = state.key, dir = state.dir;
    let av=a[key], bv=b[key];
    if (key==="ability") { av=String(av||""); bv=String(bv||""); return dir==="asc"? av.localeCompare(bv): bv.localeCompare(av); }
    // numeric: push nulls to bottom for desc, top for asc accordingly
    const an = (typeof av==="number" && isFinite(av)) ? av : (dir==="asc" ? Infinity : -Infinity);
    const bn = (typeof bv==="number" && isFinite(bv)) ? bv : (dir==="asc" ? Infinity : -Infinity);
    const d = an - bn;
    return dir==="asc"? d : -d;
  };

  carry.sort(cmp(sortC)); both.sort(cmp(sortB)); support.sort(cmp(sortS));

  tbodyC.innerHTML = carry.map(r=>rowAbilityHtml(r)).join("");
  tbodyB.innerHTML = both.map(r=>rowAbilityHtml(r)).join("");
  tbodyS.innerHTML = support.map(r=>rowAbilityHtml(r)).join("");

  countC.textContent = `${carry.length} rows`;
  countB.textContent = `${both.length} rows`;
  countS.textContent = `${support.length} rows`;

  // mark header sort defaults
  [ [theadC, sortC], [theadB, sortB], [theadS, sortS] ].forEach(([th, st])=>{
    th.querySelectorAll("th").forEach(el=>el.classList.remove("sort-asc","sort-desc"));
    const el = th.querySelector(`th[data-key="${st.key}"]`);
    if (el) el.classList.add(st.dir==="asc"?"sort-asc":"sort-desc");
  });
}

function renderPairs(){
  const selectedNames = cachedAbilities.filter(r=>r.kind==="ability").map(r=>r.ability);
  const rows = collectPairs(selectedNames);
  const cmp = (a,b)=>{
    if (sortPKey==="a1" || sortPKey==="a2") {
      const av=String(a[sortPKey]||""), bv=String(b[sortPKey]||"");
      return sortPDir==="asc"? av.localeCompare(bv) : bv.localeCompare(av);
    }
    const na=(typeof a.syn==="number")?a.syn:-Infinity;
    const nb=(typeof b.syn==="number")?b.syn:-Infinity;
    const d=na-nb;
    return sortPDir==="asc"? d : -d;
  };
  rows.sort(cmp);
  tbodyP.innerHTML = rows.map(r=>rowPairHtml(r)).join("");
  countP.textContent = `${rows.length} combos`;
}

function rowAbilityHtml(r){
  const icon = r.img
    ? `<span class="icon-wrap">
         <img class="img" src="${escapeAttr(r.img)}" alt="">
         <button class="delBtn" title="Remove from view" data-ability="${escapeAttr(r.ability)}"></button>
       </span>`
    : `<button class="delBtn" title="Remove from view" data-ability="${escapeAttr(r.ability)}"></button>`;
  return `<tr data-ability="${escapeAttr(r.ability)}">
    <td class="cell-ability">${icon}<b>${escapeHtml(r.ability)}</b></td>
    <td class="k">${fmtNum(r.good)}</td>
    <td class="k">${fmtNum(r.pick)}</td>
    <td class="k">${fmtPct(r.win)}</td>
  </tr>`;
}

function rowPairHtml(r){
  const img = (src) => src ? `<img class="img" src="${escapeAttr(src)}" alt=""> ` : "";
  return `<tr>
    <td>${img(r.a1_img)}<b>${escapeHtml(r.a1)}</b></td>
    <td>${img(r.a2_img)}<b>${escapeHtml(r.a2)}</b></td>
    <td class="k">${fmtNum(r.syn)}</td>
  </tr>`;
}
function fmtNum(v){ return (typeof v === "number" && isFinite(v)) ? v.toFixed(2) : "<span class='muted'>—</span>"; }
function fmtPct(v){ return (typeof v === "number" && isFinite(v)) ? v.toFixed(2) + "%" : "<span class='muted'>—</span>"; }
function escapeHtml(s){ return String(s).replace(/[&<>\"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":"&#39;"})[m]); }
function escapeAttr(s){ return String(s).replace(/["']/g, m => (m=='"'?'&quot;':'&#39;')); }

// boot
render();
</script>
</body>
</html>
"""
    return (
        TEMPLATE
        .replace("<<DATA_JSON>>", data_json)
        .replace("<<HS_JSON>>", hs_json)
        .replace("<<ROLES_JSON>>", roles_json)
        .replace("<<PAIRS_JSON>>", pairs_json)
    )

# ---------- MAIN ----------

def main():
    by_hero, hs_raw = load_high_skill()
    roles = load_roles()
    pairs = load_pairs()

    # Terminal warning for unlabeled abilities
    ability_names = {
        k for k, v in (hs_raw or {}).items()
        if isinstance(v, dict) and "pick_num" in v
    }
    labeled = set(roles.keys())
    missing = sorted(ability_names - labeled)
    if missing:
        print(f"WARN: {len(missing)} unlabeled abilities (not shown in UI). Add to {INFILE_ROLES}:")
        for name in missing[:25]:
            print(f"  - {name}")
        if len(missing) > 25:
            print(f"  ... (+{len(missing)-25} more)")

    html = mk_html(by_hero, hs_raw, roles, pairs)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    OUTFILE.write_text(html, encoding="utf-8")
    print(f"Wrote {OUTFILE}")

if __name__ == "__main__":
    main()

