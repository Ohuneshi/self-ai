const canvas = document.getElementById('scene');
const ctx = canvas.getContext('2d');
const input = document.getElementById('messageInput');
const form = document.getElementById('composer');
const sendBtn = document.getElementById('sendBtn');
const statusTitle = document.getElementById('statusTitle');
const statusDetail = document.getElementById('statusDetail');
const statusSteps = document.getElementById('statusSteps');
const statusBlock = document.getElementById('statusBlock');
const bubble = document.getElementById('bubble');
const bubbleText = document.getElementById('bubbleText');
const observer = document.getElementById('observer');
const observerContent = document.getElementById('observerContent');
const observeBtn = document.getElementById('observeBtn');
const closeObserver = document.getElementById('closeObserver');
const observeFab = document.getElementById('observeFab');

let W=0,H=0,dpr=1,t=0;
let mode='idle', expression='neutral', busy=false;
let statusIndex=-1;
let jobId=null;
let pointer={x:0,y:0,inside:false};
let dragState={active:false,startX:0,startY:0,x:0,y:0,strength:0,release:0};
let smoothGaze={x:0,y:0}, floatY=0, floatTarget=0;
let bodyPull={x:0,y:0,tx:0,ty:0};
let particles=[];

const expressions = new Set(['neutral','happy','curious','tired','alert','surprised','sad','thinking']);
const stageDefs = [
  ['자동처리','입력에서 즉각적인 신호와 감정적 경향을 추출하고 있습니다.'],
  ['의식','현재 상황과 기억을 하나의 작업공간으로 정리하고 있습니다.'],
  ['이성','가능한 판단과 내부 갈등을 비교하고 있습니다.'],
  ['행동','최종 행동과 표정 방식을 선택하고 있습니다.'],
  ['학습','이번 경험을 기억과 자기모델에 반영하고 있습니다.'],
];

function resize(){
  const r=window.devicePixelRatio||1; dpr=Math.min(2,r); W=window.innerWidth; H=window.innerHeight;
  canvas.width=W*dpr; canvas.height=H*dpr; canvas.style.width=W+'px'; canvas.style.height=H+'px'; ctx.setTransform(dpr,0,0,dpr,0,0);
  particles = Array.from({length: Math.max(18, Math.min(44, Math.round(W*H/28000)))}, (_,i)=>({a:Math.random()*Math.PI*2, rr:.62+Math.random()*.60, s:.18+Math.random()*.44, drift:Math.random()*Math.PI*2, size:.7+Math.random()*1.7}));
  positionBubble();
}
window.addEventListener('resize',resize); resize();

function characterCenter(){ return {x:W*0.5 + bodyPull.x, y:H*0.48 + floatY + bodyPull.y}; }
function charR(){ return Math.max(78, Math.min(165, Math.min(W,H)*0.17)); }

function bodyShape(cx,cy,r, processingLevel=0){
  const pts=[]; const n=96; const drag=dragState.strength;
  for(let i=0;i<n;i++){
    const a=i/n*Math.PI*2;
    let wobble = 1 + 0.009*Math.sin(a*3+t*1.02) + 0.005*Math.sin(a*5-t*.66);
    if(processingLevel>0){
      wobble += processingLevel*(0.14*Math.sin(a*2-t*3.5)+0.09*Math.sin(a*5+t*4.8)+0.055*Math.sin(a*7-t*6.2));
    }
    let x=Math.cos(a)*r*wobble, y=Math.sin(a)*r*wobble;
    if(processingLevel>0){
      x *= 1 + processingLevel*(0.15*Math.sin(t*1.9)+0.055*Math.cos(t*1.1));
      y *= 1 + processingLevel*(0.18*Math.cos(t*1.55)-0.06*Math.sin(t*.85));
      y += processingLevel*Math.sin(a*3-t*3.0)*r*.035;
    }
    if(drag>0.002 && !processingLevel){
      const dx=dragState.x-cx, dy=dragState.y-cy, dist=Math.hypot(dx,dy);
      if(dist>1){
        const pa=Math.atan2(dy,dx), diff=Math.atan2(Math.sin(a-pa),Math.cos(a-pa));
        const weight=Math.exp(-(diff*diff)/(2*.44*.44));
        const proximity=.14+.86*Math.min(1,dist/(r*.96))**1.7;
        const f=.38*weight*proximity*dragState.strength;
        x += dx*f; y += dy*f;
      }
    }
    if(expression==='happy'){ x*=1.03; y*=.985; }
    if(expression==='sad'||expression==='tired'){ x*=.975; y*=1.03; }
    if(expression==='alert'){ y*=.95; }
    if(expression==='surprised'){ x*=1.055; y*=.98; }
    pts.push([cx+x,cy+y]);
  }
  return pts;
}
function pathPoints(points){ ctx.beginPath(); ctx.moveTo(points[0][0],points[0][1]); for(let i=1;i<points.length;i++){const p=points[i-1],q=points[i]; const mx=(p[0]+q[0])/2,my=(p[1]+q[1])/2; ctx.quadraticCurveTo(p[0],p[1],mx,my);} const p=points[points.length-1],q=points[0]; ctx.quadraticCurveTo(p[0],p[1],q[0],q[1]); ctx.closePath(); }

function drawCharacter(){
  const r=charR(); const c=characterCenter();
  const processing = mode==='processing' ? 1 : mode==='talking' ? .38 : 0;
  const grad=ctx.createRadialGradient(c.x,c.y,r*.1,c.x,c.y,r*2.3);
  grad.addColorStop(0,'rgba(73,198,207,.10)'); grad.addColorStop(.5,'rgba(37,122,145,.06)'); grad.addColorStop(1,'rgba(5,12,20,0)');
  ctx.fillStyle=grad; ctx.beginPath(); ctx.arc(c.x,c.y,r*2.2,0,Math.PI*2); ctx.fill();
  ctx.save(); ctx.globalAlpha=.28; ctx.fillStyle='#02070D'; const sy=c.y+r*1.22; ctx.beginPath(); ctx.ellipse(c.x,sy,r*.74,r*.11,0,0,Math.PI*2); ctx.fill(); ctx.restore();
  const ringR=[r*1.72,r*1.96,r*2.20];
  ringR.forEach((rr,i)=>{
    ctx.save(); ctx.translate(c.x,c.y); ctx.rotate(t*(.13+i*.055)*(mode==='processing'?3.2:1)); ctx.scale(1,.28+.08*Math.sin(t*(.35+i))); ctx.beginPath(); ctx.ellipse(0,0,rr,rr,0,0,Math.PI*2); ctx.strokeStyle=`rgba(115,231,223,${i===0?(processing?.65:.24):(.10+processing*.18)})`; ctx.lineWidth=i===0?2:1; ctx.setLineDash(i===0?[10,8]:[6,10]); ctx.stroke(); ctx.restore();
  });
  const bodyGrad=ctx.createRadialGradient(c.x-r*.18,c.y-r*.22,r*.05,c.x,c.y,r*1.05);
  bodyGrad.addColorStop(0,'#5fd5d6'); bodyGrad.addColorStop(.28,'#2c9ba9'); bodyGrad.addColorStop(.62,'#17465f'); bodyGrad.addColorStop(1,'#0b1a30');
  const pts=bodyShape(c.x,c.y,r,processing);
  pathPoints(pts); ctx.fillStyle=bodyGrad; ctx.fill();
  ctx.strokeStyle='rgba(128,235,232,.72)'; ctx.lineWidth=1.6; ctx.stroke();
  ctx.save(); ctx.globalAlpha=.75;
  particles.forEach((p,i)=>{ const rr=r*p.rr, a=p.a+t*p.s + Math.sin(t*.7+p.drift)*.12; const x=c.x+Math.cos(a)*rr, y=c.y+Math.sin(a)*rr*.72; ctx.fillStyle=i%4===0?'rgba(213,255,255,.52)':'rgba(124,231,229,.30)'; ctx.beginPath(); ctx.arc(x,y,p.size*(processing?1.5:1),0,Math.PI*2); ctx.fill(); });
  ctx.restore();
  drawFace(c.x,c.y,r);
}

function drawFace(cx,cy,r){
  const gazeX=(pointer.inside?(pointer.x-cx)/(r*1.65):0); const gazeY=(pointer.inside?(pointer.y-cy)/(r*1.65):0);
  smoothGaze.x += (Math.max(-1,Math.min(1,gazeX))-smoothGaze.x)*.16; smoothGaze.y += (Math.max(-1,Math.min(1,gazeY))-smoothGaze.y)*.16;
  const gx=smoothGaze.x*r*.18, gy=smoothGaze.y*r*.12;
  let eyeScale={neutral:1,happy:.94,curious:1.1,tired:.82,alert:.76,surprised:1.30,sad:.94,thinking:.84}[expression]||1;
  if(expression==='thinking') gy-=r*.055;
  const eyeY=cy-r*.15+gy; const eyeDx=r*(.31+(expression==='happy'?.02:0)); const er=r*.092*eyeScale;
  const lx=cx-eyeDx+gx, rx=cx+eyeDx+gx;
  ctx.fillStyle='#f4ffff';
  if(expression==='alert'){
    drawWince(lx,eyeY,er*.8,false); drawWince(rx,eyeY,er*.8,true);
  } else if(expression==='tired'||expression==='sad'){
    drawLine(lx-er,eyeY,lx+er,eyeY); drawLine(rx-er,eyeY,rx+er,eyeY);
  } else if(expression==='thinking'){
    drawDot(lx,eyeY,er*.88); drawDot(rx+ r*.018,eyeY-r*.008,er*.88);
  } else {
    drawDot(lx,eyeY,er); drawDot(rx,eyeY,er);
  }
  ctx.strokeStyle='#f4ffff'; ctx.lineWidth=Math.max(2,r*.042); ctx.lineCap='round';
  const my=cy+r*.10;
  if(expression==='surprised'){ ctx.fillStyle='#f4ffff'; ctx.beginPath(); ctx.ellipse(cx,my,r*.055,r*.065,0,0,Math.PI*2); ctx.fill(); }
  else if(expression==='happy'){ ctx.beginPath(); ctx.arc(cx,my,r*.14,0.15*Math.PI,.85*Math.PI); ctx.stroke(); }
  else if(expression==='sad'){ ctx.beginPath(); ctx.arc(cx,my+r*.04,r*.12,1.15*Math.PI,1.85*Math.PI); ctx.stroke(); }
  else if(expression==='thinking'){ ctx.beginPath(); ctx.moveTo(cx-r*.07,my+r*.01); ctx.quadraticCurveTo(cx,my-r*.015,cx+r*.07,my+r*.01); ctx.stroke(); }
  else if(expression==='curious'){ ctx.beginPath(); ctx.arc(cx,my,r*.105,.05*Math.PI,.68*Math.PI); ctx.stroke(); }
  else if(expression==='alert'){ drawLine(cx-r*.065,my,cx+r*.065,my); }
  else { ctx.beginPath(); ctx.arc(cx,my,r*.11,.18*Math.PI,.82*Math.PI); ctx.stroke(); }
}
function drawDot(x,y,r){ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fill();}
function drawLine(x1,y1,x2,y2){ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();}
function drawWince(x,y,s,flip){ctx.beginPath();if(!flip){ctx.moveTo(x-s,y-s*.8);ctx.lineTo(x+s,y);ctx.lineTo(x-s,y+s*.8);}else{ctx.moveTo(x+s,y-s*.8);ctx.lineTo(x-s,y);ctx.lineTo(x+s,y+s*.8);}ctx.stroke();}

function loop(){ t+=1/60;
  const processing=mode==='processing';
  const targetFloat= -charR()*((processing?.16:(mode==='talking'?.085:.075))*Math.sin(t*(processing?4.1:mode==='talking'?2.1:1.65)) + .025*Math.sin(t*.83+.8));
  floatY += (targetFloat-floatY)*.18;
  if(!dragState.active){ bodyPull.tx*=.88; bodyPull.ty*=.88; bodyPull.x+=(bodyPull.tx-bodyPull.x)*.18; bodyPull.y+=(bodyPull.ty-bodyPull.y)*.18; dragState.strength*=.93; }
  ctx.clearRect(0,0,W,H); drawCharacter(); requestAnimationFrame(loop);
}
requestAnimationFrame(loop);

function pointerPos(e){ const r=canvas.getBoundingClientRect(); return {x:(e.clientX??e.touches?.[0]?.clientX)-r.left,y:(e.clientY??e.touches?.[0]?.clientY)-r.top}; }
function press(e){ const p=pointerPos(e); const c=characterCenter(); if(Math.hypot(p.x-c.x,p.y-c.y) > charR()*1.08) return; dragState.active=true; dragState.startX=dragState.x=p.x; dragState.startY=dragState.y=p.y; dragState.strength=.1; dragState.release=0; canvas.setPointerCapture?.(e.pointerId); }
function move(e){ const p=pointerPos(e); pointer={x:p.x,y:p.y,inside:true}; if(!dragState.active)return; dragState.x=p.x; dragState.y=p.y; const c=characterCenter(); const dx=p.x-c.x,dy=p.y-c.y,dist=Math.hypot(dx,dy); dragState.strength=Math.min(1,dist/(charR()*.9)); bodyPull.tx=Math.max(-charR()*.20,Math.min(charR()*.20,(p.x-dragState.startX)*.16)); bodyPull.ty=Math.max(-charR()*.20,Math.min(charR()*.20,(p.y-dragState.startY)*.16)); }
function release(e){ if(!dragState.active)return; dragState.active=false; dragState.strength*=.68; bodyPull.tx*=.35; bodyPull.ty*=.35; }
canvas.addEventListener('pointerdown',press); canvas.addEventListener('pointermove',move); canvas.addEventListener('pointerup',release); canvas.addEventListener('pointercancel',release); canvas.addEventListener('pointerleave',()=>{pointer.inside=false;});

function setMode(next, expr=expression){ mode=next; expression=expressions.has(expr)?expr:'neutral'; updateStatus(); positionBubble(); }
function updateStatus(){
  if(mode==='idle'){statusTitle.textContent='대기 중';statusDetail.textContent='천천히 유영하고 있습니다';statusSteps.innerHTML='';statusBlock.classList.remove('processing','talking');}
  else if(mode==='talking'){statusTitle.textContent='대화 중';statusDetail.textContent='당신의 이야기에 반응하고 있습니다';statusSteps.innerHTML='';statusBlock.classList.remove('processing');statusBlock.classList.add('talking');}
  else {statusTitle.textContent='처리 중';statusBlock.classList.remove('talking');statusBlock.classList.add('processing');statusDetail.textContent=stageDefs[statusIndex]?.[1]||'생각하고 있습니다';statusSteps.innerHTML=stageDefs.map((s,i)=>`<span class="step ${i<statusIndex?'done':''} ${i===statusIndex?'active':''}">${s[0]}</span>`).join('');}
}
function showBubble(text){ bubbleText.textContent=text; bubble.classList.remove('hidden'); positionBubble(); }
function hideBubble(){bubble.classList.add('hidden');}
function positionBubble(){ if(bubble.classList.contains('hidden'))return; const c=characterCenter(), r=charR(); const br=bubble.getBoundingClientRect(); let side='left'; let x=c.x-r*.9-br.width-24; if(x<12){side='right';x=c.x+r*.9+24;} x=Math.max(12,Math.min(W-br.width-12,x)); let y=Math.max(88,Math.min(H-br.height-110,c.y-r*.75)); bubble.style.left=x+'px'; bubble.style.top=y+'px'; bubble.classList.remove('left','right'); bubble.classList.add(side); }

async function postChat(text){ const res=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})}); if(!res.ok)throw new Error(await res.text()); return res.json(); }
async function pollJob(id){
  for(;;){ const res=await fetch('/api/status/'+encodeURIComponent(id)); const data=await res.json(); if(data.stage_index!==undefined){statusIndex=data.stage_index;statusDetail.textContent=data.message||stageDefs[data.stage_index]?.[1]||'';updateStatus();}
    if(data.status==='done') return data.result; if(data.status==='error') throw new Error(data.error||'처리 실패'); await new Promise(r=>setTimeout(r,350)); }
}
form.addEventListener('submit',async e=>{e.preventDefault(); if(busy)return; const text=input.value.trim(); if(!text)return; busy=true;sendBtn.disabled=true;input.disabled=true;hideBubble();statusIndex=0;setMode('processing','thinking');
  try{ const start=await postChat(text); jobId=start.job_id; const result=await pollJob(jobId); expression=result.expression||'neutral'; showBubble(result.response||''); setMode('talking',expression); setTimeout(()=>{if(!busy){setMode('idle',expression);}},Math.min(6500,Math.max(2200,1700+(result.response||'').length*18))); }catch(err){ expression='alert';showBubble('오류: '+err.message);setMode('talking','alert');setTimeout(()=>{if(!busy)setMode('idle','alert')},4200); }finally{busy=false;sendBtn.disabled=false;input.disabled=false;input.focus(); }
});

observeBtn.addEventListener('click',async()=>{ const r=await fetch('/api/state'); const data=await r.json(); observerContent.innerHTML=''; const add=(title,obj)=>{const s=document.createElement('section');s.className='observer-section';s.innerHTML='<h3>'+title+'</h3><pre>'+escapeHtml(JSON.stringify(obj,null,2))+'</pre>';observerContent.appendChild(s)}; add('내부 상태',data.internal_state); add('자기모델',data.self_model); add('목표',data.goals); add('최근 경험',data.recent_episodes); observer.classList.remove('hidden'); observer.setAttribute('aria-hidden','false');});
closeObserver.addEventListener('click',()=>{observer.classList.add('hidden');observer.setAttribute('aria-hidden','true');});
observeFab.addEventListener('click',()=>observeBtn.click());
function escapeHtml(s){return s.replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}
