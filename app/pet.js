// Bunny's brain and renderer: plays rig frames at 12 fps, lives his day, roams the taskbar, and runs his radial menu,
// notebook, board (your own words), lunch/tea/meeting signs, focus timers and water log.
const B=window.bunny,$=id=>document.getElementById(id);
const cv=$('c'),ctx=cv.getContext('2d',{willReadFrequently:true}),bubble=$('bubble'),chip=$('chip'),board=$('board'),radial=$('radial'),panel=$('panel');
const GAITS={walk:1,march:1.05,jog:1.9,tiptoe:0.5,skip:1.5};
const isWalk=a=>/^(walk|march|jog|tiptoe|skip)_(right|left)$/.test(a);
const FPS=12,LOOPS=new Set(['idle','scratch','read','sleep','wave','dance','look','dangle','write','sign','fall','hang','hang_back','sit_idle','sit_look','sit_read','sit_snooze',
  ...Object.keys(GAITS).flatMap(g=>[g+'_right',g+'_left'])]);
// where things sit in a frame, as fractions of its height: hands while hanging, feet when standing, seat when sitting
const HAND_Y=0.728,HAND_BACK_Y=0.687,FEET_Y=0.933,SEAT_Y=0.89;
let meta={},size,settings,area,pos={x:0,y:0},action='idle',frame=0,loopsLeft=2,acc=0,last=0,targetX=null,falling=false,vy=0,away=false,
  focus={mode:'off'},meeting=null,bubbleUntil=0,sign=null,bannerDismissed=0,lastActs=[],routine=null,nextThought=0,
  wins=[],perch=null,fallFrom=0,skipWin=null,cursor=null,cursorMoved=0,climb=null;
const cache=new Map();let cacheW=0;
const pick=a=>a[Math.floor(Math.random()*a.length)];
function frames(a){return meta[a]?.frames||1;}
const KEEP=new Set(['idle','fall','land','bounce','look','dangle']);
function load(a){if(cache.has(a)){const v=cache.get(a);cache.delete(a);cache.set(a,v);return v;}
  const list=new Array(frames(a)).fill(null),w=cv.width,h=cv.height;cache.set(a,list);
  for(let k=0;k<list.length;k++){const im=new Image();im.src=`frames/${a}/${String(k).padStart(3,'0')}.webp`;
    im.decode().then(()=>createImageBitmap(im,{resizeWidth:w,resizeHeight:h,resizeQuality:'high'})).then(b=>{if(cacheW===w&&cache.get(a)===list){list[k]=b;if(a===action&&k===frame)drawn='';}else b.close();}).catch(()=>{});}
  // keep memory small: the newest dozen actions plus the ones he needs instantly
  for(const k of [...cache.keys()]){if(cache.size<=14)break;if(k!==a&&!KEEP.has(k)&&!isWalk(k)&&k!==action){cache.get(k).forEach(b=>b&&b.close());cache.delete(k);}}
  return list;}
function img(a,i){return load(a)[i];}
function resetFrames(){for(const l of cache.values())l.forEach(b=>b&&b.close());cache.clear();cacheW=cv.width;drawn='';for(const a of KEEP)load(a);}
function play(a,loops){if(!meta[a])a='idle';action=a;frame=0;acc=0;loopsLeft=LOOPS.has(a)?(loops??2+Math.floor(Math.random()*3)):1;img(a,0);showBoard();}
function say(text,ms=3500){bubble.textContent=text;bubble.classList.add('show');bubbleUntil=performance.now()+ms;layout();}
function groundY(){return area.y+area.height-window.innerHeight;}
function mins(){const d=new Date();return d.getHours()*60+d.getMinutes();}
// his day: every time comes from your schedule in settings
const tm=s=>{const [h,mm]=String(s).split(':').map(Number);return (h||0)*60+(mm||0);};
const at=k=>tm((settings.schedule||{})[k]||{wake:'07:00',coffee:'08:30',office:'09:30',lunch:'13:30',tea:'15:30',pack:'18:30',evening:'19:15',bed:'23:00'}[k]);
function inRange(m,a,b){a=((a%1440)+1440)%1440;b=((b%1440)+1440)%1440;return a<=b?(m>=a&&m<b):(m>=a||m<b);}
function night(){return inRange(mins(),at('bed'),at('wake'));}
function weekend(){const d=new Date().getDay();return d===0||d===6;}
let battery=null;navigator.getBattery?.().then(b=>battery=b).catch(()=>{});

// ---------------- his day ----------------
function block(){
  const m=mins();
  if(night())return {acts:['sleep'],th:['Zzz…','Five more minutes…']};
  if(weekend())return {acts:['read','dance','look','idle','hop','drink','spin','turn_back'],th:['Weekend mode!','No emails today','One more chapter']};
  if(inRange(m,at('wake'),at('office')))return {acts:['coffee','look','yawn','read','idle'],th:['Coffee first.','Then the world.','Big day ahead?']};
  if(inRange(m,at('lunch')-15,at('lunch')+45))return {acts:['eat','dance','drink','laugh','idle','spin'],th:['Lunch!!','Burger o\'clock','Food is happiness']};
  if(inRange(m,at('tea'),at('tea')+30))return {acts:['tea','idle','look','tea'],th:['Chai break','Tea time!','Biscuit, anyone?']};
  if(inRange(m,at('pack'),at('evening')))return {acts:['pack','wave','hop'],th:['Packing up!','Good work today','Home time']};
  if(inRange(m,at('evening'),at('bed')))return {acts:['read','yawn','idle','dance','look','turn_back'],th:['Cozy evening','What\'s for dinner?','Movie night?']};
  return {acts:['write','think','coffee','scratch','look','read','idle','idle','turn_back'],th:['Taking notes…','Hmm, emails','Big idea incoming','Focus, Bunny','Ship it!']};
}
function ambient(){
  if(sign)return 'sign';
  if(away)return 'sleep';
  if(focus.mode==='focus')return pick(['read','read','write','think','drink']);
  if(settings.nightSleep&&night())return 'sleep';
  if(battery&&!battery.charging&&battery.level<=.15)return pick(['tired','sleep']);
  if(perch)return pick(['sit_idle','sit_look','sit_look','sit_read','sit_snooze']);
  if(routine&&routine.length)return routine.shift();
  let a=pick(block().acts);for(let i=0;i<8&&lastActs.includes(a)&&block().acts.length>2;i++)a=pick(block().acts);
  if(battery&&battery.charging&&Math.random()<.1)a='dance';
  lastActs=[a,...lastActs].slice(0,2);return a;
}
function next(finished){
  if(dragging){play('dangle',50);return;}
  if(falling){play(vy<0?'bounce':'fall',vy<0?1:99);return;}
  if(perch&&perch.state==='hang'){Math.random()<.75?startClimb():letGo('Nope, can\'t hold on!');return;}
  if(sign){play('sign',99);return;}
  if(!perch&&cursorMode()==='watch'&&Date.now()-cursorMoved<6000&&Math.random()<.7){play('watch');return;}
  if(!perch&&cursorMode()==='follow'&&followCursor())return;
  if(!perch&&!settings.stayPut&&cursorMode()!=='follow'&&!away&&focus.mode!=='focus'&&!(routine&&routine.length)&&!(settings.nightSleep&&night())&&!isWalk(finished)&&!panelOpen()&&Math.random()<.25){walkSomewhere();return;}
  play(ambient());
}
const cursorMode=()=>settings.cursor||'off';
function gait(){const m=mins();if(settings.nightSleep&&night())return 'tiptoe';
  if(inRange(m,at('lunch')-15,at('lunch')+45))return pick(['skip','skip','walk','jog']);
  if(inRange(m,at('evening'),at('bed')))return pick(['walk','tiptoe','walk']);
  return pick(['walk','walk','march','jog','tiptoe','skip']);}
function walkTo(x,g){targetX=x;play((g||gait())+(targetX>pos.x?'_right':'_left'),99);}
function walkSomewhere(){const margin=20,span=area.width-window.innerWidth-2*margin;walkTo(area.x+margin+Math.random()*Math.max(1,span));}

// ---------------- signs: lunch, tea, meeting and your own board ----------------
const SIGNS={lunch:['GONE FOR LUNCH','be right back'],tea:['GONE FOR TEA','be right back'],meeting:['IN A MEETING','back soon']};
const AREA={x:130,y:343,w:124,h:103},MAX_TS=[20,27,36];
function holdSign(kind){
  closeRadial();closePanel();targetX=null;sign=kind;play('sign',99);
  if(kind!=='banner')say(kind==='lunch'?'Off you go. I\'ll guard the desk.':kind==='tea'?'Enjoy your chai!':'Shh. Meeting mode.',2500);
}
function dropSign(msg){if(!sign)return;const was=sign;sign=null;if(was==='banner')bannerDismissed=Date.now();play('wave',1);if(msg)say(msg,2200);}
function showBoard(){
  if(action!=='sign'||!sign||!size){board.style.display='none';boardEcho=null;return;}
  const k=size.bw/384,r=cv.getBoundingClientRect();
  Object.assign(board.style,{display:'flex',left:(r.left+AREA.x*k)+'px',top:(r.top+AREA.y*k)+'px',width:(AREA.w*k)+'px',height:(AREA.h*k)+'px'});
  if(sign==='banner'){board.textContent=settings.banner.text||'';fit(MAX_TS[settings.banner.size??1]*k,settings.banner.text);}
  else{board.innerHTML='';const t=document.createElement('span');t.textContent=SIGNS[sign][0];const s=document.createElement('small');s.textContent=SIGNS[sign][1];
    const w=document.createElement('div');w.append(t,s);board.append(w);fit(30*k,SIGNS[sign][0][0]+SIGNS[sign][0].slice(1).toLowerCase()+', '+SIGNS[sign][1]+'!');}
}
/** Largest type that fits the board without breaking words. When Bunny is small and the words get tiny, his bubble repeats them. */
let boardEcho=null;
function fit(max,text){let fs=max;board.style.fontSize=fs+'px';
  while(fs>6&&(board.scrollHeight>board.clientHeight+1||board.scrollWidth>board.clientWidth+1)){fs-=0.5;board.style.fontSize=fs+'px';}
  boardEcho=fs<11?text:null;}
function bannerDue(){
  const b=settings.banner;if(!b||!b.text||b.mode==='off')return false;const m=mins();
  if(b.mode==='window'){const tm=s=>{const [h,mm]=String(s).split(':').map(Number);return (h||0)*60+(mm||0);};const f=tm(b.from),t=tm(b.to);return f<=t?(m>=f&&m<t):(m>=f||m<t);}
  if(b.mode==='every')return !night()&&m%Math.max(5,b.every||30)<2;
  return false;
}
setInterval(()=>{if(!settings||dragging)return;const due=bannerDue();
  if(due&&!sign&&!away&&Date.now()-bannerDismissed>3*60000)holdSign('banner');
  else if(!due&&sign==='banner'&&settings.banner.mode!=='off')dropSign();},10000);

// ---------------- falling, landing and perching on your windows ----------------
// Window rects come from the app every ~400 ms, top-most first: [id, left, top, right, bottom] in screen units.
const top0=()=>window.innerHeight-size.bh;
const handLine=y=>y+top0()+size.bh*HAND_BACK_Y;
const midX=x=>x+window.innerWidth/2;
const yFor=(edge,frac)=>edge-top0()-size.bh*frac;
const fracFor=a=>a==='hang'?HAND_Y:(a==='hang_back'||a==='climb_back')?HAND_BACK_Y:(a.startsWith('sit_')||a==='perch_turn')?SEAT_Y:FEET_Y;
const onScreen=w=>area&&w[3]>area.x+40&&w[1]<area.x+area.width-40&&w[2]>area.y-20&&w[2]<area.y+area.height-40;
function clampX(){const half=window.innerWidth/2,m=size.bw/2;pos.x=Math.max(area.x-half+m,Math.min(area.x+area.width-half-m,pos.x));}
function maximised(w){return area&&w[1]<=area.x+6&&w[2]<=area.y+6&&w[3]>=area.x+area.width-6;}
function covered(i,x,y){for(let j=0;j<i;j++){const o=wins[j];if(x>=o[1]&&x<=o[3]&&y>=o[2]&&y<=o[4])return true;}return false;}
function ledgeBetween(a,b){if(settings.windows===false)return null;const cx=midX(pos.x),grip=size.bw*0.28;
  for(let i=0;i<wins.length;i++){const w=wins[i];if(w[0]===skipWin||maximised(w))continue;
    if(onScreen(w)&&w[2]>a&&w[2]<=b+1&&cx>w[1]+grip&&cx<w[3]-grip&&!covered(i,cx,w[2]-3))return w;}
  return null;}
let bounces=0;
// squash, stretch and tilt are springs on the canvas, so every drop and bounce wobbles a little differently
let walls=0,thrown=false,thrownAt=0,vx=0,sq=0,sqv=0,tilt=0,tiltv=0,trail=[];
function spring(dt){const t=Math.min(0.05,dt/1000);
  const stretch=falling?Math.max(-0.16,Math.min(0.12,-Math.abs(vy)*0.07)):0,lean=falling?Math.max(-10,Math.min(10,vx*24)):0;
  sqv+=(-170*(sq-stretch)-11*sqv)*t;sq+=sqv*t;tiltv+=(-120*(tilt-lean)-9*tiltv)*t;tilt+=tiltv*t;
  if(Math.abs(sq)<0.002&&Math.abs(sqv)<0.01&&Math.abs(tilt)<0.05&&Math.abs(tiltv)<0.05&&!falling){if(cv.style.transform!==''){sq=sqv=tilt=tiltv=0;cv.style.transform='';}return;}
  const sy=1-sq,sx=1+sq*0.55;cv.style.transform=`translateX(-50%) rotate(${tilt.toFixed(2)}deg) scale(${sx.toFixed(3)},${sy.toFixed(3)})`;}
function impact(v){sqv+=v*4.2;tiltv+=(Math.random()-.5)*60;}
function startFall(msg,throwV){falling=true;vy=throwV?Math.max(-0.9,Math.min(0.6,throwV.y)):0;vx=throwV?Math.max(-1.2,Math.min(1.2,throwV.x)):0;bounces=0;walls=0;thrown=Math.abs(vx)>0.55||vy<-0.5;thrownAt=performance.now();fallFrom=pos.y;targetX=null;clampX();play('fall',99);if(msg)say(msg,1500);}
function catchLedge(w){B.send('log','caught '+JSON.stringify(w));falling=false;vy=0;perch={id:w[0],dx:midX(pos.x)-w[1],state:'hang'};pos.y=yFor(w[2],HAND_BACK_Y);
  play('hang_back',2);say(pick(['Gotcha!','Grabbed it!','Phew, caught it!']),1500);}
function startClimb(){const w=wins.find(o=>o[0]===perch.id);if(!w)return letGo();perch.state='climb';
  climb={t0:performance.now(),ms:1500,y0:pos.y,y1:yFor(w[2],SEAT_Y)};play('climb_back',1);}
function letGo(msg){if(!perch)return;B.send('perch-lost');B.send('log','let go of '+perch.id+' at '+Math.round(pos.x)+','+Math.round(pos.y));skipWin=perch.id;perch=null;climb=null;startFall(msg);}
function landed(){B.send('log','landed at '+Math.round(pos.x)+','+Math.round(pos.y)+' ground '+Math.round(groundY()));skipWin=null;const h=pos.y-fallFrom;
  if(sign){play('sign',99);return;}
  if(thrown&&(walls>0||bounces>=3)){thrown=false;routine=['tired'];play('land',1);say(pick(['I need a minute…','Never… again…','*wheeze*','So… dizzy…']),3000);return;}
  if(h>size.bh*0.5||bounces){play('land',1);say(pick(['Ow… my tail.','I\'m okay! I\'m okay.','Ten out of ten landing.','Who moved the floor?','Stars. I see stars.']),2000);}
  else play(pick(['hop','look']),1);}
function physics(now,dt){
  if(climb){const k=Math.min(1,(now-climb.t0)/climb.ms),e=k*k*(3-2*k);pos.y=climb.y0+(climb.y1-climb.y0)*e;
    if(k>=1){climb=null;perch.state='sit';play('perch_turn',1);say(pick(['Nice view from up here.','My window now.','Comfy!']),2200);}
    sendPos();return;}
  if(falling&&(!Number.isFinite(groundY())||pos.y>groundY()+50)){B.send('log','fell past the ground '+JSON.stringify({pos,area,h:window.innerHeight}));recover();return;}
  if(falling){const a=handLine(pos.y);vy+=0.0022*dt;pos.y+=vy*dt;
    // a sideways throw carries him along, slowed by air and bounced off the screen edges
    pos.x+=vx*dt;vx*=Math.pow(thrown?0.99985:0.9992,dt);const half=window.innerWidth/2,m=size.bw/2,lo=area.x-half+m,hi=area.x+area.width-half-m;
    // thrown hard, he pinballs: walls and the top of the screen send him back with most of his speed
    const keep=thrown?0.86:0.5,wallHit=v=>{walls++;impact(Math.min(0.5,Math.abs(v)*0.5));tiltv+=(v>0?-1:1)*90;if(walls===1&&thrown)say(pick(['Wheee!','Whoaaa!','Not the wall!','Boing boing!']),1200);};
    if(pos.x<lo){pos.x=lo;wallHit(vx);vx=Math.abs(vx)*keep;}else if(pos.x>hi){pos.x=hi;wallHit(vx);vx=-Math.abs(vx)*keep;}
    const ceil=area.y-top0()-size.bh*0.18;if(pos.y<ceil&&vy<0){pos.y=ceil;vy=-vy*0.6;impact(0.3);walls++;}
    const w=vy>0?ledgeBetween(a,handLine(pos.y)):null;
    if(w){impact(Math.min(0.5,vy*0.3));catchLedge(w);}
    else if(pos.y>=groundY()){pos.y=groundY();
      // a real drop bounces a couple of times, each lower and a little different, before he settles
      const fresh=thrown&&walls<4&&now-thrownAt<6000,maxB=thrown?10:3,minV=thrown?0.22:0.42;
      if(vy>minV&&bounces<maxB&&!sign){bounces++;impact(Math.min(0.55,vy*0.32));
        vy=-vy*(thrown?(fresh?0.74:0.5)+Math.random()*0.08:(bounces===1?0.4+Math.random()*0.08:0.26+Math.random()*0.08));vx*=thrown?(fresh?0.97:0.85):0.55;play('bounce',1);
        if(bounces===1)say(pick(['Oof!','Ow!','Boing!']),1200);}
      else if(thrown&&Math.abs(vx)>0.08){vy=0;vx*=Math.pow(fresh?0.9993:0.996,dt);if(action!=='bounce')play('bounce',1);} // still skidding along the floor
      else{impact(Math.min(0.4,vy*0.35));falling=false;vy=0;vx=0;landed();}}
    sendPos();return;}
  if(perch){const w=wins.find(o=>o[0]===perch.id);
    if(!w||maximised(w)||!onScreen(w)){letGo(pick(['Hey! Where did it go?','Whoa, it vanished!']));return;}
    const x=w[1]+perch.dx-window.innerWidth/2,y=yFor(w[2],fracFor(action));
    if(Math.abs(x-pos.x)>.5||Math.abs(y-pos.y)>.5){pos.x=x;pos.y=y;sendPos();}}
}
// ---------------- cursor modes: watch it, or follow it along the bottom ----------------
function watchFrame(){if(!cursor)return 7;const dx=cursor.x-midX(pos.x),dy=cursor.y-(pos.y+top0()+size.bh*0.4);
  const col=Math.max(0,Math.min(4,Math.round(2+2.4*Math.tanh(dx/(size.bw*1.4)))));const row=dy<-size.bh*0.35?0:dy>size.bh*0.35?2:1;return row*5+col;}
function followTarget(){const half=window.innerWidth/2,m=size.bw/2;return Math.max(area.x-half+m,Math.min(area.x+area.width-half-m,cursor.x-half));}
function followCursor(){if(!cursor||settings.stayPut||sign||away)return false;const dx=cursor.x-midX(pos.x);
  if(Math.abs(dx)>size.bw*0.7){walkTo(followTarget(),Math.abs(dx)>size.bw*3?'jog':'walk');return true;}
  if(Date.now()-cursorMoved<6000){play('watch');return true;}
  return false;}

// ---------------- tick and draw ----------------
function tick(now){
  try{step(now);}catch(e){B.send('log','tick error: '+(e&&e.stack||e));}
  lastTick=performance.now();requestAnimationFrame(tick);
}
// if Windows ever stops giving him animation frames, a plain timer keeps him moving and drawn
let lastTick=0;setInterval(()=>{if(size&&performance.now()-lastTick>300){try{step(performance.now());}catch(e){}}},1000/30);
function step(now){
  const dt=Math.min(100,now-(last||now));last=now;acc+=dt;
  if(action==='watch'){acc=0;frame=watchFrame();
    if(cursorMode()==='off'||Date.now()-cursorMoved>6000||(cursorMode()==='follow'&&cursor&&Math.abs(cursor.x-midX(pos.x))>size.bw*1.2))next('watch');}
  else while(acc>=1000/FPS){acc-=1000/FPS;frame++;if(frame>=frames(action)){if(--loopsLeft>0)frame=0;else{frame=frames(action)-1;const done=action;next(done);}}}
  spring(dt);
  if(!dragging&&(climb||falling||perch))physics(now,dt);
  else if(targetX!==null&&isWalk(action)&&!dragging){const g=action.split('_')[0];
    if(cursorMode()==='follow'&&cursor){targetX=followTarget();const want=g+(targetX>pos.x?'_right':'_left');if(want!==action&&Math.abs(targetX-pos.x)>4)play(want,99);}
    const dir=action.endsWith('_right')?1:-1;pos.x+=dir*size.bw*0.0004*GAITS[g]*dt;
    if((dir>0&&pos.x>=targetX)||(dir<0&&pos.x<=targetX)){targetX=null;next('arrived');}sendPos();}
  draw();
  if(sign&&boardEcho&&action==='sign'&&!panelOpen()&&(!bubble.classList.contains('show')||now>bubbleUntil-200))say(boardEcho,4000);
  if(bubbleUntil&&now>bubbleUntil){bubble.classList.remove('show');bubbleUntil=0;}
  if(settings.chatty&&!sign&&!away&&!panelOpen()&&Date.now()>nextThought){if(nextThought)say(pick(block().th),3500);nextThought=Date.now()+(180+Math.random()*240)*1000;}
  const parts=[];
  if(focus.mode!=='off'){const left=Math.max(0,focus.end-Date.now());parts.push((focus.label||'Focus')+' '+Math.floor(left/60000)+':'+String(Math.floor(left/1000)%60).padStart(2,'0'));}
  if(meeting){const left=Math.max(0,meeting.at-Date.now());parts.push('Meeting in '+Math.ceil(left/60000)+' min');}
  if(parts.length){chip.style.display='block';chip.textContent=parts.join(' · ');}else chip.style.display='none';
}
let drawn='',sentX=NaN,sentY=NaN;
function draw(){const key=action+':'+frame;if(key===drawn)return;const b=img(action,frame);if(!b)return;ctx.clearRect(0,0,cv.width,cv.height);ctx.drawImage(b,0,0);drawn=key;}
function sendPos(){if(!Number.isFinite(pos.x)||!Number.isFinite(pos.y)){B.send('log','bad pos '+JSON.stringify({pos,falling,perch,action,vy,vx,area}));recover();return;}const x=Math.round(pos.x),y=Math.round(pos.y);if(x===sentX&&y===sentY)return;sentX=x;sentY=y;B.send('set-pos',{x,y});}

// ---------------- radial menu (double-click) ----------------
const ITEMS=[['Notes',()=>openNotes()],['My board',()=>openBoard()],['Lunch',()=>holdSign('lunch')],['Tea',()=>holdSign('tea')],
  ['Meeting',()=>openMeeting()],['Focus',()=>openFocus()],['Water +1',()=>logWater()],[()=>settings.stayPut?'Roam':'Stay put',()=>toggleStay()],['More',()=>openMore()]];
function buildRadial(){radial.innerHTML='';for(const [label,fn] of ITEMS){const b=document.createElement('button');b.className='hit';b.textContent=typeof label==='function'?label():label;
  b.onclick=e=>{e.stopPropagation();closeRadial();fn();};radial.append(b);}}
function toggleStay(){const on=!settings.stayPut;saveS({stayPut:on,...(on&&settings.cursor==='follow'?{cursor:'off'}:{})});
  if(on){targetX=null;if(isWalk(action))play('idle');say('Staying right here.',1800);}else say('Free to roam!',1800);}
function setCursorMode(m){const v=settings.cursor===m?'off':m;saveS({cursor:v,...(v==='follow'?{stayPut:false}:{})});B.send('cursor-mode',v);
  say(v==='watch'?'I\'ll keep an eye on your cursor.':v==='follow'?'Lead the way!':'Back to my own thing.',2000);if(v==='off'&&action==='watch')next('watch');}
function openRadial(){
  closePanel();buildRadial();layout();bubble.classList.remove('show');bubbleUntil=0;
  const r=cv.getBoundingClientRect(),cx=r.left+r.width/2,cy=r.top+r.height*0.62,rx=Math.max(178,size.bw*0.8),ry=Math.max(150,size.bw*0.72);
  // an arc from his left, over his head, to his right, clear of his ears
  [...radial.children].forEach((b,i)=>{const a=Math.PI*(1.0+i/(ITEMS.length-1));b.style.left=(cx+rx*Math.cos(a))+'px';b.style.top=(cy+ry*Math.sin(a))+'px';b.style.transitionDelay=(i*18)+'ms';});
  requestAnimationFrame(()=>radial.classList.add('open'));if(!sign)play('look',1);
}
function closeRadial(){radial.classList.remove('open');}
const radialOpen=()=>radial.classList.contains('open');

// ---------------- panels ----------------
let panelKind=null;
function panelOpen(){return panel.classList.contains('show');}
function openPanel(kind,title,sub,build,typing){
  panelKind=kind;panel.innerHTML='';const h=document.createElement('h3');h.textContent=title;
  const right=document.createElement('span');right.textContent=sub||'';const x=document.createElement('button');x.className='x';x.textContent='×';x.onclick=()=>closePanel();
  const wrap=document.createElement('div');wrap.style.display='flex';wrap.style.alignItems='center';wrap.style.gap='8px';wrap.append(right,x);h.append(wrap);
  panel.append(h);build(panel);panel.classList.add('show');layout();if(typing)B.send('focusable',true);
}
function closePanel(){if(!panelOpen())return;panel.classList.remove('show');const was=panelKind;panelKind=null;B.send('focusable',false);if(!sign&&was==='notes'&&(action==='write'||action==='read'))play('idle',1);}
function btn(parent,label,fn,cls){const b=document.createElement('button');b.className='b'+(cls?' '+cls:'');b.textContent=label;b.onclick=fn;parent.append(b);return b;}
function el(tag,props,parent){const e=Object.assign(document.createElement(tag),props||{});if(parent)parent.append(e);return e;}
const saveS=patch=>{settings={...settings,...patch};B.send('set-settings',patch);};

// notebook: up to six points; he writes while it's open, reads it on the next click
function openNotes(){
  const notes=[...(settings.notes||[])];
  openPanel('notes','My notebook',`${notes.length} of 6`,p=>{
    const ul=el('ul',{},p);
    notes.forEach((n,i)=>{const li=el('li',{className:n.done?'done':''},ul);const c=el('input',{type:'checkbox',checked:!!n.done},li);
      c.onchange=()=>{notes[i]={...n,done:c.checked};saveS({notes:[...notes]});openNotes();};
      el('span',{textContent:n.text},li);const x=el('button',{className:'x',textContent:'×',title:'Remove'},li);x.onclick=()=>{notes.splice(i,1);saveS({notes:[...notes]});openNotes();};});
    if(!notes.length)el('div',{className:'hint',textContent:'Nothing yet. Tell me what to remember.'},p);
    if(notes.length<6){const inp=el('input',{type:'text',placeholder:'Add a point and press Enter',maxLength:80},p);
      inp.onkeydown=e=>{if(e.key==='Enter'&&inp.value.trim()){notes.push({text:inp.value.trim(),done:false});saveS({notes:[...notes]});openNotes();say('Noted!',1200);}
        if(e.key==='Escape')closePanel();};
      setTimeout(()=>inp.focus(),60);}
    else el('div',{className:'hint',textContent:'Six points max. Tick one off or remove it to add more.'},p);
    if(notes.some(n=>n.done)){const row=el('div',{className:'row'},p);btn(row,'Clear ticked',()=>{saveS({notes:notes.filter(n=>!n.done)});openNotes();});}
    el('div',{className:'hint',textContent:'Click me to hear it back. Click again to close.'},p);
  },true);
  if(!sign&&action!=='write')play('write',99);
}
// his board: your words, ten words max, three sizes
function words(s){s=(s||'').trim();return s?s.split(/\s+/).length:0;}
function clip(s){return (s||'').trim().split(/\s+/).slice(0,10).join(' ').slice(0,64);}
function openBoard(){
  const b={...settings.banner};
  openPanel('board','His board',`${words(b.text)} of 10 words`,p=>{
    const inp=el('input',{type:'text',value:b.text,placeholder:'Do not disturb. Unless snacks.',maxLength:64},p);
    const count=p.querySelector('h3 span');
    inp.oninput=()=>{if(words(inp.value)>10){inp.value=clip(inp.value);}count.textContent=`${words(inp.value)} of 10 words`;b.text=inp.value.trim();saveS({banner:{...b}});if(sign==='banner')showBoard();};
    inp.onkeydown=e=>{if(e.key==='Enter'){holdSign('banner');}if(e.key==='Escape')closePanel();};
    el('div',{className:'hint',textContent:'Text size'},p);const sz=el('div',{className:'row'},p);
    ['Small','Medium','Large'].forEach((l,i)=>btn(sz,l,()=>{b.size=i;saveS({banner:{...b}});[...sz.children].forEach((c,j)=>c.classList.toggle('on',j===i));if(sign==='banner')showBoard();},i===(b.size??1)?'on':''));
    el('div',{className:'hint',textContent:'When does he hold it up?'},p);const md=el('div',{className:'row'},p);
    const modes=[['off','When I ask'],['every','Now and then'],['window','Set times']];
    const extra=el('div',{},p);
    const drawExtra=()=>{extra.innerHTML='';
      if(b.mode==='every'){const r=el('div',{className:'row'},extra);[15,30,60].forEach(m=>btn(r,m===60?'Every hour':`Every ${m} min`,()=>{b.every=m;saveS({banner:{...b}});drawExtra();},b.every===m?'on':''));
        el('div',{className:'hint',textContent:'He holds it up for two minutes each time.'},extra);}
      if(b.mode==='window'){const r=el('div',{className:'row'},extra);r.style.gap='8px';r.style.marginTop='6px';
        el('span',{textContent:'From'},r);const f=el('input',{type:'time',value:b.from},r);el('span',{textContent:'to'},r);const t=el('input',{type:'time',value:b.to},r);
        f.onchange=()=>{b.from=f.value;saveS({banner:{...b}});};t.onchange=()=>{b.to=t.value;saveS({banner:{...b}});};}};
    modes.forEach(([k,l])=>btn(md,l,()=>{b.mode=k;saveS({banner:{...b}});[...md.children].forEach((c,j)=>c.classList.toggle('on',modes[j][0]===k));drawExtra();},b.mode===k?'on':''));
    drawExtra();
    const go=el('div',{className:'row'},p);btn(go,sign==='banner'?'Put it down':'Hold it up',()=>{if(sign==='banner'){dropSign();openBoard();}else holdSign('banner');},'p');
    setTimeout(()=>inp.focus(),60);
  },true);
}
function openMeeting(){
  openPanel('meeting','Meeting',meeting?'counting down':'',p=>{
    el('div',{className:'hint',textContent:'Starts in… I\'ll wave five minutes before, then hold up "In a meeting".'},p);
    const r=el('div',{className:'row'},p);[5,10,15,30,60].forEach(m=>btn(r,`${m} min`,()=>{B.send('meeting',{minutes:m});closePanel();say(`Got it. Meeting in ${m} minutes.`,2500);}));
    const r2=el('div',{className:'row'},p);btn(r2,'I\'m in one now',()=>holdSign('meeting'),'p');
    if(meeting)btn(r2,'Cancel countdown',()=>{B.send('meeting',null);closePanel();});
  });
}
function openFocus(){
  openPanel('focus','Focus',focus.mode!=='off'?(focus.label||''):'',p=>{
    el('div',{className:'hint',textContent:'I\'ll read quietly and show the countdown.'},p);
    const r=el('div',{className:'row'},p);[25,50,90].forEach(m=>btn(r,`${m} min`,()=>{B.send('focus-start',{min:m});closePanel();}));
    const r2=el('div',{className:'row'},p);btn(r2,'Pomodoro 4 × 25',()=>{B.send('focus-start',{pomo:true});closePanel();},'p');
    if(focus.mode!=='off')btn(r2,'Stop',()=>{B.send('focus-stop');closePanel();});
  });
}
async function logWater(){const w=await B.invoke('water-log',1);targetX=null;if(!sign)play('drink',1);say(w.count>=w.goal?`${w.count} of ${w.goal} glasses. Goal done!`:`${w.count} of ${w.goal} glasses today`,3000);}
function openMore(){
  openPanel('more','Bunny','',p=>{
    el('div',{className:'hint',textContent:'Size'},p);const s=el('input',{type:'range',min:90,max:360,step:5,value:settings.bw},p);
    s.onchange=()=>{saveS({bw:+s.value});};
    const r=el('div',{className:'row'},p);
    btn(r,settings.onTop?'On top: on':'On top: off',e=>{saveS({onTop:!settings.onTop});e.target.textContent=settings.onTop?'On top: on':'On top: off';e.target.classList.toggle('on',settings.onTop);},settings.onTop?'on':'');
    btn(r,'His day',()=>{closePanel();B.send('open-settings','day');});
    btn(r,'Remind me…',()=>{closePanel();B.send('open-settings','remind');});
    btn(r,'Settings',()=>{closePanel();B.send('open-settings');});
    btn(r,'Hide',()=>{closePanel();B.send('hide');});
    el('div',{className:'hint',textContent:'Moves'},p);const mv=el('div',{className:'row'},p);
    const redraw=()=>{closePanel();openMore();};
    btn(mv,'Stay put',()=>{toggleStay();redraw();},settings.stayPut?'on':'');
    btn(mv,'Watch my cursor',()=>{setCursorMode('watch');redraw();},settings.cursor==='watch'?'on':'');
    btn(mv,'Follow my cursor',()=>{setCursorMode('follow');redraw();},settings.cursor==='follow'?'on':'');
    btn(mv,'Climb on windows',()=>{saveS({windows:settings.windows===false});B.send('windows-mode',settings.windows!==false);redraw();},settings.windows!==false?'on':'');
    el('div',{className:'hint',textContent:'Drag him above a window and let go: he grabs the edge and climbs up. Tip: hold Ctrl and scroll over him to resize.'},p);
  });
}

// ---------------- layout ----------------
function layout(){
  if(!size)return;
  const r=cv.getBoundingClientRect(),top=r.top+size.bh*0.04;
  bubble.style.bottom=(window.innerHeight-top+8)+'px';
  panel.style.bottom=(window.innerHeight-top+8)+'px';
  if(panelOpen()&&bubble.classList.contains('show'))bubble.style.bottom=(window.innerHeight-top+panel.offsetHeight+18)+'px';
  chip.style.bottom=(size.bh*0.45)+'px';chip.style.right=Math.max(8,(window.innerWidth-size.bw)/2-60)+'px';
  showBoard();
}

// ---------------- mouse: click-through except on Bunny and his UI ----------------
let over=false,dragging=false,downAt=0,downPt=null,clicks=0,clickTimer=null,holdTimer=null;
function opaqueAt(x,y){const r=cv.getBoundingClientRect(),k=cv.width/r.width;const cx=(x-r.left)*k,cy=(y-r.top)*k;if(cx<0||cy<0||cx>=cv.width||cy>=cv.height)return false;return ctx.getImageData(cx|0,cy|0,1,1).data[3]>20;}
function uiAt(x,y){const e=document.elementFromPoint(x,y);return !!(e&&e.closest('.hit'));}
window.addEventListener('mousemove',e=>{
  if(dragging){const t=performance.now();trail.push([t,e.screenX,e.screenY]);while(trail.length&&t-trail[0][0]>120)trail.shift();}
  const hit=dragging||opaqueAt(e.clientX,e.clientY)||uiAt(e.clientX,e.clientY);if(hit!==over){over=hit;B.send('hit',hit);}
  if(downPt&&!dragging&&Math.hypot(e.screenX-downPt.sx,e.screenY-downPt.sy)>5){dragging=true;clearTimeout(holdTimer);closeRadial();targetX=null;falling=false;perch=null;climb=null;skipWin=null;play('dangle',50);say('Whoa!',1200);B.send('drag-start',{x:downPt.x,y:downPt.y});}
});
window.addEventListener('mousedown',e=>{if(e.button!==0)return;
  if(!opaqueAt(e.clientX,e.clientY)){if(!uiAt(e.clientX,e.clientY)){closeRadial();if(panelKind&&panelKind!=='notes'&&panelKind!=='board')closePanel();}return;}
  downAt=performance.now();downPt={x:e.clientX,y:e.clientY,sx:e.screenX,sy:e.screenY};
  holdTimer=setTimeout(()=>{if(!dragging){if(!sign&&!perch)play('pet',1);say('♥',1500);downPt=null;}},650);});
window.addEventListener('mouseup',async e=>{
  if(e.button!==0)return;clearTimeout(holdTimer);
  if(dragging){dragging=false;B.send('drag-end');const r=await B.invoke('bounds');pos={x:r.bounds.x,y:r.bounds.y};area=r.area;
    pos.x=Math.max(area.x-window.innerWidth/3,Math.min(area.x+area.width-window.innerWidth*2/3,pos.x));
    const tv=trail.length>1?(()=>{const a=trail[0],b=trail[trail.length-1],d=Math.max(16,b[0]-a[0]);return {x:(b[1]-a[1])/d,y:(b[2]-a[2])/d};})():null;trail=[];
    if(pos.y<groundY()-2)startFall(null,tv);else{pos.y=groundY();play(sign?'sign':'look',sign?99:1);}sendPos();downPt=null;return;}
  if(!downPt)return;downPt=null;if(performance.now()-downAt>=650)return;
  clicks++;clearTimeout(clickTimer);clickTimer=setTimeout(()=>{const n=clicks;clicks=0;targetX=null;
    if(n>=2){radialOpen()?closeRadial():openRadial();return;}
    if(radialOpen()){closeRadial();return;}
    if(away){away=false;play('yawn',1);say('Oh! Hi.',1500);return;}
    if(sign){dropSign(sign==='banner'?'Okay, okay.':'Welcome back!');return;}
    // the notebook: open → he writes; click → he reads it back; click again → closed
    if(panelKind==='notes'){if(action==='write'){play('read',99);say('Reading it back…',1500);}else{closePanel();say('Saved in my notebook.',1500);}return;}
    if(panelOpen()){closePanel();return;}
    if(perch){if(perch.state==='sit')play('sit_look',1);say(pick(['Hi from up here!','I like it up here.','Nice view!']),1500);return;}
    play(night()?'yawn':'tickle',1);say(night()?'Mmh… sleeping…':pick(['Hehe! That tickles!','Stop it, haha!','Not the belly!','Hee hee!']),1600);
  },260);
});
window.addEventListener('wheel',e=>{if(!e.ctrlKey||!opaqueAt(e.clientX,e.clientY))return;e.preventDefault();saveS({bw:Math.max(90,Math.min(360,Math.round(settings.bw-e.deltaY*0.2)))});},{passive:false});
window.addEventListener('contextmenu',e=>{e.preventDefault();B.send('menu');});
window.addEventListener('keydown',e=>{if(e.key==='Escape'){closeRadial();closePanel();}});

// ---------------- events from the app ----------------
B.on('remind',r=>{if(sign)return say(r.text,9000);targetX=null;play(r.action,LOOPS.has(r.action)?2:1);say(r.text,9000);});
B.on('say',r=>{if(r.action&&!sign)play(r.action,1);say(r.text,r.ms);});
B.on('do',a=>{targetX=null;if(!sign)play(a,LOOPS.has(a)?2:1);});
B.on('sign',k=>{if(sign===k)return dropSign();holdSign(k);});
B.on('radial',()=>openRadial());
B.on('routine',k=>{if(sign||away)return;targetX=null;
  if(k==='lunch'){routine=['eat','drink'];play('dance',2);say('Lunch time! Dance first, then burger.',4000);}
  if(k==='tea'){routine=['idle'];play('tea',1);say('Tea time! Chai, anyone?',3500);}
  if(k==='pack'){const open=(settings.notes||[]).filter(n=>!n.done);routine=['wave'];play('pack',1);
    say(open.length?`Packing up! ${open.length} note${open.length>1?'s':''} still open: ${open.map(n=>n.text).join(', ')}`:'Packing up! Notebook is clear. Good work today!',9000);}});
B.on('away',v=>{if(v===away)return;away=v;if(sign)return;if(v){targetX=null;closeRadial();closePanel();play('sleep',99);}else{play('wave',1);say(pick(['Welcome back!','Oh, you\'re back!','Hi again!']),2500);}});
B.on('focus',f=>{focus=f;if(sign)return;if(f.mode==='focus'){targetX=null;play('read',99);say('Focus mode. I\'ll read quietly.',3000);}else if(f.mode==='break'){play('yawn',1);}else if(f.mode==='off')play('idle');});
B.on('meeting',m=>{meeting=m;});
function recover(a){if(a)area=a;if(!area||!Number.isFinite(groundY())){B.invoke('bounds').then(r=>{area=r.area;if(Number.isFinite(groundY()))recover();});return;}perch=null;climb=null;falling=false;vy=0;vx=0;targetX=null;if(a)area=a;
  pos.x=Number.isFinite(pos.x)?Math.max(area.x,Math.min(area.x+area.width-window.innerWidth,pos.x)):area.x+area.width*0.7-window.innerWidth/2;pos.y=groundY();sentX=NaN;sendPos();drawn='';play('look',1);}
B.on('rescue',r=>recover(r&&r.area));
B.on('area',a=>{area=a;if(perch||falling||climb)return;pos.y=groundY();sendPos();});
B.on('windows',list=>{wins=list||[];});
B.on('cursor',c=>{if(!cursor||Math.abs(c.x-cursor.x)>2||Math.abs(c.y-cursor.y)>2)cursorMoved=Date.now();cursor=c;});
B.on('settings',s=>{settings=s.settings;resize(s.size);
  if(settings.stayPut&&isWalk(action)&&cursorMode()!=='follow'){targetX=null;play('idle');}
  if(settings.windows===false&&perch)letGo();});
function resize(s){size=s;const dpr=Math.min(2,window.devicePixelRatio||1);cv.style.width=s.bw+'px';cv.style.height=s.bh+'px';
  const W=Math.round(s.bw*dpr),H=Math.round(s.bh*dpr);if(cv.width!==W||cv.height!==H){cv.width=W;cv.height=H;}drawn='';if(cacheW!==W)resetFrames();bubble.style.fontSize=Math.max(13,Math.min(17,Math.round(s.bw*0.09)))+'px';draw();layout();
  B.invoke('bounds').then(r=>{area=r.area;if(!falling&&!perch&&!climb&&!dragging){pos={x:r.bounds.x,y:groundY()};sendPos();}layout();});}

(async()=>{
  meta=window.META;
  const init=await B.invoke('init');settings=init.settings;area=init.area;pos={x:init.bounds.x,y:init.bounds.y};resize(init.size);
  await document.fonts.load('20px "Patrick Hand"').catch(()=>{});
  play('wave',1);say(pick(['Hi! I\'m Bunny. Double-click me for my menu.','Hello! Let\'s have a good day.']),3500);
  nextThought=Date.now()+90000;
  requestAnimationFrame(tick);
})();
