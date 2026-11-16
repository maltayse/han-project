'use strict';

const $ = id => document.getElementById(id);
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
const state = {data:null, session:localStorage.getItem('observer.session'), node:null,
  page:0, pending:false, paused:reducedMotion.matches, desks:[], lastFrame:0};
const labels = {busy:'작업 중', idle:'입력 대기', completed:'완료',
  'response-ended':'응답 종료', observed:'활동 관측 · 실행 미확인', unknown:'상태 미확인'};
const colors = {fable:'#658a68', opus:'#c77852', sonnet:'#628f9f', haiku:'#9785b1', unknown:'#89917c'};

function el(tag, cls, text) {
  const e=document.createElement(tag);
  if(cls)e.className=cls;
  if(text!==undefined)e.textContent=text;
  return e;
}
function focusedControl() { return document.activeElement?.dataset.focusKey; }
function restoreFocus(key) {
  if(!key)return;
  const control=[...document.querySelectorAll('[data-focus-key]')].find(e=>e.dataset.focusKey===key);
  control?.focus({preventScroll:true});
}
function observedModel(n) { return n.model || n.responseModel; }
function family(n) {
  const value=(observedModel(n)?.value || n.requestedModel || '').toLowerCase();
  return Object.keys(colors).find(k=>value.includes(k)) || 'unknown';
}
function modelLabel(n) {
  const actual=observedModel(n)?.value;
  const name=actual || n.requestedModel;
  if(!name)return '모델 미확인';
  return (actual?'':'요청 ')+name.replace(/^claude-/,'').replaceAll('-','.');
}
function effortLabel(n) {
  return n.effort?.value || (n.requestedEffort?'요청 '+n.requestedEffort:'미확인');
}
function date(t) {
  if(!t)return '시각 미기록';
  const d=new Date(typeof t==='number'&&t<1e12?t*1000:t);
  return isNaN(d)?String(t):d.toLocaleTimeString('ko-KR',{hour12:false});
}
function selectSession(id) {
  state.session=id; state.node=id; state.page=0;
  localStorage.setItem('observer.session',id); render();
}
function field(parent,label,value,source) {
  parent.append(el('div','detail-label',label),el('div','value',value||'미확인'));
  if(source)parent.append(el('div','source',source));
}

// Original pixel artwork: all furniture and characters are drawn as integer rectangles.
function rect(c,x,y,w,h,color) { c.fillStyle=color;c.fillRect(Math.round(x),Math.round(y),w,h); }
function person(c,x,y,color,frame=0,working=false,done=false) {
  rect(c,x-9,y+25,19,4,'#00000018');
  rect(c,x-5,y+15,4,10,'#45534b');rect(c,x+2,y+15,4,10,'#45534b');
  rect(c,x-7,y+24,6,3,'#344039');rect(c,x+2,y+24,6,3,'#344039');
  rect(c,x-7,y+4,15,13,color);rect(c,x-9,y+7,4,9,color);rect(c,x+7,y+7,4,9,color);
  rect(c,x-7,y-12,14,14,'#e7b68b');rect(c,x-9,y-11,3,11,'#504638');
  rect(c,x-7,y-15,13,5,'#504638');rect(c,x+5,y-11,4,7,'#504638');
  rect(c,x-3,y-5,2,2,'#3e3f34');rect(c,x+3,y-5,2,2,'#3e3f34');
  rect(c,x,y,3,1,'#bd825f');
  const hand=working?(frame%2)*2:0;
  rect(c,x-10,y+14-hand,4,4,'#e7b68b');rect(c,x+8,y+14-(working?2-hand:0),4,4,'#e7b68b');
  if(done){rect(c,x+12,y-14,9,8,'#f1f4dc');rect(c,x+14,y-10,2,2,'#52764a');rect(c,x+16,y-12,3,2,'#52764a');}
}
function portrait(n) {
  const canvas=el('canvas','mini-person');canvas.width=32;canvas.height=44;
  const c=canvas.getContext('2d');person(c,16,16,colors[family(n)],0,false,n.status==='completed');return canvas;
}
function plant(c,x,y,big=false) {
  const s=big?1.4:1;c.save();c.translate(x,y);c.scale(s,s);
  rect(c,-6,0,13,11,'#b78566');rect(c,-8,-3,17,4,'#d3a27b');rect(c,-2,-20,3,18,'#688665');
  rect(c,-13,-21,11,8,'#6b8a63');rect(c,-9,-26,8,8,'#78976d');
  rect(c,1,-27,10,9,'#547955');rect(c,7,-22,7,8,'#63855d');rect(c,-3,-32,7,10,'#8ca479');c.restore();
}
function windowArt(c,x,y) {
  rect(c,x-3,y-3,70,50,'#b2bcab');rect(c,x,y,64,44,'#c8d5c8');
  rect(c,x+4,y+4,56,36,'#b3c8c6');rect(c,x+4,y+26,56,14,'#a7bd9f');
  rect(c,x+9,y+21,13,8,'#93b191');rect(c,x+35,y+15,19,15,'#9db998');
  rect(c,x+30,y,4,44,'#e4e4d0');rect(c,x,y+20,64,3,'#e4e4d0');rect(c,x-5,y+44,74,5,'#f0eedb');
}
function background(c) {
  rect(c,0,0,600,450,'#ded5ba');
  for(let y=80;y<450;y+=17)for(let x=0;x<600;x+=62){
    const offset=(Math.floor(y/17)%2)*31;
    rect(c,x-offset,y,61,16,['#e2d8bd','#ddd1b3','#e5dac0'][(Math.floor(x/62)+Math.floor(y/17))%3]);
    rect(c,x-offset+8,y+12,26,1,'#cbbd9e40');
  }
  rect(c,0,0,600,79,'#e9eadb');rect(c,0,77,600,5,'#aeb99e');rect(c,0,82,600,4,'#c4c5a7');
  windowArt(c,48,14);windowArt(c,488,14);
  // Coordinator rug and the low wall separating work areas.
  rect(c,220,105,160,73,'#b2bea0');rect(c,224,109,152,65,'#bdc6ac');
  for(let x=230;x<375;x+=12)rect(c,x,171,6,2,'#9aa98a');
  // Bookcase, books and a small wall clock.
  rect(c,154,15,45,49,'#a8aa8d');rect(c,157,18,39,18,'#c4c5a8');rect(c,157,40,39,21,'#bdbb9a');
  ['#c48767','#809d8a','#cbb576','#859fa3','#b6a1ad'].forEach((color,i)=>{rect(c,159+i*6,22-(i%2)*3,4,14+(i%2)*3,color);rect(c,160+i*6,45,4,14,color);});
  rect(c,404,21,22,22,'#aeaf95');rect(c,407,24,16,16,'#f8f3de');rect(c,414,27,2,7,'#6b7863');rect(c,415,32,5,2,'#6b7863');
  // Sofa and coffee corner.
  rect(c,21,122,79,35,'#9aa98a');rect(c,24,118,73,22,'#aabb98');
  rect(c,23,143,76,15,'#a5b591');rect(c,18,130,9,31,'#869c7e');rect(c,94,130,9,31,'#869c7e');
  rect(c,34,123,20,13,'#d6ccaa');rect(c,62,123,23,13,'#859d83');rect(c,25,160,5,5,'#8a8168');rect(c,92,160,5,5,'#8a8168');
  rect(c,47,178,35,17,'#b99e77');rect(c,51,195,4,7,'#8d7e62');rect(c,75,195,4,7,'#8d7e62');rect(c,58,175,7,7,'#f3edda');rect(c,65,177,3,3,'#f3edda');
  rect(c,501,118,71,37,'#b5ac8e');rect(c,497,114,79,7,'#eee3c7');rect(c,506,125,28,25,'#c9bda0');rect(c,539,125,28,25,'#c9bda0');
  rect(c,519,96,17,19,'#5d6f62');rect(c,522,99,10,9,'#a8b6a3');rect(c,545,106,8,8,'#f1ebd5');
  // Floor dividers and small plants, never fake agents.
  rect(c,22,224,556,2,'#b9bea160');
  plant(c,29,97,true);plant(c,575,97,true);plant(c,26,430,true);plant(c,575,430,true);
  rect(c,462,169,16,24,'#c3aa80');rect(c,459,165,22,7,'#e2cca4');plant(c,470,165);
}
function desk(c,d,time) {
  const {x,y,n}=d, main=n.kind==='session';
  const active=n.status==='busy'&&!state.paused&&!reducedMotion.matches;
  const frame=active?Math.floor(time/220):0;
  rect(c,x-35,y+22,73,12,'#00000010');
  rect(c,x-36,y-3,73,25,main?'#b9976f':'#bfa37e');
  rect(c,x-38,y-7,77,25,main?'#dbbd90':'#dcc6a0');
  rect(c,x-38,y+15,77,4,'#b1956e');rect(c,x-33,y+19,5,14,'#a58b66');rect(c,x+28,y+19,5,14,'#a58b66');
  rect(c,x-12,y-25,26,19,'#5d6c60');rect(c,x-10,y-23,22,14,active?'#9bbfa8':'#a3b7ab');
  rect(c,x-8,y-21,12,1,'#e1e7c0');rect(c,x-8,y-18,16,1,'#d3e0b9');rect(c,x-8,y-15,8+(frame%3)*3,1,'#e1e7c0');
  rect(c,x-1,y-6,4,4,'#778371');rect(c,x-6,y-3,14,2,'#7e8a76');
  rect(c,x-9,y+2,20,6,'#a4ac98');for(let i=0;i<4;i++)rect(c,x-7+i*4,y+3,2,1,'#d3d7be');
  rect(c,x+24,y-4,6,7,'#f1ebd5');rect(c,x+30,y-2,3,3,'#eee5cb');
  rect(c,x-28,y-2,11,15,'#efead6');rect(c,x-26,y+1,6,1,'#bdc3aa');rect(c,x-26,y+4,5,1,'#bdc3aa');
  rect(c,x-12,y+18,26,19,'#71846e');rect(c,x-9,y+16,20,15,'#8fa186');
  person(c,x,y+8,colors[family(n)],frame,active,n.status==='completed');
  if(n.id===state.node){rect(c,x-16,y+39,33,2,'#c77852');rect(c,x-3,y+43,8,2,'#c77852');}
  if(main){rect(c,x-2,y-53,3,10,'#bc946b');rect(c,x+1,y-53,15,8,'#d5a15f');}
}
function paint(time=0) {
  const canvas=$('office'),c=canvas.getContext('2d');
  c.setTransform(2,0,0,2,0,0);c.imageSmoothingEnabled=false;background(c);
  // Only verified parent links are drawn; unrelated sessions never get connected.
  const chosen=state.desks.find(d=>d.n.id===state.node);
  if(chosen&&chosen.n.parentId){
    const parent=state.desks.find(d=>d.n.id===chosen.n.parentId);
    if(parent){c.strokeStyle='#b78e60';c.lineWidth=1;c.setLineDash([3,4]);c.beginPath();c.moveTo(parent.x,parent.y+45);c.lineTo(parent.x,(parent.y+chosen.y)/2);c.lineTo(chosen.x,(parent.y+chosen.y)/2);c.lineTo(chosen.x,chosen.y-39);c.stroke();c.setLineDash([]);}
  }
  state.desks.forEach(d=>desk(c,d,time));
}
function animate(time) {
  if(time-state.lastFrame>110){paint(time);state.lastFrame=time;}
  requestAnimationFrame(animate);
}
function station(n,x,y) {
  const button=el('button','station'+(n.kind==='session'?' coordinator':'')+(n.id===state.node?' chosen':''));
  button.style.left=(x/6)+'%';button.style.top=((y-65)/4.5)+'%';
  button.dataset.id=n.id;
  button.dataset.focusKey='desk:'+n.id;
  button.setAttribute('aria-label',`${n.kind==='session'?'메인 오케스트레이터':'하위 에이전트'}: ${n.name}, ${modelLabel(n)}, effort ${effortLabel(n)}, ${labels[n.status]||'미확인'}`);
  const bubble=el('span','bubble');
  bubble.append(el('span','role',n.kind==='session'?'오케스트레이터':n.parentId?'연결된 동료':'부모 미확인'),
    el('span','station-name',n.kind==='session'?'메인 지휘석':n.name),
    el('span','station-meta',modelLabel(n)+' · '+effortLabel(n)));
  bubble.append(el('span','task-bubble',n.activity||n.task||n.name));
  button.append(bubble,el('span','station-state '+n.status,labels[n.status]||'미확인'));
  button.onclick=()=>{state.node=n.id;renderOffice();inspect(n);};
  return button;
}
function inspect(n) {
  const d=$('detail');d.replaceChildren();
  if(!n){d.append(el('p','muted','표시할 에이전트가 없습니다.'));return;}
  const p=el('div','detail-portrait');p.append(portrait(n),el('span','badge '+n.status,labels[n.status]||'미확인'));
  d.append(p,el('h2','',n.name));
  field(d,'모델 · 최신 API 요청',n.model?.value,n.model&&n.model.source+' · '+date(n.model.at));
  field(d,'모델 · 최신 응답',n.responseModel?.value,n.responseModel&&n.responseModel.source+' · '+date(n.responseModel.at));
  field(d,'Effort · 관측값',n.effort?.value,n.effort&&n.effort.source+' · '+date(n.effort.at));
  if(n.kind==='agent'){
    field(d,'생성 시 요청값',(n.requestedModel||'모델 미기록')+' / '+(n.requestedEffort||'effort 미기록'),'요청값은 관측값과 다를 수 있습니다.');
    field(d,'부모 에이전트',n.parentId?(state.data.nodes.find(x=>x.id===n.parentId)?.name||n.parentId):'연결 미확인',n.parentId?'실제 toolUseId 일치':'소속 세션만 확인됨');
  }
  d.append(el('div','detail-label','맡은 작업'),el('div','prose',n.kind==='agent'?n.name:(n.task||n.name)));
  d.append(el('div','detail-label','최근 활동'));
  for(const e of [...n.events].reverse().slice(0,6)){const row=el('div','event',e.text);row.prepend(el('time','',date(e.at)));d.append(row);}
  if(!n.events.length)d.append(el('p','muted','활동 기록이 아직 없습니다.'));
  d.append(el('p','muted','모델·effort는 표시된 시각의 기록입니다. 캐릭터의 움직임은 진행률을 나타내지 않습니다.'));
}
function renderOffice() {
  if(!state.data)return;
  const focus=focusedControl();
  const nodes=state.data.nodes.filter(n=>n.sessionId===state.session);
  const agents=nodes.filter(n=>n.kind==='agent'&&($('completed').checked||n.status!=='completed'));
  // Recent unfinished work goes first; the character keeps a stable desk within each snapshot.
  agents.sort((a,b)=>(a.status==='completed')-(b.status==='completed')||String(b.lastAt||'').localeCompare(String(a.lastAt||''))||a.id.localeCompare(b.id));
  const pages=Math.max(1,Math.ceil(agents.length/6));state.page=Math.min(state.page,pages-1);
  const main=nodes.find(n=>n.kind==='session');
  const coords=[[135,257],[300,257],[465,257],[135,382],[300,382],[465,382]];
  state.desks=main?[{n:main,x:300,y:128}]:[];
  agents.slice(state.page*6,state.page*6+6).forEach((n,i)=>state.desks.push({n,x:coords[i][0],y:coords[i][1]}));
  if(!state.desks.some(d=>d.n.id===state.node))state.node=main?.id;
  const stations=$('stations');stations.replaceChildren();
  state.desks.forEach(({n,x,y})=>stations.append(station(n,x,y)));
  if(!main)stations.append(el('div','office-empty','팀이 아직 출근하지 않았어요. Claude Code 세션을 실행하거나 필터를 확인하세요.'));
  $('page').textContent=`${state.page+1} / ${pages}`;$('prev').disabled=state.page===0;$('next').disabled=state.page===pages-1;
  paint();
  inspect(nodes.find(n=>n.id===state.node));
  restoreFocus(focus);
}
function neighbor(session) {
  const n=state.data.nodes.find(n=>n.id===session.id)||{status:session.status};
  const b=el('button','neighbor'),canvas=el('canvas');canvas.width=124;canvas.height=96;
  b.dataset.focusKey='neighbor:'+session.id;
  const c=canvas.getContext('2d');c.scale(2,2);rect(c,0,0,62,48,'#ded5ba');rect(c,0,0,62,17,'#bcc9b0');
  rect(c,6,5,13,9,'#e6ecdc');rect(c,19,30,32,10,'#c6ab82');rect(c,36,19,12,10,'#617a67');
  person(c,27,20,colors[family(n)],0,false);b.append(canvas);
  const info=el('span','neighbor-info');info.append(el('strong','',session.name),el('small','',labels[session.status]||'상태 미확인'));b.append(info);b.onclick=()=>selectSession(session.id);return b;
}
function render() {
  const data=state.data;if(!data)return;
  const focus=focusedControl();
  const q=$('search').value.toLowerCase(),project=$('project').value;
  const sessions=data.sessions.filter(s=>(!project||s.cwd===project)&&(!q||(s.name+' '+s.cwd).toLowerCase().includes(q)));
  if(!sessions.some(s=>s.id===state.session)){state.session=sessions.find(s=>s.status==='busy')?.id||sessions[0]?.id;state.page=0;state.node=state.session;}
  const selected=sessions.find(s=>s.id===state.session);
  $('session-count').textContent=data.sessions.length;$('sessions').replaceChildren();
  for(const s of sessions){const n=data.nodes.find(n=>n.id===s.id)||{status:s.status};const b=el('button','session'+(s.id===state.session?' selected':''));
    b.dataset.focusKey='session:'+s.id;
    const info=el('span');info.append(el('strong','',s.name),el('small','',labels[s.status]||'상태 미확인'));b.append(portrait(n),info);b.onclick=()=>selectSession(s.id);$('sessions').append(b);}
  $('title').textContent=selected?.name||'조용한 사무실';$('cwd').textContent=selected?.cwd||'세션이 없거나 필터와 일치하지 않습니다.';
  const agents=data.nodes.filter(n=>n.sessionId===state.session&&n.kind==='agent');
  $('summary').replaceChildren();$('summary').append(el('b','',agents.length),document.createTextNode('명의 동료'),el('div','',agents.filter(n=>n.status==='completed').length+'개 작업 완료'));
  if(!data.nodes.some(n=>n.id===state.node&&n.sessionId===state.session))state.node=state.session;
  renderOffice();inspect(data.nodes.find(n=>n.id===state.node));
  $('neighbors').replaceChildren();sessions.filter(s=>s.id!==state.session).forEach(s=>$('neighbors').append(neighbor(s)));
  if(sessions.length<2)$('neighbors').append(el('div','muted','다른 세션이 생기면 이곳에 표시됩니다.'));
  $('errors').replaceChildren();if(data.errors.length)$('errors').append(el('div','error','일부 기록을 읽지 못했습니다.\n'+data.errors.join('\n')));
  restoreFocus(focus);
}
async function poll() {
  if(state.pending)return;state.pending=true;
  try{
    const response=await fetch('/api/snapshot');if(!response.ok)throw new Error('HTTP '+response.status);
    state.data=await response.json();
    const selected=$('project').value,paths=[...new Set(state.data.sessions.map(s=>s.cwd))].sort();
    const options=[el('option','','모든 프로젝트')];options[0].value='';
    paths.forEach(path=>{const o=el('option','',path.split('/').pop()||path);o.value=path;options.push(o);});
    $('project').replaceChildren(...options);$('project').value=paths.includes(selected)?selected:'';
    render();$('sync').textContent='● 로컬 연결됨 · '+date(state.data.generatedAt);
  }catch(e){$('sync').textContent='연결 끊김 · 마지막 화면 유지 · '+e.message;}
  finally{state.pending=false;}
}
function motionButton(){$('motion').textContent=state.paused?'움직임 켜기':'움직임 끄기';$('motion').setAttribute('aria-pressed',String(state.paused));}
$('motion').onclick=()=>{state.paused=!state.paused;motionButton();paint();};
reducedMotion.addEventListener('change',e=>{if(e.matches)state.paused=true;motionButton();});
$('prev').onclick=()=>{state.page--;renderOffice();};$('next').onclick=()=>{state.page++;renderOffice();};
$('completed').onchange=()=>{state.page=0;renderOffice();};
$('search').oninput=render;$('project').onchange=render;
motionButton();poll();setInterval(poll,2000);requestAnimationFrame(animate);
