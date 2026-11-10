"""
Unit and Integration Tests for 3D Product Digital Twin & Equipment Inspector
Tests Three.js HTML generation, procedural model definitions, specs lookup,
multilingual translations, and Streamlit page integration.
"""

import pytest
from components.model_3d_viewer import (
    get_product_specs,
    generate_3d_html,
    render_3d_product_viewer,
    PRODUCT_3D_SPECS,
)
from utils.translations import t


def test_product_specs_lookup():
    """Verify that product specifications are defined and retrieved accurately."""
    # Test known SKUs
    pump_specs = get_product_specs("PROD003")
    assert pump_specs["model_type"] == "pump_motor"
    assert "Submersible" in pump_specs["name"]
    assert "IP68" in pump_specs["ip_rating"]
    assert "dimensions" in pump_specs
    assert "weight" in pump_specs

    valve_specs = get_product_specs("PROD011")
    assert valve_specs["model_type"] == "brass_valve"
    assert "Brass" in valve_specs["name"]

    pipe_specs = get_product_specs("PROD001")
    assert pipe_specs["model_type"] == "steel_pipe"

    # Test unknown SKU fallback
    unknown_specs = get_product_specs("PROD999")
    assert unknown_specs is not None
    assert "model_type" in unknown_specs


def test_all_12_skus_have_valid_specs():
    """Ensure all 12 default inventory SKUs have specifications."""
    for i in range(1, 13):
        pid = f"PROD{i:03d}"
        specs = get_product_specs(pid)
        assert specs is not None
        assert "model_type" in specs
        assert "dimensions" in specs
        assert "material" in specs


def test_generate_3d_html_content():
    """Verify generated Three.js WebGL HTML includes required CAD/PBR structures."""
    specs = get_product_specs("PROD003")
    html = generate_3d_html(
        product_id="PROD003",
        product_name="Submersible Water Pump 1HP",
        category="Electrical / Machinery",
        specs=specs,
        lang="English",
        height=560,
    )

    # Core WebGL and Three.js requirements
    assert "three.min.js" in html
    assert "OrbitControls.js" in html
    assert "three-canvas" in html
    assert "fallback-canvas" in html
    assert "PROD003" in html
    assert "Submersible Water Pump 1HP" in html

    # Interactive features
    assert "Turntable Auto-Rotation" in html
    assert "Exploded Assembly View" in html
    assert "explode-slider" in html
    assert "setShadingMode" in html
    assert "Realistic PBR" in html
    assert "Wireframe Mesh" in html
    assert "Solid Clay" in html
    assert "Technical Blueprint" in html
    assert "setLighting" in html
    assert "Studio Daylight" in html
    assert "Workshop Warm" in html


def test_3d_multilingual_translation_coverage():
    """Verify that 3D viewer elements translate correctly to Hindi and Hinglish."""
    # Test English
    assert t("3D Product Digital Twin & Equipment Inspector", "English") == "3D Product Digital Twin & Equipment Inspector"
    assert t("Turntable Auto-Rotation", "English") == "Turntable Auto-Rotation"

    # Test Hindi
    hi_title = t("3D Product Digital Twin & Equipment Inspector", "हिंदी")
    assert "3D उत्पाद डिजिटल ट्विन" in hi_title
    hi_spin = t("Turntable Auto-Rotation", "हिंदी")
    assert "टर्नटेबल" in hi_spin
    hi_wire = t("Wireframe Mesh", "हिंदी")
    assert "वायरफ्रेम" in hi_wire

    # Test Hinglish
    hing_title = t("3D Product Digital Twin & Equipment Inspector", "Hinglish")
    assert "3D Product Digital Twin" in hing_title
    hing_toggle = t("Enable Interactive 3D Model", "Hinglish")
    assert "Interactive 3D Model On Karein" in hing_toggle


def test_inventory_page_runs_with_3d_viewer():
    """AppTest verifying 04_inventory_and_forecasting renders without exceptions with 3D viewer enabled."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("pages/04_inventory_and_forecasting.py", default_timeout=35)
    at.session_state["owner_authenticated"] = True
    at.session_state["user_id"] = "admin"
    at.session_state["role"] = "owner"
    at.session_state["language"] = "English"
    at.run()

    assert len(at.exception) == 0, f"Exceptions occurred on Inventory page: {[e.value for e in at.exception]}"

    # Activate 3D viewer toggle and re-run to verify WebGL iframe mounts cleanly
    if at.toggle:
        for t_widget in at.toggle:
            if "3D" in t_widget.label or "toggle_3d" in str(getattr(t_widget, "key", "")):
                t_widget.set_value(True)
        at.run()
        assert len(at.exception) == 0, f"Exceptions after toggling 3D viewer: {[e.value for e in at.exception]}"


def test_3d_model_assets_exist_and_resolve():
    """Verify that actual binary 3D CAD assets exist on disk and resolve correctly."""
    from components.model_3d_viewer import resolve_3d_asset

    # Test GLB models
    b1, fmt1 = resolve_3d_asset("PROD001")
    assert b1 is not None and len(b1) > 1000
    assert fmt1 == "glb"
    assert b1[:4] == b"glTF", "Asset must have valid glTF 2.0 binary magic header"

    b3, fmt3 = resolve_3d_asset("PROD003")
    assert b3 is not None and len(b3) > 1000
    assert fmt3 == "glb"
    assert b3[:4] == b"glTF"

    # Test STL model
    b8, fmt8 = resolve_3d_asset("PROD008")
    assert b8 is not None and len(b8) > 500
    assert fmt8 == "stl"
    assert b"solid" in b8[:20].lower()

    # Test Valve GLB
    b11, fmt11 = resolve_3d_asset("PROD011")
    assert b11 is not None and len(b11) > 1000
    assert fmt11 == "glb"


def test_3d_html_cad_loaders_and_overlay():
    """Verify generated HTML includes GLTF/STL/OBJ loaders and loading indicator."""
    import base64
    from components.model_3d_viewer import resolve_3d_asset, get_product_specs, generate_3d_html

    b, fmt = resolve_3d_asset("PROD001")
    specs = get_product_specs("PROD001")
    b64 = base64.b64encode(b).decode("ascii")

    html = generate_3d_html(
        product_id="PROD001",
        product_name="Steel Pipes",
        category="Building Materials",
        specs=specs,
        lang="English",
        model_b64=b64,
        model_format=fmt,
    )

    assert "GLTFLoader.js" in html
    assert "STLLoader.js" in html
    assert "OBJLoader.js" in html
    assert "loading-overlay" in html
    assert "Loading 3D Digital Twin..." in html
    assert "loadModelFromBase64" in html
    assert "MODEL_B64" in html

