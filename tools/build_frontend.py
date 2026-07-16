"""
Wahlkompass frontend build (v1 — mobile core flow).

Reads a data-release directory and emits a single self-contained
frontend/dist/index.html with the signed bundle INLINED and the client-side
v1.2 scorer embedded (a byte-for-byte JS port of pipeline/src/scoring.py).

PREVIEW NOTE: for the standalone preview the bundle is inlined so the page runs
from file://. For the deployed site, replace the `RELEASE` const with a
`fetch()` of the signed bundle from the CDN + in-browser Ed25519 verification
(see GO-LIVE — the signature, payload and pubkey are already emitted).
"""
import os
import json

REL = os.path.join(os.path.dirname(__file__), "..", "data-releases", "2026.11.0-preview")
OUT = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")


def load(name):
    with open(os.path.join(REL, name), "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    bundle = {k: load(f"{k}.json") for k in ["meta", "statements", "parties", "positions", "evidence"]}
    os.makedirs(OUT, exist_ok=True)
    html = TEMPLATE.replace("/*__RELEASE__*/null", json.dumps(bundle, ensure_ascii=False))
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"frontend built: {os.path.join(OUT, 'index.html')} ({len(html)//1024} KB)")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Wahlkompass — belegbasierter Wahlkompass</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=Public+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --paper:#FAFAF7; --ink:#1A1C1E; --graphite:#5A5F63; --petrol:#0F6B6E; --petrol-d:#0a4d4f;
  --signal:#B4541E; --seal:#2E7D4F; --line:#e3e0d7; --card:#fff; --soft:#f2f0ea;
}
*{box-sizing:border-box}
body{margin:0;background:#e9e7e1;color:var(--ink);font-family:"Public Sans",system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.app{max-width:460px;margin:0 auto;min-height:100vh;background:var(--paper);display:flex;flex-direction:column;position:relative;box-shadow:0 0 40px rgba(0,0,0,.06)}
.mono{font-family:"JetBrains Mono",monospace}
button{font-family:inherit}
.pad{padding:24px 22px}
.preview-banner{background:#2A211C;color:#E7DECF;font:500 11px/1.4 "JetBrains Mono",monospace;padding:8px 22px;display:flex;gap:8px;align-items:center}
.preview-banner b{color:#E9982E}
.eyebrow{font:500 11px/1 "JetBrains Mono",monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--graphite)}
.h1{font:700 30px/1.15 "Archivo",sans-serif;letter-spacing:-.01em;margin:0}
.h2{font:700 21px/1.15 "Archivo",sans-serif;margin:0}
.sub{color:var(--graphite);font-size:14px;line-height:1.5}
.seal{display:inline-flex;align-items:center;gap:7px;font:500 12px "JetBrains Mono",monospace;color:var(--seal)}
.seal .ring{width:18px;height:18px;border-radius:50%;border:2px solid var(--petrol);display:inline-flex;align-items:center;justify-content:center}
.seal .ring i{width:7px;height:4px;border-left:2px solid var(--seal);border-bottom:2px solid var(--seal);transform:rotate(-45deg);margin-top:-2px}
.btn{all:unset;display:block;text-align:center;padding:15px;border-radius:12px;font:600 15px "Public Sans";cursor:pointer}
.btn.primary{background:var(--petrol);color:#fff}
.btn.ghost{border:1px solid #bfd6d6;color:var(--petrol)}
.card{border:1px solid var(--line);border-radius:14px;background:var(--card)}
.spacer{flex:1}
.footer{border-top:1px solid var(--line);padding:12px 22px;font:400 11px "Public Sans";color:var(--graphite);display:flex;gap:8px;align-items:center;justify-content:space-between}
.link{color:var(--petrol);font-weight:600;cursor:pointer;text-decoration:none}
/* progress */
.prog{height:3px;background:var(--line);border-radius:2px;overflow:hidden}
.prog>i{display:block;height:100%;background:var(--petrol);transition:width .2s}
/* scale */
.scale{display:flex;gap:8px}
.scale button{all:unset;flex:1;height:46px;border:1px solid #cfccc4;background:#fff;border-radius:10px;display:flex;align-items:center;justify-content:center;cursor:pointer;transition:.12s}
.scale button.on{border:2px solid var(--petrol);background:var(--petrol)}
.scale button .dot{border-radius:50%;background:var(--graphite)}
.scale button.on .dot{background:#fff}
.scale-lab{display:flex;justify-content:space-between;margin-top:7px;font:400 9.5px "Public Sans";color:var(--graphite)}
.chip{display:inline-flex;align-items:center;gap:6px;font:600 13px "Public Sans"}
.chip .sw{width:14px;height:14px;border-radius:4px;border:1px solid rgba(0,0,0,.15);flex:none}
.bar{position:relative;height:16px;display:flex;align-items:center}
.bar .track{position:absolute;left:0;right:0;height:8px;border-radius:4px;background:#e8e5dc}
.bar .fill{position:absolute;left:0;height:8px;border-radius:4px;background:var(--petrol)}
.bar .whisk{position:absolute;height:16px;border-left:1.5px solid var(--graphite);border-right:1.5px solid var(--graphite)}
.bar .whisk::after{content:"";position:absolute;left:0;right:0;top:50%;height:1.5px;background:var(--graphite)}
.tiebracket{border-left:1.5px solid #c9b8a0;border-radius:5px 0 0 5px;margin-left:6px;padding-left:12px}
.tier{font:600 10px "JetBrains Mono";padding:3px 7px;border-radius:3px;display:inline-block}
.tier.t1{border:1.5px solid var(--ink);color:var(--ink)}
.tier.t2{border:1.5px solid var(--graphite);border-radius:9px;color:var(--graphite)}
.tier.t3{border:1.5px solid #9aa;color:#889}
.kbp{color:#9A8E7F;font:500 12px "JetBrains Mono"}
.divdot{width:7px;height:7px;border-radius:50%;background:var(--signal);flex:none;display:inline-block}
.evcard{border:1px solid var(--line);border-radius:10px;padding:11px 12px;background:#fff;margin-top:8px}
.extract{margin-top:8px;padding:8px 10px;background:var(--soft);border-radius:7px;font:400 11.5px/1.45 "JetBrains Mono";color:var(--ink)}
.tag{padding:3px 8px;border-radius:7px;background:var(--soft);font:500 11px "JetBrains Mono";color:var(--graphite)}
.warn{border:1px solid #e6c9a8;background:#fbf3e6;border-radius:12px;padding:12px 14px;font-size:13px;color:#7a5a2a}
</style>
</head>
<body>
<div class="app" id="app"></div>
<script>
const RELEASE = /*__RELEASE__*/null;
const {meta, statements, parties, positions, evidence} = RELEASE;
const posOf = (pid,slug)=> positions[pid+":"+slug] || {p:null};
const MIN_ANSWERS = 10;

// ---- storage (safe: falls back to memory if localStorage unavailable) ----
const store = (()=>{ try{const k="wk";localStorage.setItem(k,localStorage.getItem(k)||"{}");
  return {get:()=>JSON.parse(localStorage.getItem(k)||"{}"),set:v=>localStorage.setItem(k,JSON.stringify(v))};}
  catch(e){let m={};return {get:()=>m,set:v=>m=v};}})();

// ---- state ----
let S = Object.assign({screen:"start", i:0, answers:{}, easy:false, openParty:null, openBeleg:{}}, store.get());
function save(){ store.set({answers:S.answers, easy:S.easy}); }

// ---- v1.2 scorer (port of pipeline/src/scoring.py) ----
function matchScore(answers, pid){
  let num=0,den=0,rss=0,lin=0,n=0;
  for(const slug in answers){
    const pos=posOf(pid,slug); if(pos.p==null) continue;
    const {u,w}=answers[slug]; const c=pos.confidence==null?0:pos.confidence; const r=1-c;
    num+=w*Math.abs(u-pos.p); den+=w; rss+=(w*r)**2; lin+=w*r; n++;
  }
  if(den===0) return {S:null,h:null,hmax:null,n:0};
  return {S:1-num/(2*den), h:Math.sqrt(rss)/(2*den), hmax:lin/(2*den), n};
}
function rankParties(answers){
  let scored=parties.map(p=>Object.assign({pid:p.id,party:p}, matchScore(answers,p.id)));
  let rankable=scored.filter(s=>s.S!=null).sort((a,b)=> b.S-a.S || String(a.pid).localeCompare(String(b.pid)));
  let rank=0;
  rankable.forEach((s,i)=>{ if(i===0){rank=1;} else { const prev=rankable[i-1];
    const bound=Math.max(s.hmax||0, prev.hmax||0); if(Math.abs(prev.S-s.S)>=bound) rank=i+1; }
    s.rank=rank; });
  const noOverlap=scored.filter(s=>s.S==null).map(s=>(s.rank=null,s));
  return {ranked:rankable.concat(noOverlap), low:Object.keys(answers).length<MIN_ANSWERS};
}
const pct=x=>Math.round(x*100), pp=x=>Math.round(x*100);

// ---- helpers ----
const SCALE=[{u:-1,l:"lehne stark ab",s:16},{u:-0.5,l:"lehne ab",s:11},{u:0,l:"neutral",s:7},{u:0.5,l:"stimme zu",s:11},{u:1,l:"stimme stark zu",s:16}];
const el=(h)=>{const t=document.createElement("template");t.innerHTML=h.trim();return t.content.firstChild;};
function chip(p){return `<span class="chip"><span class="sw" style="background:${p.color_hex}"></span>${p.short_name}</span>`;}

// ---- render ----
function render(){
  const app=document.getElementById("app"); app.innerHTML="";
  const banner = meta.preview ? `<div class="preview-banner"><b>VORSCHAU</b> ${meta.preview_label_de}</div>` : "";
  if(S.screen==="start") app.append(el(banner+screenStart()));
  else if(S.screen==="frage") app.append(el(banner+screenFrage()));
  else if(S.screen==="ergebnis") app.append(el(banner+screenErgebnis()));
  else if(S.screen==="methodik") app.append(el(banner+screenMethodik()));
  bind();
  window.scrollTo(0,0);
}

function sealHtml(){ return meta.signature_verified
  ? `<span class="seal"><span class="ring"><i></i></span>Signatur geprüft · ${meta.release}</span>`
  : `<span class="seal" style="color:var(--signal)">Signatur fehlt</span>`; }

function screenStart(){
  return `<div class="pad" style="display:flex;flex-direction:column;min-height:calc(100vh - 34px)">
    <div class="eyebrow">Wahlkompass · Release ${meta.release}</div>
    <h1 class="h1" style="margin-top:40px">${statements.length} Aussagen. Für jede Partei, wie nah sie Ihnen ist — mit Beleg.</h1>
    <p class="sub" style="margin-top:16px">Jede Zahl ist einen Fingertipp von den Dokumenten entfernt, die sie erzeugt haben.</p>
    <div class="card pad" style="margin-top:22px;padding:16px">
      <div style="display:flex;gap:10px;align-items:flex-start">
        <span class="seal"><span class="ring"><i></i></span></span>
        <div style="font:600 13px/1.35 'Public Sans'">Ihre Antworten verlassen dieses Gerät nicht. Kein Konto, kein Server, kein Tracking.</div>
      </div>
      <div class="sub" style="margin-top:10px;font-size:12px">${sealHtml()}</div>
    </div>
    <div class="spacer"></div>
    <div style="display:flex;flex-direction:column;gap:10px;margin-top:24px">
      <button class="btn primary" data-go="frage">Los geht's</button>
      <button class="btn ghost" data-go="ergebnis">Nur Daten ansehen</button>
    </div>
  </div>`;
}

function screenFrage(){
  const st=statements[S.i]; const a=S.answers[st.id];
  const scale=SCALE.map(o=>`<button data-u="${o.u}" class="${a&&a.u===o.u?'on':''}"><span class="dot" style="width:${o.s}px;height:${o.s}px"></span></button>`).join("");
  return `<div style="display:flex;flex-direction:column;min-height:calc(100vh - 34px)">
    <div class="pad" style="padding-bottom:0">
      <div style="display:flex;justify-content:space-between;align-items:center" class="mono" style="color:var(--graphite)">
        <span class="mono" style="font-size:12px;color:var(--graphite)">${S.i+1} / ${statements.length}</span>
        <span class="eyebrow">${st.topic}</span></div>
      <div class="prog" style="margin-top:8px"><i style="width:${(S.i+1)/statements.length*100}%"></i></div>
    </div>
    <div class="pad" style="flex:1;display:flex;flex-direction:column">
      <div class="h2" style="font-size:22px;line-height:1.3">${S.easy? (st.text_easy_de||st.text_de): st.text_de}</div>
      <div style="margin-top:14px;display:flex;gap:16px;align-items:center;font:600 12px 'Public Sans'">
        <label style="color:var(--graphite);cursor:pointer">Leichte Sprache
          <input type="checkbox" id="easy" ${S.easy?'checked':''} style="vertical-align:middle;margin-left:4px"></label>
      </div>
      <div class="spacer"></div>
      <div style="padding-bottom:16px">
        <div class="eyebrow" style="margin-bottom:10px">Ihre Position</div>
        <div class="scale">${scale}</div>
        <div class="scale-lab"><span>lehne stark ab</span><span>neutral</span><span>stimme stark zu</span></div>
        <div style="margin-top:16px;display:flex;gap:10px">
          <button class="btn ghost" style="flex:1;border-style:dashed" data-skip="1">Überspringen</button>
          <button class="btn ${a&&a.w===2?'primary':'ghost'}" style="flex:1" data-weight="1">doppelt gewichten</button>
        </div>
        <div style="margin-top:12px;display:flex;justify-content:space-between;align-items:center">
          <button class="link" data-back="1" style="background:none;border:none;${S.i===0?'visibility:hidden':''}">← zurück</button>
          <span class="mono" style="font-size:11px;color:#8a8f92">auf diesem Gerät gespeichert</span>
        </div>
      </div>
    </div></div>`;
}

function screenErgebnis(){
  const {ranked, low}=rankParties(S.answers);
  const answered=Object.keys(S.answers).length;
  let rows="";
  let prevRank=null;
  for(const r of ranked){
    if(r.S==null){ // keine Überschneidung
      rows+=`<div class="pad" style="padding:12px 22px;opacity:.7;display:flex;align-items:center;gap:10px">
        ${chip(r.party)}<span class="kbp" style="margin-left:auto">keine belegbare Überschneidung</span></div>`;
      continue;
    }
    const tie = prevRank===r.rank;
    const s=pct(r.S), ci=pp(r.h);
    const fillW=Math.max(0,Math.min(100,s)), wl=Math.max(0,s-ci), ww=Math.min(100,2*ci);
    const total=statements.length, cov=r.n;
    rows+=`<div class="pad ${tie?'tiebracket':''}" style="padding:14px 22px;cursor:pointer" data-party="${r.pid}">
      <div style="display:flex;align-items:center;gap:12px">
        <span class="mono" style="font-weight:600;width:16px;color:${tie?'var(--graphite)':'var(--ink)'}">${tie?'':r.rank}</span>
        ${chip(r.party)}
        <span class="mono" style="margin-left:auto;font-weight:600">${s} % ± ${ci}</span>
      </div>
      <div class="bar" style="margin-top:9px">
        <div class="track"></div><div class="fill" style="width:${fillW}%"></div>
        <div class="whisk" style="left:${wl}%;width:${ww}%"></div>
      </div>
      <div style="margin-top:6px;display:flex;justify-content:space-between">
        <span class="mono" style="font-size:11px;color:var(--graphite)">${cov}/${total} Fragen belegbar</span>
        <span class="link" data-party="${r.pid}">${S.openParty===r.pid?'Belege ausblenden ▴':'Belege ansehen ▾'}</span>
      </div>
      ${S.openParty===r.pid? partyBreakdown(r):""}
    </div>`;
    prevRank=r.rank;
  }
  const lowWarn = low ? `<div class="pad"><div class="warn"><b>Wenige Antworten (${answered}).</b> Unter ${MIN_ANSWERS} Antworten zeigen wir keine belastbare Reihung — bitte weitere Aussagen beantworten.</div></div>`:"";
  return `<div style="display:flex;flex-direction:column;min-height:calc(100vh - 34px)">
    <div class="pad" style="border-bottom:1px solid var(--line)">
      <div class="h2">Ihr Ergebnis</div>
      <div class="sub" style="margin-top:4px;font-size:12px">Reihung nach Übereinstimmung · ${answered} beantwortet · Balken = Wert, ├─┤ = Fehlerspanne</div>
    </div>
    ${lowWarn}
    <div>${rows}</div>
    <div class="footer">${sealHtml()}<span class="link" data-go="methodik">Methodik</span></div>
  </div>`;
}

function partyBreakdown(r){
  let out=`<div style="margin-top:12px;border-left:2px solid var(--petrol);padding:2px 0 2px 12px;display:flex;flex-direction:column;gap:8px" onclick="event.stopPropagation()">`;
  out+=`<div class="eyebrow">Aufschlüsselung je Aussage — Zelle = Beleg-Zug</div>`;
  for(const st of statements){
    const pos=posOf(r.pid,st.id); const key=r.pid+":"+st.id; const open=S.openBeleg[key];
    if(pos.p==null){ out+=`<div style="display:flex;align-items:center;gap:8px;font-size:12px"><span>${st.text_de.slice(0,42)}…</span><span class="kbp" style="margin-left:auto">— keine belegbare Position</span></div>`; continue; }
    out+=`<div>
      <div style="display:flex;align-items:center;gap:8px;font-size:12px;cursor:pointer" data-beleg="${key}">
        ${pos.divergent?'<span class="divdot" title="Sagen ≠ Tun"></span>':''}
        <span>${st.text_de.slice(0,40)}…</span>
        <span class="mono" style="margin-left:auto;color:var(--petrol);font-size:11px">p ${pos.p.toFixed(2)} · KI ${(pos.confidence).toFixed(2)} ${open?'▴':'▸'}</span>
      </div>${open?belegZug(pos):""}</div>`;
  }
  out+=`</div>`;
  return out;
}

function belegZug(pos){
  let cards="";
  const ev=(pos.evidence_ids||[]).map(id=>evidence[id]).filter(Boolean).sort((a,b)=>a.tier-b.tier||(a.date<b.date?1:-1));
  for(const e of ev){
    const tclass= e.tier===1?"t1":e.tier===2?"t2":"t3";
    const tlabel= e.tier===1?"T1 ▮ Abstimmung":e.tier===2?"T2 ● Programm":"T3 ◆ Kodierung";
    cards+=`<div class="evcard">
      <div style="display:flex;align-items:center;gap:8px"><span class="tier ${tclass}">${tlabel}</span>
        <span class="mono" style="margin-left:auto;font-size:11px;color:var(--graphite)">${e.date}</span></div>
      <div class="extract">${(e.extract||"").replace(/</g,"&lt;")}</div>
      <div style="margin-top:8px;display:flex;gap:12px;align-items:center" class="mono" style="font-size:11px">
        <span class="link">Quelle →</span><span style="color:#9A8E7F">#${(e.sha256||"").slice(0,6)}…</span></div>
    </div>`;
  }
  const div = pos.divergent ? `<div style="margin-top:8px;font-size:11px;color:var(--signal)">Sagen ≠ Tun: sagt ${pos.p_said}, tut ${pos.p_did} (Regel: |gesagt − getan| > 0,5, für alle Parteien gleich).</div>`:"";
  return `<div style="margin-top:8px">${div}${cards}<div style="margin-top:8px;font-size:11px;color:var(--graphite)">Berechnung: p = ${pos.p.toFixed(2)} aus ${ev.length} Beleg(en) · belegbasiert, nicht Selbstauskunft.</div></div>`;
}

function screenMethodik(){
  return `<div class="pad" style="display:flex;flex-direction:column;gap:14px;min-height:calc(100vh - 34px)">
    <div class="h2">Methodik</div>
    <p class="sub">Der Übereinstimmungswert ist die einzige Rechnung zwischen Ihrer Eingabe und der Reihung — symmetrisch über alle Parteien, ohne gelernte Parameter, ohne KI im Score-Pfad.</p>
    <div class="card pad" style="padding:14px">
      <div class="mono" style="font-size:13px">S(P) = 1 − Σ wᵢ·|uᵢ − pᵢ| / (2·Σ wᵢ)</div>
      <div class="mono" style="font-size:12px;color:var(--graphite);margin-top:8px">τ = (1.0, 0.8, 0.6, 0.3) · λ = ln2/4 · W₀ ≈ 1.30</div>
    </div>
    <p class="sub"><b>Sagen vs. Tun:</b> weicht die schriftliche Position (T2) vom Abstimmungsverhalten (T1) um mehr als 0,5 ab, wird die Zelle markiert — mechanisch, für jede Partei gleich.</p>
    <p class="sub"><b>Keine belegbare Position:</b> ohne ausreichenden Beleg wird nichts erfunden — die Zelle wird aus Zähler und Nenner entfernt, nicht als 0 gewertet.</p>
    <p class="sub"><b>Reproduzierbar:</b> jede Zahl lässt sich aus <span class="mono">evidence.json</span> mit den veröffentlichten Formeln nachrechnen (<span class="mono">reproduce.py</span>).</p>
    ${meta.preview?`<div class="warn">${meta.preview_label_de}</div>`:""}
    <div class="footer" style="border:none;padding-left:0">${sealHtml()}<span class="link" data-go="ergebnis">← Ergebnis</span></div>
  </div>`;
}

// ---- events ----
function bind(){
  document.querySelectorAll("[data-go]").forEach(b=>b.onclick=()=>{S.screen=b.dataset.go;render();});
  document.querySelectorAll("[data-u]").forEach(b=>b.onclick=()=>{
    const st=statements[S.i]; const cur=S.answers[st.id]||{w:1};
    S.answers[st.id]={u:parseFloat(b.dataset.u), w:cur.w||1}; save();
    setTimeout(()=>{ if(S.i<statements.length-1){S.i++;} else {S.screen="ergebnis";} render(); },140);
  });
  const easy=document.getElementById("easy"); if(easy) easy.onchange=()=>{S.easy=easy.checked;save();render();};
  const skip=document.querySelector("[data-skip]"); if(skip) skip.onclick=()=>{ const st=statements[S.i]; delete S.answers[st.id]; save();
    if(S.i<statements.length-1){S.i++;render();} else {S.screen="ergebnis";render();} };
  const wt=document.querySelector("[data-weight]"); if(wt) wt.onclick=()=>{ const st=statements[S.i]; const cur=S.answers[st.id];
    if(cur){cur.w=cur.w===2?1:2; save(); render();} };
  const back=document.querySelector("[data-back]"); if(back) back.onclick=()=>{ if(S.i>0){S.i--;render();} };
  document.querySelectorAll("[data-party]").forEach(b=>b.onclick=(e)=>{e.stopPropagation();const pid=b.dataset.party;S.openParty=S.openParty===pid?null:pid;render();});
  document.querySelectorAll("[data-beleg]").forEach(b=>b.onclick=(e)=>{e.stopPropagation();const k=b.dataset.beleg;S.openBeleg[k]=!S.openBeleg[k];render();});
}
render();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
