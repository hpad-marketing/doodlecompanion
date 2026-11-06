// Bunny's playground: a see-through layer over the screen, open only while you play. It holds his ball (fetch) and the
// falling snacks (snack catch). Clicks pass straight through except on the ball. Everything is drawn in his two brand
// colours with his own line weight, and it only animates while something moves.
const B=window.bunny,cv=document.getElementById('c'),ctx=cv.getContext('2d');
const INK='#1F1F1D',OCHRE='#E0A64B',pick=a=>a[Math.floor(Math.random()*a.length)];
let A={x:0,y:0},bun=null,game=null,ball=null,snacks=[],bits=[],raf=0,last=0,over=false,drag=null,score=0,endAt=0,nextDrop=0,lastSec=-1,dribble=null,sentAt=0,wasMoving=false;
const bw=()=>bun?bun.bw:150,lw=()=>Math.max(1.5,5.7*bw()/384),R=()=>Math.max(9,bw()*0.11),floorY=()=>innerHeight;
function fit(){const d=Math.min(2,devicePixelRatio||1);cv.width=Math.round(innerWidth*d);cv.height=Math.round(innerHeight*d);cv.style.width=innerWidth+'px';cv.style.height=innerHeight+'px';ctx.setTransform(d,0,0,d,0,0);}
fit();addEventListener('resize',()=>{fit();kick();});
function box(){if(!bun)return null;const left=bun.x-A.x+(bun.w-bun.bw)/2,top=bun.y-A.y+bun.h-bun.bh;return {left,top,cx:left+bun.bw/2,bw:bun.bw,bh:bun.bh};}
function kick(){if(!raf)raf=requestAnimationFrame(frame);}

B.on('start',s=>{A=s.area;bun=s.bunny;game=s.game;snacks=[];bits=[];score=0;dribble=null;lastSec=-1;
  if(game==='fetch'){const b=box();ball={x:b?Math.min(innerWidth-R(),b.cx+b.bw*0.5):innerWidth/2,y:floorY()-R(),vx:0,vy:0,a:0,thrown:false};}else ball=null;
  if(game==='snack'){endAt=performance.now()+30000;nextDrop=performance.now()+700;}
  last=performance.now();kick();});
B.on('bunny',b=>{bun=b;});
B.send('play-ready');
B.on('cmd',c=>{if(!ball)return;
  if(c.cmd==='dribble'){dribble={x:ball.x};ball.vx=ball.vy=0;ball.thrown=false;}
  else if(c.cmd==='at'&&dribble)dribble.x=Math.max(R(),Math.min(innerWidth-R(),c.x-A.x));
  else if(c.cmd==='drop'){dribble=null;ball.thrown=false;}
  kick();});

function frame(now){raf=0;const dt=Math.min(40,now-last);last=now;let alive=false;
  ctx.clearRect(0,0,innerWidth,innerHeight);
  if(ball){alive=stepBall(dt)||!!drag;drawBall();}
  if(game==='snack')alive=stepSnacks(now,dt)||alive;
  alive=stepBits(dt)||alive;
  if(alive)kick();}

// ---- fetch ----
function stepBall(dt){const r=R(),f=floorY()-r;
  if(drag)return true;
  if(dribble){const dx=dribble.x-ball.x,mv=Math.max(-dt*1.2,Math.min(dt*1.2,dx*0.3));ball.x+=mv;ball.a+=mv/r;ball.y=f;return Math.abs(dx)>0.5;}
  ball.vy+=0.0022*dt;ball.x+=ball.vx*dt;ball.y+=ball.vy*dt;ball.a+=ball.vx*dt/r;
  if(ball.y>f){ball.y=f;ball.vy=Math.abs(ball.vy)>0.12?-ball.vy*0.62:0;ball.vx*=0.985;}
  if(ball.y<r){ball.y=r;ball.vy=Math.abs(ball.vy)*0.6;}
  if(ball.x<r){ball.x=r;ball.vx=Math.abs(ball.vx)*0.7;}
  if(ball.x>innerWidth-r){ball.x=innerWidth-r;ball.vx=-Math.abs(ball.vx)*0.7;}
  if(ball.y>=f&&ball.vy===0){ball.vx*=Math.pow(0.996,dt);if(Math.abs(ball.vx)<0.01)ball.vx=0;}
  const moving=ball.vx!==0||ball.vy!==0||ball.y<f;report(moving);return moving;}
function report(moving,force){const now=performance.now();if(!force&&(moving?now-sentAt<90:!wasMoving))return;wasMoving=moving;sentAt=now;
  B.send('play-ev',{type:'ball',x:ball.x+A.x,y:ball.y+A.y,vx:ball.vx,ground:ball.y>=floorY()-R()-1,moving,thrown:ball.thrown,from:ball.from});}
function drawBall(){const r=R();ctx.save();ctx.translate(ball.x,ball.y);ctx.rotate(ball.a);ctx.lineWidth=lw();ctx.strokeStyle=INK;ctx.fillStyle=OCHRE;ctx.lineCap='round';
  ctx.beginPath();ctx.arc(0,0,r,0,Math.PI*2);ctx.fill();ctx.stroke();
  ctx.beginPath();ctx.arc(-r*1.35,0,r*0.95,-0.75,0.75);ctx.stroke();
  ctx.beginPath();ctx.arc(r*1.35,0,r*0.95,Math.PI-0.75,Math.PI+0.75);ctx.stroke();ctx.restore();}
const onBall=e=>ball&&Math.hypot(e.clientX-ball.x,e.clientY-ball.y)<R()*1.7;
addEventListener('mousemove',e=>{const hit=!!drag||onBall(e);if(hit!==over){over=hit;B.send('play-hit',hit);document.body.style.cursor=hit?'grab':'';}
  if(drag){const t=performance.now();drag.trail.push([t,e.clientX,e.clientY]);while(drag.trail.length>2&&t-drag.trail[0][0]>100)drag.trail.shift();
    ball.x=Math.max(R(),Math.min(innerWidth-R(),e.clientX));ball.y=Math.min(floorY()-R(),e.clientY);kick();}});
addEventListener('mousedown',e=>{if(e.button!==0||!onBall(e))return;drag={trail:[[performance.now(),e.clientX,e.clientY]]};dribble=null;ball.vx=ball.vy=0;document.body.style.cursor='grabbing';B.send('play-ev',{type:'grab'});});
addEventListener('mouseup',()=>{if(!drag)return;const tr=drag.trail,a=tr[0],b=tr[tr.length-1],d=Math.max(16,b[0]-a[0]);drag=null;document.body.style.cursor=over?'grab':'';
  ball.vx=Math.max(-3,Math.min(3,(b[1]-a[1])/d));ball.vy=Math.max(-3,Math.min(3,(b[2]-a[2])/d));ball.thrown=true;ball.from=ball.x+A.x;report(true,true);kick();});

// ---- snack catch: 30 seconds of falling snacks; he follows your cursor and catches them on his head and mouth ----
function stepSnacks(now,dt){const H=innerHeight,s=bw()*0.22,left=Math.max(0,endAt-now);
  if(left>0&&now>=nextDrop){const prog=1-left/30000;
    snacks.push({x:s+Math.random()*(innerWidth-2*s),y:-s,vy:(0.16+0.22*prog)*Math.max(0.7,H/900),k:pick(['carrot','cookie','donut']),a:(Math.random()-.5)*0.6,va:(Math.random()-.5)*0.002});
    nextDrop=now+1000-480*prog+Math.random()*250;}
  const b=box();
  for(const sn of snacks){sn.y+=sn.vy*dt;sn.a+=sn.va*dt;
    if(b&&Math.abs(sn.x-b.cx)<b.bw*0.36&&sn.y>b.top+b.bh*0.2&&sn.y<b.top+b.bh*0.72){sn.gone=true;score++;bits.push({x:sn.x,y:sn.y-s*0.6,t:0,k:'plus'});
      B.send('play-ev',{type:'snack',caught:true,score,left:Math.ceil(left/1000)});}
    else if(sn.y>H-s*0.35){sn.gone=true;bits.push({x:sn.x,y:H-lw(),t:0,k:'crumb'});}}
  snacks=snacks.filter(x=>!x.gone);for(const sn of snacks)drawSnack(sn,s);
  // tell him which snack lands next, so he can keep his eyes on it
  if(snacks.length&&now-sentAt>120){sentAt=now;const n=snacks.reduce((a,x)=>x.y>a.y?x:a);B.send('play-ev',{type:'snackpos',x:n.x+A.x,y:n.y+A.y});}
  const sec=Math.ceil(left/1000);if(sec!==lastSec){lastSec=sec;B.send('play-ev',{type:'snack',score,left:sec});}
  if(left<=0&&!snacks.length){game=null;B.send('play-ev',{type:'over',score});return false;}
  return true;}
function drawSnack(sn,s){ctx.save();ctx.translate(sn.x,sn.y);ctx.rotate(sn.a);ctx.lineWidth=lw();ctx.strokeStyle=INK;ctx.fillStyle=OCHRE;ctx.lineCap=ctx.lineJoin='round';
  if(sn.k==='carrot'){ctx.beginPath();ctx.moveTo(-s*0.3,-s*0.35);ctx.quadraticCurveTo(0,-s*0.48,s*0.3,-s*0.35);ctx.lineTo(0,s*0.55);ctx.closePath();ctx.fill();ctx.stroke();
    ctx.beginPath();ctx.moveTo(-s*0.14,-s*0.05);ctx.lineTo(s*0.06,-s*0.05);ctx.moveTo(-s*0.04,s*0.2);ctx.lineTo(s*0.12,s*0.2);
    ctx.moveTo(0,-s*0.43);ctx.lineTo(0,-s*0.72);ctx.moveTo(-s*0.04,-s*0.43);ctx.lineTo(-s*0.2,-s*0.65);ctx.moveTo(s*0.04,-s*0.43);ctx.lineTo(s*0.2,-s*0.65);ctx.stroke();}
  else{ctx.beginPath();ctx.arc(0,0,s*0.42,0,Math.PI*2);ctx.fill();ctx.stroke();
    if(sn.k==='donut'){ctx.beginPath();ctx.arc(0,0,s*0.13,0,Math.PI*2);ctx.stroke();ctx.beginPath();ctx.arc(0,0,s*0.28,Math.PI*1.1,Math.PI*1.6);ctx.stroke();}
    else{ctx.fillStyle=INK;for(const [x,y] of [[-0.16,-0.12],[0.15,-0.04],[-0.02,0.18]]){ctx.beginPath();ctx.arc(x*s,y*s,lw()*0.9,0,Math.PI*2);ctx.fill();}}}
  ctx.restore();}
function stepBits(dt){for(const b of bits)b.t+=dt;bits=bits.filter(b=>b.t<650);
  for(const b of bits){const k=b.t/650;ctx.save();ctx.globalAlpha=1-k;ctx.strokeStyle=ctx.fillStyle=INK;ctx.lineWidth=lw();ctx.lineCap='round';
    if(b.k==='plus'){ctx.font=`${Math.round(bw()*0.17)}px "Patrick Hand"`;ctx.textAlign='center';ctx.fillText('+1',b.x,b.y-k*bw()*0.25);}
    else{ctx.beginPath();for(const a of [-2.4,-1.57,-0.7]){const r0=bw()*0.04,r1=r0+bw()*0.06*(0.5+k);ctx.moveTo(b.x+Math.cos(a)*r0,b.y+Math.sin(a)*r0);ctx.lineTo(b.x+Math.cos(a)*r1,b.y+Math.sin(a)*r1);}ctx.stroke();}
    ctx.restore();}
  return bits.length>0;}
