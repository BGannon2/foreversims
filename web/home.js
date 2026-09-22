const PALADIN=[{id:'protection',class_name:'Paladin',name:'Protection',role:'tank',detail:true},{id:'retribution',class_name:'Paladin',name:'Retribution',role:'dps',detail:true}];
async function init(){const payload=await(await fetch('/data/specs.json?v=e3fc2f8')).json(),all=[...payload.specs,...PALADIN],order=['Warrior','Paladin','Hunter','Rogue','Priest','Shaman','Mage','Warlock','Druid'],root=document.getElementById('classRoster');for(const className of order){const specs=all.filter(s=>s.class_name===className);if(!specs.length)continue;const key=className.toLowerCase(),section=document.createElement('section');section.className='home-class';section.dataset.class=key;section.dataset.class=key;section.innerHTML=`<header class="class-label"><img src="/class-icons/${key}.jpg" alt=""><div><h3>${className}</h3><small>${specs.length} simulator${specs.length===1?'':'s'}</small></div></header><div class="home-specs"></div>`;for(const spec of specs){const a=document.createElement('a');a.className='home-spec';a.dataset.class=key;a.dataset.class=key;a.href=spec.detail?`/paladin.html?spec=${spec.id}&v=42`:`/all-specs.html?spec=${spec.id}&v=42`;a.innerHTML=`<img src="/spec-icons/${spec.detail?"paladin-"+spec.id:spec.id}.jpg" alt=""><span><strong>${spec.name}</strong><small>Alpha · Classic Anniversary Phase 1–2 gear</small></span><i class="role-dot ${spec.role}"></i>`;section.lastElementChild.append(a)}root.append(section)}}init();






