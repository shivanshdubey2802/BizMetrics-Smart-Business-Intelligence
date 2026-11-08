"""
BizMetrics 3D Product Digital Twin & Equipment Inspector Component
Provides interactive 3D WebGL visualization for inventory products and equipment.
Features:
- Three.js WebGL rendering with 360° OrbitControls (rotate, pan, zoom)
- Procedural digital twin geometries for inventory SKUs (Steel Pipes, PVC Valves, Motors, LED Fixtures, etc.)
- Material shading modes: Realistic PBR, Wireframe Mesh, Solid Clay, Technical Blueprint
- Lighting presets: Studio Daylight, Workshop Warm, High-Contrast Inspection
- Interactive Exploded Assembly slider to inspect internal components
- Engineering specifications HUD (Dimensions, Net Weight, Material Grade, IP Rating)
- Turntable auto-rotation toggle
- Offline Canvas fallback if WebGL/CDN is unavailable
- Lazy loaded to ensure 0 ms latency on initial dashboard load
- Multilingual translation support (English, हिंदी, Hinglish)
"""

from __future__ import annotations
import json
import streamlit as st
import streamlit.components.v1 as components
from typing import Any, Optional

try:
    from utils.translations import t, get_current_language
except Exception:
    def t(key, lang=None): return str(key) if key is not None else ""
    def get_current_language(): return "English"

# Technical engineering specifications for BizMetrics SKUs
PRODUCT_3D_SPECS: dict[str, dict[str, Any]] = {
    "PROD001": {
        "model_type": "steel_pipe",
        "name": "Steel Pipes - 1 inch (Flanged)",
        "category": "Building Materials",
        "dimensions": "1000 mm × Ø 33.4 mm × 3.2 mm wall",
        "weight": "2.42 kg / m",
        "material": "IS 1239 Grade Heavy Seamless Steel",
        "tolerance": "± 0.25 mm",
        "ip_rating": "N/A (Hydrostatic tested to 50 bar)",
        "thermal_range": "-20°C to +400°C",
        "components": ["Flange A", "Seamless Tube", "Flange B", "Collar Ring", "Bolt Circle"],
        "default_color": "#475569",
    },
    "PROD002": {
        "model_type": "pvc_pipe",
        "name": "PVC Pipe - 1 inch (Rigid Conduit)",
        "category": "Plumbing",
        "dimensions": "3000 mm × Ø 32 mm × 2.0 mm wall",
        "weight": "0.38 kg / m",
        "material": "Unplasticized Polyvinyl Chloride (uPVC Class 3)",
        "tolerance": "± 0.15 mm",
        "ip_rating": "IP67 (Joint Welded)",
        "thermal_range": "0°C to +60°C",
        "components": ["Main Conduit", "Bell Socket", "Solvent Union Ring"],
        "default_color": "#94A3B8",
    },
    "PROD003": {
        "model_type": "pump_motor",
        "name": "Submersible Water Pump 1HP / High-Torque Motor",
        "category": "Electrical / Machinery",
        "dimensions": "420 mm × Ø 98 mm",
        "weight": "9.80 kg",
        "material": "AISI 304 Stainless Steel & Noryl Impellers",
        "tolerance": "Precision Machined Class H",
        "ip_rating": "IP68 Submersible (Continuous Immersion)",
        "thermal_range": "0°C to +45°C Liquid Temp",
        "components": ["Stainless Motor Casing", "Multi-Stage Impeller Stack", "Suction Strainer", "Discharge Outlet", "Shaft Coupling"],
        "default_color": "#0D9488",
    },
    "PROD004": {
        "model_type": "led_bulb",
        "name": "Commercial LED Luminaire / High-Bay 50W",
        "category": "Electrical",
        "dimensions": "Ø 140 mm × 185 mm",
        "weight": "0.45 kg",
        "material": "Die-Cast Aluminum Heat Sink & Polycarbonate Diffuser",
        "tolerance": "Standard B22 / E27 Base",
        "ip_rating": "IP65 Weatherproof",
        "thermal_range": "-10°C to +50°C",
        "components": ["Aluminum Heatsink Core", "SMD LED Array PCB", "Frosted PC Dome", "Internal Constant-Current Driver", "Brass Contact Base"],
        "default_color": "#0284C7",
    },
    "PROD005": {
        "model_type": "cement_bag",
        "name": "Portland Slag Cement - 50 kg Bag",
        "category": "Construction",
        "dimensions": "620 mm × 480 mm × 160 mm",
        "weight": "50.0 kg ± 1%",
        "material": "HDPE Woven Sack with Moisture Barrier",
        "tolerance": "IS 455 Specification",
        "ip_rating": "Moisture Sealed (Poly Lined)",
        "thermal_range": "Dry Ambient Storage",
        "components": ["Woven Outer Shell", "Inner Moisture Liner", "Sealed Stitch Hem", "Valve Spout"],
        "default_color": "#78716C",
    },
    "PROD006": {
        "model_type": "paint_bucket",
        "name": "Wall Paint - 20 L Industrial Drum Container",
        "category": "Paint & Hardware",
        "dimensions": "Ø 310 mm × 390 mm",
        "weight": "26.5 kg Gross",
        "material": "Virgin HDPE Polymer / Galvanized Wire Handle",
        "tolerance": "Tamper-Evident Snap Cap",
        "ip_rating": "Airtight Seal (Zero VOC Leakage)",
        "thermal_range": "+5°C to +40°C",
        "components": ["HDPE Bucket Body", "Tamper-Evident Lid", "Galvanized Bail Handle", "Plastic Grip Roller"],
        "default_color": "#E11D48",
    },
    "PROD007": {
        "model_type": "roofing_sheet",
        "name": "GI Corrugated Roofing Sheet 0.45 mm",
        "category": "Roofing",
        "dimensions": "3660 mm × 840 mm × 0.45 mm",
        "weight": "11.2 kg per sheet",
        "material": "Hot-Dip Galvanized Zinc Coated Mild Steel (IS 277)",
        "tolerance": "Class VIII Zinc Coating (120 gsm)",
        "ip_rating": "UV & Weather Resisting",
        "thermal_range": "-15°C to +85°C",
        "components": ["Corrugated Steel Profile", "Galvanized Passivation Layer", "Pre-Punched Edge"],
        "default_color": "#64748B",
    },
    "PROD008": {
        "model_type": "pvc_elbow",
        "name": "PVC 90° Elbow Fitting - 1 inch",
        "category": "Plumbing",
        "dimensions": "65 mm × 65 mm × Ø 32 mm",
        "weight": "0.065 kg",
        "material": "Injection Molded PVC Schedule 40",
        "tolerance": "ASTM D2466 Tight Slip Fit",
        "ip_rating": "IP67 (Solvent Welded)",
        "thermal_range": "0°C to +60°C",
        "components": ["90° Elbow Body", "Socket Bore Inlet", "Socket Bore Outlet", "Reinforcement Rib"],
        "default_color": "#94A3B8",
    },
    "PROD009": {
        "model_type": "switch_modular",
        "name": "Modular Electrical Switch 6A / 240V",
        "category": "Electrical",
        "dimensions": "48 mm × 25 mm × 32 mm",
        "weight": "0.040 kg",
        "material": "Flame-Retardant Polycarbonate & Silver-Cadmium Contacts",
        "tolerance": "IS 3854 Compliant",
        "ip_rating": "IP20 (Indoor Shock Resistant)",
        "thermal_range": "-5°C to +55°C",
        "components": ["Front Rocker Lever", "Polycarbonate Housing", "Phosphor Bronze Terminals", "Spring Toggle Mechanism"],
        "default_color": "#F8FAFC",
    },
    "PROD010": {
        "model_type": "tmt_bar",
        "name": "TMT Rebar 8 mm Fe 500D (Ribbed Reinforcing Bar)",
        "category": "Building Materials",
        "dimensions": "12000 mm × Ø 8 mm",
        "weight": "0.395 kg / m",
        "material": "Thermo-Mechanically Treated High-Yield Rebar (Fe 500D)",
        "tolerance": "IS 1786 Standard Cross-Rib Pitch",
        "ip_rating": "Corrosion Inhibited Surface",
        "thermal_range": "-20°C to +600°C Fire Resistance",
        "components": ["Tempered Martensite Core", "Helical Transverse Ribs", "Longitudinal Rib Ridge"],
        "default_color": "#334155",
    },
    "PROD011": {
        "model_type": "brass_valve",
        "name": "Heavy Brass Bibcock / Gate Valve 15 mm",
        "category": "Plumbing",
        "dimensions": "115 mm × 45 mm × 85 mm",
        "weight": "0.320 kg",
        "material": "Forged CW617N Solid Brass (Lead Safe)",
        "tolerance": "BSPT 1/2 inch Precision Threads",
        "ip_rating": "100% Pressure Leak Tested at 16 bar",
        "thermal_range": "-10°C to +95°C",
        "components": ["Forged Brass Body", "Hexagonal Bonnet Nut", "Teflon Spindle Gland", "Tri-Lobe Control Wheel", "Threaded Spout Nozzle"],
        "default_color": "#D97706",
    },
    "PROD012": {
        "model_type": "tile_adhesive",
        "name": "Polymer Modified Tile Adhesive - 20 kg",
        "category": "Construction",
        "dimensions": "480 mm × 320 mm × 110 mm",
        "weight": "20.0 kg ± 1%",
        "material": "Polymer Fortified Grey Cementitious Powder",
        "tolerance": "IS 15477 Type 2 Standard",
        "ip_rating": "Moisture Resistant Sealed Pouch",
        "thermal_range": "+5°C to +45°C Application",
        "components": ["Multi-Wall Paper Sack", "Polyethylene Moisture Barrier", "Easy-Pour Gusset"],
        "default_color": "#A8A29E",
    },
}

def get_product_specs(product_id: str) -> dict[str, Any]:
    """Retrieve specifications for a given product ID with safe defaults."""
    pid = str(product_id).upper().strip()
    if pid in PRODUCT_3D_SPECS:
        return PRODUCT_3D_SPECS[pid]
    # Fallback to PROD001 specs
    fallback = dict(PRODUCT_3D_SPECS["PROD001"])
    fallback["name"] = f"Product {product_id}"
    return fallback


@st.cache_data(show_spinner=False)
def generate_3d_html(
    product_id: str,
    product_name: str,
    category: str,
    specs: dict[str, Any],
    lang: str = "English",
    height: int = 560,
) -> str:
    """
    Generates a self-contained, responsive WebGL Three.js 3D viewer HTML document.
    Includes OrbitControls, PBR materials, multi-part procedural models, exploded view,
    turntable auto-rotate, rendering mode toggles, and fallback canvas.
    """
    model_type = specs.get("model_type", "steel_pipe")
    default_hex = specs.get("default_color", "#0D9488")
    components_list = specs.get("components", ["Main Body", "Sub-Assembly", "Mounting"])
    components_json = json.dumps(components_list)
    specs_json = json.dumps(specs)

    # Translations for in-viewer HUD
    lbl_orbit = t("360° Free Orbit", lang)
    lbl_hint = t("Left-click and drag to rotate, right-click to pan, scroll wheel to zoom", lang)
    lbl_turntable = t("Turntable Auto-Rotation", lang)
    lbl_exploded = t("Exploded Assembly View", lang)
    lbl_shading = t("Rendering Mode", lang)
    lbl_reset = t("Reset Camera View", lang)
    lbl_specs = t("Engineering Specifications", lang)
    lbl_pbr = t("Realistic PBR", lang)
    lbl_wire = t("Wireframe Mesh", lang)
    lbl_clay = t("Solid Clay", lang)
    lbl_blueprint = t("Technical Blueprint", lang)
    lbl_lighting = t("Lighting Scheme", lang)
    lbl_daylight = t("Studio Daylight", lang)
    lbl_warm = t("Workshop Warm", lang)
    lbl_contrast = t("High-Contrast", lang)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
  body, html {{ width: 100%; height: 100%; overflow: hidden; background: #0F172A; }}
  #viewer-container {{ position: relative; width: 100%; height: {height}px; background: radial-gradient(circle at 50% 40%, #1E293B 0%, #0F172A 100%); }}
  #three-canvas {{ width: 100%; height: 100%; display: block; }}
  
  /* Top Overlay HUD */
  .hud-top {{
    position: absolute; top: 12px; left: 14px; right: 14px;
    display: flex; justify-content: space-between; align-items: flex-start;
    pointer-events: none; z-index: 10;
  }}
  .hud-card {{
    background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 8px;
    padding: 8px 14px; color: #F8FAFC; pointer-events: auto;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
  }}
  .badge-tag {{
    display: inline-block; background: #0D9488; color: #FFFFFF;
    font-size: 11px; font-weight: 700; padding: 2px 7px; border-radius: 4px;
    margin-right: 6px; text-transform: uppercase; letter-spacing: 0.5px;
  }}
  .product-title {{ font-size: 14px; font-weight: 700; color: #F1F5F9; display: flex; align-items: center; }}
  .product-meta {{ font-size: 11px; color: #94A3B8; margin-top: 3px; }}
  
  /* Right Specs HUD */
  .hud-specs {{
    max-width: 260px; font-size: 11px; line-height: 1.4;
  }}
  .spec-row {{ display: flex; justify-content: space-between; margin-bottom: 3px; border-bottom: 1px dotted rgba(255,255,255,0.08); padding-bottom: 2px; }}
  .spec-key {{ color: #94A3B8; }}
  .spec-val {{ color: #38BDF8; font-weight: 600; text-align: right; }}

  /* Bottom Controls Toolbar */
  .hud-bottom {{
    position: absolute; bottom: 12px; left: 14px; right: 14px;
    display: flex; justify-content: space-between; align-items: center;
    pointer-events: none; z-index: 10; flex-wrap: wrap; gap: 8px;
  }}
  .btn-group {{
    display: flex; gap: 6px; align-items: center; pointer-events: auto;
  }}
  .hud-btn {{
    background: rgba(30, 41, 59, 0.9); border: 1px solid rgba(255, 255, 255, 0.15);
    color: #E2E8F0; padding: 6px 11px; border-radius: 6px; font-size: 11px;
    font-weight: 600; cursor: pointer; transition: all 0.15s ease;
    display: inline-flex; align-items: center; gap: 5px;
  }}
  .hud-btn:hover {{ background: #0D9488; color: #FFFFFF; border-color: #14B8A6; }}
  .hud-btn.active {{ background: #0D9488; color: #FFFFFF; border-color: #14B8A6; }}
  
  .slider-box {{
    display: flex; align-items: center; gap: 8px; background: rgba(30, 41, 59, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 6px; padding: 4px 10px;
    color: #E2E8F0; font-size: 11px; font-weight: 600; pointer-events: auto;
  }}
  .slider-box input[type=range] {{
    width: 90px; accent-color: #0D9488; cursor: pointer;
  }}

  /* Instruction hint banner */
  .hud-hint {{
    position: absolute; bottom: 58px; left: 50%; transform: translateX(-50%);
    background: rgba(15, 23, 42, 0.7); backdrop-filter: blur(4px);
    border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 20px;
    padding: 3px 12px; color: #94A3B8; font-size: 10px; pointer-events: none;
    letter-spacing: 0.3px; white-space: nowrap; z-index: 8;
  }}
  
  /* Fallback Canvas Overlay */
  #fallback-canvas {{
    position: absolute; top: 0; left: 0; width: 100%; height: 100%;
    display: none; z-index: 1;
  }}
</style>
<!-- Load Three.js and OrbitControls with robust failover -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
</head>
<body>

<div id="viewer-container">
  <!-- Dynamic Three.js WebGL Viewport -->
  <canvas id="three-canvas"></canvas>
  <canvas id="fallback-canvas"></canvas>

  <!-- Top Metadata HUD -->
  <div class="hud-top">
    <div class="hud-card">
      <div class="product-title">
        <span class="badge-tag">{product_id}</span>
        {product_name}
      </div>
      <div class="product-meta">📐 {category} • {lbl_orbit}</div>
    </div>
    <div class="hud-card hud-specs">
      <div style="font-weight:700; color:#38BDF8; margin-bottom:4px; font-size:11px;">⚙️ {lbl_specs}</div>
      <div class="spec-row"><span class="spec-key">Dimensions:</span><span class="spec-val">{specs.get('dimensions', 'N/A')}</span></div>
      <div class="spec-row"><span class="spec-key">Weight:</span><span class="spec-val">{specs.get('weight', 'N/A')}</span></div>
      <div class="spec-row"><span class="spec-key">Material:</span><span class="spec-val">{specs.get('material', 'N/A')}</span></div>
      <div class="spec-row"><span class="spec-key">Protection:</span><span class="spec-val">{specs.get('ip_rating', 'N/A')}</span></div>
      <div class="spec-row"><span class="spec-key">Tolerance:</span><span class="spec-val">{specs.get('tolerance', 'N/A')}</span></div>
    </div>
  </div>

  <!-- Instruction Hint -->
  <div class="hud-hint">🖱️ {lbl_hint}</div>

  <!-- Bottom Interactive Controls -->
  <div class="hud-bottom">
    <div class="btn-group">
      <button class="hud-btn active" id="btn-spin" onclick="toggleTurntable()">🔄 {lbl_turntable}</button>
      <button class="hud-btn" id="btn-reset" onclick="resetCamera()">🎯 {lbl_reset}</button>
    </div>

    <!-- Exploded Assembly Slider -->
    <div class="slider-box">
      <span>💥 {lbl_exploded}</span>
      <input type="range" id="explode-slider" min="0" max="100" value="0" oninput="onExplodeChange(this.value)">
      <span id="explode-val" style="min-width:24px; color:#38BDF8;">0%</span>
    </div>

    <!-- Render Modes -->
    <div class="btn-group">
      <button class="hud-btn active" id="mode-pbr" onclick="setShadingMode('pbr')">✨ {lbl_pbr}</button>
      <button class="hud-btn" id="mode-wire" onclick="setShadingMode('wireframe')">🕸️ {lbl_wire}</button>
      <button class="hud-btn" id="mode-clay" onclick="setShadingMode('clay')">🗿 {lbl_clay}</button>
      <button class="hud-btn" id="mode-blue" onclick="setShadingMode('blueprint')">📐 {lbl_blueprint}</button>
    </div>

    <!-- Lighting Preset -->
    <div class="btn-group">
      <button class="hud-btn active" id="light-day" onclick="setLighting('daylight')">☀️ {lbl_daylight}</button>
      <button class="hud-btn" id="light-warm" onclick="setLighting('warm')">💡 {lbl_warm}</button>
      <button class="hud-btn" id="light-contrast" onclick="setLighting('contrast')">🔍 {lbl_contrast}</button>
    </div>
  </div>
</div>

<script>
// State & Configuration
const MODEL_TYPE = "{model_type}";
const BASE_COLOR_HEX = "{default_hex}";
const COMPONENTS = {components_json};
const SPECS = {specs_json};

let scene, camera, renderer, controls;
let productGroup, partMeshes = [];
let isTurntableActive = true;
let currentShadingMode = 'pbr';
let currentLightingMode = 'daylight';
let dirLight, warmLight, spotLight, ambientLight;
let floorGrid;

function init3D() {{
  const container = document.getElementById('viewer-container');
  const canvas = document.getElementById('three-canvas');

  if (typeof THREE === 'undefined') {{
    console.warn("Three.js not available via CDN. Launching HTML5 procedural fallback.");
    runSoftwareFallback();
    return;
  }}

  // 1. Scene
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0F172A);
  scene.fog = new THREE.FogExp2(0x0F172A, 0.04);

  // 2. Camera
  const aspect = container.clientWidth / container.clientHeight;
  camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 100);
  camera.position.set(3.5, 2.5, 4.5);

  // 3. Renderer
  try {{
    renderer = new THREE.WebGLRenderer({{ canvas: canvas, antialias: true, alpha: false, powerPreference: "high-performance" }});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;
  }} catch (e) {{
    console.error("WebGL failed:", e);
    runSoftwareFallback();
    return;
  }}

  // 4. OrbitControls
  if (typeof THREE.OrbitControls !== 'undefined') {{
    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.maxDistance = 15;
    controls.minDistance = 1.2;
    controls.target.set(0, 0.5, 0);
  }}

  // 5. Lighting Setup
  ambientLight = new THREE.AmbientLight(0xFFFFFF, 0.7);
  scene.add(ambientLight);

  dirLight = new THREE.DirectionalLight(0xFFFFFF, 1.4);
  dirLight.position.set(5, 8, 5);
  dirLight.castShadow = true;
  dirLight.shadow.mapSize.width = 1024;
  dirLight.shadow.mapSize.height = 1024;
  scene.add(dirLight);

  warmLight = new THREE.DirectionalLight(0xFDBA74, 0.0);
  warmLight.position.set(-5, 4, -3);
  scene.add(warmLight);

  spotLight = new THREE.SpotLight(0x38BDF8, 0.0, 20, Math.PI / 4, 0.3);
  spotLight.position.set(0, 6, 4);
  scene.add(spotLight);

  // Studio Ground Plane with circular grid
  const gridHelper = new THREE.GridHelper(10, 20, 0x0D9488, 0x1E293B);
  gridHelper.position.y = -0.01;
  scene.add(gridHelper);
  floorGrid = gridHelper;

  // Shadow receiving floor plane
  const floorGeo = new THREE.PlaneGeometry(16, 16);
  const floorMat = new THREE.ShadowMaterial({{ opacity: 0.35 }});
  const floor = new THREE.Mesh(floorGeo, floorMat);
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  scene.add(floor);

  // 6. Build Procedural 3D Model
  productGroup = new THREE.Group();
  scene.add(productGroup);
  buildProceduralProduct(MODEL_TYPE);

  // Window resize handler
  window.addEventListener('resize', onWindowResize, false);

  // Animation Loop
  animate();
}}

// Build High-Fidelity 3D Geometries based on Model Type
function buildProceduralProduct(type) {{
  partMeshes = [];
  const baseMat = createPBRMaterial(BASE_COLOR_HEX, 0.7, 0.3);
  const metalMat = createPBRMaterial('#CBD5E1', 0.9, 0.2);
  const accentMat = createPBRMaterial('#0D9488', 0.4, 0.5);
  const brassMat = createPBRMaterial('#D97706', 0.85, 0.25);
  const glassMat = new THREE.MeshPhysicalMaterial({{
    color: 0xFFFFFF, transparent: true, opacity: 0.4, roughness: 0.1, transmission: 0.9, thickness: 0.5
  }});

  if (type === 'steel_pipe') {{
    // Heavy Seamless Steel Pipe with bolted flanges
    // Main tube
    const tubeGeo = new THREE.CylinderGeometry(0.35, 0.35, 3.2, 32, 1, true);
    const tube = new THREE.Mesh(tubeGeo, metalMat);
    tube.castShadow = true;
    tube.userData = {{ explodeDir: new THREE.Vector3(0, 0, 0), origPos: new THREE.Vector3(0, 1.6, 0) }};
    tube.position.copy(tube.userData.origPos);
    partMeshes.push(tube);
    productGroup.add(tube);

    // Flange Bottom
    const f1Geo = new THREE.CylinderGeometry(0.65, 0.65, 0.18, 32);
    const f1 = new THREE.Mesh(f1Geo, baseMat);
    f1.castShadow = true;
    f1.userData = {{ explodeDir: new THREE.Vector3(0, -1.2, 0), origPos: new THREE.Vector3(0, 0.1, 0) }};
    f1.position.copy(f1.userData.origPos);
    partMeshes.push(f1);
    productGroup.add(f1);

    // Flange Top
    const f2Geo = new THREE.CylinderGeometry(0.65, 0.65, 0.18, 32);
    const f2 = new THREE.Mesh(f2Geo, baseMat);
    f2.castShadow = true;
    f2.userData = {{ explodeDir: new THREE.Vector3(0, 1.2, 0), origPos: new THREE.Vector3(0, 3.1, 0) }};
    f2.position.copy(f2.userData.origPos);
    partMeshes.push(f2);
    productGroup.add(f2);

    // Flange Bolts
    for (let i = 0; i < 8; i++) {{
      const angle = (i / 8) * Math.PI * 2;
      const bx = Math.cos(angle) * 0.52;
      const bz = Math.sin(angle) * 0.52;
      const bGeo = new THREE.CylinderGeometry(0.04, 0.04, 0.28, 8);
      const bolt = new THREE.Mesh(bGeo, metalMat);
      bolt.position.set(bx, 3.12, bz);
      bolt.userData = {{ explodeDir: new THREE.Vector3(bx * 0.8, 1.6, bz * 0.8), origPos: bolt.position.clone() }};
      partMeshes.push(bolt);
      productGroup.add(bolt);
    }}

  }} else if (type === 'pump_motor') {{
    // Submersible Water Pump 1HP / Induction Machine
    // Lower Motor Housing (Stainless cylinder)
    const motGeo = new THREE.CylinderGeometry(0.48, 0.48, 1.8, 32);
    const mot = new THREE.Mesh(motGeo, metalMat);
    mot.castShadow = true;
    mot.userData = {{ explodeDir: new THREE.Vector3(0, -1.0, 0), origPos: new THREE.Vector3(0, 0.9, 0) }};
    mot.position.copy(mot.userData.origPos);
    partMeshes.push(mot);
    productGroup.add(mot);

    // Suction Screen / Intake Strainer (Slotted ring)
    const scrGeo = new THREE.CylinderGeometry(0.50, 0.50, 0.35, 32);
    const scrMat = createPBRMaterial('#0284C7', 0.5, 0.4);
    const scr = new THREE.Mesh(scrGeo, scrMat);
    scr.castShadow = true;
    scr.userData = {{ explodeDir: new THREE.Vector3(0, 0.0, 0), origPos: new THREE.Vector3(0, 1.95, 0) }};
    scr.position.copy(scr.userData.origPos);
    partMeshes.push(scr);
    productGroup.add(scr);

    // Upper Multi-Stage Impeller Chamber
    const impGeo = new THREE.CylinderGeometry(0.44, 0.44, 1.2, 32);
    const imp = new THREE.Mesh(impGeo, accentMat);
    imp.castShadow = true;
    imp.userData = {{ explodeDir: new THREE.Vector3(0, 1.0, 0), origPos: new THREE.Vector3(0, 2.7, 0) }};
    imp.position.copy(imp.userData.origPos);
    partMeshes.push(imp);
    productGroup.add(imp);

    // Top Discharge Brass Head & Eye Bolt
    const headGeo = new THREE.ConeGeometry(0.44, 0.5, 32);
    const head = new THREE.Mesh(headGeo, brassMat);
    head.castShadow = true;
    head.userData = {{ explodeDir: new THREE.Vector3(0, 1.8, 0), origPos: new THREE.Vector3(0, 3.45, 0) }};
    head.position.copy(head.userData.origPos);
    partMeshes.push(head);
    productGroup.add(head);

  }} else if (type === 'brass_valve') {{
    // Heavy Brass Gate Valve / Bibcock
    // Valve body (horizontal barrel)
    const bodGeo = new THREE.CylinderGeometry(0.32, 0.32, 1.4, 24);
    const bod = new THREE.Mesh(bodGeo, brassMat);
    bod.rotation.z = Math.PI / 2;
    bod.castShadow = true;
    bod.userData = {{ explodeDir: new THREE.Vector3(0, 0, 0), origPos: new THREE.Vector3(0, 0.6, 0) }};
    bod.position.copy(bod.userData.origPos);
    partMeshes.push(bod);
    productGroup.add(bod);

    // Vertical Bonnet Stem
    const stemGeo = new THREE.CylinderGeometry(0.22, 0.22, 0.9, 24);
    const stem = new THREE.Mesh(stemGeo, brassMat);
    stem.castShadow = true;
    stem.userData = {{ explodeDir: new THREE.Vector3(0, 0.8, 0), origPos: new THREE.Vector3(0, 1.15, 0) }};
    stem.position.copy(stem.userData.origPos);
    partMeshes.push(stem);
    productGroup.add(stem);

    // Tri-lobe / Circular Cast Handwheel
    const whlGeo = new THREE.TorusGeometry(0.55, 0.08, 16, 32);
    const whlMat = createPBRMaterial('#DC2626', 0.2, 0.6); // Red industrial handle
    const whl = new THREE.Mesh(whlGeo, whlMat);
    whl.rotation.x = Math.PI / 2;
    whl.castShadow = true;
    whl.userData = {{ explodeDir: new THREE.Vector3(0, 1.6, 0), origPos: new THREE.Vector3(0, 1.65, 0) }};
    whl.position.copy(whl.userData.origPos);
    partMeshes.push(whl);
    productGroup.add(whl);

    // Spindle Hub Nut
    const nutGeo = new THREE.CylinderGeometry(0.12, 0.12, 0.16, 6);
    const nut = new THREE.Mesh(nutGeo, metalMat);
    nut.position.set(0, 1.68, 0);
    nut.userData = {{ explodeDir: new THREE.Vector3(0, 2.0, 0), origPos: nut.position.clone() }};
    partMeshes.push(nut);
    productGroup.add(nut);

  }} else if (type === 'led_bulb') {{
    // Commercial LED Luminaire / High Bay Floodlight
    // Finned Heat Sink Base
    const hsGeo = new THREE.CylinderGeometry(0.7, 0.5, 0.8, 24);
    const hs = new THREE.Mesh(hsGeo, metalMat);
    hs.castShadow = true;
    hs.userData = {{ explodeDir: new THREE.Vector3(0, -0.6, 0), origPos: new THREE.Vector3(0, 0.6, 0) }};
    hs.position.copy(hs.userData.origPos);
    partMeshes.push(hs);
    productGroup.add(hs);

    // Aluminum Heatsink cooling fins
    for (let f = 0; f < 12; f++) {{
      const a = (f / 12) * Math.PI * 2;
      const finGeo = new THREE.BoxGeometry(0.04, 0.7, 0.25);
      const fin = new THREE.Mesh(finGeo, metalMat);
      fin.position.set(Math.cos(a) * 0.65, 0.6, Math.sin(a) * 0.65);
      fin.rotation.y = -a;
      fin.userData = {{ explodeDir: new THREE.Vector3(Math.cos(a) * 0.8, -0.6, Math.sin(a) * 0.8), origPos: fin.position.clone() }};
      partMeshes.push(fin);
      productGroup.add(fin);
    }}

    // LED PCB Matrix plate
    const pcbGeo = new THREE.CylinderGeometry(0.68, 0.68, 0.05, 32);
    const pcbMat = createPBRMaterial('#059669', 0.3, 0.7);
    const pcb = new THREE.Mesh(pcbGeo, pcbMat);
    pcb.userData = {{ explodeDir: new THREE.Vector3(0, 0.4, 0), origPos: new THREE.Vector3(0, 1.05, 0) }};
    pcb.position.copy(pcb.userData.origPos);
    partMeshes.push(pcb);
    productGroup.add(pcb);

    // Frosted Optical PC Dome
    const domeGeo = new THREE.SphereGeometry(0.72, 32, 16, 0, Math.PI * 2, 0, Math.PI * 0.5);
    const dome = new THREE.Mesh(domeGeo, glassMat);
    dome.userData = {{ explodeDir: new THREE.Vector3(0, 1.2, 0), origPos: new THREE.Vector3(0, 1.1, 0) }};
    dome.position.copy(dome.userData.origPos);
    partMeshes.push(dome);
    productGroup.add(dome);

  }} else if (type === 'tmt_bar') {{
    // Ribbed TMT Steel Bar Fe 500D
    const coreGeo = new THREE.CylinderGeometry(0.18, 0.18, 3.4, 24);
    const bar = new THREE.Mesh(coreGeo, metalMat);
    bar.castShadow = true;
    bar.userData = {{ explodeDir: new THREE.Vector3(0, 0, 0), origPos: new THREE.Vector3(0, 1.7, 0) }};
    bar.position.copy(bar.userData.origPos);
    partMeshes.push(bar);
    productGroup.add(bar);

    // Transverse Lug Ribs
    for (let r = 0; r < 24; r++) {{
      const ribGeo = new THREE.TorusGeometry(0.19, 0.025, 8, 16, Math.PI * 0.85);
      const rib = new THREE.Mesh(ribGeo, metalMat);
      rib.rotation.x = Math.PI / 2;
      rib.rotation.z = (r % 2 === 0) ? 0.3 : -0.3;
      rib.position.set(0, 0.2 + r * 0.13, 0);
      rib.userData = {{ explodeDir: new THREE.Vector3((r % 2 === 0 ? 0.4 : -0.4), 0, 0), origPos: rib.position.clone() }};
      partMeshes.push(rib);
      productGroup.add(rib);
    }}

  }} else {{
    // Default Robust Industrial Box Container (Cement, Paint, Tile Adhesive, Conduit)
    const boxGeo = new THREE.BoxGeometry(1.6, 2.2, 1.1);
    const box = new THREE.Mesh(boxGeo, baseMat);
    box.castShadow = true;
    box.userData = {{ explodeDir: new THREE.Vector3(0, 0, 0), origPos: new THREE.Vector3(0, 1.1, 0) }};
    box.position.copy(box.userData.origPos);
    partMeshes.push(box);
    productGroup.add(box);

    // Cap / Lid / Sealing Band
    const capGeo = new THREE.BoxGeometry(1.68, 0.15, 1.18);
    const cap = new THREE.Mesh(capGeo, accentMat);
    cap.castShadow = true;
    cap.userData = {{ explodeDir: new THREE.Vector3(0, 1.2, 0), origPos: new THREE.Vector3(0, 2.25, 0) }};
    cap.position.copy(cap.userData.origPos);
    partMeshes.push(cap);
    productGroup.add(cap);

    // Side Handle or Bracket
    const h1Geo = new THREE.CylinderGeometry(0.04, 0.04, 0.8, 12);
    const h1 = new THREE.Mesh(h1Geo, metalMat);
    h1.position.set(0.85, 1.5, 0);
    h1.userData = {{ explodeDir: new THREE.Vector3(0.8, 0, 0), origPos: h1.position.clone() }};
    partMeshes.push(h1);
    productGroup.add(h1);
  }}

  // Center model vertically
  productGroup.position.y = 0.0;
}}

function createPBRMaterial(colorHex, metalness, roughness) {{
  return new THREE.MeshStandardMaterial({{
    color: new THREE.Color(colorHex),
    metalness: metalness,
    roughness: roughness,
    envMapIntensity: 1.0,
  }});
}}

// Exploded Assembly Interaction
function onExplodeChange(value) {{
  const factor = parseFloat(value) / 100.0;
  document.getElementById('explode-val').innerText = Math.round(value) + '%';
  partMeshes.forEach(mesh => {{
    if (mesh.userData && mesh.userData.explodeDir && mesh.userData.origPos) {{
      mesh.position.x = mesh.userData.origPos.x + mesh.userData.explodeDir.x * factor * 1.5;
      mesh.position.y = mesh.userData.origPos.y + mesh.userData.explodeDir.y * factor * 1.5;
      mesh.position.z = mesh.userData.origPos.z + mesh.userData.explodeDir.z * factor * 1.5;
    }}
  }});
}}

// Turntable Auto-Rotation
function toggleTurntable() {{
  isTurntableActive = !isTurntableActive;
  const btn = document.getElementById('btn-spin');
  if (isTurntableActive) {{
    btn.classList.add('active');
  }} else {{
    btn.classList.remove('active');
  }}
}}

// Camera Reset
function resetCamera() {{
  if (camera && controls) {{
    camera.position.set(3.5, 2.5, 4.5);
    controls.target.set(0, 0.5, 0);
    controls.update();
  }}
}}

// Shading Modes: PBR, Wireframe, Solid Clay, Technical Blueprint
function setShadingMode(mode) {{
  currentShadingMode = mode;
  ['pbr', 'wire', 'clay', 'blue'].forEach(m => {{
    const el = document.getElementById('mode-' + m);
    if (el) el.classList.remove('active');
  }});

  if (mode === 'pbr') {{
    document.getElementById('mode-pbr').classList.add('active');
    scene.background = new THREE.Color(0x0F172A);
    floorGrid.visible = true;
    partMeshes.forEach(m => {{
      if (m.material) {{
        m.material.wireframe = false;
        if (m.userData.origColor) m.material.color.set(m.userData.origColor);
      }}
    }});
  }} else if (mode === 'wireframe') {{
    document.getElementById('mode-wire').classList.add('active');
    scene.background = new THREE.Color(0x020617);
    floorGrid.visible = true;
    partMeshes.forEach(m => {{
      if (m.material) m.material.wireframe = true;
    }});
  }} else if (mode === 'clay') {{
    document.getElementById('mode-clay').classList.add('active');
    scene.background = new THREE.Color(0x1E293B);
    floorGrid.visible = false;
    partMeshes.forEach(m => {{
      if (m.material) {{
        m.material.wireframe = false;
        if (!m.userData.origColor) m.userData.origColor = m.material.color.getHex();
        m.material.color.setHex(0xE2E8F0);
        m.material.metalness = 0.05;
        m.material.roughness = 0.85;
      }}
    }});
  }} else if (mode === 'blueprint') {{
    document.getElementById('mode-blue').classList.add('active');
    scene.background = new THREE.Color(0x0A192F);
    floorGrid.visible = true;
    floorGrid.material.color.setHex(0x38BDF8);
    partMeshes.forEach(m => {{
      if (m.material) {{
        m.material.wireframe = true;
        if (!m.userData.origColor) m.userData.origColor = m.material.color.getHex();
        m.material.color.setHex(0x38BDF8);
      }}
    }});
  }}
}}

// Lighting Schemes
function setLighting(mode) {{
  ['day', 'warm', 'contrast'].forEach(m => {{
    const el = document.getElementById('light-' + m);
    if (el) el.classList.remove('active');
  }});

  if (mode === 'daylight') {{
    document.getElementById('light-day').classList.add('active');
    dirLight.intensity = 1.4;
    dirLight.color.setHex(0xFFFFFF);
    warmLight.intensity = 0.0;
    spotLight.intensity = 0.0;
    ambientLight.intensity = 0.7;
  }} else if (mode === 'warm') {{
    document.getElementById('light-warm').classList.add('active');
    dirLight.intensity = 0.6;
    warmLight.intensity = 1.6;
    spotLight.intensity = 0.0;
    ambientLight.intensity = 0.5;
  }} else if (mode === 'contrast') {{
    document.getElementById('light-contrast').classList.add('active');
    dirLight.intensity = 0.4;
    warmLight.intensity = 0.0;
    spotLight.intensity = 2.5;
    ambientLight.intensity = 0.2;
  }}
}}

// Resize Handler
function onWindowResize() {{
  const container = document.getElementById('viewer-container');
  if (camera && renderer && container) {{
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
  }}
}}

// Render Loop
function animate() {{
  requestAnimationFrame(animate);

  if (isTurntableActive && productGroup) {{
    productGroup.rotation.y += 0.008;
  }}

  if (controls) controls.update();
  if (renderer && scene && camera) renderer.render(scene, camera);
}}

// HTML5 Canvas Procedural 3D Software Fallback (Ensures 100% offline rendering)
function runSoftwareFallback() {{
  const threeCanvas = document.getElementById('three-canvas');
  threeCanvas.style.display = 'none';
  const canvas = document.getElementById('fallback-canvas');
  canvas.style.display = 'block';
  const ctx = canvas.getContext('2d');
  const container = document.getElementById('viewer-container');
  canvas.width = container.clientWidth;
  canvas.height = container.clientHeight;

  let angle = 0;
  function drawFallback() {{
    ctx.fillStyle = '#0F172A';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.save();
    ctx.translate(canvas.width / 2, canvas.height / 2);

    // Draw isometric grid
    ctx.strokeStyle = 'rgba(13, 148, 136, 0.2)';
    ctx.lineWidth = 1;
    for (let i = -150; i <= 150; i += 30) {{
      ctx.beginPath();
      ctx.moveTo(-200, i + 80);
      ctx.lineTo(200, i + 80);
      ctx.stroke();
    }}

    // Draw rotating 3D wireframe box
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    const w = 90, h = 130, d = 70;
    const vertices = [
      [-w, -h, -d], [w, -h, -d], [w, h, -d], [-w, h, -d],
      [-w, -h, d], [w, -h, d], [w, h, d], [-w, h, d]
    ].map(v => {{
      const x = v[0] * cos - v[2] * sin;
      const z = v[0] * sin + v[2] * cos;
      const y = v[1];
      const scale = 300 / (300 + z);
      return [x * scale, y * scale];
    }});

    const edges = [
      [0,1],[1,2],[2,3],[3,0],
      [4,5],[5,6],[6,7],[7,4],
      [0,4],[1,5],[2,6],[3,7]
    ];

    ctx.strokeStyle = '#0D9488';
    ctx.lineWidth = 2.5;
    edges.forEach(e => {{
      ctx.beginPath();
      ctx.moveTo(vertices[e[0]][0], vertices[e[0]][1]);
      ctx.lineTo(vertices[e[1]][0], vertices[e[1]][1]);
      ctx.stroke();
    }});

    // Center product label
    ctx.fillStyle = '#38BDF8';
    ctx.font = 'bold 13px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('{product_id}: {product_name}', 0, h + 30);
    ctx.fillStyle = '#94A3B8';
    ctx.font = '11px sans-serif';
    ctx.fillText('WebGL Offline Mode • Procedural 3D Canvas Projection', 0, h + 48);

    ctx.restore();
    if (isTurntableActive) angle += 0.015;
    requestAnimationFrame(drawFallback);
  }}
  drawFallback();
}}

// Initialize when DOM ready
window.addEventListener('DOMContentLoaded', init3D);
setTimeout(init3D, 80);
</script>
</body>
</html>"""
    return html_content


def render_3d_product_viewer(
    product_id: str,
    product_name: Optional[str] = None,
    category: Optional[str] = None,
    height_px: int = 560,
    lang: Optional[str] = None,
    lazy_load: bool = True,
    key: str = "default",
) -> None:
    """
    Renders the professional 3D Product Digital Twin & Equipment Inspector in Streamlit.
    Optimized with lazy loading to ensure 0 ms latency when collapsed or toggled off.
    """
    curr_lang = lang or get_current_language()
    specs = get_product_specs(product_id)
    p_name = product_name or specs.get("name", f"Product {product_id}")
    p_cat = category or specs.get("category", "General Hardware")

    st.markdown(
        f"""
        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:1.2rem; margin-bottom:1.2rem; box-shadow:0 1px 4px rgba(0,0,0,0.04);">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
                <div>
                    <h3 style="margin:0; color:#1E293B; font-size:1.15rem; display:flex; align-items:center; gap:8px;">
                        <span>📐</span> {t("3D Product Digital Twin & Equipment Inspector", curr_lang)}
                    </h3>
                    <p style="margin:4px 0 0 0; color:#64748B; font-size:0.83rem;">
                        {t("Interactive 360° CAD-grade WebGL model inspection, component separation, and tolerance verification.", curr_lang)}
                    </p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if lazy_load:
        c_toggle, c_info = st.columns([1.5, 3.5])
        with c_toggle:
            is_active = st.toggle(
                f"⚡ {t('Enable Interactive 3D Model', curr_lang)}",
                value=False,
                key=f"toggle_3d_{key}_{product_id}",
                help=t("Lazy-loads WebGL 3D canvas on demand to preserve maximum dashboard performance.", curr_lang),
            )
        with c_info:
            if not is_active:
                st.caption(f"💡 {t('3D model viewer is in standby mode. Toggle switch on to load interactive WebGL digital twin.', curr_lang)}")
        
        if not is_active:
            return

    # Generate and embed the 3D viewer iframe
    html_code = generate_3d_html(
        product_id=product_id,
        product_name=p_name,
        category=p_cat,
        specs=specs,
        lang=curr_lang,
        height=height_px,
    )

    components.html(html_code, height=height_px + 20, scrolling=False)
