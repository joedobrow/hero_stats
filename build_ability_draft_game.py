#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path

# ---- fixed paths ----
CANDIDATE_PATHS = [
    Path("~/dotaApi/cache/ability_high_skill.json").expanduser(),
    Path("~/cache/ability_high_skill.json").expanduser(),
    (Path(__file__).resolve().parent / "cache" / "ability_high_skill.json"),
]
def locate_src() -> Path:
    for p in CANDIDATE_PATHS:
        if p.exists():
            return p
    raise FileNotFoundError("ability_high_skill.json not found:\n" + "\n".join(str(p) for p in CANDIDATE_PATHS))

SRC_PATH = locate_src()
OUT_FILE = Path("/Users/joedobrow/dotaApi/ability_draft_table.html")

# ---- data ----
def load_hero_data():
    with open(SRC_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    data = raw.get("data", {})
    heroes = {}
    for k, v in data.items():
        if isinstance(v, dict) and isinstance(v.get("abilities"), list):
            heroes[k] = {
                "name": k,
                "hero_img": v.get("hero_img"),
                "abilities": [
                    {"ability_name": a.get("ability_name"), "img": a.get("img")}
                    for a in v.get("abilities", [])
                    if a and a.get("ability_name")
                ],  # keep all; JS trims/pads to 4
            }
    return heroes

# ---- html ----
def build_html(all_heroes):
    data_json = json.dumps(all_heroes, ensure_ascii=False).replace("</", "<\\/")

    css = r"""
    :root{
      /* sizing (~40% larger) */
      --tile: 56px;
      --gap: 8px;
      --rad: 8px;

      --bg:#0b0e12; --surface:#10141a; --line:#232a35; --hl:#4f7df4;

      --p-inner-gap: 4px;
      --p-width: calc(5*var(--tile) + 4*var(--p-inner-gap));
      --row-pad: 6px;

      /* total width: [P] [H] [4A] [4A] [H] [P] + gaps + padding */
      --W: calc(
         var(--p-width) + var(--tile) + 4*var(--tile) + 4*var(--tile) + var(--tile) + var(--p-width)
         + 12*var(--gap) + 2*var(--row-pad)
      );

      /* total height for 6 rows (5 player rows + 1 bench), gaps and padding */
      --H: calc( 6*(var(--tile) + 2*var(--row-pad)) + 5*var(--gap) );
    }
    *{box-sizing:border-box}
    html,body{height:100%}
    body{
      margin:0; background:var(--bg); color:#e5e7eb;
      font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial;
      overflow:hidden; /* fixed canvas */
    }

    .outer{
      display:flex; flex-direction:column; align-items:center;
      padding-block: 18px; gap: 12px;
    }
    .title{
      font-weight:800; letter-spacing:.3px; font-size:18px;
      color:#dbe3ee; text-transform:uppercase;
    }

    .controls{display:flex; gap:10px; align-items:center}
    .btn{
      border:1px solid var(--line); background:#0f1319; color:#e5e7eb;
      border-radius:10px; padding:8px 12px; cursor:pointer; font-weight:700; font-size:13px;
    }
    .btn:active{transform:translateY(1px)}

    .wrap{
      width: var(--W);
      height: var(--H);
      display: grid;
      grid-template-rows: repeat(6, 1fr); /* 5 player rows + 1 bench row */
      gap: var(--gap);
    }

    .row, .bench-row{
      display: grid; align-items: center; gap: var(--gap);
      grid-template-columns:
        var(--p-width)         /* Player/empty */
        var(--tile)            /* Hero A */
        repeat(4, var(--tile)) /* Abil A */
        repeat(4, var(--tile)) /* Abil B */
        var(--tile)            /* Hero B */
        var(--p-width);        /* Player/empty */
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: var(--row-pad);
    }

    .cellP, .cellH, .cellA{
      display:flex; align-items:center; justify-content:center;
      background:#0e1218; border:1px solid var(--line); border-radius: var(--rad);
      height: var(--tile); overflow:hidden; position:relative;
    }
    .cellP{ width: var(--p-width); border-radius:10px; }
    .cellP.empty{ background: transparent; border-color: transparent; }
    .cellH, .cellA{ width: var(--tile); }

    /* player strip: [model][A][A][A][A] */
    .p-strip{
      display: grid;
      grid-template-columns: repeat(5, var(--tile));
      grid-auto-rows: var(--tile);
      gap: var(--p-inner-gap);
      width: 100%; height: 100%;
    }
    .p-slot{
      width: var(--tile); height: var(--tile);
      border:1px solid var(--line); border-radius: 6px;
      background:#0a0d12; overflow:hidden;
    }

    .tile{ width:100%; height:100%; object-fit:cover; display:block; }
    .pickbtn{ all:unset; cursor:pointer; display:block; width:100%; height:100%; }
    .pickbtn:focus-visible{ outline:2px solid var(--hl); }
    .disabled{ opacity:.4; filter:grayscale(1); pointer-events:none; }
    .current{ outline:2px dashed var(--hl); outline-offset:2px; }
    """

    js = r"""
    const ALL_HEROES = JSON.parse(document.getElementById('all-heroes-json').textContent);
    const SEATS = 10;

    // state
    let snakeForward = true;
    let turnIndex = 0; // 0..SEATS-1
    let players = [];  // [{seat, modelImg:null|string, abilities:[img,...] max 4}]
    let pickedModels = new Set();     // heroName
    let pickedAbilities = new Set();  // `${abilityName}__${sourceHeroName}`
    let selected = [];                // 12 heroes
    let boardHeroes = [];             // 12 heroes with exactly 4 tiles each (padded if needed)

    function rngShuffle(a){
      for (let i=a.length-1;i>0;i--){ const j=Math.floor(Math.random()*(i+1)); [a[i],a[j]]=[a[j],a[i]]; }
      return a;
    }
    function rngSample(arr, k){ return rngShuffle([...arr]).slice(0, k); }

    function buildPlayers(){
      players = Array.from({length: SEATS}, (_, i)=>({
        seat: i+1,
        modelImg: null,
        abilities: []
      }));
    }
    function seatIdx(){ return snakeForward ? turnIndex : (SEATS-1-turnIndex); }
    function curPlayer(){ return players[seatIdx()]; }
    function advanceTurn(){
      if (turnIndex < SEATS-1) turnIndex++;
      else { turnIndex = 0; snakeForward = !snakeForward; }
      highlight();
    }

    function abilityKey(aName, srcHero){ return `${aName}__${srcHero}`; }

    // Pad ALL 12 heroes to 4 tiles each using abilities from outside the selected pool
    function padAllSelected(){
      const names = new Set(selected.map(h => h.name));
      const outside = [];
      for (const [name, hero] of Object.entries(ALL_HEROES)){
        if (names.has(name)) continue;
        for (const a of (hero.abilities||[])){
          if (!a || !a.ability_name) continue;
          outside.push({ ability_name:a.ability_name, img:a.img||"", srcHero:hero.name, borrowed:true });
        }
      }
      rngShuffle(outside);

      boardHeroes = selected.map(h => {
        const tiles = [];
        for (const a of (h.abilities||[]).slice(0,4)){
          tiles.push({ ability_name:a.ability_name, img:a.img||"", srcHero:h.name, borrowed:false });
        }
        while (tiles.length < 4 && outside.length){
          tiles.push(outside.pop());
        }
        return { name:h.name, hero_img:h.hero_img||"", tiles };
      });
    }

    // cells
    function cellP(p, isCurrent){
      const slots = [];
      slots.push(`<div class="p-slot">${p.modelImg ? `<img class="tile" src="${p.modelImg}">` : ""}</div>`);
      for (let i=0;i<4;i++){
        const img = p.abilities[i] || "";
        slots.push(`<div class="p-slot">${img ? `<img class="tile" src="${img}">` : ""}</div>`);
      }
      return `<div class="cellP ${isCurrent?'current':''}" data-seat="${p.seat}">
                <div class="p-strip">${slots.join("")}</div>
              </div>`;
    }
    function cellPEmpty(){
      return `<div class="cellP empty" aria-hidden="true"></div>`;
    }
    function cellH(heroName){
      const h = selected.find(x => x.name === heroName);
      const disabled = pickedModels.has(heroName) ? "disabled" : "";
      const img = h && h.hero_img ? `<img class="tile" src="${h.hero_img}">` : "";
      return `<div class="cellH ${disabled}">
                <button class="pickbtn" data-model="${heroName}">${img}</button>
              </div>`;
    }
    function cellA(tile){
      const key = abilityKey(tile.ability_name, tile.srcHero);
      const disabled = pickedAbilities.has(key) ? "disabled" : "";
      const img = tile.img ? `<img class="tile" src="${tile.img}">` : "";
      return `<div class="cellA ${disabled}">
                <button class="pickbtn" data-ability="${key}" data-img="${tile.img||""}">${img}</button>
              </div>`;
    }

    function render(){
      const root = document.getElementById("wrap");
      const rows = [];

      // first 10 heroes across 5 rows with players
      for (let r=0;r<5;r++){
        const pL = players[2*r];
        const pR = players[2*r+1];
        const hA = boardHeroes[2*r];
        const hB = boardHeroes[2*r+1];
        const curSeat = (snakeForward ? turnIndex : (SEATS-1-turnIndex)) + 1;

        rows.push(`
          <div class="row">
            ${cellP(pL, pL.seat === curSeat)}
            ${cellH(hA.name)}
            ${hA.tiles.map(cellA).join("")}
            ${hB.tiles.map(cellA).join("")}
            ${cellH(hB.name)}
            ${cellP(pR, pR.seat === curSeat)}
          </div>
        `);
      }

      // 6th row: bench for the last 2 heroes (indices 10 & 11) with empty player cells
      const h10 = boardHeroes[10];
      const h11 = boardHeroes[11];
      rows.push(`
        <div class="bench-row">
          ${cellPEmpty()}
          ${cellH(h10.name)}
          ${h10.tiles.map(cellA).join("")}
          ${h11.tiles.map(cellA).join("")}
          ${cellH(h11.name)}
          ${cellPEmpty()}
        </div>
      `);

      root.innerHTML = rows.join("");
      highlight();
    }

    function highlight(){
      document.querySelectorAll(".cellP").forEach(el=>el.classList.remove("current"));
      const curSeat = (snakeForward ? turnIndex : (SEATS-1-turnIndex)) + 1;
      const cur = document.querySelector(`.cellP[data-seat="${curSeat}"]`);
      if (cur) cur.classList.add("current");
    }

    function wire(){
      document.body.addEventListener("click", (e)=>{
        const m = e.target.closest("[data-model]");
        const a = e.target.closest("[data-ability]");
        if (!m && !a) return;

        if (m){
          const name = m.getAttribute("data-model");
          if (pickedModels.has(name)) return;

          const p = curPlayer();
          if (p.modelImg) return; // one model per player

          const h = selected.find(x => x.name === name);
          const img = h && h.hero_img ? h.hero_img : "";
          p.modelImg = img;
          pickedModels.add(name);

          render();
          advanceTurn();
          return;
        }

        if (a){
          const key = a.getAttribute("data-ability");
          if (pickedAbilities.has(key)) return;

          const p = curPlayer();
          if (p.abilities.length >= 4) return;

          const img = a.getAttribute("data-img") || "";
          p.abilities.push(img);
          pickedAbilities.add(key);

          render();
          advanceTurn();
        }
      });

      document.getElementById("reroll").addEventListener("click", ()=>init(true));
    }

    function init(reroll=false){
      // choose 12 heroes
      const names = Object.keys(ALL_HEROES);
      selected = rngSample(names, 12).map(n=>ALL_HEROES[n]);

      // reset state
      buildPlayers();
      pickedModels.clear();
      pickedAbilities.clear();
      snakeForward = true;
      turnIndex = 0;

      // pad all 12 heroes to 4 tiles each
      padAllSelected();

      render();
    }

    document.addEventListener("DOMContentLoaded", ()=>{
      wire();
      init(false);
    });
    """

    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Ability Draft – Table</title>
<style>__CSS__</style>
</head>
<body>
  <div class="outer">
    <div class="title">Ability Draft</div>
    <div class="controls">
      <button id="reroll" class="btn">Pick new heroes</button>
    </div>
    <div class="wrap" id="wrap"></div>
  </div>
  <script id="all-heroes-json" type="application/json">__DATA__</script>
  <script>__JS__</script>
</body>
</html>
"""
    html = (html_template
        .replace("__CSS__", css)
        .replace("__DATA__", data_json)
        .replace("__JS__", js))


    return html

def main():
    heroes = load_hero_data()
    html_text = build_html(heroes)
    OUT_FILE.write_text(html_text, encoding="utf-8")
    print(f"Using data file: {SRC_PATH}")
    print(f"Wrote {OUT_FILE}")

if __name__ == "__main__":
    main()

