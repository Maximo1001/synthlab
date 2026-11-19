import { initAccount } from './account.js';
(()=>{
'use strict';
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const RM=matchMedia('(prefers-reduced-motion:reduce)').matches,INK='#231942',cl=(v,a,b)=>Math.min(b,Math.max(a,v));
const LI='#C9B8FF',SK='#A9D6FF',YE='#FFE27A',PN='#FFC2E2',MI='#B8F0D8',PU='#8B6CF0';
/* ---------- LOGO ---------- */
const LOGO=`<svg viewBox="0 0 40 40" aria-hidden="true"><defs><linearGradient id="lgg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8B6CF0"/><stop offset="1" stop-color="#5AA7F5"/></linearGradient></defs><rect width="40" height="40" rx="12" fill="url(#lgg)"/><g stroke-linecap="round" stroke-width="3.6"><path d="M11 21v-2" stroke="#fff"/><path d="M16.5 25v-10" stroke="#fff"/><path d="M22 29V11" stroke="#FFE27A"/><path d="M27.5 24v-8" stroke="#fff"/><path d="M33 21v-2" stroke="#fff" transform="translate(-1)"/></g></svg><span>synth<i class="grad">lab</i></span>`;
['#lg1','#lg2','#ldl'].forEach(s=>$(s).innerHTML=LOGO);
/* ---------- DATA ---------- */
const CATS={midi:['MIDI',LI],dj:['DJ',SK],synth:['Sintetizadores',PN],sampler:['Samplers',YE],drums:['Ritmos',MI],audio:['Audio',SK]};
const PRODS=[
['Keystone 49','midi','Teclado MIDI','Concepto de controlador de 49 teclas pensado para tocar con expresividad y mapear rápido en tu DAW.',['49 teclas','Knobs asignables','Transporte'],'Los teclados traducen tu forma de tocar en datos: notas, velocidad y expresión. Este concepto se centra en un mapeo rápido y un tamaño compacto para tu escritorio.'],
['Orbit DJ-2','dj','Controlador DJ','Concepto de controlador de dos platos con jog wheels XL para una mezcla muy táctil.',['2 platos','Jog wheels','Modos de pads'],'Los controladores DJ mezclan temas con jog wheels, faders y pads. Este concepto imagina ruedas grandes y sensibles para hacer scratch y cues con precisión.'],
['Helix One','synth','Sintetizador','Concepto de sintetizador híbrido con un recorrido de señal claro y macros a mano.',['Doble oscilador','Filtro','Macros'],'Los sintetizadores generan sonido con osciladores y lo moldean con filtros y envolventes. Helix One es un concepto construido sobre un recorrido de señal transparente.'],
['Slicer S4','sampler','Sampler','Concepto de sampler con pads, pensado para cortar y remuestrear rápido.',['Auto-corte','Remuestreo','Pads 4x4'],'Un sampler graba audio y lo reproduce en pads. Trocear bucles en patrones nuevos es un pilar del hip-hop y la música electrónica.'],
['Pulse 16','drums','Caja de ritmos','Concepto de caja de ritmos con secuenciador de pasos para crear grooves en segundos.',['16 pasos','Swing','Cadena de patrones'],'Las cajas de ritmos programan el ritmo con secuenciadores de pasos, igual que el de nuestro laboratorio. Pulse 16 imagina un flujo de trabajo centrado en el groove.'],
['Core I/O','audio','Interfaz de audio','Concepto de interfaz compacta con entradas limpias y monitorización sin complicaciones.',['2 entradas','Monitor directo','Alimentación USB'],'Una interfaz de audio convierte señales analógicas a digitales y viceversa, con previos limpios y monitorización de baja latencia.']];
const SLUGS=['keystone-49','orbit-dj-2','helix-one','slicer-s4','pulse-16','core-io'];
const FIL=[['all','Todos'],...Object.entries(CATS).map(([k,v])=>[k,v[0]])];
const WF=[['Crear','Generar ideas','Empieza con una chispa: un acorde, un ritmo, una textura. Captura las ideas rápido, antes de juzgarlas. Los bucles y los accidentes felices son tu materia prima.',LI],['Grabar','Capturar la interpretación','Graba instrumentos, voces y MIDI. Un buen nivel de ganancia ahora te ahorra horas después. Haz varias tomas y quédate con los mejores momentos.',SK],['Diseñar','Dar forma al sonido','Crea timbres con síntesis, sampleo y procesado. Filtros, envolventes y efectos convierten una onda básica en un sonido propio.',YE],['Arreglar','Construir la estructura','Convierte bucles en una canción. Planifica intros, subidas, drops y pausas, y usa el contraste y el silencio para crear tensión y liberación.',PN],['Mezclar','Equilibrar todo','Equilibra niveles, coloca los elementos en el panorama, haz hueco con la EQ y cohesiona con compresión. Cada sonido necesita su lugar.',MI],['Masterizar','El pulido final','Prepara la pista para el mundo: volumen coherente, balance tonal y formato. Compárala con temas de referencia en varios sistemas de escucha.',LI]];
const SW=[['DAWs','Tu centro de mando: graba, secuencia y mezcla en un solo lugar.','M3 5h18v14H3zM3 10h18M9 5v14','Digital_audio_workstation',LI],['Plugins','Procesadores de EQ, compresión, reverb y más.','M12 2v6M12 16v6M2 12h6M16 12h6M7 7l3 3M14 14l3 3','Audio_plug-in',SK],['Instrumentos VST','Sintetizadores y samplers de software tocables por MIDI.','M3 8h18v10H3zM7 8v6M11 8v6M15 8v6M19 8v6','Virtual_Studio_Technology',YE],['Efectos','Delay, distorsión, chorus y modulación.','M2 12c3-8 5-8 8 0s5 8 8 0 3-4 4-2','Effects_unit',PN],['Utilidades de audio','Afinadores, analizadores y medidores para una mezcla honesta.','M4 18a8 8 0 1116 0M12 18l4-6','Audio_analyzer',MI]];
const SOCURL={Instagram:'#',YouTube:'#',SoundCloud:'#',Discord:'#'}; // configurable: put real URLs here
/* ---------- DEVICE ART ---------- */
const S=(x='')=>`stroke="${INK}" stroke-width="2.5" ${x}`;
const keys=(y,h)=>{let s='';for(let i=0;i<8;i++)s+=`<rect x="${20+i*20}" y="${y}" width="20" height="${h}" fill="#fff" ${S('stroke-width="2"')}/>`;[1,2,4,5,6].forEach(i=>s+=`<rect x="${18+i*20}" y="${y}" width="12" height="${h*.6}" fill="${INK}"/>`);return s};
const body=c=>`<rect x="8" y="12" width="184" height="116" rx="16" fill="${c}" ${S()}/>`;
const kn=(x,y,r=11)=>`<circle cx="${x}" cy="${y}" r="${r}" fill="#fff" ${S('stroke-width="2"')}/><path d="M${x} ${y}l${r*.5} ${-r*.7}" ${S('stroke-width="2.5" stroke-linecap="round"')}/>`;
const DEV={
midi:c=>body(c)+kn(34,38)+kn(60,38)+`<rect x="120" y="30" width="56" height="14" rx="5" fill="#fff" ${S('stroke-width="2"')}/>`+keys(62,56),
dj:c=>body(c)+[52,148].map(x=>`<circle cx="${x}" cy="62" r="33" fill="#fff" ${S()}/><circle cx="${x}" cy="62" r="9" fill="${INK}"/>`).join('')+`<rect x="92" y="30" width="16" height="68" rx="5" fill="${INK}"/><rect x="94" y="56" width="12" height="9" fill="${YE}"/>`+[0,1,2,3].map(i=>`<rect x="${22+i*19}" y="106" width="15" height="14" rx="4" fill="#fff" ${S('stroke-width="2"')}/><rect x="${108+i*19}" y="106" width="15" height="14" rx="4" fill="#fff" ${S('stroke-width="2"')}/>`).join(''),
sampler:c=>body(c)+Array.from({length:16},(_,i)=>`<rect x="${50+(i%4)*26}" y="${28+(i>>2)*24}" width="21" height="19" rx="5" fill="${i%3?'#fff':LI}" ${S('stroke-width="2"')}/>`).join(''),
synth:c=>body(c)+[0,1,2,3].map(i=>kn(36+i*38,34)).join('')+keys(60,60),
drums:c=>body(c)+kn(36,34)+kn(74,34)+kn(112,34)+Array.from({length:16},(_,i)=>`<rect x="${22+i*10.5}" y="56" width="8" height="${i%4?16:26}" rx="2" fill="${i%4?'#fff':INK}" ${S('stroke-width="2"')}/>`).join('')+[0,1,2,3].map(i=>`<rect x="${24+i*42}" y="96" width="34" height="22" rx="6" fill="#fff" ${S('stroke-width="2"')}/>`).join(''),
audio:c=>`<rect x="8" y="34" width="184" height="76" rx="16" fill="${c}" ${S()}/>`+kn(44,72,15)+kn(86,72,15)+kn(152,72,18)+`<circle cx="114" cy="50" r="4" fill="${PN}" ${S('stroke-width="2"')}/>`};
const dsvg=(t,c)=>`<svg viewBox="0 0 200 140" role="img" aria-label="${CATS[t][0]}">${DEV[t](c)}</svg>`;
/* ---------- BUILD UI ---------- */
$('#fil').innerHTML=FIL.map(([k,l],i)=>`<button data-f="${k}" aria-pressed="${!i}">${l}</button>`).join('');
$('#prods').innerHTML=PRODS.map((p,i)=>`<article class="card pr rv" data-f="${p[1]}" style="--b:${CATS[p[1]][1]};transition-delay:${i*50}ms"><div class="im">${dsvg(p[1],'#fff')}</div><button class="fav" data-fav="${SLUGS[i]}" aria-pressed="false" aria-label="Favorito: ${p[0]}">♥</button><small>Concepto · ${p[2]}</small><h3>${p[0]}</h3><p>${p[3]}</p><ul>${p[4].map(k=>`<li>${k}</li>`).join('')}</ul><button class="btn o" data-p="${i}">Ver detalles</button></article>`).join('');
$('#wf').innerHTML=WF.map((w,i)=>`<button class="st" data-w="${i}" aria-expanded="false" style="--c:${w[3]}"><small>0${i+1}</small><h3>${w[0]}</h3></button>`).join('');
$('#wd').innerHTML='<p>Selecciona una etapa para leer más.</p>';
$('#sw').innerHTML=SW.map(s=>`<a class="card rv" href="https://en.wikipedia.org/wiki/${s[3]}" target="_blank" rel="noopener"><div class="ico" style="background:${s[4]}"><svg viewBox="0 0 24 24"><path d="${s[2]}"/></svg></div><h3>${s[0]}</h3><p>${s[1]}</p><span>Saber más ↗</span></a>`).join('');
$('#fc').innerHTML=FIL.slice(1).map(([k,l])=>`<li><a href="#products" data-f="${k}">${l}</a></li>`).join('');
$('#soc').innerHTML=Object.keys(SOCURL).map(s=>`<li><a href="${SOCURL[s]}" data-s="${s}">${s}</a></li>`).join('');
const toast=m=>{const t=document.createElement('div');t.className='t';t.textContent=m;$('#ts').append(t);setTimeout(()=>{t.style.opacity=0;setTimeout(()=>t.remove(),400)},2000)};
/* ---------- ROUTER ---------- */
const PG=['home','lab','products','about','resources','account','admin'],TT={home:'Da forma a tu sonido.',lab:'Laboratorio',products:'Equipo',about:'Nosotros',resources:'Recursos',account:'Mi cuenta',admin:'Administración'};
const lk=$('#lk'),bg=$('#burger'),ind=$('#ind');let Z,H;
function moveInd(){const a=$('.links a.act');if(!a){ind.style.opacity=0;return}ind.style.opacity=1;ind.style.width=a.offsetWidth+'px';ind.style.transform=`translateX(${a.offsetLeft}px)`}
let boot=true;try{history.scrollRestoration='manual';if(location.hash)history.replaceState(null,'',location.pathname+location.search)}catch(e){}
function route(){let h=boot?'home':location.hash.slice(1);if(!PG.includes(h))h='home';$$('.pg').forEach(p=>p.hidden=p.id!=='p-'+h);$$('.links a').forEach(a=>{const on=a.dataset.p===h;a.classList.toggle('act',on);on?a.setAttribute('aria-current','page'):a.removeAttribute('aria-current')});
document.title='SYNTHLAB — '+TT[h];lk.classList.remove('open');bg.setAttribute('aria-expanded','false');document.body.style.overflow='';const pgEl=$('#p-'+h);pgEl.tabIndex=-1;pgEl.focus({preventScroll:true});scrollTo({top:0,behavior:'instant'});moveInd();Z=fit(vz);H=fit(hw);if(h!=='lab'&&play)pb.click()}
addEventListener('hashchange',route);addEventListener('resize',()=>{if(innerWidth>980&&lk.classList.contains('open'))bg.click();moveInd();Z=fit(vz);H=fit(hw)});
bg.addEventListener('click',()=>{const o=lk.classList.toggle('open');bg.setAttribute('aria-expanded',o);document.body.style.overflow=o?'hidden':''});
addEventListener('scroll',()=>$('#nav').classList.toggle('sc',scrollY>20),{passive:true});
$('#top').addEventListener('click',()=>scrollTo({top:0,behavior:RM?'auto':'smooth'}));
$$('#soc a').forEach(a=>a.addEventListener('click',e=>{if(a.getAttribute('href')==='#'){e.preventDefault();toast(a.dataset.s+': enlace aún sin configurar')}}));
const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}}),{threshold:.1});$$('.rv').forEach(el=>io.observe(el));
const cio=new IntersectionObserver(es=>es.forEach(e=>{if(!e.isIntersecting)return;cio.unobserve(e.target);const n=+e.target.dataset.n,t0=performance.now();(function f(t){const p=Math.min((t-t0)/1200,1);e.target.textContent=Math.round(n*(1-Math.pow(1-p,3)));if(p<1)requestAnimationFrame(f)})(t0)}));$$('[data-n]').forEach(el=>cio.observe(el));
/* ---------- MODAL + FILTER + WORKFLOW ---------- */
const md=$('#md'),mb=$('#mb');let last=null,onCloseM=null;
const closeM=()=>{md.classList.remove('open');document.body.style.overflow='';const f=onCloseM;onCloseM=null;f&&f();last&&last.focus()};
const openModal=(html,onClose)=>{last=document.activeElement;onCloseM=onClose||null;mb.innerHTML=html;md.classList.add('open');document.body.style.overflow='hidden'};
mb.addEventListener('click',e=>{if(e.target.closest('.x,[data-close]'))closeM()});md.addEventListener('click',e=>{if(e.target===md)closeM()});
addEventListener('keydown',e=>{if(e.key==='Escape'){if(md.classList.contains('open'))closeM();else if(lk.classList.contains('open'))bg.click()}});
$('#prods').addEventListener('click',e=>{const b=e.target.closest('[data-p]');if(!b)return;const p=PRODS[b.dataset.p];last=b;mb.innerHTML=`<button class="x" aria-label="Cerrar">✕</button><div class="im" style="--b:${CATS[p[1]][1]}">${$('svg',b.closest('.pr')).outerHTML}</div><small>Concepto · ${p[2]}</small><h3 id="mt">${p[0]}</h3><p>${p[5]}</p><ul>${p[4].map(x=>`<li>${x}</li>`).join('')}</ul><p><small>Concepto ficticio con fines ilustrativos. Sin especificaciones reales.</small></p><a class="btn" href="#lab" data-close>Probar el laboratorio</a>`;md.classList.add('open');document.body.style.overflow='hidden';$('.x',mb).focus()});
function filter(f){$$('#fil button').forEach(x=>x.setAttribute('aria-pressed',x.dataset.f===f));$$('.pr').forEach(c=>{if(f==='all'||c.dataset.f===f){c.hidden=false;c.classList.add('in');requestAnimationFrame(()=>c.classList.remove('out'))}else{c.classList.add('out');setTimeout(()=>{if(c.classList.contains('out'))c.hidden=true},350)}})}
$('#fil').addEventListener('click',e=>{const b=e.target.closest('button');if(b)filter(b.dataset.f)});
$('#fc').addEventListener('click',e=>{const a=e.target.closest('a');if(a)filter(a.dataset.f)});
$('#wf').addEventListener('click',e=>{const b=e.target.closest('.st');if(!b)return;const i=+b.dataset.w;$$('.st').forEach(s=>s.setAttribute('aria-expanded',s===b));const d=$('#wd');d.style.animation='none';void d.offsetWidth;d.style.animation='';d.style.background=WF[i][3];d.style.color=INK;d.innerHTML=`<small>ETAPA 0${i+1}/06 · ${WF[i][1]}</small><h3>${WF[i][0]}</h3><p style="color:${INK}">${WF[i][2]}</p>`});
/* ---------- CANVAS ---------- */
const fit=c=>{const r=c.getBoundingClientRect(),d=Math.min(devicePixelRatio||1,2);c.width=r.width*d;c.height=r.height*d;const x=c.getContext('2d');x.setTransform(d,0,0,d,0,0);return[x,r.width,r.height]};
const hw=$('#hw'),vz=$('#vz');let hv=false;new IntersectionObserver(es=>hv=es[0].isIntersecting).observe(hw);
function amb(t){if(hv&&H){const[x,w,h]=H;x.clearRect(0,0,w,h);[['#fff',.02,1,.8],[PU,.013,1.6,.5],[YE,.03,.7,.9]].forEach(([c,f,s,a],k)=>{x.beginPath();for(let i=0;i<=w;i+=5){const y=h*(.3+k*.2)+Math.sin(i*f+t/600*s)*18*Math.sin(i/w*Math.PI);i?x.lineTo(i,y):x.moveTo(i,y)}x.strokeStyle=c;x.globalAlpha=a;x.lineWidth=2;x.stroke()});x.globalAlpha=1}
if(!RM)requestAnimationFrame(amb)}requestAnimationFrame(amb);
/* ---------- KNOB ---------- */
function knob(host,{label,t=.5,col,fmt,on}){host.className='kn';host.tabIndex=0;host.setAttribute('role','slider');host.setAttribute('aria-label',label);host.setAttribute('aria-valuemin',0);host.setAttribute('aria-valuemax',100);
host.innerHTML=`<svg viewBox="0 0 60 60"><circle cx="30" cy="30" r="25" fill="${col}" ${S()}/><circle cx="30" cy="30" r="15" fill="#fff" ${S('stroke-width="2"')}/><g><path d="M30 30V9" ${S('stroke-width="5" stroke-linecap="round"')}/></g></svg><b></b>${label}`;
const g=$('g',host),out=$('b',host),d0=t;let tt=t,ly,lx,dr=false;
const set=v=>{tt=cl(v,0,1);g.setAttribute('transform',`rotate(${-135+270*tt} 30 30)`);out.textContent=fmt(tt);host.setAttribute('aria-valuenow',Math.round(tt*100));on(tt)};
host.addEventListener('pointerdown',e=>{dr=true;ly=e.clientY;lx=e.clientX;host.setPointerCapture(e.pointerId)});
host.addEventListener('pointermove',e=>{if(!dr)return;set(tt+((ly-e.clientY)+(e.clientX-lx))/160);ly=e.clientY;lx=e.clientX});
['pointerup','pointercancel'].forEach(n=>host.addEventListener(n,()=>dr=false));
host.addEventListener('wheel',e=>{e.preventDefault();set(tt-Math.sign(e.deltaY)*.04)},{passive:false});
host.addEventListener('dblclick',()=>set(d0));
host.addEventListener('keydown',e=>{const k={ArrowUp:.04,ArrowRight:.04,ArrowDown:-.04,ArrowLeft:-.04}[e.key];if(k){e.preventDefault();set(tt+k)}});set(t);return set}
/* ---------- AUDIO ---------- */
let ctx,master,an,data,muted=false,vol=.7,bpm=108,play=false;
const live=$('#live'),vmb=$$('#vm i'),snd=$('#snd');
const init=()=>{if(ctx){if(ctx.state==='suspended')ctx.resume();return true}
try{ctx=new(window.AudioContext||window.webkitAudioContext)();master=ctx.createGain();master.gain.value=muted?0:vol;an=ctx.createAnalyser();an.fftSize=512;an.smoothingTimeConstant=.8;data=new Uint8Array(an.frequencyBinCount);master.connect(an);an.connect(ctx.destination);live.classList.add('on');live.lastChild.textContent='EN VIVO · audio activo';snd.setAttribute('aria-pressed','true');snd.textContent='Sonido activado';toast('Motor de audio iniciado');return true}catch(e){toast('Tu navegador no soporta Web Audio');return false}};
const setM=()=>{if(master)master.gain.setTargetAtTime(muted?0:vol,ctx.currentTime,.02)};
knob($('#k-vol'),{label:'VOLUMEN',t:.7,col:LI,fmt:t=>Math.round(t*100),on:t=>{vol=t;setM()}});
const setBpmKnob=knob($('#k-bpm'),{label:'BPM',t:.4,col:YE,fmt:t=>60+Math.round(t*120),on:t=>bpm=60+Math.round(t*120)});
snd.addEventListener('click',()=>{if(!ctx){init();return}muted=!muted;snd.setAttribute('aria-pressed',!muted);snd.textContent=muted?'Sonido silenciado':'Sonido activado';setM();toast(muted?'Laboratorio silenciado':'Sonido activado')});
const noise=()=>{const b=ctx.createBuffer(1,ctx.sampleRate*.5,ctx.sampleRate),d=b.getChannelData(0);for(let i=0;i<d.length;i++)d[i]=Math.random()*2-1;const s=ctx.createBufferSource();s.buffer=b;return s};
const env=(g,t,a,d,v=1)=>{g.gain.setValueAtTime(.0001,t);g.gain.exponentialRampToValueAtTime(v,t+a);g.gain.exponentialRampToValueAtTime(.0001,t+a+d)};
const DR=['BOMBO','CAJA','HI-HAT','PALMAS','TOM','RIM','ABIERTO','CAMPANA','BOMBO 2','CAJA 2','HAT 2','CRASH','TOM 2','ZAP','BAJO','PERC'];
function drum(i){if(!init())return;const t=ctx.currentTime,o=ctx.createOscillator(),g=ctx.createGain(),k=i%8,s=i>7?1.35:1;o.connect(g);g.connect(master);
if(k===0){o.frequency.setValueAtTime(150*s,t);o.frequency.exponentialRampToValueAtTime(40,t+.15);env(g,t,.002,.35);o.start(t);o.stop(t+.4)}
else if([1,2,3,6].includes(k)){const n=noise(),f=ctx.createBiquadFilter(),ng=ctx.createGain(),hi=k===2||k===6;f.type=hi?'highpass':'bandpass';f.frequency.value=hi?7000/(s>1?1.3:1):k===3?1500:1800;n.connect(f);f.connect(ng);ng.connect(master);env(ng,t,.001,k===6?.4:hi?.06:k===3?.18:.2,.8);n.start(t);n.stop(t+.5);if(k===1){o.type='triangle';o.frequency.value=190*s;env(g,t,.001,.1,.5);o.start(t);o.stop(t+.15)}}
else if(k===4){o.frequency.setValueAtTime(220*s,t);o.frequency.exponentialRampToValueAtTime(80*s,t+.25);env(g,t,.003,.3,.9);o.start(t);o.stop(t+.35)}
else if(k===5){o.type='square';o.frequency.value=800*s;env(g,t,.001,.04,.35);o.start(t);o.stop(t+.06)}
else{o.type='square';o.frequency.value=540*s;const o2=ctx.createOscillator();o2.type='square';o2.frequency.value=800*s;o2.connect(g);env(g,t,.001,.25,.3);o.start(t);o2.start(t);o.stop(t+.3);o2.stop(t+.3)}}
/* pads (lab + hero) */
const PKEYS='1234qwerasdfzxcv',PC=[LI,YE,SK,PN,MI,LI,YE,SK,PN,MI,LI,YE,SK,PN,MI,LI];
$('#pads').innerHTML=DR.map((n,i)=>`<button class="pad" data-i="${i}" style="--c:${PC[i]}" aria-label="Pad ${n}"><span>${n}</span><span>${PKEYS[i].toUpperCase()}</span></button>`).join('');
$('#hp').innerHTML=DR.map((n,i)=>`<button aria-label="Pad de inicio ${n}"></button>`).join('');
const pe=$$('.pad'),he=$$('#hp button'),hit=i=>{drum(i);[pe[i],he[i]].forEach(p=>{p.classList.add('hit');setTimeout(()=>p.classList.remove('hit'),110)})};
pe.forEach((p,i)=>p.addEventListener('pointerdown',e=>{e.preventDefault();hit(i)}));he.forEach((p,i)=>p.addEventListener('pointerdown',e=>{e.preventDefault();hit(i)}));
addEventListener('keydown',e=>{if(e.repeat||e.ctrlKey||e.metaKey||e.altKey||md.classList.contains('open')||e.target.closest('input,textarea,select'))return;if(!$('#p-lab').hidden||!$('#p-home').hidden){const k=e.key.toLowerCase(),i=PKEYS.indexOf(k);if(i>-1&&k.length===1)hit(i)}});
/* ---------- SEQUENCER ---------- */
const ROWS=[[0,LI,'BOMBO'],[1,YE,'CAJA'],[2,SK,'HAT'],[3,PN,'PALMAS']];
let pat=[[1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0],[0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0],[0,0,1,0,0,0,1,0,0,0,1,0,0,0,1,0],[0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0]];
const sq=$('#sq');
const gp=f=>[0,1,2,3].map(g=>`<div class="gr">${[0,1,2,3].map(k=>f(g*4+k)).join('')}</div>`).join('');
const drawSq=()=>sq.innerHTML=`<div class="sq hd" aria-hidden="true"><small></small>${gp(j=>`<span>${j+1}</span>`)}</div>`+ROWS.map((r,i)=>`<div class="sq" style="--r:${r[1]}" data-r="${i}"><small>${r[2]}</small>${gp(j=>`<button data-s="${j}" aria-pressed="${!!pat[i][j]}" aria-label="${r[2]} paso ${j+1}"></button>`)}</div>`).join('');drawSq();
sq.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;const r=+b.closest('.sq').dataset.r,s=+b.dataset.s;pat[r][s]^=1;b.setAttribute('aria-pressed',!!pat[r][s]);if(pat[r][s])drum(ROWS[r][0])});
$('#rnd').addEventListener('click',()=>{pat=pat.map((r,i)=>r.map((_,j)=>Math.random()<[.25,.15,.45,.1][i]?1:0));drawSq();toast('Patrón aleatorio')});
$('#clr').addEventListener('click',()=>{pat=pat.map(r=>r.map(()=>0));drawSq();toast('Patrón borrado')});
let step=0,tm;const pb=$('#play');
function tick(){$$('.sq .cur').forEach(x=>x.classList.remove('cur'));$$('.hd span').forEach((x,k)=>x.classList.toggle('on',k===step));$$('.sq[data-r]').forEach((r,i)=>{r.querySelector('[data-s="'+step+'"]').classList.add('cur');if(pat[i][step])drum(ROWS[i][0])});step=(step+1)%16;tm=setTimeout(tick,60000/bpm/4)}
pb.addEventListener('click',()=>{if(!play&&!init())return;play=!play;pb.textContent=play?'■ Parar':'▶ Reproducir';pb.setAttribute('aria-pressed',play);if(play){step=0;tick()}else{clearTimeout(tm);$$('.sq .cur').forEach(x=>x.classList.remove('cur'));$$('.hd span.on').forEach(x=>x.classList.remove('on'))}});
/* ---------- VISUALIZER ---------- */
let vm='bars',zv=false;new IntersectionObserver(es=>zv=es[0].isIntersecting).observe(vz);
$('#vmode').addEventListener('click',e=>{vm=vm==='bars'?'radial':'bars';e.currentTarget.textContent='Modo: '+(vm==='bars'?'barras':'radial')});
function draw(){requestAnimationFrame(draw);if(!zv||!Z)return;const[x,w,h]=Z;x.clearRect(0,0,w,h);const N=40,v=new Array(N).fill(0);let lvl=0,wf=[];
if(an){an.getByteFrequencyData(data);wf=new Uint8Array(an.fftSize);an.getByteTimeDomainData(wf);for(let i=0;i<N;i++)v[i]=data[Math.floor(i*i/N*.9)+1]/255;lvl=v.reduce((a,b)=>a+b,0)/N}
const C=[LI,SK,YE,PN,MI];
if(vm==='bars'){const bw=w/N;v.forEach((q,i)=>{const bh=Math.max(q*h*.9,4);x.fillStyle=C[i%5];x.beginPath();x.roundRect(i*bw+2,h-bh,bw-4,bh,4);x.fill()});x.beginPath();x.strokeStyle='#fff';x.lineWidth=2;for(let i=0;i<wf.length;i++){const X=i/wf.length*w,Y=h/2+(wf[i]-128)/128*h*.35;i?x.lineTo(X,Y):x.moveTo(X,Y)}x.stroke()}
else{const cx=w/2,cy=h/2,r0=Math.min(w,h)*.2;x.lineWidth=5;x.lineCap='round';v.forEach((q,i)=>{const a=i/N*6.283,l=r0+q*h*.3;x.strokeStyle=C[i%5];x.beginPath();x.moveTo(cx+Math.cos(a)*r0,cy+Math.sin(a)*r0);x.lineTo(cx+Math.cos(a)*l,cy+Math.sin(a)*l);x.stroke()});x.beginPath();x.arc(cx,cy,r0*(1+lvl*.5),0,7);x.strokeStyle='#fff';x.lineWidth=2;x.stroke()}
if(!an){x.fillStyle='#cfc4f5';x.font='13px Space Mono';x.textAlign='center';x.fillText('Pulsa un pad para activar el audio',w/2,h-14)}
vmb.forEach((b,i)=>b.style.height=3+cl(lvl*70*(.6+i*.2),0,20)+'px')}
requestAnimationFrame(draw);
/* ---------- CUENTAS + BACKEND (ver account.js) ---------- */
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
initAccount({$,$$,toast,esc,openModal,closeModal:closeM,SLUGS,
 productName:s=>{const i=SLUGS.indexOf(s);return i>-1?PRODS[i][0]:s},
 getPattern:()=>({bpm,steps:pat.map(r=>r.slice())}),
 setPattern:p=>{pat=p.steps.map(r=>r.map(v=>v?1:0));drawSq();bpm=cl(p.bpm|0,60,180);setBpmKnob((bpm-60)/120)}});
route();
addEventListener('load',()=>{route();boot=false;setTimeout(()=>$('#ld').classList.add('off'),450)});
})();
