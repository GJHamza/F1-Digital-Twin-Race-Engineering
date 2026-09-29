// F1 DIGITAL TWIN — FULL SIMULATOR WITH ALL FEATURES
(function(){
'use strict';
var API_URL='/telemetry', SEND_INTERVAL=1000;
var CAR_PATHS=['car/car2.glb','car/car3.glb','car/car4.glb','car/car5.glb'];
var CAR_NAMES=['AERO PHANTOM','NEON STRIKER','TITAN X','ECLIPSE RS'];
var CAR_COLORS=['#00edff','#ff00ff','#ffaa00','#00ff66'];
var CAR_THEMES=['williams','mclaren','redbull','mercedes'];
var mode='HOME',carIndex=-1,lastSend=0,carCache=[],dataPointsSent=0,runActive=false,runTimerVal=30,runTelemetryData=[],runIntervalId=null;
var currentSpeed=0,targetSpeed=0,windActive=false,windForce=0,targetWind=0;
var brakeTest=false,tireStress=false,roadRunning=false;
var tireTemps=[90,90,90,90],torque=0,gForce=1,dragCoeff=0,downforce=0;
var throttlePercent=0,brakePercent=0;
// Tire wear (0-100%) — degrades over time when road is running
var tireWear=[0,0,0,0];
// GPS circuit position — parameterised lap along an oval-ish track
var lapAngle=0,posX=0,posZ=0;
var setupDownforce=50,setupEngineMix=5;
var $=function(id){return document.getElementById(id);};

// ── THEME SYSTEM ──
document.querySelectorAll('.theme-btn').forEach(function(btn){
    btn.addEventListener('click',function(){
        document.documentElement.setAttribute('data-theme',this.dataset.theme);
        document.querySelectorAll('.theme-btn').forEach(function(b){b.classList.remove('active');});
        this.classList.add('active');
    });
});

// ── PARTICLES BACKGROUND ──
var pCanvas=$('particles-canvas'),pCtx=pCanvas.getContext('2d');
var dots=[];
function initParticles(){
    pCanvas.width=window.innerWidth;pCanvas.height=window.innerHeight;
    dots=[];
    for(var i=0;i<80;i++) dots.push({x:Math.random()*pCanvas.width,y:Math.random()*pCanvas.height,vx:(Math.random()-0.5)*0.3,vy:(Math.random()-0.5)*0.3,r:Math.random()*1.5+0.5});
}
function drawParticles(){
    if(mode!=='HOME'){return;}
    pCtx.clearRect(0,0,pCanvas.width,pCanvas.height);
    var cs=getComputedStyle(document.documentElement);
    var col=cs.getPropertyValue('--primary').trim()||'#00edff';
    dots.forEach(function(d){
        d.x+=d.vx;d.y+=d.vy;
        if(d.x<0||d.x>pCanvas.width)d.vx*=-1;
        if(d.y<0||d.y>pCanvas.height)d.vy*=-1;
        pCtx.beginPath();pCtx.arc(d.x,d.y,d.r,0,Math.PI*2);
        pCtx.fillStyle=col;pCtx.globalAlpha=0.3;pCtx.fill();
    });
    // Lines between close dots
    for(var i=0;i<dots.length;i++){
        for(var j=i+1;j<dots.length;j++){
            var dx=dots[i].x-dots[j].x,dy=dots[i].y-dots[j].y;
            var dist=Math.sqrt(dx*dx+dy*dy);
            if(dist<120){
                pCtx.beginPath();pCtx.moveTo(dots[i].x,dots[i].y);pCtx.lineTo(dots[j].x,dots[j].y);
                pCtx.strokeStyle=col;pCtx.globalAlpha=0.06*(1-dist/120);pCtx.stroke();
            }
        }
    }
    pCtx.globalAlpha=1;
}
initParticles();
window.addEventListener('resize',initParticles);

// ── COUNT-UP ANIMATION ──
var counted=false;
function countUp(){
    if(counted)return;counted=true;
    document.querySelectorAll('.count-up').forEach(function(el){
        var target=parseInt(el.dataset.target),cur=0;
        var step=Math.ceil(target/40);
        var iv=setInterval(function(){cur+=step;if(cur>=target){cur=target;clearInterval(iv);}el.textContent=cur;},30);
    });
}
// Trigger on scroll
if($('home-screen'))$('home-screen').addEventListener('scroll',function(){
    var about=$('about');
    if(about&&about.getBoundingClientRect().top<window.innerHeight*0.8)countUp();
});

// ── GARAGE SCENE ──
var garageRenderer,garageScene,garageCam,garageCarGroup,garageBuilt=false;
function initGarage(){
    if(garageBuilt)return;garageBuilt=true;
    var c=$('garage-3d');
    garageScene=new THREE.Scene();garageScene.background=new THREE.Color(0xeef1f6);
    garageCam=new THREE.PerspectiveCamera(40,600/300,0.1,200);
    garageCam.position.set(6,3.5,6);garageCam.lookAt(0,0.5,0);
    garageRenderer=new THREE.WebGLRenderer({antialias:true});
    garageRenderer.setSize(600,300);garageRenderer.setPixelRatio(Math.min(devicePixelRatio,2));
    c.appendChild(garageRenderer.domElement);
    garageScene.add(new THREE.AmbientLight(0xffffff,1));
    var d1=new THREE.DirectionalLight(0xffffff,0.8);d1.position.set(5,8,5);garageScene.add(d1);
    var d2=new THREE.DirectionalLight(0x00edff,0.4);d2.position.set(-4,5,-3);garageScene.add(d2);
    var plat=new THREE.Mesh(new THREE.CylinderGeometry(4,4.2,0.3,64),new THREE.MeshStandardMaterial({color:0x111,roughness:0.1,metalness:0.9}));
    plat.position.y=-0.15;garageScene.add(plat);
    var ring=new THREE.Mesh(new THREE.TorusGeometry(4.1,0.06,16,128),new THREE.MeshBasicMaterial({color:0x00edff}));
    ring.rotation.x=Math.PI/2;ring.position.y=0.01;garageScene.add(ring);
    garageCarGroup=new THREE.Group();garageScene.add(garageCarGroup);
}

// ── BENCH SCENE ──
var benchRenderer,benchScene,benchCam,benchCarGroup,controls;
var roadStripes=[],windParticles=[],windGroup,benchInit=false;
function initBench(){
    if(benchInit)return;benchInit=true;
    var c=$('bench-3d');
    benchScene=new THREE.Scene();benchScene.background=new THREE.Color(0xeef1f6);
    benchCam=new THREE.PerspectiveCamera(50,1,0.1,500);benchCam.position.set(5,4,8);
    benchRenderer=new THREE.WebGLRenderer({antialias:true});c.appendChild(benchRenderer.domElement);
    benchScene.add(new THREE.AmbientLight(0xffffff,1));
    var b1=new THREE.DirectionalLight(0xffffff,0.7);b1.position.set(5,10,5);benchScene.add(b1);
    var b2=new THREE.DirectionalLight(0x00edff,0.4);b2.position.set(-5,8,-3);benchScene.add(b2);
    var b3=new THREE.DirectionalLight(0xff5500,0.2);b3.position.set(0,5,-8);benchScene.add(b3);
    var rg=new THREE.Group();benchScene.add(rg);
    var rm=new THREE.Mesh(new THREE.PlaneGeometry(8,40),new THREE.MeshStandardMaterial({color:0x1a1a1a,roughness:0.7}));
    rm.rotation.x=-Math.PI/2;rg.add(rm);
    for(var i=-18;i<20;i+=2){var s=new THREE.Mesh(new THREE.PlaneGeometry(0.15,0.8),new THREE.MeshBasicMaterial({color:0x444}));s.rotation.x=-Math.PI/2;s.position.set(0,0.01,i);rg.add(s);roadStripes.push(s);}
    var sm=new THREE.MeshBasicMaterial({color:0x00edff});
    [[-4,0.01,0],[4,0.01,0]].forEach(function(p){var l=new THREE.Mesh(new THREE.PlaneGeometry(0.1,40),sm);l.rotation.x=-Math.PI/2;l.position.set(p[0],p[1],p[2]);rg.add(l);});
    windGroup=new THREE.Group();benchScene.add(windGroup);
    var pm=new THREE.MeshBasicMaterial({color:0x00edff,transparent:true,opacity:0.5});
    for(var j=0;j<80;j++){var p=new THREE.Mesh(new THREE.SphereGeometry(0.04,4,4),pm);p.position.set((Math.random()-0.5)*8,Math.random()*3+0.2,(Math.random()-0.5)*20);windGroup.add(p);windParticles.push(p);}
    windGroup.visible=false;
    benchCarGroup=new THREE.Group();benchScene.add(benchCarGroup);
    controls=new THREE.OrbitControls(benchCam,benchRenderer.domElement);
    controls.target.set(0,1,0);controls.enablePan=false;controls.maxPolarAngle=Math.PI/2.1;controls.minDistance=4;controls.maxDistance=18;controls.update();
    resizeBench();
}
function resizeBench(){if(!benchRenderer)return;var r=$('bench-3d').getBoundingClientRect();if(r.width<1)return;benchCam.aspect=r.width/r.height;benchCam.updateProjectionMatrix();benchRenderer.setSize(r.width,r.height);}
window.addEventListener('resize',resizeBench);

// ── CAR LOADING ──
var loader=new THREE.GLTFLoader();
function makeFallback(){var g=new THREE.Group(),b=new THREE.MeshStandardMaterial({color:0xcc0000,roughness:0.3,metalness:0.7}),gl=new THREE.MeshStandardMaterial({color:0x00edff,emissive:0x00edff,emissiveIntensity:0.5}),dk=new THREE.MeshStandardMaterial({color:0x333,roughness:0.9});var ch=new THREE.Mesh(new THREE.BoxGeometry(1.8,0.5,5.5),b);ch.position.y=0.35;g.add(ch);g.add(Object.assign(new THREE.Mesh(new THREE.BoxGeometry(1,0.4,1.2),dk),{position:new THREE.Vector3(0,0.7,-0.2)}));g.add(Object.assign(new THREE.Mesh(new THREE.BoxGeometry(2.8,0.08,0.5),gl),{position:new THREE.Vector3(0,0.15,4.5)}));g.add(Object.assign(new THREE.Mesh(new THREE.BoxGeometry(2.4,0.08,0.7),gl),{position:new THREE.Vector3(0,1.1,-2.5)}));return g;}
function processModel(m){var box=new THREE.Box3().setFromObject(m);var size=new THREE.Vector3();box.getSize(size);var s=5/Math.max(size.x,size.y,size.z);m.scale.setScalar(s);var nb=new THREE.Box3().setFromObject(m);var c=new THREE.Vector3();nb.getCenter(c);m.position.x-=c.x;m.position.z-=c.z;m.position.y-=nb.min.y;m.traverse(function(ch){if(ch.isMesh){ch.castShadow=true;ch.receiveShadow=true;}});}
function loadCarInto(idx,grp){while(grp.children.length)grp.remove(grp.children[0]);if(carCache[idx]){grp.add(carCache[idx].clone());return;}loader.load(CAR_PATHS[idx],function(g){processModel(g.scene);carCache[idx]=g.scene;grp.add(g.scene.clone());},null,function(){var fb=makeFallback();carCache[idx]=fb;grp.add(fb.clone());});}

// ── CARDS ──
var CAR_TEAM_NAMES=['WILLIAMS','McLAREN','RED BULL','MERCEDES'];
function buildCards(){var c=$('car-cards');if(!c)return;c.innerHTML='';CAR_NAMES.forEach(function(name,i){var card=document.createElement('div');card.className='car-card';card.innerHTML='<div class="card-color" style="background:'+CAR_COLORS[i]+';box-shadow:0 0 12px '+CAR_COLORS[i]+'55;"></div><div class="card-name">'+name+'</div><div class="card-team" style="color:'+CAR_COLORS[i]+'">'+CAR_TEAM_NAMES[i]+'</div>';card.addEventListener('click',function(){selectCar(i);});c.appendChild(card);});}
function selectCar(idx){carIndex=idx;document.querySelectorAll('.car-card').forEach(function(c,i){c.classList.toggle('selected',i===idx);});$('btn-start').classList.remove('hidden');loadCarInto(idx,garageCarGroup);
    // Auto-apply team theme
    var theme=CAR_THEMES[idx];
    document.documentElement.setAttribute('data-theme',theme);
    document.querySelectorAll('.theme-btn').forEach(function(b){b.classList.toggle('active',b.dataset.theme===theme);});
}

// ── NAVIGATION ──
function goToGarage(){mode='GARAGE';$('home-screen').classList.add('hidden');$('garage-screen').classList.remove('hidden');initGarage();buildCards();}
$('btn-enter-garage').addEventListener('click',goToGarage);
$('btn-enter-garage-2').addEventListener('click',goToGarage);
$('btn-start').addEventListener('click',function(){if(carIndex<0)return;mode='BENCH';$('garage-screen').classList.add('hidden');$('bench-screen').classList.remove('hidden');initBench();setTimeout(function(){resizeBench();loadCarInto(carIndex,benchCarGroup);},100);resetBench();});
$('btn-back').addEventListener('click',function(){mode='GARAGE';$('bench-screen').classList.add('hidden');$('garage-screen').classList.remove('hidden');resetBench();});
$('btn-garage-home').addEventListener('click',function(){window.location.href='/';});
$('btn-bench-home').addEventListener('click',function(){window.location.href='/';});

// ── BENCH CONTROLS ──
function resetBench(){newSession();currentSpeed=0;targetSpeed=0;windActive=false;windForce=0;targetWind=0;brakeTest=false;tireStress=false;roadRunning=false;tireTemps=[90,90,90,90];torque=0;gForce=1;dragCoeff=0;downforce=0;throttlePercent=0;brakePercent=0;$('slider-speed').value=0;$('slider-wind').value=0;$('val-speed').textContent='0 km/h';$('val-wind').textContent='0 kts';$('test-status').textContent='IDLE — AWAITING INSTRUCTIONS';if(windGroup)windGroup.visible=false;document.querySelectorAll('.btn-test').forEach(function(b){b.classList.remove('running');});runActive=false;if(runIntervalId){clearInterval(runIntervalId);runIntervalId=null;}if($('session-timer-text')){$('session-timer-text').textContent='READY FOR RUN';$('session-progress-fill').style.width='0%';$('btn-start-run').classList.remove('hidden');$('btn-start-run').disabled=false;$('btn-download-run').classList.add('hidden');$('link-dashboard').classList.add('disabled');$('link-dashboard').classList.remove('ready-glow');}}
function toggleRoad(){roadRunning=!roadRunning;$('btn-road').classList.toggle('running',roadRunning);$('test-status').textContent=roadRunning?'ROLLING ROAD — ACTIVE':'ROLLING ROAD — STOPPED';}
function toggleWind(){windActive=!windActive;$('btn-wind').classList.toggle('running',windActive);if(windGroup)windGroup.visible=windActive;$('test-status').textContent=windActive?'WIND TUNNEL — ACTIVE':'WIND TUNNEL — OFF';}
function doBrake(){brakeTest=true;$('btn-brake').classList.add('running');$('test-status').textContent='BRAKE TEST — EMERGENCY STOP';setTimeout(function(){$('btn-brake').classList.remove('running');brakeTest=false;},3000);}
function toggleTires(){tireStress=!tireStress;$('btn-tire').classList.toggle('running',tireStress);$('test-status').textContent=tireStress?'TIRE STRESS — OVERHEATING':'TIRE STRESS — OFF';}

$('btn-road').addEventListener('click',toggleRoad);
$('slider-speed').addEventListener('input',function(){targetSpeed=parseInt(this.value);$('val-speed').textContent=targetSpeed+' km/h';});
$('btn-wind').addEventListener('click',toggleWind);
$('slider-wind').addEventListener('input',function(){targetWind=parseInt(this.value);$('val-wind').textContent=targetWind+' kts';});
$('btn-brake').addEventListener('click',doBrake);
$('btn-tire').addEventListener('click',toggleTires);

// ── PRESETS ──
var PRESETS={qualifying:{speed:340,wind:50,tires:false,brake:false},wet:{speed:200,wind:80,tires:true,brake:false},endurance:{speed:280,wind:30,tires:true,brake:false},emergency:{speed:300,wind:0,tires:false,brake:true}};
document.querySelectorAll('.btn-preset').forEach(function(btn){
    btn.addEventListener('click',function(){
        var p=PRESETS[this.dataset.profile];if(!p)return;
        if(!roadRunning)toggleRoad();
        targetSpeed=p.speed;$('slider-speed').value=p.speed;$('val-speed').textContent=p.speed+' km/h';
        targetWind=p.wind;$('slider-wind').value=p.wind;$('val-wind').textContent=p.wind+' kts';
        if(p.wind>0&&!windActive)toggleWind();
        if(p.wind===0&&windActive)toggleWind();
        if(p.tires&&!tireStress)toggleTires();
        if(!p.tires&&tireStress)toggleTires();
        if(p.brake)setTimeout(doBrake,1500);
        $('test-status').textContent='PROFILE: '+this.dataset.profile.toUpperCase()+' — LOADED';
    });
});

// ── KEYBOARD SHORTCUTS ──
document.addEventListener('keydown',function(e){
    if(mode!=='BENCH')return;
    var k=e.key.toLowerCase();
    if(k===' '||k==='space'){e.preventDefault();toggleRoad();}
    else if(k==='w')toggleWind();
    else if(k==='b')doBrake();
    else if(k==='t')toggleTires();
    else if(k==='f'){e.preventDefault();toggleFullscreen();}
    else if(k==='arrowup'){e.preventDefault();targetSpeed=Math.min(350,targetSpeed+10);$('slider-speed').value=targetSpeed;$('val-speed').textContent=targetSpeed+' km/h';}
    else if(k==='arrowdown'){e.preventDefault();targetSpeed=Math.max(0,targetSpeed-10);$('slider-speed').value=targetSpeed;$('val-speed').textContent=targetSpeed+' km/h';}
});

// ── FULLSCREEN ──
function toggleFullscreen(){var el=$('bench-3d');if(!document.fullscreenElement)el.requestFullscreen().catch(function(){});else document.exitFullscreen();}
$('btn-fullscreen').addEventListener('click',toggleFullscreen);

// ── KAFKA STATUS ──
function checkKafka(){
    fetch(API_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ping:true})})
    .then(function(r){var badge=$('kafka-badge');if(r.ok){badge.textContent='● LIVE';badge.className='kafka-badge live';}else{badge.textContent='● OFFLINE';badge.className='kafka-badge offline';}})
    .catch(function(){var badge=$('kafka-badge');badge.textContent='● OFFLINE';badge.className='kafka-badge offline';});
}
setInterval(checkKafka,5000);

// ── MAIN LOOP ──
function tick(){
    requestAnimationFrame(tick);
    drawParticles();
    if(mode==='GARAGE'){if(garageCarGroup)garageCarGroup.rotation.y+=0.008;if(garageRenderer)garageRenderer.render(garageScene,garageCam);}
    else if(mode==='BENCH'&&benchInit){
        updateSim();animateRoad();animateWheels();animateWind();updateUI();controls.update();benchRenderer.render(benchScene,benchCam);
        if(Date.now()-lastSend>SEND_INTERVAL&&currentSpeed>1){sendTelemetry();lastSend=Date.now();}
    }
}
function updateSim(){
    var accFactor = 0.02 * (0.7 + (setupEngineMix / 10) * 0.6) / (0.8 + (setupDownforce / 100) * 0.4);
    if(roadRunning){if(brakeTest){currentSpeed+=(0-currentSpeed)*0.08;brakePercent=Math.min(100,brakePercent+8);throttlePercent*=0.9;}else{currentSpeed+=(targetSpeed-currentSpeed)*accFactor;throttlePercent=(targetSpeed/350)*100;brakePercent*=0.95;}}else{currentSpeed+=(0-currentSpeed)*0.05;throttlePercent*=0.9;brakePercent*=0.9;}
    if(windActive)windForce+=(targetWind-windForce)*0.05;else windForce*=0.95;
    var v=currentSpeed/3.6;
    dragCoeff=(0.28+(windForce/100)*0.15)*(0.8+(setupDownforce/100)*0.4);
    downforce=0.5*1.225*v*v*dragCoeff*3.2*(0.5+(setupDownforce/100)*1.0);
    torque=Math.max(0,(currentSpeed/350)*850)*(0.6+(setupEngineMix/10)*0.8);
    gForce=(1+(Math.abs(currentSpeed-targetSpeed)/350)*2)*(0.9+(setupDownforce/100)*0.2);
    if(brakeTest)gForce=Math.min(5,1+(currentSpeed/100)*3);
    for(var i=0;i<4;i++){
        var t=90+(currentSpeed/350)*30*(0.8+(setupEngineMix/10)*0.4);
        if(tireStress)t+=25*(1.3-(setupDownforce/100)*0.6);
        if(brakeTest&&i<2)t+=20;
        tireTemps[i]+=(t-tireTemps[i])*0.02;
    }
    if(roadRunning&&currentSpeed>10){
        var wearRate=0.002*(currentSpeed/350)*(1.2-(setupDownforce/100)*0.4)*(0.7+(setupEngineMix/10)*0.6);
        if(tireStress)wearRate*=3;
        if(brakeTest){wearRate*=2;tireWear[0]=Math.min(100,tireWear[0]+wearRate*1.5);tireWear[1]=Math.min(100,tireWear[1]+wearRate*1.5);}
        for(var j=0;j<4;j++)tireWear[j]=Math.min(100,tireWear[j]+wearRate);
    }
    if(roadRunning&&currentSpeed>5){
        lapAngle+=currentSpeed/350*0.04;
        posX=120*Math.sin(lapAngle)+40*Math.sin(2*lapAngle);
        posZ=80*Math.cos(lapAngle)+20*Math.cos(2*lapAngle);
    }
}
function animateRoad(){var sp=(currentSpeed/350)*0.8;roadStripes.forEach(function(s){s.position.z+=sp;if(s.position.z>20)s.position.z-=40;});}
function animateWheels(){
    if(!benchCarGroup||!benchCarGroup.children[0])return;var spin=(currentSpeed/350)*0.6;
    benchCarGroup.children[0].traverse(function(c){if(!c.isMesh)return;var n=(c.name||'').toLowerCase();if(n.indexOf('wheel')>=0||n.indexOf('tire')>=0||n.indexOf('tyre')>=0||n.indexOf('rim')>=0||n.indexOf('whl')>=0||n.indexOf('disc')>=0)c.rotation.x+=spin;});
    if(currentSpeed>10){var t=Date.now()*0.001,int=currentSpeed/350;benchCarGroup.position.y=Math.sin(t*25)*int*0.008+Math.sin(t*40)*int*0.003;benchCarGroup.rotation.x=Math.sin(t*15)*int*0.002;benchCarGroup.rotation.z=Math.sin(t*18)*int*0.001;}else{benchCarGroup.position.y=0;benchCarGroup.rotation.x=0;benchCarGroup.rotation.z=0;}
    if(brakeTest)benchCarGroup.rotation.x=-0.015;
}
function animateWind(){if(!windActive)return;var ws=(windForce/100)*0.5;windParticles.forEach(function(p){p.position.z-=ws;if(p.position.z<-10)p.position.z=10;p.position.x+=(Math.random()-0.5)*0.03;p.position.x=Math.max(-4,Math.min(4,p.position.x));p.position.y+=(Math.random()-0.5)*0.02;p.position.y=Math.max(0.1,Math.min(3,p.position.y));});}
function updateUI(){
    $('t-speed').textContent=Math.floor(currentSpeed);$('bar-speed').style.width=(currentSpeed/350*100)+'%';
    $('t-drag').textContent=dragCoeff.toFixed(3);$('bar-drag').style.width=(dragCoeff/0.5*100)+'%';
    $('t-downforce').textContent=Math.floor(downforce);$('t-gforce').textContent=gForce.toFixed(2);
    $('t-torque').textContent=Math.floor(torque);$('t-wind').textContent=windForce.toFixed(1);
    $('bar-throttle').style.width=throttlePercent+'%';$('bar-brake').style.width=brakePercent+'%';
    ['fl','fr','rl','rr'].forEach(function(id,i){var el=$('tire-'+id);el.querySelector('.tire-val').textContent=Math.floor(tireTemps[i])+'°C';el.classList.remove('tire-hot','tire-critical');if(tireTemps[i]>110)el.classList.add('tire-critical');else if(tireTemps[i]>100)el.classList.add('tire-hot');});
}
// ── SESSION MANAGEMENT ──
var currentSessionId = 'SES-' + Math.random().toString(36).substr(2, 9) + '-' + Date.now();
function newSession(){
    currentSessionId = 'SES-' + Math.random().toString(36).substr(2, 9) + '-' + Date.now();
}

function sendTelemetry(){
    var eventId = 'EVT-' + Date.now() + '-' + Math.floor(Math.random() * 10000);
    var selectedIdx = carIndex >= 0 ? carIndex : 0;
    var carId = 'SIM-CAR-0' + (selectedIdx + 1);
    var carName = CAR_NAMES[selectedIdx] || 'AERO PHANTOM';
    var teamName = CAR_TEAM_NAMES[selectedIdx] || 'WILLIAMS';
    var driverId = 'SIM-DRV-0' + (selectedIdx + 1);
    var driverName = teamName + ' Driver (Sim)';
    
    // Deterministic Gear and RPM derivation
    var gear = 0;
    if (currentSpeed >= 330) gear = 8;
    else if (currentSpeed >= 300) gear = 7;
    else if (currentSpeed >= 260) gear = 6;
    else if (currentSpeed >= 210) gear = 5;
    else if (currentSpeed >= 160) gear = 4;
    else if (currentSpeed >= 110) gear = 3;
    else if (currentSpeed >= 60) gear = 2;
    else if (currentSpeed >= 2) gear = 1;
    else gear = 0;
    
    var rpm = currentSpeed <= 1 ? 1000 : Math.min(15000, Math.floor(1000 + (currentSpeed / 350) * 13000 + throttlePercent * 10));
    var lapNumber = Math.floor(lapAngle / (2 * Math.PI)) + 1;

    var payload = {
        schema_version: "1.0",
        session_id: currentSessionId,
        event_id: eventId,
        car_id: carId,
        car_name: carName,
        team: teamName,
        driver_id: driverId,
        driver_name: driverName,
        timestamp: new Date().toISOString(),
        lap_number: lapNumber,
        throttle: parseFloat(throttlePercent.toFixed(1)),
        brake: parseFloat(brakePercent.toFixed(1)),
        telemetry: {
            speed: currentSpeed,
            rpm: rpm,
            gear: gear,
            torque: torque,
            g_force: gForce,
            pos_x: posX,
            pos_z: posZ
        },
        aerodynamics: {
            wind_speed: windForce,
            drag_coefficient: dragCoeff,
            downforce: downforce
        },
        tires: {
            tire_temp: Array.from(tireTemps),
            tire_wear: tireWear.slice()
        },
        // Legacy flat structure compatibility
        speed: currentSpeed,
        wind_speed: windForce,
        drag_coefficient: dragCoeff,
        downforce: downforce,
        g_force: gForce,
        torque: torque,
        tire_temp: Array.from(tireTemps),
        tire_wear: tireWear.slice(),
        pos_x: posX,
        pos_z: posZ
    };
    if(runActive){
        runTelemetryData.push(payload);
    }
    fetch(API_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
    .then(function(r){if(r.ok){dataPointsSent++;$('data-counter').textContent='📡 '+dataPointsSent+' data points sent';var b=$('kafka-badge');b.textContent='● LIVE';b.className='kafka-badge live';}})
    .catch(function(){});
}

// ── BOOT ──
var setupInterval=null;
function fetchSetup(){
    fetch('/setup')
    .then(function(r){if(!r.ok)throw new Error();return r.json();})
    .then(function(data){
        if(data&&typeof data.downforce!=='undefined'&&typeof data.engine_mix!=='undefined'){
            setupDownforce=parseInt(data.downforce);
            setupEngineMix=parseInt(data.engine_mix);
            console.log('📥 Onboard computer sync — Downforce: '+setupDownforce+'% | Engine Mix: '+setupEngineMix);
        }
    })
    .catch(function(){});
}
fetchSetup();
setupInterval=setInterval(fetchSetup,10000);

if (window.location.pathname.indexOf('simulation') >= 0 || window.location.pathname === '/simulation') {
    goToGarage();
}

// ── SESSION RUN ENGINE ──
if ($('btn-start-run')) {
    $('btn-start-run').addEventListener('click', function() {
        if(runActive) return;
        resetBench();
        runTelemetryData=[];
        runActive=true;
        runTimerVal=30;
        
        this.disabled=true;
        $('session-timer-text').textContent='ACQUIRING: 30s';
        
        // Auto-engage rolling road to a high speed and wind tunnel
        if(!roadRunning) toggleRoad();
        targetSpeed=310;
        $('slider-speed').value=310;
        $('val-speed').textContent='310 km/h';
        
        if(!windActive) toggleWind();
        targetWind=50;
        $('slider-wind').value=50;
        $('val-wind').textContent='50 kts';
        
        $('test-status').textContent='QUALIFYING RUN — ACTIVE DATA STREAM';
        
        var elapsed = 0;
        runIntervalId = setInterval(function() {
            elapsed++;
            var remaining = 30 - elapsed;
            $('session-timer-text').textContent='ACQUIRING: ' + remaining + 's';
            $('session-progress-fill').style.width = (elapsed / 30 * 100) + '%';
            
            if (elapsed >= 30) {
                clearInterval(runIntervalId);
                runIntervalId = null;
                runActive = false;
                
                // Stop simulator engines
                if (roadRunning) toggleRoad();
                if (windActive) toggleWind();
                currentSpeed = 0;
                targetSpeed = 0;
                $('slider-speed').value = 0;
                $('val-speed').textContent = '0 km/h';
                
                $('test-status').textContent = 'RUN COMPLETE — DATA RETRIEVAL READY';
                $('session-timer-text').textContent = 'SYNCED ✅';
                
                $('btn-start-run').classList.add('hidden');
                $('btn-download-run').classList.remove('hidden');
                $('link-dashboard').classList.remove('disabled');
                $('link-dashboard').classList.add('ready-glow');
            }
        }, 1000);
    });
}

if ($('btn-download-run')) {
    $('btn-download-run').addEventListener('click', function() {
        if (runTelemetryData.length === 0) return;
        var dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(runTelemetryData, null, 4));
        var dlAnchorElem = document.createElement('a');
        dlAnchorElem.setAttribute("href", dataStr);
        dlAnchorElem.setAttribute("download", "f1_telemetry_session.json");
        dlAnchorElem.click();
    });
}

tick();
})();
