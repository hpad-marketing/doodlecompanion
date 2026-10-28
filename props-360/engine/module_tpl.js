// 360° prop library: approved props, each drawn from its own 3D model at every 15° of turn and 30° of tilt.
// Animate › 360° props… puts one in Bunny's hand at the playhead, or on its own in the scene. The holding pose is keyed, and the prop
// swaps to the right view as Bunny turns, drawing over the body on the near side and behind it on the far side.
const PropLibrary360=(()=>{
  const S=Studio,W=Workflow,LIB=__PROP360_DATA__,PITCH=10,BLEND=200;
  const rad=d=>d*Math.PI/180,wrap=a=>((a%360)+360)%360,esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const nearest=(list,x)=>list.reduce((b,v)=>Math.abs(v-x)<Math.abs(b-x)?v:b,list[0]);
  const find=id=>LIB.props.find(p=>p.id===id);
  // Same rotation as the generator (p3d.view_matrix): z of a point toward the camera after yaw, then pitch.
  function depthOf([x,y,z],yaw,pitch){const sy=Math.sin(rad(yaw)),cy=Math.cos(rad(yaw)),z1=-sy*x+cy*z;return Math.sin(rad(pitch))*y+Math.cos(rad(pitch))*z1;}
  const viewKey=(rec,turn,pitch)=>(Math.round(wrap(turn)/15)*15%360)+'_'+nearest(LIB.pitches,pitch);
  function frame(rec,turn,pitch=PITCH){
    const h=rec.hold,hx=h.attach==='armR'?60:-60;
    const zh=h.hand==='both'?25*Math.cos(rad(turn)):-hx*Math.sin(rad(turn))+25*Math.cos(rad(turn));
    // Near side: over the body, only the hands cut in (fingers round a handle). Far side: depth-tested, the body hides it.
    const placement=h.placement||(zh>=0?'under-hands':undefined);
    return{svg:rec.views[viewKey(rec,turn,pitch)],placement,value:{attachment:h.attach,upright:true,rotation:0,visible:true,depth:+(-.1-.01*depthOf(h.centroid,turn,pitch)).toFixed(3),x:h.offset[0],y:h.offset[1]}};
  }
  // One prop entry per run of frames that share a view, keyed visible only for that run.
  function track(rec,turnAt,duration){
    const out=[];let cur=null;
    for(let f=0;f*1000/30<duration;f++){
      const t=f*1000/30,turn=turnAt(t),v=frame(rec,turn),id=viewKey(rec,turn,PITCH)+'|'+(v.placement||'depth');
      if(!cur||cur.id!==id){
        if(cur)cur.keys.push({t,ease:'constant',value:{...cur.last,visible:false}});
        cur={id,svg:v.svg,placement:v.placement,keys:[],last:v.value};
        if(t>0)cur.keys.push({t:0,ease:'constant',value:{...v.value,visible:false}});
        cur.keys.push({t,ease:'constant',value:v.value});out.push(cur);
      }
      cur.last=v.value;
    }
    return out;
  }
  function hold(id,{at=playhead,seconds=3}={}){
    const rec=find(id);if(!rec)throw Error('Choose a prop from the library');
    const D=Math.max(500,Math.min(120000,Math.round(seconds*1000))),turns=W.snapshot().keys.turn||[];
    const turnAt=t=>turns.length?Performance.sampleKeys('turn',turns,at+t,0):0;
    // Bunny reaches into the pose over BLEND ms; prop key times are pre-mapped so each view lands on its real frame.
    const span=D-2*BLEND,toAction=t=>t<=0?0:Math.max(0,(t-BLEND)*D/span);
    const keys={};for(const [track,v] of Object.entries(rec.hold.pose))keys[track]=[{t:0,v,ease:'auto'},{t:D,v,ease:'auto'}];
    const props=track(rec,turnAt,D).map((p,i)=>({id:'prop360-'+rec.id+'-'+i,name:rec.label+(i?' · view '+(i+1):''),svg:p.svg,size:rec.size,...(p.placement?{placement:p.placement}:{}),keys:p.keys.map(k=>({...k,t:toAction(k.t)}))}));
    return Performance.apply({uid:'prop360-'+rec.id,name:'Hold '+rec.label.toLowerCase(),duration:D,keys,category:'Props',loop:false,props},{at,duration:D,strength:1,blend:BLEND,recent:false});
  }

  // A prop on its own: a free scene object at the chosen turn, moved and scaled like any other prop.
  function place(id,{turn=0,at=playhead}={}){
    const rec=find(id);if(!rec)throw Error('Choose a prop from the library');
    const svg=rec.views[viewKey(rec,turn,PITCH)];
    const uid=BunnyProps.add(svg,{name:rec.label+(turn?' · '+wrap(Math.round(turn/15)*15)+'°':''),attachment:'scene',time:at,size:rec.size});
    // Dead centre is behind Bunny, so it lands beside him, ready to drag.
    const p=BunnyProps.find(uid);BunnyProps.put(uid,{...p.keys[0].value,x:120},{time:p.keys[0].t});return uid;
  }
  let dlg=null;
  function build(){
    dlg=document.createElement('dialog');dlg.id='prop360-dialog';dlg.setAttribute('aria-labelledby','prop360-title');
    const cats=[...new Set(LIB.props.map(p=>p.category))];
    dlg.innerHTML=`<style>
#prop360-dialog{background:#E0A64B;color:#1F1F1D;border:3px solid #1F1F1D;border-radius:14px;padding:0;width:min(1100px,94vw);max-height:88vh}
#prop360-dialog header,#prop360-dialog .p3-row{display:flex;flex-wrap:wrap;gap:10px;align-items:center;padding:10px 16px}
#prop360-dialog header{border-bottom:3px solid #1F1F1D}#prop360-dialog h2{margin:0;font-size:18px}#prop360-dialog header button{margin-left:auto}
#prop360-dialog .p3-body{overflow:auto;max-height:calc(88vh - 150px);padding:0 16px 12px}
#prop360-dialog h3{margin:12px 0 6px;font-size:14px}
#prop360-dialog .p3-grid{display:flex;flex-wrap:wrap;gap:8px}
#prop360-dialog .p3-card{display:flex!important;flex-direction:column!important;align-items:center;justify-content:flex-start;gap:4px;width:120px;height:auto!important;min-height:108px;overflow:visible!important;white-space:normal!important;line-height:1.2;padding:6px!important;background:#E0A64B;color:#1F1F1D;border:2px solid #1F1F1D;border-radius:10px;cursor:pointer;font:inherit;font-size:12px}
#prop360-dialog .p3-card:hover,#prop360-dialog .p3-card:focus-visible{outline:3px solid #1F1F1D;outline-offset:1px}
#prop360-dialog .p3-card img{width:72px!important;height:72px!important;max-width:none}
#prop360-dialog input[type=number]{width:70px}#prop360-dialog .p3-hint{opacity:.8;font-size:12px}
#prop360-status{padding:8px 16px;border-top:3px solid #1F1F1D;min-height:20px;font-size:13px}</style>
<header><h2 id="prop360-title">360° props</h2><span class="p3-hint">Click a prop. In his hand it turns with Bunny. On its own it stays at the angle you pick.</span><button type="button" id="prop360-close">Done</button></header>
<div class="p3-row"><b>Use it</b><label><input type="radio" name="prop360-mode" value="hold" checked> in Bunny's hand</label><label><input type="radio" name="prop360-mode" value="place"> on its own in the scene</label><label for="prop360-turn">turned</label><select id="prop360-turn">${Array.from({length:24},(_,i)=>`<option value="${i*15}">${i*15}°</option>`).join('')}</select><span class="p3-hint">On its own, it lands beside Bunny. Move, scale or key it in Props like any other prop.</span></div>
<div class="p3-row"><label for="prop360-seconds"><b>Hold for</b></label><input type="number" id="prop360-seconds" min="0.5" max="120" step="0.5" value="3"><span>seconds from the playhead</span><span class="p3-hint">The arm pose is keyed for the same span, so you can change it afterwards like any other keys.</span></div>
<div class="p3-body">${cats.map(c=>`<h3>${esc(c)}</h3><div class="p3-grid">${LIB.props.filter(p=>p.category===c).map(p=>`<button type="button" class="p3-card" data-prop="${esc(p.id)}" title="${esc(p.grip)}"><img alt="" src="data:image/svg+xml;charset=utf-8,${encodeURIComponent(p.views['30_30'])}"><span>${esc(p.label)}</span></button>`).join('')}</div>`).join('')}</div>
<div id="prop360-status" role="status"></div>`;
    document.body.append(dlg);const q=s=>dlg.querySelector(s),status=t=>q('#prop360-status').textContent=t;
    q('#prop360-close').onclick=()=>dlg.close();
    for(const b of dlg.querySelectorAll('[data-prop]'))b.onclick=()=>{
      try{const rec=find(b.dataset.prop);if(dlg.querySelector('[name=prop360-mode]:checked').value==='place'){place(rec.id,{turn:+q('#prop360-turn').value});status(rec.label+' placed in the scene. Select it in Props to move or scale it.');if(typeof applyPose==='function')applyPose(playhead);return;}const r=hold(rec.id,{seconds:+q('#prop360-seconds').value||3});status(rec.label+' added: '+r.props.length+' view'+(r.props.length>1?'s':'')+(r.skipped.length?'. Kept protected tracks: '+r.skipped.join(', ')+'.':'.'));if(typeof applyPose==='function')applyPose(playhead);}
      catch(e){status(e.message||String(e));}
    };
  }
  function open(){if(!dlg)build();if(!dlg.open)dlg.showModal();}
  const addMenu=()=>{try{window.DoodleMenu?.add('animate',{id:'animate:prop360',label:'360° props…',run:open})}catch{}};addMenu();DoodleSurfaces.onWindow('bunny-studio-ready',addMenu,{once:true});
  return{open,hold,place,frame,track,viewKey,list:()=>LIB.props.map(p=>({id:p.id,label:p.label,category:p.category,hands:p.hold.hand}))};
})();
window.DoodlePropLibrary360=PropLibrary360;
