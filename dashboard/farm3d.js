(function(){
'use strict';
const outlines=[
[[-34,-20],[-18,-23],[-15,-6],[-37,-5],[-40,-13]],
[[-14,-23],[6,-22],[9,-7],[-12,-6]],
[[11,-21],[27,-19],[38,-10],[35,-4],[12,-6]],
[[-37,-1],[-15,-2],[-14,16],[-22,24],[-35,17],[-41,8]],
[[-11,-2],[9,-3],[13,15],[6,24],[-12,21]],
[[13,-2],[36,0],[39,8],[31,20],[16,23],[16,14]]
];
const centers=[[-27,-13],[-3,-14],[24,-12],[-27,9],[0,10],[26,11]];
const names={watching:'Watching flight',accumulating:'DD accumulating',spray_window:'Window open',window_closed:'Window closed'};
function inside(x,z,poly){let hit=false;for(let i=0,j=poly.length-1;i<poly.length;j=i++){const a=poly[i],b=poly[j];if((a[1]>z)!==(b[1]>z)&&x<(b[0]-a[0])*(z-a[1])/(b[1]-a[1])+a[0])hit=!hit;}return hit;}
function mount(container,initial){
 let ctx=initial,dead=false,raf=0,view='orbit',selected=ctx.block,tween=null;
 const T=window.THREE;
 container.classList.add('farm3d-host');
 function fallback(reason){
  container.classList.add('farm3d-fallback');
  const draw=()=>{container.innerHTML=`<div class="farm3d-fallback-note">3D view unavailable on this device · interactive orchard map</div>${window.FOFarm?window.FOFarm.map(ctx,{large:true}):'<p>Use the block selector to explore the orchard.</p>'}`;};
  const choose=e=>{const b=e.target.closest('[data-block]');if(b){e.stopPropagation();ctx.actions.update({block:b.dataset.block});}};
  const key=e=>{if((e.key==='Enter'||e.key===' ')&&e.target.closest('[data-block]')){e.preventDefault();choose(e);}};
  draw();container.addEventListener('click',choose);container.addEventListener('keydown',key);
  return {update(next){ctx=next;draw();},destroy(){container.removeEventListener('click',choose);container.removeEventListener('keydown',key);container.innerHTML='';container.classList.remove('farm3d-host','farm3d-fallback');},home(){},focus(id){ctx.actions.update({block:id});},setView(){},zoom(){},setAutoRotate(){},getState(){return {fallback:true,reason,view:'2d',autoRotate:false,selected:ctx.block};}};
 }
 if(!T||!T.OrbitControls)return fallback('Three.js is unavailable');
 let renderer;
 try{renderer=new T.WebGLRenderer({antialias:true,alpha:false,powerPreference:'high-performance'});}catch(e){return fallback('WebGL is unavailable');}
 renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.75));
 renderer.shadowMap.enabled=true;renderer.shadowMap.type=T.PCFSoftShadowMap;
 renderer.outputColorSpace=T.SRGBColorSpace;renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=1.25;
 const scene=new T.Scene(),camera=new T.PerspectiveCamera(40,1,.1,700);
 const canvas=renderer.domElement;canvas.className='farm3d-canvas';canvas.setAttribute('aria-label','Interactive 3D orchard. Drag to orbit, wheel or pinch to zoom. Select a labeled block.');canvas.setAttribute('role','img');canvas.tabIndex=0;canvas.setAttribute('aria-label','Interactive 3D orchard. Drag to orbit, scroll or pinch to zoom. Arrow keys pan; R resets; T shows overhead. Select a labeled block.');container.appendChild(canvas);
 const labels=document.createElement('div');labels.className='farm3d-labels';container.appendChild(labels);
 const controls=new T.OrbitControls(camera,canvas);controls.enableDamping=true;controls.dampingFactor=.07;controls.minDistance=24;controls.maxDistance=500;controls.maxPolarAngle=Math.PI*.48;controls.minPolarAngle=.03;controls.enablePan=true;controls.screenSpacePanning=false;controls.autoRotateSpeed=.4;controls.listenToKeyEvents(canvas);controls.target.set(0,0,0);camera.position.set(84,80,100);
 controls.addEventListener('start',()=>{tween=null;});
 const hemi=new T.HemisphereLight(0xdbefff,0x596044,2.4);scene.add(hemi);
 const sun=new T.DirectionalLight(0xffe4b4,3.2);sun.position.set(-38,80,30);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);Object.assign(sun.shadow.camera,{left:-65,right:65,top:65,bottom:-65,near:1,far:180});sun.shadow.normalBias=.08;sun.shadow.bias=-.0002;sun.shadow.radius=3;scene.add(sun);
 const mat=(color,extra={})=>new T.MeshStandardMaterial({color,roughness:1,...extra});
 const grass=mat(0x638052),earth=mat(0x655643),pathMat=mat(0xc7b68b),trunkMat=mat(0x655242),leafMat=mat(0x416943),stoneMat=mat(0x8b927c);
 const geometries=new Set(),materials=new Set();
 const remember=o=>{if(o.geometry)geometries.add(o.geometry);if(o.material)(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>materials.add(m));return o;};
 function mesh(geometry,material,x=0,y=0,z=0){const m=remember(new T.Mesh(geometry,material));m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;scene.add(m);return m;}
 function shape(poly){const s=new T.Shape();poly.forEach(([x,z],i)=>i?s.lineTo(x,-z):s.moveTo(x,-z));s.closePath();return s;}
 function plate(poly,material,y=.04,depth=0){const g=depth?new T.ExtrudeGeometry(shape(poly),{depth,bevelEnabled:false}):new T.ShapeGeometry(shape(poly));g.rotateX(-Math.PI/2);return mesh(g,material,0,y,0);}
 const edge=[];for(let i=0;i<64;i++){const a=i/64*Math.PI*2;const r=1+.045*Math.sin(a*5)+.025*Math.cos(a*9);edge.push([Math.cos(a)*49*r,Math.sin(a)*32*r]);}
 plate(edge,earth,-2.4,2.35);plate(edge,grass,0,.12);
 // A darker underside gives the terrain a legible cutaway silhouette.
 const lower=edge.map(([x,z])=>[x*.975,z*.975]);plate(lower,mat(0x403e33),-3,.65);
 const floor=mesh(new T.PlaneGeometry(1600,1600),mat(0x10212b),0,-3.1,0);floor.rotation.x=-Math.PI/2;floor.castShadow=false;
 const outlineMaterials=[],groundMaterials=[],blockMeshes=[],labelItems=[];
 function tube(points,radius,material,closed=false){const curve=new T.CatmullRomCurve3(points.map(p=>new T.Vector3(...p)),closed,'catmullrom',.2);return mesh(new T.TubeGeometry(curve,Math.max(32,points.length*8),radius,5,closed),material);}
 function lane(points,width){const curve=new T.CatmullRomCurve3(points.map(([x,z])=>new T.Vector3(x,.16,z)));const verts=[],indices=[];for(let i=0;i<=90;i++){const t=i/90,p=curve.getPoint(t),v=curve.getTangent(t),side=new T.Vector3(-v.z,0,v.x).normalize().multiplyScalar(width/2);verts.push(p.x+side.x,p.y,p.z+side.z,p.x-side.x,p.y,p.z-side.z);if(i<90){const k=i*2;indices.push(k,k+1,k+2,k+1,k+3,k+2);}}const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(verts,3));g.setIndex(indices);g.computeVertexNormals();const m=mesh(g,pathMat);m.material.side=T.DoubleSide;m.castShadow=false;}
 lane([[-47,-3],[-26,-3],[-6,-4],[12,-4],[32,-2],[46,2]],2.1);
 lane([[-17,-28],[-14,-14],[-13,-3],[-12,11],[-13,29]],1.6);
 lane([[9,-27],[10,-15],[11,-4],[14,9],[12,29]],1.7);
 const treePositions=[];
 ctx.blocks.slice(0,6).forEach((b,i)=>{
  const poly=outlines[i],gm=mat(i%2?0x738751:0x6b804c);groundMaterials.push(gm);const region=plate(poly,gm,.17);region.userData.block=b.id;blockMeshes.push(region);
  const om=mat(0x8caa76,{emissive:0x213925,emissiveIntensity:.2});outlineMaterials.push(om);tube(poly.map(([x,z])=>[x,.30,z]),.12,om,true);
  for(let z=-24;z<=25;z+=3.4){for(let x=-41;x<=40;x+=3.2){const xx=x+Math.sin(z*.15)*.7;if(inside(xx,z,poly)&&inside(xx+.9,z+.8,poly)&&inside(xx-.9,z-.8,poly))treePositions.push([xx,z,.85+((Math.round(x*7+z*3)%11+11)%11)/34]);}}
  const [cx,cz]=centers[i];
  const button=document.createElement('button');button.className='farm3d-label';button.type='button';button.dataset.farm3dBlock=b.id;button.addEventListener('pointerdown',e=>e.stopPropagation());button.addEventListener('click',e=>{e.stopPropagation();ctx.actions.update({block:b.id});});labels.appendChild(button);labelItems.push({button,id:b.id,point:new T.Vector3(cx,6.5,cz),index:i});
  const trapLocations=[poly[0],poly[Math.floor(poly.length/2)],poly[poly.length-1]];
  (b.traps||[]).forEach((id,j)=>{const p=trapLocations[j%3],x=p[0]*.84+cx*.16,z=p[1]*.84+cz*.16;mesh(new T.CylinderGeometry(.055,.075,2.5,5),mat(0xddd5aa),x,1.4,z);const flag=mesh(new T.BoxGeometry(.7,.85,.07),mat(0xf2bc67),x,2.4,z);flag.rotation.y=.35;flag.userData.trap=id;mesh(new T.ConeGeometry(.52,.35,4),mat(0xc07143),x,2.96,z);});
 });
 // Instancing keeps hundreds of individually varied three-dimensional trees inexpensive.
 const treeCount=treePositions.length, dummy=new T.Object3D();
 const trunks=remember(new T.InstancedMesh(new T.CylinderGeometry(.12,.18,1.4,5),trunkMat,treeCount));trunks.castShadow=true;scene.add(trunks);
 const crowns=remember(new T.InstancedMesh(new T.DodecahedronGeometry(1,0),leafMat,treeCount*3));crowns.castShadow=true;crowns.receiveShadow=true;scene.add(crowns);
 treePositions.forEach(([x,z,s],i)=>{dummy.position.set(x,.85,z);dummy.scale.set(s,s,s);dummy.rotation.set(0,0,0);dummy.updateMatrix();trunks.setMatrixAt(i,dummy.matrix);for(let j=0;j<3;j++){dummy.position.set(x+(j-1)*.38,1.7+s*.5+(j===1?.6:0),z+(j%2)*.32);dummy.scale.set(s*(j===1?1:1.05),s*(j===1?1.1:.9),s*.92);dummy.rotation.set(i*.1,j*.7,i*.08);dummy.updateMatrix();crowns.setMatrixAt(i*3+j,dummy.matrix);crowns.setColorAt(i*3+j,new T.Color().setHSL(.25+(i%7)*.009,.24+(j*.025),.27+(i%5)*.022));}});trunks.instanceMatrix.needsUpdate=true;crowns.instanceMatrix.needsUpdate=true;
 // Boundary hedges and post-and-wire fence follow the actual irregular perimeter.
 const hedge=remember(new T.InstancedMesh(new T.DodecahedronGeometry(1,0),mat(0x456544),edge.length));hedge.castShadow=true;hedge.receiveShadow=true;scene.add(hedge);
 edge.forEach(([x,z],i)=>{dummy.position.set(x*.98,.8,z*.98);dummy.scale.set(1.45,.9,1.05);dummy.rotation.set(0,i*.3,0);dummy.updateMatrix();hedge.setMatrixAt(i,dummy.matrix);if(i%2===0){mesh(new T.CylinderGeometry(.08,.12,1.6,5),trunkMat,x, .75,z);}});hedge.instanceMatrix.needsUpdate=true;
 tube(edge.map(([x,z])=>[x,1.15,z]),.025,mat(0x888a72),true);
 tube(edge.map(([x,z])=>[x,.65,z]),.025,mat(0x888a72),true);
 // Pond, reeds, stones, a little jetty and a farmhouse at the access lane.
 const pond=[];for(let i=0;i<36;i++){const a=i/36*Math.PI*2,r=1+.12*Math.sin(a*3);pond.push([41+Math.cos(a)*5*r,12+Math.sin(a)*7*r]);}
 plate(pond.map(([x,z])=>[41+(x-41)*1.12,12+(z-12)*1.10]),stoneMat,.18);
 const water=plate(pond,mat(0x4b9294,{roughness:.3,metalness:.25,transparent:true,opacity:.92}),.22);water.castShadow=false;
 for(let j=0;j<4;j++){const ripple=mesh(new T.TorusGeometry(1.0+j*.72,.025,3,40),mat(0x91b8ad),41,.25,12);ripple.rotation.x=-Math.PI/2;ripple.scale.y=.72;ripple.castShadow=false;}
 for(let i=0;i<12;i++){const a=i*.55,x=41+Math.cos(a)*5.3,z=12+Math.sin(a)*7.1;mesh(new T.ConeGeometry(.18,.8+(i%3)*.3,4),mat(0x80925b),x,.65,z);}
 mesh(new T.BoxGeometry(2.6,.22,4.7),mat(0xb69d75),36,.5,11);
 const barn=mesh(new T.BoxGeometry(7,3.3,5),mat(0xba8262),-7,1.9,27);
 const roof=mesh(new T.CylinderGeometry(0,4.7,3.1,4,1),mat(0x3f6267),-7,4.7,27);roof.rotation.y=Math.PI/4;roof.scale.z=.8;
 mesh(new T.BoxGeometry(1.8,2.7,.08),mat(0x485c50),-7,1.65,29.54);
 for(const x of [-9.4,-4.6])mesh(new T.BoxGeometry(1.0,1,.09),mat(0xf1cf88,{emissive:0x6f5125,emissiveIntensity:.25}),x,2.3,29.55);
 mesh(new T.BoxGeometry(.7,2,.7),mat(0x756b5b),-5,5.1,26.4);
 // Meadow rocks make the farm read as a place, rather than a diagram floating in space.
 for(let i=0;i<18;i++){const a=i*2.399,x=Math.cos(a)*(43+i%3),z=Math.sin(a)*(27+i%2);const rock=mesh(new T.DodecahedronGeometry(.4+(i%3)*.18,0),stoneMat,x,.28,z);rock.scale.y=.65;rock.rotation.set(i,.3*i,.5);}
 const project=new T.Vector3(),ray=new T.Raycaster(),pointer=new T.Vector2();let startPoint=null;
 const pointerDown=e=>{startPoint=[e.clientX,e.clientY];};
 const pointerUp=e=>{if(!startPoint||Math.hypot(e.clientX-startPoint[0],e.clientY-startPoint[1])>5)return;startPoint=null;const r=canvas.getBoundingClientRect();pointer.set((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1);ray.setFromCamera(pointer,camera);const hit=ray.intersectObjects(blockMeshes)[0];if(hit)ctx.actions.update({block:hit.object.userData.block});};
 canvas.addEventListener('pointerdown',pointerDown);canvas.addEventListener('pointerup',pointerUp);
 let width=1,height=1;
 function resize(){width=Math.max(1,container.clientWidth);height=Math.max(1,container.clientHeight);renderer.setSize(width,height,false);camera.aspect=width/height;camera.updateProjectionMatrix();}
 const observer=new ResizeObserver(resize);observer.observe(container);resize();
 function theme(){const light=document.documentElement.dataset.theme==='light';scene.background=new T.Color(light?0xdde6df:0x10212b);scene.fog=new T.Fog(light?0xdde6df:0x10212b,350,850);floor.material.color.setHex(light?0xdde6df:0x10212b);}
 const themeObserver=new MutationObserver(theme);themeObserver.observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});theme();
 function update(next){ctx=next;selected=ctx.block;labelItems.forEach(({button,id,index})=>{const b=ctx.blocks.find(x=>x.id===id),s=ctx.status(id),active=id===selected,open=s.status==='spray_window';button.classList.toggle('farm3d-selected',active);button.classList.toggle('farm3d-window',open);button.setAttribute('aria-pressed',String(active));button.setAttribute('aria-label',`${b.name}, ${b.variety}, ${ctx.count(id)} counted today, ${names[s.status]||s.status}, ${ctx.num(s.dd_since_biofix,1)} degree-days`);button.innerHTML=`<span class="farm3d-label-title">${ctx.esc(b.name)} <b>${ctx.num(ctx.count(id))}</b></span><span class="farm3d-label-detail">${ctx.esc(b.variety)} · ${ctx.num(b.acres,1)} ac</span><span class="farm3d-label-status">${open?'Window open':s.biofix_date?ctx.num(s.dd_since_biofix,0)+' DD':names[s.status]||s.status}</span>`;outlineMaterials[index].color.setHex(active?0xffd18b:open?0xd6ad69:0x9caf78);outlineMaterials[index].emissive.setHex(active?0xb98232:0x213925);outlineMaterials[index].emissiveIntensity=active?.55:.12;groundMaterials[index].color.setHex(active?0x8b8a50:index%2?0x738751:0x6b804c);});}
 function move(pos,target,duration=650){tween={start:performance.now(),duration,from:camera.position.clone(),to:pos.clone(),targetFrom:controls.target.clone(),targetTo:target.clone()};}
 function homePosition(){return new T.Vector3(84,80,100).multiplyScalar(Math.max(1,1/camera.aspect));} function home(){resize();view='orbit';move(homePosition(),new T.Vector3(0,0,0));}
 function focus(id){const i=ctx.blocks.findIndex(b=>b.id===id);if(i<0||i>=centers.length)return;const [x,z]=centers[i];const target=new T.Vector3(x,1,z),direction=camera.position.clone().sub(controls.target).normalize();move(target.clone().add(direction.multiplyScalar(width<650?62:45)),target);}
 function setView(next){resize();view=next==='top'?'top':'orbit';move(view==='top'?new T.Vector3(0,Math.max(110,155/camera.aspect),.1):homePosition(),new T.Vector3());}
 function zoom(delta){tween=null;const offset=camera.position.clone().sub(controls.target);offset.multiplyScalar(Math.exp(Number(delta)*.12));offset.clampLength(controls.minDistance,controls.maxDistance);camera.position.copy(controls.target).add(offset);controls.update();}
 function frame(now){if(dead)return;raf=requestAnimationFrame(frame);if(tween){const t=Math.min(1,(now-tween.start)/tween.duration),e=1-Math.pow(1-t,3);camera.position.lerpVectors(tween.from,tween.to,e);controls.target.lerpVectors(tween.targetFrom,tween.targetTo,e);if(t===1)tween=null;}controls.update();renderer.render(scene,camera);labelItems.forEach(({button,point,id})=>{project.copy(point).project(camera);const x=(project.x*.5+.5)*width,y=(-project.y*.5+.5)*height;const show=project.z<1&&project.z>-1&&x>15&&x<width-15&&y>30&&y<height-15;button.hidden=!show;button.style.transform=`translate(${x.toFixed(1)}px,${y.toFixed(1)}px) translate(-50%,-100%)`;button.style.zIndex=id===selected?'3':'2';});}
 update(ctx);camera.position.copy(homePosition());raf=requestAnimationFrame(frame);
 const contextLost=e=>{e.preventDefault();container.classList.add('farm3d-context-lost');};canvas.addEventListener('webglcontextlost',contextLost);
 return {update,home,focus,setView,zoom,setAutoRotate(value){controls.autoRotate=Boolean(value);},getState(){return {fallback:false,view,selected,autoRotate:controls.autoRotate,azimuth:controls.getAzimuthalAngle(),distance:camera.position.distanceTo(controls.target),renderer:'WebGL / Three.js',camera:camera.position.toArray(),target:controls.target.toArray(),trees:treeCount,traps:ctx.blocks.reduce((n,b)=>n+(b.traps?.length||0),0)};},destroy(){if(dead)return;dead=true;cancelAnimationFrame(raf);observer.disconnect();themeObserver.disconnect();controls.dispose();canvas.removeEventListener('pointerdown',pointerDown);canvas.removeEventListener('pointerup',pointerUp);canvas.removeEventListener('webglcontextlost',contextLost);geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());trunks.dispose();crowns.dispose();hedge.dispose();sun.shadow.dispose();renderer.dispose();renderer.forceContextLoss();container.innerHTML='';container.classList.remove('farm3d-host','farm3d-context-lost');}};
}
window.FOFarm3D={mount};
})();
