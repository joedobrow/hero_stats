#!/usr/bin/env python3
"""
Build Ability Draft helper (categorized abilities) with Supabase realtime.
- Realtime sync via a room id in #r=...
- Cold-join sync (new tab requests state; existing tabs reply)
- Versioning to avoid echo/race (source + rev)
- Hide/unhide syncs across participants

Inputs:
  - cache/ability_high_skill.json
  - cache/ability_roles.json   [optional]
  - cache/ability_pairs.json   [optional]
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
    if not INFILE_HS.exists():
        raise SystemExit(f"Missing {INFILE_HS}. Run the HS scraper first.")
    doc = _load(INFILE_HS)
    data = doc.get("data", {}) if isinstance(doc, dict) else {}
    if not isinstance(data, dict):
        data = {}

    by_hero = {}
    for k, v in data.items():
        if isinstance(v, dict) and "abilities" in v:
            by_hero[k] = v

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

    return compact, data

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
                    "pick_num": a.get("pick_num"),
                }
                for a in hrow.get("abilities", [])
                if isinstance(a, dict)
            ],
        }

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
<title>Ability Draft Helper (realtime)</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root { --bg:#0f1115; --card:#151923; --muted:#9aa3b2; --text:#e7ecf3; --pill:#1f2633; }
  html,body { margin:0; padding:0; background:var(--bg); color:var(--text); font:14px/1.4 system-ui,-apple-system,Segoe UI,Roboto,Arial; }
  .wrap { max-width:1300px; margin:24px auto; padding:0 16px; }
  h1 { font-size:20px; margin:0 0 12px; display:flex; align-items:center; gap:10px; }
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
  .k { font-variant-numeric: tabular-nums; }
  .small { font-size:12px; }
  .footer { margin-top:8px; color:var(--muted); font-size:12px; }
  .dropdown { position:absolute; left:0; right:0; top:100%; margin-top:6px; background:#0f1320; border:1px solid #2a3142; border-radius:10px; max-height:240px; overflow:auto; z-index:5; display:none; }
  .dropdown .opt { padding:8px 10px; border-bottom:1px solid #1c2435; }
  .dropdown .opt:last-child { border-bottom:none; }
  .dropdown .opt:hover, .dropdown .opt.active { background:#131a2a; }
  .triplet { display:flex; gap:12px; flex-wrap:wrap; }
  th[data-key="pick"], th[data-key="win"], td.k { white-space:nowrap; }
  .cell-ability { position: relative; }
  .icon-wrap { position: relative; display:inline-block; width:28px; height:28px; vertical-align:middle; margin-right:4px; }
  .icon-wrap .img { position:absolute; inset:0; width:100%; height:100%; border-radius:6px; }
  .icon-wrap .delBtn { position:absolute; inset:0; display:none; border:none; border-radius:6px; background: rgba(220,53,69,0); cursor:pointer; }
  .icon-wrap:hover .delBtn { display:block; background: rgba(220,53,69,0.35); }
  .icon-wrap .delBtn::before { content: "✕"; display:block; width:100%; height:100%; text-align:center; line-height:28px; font-weight:800; color:#fff; text-shadow: 0 1px 2px rgba(0,0,0,.6); }
  .room { color:var(--muted); font-size:12px; }
</style>

<!-- Supabase client -->
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
</head>
<body>
<div class="wrap">
  <h1>
    <span>Ability Draft Helper</span>
    <span class="room" id="roomTag"></span>
    <button id="shareBtn" class="small" title="Copy room link">Share Room</button>
    <span id="copied" class="small muted" style="display:none;">Copied ✓</span>
  </h1>

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
            <th data-key="good">Goody</th>
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
            <th data-key="good">Goody</th>
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
            <th data-key="good">Goody</th>
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
const DATA   = <<DATA_JSON>>;
const HS     = <<HS_JSON>>;
const ROLES  = <<ROLES_JSON>>;
const PAIRS  = <<PAIRS_JSON>>;

const HEROES = Object.keys(DATA).sort((a,b)=>a.localeCompare(b));
const MAX = 12;
const $ = (id)=>document.getElementById(id);

// UI refs
const heroInput = $("heroInput"), dd = $("dd"), addBtn = $("addBtn"), clearBtn = $("clearBtn");
const pills = $("selPills"), hint = $("selHint"), shareBtn = $("shareBtn"), copiedTag = $("copied"), roomTag = $("roomTag");
const tblC = $("tblCarry"), theadC = tblC.querySelector("thead"), tbodyC = tblC.querySelector("tbody"), countC = $("countCarry");
const tblB = $("tblBoth"),  theadB = tblB.querySelector("thead"), tbodyB = tblB.querySelector("tbody"), countB = $("countBoth");
const tblS = $("tblSupport"), theadS = tblS.querySelector("thead"), tbodyS = tblS.querySelector("tbody"), countS = $("countSupport");
const tblP = $("tblPairs"), theadP = tblP.querySelector("thead"), tbodyP = tblP.querySelector("tbody"), countP = $("countPairs");

// Clean old local storage (state sync is realtime)
try { localStorage.removeItem("ad_hidden_abilities"); } catch(e) {}
const hidden = new Set();
function hideAbility(name){ hidden.add(canon(name)); render(); }
function unhideAll(){ hidden.clear(); render(); }
$("restoreBtn").onclick = unhideAll;

// Canonicalize
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

// Ability owners for current selection
let abilityOwners = new Map();

// Autocomplete
let ddItems=[], ddIndex=-1;
function filterHeroes(q){ q=q.trim().toLowerCase(); if(!q) return HEROES.slice(0,50); return HEROES.filter(h=>h.toLowerCase().startsWith(q)).slice(0,50); }
function renderDD(){ dd.innerHTML = ddItems.map((h,i)=>`<div class="opt${i===ddIndex?' active':''}" data-v="${escapeAttr(h)}">${escapeHtml(h)}</div>`).join(""); dd.style.display = ddItems.length?"block":"none"; }
function openDD(items){ ddItems = items||[]; if(!ddItems.length) ddIndex=-1; else if(ddIndex<0) ddIndex=0; else if(ddIndex>=ddItems.length) ddIndex=ddItems.length-1; renderDD(); }
function closeDD(){ dd.style.display="none"; ddItems=[]; ddIndex=-1; }
dd.addEventListener("mousedown",(e)=>{ const opt=e.target.closest(".opt"); if(!opt) return; heroInput.value=opt.dataset.v; addBtn.click(); closeDD(); });
dd.addEventListener("mousemove",(e)=>{ const opt=e.target.closest(".opt"); if(!opt) return; const idx=Array.prototype.indexOf.call(dd.children,opt); if(idx>=0 && idx!==ddIndex){ ddIndex=idx; renderDD(); }});
heroInput.addEventListener("input",()=>openDD(filterHeroes(heroInput.value)));
heroInput.addEventListener("keydown",(e)=>{
  if(dd.style.display==="block"){
    if(e.key==="ArrowDown"){ e.preventDefault(); if(ddItems.length){ ddIndex=Math.min(ddIndex+1,ddItems.length-1); renderDD(); } return; }
    if(e.key==="ArrowUp"){ e.preventDefault(); if(ddItems.length){ ddIndex=Math.max(ddIndex-1,0); renderDD(); } return; }
    if(e.key==="Enter"){ e.preventDefault(); if(ddIndex>=0){ heroInput.value=ddItems[ddIndex]; addBtn.click(); closeDD(); } return; }
    if(e.key==="Escape"){ closeDD(); return; }
  }
  if(e.key==="Enter" && dd.style.display!=="block") addBtn.click();
});
document.addEventListener("click",(e)=>{ if(!e.target.closest(".control")) closeDD(); });

// Selection
const sel = new Set();
addBtn.onclick = ()=>{ const name=heroInput.value.trim(); if(!name) return; if(!DATA[name]){ alert("Unknown hero."); return; } if(sel.has(name)){ heroInput.value=""; return; } if(sel.size>=MAX){ alert("You already picked 12 heroes."); return; } sel.add(name); heroInput.value=""; closeDD(); render(); };
clearBtn.onclick = ()=>{ sel.clear(); render(); };

// Collect
function collectAbilities(){
  const map = new Map();
  for(const h of sel){
    const H=DATA[h], hsModel=HS[h]||null;
    map.set("MODEL::"+h, {
      kind:"model",
      ability:"Model — "+h,
      from:[h],
      pick: (hsModel && typeof hsModel.pick_num==="number") ? hsModel.pick_num : null,
      win:  (typeof H.body_winrate==="number") ? H.body_winrate : (hsModel && typeof hsModel.win_pct==="number" ? hsModel.win_pct : null),
      img: H.hero_img || null,
      role:null
    });
    for(const a of (H.abilities||[])){
      const key=a.name;
      if(!map.has(key)) map.set(key,{kind:"ability",ability:a.name,from:[],pick:null,win:null,img:a.img||null,role:null});
      const row=map.get(key);
      row.from.push(h);
      if(typeof a.win_pct==="number") row.win = (row.win==null)? a.win_pct : Math.max(row.win,a.win_pct);
      const hs = HS[a.name];
      if(hs && typeof hs.pick_num==="number") row.pick = hs.pick_num;
      else if(typeof a.pick_num==="number") row.pick = a.pick_num;
      const r = ROLES[a.name];
      row.role = (r==="carry"||r==="support"||r==="both") ? r : row.role;
    }
  }
  return [...map.values()];
}

// Pairs
function collectPairs(selectedAbilityNames){
  if(!PAIRS || !Array.isArray(PAIRS)) return [];
  const selectedHeroes = new Set([...sel].map(canon));
  const selectedAbilities = new Set(selectedAbilityNames.map(canon));
  const rows = [];
  for(const p of PAIRS){
    const a1raw=p.a1, a2raw=p.a2; if(!a1raw||!a2raw) continue;
    const a1n=canon(a1raw), a2n=canon(a2raw); if(a1n===a2n) continue;
    const o1=abilityOwners.get(a1n), o2=abilityOwners.get(a2n);
    const a1IsAbility=!!o1, a2IsAbility=!!o2;
    const a1IsHero=selectedHeroes.has(a1n), a2IsHero=selectedHeroes.has(a2n);
    let ok=false;
    if(a1IsAbility && a2IsAbility){
      if(selectedAbilities.has(a1n) && selectedAbilities.has(a2n)){
        outer: for(const h1 of (o1||[])){ if(!selectedHeroes.has(h1)) continue;
          for(const h2 of (o2||[])){ if(!selectedHeroes.has(h2)) continue;
            if(h1!==h2){ ok=true; break outer; } } }
      }
    } else if(a1IsHero && a2IsAbility){
      if(selectedAbilities.has(a2n)){ for(const h2 of (o2||[])){ if(!selectedHeroes.has(h2)) continue; if(h2!==a1n){ ok=true; break; } } }
    } else if(a2IsHero && a1IsAbility){
      if(selectedAbilities.has(a1n)){ for(const h1 of (o1||[])){ if(!selectedHeroes.has(h1)) continue; if(h1!==a2n){ ok=true; break; } } }
    }
    if(!ok) continue;
    rows.push({ a1:a1raw, a2:a2raw, a1_img:p.a1_img||null, a2_img:p.a2_img||null, syn: (typeof p.synergy==="number")?p.synergy:null });
  }
  return rows;
}

// Sorting
function makeSortState(k,d){ return {key:k, dir:d}; }
const sortC = makeSortState("good","desc");
const sortB = makeSortState("good","desc");
const sortS = makeSortState("good","desc");
let sortPKey="syn", sortPDir="desc";
function bindSort(thead, state, renderFn){
  thead.addEventListener("click",(e)=>{
    const th=e.target.closest("th"); if(!th) return;
    const k=th.dataset.key; if(!k) return;
    if(state.key===k) state.dir=(state.dir==="asc")?"desc":"asc";
    else { state.key=k; state.dir=(k==="ability")?"asc":"desc"; }
    thead.querySelectorAll("th").forEach(el=>el.classList.remove("sort-asc","sort-desc"));
    th.classList.add(state.dir==="asc"?"sort-asc":"sort-desc");
    renderFn();
  });
}
bindSort(theadC, sortC, renderTables);
bindSort(theadB, sortB, renderTables);
bindSort(theadS, sortS, renderTables);
theadP.addEventListener("click",(e)=>{
  const th=e.target.closest("th"); if(!th) return;
  const k=th.dataset.key; if(!k) return;
  if(sortPKey===k) sortPDir=(sortPDir==="asc")?"desc":"asc";
  else { sortPKey=k; sortPDir=(k==="a1"||k==="a2")?"asc":"desc"; }
  theadP.querySelectorAll("th").forEach(el=>el.classList.remove("sort-asc","sort-desc"));
  th.classList.add(sortPDir==="asc"?"sort-asc":"sort-desc");
  renderPairs();
});

// -------- Realtime (Supabase): versioning + cold-join sync --------
const SUPA_URL = "https://subxkjymwzzroctziiro.supabase.co";
const SUPA_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN1Ynhranltd3p6cm9jdHppaXJvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjE0ODk1NTYsImV4cCI6MjA3NzA2NTU1Nn0.xhubkk6Gsx8N7btGH8vCj3B8-AGNaQCoqBZkB0PZ1zo";

// room id in #r=...
function getHashParam(key){
  const h=location.hash.replace(/^#/,""); if(!h) return null;
  const map=new Map(h.split("&").filter(Boolean).map(kv=>{ const i=kv.indexOf("="); return i<0?[kv,""]:[kv.slice(0,i),kv.slice(i+1)]; }));
  return map.get(key)||null;
}
function setHashParam(key,value){
  const h=location.hash.replace(/^#/,""); const pairs=h? h.split("&").filter(Boolean):[];
  const map=new Map(pairs.map(kv=>{ const i=kv.indexOf("="); return i<0?[kv,""]:[kv.slice(0,i),kv.slice(i+1)]; }));
  if(value==null) map.delete(key); else map.set(key,String(value));
  const newHash="#"+[...map.entries()].map(([k,v])=>`${k}=${v}`).join("&");
  history.replaceState(null,"",location.pathname+location.search+newHash);
}
function randomRoomId(n=8){ let s=""; while(s.length<n) s+=Math.random().toString(36).slice(2); return s.slice(0,n); }
let ROOM_ID = getHashParam("r"); if(!ROOM_ID){ ROOM_ID=randomRoomId(); setHashParam("r",ROOM_ID); }
roomTag.textContent = "Room: "+ROOM_ID;

// identity + revisioning + cold-join flags
const CLIENT_ID = Math.random().toString(36).slice(2,10);
let localRev=0, lastAppliedRev=0;
let isApplyingRemote=false;
let isReady=false, gotRemoteState=false;
let isSyncing=true; const JOIN_TIMEOUT_MS=800; const SYNC_NONCE=Math.random().toString(36).slice(2,10);

let supa=null, channel=null;
function debounce(fn,ms){ let t; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn(...a),ms); }; }

function currentState(){
  return {
    v:1,
    sel:[...sel],
    hidden:[...hidden],
    sort:{ C:{key:sortC.key,dir:sortC.dir}, B:{key:sortB.key,dir:sortB.dir}, S:{key:sortS.key,dir:sortS.dir}, P:{key:sortPKey,dir:sortPDir} }
  };
}
function applyState(st){
  if(!st || st.v!==1) return;
  sel.clear(); (st.sel||[]).forEach(h=>{ if(DATA[h]) sel.add(h); });
  hidden.clear(); (st.hidden||[]).forEach(a=>hidden.add(canon(a)));
  if(st.sort?.C){ sortC.key=st.sort.C.key; sortC.dir=st.sort.C.dir; }
  if(st.sort?.B){ sortB.key=st.sort.B.key; sortB.dir=st.sort.B.dir; }
  if(st.sort?.S){ sortS.key=st.sort.S.key; sortS.dir=st.sort.S.dir; }
  if(st.sort?.P){ sortPKey=st.sort.P.key; sortPDir=st.sort.P.dir; }
}

const broadcastDebounced = debounce(async ()=>{
  if(!isReady || !channel || isApplyingRemote || isSyncing) return;
  const state=currentState();
  try{
    await channel.send({ type:"broadcast", event:"state", payload:{ source:CLIENT_ID, rev:localRev, state } });
  }catch{}
},150);

async function initRealtime(){
  const supabaseClient = window.supabase; // from CDN
  supa = supabaseClient.createClient(SUPA_URL, SUPA_KEY);
  channel = supa.channel("ad_helper_"+ROOM_ID, { config:{ broadcast:{ ack:true } } });

  // respond to joiners
  channel.on("broadcast", {event:"request_state"}, (msg)=>{
    const {source,nonce} = msg?.payload||{};
    if(!source || source===CLIENT_ID) return;
    channel.send({ type:"broadcast", event:"state", payload:{ source:CLIENT_ID, rev:localRev, state:currentState(), reply_to:nonce } });
  });

  // apply inbound states (newest only)
  channel.on("broadcast", {event:"state"}, (msg)=>{
    const { source, rev, state } = msg?.payload||{};
    if(!state) return;
    if(source===CLIENT_ID) return;
    if(typeof rev==="number" && rev<=lastAppliedRev) return;
    lastAppliedRev = (typeof rev==="number") ? rev : lastAppliedRev;
    gotRemoteState = true;
    isApplyingRemote=true;
    applyState(state);
    render();              // guarded; won't rebroadcast
    isApplyingRemote=false;
  });

  await channel.subscribe((status)=>{
    if(status==="SUBSCRIBED"){
      isReady=true;
      // ask for state
      channel.send({ type:"broadcast", event:"request_state", payload:{ source:CLIENT_ID, nonce:SYNC_NONCE } });
      // seed if nobody answers
      setTimeout(()=>{
        if(!gotRemoteState){
          isSyncing=false;
          broadcastDebounced();
        }else{
          isSyncing=false;
        }
      }, JOIN_TIMEOUT_MS);
    }
  });
}

// Share room link
shareBtn.onclick = async ()=>{
  try{ await navigator.clipboard.writeText(location.href); copiedTag.style.display="inline"; setTimeout(()=>copiedTag.style.display="none",1200); }
  catch{ alert("Link copied:\\n"+location.href); }
};

// Render
function render(){
  if(!isApplyingRemote) localRev++;       // bump only on local change
  // pills
  pills.innerHTML="";
  [...sel].sort((a,b)=>a.localeCompare(b)).forEach(h=>{
    const el=document.createElement("div"); el.className="pill";
    el.innerHTML = `<b>${escapeHtml(h)}</b> <button title="Remove" aria-label="Remove" onclick="removeHero('${escapeAttr(h)}')">✕</button>`;
    pills.appendChild(el);
  });
  hint.textContent = `${sel.size} / ${MAX} selected`;
  renderTables();
  renderPairs();
  if(!isApplyingRemote && !isSyncing) broadcastDebounced();
}
window.removeHero=(h)=>{ sel.delete(h); render(); };

// Click on overlay delete
[tbodyC, tbodyB, tbodyS].forEach(tb=>{
  tb.addEventListener("click",(e)=>{
    const btn=e.target.closest(".delBtn"); if(!btn) return;
    const ability=btn.dataset.ability; if(ability) hideAbility(ability);
  });
});

let cachedAbilities=[];
function renderTables(){
  const rows=collectAbilities();
  cachedAbilities=rows;

  abilityOwners=new Map();
  for(const r of rows){
    if(r.kind==="ability"){
      const aKey=canon(r.ability);
      const owners=new Set();
      for(const h of (r.from||[])) owners.add(canon(h));
      abilityOwners.set(aKey, owners);
    }
  }

  const all=[], carry=[], both=[], support=[];
  for(const r of rows){
    if(r.kind!=="ability") continue;
    if(hidden.has(canon(r.ability))) continue;
    all.push(r);
    if(r.role==="carry") carry.push(r);
    else if(r.role==="both") both.push(r);
    else if(r.role==="support") support.push(r);
  }

  function rawScore(row){ const p=row.pick,w=row.win; if(typeof p!=="number"||typeof w!=="number") return null; return p*(100-w); }
  const scores=all.map(rawScore).filter(v=>typeof v==="number" && isFinite(v));
  const rmin=Math.min(...scores), rmax=Math.max(...scores);
  function scaled(row){
    const r=rawScore(row); if(r==null||!isFinite(r)) return null; if(!scores.length) return null; if(rmax===rmin) return 10;
    const t = 1 + 9*(rmax - r)/(rmax - rmin);
    return Math.max(1, Math.min(10, t));
  }
  for(const r of all) r.good=scaled(r);

  const cmp=(state)=>(a,b)=>{
    const key=state.key, dir=state.dir;
    let av=a[key], bv=b[key];
    if(key==="ability"){ av=String(av||""); bv=String(bv||""); return dir==="asc"? av.localeCompare(bv) : bv.localeCompare(av); }
    const an=(typeof av==="number"&&isFinite(av))?av:(dir==="asc"?Infinity:-Infinity);
    const bn=(typeof bv==="number"&&isFinite(bv))?bv:(dir==="asc"?Infinity:-Infinity);
    const d=an-bn; return dir==="asc"? d : -d;
  };

  carry.sort(cmp(sortC)); both.sort(cmp(sortB)); support.sort(cmp(sortS));
  tbodyC.innerHTML = carry.map(rowAbilityHtml).join("");
  tbodyB.innerHTML = both.map(rowAbilityHtml).join("");
  tbodyS.innerHTML = support.map(rowAbilityHtml).join("");

  countC.textContent = `${carry.length} rows`;
  countB.textContent = `${both.length} rows`;
  countS.textContent = `${support.length} rows`;

  [[theadC,sortC],[theadB,sortB],[theadS,sortS]].forEach(([th,st])=>{
    th.querySelectorAll("th").forEach(el=>el.classList.remove("sort-asc","sort-desc"));
    const el = th.querySelector(`th[data-key="${st.key}"]`);
    if(el) el.classList.add(st.dir==="asc"?"sort-asc":"sort-desc");
  });
}

function renderPairs(){
  const selectedNames=cachedAbilities.filter(r=>r.kind==="ability").map(r=>r.ability);
  const rows=collectPairs(selectedNames);
  const cmp=(a,b)=>{
    if(sortPKey==="a1"||sortPKey==="a2"){
      const av=String(a[sortPKey]||""), bv=String(b[sortPKey]||"");
      return sortPDir==="asc"? av.localeCompare(bv) : bv.localeCompare(av);
    }
    const na=(typeof a.syn==="number")?a.syn:-Infinity;
    const nb=(typeof b.syn==="number")?b.syn:-Infinity;
    const d=na-nb; return sortPDir==="asc"? d : -d;
  };
  rows.sort(cmp);
  tbodyP.innerHTML = rows.map(rowPairHtml).join("");
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
  const img=(src)=> src? `<img class="img" src="${escapeAttr(src)}" alt=""> `:"";
  return `<tr>
    <td>${img(r.a1_img)}<b>${escapeHtml(r.a1)}</b></td>
    <td>${img(r.a2_img)}<b>${escapeHtml(r.a2)}</b></td>
    <td class="k">${fmtNum(r.syn)}</td>
  </tr>`;
}
function fmtNum(v){ return (typeof v==="number" && isFinite(v)) ? v.toFixed(2) : "<span class='muted'>—</span>"; }
function fmtPct(v){ return (typeof v==="number" && isFinite(v)) ? v.toFixed(2)+"%" : "<span class='muted'>—</span>"; }
function escapeHtml(s){ return String(s).replace(/[&<>\"']/g, m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":"&#39;"}[m])); }
function escapeAttr(s){ return String(s).replace(/["']/g, m => (m=='"'?'&quot;':'&#39;')); }

// Boot
render();
initRealtime();
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

