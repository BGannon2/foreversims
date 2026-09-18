const fmt=(v,d=1)=>Number(v).toLocaleString(undefined,{maximumFractionDigits:d,minimumFractionDigits:d});
const classKey=n=>n.toLowerCase().replaceAll(' ','-');
const VIEWS={
  all:{metric:'dps',label:'DPS',filter:()=>true},
  dps:{metric:'dps',label:'DPS',filter:x=>x.role==='dps'},
  'tank-dps':{metric:'dps',label:'DPS',filter:x=>x.role==='tank'},
  'tank-tps':{metric:'tps',label:'TPS',filter:x=>x.role==='tank'},
};
async function init(){
  const payload=await fetch('/data/aoe-benchmarks.json').then(r=>r.json());
  const state={targets:payload.target_counts[0],view:'all'};
  document.getElementById('assumptions').textContent=`${payload.duration}s ${payload.encounter} · ${payload.iterations} iterations · every race per spec · no world buffs`;
  const targetGroup=document.getElementById('targetGroup');
  targetGroup.innerHTML=payload.target_counts.map(n=>`<button type="button" data-targets="${n}" aria-pressed="${n===state.targets}">${n} targets</button>`).join('');
  targetGroup.addEventListener('click',e=>{
    const btn=e.target.closest('button[data-targets]'); if(!btn) return;
    state.targets=+btn.dataset.targets;
    [...targetGroup.querySelectorAll('button')].forEach(b=>b.setAttribute('aria-pressed',b===btn));
    render();
  });
  const viewGroup=document.getElementById('viewGroup');
  viewGroup.addEventListener('click',e=>{
    const btn=e.target.closest('button[data-view]'); if(!btn) return;
    state.view=btn.dataset.view;
    [...viewGroup.querySelectorAll('button')].forEach(b=>b.setAttribute('aria-pressed',b===btn));
    render();
  });
  function render(){
    const view=VIEWS[state.view], metric=view.metric, label=view.label;
    document.getElementById('panelTitle').textContent=`AoE ${label} · ${state.targets} targets`;
    let rows=payload.rows.filter(x=>x.targets===state.targets && view.filter(x));
    rows=[...rows].sort((a,b)=>b[metric]-a[metric]);
    const max=Math.max(...rows.map(x=>x[metric]),1),min=Math.min(...rows.map(x=>x[metric]),0),total=rows.reduce((a,x)=>a+x[metric],0),mean=rows.length?total/rows.length:0;
    const floor=Math.max(0,min-(max-min)*0.15),span=Math.max(1,max-floor),width=v=>100*(v-floor)/span;
    document.getElementById('summary').innerHTML=`<article><span>Profiles</span><strong>${rows.length}</strong></article><article><span>Highest ${label}</span><strong>${rows.length?fmt(rows[0][metric]):'—'}</strong></article><article><span>Mean ${label}</span><strong>${fmt(mean)}</strong></article><article><span>Targets</span><strong>${state.targets}</strong></article>`;
    document.getElementById('benchmarkRows').innerHTML=rows.map((x,i)=>`<a class="benchmark-row" data-class="${classKey(x.class_name)}" href="${x.url}"><span class="rank">${i+1}</span><img src="/class-icons/${classKey(x.class_name)}.jpg" alt=""><span class="benchmark-name"><strong>${x.class_name} · ${x.name} · ${x.race}</strong><small>${x.role==='tank'?`Tank · ${fmt(x.dps)} DPS · ${fmt(x.tps)} TPS`:`${fmt(x.dps)} DPS`}</small></span><span class="benchmark-bar" data-tier="${i===0?'top':x[metric]>=mean?'above':'below'}"><i data-bar-width="${width(x[metric]).toFixed(2)}"></i><em>${i===0?'#1':'-'+fmt(100*(max-x[metric])/max,1)+'%'}</em></span><strong class="benchmark-value">${fmt(x[metric])} <small>${label}</small></strong></a>`).join('');
    document.querySelectorAll('.benchmark-bar i[data-bar-width]').forEach(el=>{el.style.width=`${Math.max(0,Math.min(100,+el.dataset.barWidth))}%`});
  }
  render();
}
init();
