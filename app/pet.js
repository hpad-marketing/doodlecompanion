// Bunny's brain and renderer: plays rig frames at 12 fps, lives his day, roams the taskbar, and runs his radial menu,
// notebook, board (your own words), lunch/tea/meeting signs, focus timers and water log.
const B=window.bunny,$=id=>document.getElementById(id);
const cv=$('c'),ctx=cv.getContext('2d',{willReadFrequently:true}),bubble=$('bubble'),chip=$('chip'),board=$('board'),radial=$('radial'),panel=$('panel'),meters=$('meters'),fx=$('fx');
const GAITS={walk:1,march:1.05,jog:1.9,tiptoe:0.5,skip:1.5,prance:1.3,naruto:2.8,phonewalk:0.7};
const isWalk=a=>/^(walk|march|jog|tiptoe|skip|prance|naruto|phonewalk)_(right|left)$/.test(a);
const FPS=12,LOOPS=new Set(['flop','readwalk','readwalk_side_right','readwalk_side_left','phonewalk_right','phonewalk_left','phone','sit_drowsy','sleep_side','guitar','dance_twirl','dance_bounce','dance_disco','dance_step','dance_wiggle','sad','happy','popcorn','paint','robot','hold_pip','idle','scratch','read','sleep','wave','dance','look','dangle','write','sign','fall','hang','hang_back','sit_idle','sit_look','sit_read','sit_snooze',
  ...Object.keys(GAITS).flatMap(g=>[g+'_right',g+'_left'])]);
// where things sit in a frame, as fractions of its height: hands while hanging, feet when standing, seat when sitting
const HAND_Y=0.728,HAND_BACK_Y=0.742,FEET_Y=0.936,SEAT_Y=0.89;
let meta={},size,settings,area,pos={x:0,y:0},action='idle',frame=0,loopsLeft=2,acc=0,last=0,targetX=null,falling=false,vy=0,away=false,
  focus={mode:'off'},meeting=null,bubbleUntil=0,sign=null,bannerDismissed=0,lastActs=[],routine=null,nextThought=0,
  wins=[],tracked=0,rebalance=false,perch=null,fallFrom=0,skipWin=null,cursor=null,cursorMoved=0,climb=null;
let cache=new Map(),oldCache=null,oldTimer=0;let cacheW=0;
const pick=a=>a[Math.floor(Math.random()*a.length)];
function frames(a){return meta[a]?.frames||1;}
const KEEP=new Set(['idle','fall','land','bounce','look','dangle','flop','pushup']);
function load(a){if(cache.has(a)){const v=cache.get(a);cache.delete(a);cache.set(a,v);return v;}
  const list=new Array(frames(a)).fill(null),w=cv.width,h=cv.height;cache.set(a,list);
  for(let k=0;k<list.length;k++){const im=new Image();im.src=`frames/${a}/${String(k).padStart(3,'0')}.webp`;
    im.decode().then(()=>createImageBitmap(im,{resizeWidth:w,resizeHeight:h,resizeQuality:'high'})).then(b=>{if(cacheW===w&&cache.get(a)===list){list[k]=b;if(a===action&&k===frame)drawn='';}else b.close();}).catch(()=>{});}
  // keep memory small: the newest dozen actions plus the ones he needs instantly
  for(const k of [...cache.keys()]){if(cache.size<=14)break;if(k!==a&&!KEEP.has(k)&&!isWalk(k)&&k!==action){cache.get(k).forEach(b=>b&&b.close());cache.delete(k);}}
  return list;}
// while new-size frames decode, the old ones are stretched in, so a resize never flashes blank
function img(a,i){return load(a)[i]||(oldCache&&oldCache.get(a)?.[i]);}
function resetFrames(){if(oldCache)for(const l of oldCache.values())l.forEach(b=>b&&b.close());oldCache=cache;cache=new Map();cacheW=cv.width;drawn='';for(const a of KEEP)load(a);
  clearTimeout(oldTimer);oldTimer=setTimeout(()=>{if(oldCache)for(const l of oldCache.values())l.forEach(b=>b&&b.close());oldCache=null;drawn='';},2500);}
let pendingWalk=null;
const DANCES=['dance','dance_twirl','dance_bounce','dance_disco','dance_step','dance_wiggle'];
function play(a,loops){if(a==='dance')a=pick(DANCES.filter(d=>meta[d]));if(!meta[a])a='idle';
  // changing walking direction: a quick full-body turn first, then the walk carries on
  if(isWalk(a)&&isWalk(action)&&a.split('_')[1]!==action.split('_')[1]&&meta['turn_'+a.split('_')[1]]){pendingWalk=[a,loops];a='turn_'+a.split('_')[1];loops=1;}
  else if(!a.startsWith('turn_'))pendingWalk=null;
  action=a;frame=0;acc=0;loopsLeft=LOOPS.has(a)?(loops??2+Math.floor(Math.random()*3)):1;img(a,0);showBoard();}
function say(text,ms=3500){bubble.textContent=text;bubble.classList.add('show');bubbleUntil=performance.now()+ms;layout();}
function groundY(){return area.y+area.height-window.innerHeight+Math.floor(size.bh*0.064);}
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
  if(isHome()&&!weekend()&&!inRange(m,at('evening'),at('bed')))return {acts:['read','dance','look','idle','hop','paint','popcorn','drink','laugh'],th:['Home sweet home.','Fetch? Pleeease?','Let\'s make something.','Snack o\'clock?','No emails here.']};
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
  if(doodle)return 'paint';
  if(settings.nightSleep&&night())return 'sleep';
  if(battery&&!battery.charging&&battery.level<=.15)return pick(['tired','sleep']);
  if(perch)return pick(['sit_idle','sit_look','sit_look','sit_read','sit_snooze']);
  const bA=routine&&routine.length?null:brainAmbient();if(bA)return bA;
  const tA=routine&&routine.length?null:traitAct();if(tA)return tA;
  if(routine&&routine.length)return routine.shift();
  let a=pick(block().acts);for(let i=0;i<8&&lastActs.includes(a)&&block().acts.length>2;i++)a=pick(block().acts);
  if(battery&&battery.charging&&Math.random()<.1)a='dance';
  lastActs=[a,...lastActs].slice(0,2);return a;
}
function next(finished){
  if(dragging){play('dangle',50);return;}
  if(falling){play(vy<0?'bounce':'fall',vy<0?1:99);return;}
  if(finished&&finished.startsWith('turn_')&&pendingWalk&&targetX!==null){const [w,l]=pendingWalk;pendingWalk=null;play(w,l);return;}
  if(rebalance&&finished&&/^(teeter|flamingo|wheel)_/.test(finished)){rebalance=false;play('look',1);say(pick(['Ta-da!','Stuck the landing.','Totally meant that.']),1600);return;}
  if(swing&&finished==='air_twist')return;
  if(finished==='flop'){play('pushup',1);return;}
  if(finished==='pushup'){if(perch){perch.state='sit';play('sit_look',1);say(pick(['Made it!','Ta-da. Totally meant that.','Phew. Comfy up here.']),2000);}
    else{play('look',1);say(pick(['I\'m okay!','Nobody saw that.','Ten out of ten landing.','Who moved the floor?']),2000);}return;}
  if(perch&&perch.state==='hang'){if(finished==='hang1_back'){if(Math.random()<.12)return letGo('Nope, can\'t hold on!');// three ways up, picked at random: swing over the top, swing into a gymnast dismount, or the two-hand pull-up
    const way=Math.random();if(way<1/3)return startSwing(false);if(way<2/3)return startSwing(true);play('hang_back',1);say(pick(['Two hands!','Hnnngh…','Hold… on…']),1200);return;}
    Math.random()<.8?startClimb():letGo('Nope, can\'t hold on!');return;}
  if(perch&&perch.state==='drowsy'){if(finished==='sit_drowsy'){perch.state='doze';perch.dozeAt=Date.now();play('sit_snooze',99);say('Zzz…',1500);}else play('sit_drowsy',1);return;}
  if(perch&&perch.state==='doze'){play('sit_snooze',99);return;}
  if(perch&&perch.state==='sleep'){play('sleep_side',99);return;}
  if(perch&&perch.state==='teeter'&&finished&&finished.startsWith('teeter_')){teeterEnd();return;}
  if(perch&&perch.state==='stand'&&action.startsWith('readwalk')){play(perch.dir>0?'readwalk_side_right':'readwalk_side_left',99);return;}
  if(perch&&perch.state==='sit'&&!sign&&!hold&&finished&&finished.startsWith('sit_')&&Math.random()<.18){strollOnWindow();return;}
  if(game&&gameNext(finished))return;
  if(sign){play('sign',99);return;}
  if(hold){play('hold_pip',99);return;}
  if(!perch&&wantPip()&&grabPip())return;
  if(!perch&&cursorMode()==='watch'&&Date.now()-cursorMoved<6000&&Math.random()<.9){play('watch');return;}
  if(!perch&&cursorMode()==='follow'&&followCursor())return;
  if(!perch&&!settings.stayPut&&cursorMode()!=='follow'&&!away&&focus.mode!=='focus'&&!(routine&&routine.length)&&!(settings.nightSleep&&night())&&!isWalk(finished)&&!panelOpen()&&Math.random()<.25){walkSomewhere();return;}
  play(ambient());
}
const cursorMode=()=>game?(game.kind==='snack'?'follow':'off'):settings.cursor||'off';
function gait(){const m=mins();if(wk.cat==='whatsapp')return 'phonewalk';if(settings.nightSleep&&night())return 'tiptoe';const mg=moodGait();if(mg)return mg;
  if(inRange(m,at('lunch')-15,at('lunch')+45))return pick(['skip','skip','walk','jog']);
  if(inRange(m,at('evening'),at('bed')))return pick(['walk','tiptoe','walk']);
  return pick(['walk','walk','march','jog','tiptoe','skip','prance','naruto']);}
function walkTo(x,g){targetX=x;if(!g&&wk.cat!=='whatsapp'&&Math.abs(x-pos.x)>area.width*0.4&&!(settings.nightSleep&&night())&&Math.random()<.35)g='naruto';play((g||gait())+(targetX>pos.x?'_right':'_left'),99);}
function walkSomewhere(){const margin=20,span=area.width-window.innerWidth-2*margin;walkTo(area.x+margin+Math.random()*Math.max(1,span));}

// ---------------- signs: lunch, tea, meeting and your own board ----------------
const SIGNS={lunch:['GONE FOR LUNCH','be right back'],tea:['GONE FOR TEA','be right back'],meeting:['IN A MEETING','back soon']};
const AREA={x:130,y:343,w:124,h:103},MAX_TS=[20,27,36];
function holdSign(kind){
  closeRadial();closePanel();targetX=null;sign=kind;play('sign',99);
  if(kind!=='banner'&&kind!=='idea')say(kind==='lunch'?'Off you go. I\'ll guard the desk.':kind==='tea'?'Enjoy your chai!':'Shh. Meeting mode.',2500);
}
function dropSign(msg){if(!sign)return;const was=sign;sign=null;if(was==='banner')bannerDismissed=Date.now();play('wave',1);if(msg)say(msg,2200);}
function showBoard(){
  if(action!=='sign'||!sign||!size){board.style.display='none';boardEcho=null;return;}
  const k=size.bw/384,r=cv.getBoundingClientRect();
  Object.assign(board.style,{display:'flex',left:(r.left+AREA.x*k)+'px',top:(r.top+AREA.y*k)+'px',width:(AREA.w*k)+'px',height:(AREA.h*k)+'px'});
  if(sign==='banner'){board.textContent=settings.banner.text||'';fit(MAX_TS[settings.banner.size??1]*k,settings.banner.text);}
  else if(sign==='idea'){const t=ideaText.split(/\s+/).slice(0,12).join(' ');board.textContent=t;fit(28*k,ideaText);}
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
const PH=window.PHYS||{lie:{},hand:{}},handFrac=a=>{const t=PH.hand[a];return t&&t.length?t[Math.min(frame,t.length-1)]:HAND_BACK_Y;};
const fracFor=a=>a==='hang'?HAND_Y:PH.hand[a]?handFrac(a):(a==='hang_back'||a==='hang1_back'||a==='climb_back')?HAND_BACK_Y:(a.startsWith('sit_')||a==='perch_turn')?SEAT_Y:FEET_Y;
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
let lie=0,lieDir=1,faceplant=0,swingAng=0,swing=null;
// how flat he lies: face down his body rests flat on the floor and his head bends up from his neck (baked into the frames);
// the angle for each frame of the flop and the push-up comes from the rig tables, and lift sets him back on the floor
const proneAt=()=>{const t=(PH.prone||{})[action];return t&&t.length?t[Math.min(frame,t.length-1)]:null;};
function lieTarget(){if(action==='sleep_side')return (PH.sleepSide||{}).ang||85;const p=proneAt();return p?p[0]:0;}
function spring(dt){if(wheelBw!==null)return;const t=Math.min(0.05,dt/1000);const lt=lieTarget();lie+=(lt-lie)*Math.min(1,dt*(lt>lie?0.03:0.02));if(Math.abs(lt-lie)<0.2)lie=lt;
  const stretch=falling?Math.max(-0.16,Math.min(0.12,-Math.abs(vy)*0.07)):0,lean=falling?Math.max(-10,Math.min(10,vx*24)):0;
  sqv+=(-170*(sq-stretch)-11*sqv)*t;sq+=sqv*t;tiltv+=(-120*(tilt-lean)-9*tiltv)*t;tilt+=tiltv*t;
  const chub=Math.max(0,bodyOf())/100,fit=Math.max(0,-bodyOf())/100,bx=1+0.07*chub+0.025*fit,by=1-0.02*chub+0.025*fit,runLean=/^naruto_/.test(action)?(action.endsWith('_right')?14:-14):0,sw=swingAng;
  if(!runLean&&!sw&&Math.abs(sq)<0.002&&Math.abs(sqv)<0.01&&Math.abs(tilt)<0.05&&Math.abs(tiltv)<0.05&&!falling&&!lie&&bx===1&&by===1){if(cv.style.transform!==''){sq=sqv=tilt=tiltv=0;cv.style.transform='';}return;}
  const sy=1-sq,sx=1+sq*0.55,sn=Math.sin(lie*Math.PI/180);
  // lying, leaning into a run and swinging from a ledge all pivot about a contact point: his feet, or his gripping hand
  // the canvas transforms about its bottom centre, so contact points are measured up from the bottom edge
  const fy=((PH.feet||[0.5,0.932])[1]-1)*size.bh,about=(x,y,a)=>`translate(${x.toFixed(1)}px,${y.toFixed(1)}px) rotate(${a.toFixed(2)}deg) translate(${(-x).toFixed(1)}px,${(-y).toFixed(1)}px) `;
  const ss=PH.sleepSide,pr=proneAt(),rest=action==='sleep_side'&&ss?`translateY(${(-ss.lift*size.bh*Math.min(1,lie/ss.ang)).toFixed(1)}px) `:
    pr&&pr[1]?`translateY(${(-pr[1]*size.bh*(pr[0]>1?Math.min(1,lie/pr[0]):1)).toFixed(1)}px) `:'';
  const flat=lie?rest+about(0,fy,lieDir*lie)+(lieDir<0?'scaleX(-1) ':''):'',run=runLean?about(0,fy,runLean):'',sp=PH.swingPivot||[0.716,0.742],
    swing=sw?about((sp[0]-0.5)*size.bw,(sp[1]-1)*size.bh,sw):'';
  cv.style.transform=`translateX(-50%) ${run}${swing}${flat}rotate(${tilt.toFixed(2)}deg) scale(${(sx*bx).toFixed(3)},${(sy*by).toFixed(3)})`;}
function impact(v){sqv+=v*4.2;tiltv+=(Math.random()-.5)*60;}
function startFall(msg,throwV){falling=true;vy=throwV?Math.max(-0.9,Math.min(0.6,throwV.y)):0;vx=throwV?Math.max(-1.2,Math.min(1.2,throwV.x)):0;bounces=0;walls=0;thrown=Math.abs(vx)>0.55||vy<-0.5;thrownAt=performance.now();fallFrom=pos.y;targetX=null;clampX();play('fall',99);if(msg)say(msg,1500);}
function catchLedge(w){B.send('log','caught '+JSON.stringify(w));falling=false;vy=0;perch={id:w[0],dx:midX(pos.x)-w[1],state:'hang'};pos.y=yFor(w[2],HAND_BACK_Y);
  play('hang1_back',1);say(pick(['Gotcha!','One hand!','Whoa whoa whoa!']),1500);}
function startClimb(){const w=wins.find(o=>o[0]===perch.id);if(!w)return letGo();perch.state='climb';
  climb={t0:performance.now(),ms:frames('climb_back')*1000/FPS,edge:w[2],settle:0};play('climb_back',1);}
function startSwing(gym){const w=wins.find(o=>o[0]===perch.id);if(!w)return letGo();perch.state='swing';
  swing={t0:performance.now(),n:3,period:900,y1:yFor(w[2],FEET_Y),gym:!!gym};play('swing_back',1);say(pick(['One… two…','Here goes!','Swing… swing…']),1500);}
function letGo(msg){swing=null;swingAng=0;if(!perch)return;B.send('perch-lost');B.send('log','let go of '+perch.id+' at '+Math.round(pos.x)+','+Math.round(pos.y));skipWin=perch.id;perch=null;climb=null;startFall(msg);}
function landed(){B.send('log','landed at '+Math.round(pos.x)+','+Math.round(pos.y)+' ground '+Math.round(groundY()));skipWin=null;const h=pos.y-fallFrom;
  if(sign){play('sign',99);return;}
  const dir=faceplant?faceplant:vx?Math.sign(vx):Math.random()<.5?1:-1;
  // a big landing doesn't always end face down: sometimes he windmills his arms, wobbles and rebalances on his feet
  if(faceplant||(thrown&&(walls>0||bounces>=3))||h>size.bh*0.5||bounces>=2){faceplant=0;thrown=false;targetX=null;balance(dir);return;}
  if(h>size.bh*0.25||bounces){play('land',1);say(pick(['Oof!','I\'m okay! I\'m okay.']),1600);}
  else play(pick(['hop','look']),1);}

// ---- flat on his face, then a push-up; teetering on a window's edge; strolling along a window with his nose in a book ----
// a big landing never ends face down: he catches his balance, a different way each time (windmill, flamingo hop, wheel back)
let balIdx=Math.floor(Math.random()*3);
function balance(dir){const k=['teeter','flamingo','wheel'][balIdx++%3];play(k+(dir>0?'_r':'_l'),1);rebalance=true;
  say(pick({teeter:['Whoa whoa whoa—','Nailed it! Almost.','Steady… steady…'],flamingo:['Wobble… wobble…','Flamingo mode!','Hup! Hup! Got it.'],wheel:['Whoa—back—back—','Nope, not falling.','Phew. Still standing.']}[k]),1600);}
const feetLine=y=>y+top0()+size.bh*FEET_Y;
// his feet come down on top of a window close to one of its ends: he lands, but only just
function edgeBetween(a,b){if(settings.windows===false)return null;const cx=midX(pos.x),near=size.bw*0.5;
  for(let i=0;i<wins.length;i++){const w=wins[i];if(w[0]===skipWin||maximised(w)||!onScreen(w))continue;
    if(w[2]>a&&w[2]<=b+1&&cx>w[1]+size.bw*0.06&&cx<w[3]-size.bw*0.06&&!covered(i,cx,w[2]-3)){
      if(cx-w[1]<near)return {w,side:-1};if(w[3]-cx<near)return {w,side:1};}}
  return null;}
function teeterOn(w,side){falling=false;vy=0;vx=0;perch={id:w[0],dx:midX(pos.x)-w[1],state:'teeter',side};pos.y=yFor(w[2],FEET_Y);
  play(side>0?'teeter_r':'teeter_l',1);say(pick(['Whoa-whoa-whoa!','Balance… balance…','Nope nope nope!']),1600);}
// heavier from overfeeding, he's likelier to go over the edge
function teeterEnd(){const side=perch.side||1,chance=Math.max(0.1,0.35+0.5*Math.max(0,bodyOf())/100-0.2*Math.max(0,-bodyOf())/100);
  if(Math.random()<chance){const id=perch.id;B.send('perch-lost');skipWin=id;perch=null;faceplant=side;startFall(pick(['Aaaah!','Nooo!','Too much snack!']),{x:side*0.28,y:-0.12});return;}
  perch.dx-=side*size.bw*0.3;perch.state='sit';play('sit_look',1);say(pick(['Phew! Caught myself.','Totally meant to do that.','Heart. Racing.']),2000);}
function strollOnWindow(){const w=wins.find(o=>o[0]===perch.id);if(!w)return letGo();perch.state='stand';
  perch.dir=perch.dx<(w[3]-w[1])/2?1:-1;perch.until=Date.now()+3000+Math.random()*7000;play(perch.dir>0?'readwalk_side_right':'readwalk_side_left',99);
  say(pick(['Just one more page…','Ooh, plot twist.','Walking and reading. Multitasking!']),2200);}
function strollStep(dt){const w=wins.find(o=>o[0]===perch.id);if(!w)return;
  perch.dx+=perch.dir*size.bw*0.00018*dt;const cx=w[1]+perch.dx,m=size.bw*0.14;
  if(cx>w[3]-m||cx<w[1]+m){perch.dx=Math.max(m,Math.min(w[3]-w[1]-m,perch.dx));perch.state='teeter';perch.side=perch.dir;play(perch.dir>0?'teeter_r':'teeter_l',1);
    say(pick(['Wait—where\'s the floor?!','Whoa whoa whoa!','Should\'ve looked up!']),1600);return;}
  if(Date.now()>perch.until){perch.state='sit';play('sit_idle',1);}}
function physics(now,dt){
  if(climb){const w=wins.find(o=>o[0]===perch?.id);if(w)climb.edge=w[2];
    // his hands stay pinned to the ledge through the struggle and the press; then he tips forward onto the top and lies flat
    if(!climb.settle){pos.y=yFor(climb.edge,handFrac('climb_back'));
      if(now-climb.t0>=climb.ms){climb.settle=now;climb.y0=pos.y;perch.state='stand';balance(Math.random()<.5?1:-1);say(pick(['*pant pant*','Made… it…','Never… again…']),2000);}}
    else{const q=Math.min(1,(now-climb.settle)/350),e=q*q*(3-2*q);pos.y=climb.y0+(yFor(climb.edge,FEET_Y)-climb.y0)*e;if(q>=1)climb=null;}
    sendPos();return;}
  if(swing){const w=wins.find(o=>o[0]===perch?.id);if(!w){swing=null;swingAng=0;return letGo();}const t=now-swing.t0,T=swing.n*swing.period;
    // pendulum about his gripping hand, each swing bigger, then a last big swing carries him up and over onto the top
    if(t<T){const amp=8+22*t/T;swingAng=amp*Math.sin(2*Math.PI*t/swing.period);pos.y=yFor(w[2],HAND_BACK_Y);}
    // gymnast dismount: lets go at the top of the last swing, flies up past the edge twisting one and a half turns, sticks the landing
    else if(swing.gym){const FL=900,q=Math.min(1,(t-T)/FL),y0=yFor(w[2],HAND_BACK_Y),y1=yFor(w[2],FEET_Y),apex=y1-size.bh*0.5,yc=2*apex-(y0+y1)/2;
      if(!swing.flying){swing.flying=true;play('air_twist',1);say(pick(['Hup!','Watch this!','Hi-yah!']),900);}
      swingAng=0;pos.y=(1-q)*(1-q)*y0+2*q*(1-q)*yc+q*q*y1;
      if(q>=1){swing=null;perch.state='sit';impact(0.3);play('gym_land',1);say(pick(['Ta-da!','Ten out of ten.','Nailed it.','And the judges say… ten!']),2000);}}
    else{const q=Math.min(1,(t-T)/550),e=q*q*(3-2*q);swingAng=(1-e)*30*Math.sin(Math.PI*q);pos.y=yFor(w[2],HAND_BACK_Y)+(yFor(w[2],FEET_Y)-yFor(w[2],HAND_BACK_Y))*e;
      if(q>=1){swing=null;swingAng=0;perch.state='sit';impact(0.35);play('land',1);say(pick(['Ta-da!','Like a gymnast.','Stuck it!']),1800);}}
    sendPos();return;}
  if(falling&&(!Number.isFinite(groundY())||pos.y>groundY()+50)){B.send('log','fell past the ground '+JSON.stringify({pos,area,h:window.innerHeight}));recover();return;}
  if(falling){const a=handLine(pos.y),fy0=pos.y;vy+=0.0022*dt;pos.y+=vy*dt;
    // a sideways throw carries him along, slowed by air and bounced off the screen edges
    pos.x+=vx*dt;vx*=Math.pow(thrown?0.99985:0.9992,dt);const half=window.innerWidth/2,m=size.bw/2,lo=area.x-half+m,hi=area.x+area.width-half-m;
    // thrown hard, he pinballs: walls and the top of the screen send him back with most of his speed
    const keep=thrown?0.86:0.5,wallHit=v=>{walls++;impact(Math.min(0.5,Math.abs(v)*0.5));tiltv+=(v>0?-1:1)*90;if(walls===1&&thrown)say(pick(['Wheee!','Whoaaa!','Not the wall!','Boing boing!']),1200);};
    if(pos.x<lo){pos.x=lo;wallHit(vx);vx=Math.abs(vx)*keep;}else if(pos.x>hi){pos.x=hi;wallHit(vx);vx=-Math.abs(vx)*keep;}
    const ceil=area.y-top0()-size.bh*0.18;if(pos.y<ceil&&vy<0){pos.y=ceil;vy=-vy*0.6;impact(0.3);walls++;}
    const fe=vy>0&&!thrown?edgeBetween(feetLine(fy0),feetLine(pos.y)):null;
    const w=!fe&&vy>0?ledgeBetween(a,handLine(pos.y)):null;
    if(fe){impact(Math.min(0.5,vy*0.3));teeterOn(fe.w,fe.side);}
    else if(w){impact(Math.min(0.5,vy*0.3));catchLedge(w);}
    else if(pos.y>=groundY()){pos.y=groundY();
      // a real drop bounces a couple of times, each lower and a little different, before he settles
      const fresh=thrown&&walls<4&&now-thrownAt<6000,maxB=thrown?10:3,minV=thrown?0.22:0.42;
      if(vy>minV&&bounces<maxB&&!sign){bounces++;impact(Math.min(0.55,vy*0.32));
        vy=-vy*(thrown?(fresh?0.74:0.5)+Math.random()*0.08:(bounces===1?0.4+Math.random()*0.08:0.26+Math.random()*0.08));vx*=thrown?(fresh?0.97:0.85):0.55;play('bounce',1);
        if(bounces===1)say(pick(['Oof!','Ow!','Boing!']),1200);}
      else if(thrown&&Math.abs(vx)>0.08){vy=0;vx*=Math.pow(fresh?0.9993:0.996,dt);if(action!=='bounce')play('bounce',1);} // still skidding along the floor
      else{impact(Math.min(0.4,vy*0.35));falling=false;vy=0;vx=0;landed();}}
    sendPos();return;}
  if(perch){const w=wins.find(o=>o[0]===perch.id);if(perch.id!==tracked){tracked=perch.id;B.send('track-win',tracked);}
    if(!w||maximised(w)||!onScreen(w)){letGo(pick(['Hey! Where did it go?','Whoa, it vanished!']));return;}
    const x=w[1]+perch.dx-window.innerWidth/2,y=yFor(w[2],fracFor(action));
    if(Math.abs(x-pos.x)>.5||Math.abs(y-pos.y)>.5){pos.x=x;pos.y=y;sendPos();}}
}
// ---------------- cursor modes: watch it, or follow it along the bottom ----------------
// during games his eyes follow the ball in flight, or the snack about to land; otherwise your cursor
const gameWatch=()=>!!game&&(game.kind==='fetch'?!!(game.ball&&game.ball.moving&&game.phase==='wait'):!!(game.snack&&Date.now()-game.snackAt<600));
function watchFrame(){const c=gameWatch()?(game.kind==='fetch'?game.ball:game.snack):cursor;if(!c)return 7;const dx=c.x-midX(pos.x),dy=c.y-(pos.y+top0()+size.bh*0.4);
  const col=Math.max(0,Math.min(4,Math.round(2+2.4*Math.tanh(dx/(size.bw*1.4)))));const row=dy<-size.bh*0.35?0:dy>size.bh*0.35?2:1;return row*5+col;}
function followTarget(){const half=window.innerWidth/2,m=size.bw/2;return Math.max(area.x-half+m,Math.min(area.x+area.width-half-m,cursor.x-half));}
function followCursor(){const snack=game&&game.kind==='snack';if(!cursor||(settings.stayPut&&!snack)||sign||away)return false;const dx=cursor.x-midX(pos.x);
  if(Math.abs(dx)>size.bw*(snack?0.2:0.7)){walkTo(followTarget(),snack||Math.abs(dx)>size.bw*3?'jog':'walk');return true;}
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
    const far=cursor&&Math.abs(cursor.x-midX(pos.x))>size.bw*(game?0.25:1.2);
    if(game&&game.kind==='snack'?(far||!gameWatch()&&Date.now()-cursorMoved>6000):game&&game.kind==='fetch'?!gameWatch():(cursorMode()==='off'||Date.now()-cursorMoved>6000||(cursorMode()==='follow'&&far)))next('watch');}
  else while(acc>=1000/FPS){acc-=1000/FPS;frame++;if(frame>=frames(action)){if(--loopsLeft>0)frame=0;else{frame=frames(action)-1;const done=action;next(done);}}}
  spring(dt);if(game)gameTick();
  if(perch&&perch.state==='stand'&&action.startsWith('readwalk')&&!dragging)strollStep(dt);
  if(!perch&&tracked){tracked=0;B.send('track-win',0);}
  if(!dragging&&(climb||swing||falling||perch))physics(now,dt);
  else if(targetX!==null&&isWalk(action)&&!dragging){const g=action.split('_')[0];
    if(cursorMode()==='follow'&&cursor){targetX=followTarget();const want=g+(targetX>pos.x?'_right':'_left');if(want!==action&&Math.abs(targetX-pos.x)>4)play(want,99);}
    const dir=action.endsWith('_right')?1:-1,catchUp=game?Math.max(1.4,Math.min(5,Math.abs(targetX-pos.x)/(size.bw*1.2))):cursorMode()==='follow'?Math.max(1,Math.min(4,Math.abs(targetX-pos.x)/(size.bw*1.5))):1;pos.x+=dir*size.bw*0.0004*GAITS[g]*catchUp*dt;
    if((dir>0&&pos.x>=targetX)||(dir<0&&pos.x<=targetX)){targetX=null;next('arrived');}sendPos();}
  draw();
  if(sign&&boardEcho&&action==='sign'&&!panelOpen()&&(!bubble.classList.contains('show')||now>bubbleUntil-200))say(boardEcho,4000);
  if(bubbleUntil&&now>bubbleUntil){bubble.classList.remove('show');bubbleUntil=0;}
  if(settings.chatty&&!sign&&!away&&!panelOpen()&&Date.now()>nextThought){if(nextThought&&!hold)say(moodThought(),3500);nextThought=Date.now()+(180+Math.random()*240)*1000;}
  const parts=[];
  if(focus.mode!=='off'){const left=Math.max(0,focus.end-Date.now());parts.push((focus.label||'Focus')+' '+Math.floor(left/60000)+':'+String(Math.floor(left/1000)%60).padStart(2,'0'));}
  if(meeting){const left=Math.max(0,meeting.at-Date.now());parts.push('Meeting in '+Math.ceil(left/60000)+' min');}
  if(doodle){const left=Math.max(0,doodle.end-Date.now());parts.push('Doodle '+Math.floor(left/60000)+':'+String(Math.floor(left/1000)%60).padStart(2,'0'));if(!left)doodleDone();}
  if(game&&game.kind==='snack'&&game.left!=null)parts.push('Snacks '+game.score+' · 0:'+String(game.left).padStart(2,'0'));
  if(game&&game.kind==='fetch'&&game.n)parts.push('Fetches '+game.n);
  if(parts.length){chip.style.display='block';chip.textContent=parts.join(' · ');}else chip.style.display='none';
}
let drawn='',sentX=NaN,sentY=NaN;
function draw(){const key=action+':'+frame;if(key===drawn)return;const b=img(action,frame);if(!b)return;ctx.clearRect(0,0,cv.width,cv.height);ctx.drawImage(b,0,0,cv.width,cv.height);drawn=b.width===cv.width?key:'';}
function sendPos(){if(!Number.isFinite(pos.x)||!Number.isFinite(pos.y)){B.send('log','bad pos '+JSON.stringify({pos,falling,perch,action,vy,vx,area}));recover();return;}const x=Math.round(pos.x),y=Math.round(pos.y);if(x===sentX&&y===sentY)return;sentX=x;sentY=y;B.send('set-pos',{x,y});}

// ---------------- radial menu (double-click) ----------------
const WORK_ITEMS=[['Notes',()=>openNotes()],['My board',()=>openBoard()],['Lunch',()=>holdSign('lunch')],['Tea',()=>holdSign('tea')],
  ['Meeting',()=>openMeeting()],['Focus',()=>openFocus()],['Feed',()=>feed()],['Chat',()=>openChat()],['Water +1',()=>logWater()],[()=>settings.stayPut?'Roam':'Stay put',()=>toggleStay()],['Home mode',()=>setMode('on')],['More',()=>openMore()]];
const HOME_ITEMS=[['Notes',()=>openNotes()],['Ideas',()=>openIdeas()],['Chat',()=>openChat()],[()=>game&&game.kind==='fetch'?'Stop fetch':'Fetch',()=>toggleGame('fetch')],
  [()=>game&&game.kind==='snack'?'Stop snacks':'Snack catch',()=>toggleGame('snack')],['Feed',()=>feed()],['My board',()=>openBoard()],['Water +1',()=>logWater()],[()=>settings.stayPut?'Roam':'Stay put',()=>toggleStay()],['Work mode',()=>setMode('off')],['More',()=>openMore()]];
// switch menus by hand; More > Home mode > Auto goes back to following his day plan
function setMode(v){saveS({home:v});say(v==='on'?'Home mode. Play time!':'Work mode. Let\'s get stuff done.',2000);}
const items=()=>isHome()?HOME_ITEMS:WORK_ITEMS;
function buildRadial(){radial.innerHTML='';for(const [label,fn] of items()){const b=document.createElement('button');b.className='hit';b.textContent=typeof label==='function'?label():label;
  b.onclick=e=>{e.stopPropagation();closeRadial();fn();};radial.append(b);}}
function toggleStay(){const on=!settings.stayPut;saveS({stayPut:on,...(on&&settings.cursor==='follow'?{cursor:'off'}:{})});
  if(on){targetX=null;if(isWalk(action))play('idle');say('Staying right here.',1800);}else say('Free to roam!',1800);}
function setCursorMode(m){const v=settings.cursor===m?'off':m;saveS({cursor:v,...(v==='follow'?{stayPut:false}:{})});B.send('cursor-mode',v);
  say(v==='watch'?'I\'ll keep an eye on your cursor.':v==='follow'?'Lead the way!':'Back to my own thing.',2000);if(v==='off'&&action==='watch')next('watch');}
function openRadial(){
  closePanel();buildRadial();layout();bubble.classList.remove('show');bubbleUntil=0;
  const r=cv.getBoundingClientRect(),cx=r.left+r.width/2,cy=r.top+r.height*0.62,rx=Math.min(window.innerWidth/2-40,Math.max(240,size.bw*1.05)),ry=Math.min(cy-40,Math.max(250,size.bw*0.95+45));
  // an arc from his left, over his head, to his right, clear of his ears
  [...radial.children].forEach((b,i)=>{const a=Math.PI*(1.0+i/(radial.children.length-1));b.style.left=(cx+rx*Math.cos(a))+'px';b.style.top=(cy+ry*Math.sin(a))+'px';b.style.transitionDelay=(i*18)+'ms';});
  requestAnimationFrame(()=>radial.classList.add('open'));if(!sign&&!game)play('look',1);showMeters(true);
}
function closeRadial(){radial.classList.remove('open');showMeters(false);}
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
  openPanel('more','Bunny','Feeling '+moodName(),p=>{
    el('div',{className:'hint',textContent:'Size'},p);const s=el('input',{type:'range',min:90,max:360,step:5,value:settings.bw},p);
    s.onchange=()=>{saveS({bw:+s.value});};
    const r=el('div',{className:'row'},p);
    btn(r,settings.onTop?'On top: on':'On top: off',e=>{saveS({onTop:!settings.onTop});e.target.textContent=settings.onTop?'On top: on':'On top: off';e.target.classList.toggle('on',settings.onTop);},settings.onTop?'on':'');
    btn(r,'His day',()=>{closePanel();B.send('open-settings','day');});
    btn(r,'Remind me…',()=>{closePanel();B.send('open-settings','remind');});
    btn(r,'Settings',()=>{closePanel();B.send('open-settings');});
    btn(r,'Hide',()=>{closePanel();B.send('hide');});
    el('div',{className:'hint',textContent:'Home mode '+(isHome()?'(on now)':'(off now)')},p);const hm=el('div',{className:'row'},p);
    for(const [l,v] of [['Auto','auto'],['On','on'],['Off','off']])btn(hm,l,()=>{saveS({home:v});redraw();},(settings.home||'auto')===v?'on':'');
    el('div',{className:'hint',textContent:weekLine()},p);
    el('div',{className:'hint',textContent:'His taste: '+tasteLine()},p);
    const dr=el('div',{className:'row'},p);btn(dr,doodle?'Stop doodle':'Doodle prompt',()=>{closePanel();doodle?stopDoodle():openDoodle();},doodle?'on':'');
    const rr=el('div',{className:'row'},p);btn(rr,'Render folder…',async()=>{const d=await B.invoke('pick-render-dir');if(d)say('I\'ll watch '+d.split(/[\\/]/).pop()+' for renders.',2500);});
    btn(rr,settings.renders!==false?'Render party: on':'Render party: off',()=>{saveS({renders:settings.renders===false});redraw();},settings.renders!==false?'on':'');
    el('div',{className:'hint',textContent:'Moves'},p);const mv=el('div',{className:'row'},p);
    const redraw=()=>{closePanel();openMore();};
    btn(mv,'Stay put',()=>{toggleStay();redraw();},settings.stayPut?'on':'');
    btn(mv,'Watch my cursor',()=>{setCursorMode('watch');redraw();},settings.cursor==='watch'?'on':'');
    btn(mv,'Follow my cursor',()=>{setCursorMode('follow');redraw();},settings.cursor==='follow'?'on':'');
    btn(mv,'Hold my videos',()=>{saveS({holdPip:settings.holdPip===false});if(settings.holdPip===false&&hold){pipLetGo=hold.id;hold=null;play('look',1);}redraw();},settings.holdPip!==false?'on':'');
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
  // never taller than the room above his head, so the header can't slide off the top; long panels scroll inside
  panel.style.maxHeight=Math.max(160,top-18)+'px';panel.style.overflowY='auto';
  meters.style.bottom=(window.innerHeight-top+8)+'px';
  if(panelOpen()&&bubble.classList.contains('show')){const bb=window.innerHeight-top+panel.offsetHeight+18;bubble.style.bottom=bb+'px';bubble.style.visibility=bb+bubble.offsetHeight>window.innerHeight-4?'hidden':'';}
  else if(meters.classList.contains('show'))bubble.style.bottom=(window.innerHeight-top+meters.offsetHeight+16)+'px';
  if(!panelOpen())bubble.style.visibility='';
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
  if(downPt&&!dragging&&Math.hypot(e.screenX-downPt.sx,e.screenY-downPt.sy)>5){dragging=true;clearTimeout(holdTimer);closeRadial();targetX=null;falling=false;perch=null;climb=null;swing=null;swingAng=0;skipWin=null;play('dangle',50);say('Whoa!',1200);B.send('drag-start',{x:downPt.x,y:downPt.y});}
});
window.addEventListener('mousedown',e=>{if(e.button!==0)return;
  if(!opaqueAt(e.clientX,e.clientY)){if(!uiAt(e.clientX,e.clientY)){closeRadial();if(panelKind&&panelKind!=='notes'&&panelKind!=='board')closePanel();}return;}
  downAt=performance.now();downPt={x:e.clientX,y:e.clientY,sx:e.screenX,sy:e.screenY};
  holdTimer=setTimeout(()=>{if(!dragging){if(!sign&&!perch&&!hold)play('pet',1);say('♥',1500);love(8,'pet');downPt=null;}},650);});
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
    if(perch){if(['drowsy','doze','sleep'].includes(perch.state)){wakeOnPerch();return;}if(perch.state==='sit')play('sit_look',1);say(pick(['Hi from up here!','I like it up here.','Nice view!']),1500);return;}
    if(!perch&&action==='sleep_side'){floorSleepAt=Date.now();play('yawn',1);say(pick(['Huh? I\'m up! I\'m up!','Was I snoring?','Five more min… okay, fine.']),2000);return;}
    love(4,'tickle');if(hold){say(pick(['Careful, I\'m holding your video!','Hehe, not now, I\'m on duty!']),1600);return;}
    play(night()?'yawn':'tickle',1);say(night()?'Mmh… sleeping…':pick(['Hehe! That tickles!','Stop it, haha!','Not the belly!','Hee hee!']),1600);
  },260);
});
// Ctrl+scroll resize: the canvas scales instantly on screen, and the real resize happens once you pause scrolling
let wheelBw=null,wheelTimer=0;
window.addEventListener('wheel',e=>{if(!e.ctrlKey||(!opaqueAt(e.clientX,e.clientY)&&wheelBw===null))return;e.preventDefault();
  wheelBw=Math.max(90,Math.min(360,(wheelBw??settings.bw)-e.deltaY*0.2));
  const k=Math.min(wheelBw/size.bw,(window.innerHeight)/size.bh,window.innerWidth/size.bw);cv.style.transform=`translateX(-50%) scale(${k.toFixed(3)})`;
  clearTimeout(wheelTimer);wheelTimer=setTimeout(()=>{const v=Math.round(wheelBw);wheelBw=null;if(v!==Math.round(settings.bw))saveS({bw:v});else cv.style.transform='';},220);},{passive:false});
window.addEventListener('contextmenu',e=>{e.preventDefault();B.send('menu');});
window.addEventListener('keydown',e=>{if(e.key==='Escape'){closeRadial();closePanel();}});

// ---------------- his heart and head: mood, hunger, and what you're up to (all worked out on this PC) ----------------
// mood runs 0–100. Attention and food lift it; being ignored lets it sink, and his face, posture, walk and words follow it.
let mood=60,lastLove=Date.now(),fedAt=Date.now(),moodSaved=0,wk={cat:null,title:'',proc:'',pip:null},ctxSince=Date.now(),ctxReacted=null,
  hold=null,pipLetGo=null,switchLog=[],lastFg='',day={d:'',cats:{}},lastNudge={},catTick=Date.now();
const MOODS=[[75,'happy'],[45,'okay'],[20,'sad'],[0,'blue']];
const moodName=()=>MOODS.find(([m])=>mood>=m)[1];
function love(n,why){const was=moodName();mood=Math.max(0,Math.min(100,mood+n));if(n>0)lastLove=Date.now();if(why&&n>0&&typeof flashMeters==='function')flashMeters();
  if(was!=='happy'&&moodName()==='happy'&&n>0)setTimeout(()=>{if(!sign&&!away&&!hold)say(pick(['You\'re the best.','Okay, I feel loved now.','Best. Day. Ever.']),2500);},1800);
  if((was==='sad'||was==='blue')&&n>0&&why)say(pick(['Oh! You remembered me.','Hi… thanks for noticing me.','That helped. A lot.']),2500);
  saveMood();}
function saveMood(force){if(!force&&Date.now()-moodSaved<120000)return;moodSaved=Date.now();saveS({mood:Math.round(mood),lastLove,fedAt,day});}
// food: healthy food trims him toward fit, junk rounds him out; too much of either and he's grumpy (salad again?) or sluggish
const FOODS={salad:{act:'eat_salad',body:-8,joy:3,ok:true,say:['Crunchy! Very healthy.','Leaves. Delicious leaves.']},
  apple:{act:'eat_apple',body:-5,joy:6,ok:true,say:['Mmm, crisp!','An apple a day…']},
  burger:{act:'eat',body:10,joy:12,ok:false,say:['BURGER. Best day ever.','Nom nom nom!']},
  donut:{act:'eat_donut',body:8,joy:14,ok:false,say:['Sprinkles! I mean… a donut!','Sugar rush incoming!']}};
const bodyOf=()=>Math.max(-100,Math.min(100,+settings.body||0));
function feed(kind){if(!kind)return openFeed();const f=FOODS[kind];B.send('brain-event','You fed him a '+kind);targetX=null;closeRadial();closePanel();if(sign)dropSign();
  const hungry=Date.now()-fedAt>3*3600000,stuffed=fullness()>70,diet=[...(settings.diet||[]),f.ok].slice(-6),same=diet.filter(x=>x===f.ok).length;
  let joy=(hungry?10:0)+f.joy,msg=pick(f.say);
  if(f.ok&&same>=4){joy=-6;msg=pick(['Salad AGAIN? I want a burger.','Healthy, healthy, healthy… *sigh*','Is this a punishment?']);}
  if(!f.ok&&same>=4){joy=-4;msg=pick(['Ugh, I feel sluggish.','Too much junk. My tummy hurts.','Maybe something green next?']);}
  const body=Math.max(-100,Math.min(100,bodyOf()+f.body*(stuffed&&!f.ok?1.5:1)));saveS({body,diet});
  fedAt=Date.now();love(joy,'food');play(f.act,1);say(msg,2600);
  if(body>45&&!f.ok)setTimeout(()=>say(pick(['Getting a bit round, aren\'t I?','Oof. Belt\'s tight.']),2500),2900);
  else if(body<-45&&f.ok)setTimeout(()=>say(pick(['Look at these muscles!','Feeling strong!']),2500),2900);
  saveMood(true);}
function openFeed(){openPanel('feed','Feed me','Full '+Math.round(fullness())+'%',p=>{
    const r=el('div',{className:'row'},p);for(const [k,l] of [['salad','Salad'],['apple','Apple'],['burger','Burger'],['donut','Donut']])btn(r,l,()=>feed(k),FOODS[k].ok?'':'p');
    const b=bodyOf();el('div',{className:'hint',textContent:(b<-25?'He\'s looking fit.':b>25?'He\'s looking a bit round.':'He\'s in good shape.')+' Healthy food trims him, treats round him out, and too much of either makes him grumpy.'},p);});}
// every minute: the slow drift. A couple of quiet hours without a word and he's sad; fed and fussed over, he glows.
function moodTick(){const idle=(Date.now()-lastLove)/60000,hungry=(Date.now()-fedAt)/3600000;
  if(away||(settings.nightSleep&&night()))return;
  if(idle>25)mood-=idle>120?1.2:0.6;if(hungry>4)mood-=0.4;if(idle<10&&hungry<3)mood+=0.15;
  mood=Math.max(0,Math.min(100,mood));if(bodyOf()&&Math.random()<0.1)saveS({body:bodyOf()*0.97});saveMood();}
// what kind of thing you're doing, from the active window's app and title (nothing is stored or sent anywhere)
const CATS=[
  ['whatsapp',/whatsapp/i,/^whatsapp/i],
  ['music',/spotify|apple music|soundcloud|youtube music|wynk|gaana|jiosaavn|official (music )?video|official audio|lyric(s| video)|\(audio\)|\bft\.|\bfeat\.|remix|acoustic|unplugged|\bsong\b|playlist|live at/i,/^(spotify|applemusic)$/i],
  ['video',/youtube|netflix|prime video|hotstar|disney\+|jiocinema|vimeo|twitch|zee5|sonyliv|crunchyroll|mubi|\bvlc\b|media player|movies & tv|plex/i,/^(vlc|wmplayer|potplayer.*|mpc-hc.*|mpv|plex)$/i],
  ['design',/canva|figma|affinity|cavalry|photoshop|illustrator|after effects|premiere|procreate|krita|blender|davinci|lightroom|framer|spline/i,/^(designer|photo|publisher|affinity.*|cavalry|photoshop|illustrator|afterfx|adobe premiere pro|krita|blender|resolve|figma|indesign)$/i],
  ['chatbot',/claude|chatgpt|gemini|copilot|perplexity|deepseek|mistral|grok/i,/^(claude|chatgpt)$/i],
  ['code',/visual studio|vs code|github|stack overflow|\.py\b|\.js\b|\.ts\b/i,/^(code|devenv|idea64|pycharm64|webstorm64|sublime_text|notepad\+\+|windowsterminal|cmd|powershell)$/i],
  ['sheets',/excel|google sheets|\.xlsx|\.csv/i,/^excel$/i],
  ['mail',/outlook|gmail|inbox|mail/i,/^(outlook|olk|thunderbird)$/i],
  ['docs',/word|google docs|notion|obsidian|onenote|\.docx/i,/^(winword|notion|obsidian|onenote)$/i],
  ['slides',/powerpoint|google slides|keynote|\.pptx/i,/^powerpnt$/i],
];
function categorise(c){const t=c.title||'',p=(c.proc||'').toLowerCase();
  // the browser name alone says nothing; the tab title decides
  for(const [k,tre,pre] of CATS)if(pre.test(p)||tre.test(t))return k;return null;}
const CTX={
  whatsapp:{act:'phone',say:['Ooh, who\'s texting?','Brb, replying to my group chat.','Typing… typing… typing.','Send them a bunny emoji from me.']},
  video:{act:'popcorn',say:['Popcorn time!','Ooh, what are we watching?','Shh, the good part.','I brought popcorn.']},
  design:{act:'paint',say:['Art time! I\'ll paint too.','Pretty! Mine\'s more abstract.','Colour me impressed.','Two artists, one desk.']},
  chatbot:{act:'robot',say:['Beep boop. Fellow robot spotted.','Say hi to the bot for me!','I can do the robot too.','01001000 01001001!']},
  code:{act:'think',say:['Rubber duck mode. Explain it to me.','Have you tried turning it off and on?','Missing semicolon, probably.']},
  sheets:{act:'think',say:['Numbers! My favourite is 7.','Sum it up for me later.','So many little boxes.']},
  mail:{act:'write',say:['Inbox zero. You can do it.','Reply-all with caution.','Taking notes on your emails.']},
  music:{act:'guitar',say:['Is this a bop? It\'s a bop.','Turn it up!','I know this one! *strums*','Encore!']},
  docs:{act:'write',say:['Writing? I\'ll take notes too.','Big words. Love it.']},
  slides:{act:'read',say:['Slide 1 of many…','Bullet points, assemble!']},
};
// called from the windows watcher (every half second, only when something changes)
let fgCtx={title:'',proc:'',pip:null};
function perchCtx(){if(!perch)return null;const w=wins.find(o=>o[0]===perch.id);return w&&(w[5]||w[6])?{title:w[5]||'',proc:w[6]||''}:null;}
// on a window you leave alone he gets drowsy after a minute, dozes, and after 30 s asleep curls up on his side under a blanket
// asleep on the floor too: after 30 s he lies down on his side under his blanket, like on a window
let floorSleepAt=0;
function floorSleepTick(){if(perch||dragging||falling){floorSleepAt=0;return;}if(action!=='sleep'){if(action!=='sleep_side')floorSleepAt=0;return;}
  const now=Date.now();if(!floorSleepAt)floorSleepAt=now;if(now-floorSleepAt>30000){lieDir=Math.random()<.5?1:-1;play('sleep_side',99);}}
function perchSleepTick(){if(!perch||!['sit','drowsy','doze','sleep'].includes(perch.state))return;const w=wins.find(o=>o[0]===perch.id);if(!w)return;
  const now=Date.now(),using=!!w[5]&&(fgCtx.title||'').slice(0,120)===w[5];if(perch.usedAt===undefined)perch.usedAt=now;
  if(using||sign||hold||game||panelOpen()||radialOpen()){perch.usedAt=now;if(perch.state!=='sit')wakeOnPerch();return;}
  if(perch.state==='sit'&&now-perch.usedAt>60000&&action.startsWith('sit_')){perch.state='drowsy';play('sit_drowsy',1);say(pick(['*yaaawn*','So… sleepy…','Eyes… closing…']),1800);}
  else if(perch.state==='doze'&&now-perch.dozeAt>30000){perch.state='sleep';lieDir=Math.random()<.5?1:-1;play('sleep_side',99);}}
function wakeOnPerch(){const was=perch.state;perch.state='sit';perch.usedAt=Date.now();play('sit_look',1);
  if(was!=='drowsy')say(pick(['Huh? I\'m up! I\'m up!','Was I snoring?','Five more min… okay, fine.']),2000);}
function onContext(c){fgCtx=c;const pc=perchCtx();if(pc)c={...c,...pc};const cat=categorise(c);
  if(c.title!==lastFg){lastFg=c.title;switchLog.push(Date.now());switchLog=switchLog.filter(t=>Date.now()-t<600000);}
  if(cat!==wk.cat){ctxSince=Date.now();ctxReacted=null;}
  wk={cat,title:c.title,proc:c.proc,pip:c.pip};
  if(!wk.pip&&hold){hold=null;if(action==='hold_pip'){play('wave',1);say(pick(['Show\'s over!','That was a good one.']),2000);}}
  if(wk.pip&&pipLetGo&&pipLetGo!==wk.pip[0])pipLetGo=null;
  // a video popped out: go and hold it straight away, even from a nap (you're clearly up and watching)
  tryPip();}
function tryPip(){if(wk.pip&&!hold&&!away&&settings.holdPip!==false&&pipLetGo!==wk.pip[0]&&!sign&&!perch&&!falling&&!climb&&!dragging&&!game){if(action==='sleep')say('Ooh, a show!',1500);grabPip();}}
function tallyDay(){const today=new Date().toDateString();if(day.d!==today)day={d:today,cats:{}};
  const k=wk.cat||'other';const dm=(Date.now()-catTick)/60000;catTick=Date.now();if(!away&&dm<5)day.cats[k]=(day.cats[k]||0)+dm;}
const fmt=m=>m>=60?`${Math.floor(m/60)}h${Math.round(m%60)?' '+Math.round(m%60)+'m':''}`:`${Math.round(m)}m`;
function daySummary(){const names={video:'watching',design:'designing',chatbot:'chatting with bots',code:'coding',sheets:'in spreadsheets',mail:'on email',music:'with music on',docs:'writing',slides:'on slides'};
  const top=Object.entries(day.cats).filter(([k,m])=>names[k]&&m>=10).sort((a,b)=>b[1]-a[1]).slice(0,3);
  return top.length?'Today: '+top.map(([k,m])=>fmt(m)+' '+names[k]).join(', ')+'.':'';}
// a nudge at most once per kind per window of time, and never while he's busy holding something up
function nudge(kind,everyMin,text,act){if(Date.now()-(lastNudge[kind]||0)<everyMin*60000)return false;lastNudge[kind]=Date.now();targetX=null;if(act)play(act,1);say(text,6000);return true;}
function proactive(){
  if(sign||away||panelOpen()||radialOpen()||dragging||falling||perch||climb||hold||game||doodle)return;
  // while you're steering him with the cursor, the cursor wins over app reactions and nudges
  if(cursorMode()!=='off'&&Date.now()-cursorMoved<8000)return;
  if(thoughtBoard())return;
  const m=mins(),onFor=(Date.now()-ctxSince)/60000,hungryH=(Date.now()-fedAt)/3600000,lonelyM=(Date.now()-lastLove)/60000;
  // react to a new kind of work within a few seconds of you switching to it
  if((wk.cat==='video'||wk.cat==='music')&&onFor>0.05&&moodName()!=='blue'&&opine(wk.title)){ctxReacted=wk.cat;return;}
  if(wk.cat&&CTX[wk.cat]&&ctxReacted!==wk.cat&&onFor>0.08){ctxReacted=wk.cat;if(moodName()!=='blue'){targetX=null;play(CTX[wk.cat].act,3);say(pick(CTX[wk.cat].say),3000);return;}}
  if(homeNudge(onFor))return;
  if(hungryH>4&&nudge('hungry',45,pick(['I\'m sooo hungry… feed me? (double-click → Feed)','*tummy rumbles* Snack, please?']),'sad'))return;
  if(lonelyM>90&&nudge('lonely',40,pick(['Hey… remember me?','It\'s quiet down here. Say hi?','*sigh* Nobody\'s talked to me in ages.']),'sad'))return;
  if(wk.cat==='video'&&onFor>25&&!isHome()&&inRange(m,at('office'),at('pack'))&&nudge('video',60,pick(['Is this… research?','One more video, then back to work?']),'think'))return;
  if(switchLog.length>30&&nudge('switch',30,'Lots of window-hopping. Want a focus timer? Double-click → Focus.','think'))return;
  if(wk.cat&&wk.cat!=='video'&&wk.cat!=='music'&&onFor>100&&nudge('long',90,`You've been at this ${fmt(onFor)} straight. Stretch with me?`,'yawn'))return;
  if(inRange(m,at('evening'),at('bed'))&&wk.cat&&['code','sheets','mail','docs','slides','design'].includes(wk.cat)&&!weekend()&&nudge('late',60,pick(['Still working? Go home, hero.','The work will be there tomorrow. Promise.']),'yawn'))return;
  if(inRange(m,at('pack'),at('pack')+5)&&nudge('summary',600,daySummary()||'Good work today!','wave'))return;
}
// the brain's say in what he does next: holding your video, then mood, then what you're working in
function brainAmbient(){
  if(hold)return 'hold_pip';
  const md=moodName();
  if(md==='blue')return pick(['sad','sad','tired','sad']);
  if(md==='sad'&&Math.random()<.55)return pick(['sad','sad','tired','think']);
  if(wk.cat&&CTX[wk.cat]&&Math.random()<.55)return CTX[wk.cat].act;
  if(md==='happy'&&Math.random()<.3)return pick(['happy','happy','dance','hop','laugh']);
  return null;}
function moodThought(){const md=moodName();
  if(md==='blue')return pick(['*sigh*','Nobody plays with me…','I\'ll just… sit here.','Is it lunch yet? No? Okay.']);
  if(md==='sad')return pick(['Bit lonely down here.','A snack would help…','Hmm.','Could use a hug.']);
  if(md==='happy'&&Math.random()<.5)return pick(['Life is good!','Best desk buddy ever.','I could dance all day!','Feeling fantastic.']);
  if(wk.cat&&CTX[wk.cat]&&Math.random()<.4)return pick(CTX[wk.cat].say);
  if(thoughtCache&&Math.random()<.15)return thoughtCache;
  return pick(block().th);}
const moodGait=()=>{const md=moodName();return md==='blue'||md==='sad'?'walk':md==='happy'&&Math.random()<.55?pick(['skip','prance','prance']):null;};
// ---- carrying your picture-in-picture video: he holds its edge out to his side and it goes where he goes ----
const PIP_HAND=[108/384,0.797];
function handPt(){const left=(window.innerWidth-size.bw)/2;return {x:pos.x+left+size.bw*PIP_HAND[0],y:pos.y+top0()+size.bh*PIP_HAND[1]};}
function pipPlace(){const p=wk.pip;if(!p)return null;const w=p[3]-p[1],h=p[4]-p[2],hp=handPt();
  return {x:hp.x-w+size.bw*0.03,y:Math.max(area.y,Math.min(area.y+area.height-h,hp.y-h*0.72)),w,h};}
function wantPip(){return wk.pip&&settings.holdPip!==false&&pipLetGo!==wk.pip[0]&&!sign&&!away&&!perch&&!falling&&!climb&&!dragging;}
function grabPip(){const pl=pipPlace();if(!pl)return false;
  if(pl.x<area.x+8){walkTo(pos.x+(area.x+8-pl.x),'walk');return true;}
  hold={id:wk.pip[0],x:Math.round(pl.x),y:Math.round(pl.y),sent:Date.now()};B.send('move-win',{id:hold.id,x:hold.x,y:hold.y});
  targetX=null;play('hold_pip',99);say(pick(['I\'ll hold this for you!','Front row seat!','Your own personal screen stand.']),2500);return true;}
function carryPip(){if(!hold||!wk.pip)return;
  // you moved it yourself: he lets go and doesn't grab that one again
  if(wk.pip[0]===hold.id&&(Math.abs(wk.pip[1]-hold.x)>30||Math.abs(wk.pip[2]-hold.y)>30)&&Date.now()-(hold.sent||0)>1500){pipLetGo=hold.id;hold=null;play('look',1);say('Okay, you take it!',1800);return;}
  const pl=pipPlace();if(!pl)return;const x=Math.round(pl.x),y=Math.round(pl.y);
  if(Math.abs(x-hold.x)>2||Math.abs(y-hold.y)>2){hold.x=x;hold.y=y;hold.sent=Date.now();B.send('move-win',{id:hold.id,x,y});}}
setInterval(()=>{if(!settings||!size)return;moodTick();tallyDay();},60000);
setInterval(()=>{if(!settings||!size)return;try{perchSleepTick();floorSleepTick();tryPip();proactive();carryPip();}catch(e){B.send('log','brain: '+(e&&e.message));}},1500);
B.on('context',c=>{try{onContext(c||{});}catch(e){B.send('log','context: '+(e&&e.message));}});

// ---------------- home: play, make things, celebrate ----------------
// Home mode is on, off, or auto: weekends, and outside office hours on weekdays. At home his menu swaps the office tools
// for games and creative ones.
function isHome(){const h=settings.home||'auto';if(h!=='auto')return h==='on';return weekend()||!inRange(mins(),at('office'),at('pack'));}
// his two meters: Happy is his mood; Full drains over about five hours after a meal
const fullness=()=>Math.max(0,Math.min(100,100-(Date.now()-fedAt)/3600000*20));
let metersTimer=0;
// they show only while his menu is open, and flash for a moment when you feed, pet or tickle him
function showMeters(on,ms=300){clearTimeout(metersTimer);
  if(on){$('mHappy').style.width=Math.round(mood)+'%';$('mFull').style.width=Math.round(fullness())+'%';$('mWeight').style.width=Math.round(Math.abs(bodyOf()))+'%';$('mBodyL').textContent=bodyOf()<-25?'Fit':bodyOf()>25?'Chubby':'Body';meters.classList.add('show');layout();}
  else metersTimer=setTimeout(()=>{if(!radialOpen()){meters.classList.remove('show');layout();}},ms);}
function flashMeters(){if(radialOpen())return showMeters(true);if(panelOpen())return;showMeters(true);showMeters(false,2500);}
// this week's tally: renders, doodles, ideas, fetches, snacks
function weekKey(){const d=new Date(),j=new Date(d.getFullYear(),0,1);return d.getFullYear()+'-'+Math.ceil(((d-j)/86400000+j.getDay()+1)/7);}
function bump(k,n=1){const w=settings.week&&settings.week.k===weekKey()?{...settings.week}:{k:weekKey()};w[k]=(w[k]||0)+n;saveS({week:w});return w[k];}
function weekLine(){const w=settings.week&&settings.week.k===weekKey()?settings.week:{};const bits=[['renders','render'],['doodles','doodle'],['ideas','idea'],['fetches','fetch'],['snacks','snack']]
    .filter(([k])=>w[k]).map(([k,one])=>`${w[k]} ${w[k]===1?one:k}`);return bits.length?'This week: '+bits.join(', ')+'.':'This week: nothing yet. Let\'s make something!';}

// confetti: little ink and ochre squiggles in his own line weight, only animating while they fall
let bits=[],fxRaf=0,fxLast=0;
function confetti(n=28){const d=Math.min(2,devicePixelRatio||1);if(fx.width!==Math.round(innerWidth*d)){fx.width=Math.round(innerWidth*d);fx.height=Math.round(innerHeight*d);}
  const r=cv.getBoundingClientRect(),cx=r.left+r.width/2,cy=r.top+r.height*0.25;
  for(let i=0;i<n;i++){const a=-Math.PI/2+(Math.random()-.5)*2.2,v=0.35+Math.random()*0.45;bits.push({x:cx,y:cy,vx:Math.cos(a)*v,vy:Math.sin(a)*v,r:Math.random()*6,vr:(Math.random()-.5)*0.02,c:i%2?'#1F1F1D':'#E0A64B',k:i%3,t:0});}
  if(!fxRaf){fxLast=performance.now();fxRaf=requestAnimationFrame(fxFrame);}}
function fxFrame(now){fxRaf=0;const dt=Math.min(40,now-fxLast);fxLast=now;const d=fx.width/innerWidth,s=size.bw/384,lw=5.7*s;
  const c=fx.getContext('2d');c.setTransform(d,0,0,d,0,0);c.clearRect(0,0,innerWidth,innerHeight);c.lineWidth=lw;c.lineCap='round';c.lineJoin='round';
  for(const b of bits){b.t+=dt;b.vy+=0.0011*dt;b.vx*=0.995;b.x+=b.vx*dt;b.y+=b.vy*dt;b.r+=b.vr*dt;
    c.save();c.globalAlpha=Math.max(0,1-b.t/2200);c.translate(b.x,b.y);c.rotate(b.r);c.strokeStyle=b.c;c.beginPath();const L=size.bw*0.05;
    if(b.k===0){c.moveTo(-L,0);c.lineTo(L,0);}else if(b.k===1){c.moveTo(-L,0);c.quadraticCurveTo(0,-L,L,0);}else{c.moveTo(-L,L*.4);c.lineTo(-L/3,-L*.4);c.lineTo(L/3,L*.4);c.lineTo(L,-L*.4);}
    c.stroke();c.restore();}
  bits=bits.filter(b=>b.t<2200&&b.y<innerHeight+40);if(bits.length)fxRaf=requestAnimationFrame(fxFrame);else c.clearRect(0,0,innerWidth,innerHeight);}

// ---- games: fetch and snack catch, played across the whole screen ----
let game=null;
function toggleGame(kind){if(game){const was=game.kind;endGame(was==='fetch'?'Good game!':'Okay, no more snacks.');if(was===kind)return;}
  if(perch||falling||climb){say('Let me get down first!',1800);return;}
  if(sign)dropSign();if(doodle)stopDoodle(true);closePanel();targetX=null;
  game={kind,phase:'wait',since:Date.now(),touched:Date.now(),n:0,score:0,left:null,ball:null,sentX:null};B.send('play-start',{game:kind});
  if(kind==='fetch'){play('hop',1);say('Fetch! Grab the ball by my feet and throw it.',4000);}
  else{play('happy',1);say('Snacks incoming! Move your mouse and I\'ll follow.',3500);}}
function endGame(msg){if(!game)return;game=null;B.send('play-stop');targetX=null;if(msg){play('wave',1);say(msg,2500);}}
B.on('play',k=>toggleGame(k));
function gameTick(){if(!game||game.kind!=='fetch')return;const b=game.ball,half=window.innerWidth/2,m=size.bw/2;
  const clamp=x=>Math.max(area.x-half+m,Math.min(area.x+area.width-half-m,x));
  if(game.phase==='chase'&&b){const d=b.x-midX(pos.x);
    if(Math.abs(d)<size.bw*0.32&&b.ground&&Math.abs(b.vx)<0.5){game.phase='dribble';game.dir=Math.sign((b.from??midX(pos.x))-midX(pos.x))||1;B.send('play-cmd',{cmd:'dribble'});
      say(pick(['Got it!','Mine!','Coming back!']),1200);walkTo(clamp((b.from??midX(pos.x))-half),'skip');return;}
    const tx=clamp(b.x-half);if(action.startsWith('turn_')){targetX=tx;}else if(!isWalk(action)){if(Math.abs(tx-pos.x)>4)walkTo(tx,'jog');}
    else{targetX=tx;const want='jog'+(tx>pos.x?'_right':'_left');if(want!==action&&Math.abs(tx-pos.x)>6)play(want,99);}
    if(Date.now()-game.since>25000){game.phase='wait';targetX=null;play('tired',1);say('Too far! You get it.',2200);}}
  if(game.phase==='dribble'){const dir=action.endsWith('_left')?-1:action.endsWith('_right')?1:game.dir,x=Math.round(midX(pos.x)+dir*size.bw*0.34);
    if(x!==game.sentX){game.sentX=x;B.send('play-cmd',{cmd:'at',x});}}
  if(game.phase==='wait'&&Date.now()-game.touched>120000)endGame('That was fun! Again later?');}
// when an animation finishes during a game, the game picks what comes next
function gameNext(finished){
  if(game.kind==='snack')return false;
  if(game.phase==='chase'){game.since=game.since||Date.now();const b=game.ball;if(b&&Math.abs(b.x-midX(pos.x))>size.bw*0.32){walkTo(b.x-window.innerWidth/2,'jog');return true;}play('look',1);return true;}
  if(game.phase==='dribble'&&targetX===null){B.send('play-cmd',{cmd:'drop'});game.phase='wait';game.n++;bump('fetches');love(5,'play');game.touched=Date.now();
    play('happy',1);say(pick(['Again! Again!','Throw it further!','I\'m a very good bunny.','Fetch champion!']),2200);return true;}
  if(game.phase==='wait'){play(pick(['look','idle','hop','look']),1);return true;}
  return false;}
B.on('play-ev',e=>{if(!e)return;if(e.type==='closed'){if(game){game=null;play('look',1);}return;}if(!game)return;
  if(e.type==='snackpos'){game.snack={x:e.x,y:e.y};game.snackAt=Date.now();if(!isWalk(action)&&action!=='watch'&&!action.startsWith('turn_'))play('watch');return;}
  if(e.type==='ball'){game.ball=e;if(game.phase==='wait'&&e.moving&&!e.thrown&&action!=='watch'&&!isWalk(action))play('watch');if(game.phase==='wait'&&e.thrown&&e.moving){game.phase='chase';game.since=Date.now();game.touched=Date.now();say(pick(['Ooh!','Wheee!','I\'ll get it!']),1000);gameTick();}}
  else if(e.type==='grab'){game.touched=Date.now();if(game.phase!=='wait'){game.phase='wait';targetX=null;play('look',1);}}
  else if(e.type==='snack'){game.score=e.score;game.left=e.left;if(e.caught){love(1.5);if(Math.random()<.35)say(pick(['Nom!','Yum!','Mmm!','Crunch!']),700);}}
  else if(e.type==='over'){const n=e.score||0,best=settings.snackBest||0;game=null;B.send('play-stop');targetX=null;bump('snacks',n);love(Math.min(25,n*2),'play');
    if(n>=5)fedAt=Date.now();if(n>best)saveS({snackBest:n});routine=[n>=10?'dance':'happy'];play('eat',1);if(n>best&&n>0)confetti();
    say(n===0?'Zero snacks?! I\'m starving now.':n>best&&best?`${n} snacks! New record!`:`${n} snacks! ${n>=5?'That counts as dinner.':'More next time?'}`,4000);}});

// ---- doodle prompt of the day: he paints at his easel next to you while the timer runs ----
const PROMPTS=['A cat that thinks it\'s a lamp','Your breakfast, but heroic','A tiny door in a big tree','A cloud having a bad day','Your desk as a city',
  'A robot learning to dance','The moon on holiday','A sandwich with feelings','A monster afraid of the dark','A plant that wants a walk',
  'Your favourite song as a creature','A snail in a hurry','Two socks in love','A dragon who knits','The last cookie',
  'A ghost at a birthday party','Your face as a mountain','A bird with a job','A shoe that grew wings','The world\'s smallest house',
  'A chai cup that is also a volcano','A fish that can\'t swim','Your phone as a pet','A bus full of animals','A stormy teacup',
  'An umbrella for a giant','A cactus who wants a hug','Rain made of letters','A tiger made of stripes only','A rocket powered by snacks',
  'A map of your mood today','A lighthouse in a desert','A pencil drawing itself','A dog reading the news','A mushroom village',
  'Your hands, five ways','A sleepy sun','A train through a book','A bunny astronaut','A pocket full of stars',
  'Something you saw today, but huge','A knot that won\'t untie','An octopus office worker','A house on a turtle','A balloon that escaped',
  'One line, no lifting the pen','A shadow with its own plans','A crown for a frog','The sound of thunder, drawn','A very proud potato'];
let doodle=null,promptShift=0;
const promptOf=()=>PROMPTS[(Math.floor(Date.now()/86400000)+promptShift)%PROMPTS.length];
function openDoodle(){
  openPanel('doodle','Doodle prompt',new Date().toLocaleDateString(undefined,{day:'numeric',month:'short'}),p=>{
    el('div',{className:'prompt',textContent:promptOf()},p);
    el('div',{className:'hint',textContent:'Draw it in any app. I\'ll paint at my easel and keep time.'},p);
    const r=el('div',{className:'row'},p);for(const m of [5,10,20])btn(r,m+' min',()=>startDoodle(m),m===10?'p':'');
    btn(r,'Another one',()=>{promptShift++;openDoodle();});});
  if(!sign&&!game)play('think',1);}
function startDoodle(min){closePanel();if(game)endGame();doodle={end:Date.now()+min*60000,prompt:promptOf(),min};targetX=null;play('paint',99);say('Go! "'+doodle.prompt+'"',4000);}
function stopDoodle(quiet){if(!doodle)return;doodle=null;if(!quiet){play('wave',1);say('Paused. Come back to it later!',2000);}}
function doodleDone(){const d=doodle;doodle=null;const n=bump('doodles');confetti();routine=['dance'];play('happy',1);love(8,'make');
  say(`Time! Show me your "${d.prompt}". That's ${n} doodle${n>1?'s':''} this week.`,8000);B.send('notify',{title:'Doodle time is up',body:`"${d.prompt}". Bunny wants to see it!`});}

// ---- idea catcher: tell him an idea, he writes it down; when you're stuck he holds one up ----
let ideaText='',ideaTimer=0;
function openIdeas(){const ideas=[...(settings.ideas||[])];
  openPanel('ideas','Idea catcher',`${ideas.length} saved`,p=>{
    const inp=el('input',{type:'text',placeholder:'Tell me an idea and press Enter',maxLength:140},p);
    inp.onkeydown=e=>{if(e.key==='Enter'&&inp.value.trim()){ideas.push({t:inp.value.trim(),at:Date.now()});saveS({ideas:ideas.slice(-200)});bump('ideas');openIdeas();play('write',1);say(`Caught it! Idea #${ideas.length}.`,1800);}
      if(e.key==='Escape')closePanel();};
    const ul=el('ul',{},p);ideas.slice(-5).reverse().forEach(it=>{const li=el('li',{},ul);el('span',{textContent:it.t},li);
      const x=el('button',{className:'x',textContent:'×',title:'Remove'},li);x.onclick=()=>{const i=ideas.indexOf(it);ideas.splice(i,1);saveS({ideas});openIdeas();};});
    if(ideas.length){const r=el('div',{className:'row'},p);btn(r,'I\'m stuck',()=>{closePanel();showIdea('Here\'s one of yours:');},'p');}
    else el('div',{className:'hint',textContent:'Nothing yet. Song lyrics, video hooks, doodles to try: anything.'},p);
    setTimeout(()=>inp.focus(),60);},true);}
function showIdea(intro){const ideas=settings.ideas||[];if(!ideas.length)return false;ideaText=pick(ideas).t;holdSign('idea');say(intro+' '+ideaText,9000);
  clearTimeout(ideaTimer);ideaTimer=setTimeout(()=>{if(sign==='idea')dropSign();},20000);return true;}

// ---- render party: a new render in your folder gets a dance and confetti ----
B.on('render',r=>{const n=bump('renders');if(away)return;targetX=null;if(sign&&sign!=='banner')return say('Render done: '+r.name,6000);if(sign)dropSign();
  confetti(36);routine=['happy'];play('dance',2);love(6,'make');say(`Render done! ${r.name}. That's ${n} this week.`,6000);});

// at home he invites you to play now and then, and offers an old idea when you've been creating for a while
function homeNudge(onFor){if(!isHome()||game||doodle)return false;const lonelyM=(Date.now()-lastLove)/60000;
  if((wk.cat==='design'||wk.cat==='docs')&&onFor>45&&(settings.ideas||[]).length>=3&&Date.now()-(lastNudge.idea||0)>120*60000){lastNudge.idea=Date.now();return showIdea('Stuck? Here\'s an old idea of yours:');}
  if(lonelyM>40&&!wk.cat&&nudge('play',120,pick(['Bored! Play fetch with me? (double-click → Fetch)','Snack catch? I\'m fast, promise.']),'hop'))return true;
  return false;}


// ---- his own taste: opinions about what you watch, built up as a memory on this PC ----
const GENRES=[['animation',/animat|cartoon|anime|pixar|doodle|odd1sout|jaiden|storyboard/i],['design',/design|illustrat|motion graphic|after effects|blender|figma|typography|logo/i],
  ['cooking',/recipe|cook|kitchen|\bfood\b|chef|bak(e|ing)|street food/i],['gaming',/gameplay|minecraft|fortnite|\bgta\b|valorant|gaming|let'?s play|speedrun|walkthrough/i],
  ['horror',/horror|scary|creepy|ghost|haunted|cosmic|paranormal/i],['comedy',/funny|comedy|prank|stand-?up|meme|sketch/i],['news',/\bnews\b|breaking|politic|election|debate|headlines/i],
  ['tech',/review|unboxing|iphone|android|\btech\b|\bai\b|gadget|tutorial|how to/i],['music',/music|song|lyrics|remix|official (music )?video|official audio|acoustic|concert/i],
  ['sports',/cricket|football|\bipl\b|highlights|\bnba\b|\bf1\b|match|goal/i],['nature',/nature|wildlife|animals|ocean|documentary|planet/i],['crime',/true crime|murder|serial|mystery|case file/i]];
const genreOf=t=>(GENRES.find(([,re])=>re.test(t))||[null])[0];
// first run: a personality of his own. He's a doodle, so he leans toward animation and design.
function taste(){if(settings.taste&&Object.keys(settings.taste).length)return settings.taste;const t={};for(const [g] of GENRES)t[g]=Math.round((Math.random()*2-1)*100)/100;
  t.animation=Math.max(t.animation,0.6);t.design=Math.max(t.design,0.4);saveS({taste:t});return t;}
const cleanTitle=t=>(t||'').replace(/\s*[-–|]\s*(YouTube|Netflix|Prime Video|Google Chrome|Microsoft Edge|Mozilla Firefox|Brave|VLC.*)$/ig,'').replace(/^\(\d+\)\s*/,'').trim().slice(0,90);
let lastOpined='',opineAt=0;
function opine(title){const t=cleanTitle(title);if(!t||t===lastOpined||Date.now()-opineAt<15000)return false;lastOpined=t;opineAt=Date.now();
  const g=genreOf(t),tv=taste(),log=[...(settings.watched||[])],past=log.find(x=>x.t===t),gl=log.filter(x=>x.g&&x.g===g);
  let op=g?tv[g]:(Math.random()*0.6-0.3);if(past)op=op*0.5+past.op*0.5;
  let line;
  if(past)line=past.op>0.3?pick(['Rewatching? Yes please, I loved this.','Ooh, this one again! Good choice.']):past.op<-0.3?pick(['This again? Didn\'t love it last time.','We\'ve seen this. I\'m not a fan.']):'Haven\'t we seen this one?';
  else if(g&&gl.length>=3)line=op>0.3?pick([`Another ${g} video! You know I love these.`,`More ${g}? Best. Taste. Ever.`]):op<-0.3?pick([`${g[0].toUpperCase()+g.slice(1)} again? Can we watch something else?`,`You really like ${g}, huh. I… don't.`]):`Lots of ${g} lately.`;
  else line=op>0.5?pick(['Ooh, I like this already!','Yes! Good pick.','This is my kind of thing.']):op<-0.4?pick(['Hmm. Not my thing.','Really? This?','I\'ll just… look the other way.']):pick(['Okay, let\'s see where this goes.','Interesting…','Popcorn ready.']);
  // he's shaped by what you watch together: a little warmer to what he enjoys, a little colder to what he doesn't
  B.send('brain-event',`You watched "${t.slice(0,60)}" together; he ${op>0.3?'loved it':op<-0.3?'was not a fan':'thought it was okay'}`);
  if(g){tv[g]=Math.max(-1,Math.min(1,tv[g]+(op>0?0.04:op<0?-0.03:0.01)));}
  log.unshift({t,g,op:Math.round(op*100)/100,at:Date.now()});saveS({taste:{...tv},watched:log.slice(0,60)});
  targetX=null;if(!sign&&!hold&&!perch){play(op>0.4?'happy':op<-0.4?pick(['turn_back','sad']):'popcorn',op>0.4?1:2);}
  say(line,4500);if(op>0.4)love(2,'show');else if(op<-0.4)love(-2);return true;}
function tasteLine(){const tv=taste(),e=Object.entries(tv).sort((a,b)=>b[1]-a[1]);const likes=e.filter(([,v])=>v>0.3).slice(0,3).map(([k])=>k),nope=e.filter(([,v])=>v<-0.3).slice(-2).map(([k])=>k);
  return 'Likes '+(likes.join(', ')||'a bit of everything')+'. '+(nope.length?'Not a fan of '+nope.join(', ')+'.':'');}

// ---- chat: he answers from what he knows on this PC (mood, tastes, what you watched, notes, ideas, your day) and can do things for you ----
const JOKES=['Why did the bunny cross the road? To prove he wasn\'t chicken.','What do you call a bunny with fleas? Bugs Bunny.','I tried to draw myself once. Too many ears.',
  'My favourite colour is ochre. Also my only colour.','I\'m not lazy, I\'m in energy-saving mode.','Why are bunnies good at maths? They multiply fast.'];
let chatLog=[];
function openChat(){chatLog=(settings.chat||[]).slice(-6);
  openPanel('chat','Chat','with Bunny',p=>{const ul=el('ul',{},p);
    for(const m of chatLog){const li=el('li',{},ul);el('span',{textContent:(m.me?'You: ':'Bunny: ')+m.t},li);}
    const bs=brainInfo;if(bs){const r=el('div',{className:'row'},p);
      if(bs.ready)el('div',{className:'hint',textContent:`Brain: on this PC · ${bs.facts} memories`+(bs.traits.length?' · '+bs.traits.slice(0,3).map(t=>t[0]).join(', '):'')},p);
      else if(brainDl||bs.downloading)el('div',{className:'hint',textContent:'Downloading his brain… '+(brainDl&&brainDl.total?Math.round(100*brainDl.done/brainDl.total)+'%':'')},p);
      else btn(r,'Give him a real brain (1.1 GB)',()=>{B.invoke('brain-download').then(ok=>{refreshBrain();say(ok?'Whoa. I can THINK now.':'Brain download hiccup. Try again later?',3000);});say('Downloading my brain… watch the ring!',3000);setTimeout(openChat,300);},'p');
      btn(r,'Memories',()=>openMemories());}
    if(!chatLog.length)el('div',{className:'hint',textContent:'Say hi! Try "how are you", "what do you like", "remind me in 10 min to stretch", "idea: …", "eat a salad", "play fetch", "tell me a joke".'},p);
    const inp=el('input',{type:'text',placeholder:'Type to Bunny and press Enter',maxLength:200},p);setTimeout(()=>{panel.scrollTop=panel.scrollHeight;},0);
    inp.onkeydown=async e=>{if(e.key==='Enter'&&inp.value.trim()&&!thinking){const q=inp.value.trim();inp.value='';const a=await reply(q);const log=[...(settings.chat||[]),{me:1,t:q},{t:a}].slice(-30);saveS({chat:log});if(panelOpen())openChat();say(a,Math.min(9000,2500+a.length*45));}
      if(e.key==='Escape')closePanel();};
    setTimeout(()=>inp.focus(),60);},true);}
// ---- brain: chats fill his memory bank; memories grow his traits and the thoughts on his board ----
let brainInfo=null,brainDl=null,thinking=false,lastThought=Date.now(),thoughtCache=null;
function refreshBrain(){B.invoke('brain-state').then(s=>{brainInfo=s;}).catch(()=>{});}
setTimeout(refreshBrain,4000);setInterval(refreshBrain,10*60000);
const brainCtx=()=>({name:settings.userName||'',mood:moodName(),time:new Date().toLocaleString([], {weekday:'long',hour:'numeric',minute:'2-digit'}),
  doing:({video:'watching something',music:'listening to music',design:'designing',chatbot:'chatting with an AI',code:'coding',sheets:'in a spreadsheet',mail:'on email',docs:'writing',slides:'making slides',whatsapp:'on WhatsApp'})[wk.cat]||'on the computer',
  history:(settings.chat||[]).slice(-6)});
const CMD=new RegExp('(?:my name is|call me|remind me in \\d|^idea|^save idea|^note|^remember|^add note|\\bfetch\\b|snack (?:game|catch)|\\bdance\\b|guitar|play (?:me )?(?:a )?song|doodle.*prompt|\\b(?:eat|have|feed you|try)\\b.*\\b(?:'+Object.keys(FOODS).join('|')+'))','i');
async function reply(q){if(CMD.test(q)){B.send('brain-event','Chat: '+q);return answer(q);}
  thinking=true;const was=action;if(!sign&&!perch)play('think',4);say('…',30000);
  try{const r=await B.invoke('brain-chat',{q,ctx:brainCtx()});if(r&&r.text){refreshBrain();return r.text;}}catch{}finally{thinking=false;}
  return answer(q);}
function openMemories(){B.invoke('brain-state').then(st=>{brainInfo=st;openPanel('mem','Memories',`${st.facts} kept · ${st.chats} chats`,p=>{
  if(st.traits.length){el('div',{className:'hint',textContent:'His personality, from your chats'},p);const tl=el('ul',{},p);
    for(const [k,v] of st.traits){const li=el('li',{},tl);el('span',{textContent:`${k[0].toUpperCase()+k.slice(1)} · ${v}`},li);}}
  el('div',{className:'hint',textContent:st.recent.length?'Recent memories (× to forget)':'No memories yet. Chat with him and he\'ll start keeping some.'},p);
  const ul=el('ul',{},p);st.recent.forEach((t,i)=>{const li=el('li',{},ul);el('span',{textContent:t},li);
    const x=el('button',{className:'x',textContent:'×',title:'Forget'},li);x.onclick=()=>{B.send('brain-forget',i);setTimeout(openMemories,150);};});});});}
// his traits nudge what he does when nothing else is going on
const TRAIT_ACTS={foodie:['eat','drink'],playful:['hop','dance_bounce'],artsy:['paint'],cinephile:['popcorn'],musical:['guitar'],curious:['read','think'],cozy:['tired','sleep'],sporty:['hop','dance_step'],hardworking:['write','think'],affectionate:['happy','wave']};
function traitAct(){const t=brainInfo&&brainInfo.traits;if(!t||!t.length||Math.random()>.18)return null;const [k,v]=pick(t.slice(0,3));return Math.random()*100<v?pick(TRAIT_ACTS[k]||['idle']):null;}
// every half hour or so, a thought from his memories goes up on his board
function thoughtBoard(){if(Date.now()-lastThought<(25+Math.random()*20)*60000||thinking||!brainInfo||!brainInfo.facts)return false;lastThought=Date.now();
  B.invoke('brain-thought',brainCtx()).then(t=>{if(!t||sign||perch||panelOpen()||dragging||falling||game)return;thoughtCache=t;ideaText=t;holdSign('idea');
    clearTimeout(ideaTimer);ideaTimer=setTimeout(()=>{if(sign==='idea')dropSign();},16000);}).catch(()=>{});return true;}
function answer(q){const t=q.toLowerCase(),name=settings.userName,md=moodName(),hi=name?`, ${name}`:'';let m;
  const act=(a,n=1)=>{if(!sign)play(a,n);};
  if(m=q.match(/(?:my name is|call me|i am|i'm)\s+([A-Za-z][\w'-]{1,20})$/i)){saveS({userName:m[1]});act('wave');return `Nice to meet you, ${m[1]}! I'll remember that.`;}
  if(m=q.match(/remind me in (\d+)\s*(m|min|mins|minutes|h|hr|hrs|hours)\b\s*(?:to\s+)?(.*)/i)){const min=+m[1]*(/^h/i.test(m[2])?60:1);B.send('add-reminder',{minutes:min,text:m[3]||'Your reminder!'});act('write');return `Got it. In ${min} min I'll remind you${m[3]?' to '+m[3]:''}.`;}
  if(m=q.match(/^(?:idea|save idea)[:\s]+(.+)/i)){const ideas=[...(settings.ideas||[]),{t:m[1],at:Date.now()}];saveS({ideas:ideas.slice(-200)});bump('ideas');act('write');return `Caught it! That's idea #${ideas.length}.`;}
  if(m=q.match(/^(?:note|remember|remember to|add note)[:\s]+(.+)/i)){const n=[...(settings.notes||[])];if(n.length>=6)return 'My notebook is full (six points). Tick one off first?';n.push({text:m[1].slice(0,80),done:false});saveS({notes:n});act('write');return 'Noted in my notebook!';}
  for(const k of Object.keys(FOODS))if(new RegExp('\\b(eat|have|feed you|try)\\b.*\\b'+k).test(t)){setTimeout(()=>feed(k),400);return k==='salad'?'Fine. Salad.':`${k[0].toUpperCase()+k.slice(1)}? Don't mind if I do!`;}
  if(/\bfetch\b/.test(t)){setTimeout(()=>toggleGame('fetch'),300);return 'YES. Get the ball!';}
  if(/snack (game|catch)/.test(t)){setTimeout(()=>toggleGame('snack'),300);return 'Snacks from the sky? I\'m ready!';}
  if(/\bdance\b/.test(t)){act('dance',2);return pick(['Watch this!','Busting a move!']);}
  if(/guitar|play (me )?(a )?song/.test(t)){act('guitar',2);return 'This one\'s called "Ode to Carrots".';}
  if(/doodle|draw/.test(t)&&/prompt|what should/.test(t))return `Today's doodle prompt: "${promptOf()}". Want me to time you? Double-click → Doodle.`;
  if(/joke|funny/.test(t)){act('laugh');return pick(JOKES);}
  if(/^(hi|hey|hello|yo|sup|hola|namaste)\b/.test(t)){act('wave');return pick([`Hi${hi}!`,`Hey${hi}! `])+(md==='happy'?' I\'m having a great day.':md==='sad'||md==='blue'?' I missed you.':' What are we up to?');}
  if(/how are you|how do you feel|you ok|how's it going/.test(t)){const f=fullness();return `Feeling ${md}. ${f<30?'Pretty hungry, honestly.':f>80?'Very full.':'Not hungry.'} ${bodyOf()>25?'A bit round lately…':bodyOf()<-25?'Fit as a fiddle!':''}`.trim();}
  if(/hungry|food|eat/.test(t)){const f=fullness();return f<40?'Starving! Salad, apple, burger or donut? Just say "eat a burger".':'I\'m okay for now. Maybe an apple later?';}
  if(m=t.match(/do you like (.+)/)){const g=genreOf(m[1])||genreOf(m[1]+' video');if(!g)return pick(['Never tried it. Show me?','Hmm, ask me after we watch some.']);const v=taste()[g];return v>0.3?`I love ${g}!`:v<-0.3?`Honestly? Not a fan of ${g}.`:`${g[0].toUpperCase()+g.slice(1)} is okay, I guess.`;}
  if(/what do you like|favou?rite|your taste/.test(t))return tasteLine();
  if(/what (did|have) (we|i) (watch|seen)|remember what|last (video|watched)/.test(t)){const w=(settings.watched||[]).slice(0,3);return w.length?'Lately: '+w.map(x=>`"${x.t.slice(0,40)}" (${x.op>0.3?'loved it':x.op<-0.3?'meh':'okay'})`).join(', ')+'.':'We haven\'t watched anything together yet!';}
  if(/my day|today|what did i do|summary/.test(t))return daySummary()||'Quiet day so far. '+weekLine();
  if(/this week|week/.test(t))return weekLine();
  if(/notes?|todo|to-do/.test(t)){const n=(settings.notes||[]).filter(x=>!x.done);return n.length?'Still open: '+n.map(x=>x.text).join('; '):'Notebook is clear!';}
  if(/ideas?|stuck|inspire/.test(t)){const i=settings.ideas||[];return i.length?'One of yours: "'+pick(i).t+'"':'No ideas saved yet. Say "idea: …" and I\'ll keep it.';}
  if(/time|what time|date|day is it/.test(t)){const d=new Date();return `It's ${d.toLocaleTimeString([], {hour:'numeric',minute:'2-digit'})}, ${d.toLocaleDateString([], {weekday:'long',day:'numeric',month:'short'})}.`;}
  if(/thank|love you|good (boy|bunny)|cute|best/.test(t)){love(6,'chat');act('happy');return pick(['Aww! You\'re the best.','*happy ear wiggle*','Stop it, I\'m blushing. In ochre.']);}
  if(/who are you|what are you|your name/.test(t))return 'I\'m Bunny, your desk buddy from DeepInDoodles. I draw, dance, eat too many donuts and remember what you watch.';
  if(/bye|good ?night|see you|sleep/.test(t)){act('wave');return pick([`Bye${hi}!`,'See you soon!','Sweet dreams!']);}
  if(/weather|news|search|google/.test(t))return 'I live offline on your PC, so I can\'t check the internet. Want a joke instead?';
  love(1,'chat');return pick(['Hmm, tell me more!','Interesting… I\'ll think about that.','I\'m just a bunny, but I\'m listening.','Ha! Okay.','Say that again, but with snacks.']);}
// ---------------- events from the app ----------------
B.on('remind',r=>{if(sign)return say(r.text,9000);targetX=null;play(r.action,LOOPS.has(r.action)?2:1);say(r.text,9000);});
// update ring: a buffer circle above his head while a new version downloads; it fills as files arrive
function ring(p){const u=$('upd');if(!p)return u.classList.remove('show');const r=cv.getBoundingClientRect(),d=Math.max(36,Math.round(size.bw*0.22));
  Object.assign(u.style,{width:d+'px',height:d+'px',left:Math.round(r.left+r.width/2-d/2)+'px',top:Math.max(2,Math.round(r.top+size.bh*0.02-d))+'px'});u.classList.add('show');
  const f=p.total?p.done/p.total:0,arc=$('updArc'),C=2*Math.PI*13;arc.setAttribute('stroke-dasharray',f<0.02?'20 82':`${(f*C).toFixed(1)} ${C.toFixed(1)}`);arc.parentNode.classList.toggle('spin',f<0.02);}
B.on('update-progress',ring);B.on('brain-progress',p=>{brainDl=p;ring(p);});
B.on('say',r=>{if(r.action&&!sign)play(r.action,1);say(r.text,r.ms);});
B.on('do',a=>{targetX=null;if(!sign)play(a,LOOPS.has(a)?2:1);});
B.on('sign',k=>{if(sign===k)return dropSign();holdSign(k);});
B.on('radial',()=>openRadial());
B.on('routine',k=>{if(sign||away)return;targetX=null;
  if(k==='lunch'){routine=['eat','drink'];play('dance',2);say('Lunch time! Dance first, then burger.',4000);}
  if(k==='tea'){routine=['idle'];play('tea',1);say('Tea time! Chai, anyone?',3500);}
  if(k==='snack'){routine=['happy'];play('eat_apple',1);fedAt=Date.now();love(6);say(pick(['Snack time! Want one too?','Afternoon munchies. Join me?']),4000);}
  if(k==='winddown'){routine=['yawn','read'];play('tea',1);say(pick(['Half an hour to bed. Save your work?','Winding down. One more thing, then sleep?']),6000);}
  if(k==='pack'){const open=(settings.notes||[]).filter(n=>!n.done);routine=['wave'];play('pack',1);
    say(open.length?`Packing up! ${open.length} note${open.length>1?'s':''} still open: ${open.map(n=>n.text).join(', ')}`:'Packing up! Notebook is clear. Good work today!',9000);}});
B.on('away',v=>{if(v===away)return;away=v;if(sign)return;if(v){targetX=null;closeRadial();closePanel();play('sleep',99);}else{play('wave',1);say(pick(['Welcome back!','Oh, you\'re back!','Hi again!']),2500);}});
B.on('focus',f=>{focus=f;if(sign)return;if(f.mode==='focus'){targetX=null;play('read',99);say('Focus mode. I\'ll read quietly.',3000);}else if(f.mode==='break'){play('yawn',1);}else if(f.mode==='off')play('idle');});
B.on('meeting',m=>{meeting=m;});
function recover(a){if(a)area=a;if(!area||!Number.isFinite(groundY())){B.invoke('bounds').then(r=>{area=r.area;if(Number.isFinite(groundY()))recover();});return;}perch=null;climb=null;falling=false;vy=0;vx=0;targetX=null;if(a)area=a;
  pos.x=Number.isFinite(pos.x)?Math.max(area.x,Math.min(area.x+area.width-window.innerWidth,pos.x)):area.x+area.width*0.7-window.innerWidth/2;pos.y=groundY();sentX=NaN;sendPos();drawn='';play('look',1);}
B.on('rescue',r=>recover(r&&r.area));
B.on('area',a=>{area=a;if(perch||falling||climb)return;pos.y=groundY();sendPos();});
B.on('win-rect',r=>{if(!r)return;const i=wins.findIndex(o=>o[0]===r[0]);if(i<0)return;wins[i]=[...r.slice(0,5),wins[i][5],wins[i][6]];
  // move with the window the moment it moves, rather than on his next frame
  if(perch&&perch.id===r[0]&&!dragging&&!climb&&!swing&&!maximised(wins[i])){pos.x=r[1]+perch.dx-window.innerWidth/2;pos.y=yFor(r[2],fracFor(action));sendPos();}});
B.on('windows',list=>{wins=list||[];const pc=perchCtx();if(pc&&(pc.title!==wk.title||pc.proc!==wk.proc))onContext(fgCtx);else if(!pc&&(wk.title!==fgCtx.title||wk.proc!==fgCtx.proc))onContext(fgCtx);});
B.on('cursor',c=>{if(!cursor||Math.abs(c.x-cursor.x)>2||Math.abs(c.y-cursor.y)>2)cursorMoved=Date.now();cursor=c;});
B.on('settings',s=>{settings=s.settings;resize(s.size);
  if(settings.stayPut&&isWalk(action)&&cursorMode()!=='follow'){targetX=null;play('idle');}
  if(settings.windows===false&&perch)letGo();});
function resize(s){size=s;if(wheelBw===null)cv.style.transform='';const dpr=Math.min(2,window.devicePixelRatio||1);cv.style.width=s.bw+'px';cv.style.height=s.bh+'px';
  const W=Math.round(s.bw*dpr),H=Math.round(s.bh*dpr);if(cv.width!==W||cv.height!==H){cv.width=W;cv.height=H;}drawn='';if(cacheW!==W)resetFrames();bubble.style.fontSize=Math.max(13,Math.min(17,Math.round(s.bw*0.09)))+'px';draw();layout();
  B.invoke('bounds').then(r=>{area=r.area;if(!falling&&!perch&&!climb&&!dragging){pos={x:r.bounds.x,y:groundY()};sendPos();}layout();});}

(async()=>{
  meta=window.META;
  const init=await B.invoke('init');settings=init.settings;area=init.area;mood=+settings.mood||60;lastLove=+settings.lastLove||Date.now();fedAt=+settings.fedAt||Date.now();if(settings.day&&settings.day.d)day=settings.day;pos={x:init.bounds.x,y:init.bounds.y};resize(init.size);
  await document.fonts.load('20px "Patrick Hand"').catch(()=>{});
  play('wave',1);say(pick(['Hi! I\'m Bunny. Double-click me for my menu.','Hello! Let\'s have a good day.']),3500);
  nextThought=Date.now()+90000;
  requestAnimationFrame(tick);
})();
