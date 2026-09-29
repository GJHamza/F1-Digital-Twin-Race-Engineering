import React, { useState, useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar
} from 'recharts';

const API_BASE = '';

function App() {
  // Telemetry state
  const [telemetryHistory, setTelemetryHistory] = useState([]);
  const [latestData, setLatestData] = useState(null);
  const [isLive, setIsLive] = useState(false);
  const [dataPointsReceived, setDataPointsReceived] = useState(0);

  // Setup state
  const [downforce, setDownforce] = useState(50);
  const [engineMix, setEngineMix] = useState(5);
  const [uploadSuccess, setUploadSuccess] = useState(false);

  // Quick profiles configurations
  const PRESETS = {
    qualifying: { downforce: 20, engine_mix: 10 },
    wet: { downforce: 85, engine_mix: 4 },
    endurance: { downforce: 55, engine_mix: 7 },
    emergency: { downforce: 60, engine_mix: 3 }
  };
  const [activePreset, setActivePreset] = useState(null);

  // Three.js refs
  const canvasRef = useRef(null);
  const tiresRef = useRef([]);
  const carGroupRef = useRef(null);

  // 1. Fetch live telemetry history and check server state
  useEffect(() => {
    let timer;
    const fetchTelemetry = async () => {
      try {
        const response = await fetch(`${API_BASE}/telemetry`);
        if (response.ok) {
          const data = await response.json();
          setIsLive(true);
          if (data && data.length > 0) {
            setTelemetryHistory(data);
            const latest = data[data.length - 1];
            setLatestData(latest);
            setDataPointsReceived(prev => prev + 1);
          }
        } else {
          setIsLive(false);
        }
      } catch (err) {
        setIsLive(false);
      }
    };

    const fetchCurrentSetup = async () => {
      try {
        const response = await fetch(`${API_BASE}/setup`);
        if (response.ok) {
          const setup = await response.json();
          setDownforce(setup.downforce || 50);
          setEngineMix(setup.engine_mix || 5);
        }
      } catch (err) {}
    };

    fetchCurrentSetup();
    fetchTelemetry();
    timer = setInterval(fetchTelemetry, 1000);

    return () => clearInterval(timer);
  }, []);

  // 2. Upload configuration
  const handleUploadSetup = async (dfVal = downforce, emVal = engineMix) => {
    try {
      const response = await fetch(`${API_BASE}/setup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ downforce: dfVal, engine_mix: emVal })
      });
      if (response.ok) {
        setUploadSuccess(true);
        setTimeout(() => setUploadSuccess(false), 3000);
      }
    } catch (err) {
      console.error('Failed to upload setup', err);
    }
  };

  const applyPreset = (presetKey) => {
    const preset = PRESETS[presetKey];
    if (preset) {
      setActivePreset(presetKey);
      setDownforce(preset.downforce);
      setEngineMix(preset.engine_mix);
      handleUploadSetup(preset.downforce, preset.engine_mix);
    }
  };

  // 3. Three.js Engine for F1 vehicle visualization
  useEffect(() => {
    if (!canvasRef.current) return;

    const width = canvasRef.current.clientWidth;
    const height = canvasRef.current.clientHeight;

    const scene = new THREE.Scene();
    // Dark transparent viewport background
    scene.background = null;

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.set(5, 3.5, 7);

    const renderer = new THREE.WebGLRenderer({ canvas: canvasRef.current, antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.2);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight1.position.set(5, 8, 5);
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x00edff, 0.5);
    dirLight2.position.set(-5, 5, -5);
    scene.add(dirLight2);

    // Platform ring grid helper (light themed)
    const gridHelper = new THREE.GridHelper(10, 20, 0x0066ff, 0xcccccc);
    gridHelper.position.y = 0;
    scene.add(gridHelper);

    // Interactive orbit controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enablePan = false;
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.minDistance = 4;
    controls.maxDistance = 15;
    controls.target.set(0, 0.4, 0);

    // Load car mesh or construct fallback group
    const carGroup = new THREE.Group();
    scene.add(carGroup);
    carGroupRef.current = carGroup;

    let localTires = [];

    const loader = new GLTFLoader();
    // Attempt loading car from static folder on localhost:5000 (Flask host)
    loader.load(
      `${API_BASE}/car/car2.glb`,
      (gltf) => {
        const model = gltf.scene;
        // Fit scaling
        const box = new THREE.Box3().setFromObject(model);
        const size = new THREE.Vector3();
        box.getSize(size);
        const s = 4.5 / Math.max(size.x, size.y, size.z);
        model.scale.setScalar(s);
        
        // Center alignment
        const nb = new THREE.Box3().setFromObject(model);
        const c = new THREE.Vector3();
        nb.getCenter(c);
        model.position.x -= c.x;
        model.position.z -= c.z;
        model.position.y -= nb.min.y;

        carGroup.add(model);

        // Identify wheel objects in GLB to paint them
        model.traverse((node) => {
          if (node.isMesh) {
            const name = (node.name || '').toLowerCase();
            if (
              name.includes('wheel') || 
              name.includes('tire') || 
              name.includes('tyre') || 
              name.includes('rim')
            ) {
              localTires.push(node);
            }
          }
        });
        tiresRef.current = localTires;
      },
      null,
      () => {
        // Fallback: 3D box frame car with 4 cylinders as tires
        const bMat = new THREE.MeshStandardMaterial({ color: 0x0c131a, roughness: 0.4, metalness: 0.8 });
        const chassis = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.4, 4.2), bMat);
        chassis.position.y = 0.35;
        carGroup.add(chassis);

        const wingMat = new THREE.MeshStandardMaterial({ color: 0x00edff, emissive: 0x00edff, emissiveIntensity: 0.4 });
        const frontWing = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.08, 0.4), wingMat);
        frontWing.position.set(0, 0.2, 1.9);
        carGroup.add(frontWing);

        const rearWing = new THREE.Mesh(new THREE.BoxGeometry(2.0, 0.08, 0.6), wingMat);
        rearWing.position.set(0, 0.9, -1.9);
        carGroup.add(rearWing);

        const tirePositions = [
          [-0.9, 0.35, 1.3],  // FL
          [0.9, 0.35, 1.3],   // FR
          [-0.9, 0.35, -1.3],  // RL
          [0.9, 0.35, -1.3]   // RR
        ];

        const fallbackTires = tirePositions.map((pos, idx) => {
          const tMat = new THREE.MeshStandardMaterial({ color: 0x1a1a1a, roughness: 0.8 });
          const tMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.45, 0.35, 16), tMat);
          tMesh.rotation.z = Math.PI / 2;
          tMesh.position.set(...pos);
          tMesh.name = `tire_${idx}`;
          carGroup.add(tMesh);
          return tMesh;
        });

        tiresRef.current = fallbackTires;
      }
    );

    // Animation Loop
    let animId;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      controls.update();

      // Slow idle rotation
      if (carGroup) {
        carGroup.rotation.y += 0.003;
      }

      renderer.render(scene, camera);
    };
    animate();

    // Resize Handler
    const handleResize = () => {
      if (!canvasRef.current) return;
      const w = canvasRef.current.clientWidth;
      const h = canvasRef.current.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  // 4. Update tire colors dynamically based on telemetry temperature inputs
  useEffect(() => {
    if (!tiresRef.current || tiresRef.current.length === 0 || !latestData) return;

    // Get temps
    const temps = latestData.tire_temp || [90, 90, 90, 90];

    const getTireColor = (temp) => {
      if (temp > 105) return new THREE.Color(0xff3c3c); // Red
      if (temp > 98) return new THREE.Color(0xffb700);  // Amber
      return new THREE.Color(0x00edff);                 // Cyan/Normal
    };

    // Apply material colors
    tiresRef.current.forEach((tireMesh, idx) => {
      // Map index FL(0), FR(1), RL(2), RR(3)
      const tempVal = temps[idx] || 90;
      const targetColor = getTireColor(tempVal);
      
      if (tireMesh.material) {
        // If shared material, clone it to make it unique per wheel
        if (!tireMesh.material._cloned) {
          tireMesh.material = tireMesh.material.clone();
          tireMesh.material._cloned = true;
        }
        tireMesh.material.color = targetColor;
        if (tireMesh.material.emissive) {
          tireMesh.material.emissive = targetColor;
          tireMesh.material.emissiveIntensity = tempVal > 98 ? 0.6 : 0.2;
        }
      }
    });
  }, [latestData]);

  // Derived Performance Indices for Radar Chart
  const getRadarData = () => {
    if (!latestData || typeof latestData.speed === 'undefined') {
      return [
        { subject: 'Agility', value: 50 },
        { subject: 'Top Speed', value: 50 },
        { subject: 'Power', value: 50 },
        { subject: 'Stability', value: 50 },
        { subject: 'Stamina', value: 50 }
      ];
    }

    const speed = latestData.speed || 0;
    const gForce = latestData.g_force || 1.0;
    const torque = latestData.torque || 0;
    const wear = latestData.tire_wear || [0,0,0,0];

    return [
      { subject: 'Agility', value: Math.min(100, Math.floor((gForce / 4.5) * 100)) },
      { subject: 'Top Speed', value: Math.min(100, Math.floor((speed / 350) * 100)) },
      { subject: 'Power', value: Math.min(100, Math.floor((torque / 850) * 100)) },
      { subject: 'Stability', value: Math.max(0, 100 - Math.floor(gForce * 6)) },
      { subject: 'Stamina', value: Math.max(0, Math.floor(100 - (wear.reduce((a,b)=>a+b, 0)/4))) }
    ];
  };

  const getAISuggestions = () => {
    const suggestions = [];
    if (!latestData) {
      return ["Chassis balance is optimal. Awaiting telemetry stream..."];
    }
    const temps = latestData.tire_temp || [90, 90, 90, 90];
    const wear = latestData.tire_wear || [0, 0, 0, 0];
    const avgWear = wear.reduce((a, b) => a + b, 0) / 4;

    if (avgWear > 30) {
      suggestions.push("🛞 High tyre degradation detected. Decrease engine fuel mix to preserve rubber.");
    }
    const gForce = latestData.g_force || 1.0;
    const stability = Math.max(0, 100 - Math.floor(gForce * 8));
    if (stability < 40) {
      suggestions.push("🏎️ Rear stability issues. Increase downforce setup to improve cornering grip.");
    }
    if (temps[0] > 110 || temps[1] > 110) {
      suggestions.push("🔥 Front tyres overheating. Lower pressures or reduce downforce.");
    }
    if (suggestions.length === 0) {
      suggestions.push("✅ Chassis balance is optimal. Maintain current engine mapping.");
    }
    return suggestions;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      {/* Header */}
      <header className="cockpit-header">
        <div className="header-logo">
          F1<span>_DIGITAL_TWIN</span> // COCKPIT
        </div>
        <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
          <div className="live-badge" style={{ fontFamily: 'monospace' }}>
            💾 PKT_RECV: {dataPointsReceived}
          </div>
          <div className="live-badge">
            <div className={`live-dot ${!isLive ? 'offline' : ''}`}></div>
            <span>{!isLive ? 'OFFLINE fallback' : 'TELEMETRY LIVE'}</span>
          </div>
        </div>
      </header>

      {/* Grid Layout */}
      <main className="cockpit-grid">
        {/* Left Panel - Configurations */}
        <section className="panel">
          <h3 className="panel-title">Onboard Tuning</h3>

          <div className="control-group">
            <span className="label">⚡ QUICK PRESETS</span>
            <div className="preset-grid">
              <button 
                className={`btn-preset ${activePreset === 'qualifying' ? 'active' : ''}`}
                onClick={() => applyPreset('qualifying')}
              >
                🏁 QUALI
              </button>
              <button 
                className={`btn-preset ${activePreset === 'wet' ? 'active' : ''}`}
                onClick={() => applyPreset('wet')}
              >
                🌧️ WET
              </button>
              <button 
                className={`btn-preset ${activePreset === 'endurance' ? 'active' : ''}`}
                onClick={() => applyPreset('endurance')}
              >
                🔥 ENDUR
              </button>
              <button 
                className={`btn-preset ${activePreset === 'emergency' ? 'active' : ''}`}
                onClick={() => applyPreset('emergency')}
              >
                🛑 E-STOP
              </button>
            </div>
          </div>

          <div className="control-group">
            <span className="label">🔧 CUSTOM CONFIG</span>
            
            <div className="slider-group">
              <div className="slider-header">
                <span>Downforce Wing Setup</span>
                <span className="slider-val">{downforce}%</span>
              </div>
              <input 
                type="range" 
                min="0" 
                max="100" 
                value={downforce} 
                className="neon-slider"
                onChange={(e) => {
                  setDownforce(parseInt(e.target.value));
                  setActivePreset(null);
                }}
              />
            </div>

            <div className="slider-group">
              <div className="slider-header">
                <span>Engine Fuel Mix (Aggressiveness)</span>
                <span className="slider-val">{engineMix} / 10</span>
              </div>
              <input 
                type="range" 
                min="1" 
                max="10" 
                value={engineMix} 
                className="neon-slider"
                onChange={(e) => {
                  setEngineMix(parseInt(e.target.value));
                  setActivePreset(null);
                }}
              />
            </div>

            <button 
              className="btn-primary" 
              onClick={() => handleUploadSetup(downforce, engineMix)}
              style={{ marginTop: '10px' }}
            >
              Upload Setup to Vehicle
            </button>

            {uploadSuccess && (
              <div style={{ color: 'var(--green)', fontSize: '13px', textAlign: 'center', fontWeight: 'bold' }}>
                ✓ Onboard setup successfully synced!
              </div>
            )}
          </div>

          {/* AI Setup Advisor Widget */}
          <div className="control-group" style={{ marginTop: '15px', background: 'rgba(0, 102, 255, 0.03)', border: '1px solid rgba(0, 102, 255, 0.1)', padding: '12px', borderRadius: '6px' }}>
            <span className="label" style={{ color: 'var(--cyan)' }}>🤖 AI Setup Advisor</span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '6px' }}>
              {getAISuggestions().map((sug, i) => (
                <div key={i} style={{ fontSize: '12px', lineHeight: '1.4', fontWeight: '500', color: 'var(--text-secondary)' }}>
                  {sug}
                </div>
              ))}
            </div>
          </div>

          <div className="control-group" style={{ flexGrow: 1, justifyContent: 'flex-end' }}>
            <span className="label">🏁 SIMULATOR PANEL</span>
            <a 
              href={`${API_BASE}/simulation`} 
              target="_blank" 
              rel="noreferrer" 
              className="btn-primary" 
              style={{ textAlign: 'center', textDecoration: 'none' }}
            >
              Open 3D Simulator ↗
            </a>
          </div>
        </section>

        {/* Center Panel - 3D Visualizer */}
        <section className="panel" style={{ padding: '15px' }}>
          <h3 className="panel-title" style={{ marginBottom: '10px' }}>3D Digital Twin View</h3>
          <div className="viewport-container">
            <canvas ref={canvasRef} className="three-canvas" />
            <div className="viewport-hud">
              <div className="hud-title">F1 Chassis Visualizer</div>
              <div className="hud-desc">Tyres dynamically colored by telemetry heat sensors</div>
            </div>
          </div>

          <div className="tyre-overlay">
            <div className="tyre-card">
              <span className="tyre-name">Front-Left Temp</span>
              <span className={`tyre-temp-val ${latestData?.tire_temp?.[0] > 105 ? 'critical' : latestData?.tire_temp?.[0] > 98 ? 'warning' : 'normal'}`}>
                {latestData && latestData.tire_temp ? Math.floor(latestData.tire_temp[0]) : 90}°C
              </span>
            </div>
            <div className="tyre-card">
              <span className="tyre-name">Front-Right Temp</span>
              <span className={`tyre-temp-val ${latestData?.tire_temp?.[1] > 105 ? 'critical' : latestData?.tire_temp?.[1] > 98 ? 'warning' : 'normal'}`}>
                {latestData && latestData.tire_temp ? Math.floor(latestData.tire_temp[1]) : 90}°C
              </span>
            </div>
            <div className="tyre-card">
              <span className="tyre-name">Rear-Left Temp</span>
              <span className={`tyre-temp-val ${latestData?.tire_temp?.[2] > 105 ? 'critical' : latestData?.tire_temp?.[2] > 98 ? 'warning' : 'normal'}`}>
                {latestData && latestData.tire_temp ? Math.floor(latestData.tire_temp[2]) : 90}°C
              </span>
            </div>
            <div className="tyre-card">
              <span className="tyre-name">Rear-Right Temp</span>
              <span className={`tyre-temp-val ${latestData?.tire_temp?.[3] > 105 ? 'critical' : latestData?.tire_temp?.[3] > 98 ? 'warning' : 'normal'}`}>
                {latestData && latestData.tire_temp ? Math.floor(latestData.tire_temp[3]) : 90}°C
              </span>
            </div>
          </div>
        </section>

        {/* Right Panel - Graphs & Indices */}
        <section className="panel">
          <h3 className="panel-title">Race Analytics</h3>

          {/* Quick Metrics Cards */}
          <div className="metrics-row">
            <div className="metric-card">
              <span className="label">Live Speed</span>
              <span className="metric-val">{latestData ? Math.floor(latestData.speed) : 0} <span className="metric-unit">km/h</span></span>
            </div>
            <div className="metric-card">
              <span className="label">Engine Torque</span>
              <span className="metric-val">{latestData ? Math.floor(latestData.torque) : 0} <span className="metric-unit">Nm</span></span>
            </div>
          </div>

          {/* Telemetry charts */}
          <div className="control-group">
            <span className="label">📊 Speed Telemetry Stream</span>
            <div className="chart-container">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={telemetryHistory} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                  <XAxis dataKey="timestamp" hide />
                  <YAxis domain={[0, 360]} tickStyle={{ fill: 'var(--text-secondary)', fontSize: 10 }} />
                  <Tooltip contentStyle={{ background: '#ffffff', borderColor: 'var(--cyan)', color: 'var(--text-primary)', borderRadius: '6px', fontSize: '11px', fontFamily: 'monospace' }} labelStyle={{ display: 'none' }} />
                  <Area type="monotone" dataKey="speed" stroke="var(--cyan)" fill="rgba(0, 237, 255, 0.15)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Performance Index radar */}
          <div className="control-group" style={{ height: '220px', marginTop: '10px' }}>
            <span className="label">🕸️ Performance Radar</span>
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart cx="50%" cy="50%" radius="70%" data={getRadarData()}>
                <PolarGrid stroke="#e2e8f0" />
                <PolarAngleAxis dataKey="subject" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                <PolarRadiusAxis angle={30} domain={[0, 100]} hide />
                <Radar name="F1 Performance" dataKey="value" stroke="var(--cyan)" fill="var(--cyan)" fillOpacity={0.2} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </section>
      </main>

      {/* Scrolling Ticker Footer */}
      <footer className="marquee-footer">
        <div className="marquee-content">
          {latestData && typeof latestData.speed !== 'undefined' ? (
            `[SYS_PACKET_STREAM] SPEED: ${latestData.speed.toFixed(1)} KM/H | TORQUE: ${latestData.torque.toFixed(0)} Nm | G-FORCE: ${latestData.g_force.toFixed(2)}G | TYRE WEAR: ${latestData.tire_wear.map(w => w.toFixed(1) + '%').join(', ')} | DRAG Cd: ${latestData.drag_coefficient.toFixed(3)} | DOWNFORCE: ${latestData.downforce.toFixed(0)}N | GPS: pos_x(${latestData.pos_x.toFixed(1)}), pos_z(${latestData.pos_z.toFixed(1)})`
          ) : (
            'AWAITING TELEMETRY PACKETS FROM F1 VEHICLE SIMULATOR... START ROLLING ROAD TO STREAM DATA.'
          )}
        </div>
      </footer>
    </div>
  );
}

export default App;
