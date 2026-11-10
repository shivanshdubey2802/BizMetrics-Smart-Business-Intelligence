"""
Script to generate valid 3D model assets for BizMetrics Digital Twin.
Creates .glb, .stl, and .obj models in assets/3d_models/
"""
import os
import math
import struct
import json

def create_stl_cylinder(filename, radius, height, radial_segments=32):
    """Generate an ASCII STL model of an industrial flanged cylinder/fitting."""
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"solid IndustrialFitting\n")
        # Generate vertices for top and bottom circles
        half_h = height / 2.0
        angle_step = 2.0 * math.pi / radial_segments
        
        # Side facets
        for i in range(radial_segments):
            a1 = i * angle_step
            a2 = (i + 1) * angle_step
            
            x1, z1 = radius * math.cos(a1), radius * math.sin(a1)
            x2, z2 = radius * math.cos(a2), radius * math.sin(a2)
            
            # Normal for side quad
            mid_a = (a1 + a2) / 2.0
            nx, nz = math.cos(mid_a), math.sin(mid_a)
            
            # Triangle 1
            f.write(f"  facet normal {nx:.4f} 0.0000 {nz:.4f}\n")
            f.write("    outer loop\n")
            f.write(f"      vertex {x1:.4f} {-half_h:.4f} {z1:.4f}\n")
            f.write(f"      vertex {x2:.4f} {-half_h:.4f} {z2:.4f}\n")
            f.write(f"      vertex {x1:.4f} {half_h:.4f} {z1:.4f}\n")
            f.write("    endloop\n")
            f.write("  endfacet\n")
            
            # Triangle 2
            f.write(f"  facet normal {nx:.4f} 0.0000 {nz:.4f}\n")
            f.write("    outer loop\n")
            f.write(f"      vertex {x2:.4f} {-half_h:.4f} {z2:.4f}\n")
            f.write(f"      vertex {x2:.4f} {half_h:.4f} {z2:.4f}\n")
            f.write(f"      vertex {x1:.4f} {half_h:.4f} {z1:.4f}\n")
            f.write("    endloop\n")
            f.write("  endfacet\n")

            # Top cap
            f.write("  facet normal 0.0000 1.0000 0.0000\n")
            f.write("    outer loop\n")
            f.write(f"      vertex 0.0000 {half_h:.4f} 0.0000\n")
            f.write(f"      vertex {x1:.4f} {half_h:.4f} {z1:.4f}\n")
            f.write(f"      vertex {x2:.4f} {half_h:.4f} {z2:.4f}\n")
            f.write("    endloop\n")
            f.write("  endfacet\n")

            # Bottom cap
            f.write("  facet normal 0.0000 -1.0000 0.0000\n")
            f.write("    outer loop\n")
            f.write(f"      vertex 0.0000 {-half_h:.4f} 0.0000\n")
            f.write(f"      vertex {x2:.4f} {-half_h:.4f} {z2:.4f}\n")
            f.write(f"      vertex {x1:.4f} {-half_h:.4f} {z1:.4f}\n")
            f.write("    endloop\n")
            f.write("  endfacet\n")

        f.write("endsolid IndustrialFitting\n")
    print(f"Created STL: {filename}")


def create_obj_bracket(filename):
    """Generate a Wavefront OBJ model of an industrial mounting bracket with bolt holes."""
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    obj_content = """# BizMetrics 3D Mounting Bracket OBJ
o MountingBracket
v -1.5000 0.0000 -1.0000
v 1.5000 0.0000 -1.0000
v 1.5000 0.0000 1.0000
v -1.5000 0.0000 1.0000
v -1.5000 0.4000 -1.0000
v 1.5000 0.4000 -1.0000
v 1.5000 0.4000 1.0000
v -1.5000 0.4000 1.0000
v -1.5000 2.2000 -1.0000
v -1.1000 2.2000 -1.0000
v -1.1000 2.2000 1.0000
v -1.5000 2.2000 1.0000
vn 0.0 1.0 0.0
vn 0.0 -1.0 0.0
vn 1.0 0.0 0.0
vn -1.0 0.0 0.0
vn 0.0 0.0 1.0
vn 0.0 0.0 -1.0
s 1
f 1//2 2//2 3//2 4//2
f 5//1 8//1 7//1 6//1
f 1//6 5//6 6//6 2//6
f 2//3 6//3 7//3 3//3
f 3//5 7//5 8//5 4//5
f 4//4 8//4 5//4 1//4
f 5//4 12//4 9//4 8//4
f 8//5 11//5 12//5 7//5
f 12//1 11//1 10//1 9//1
f 9//6 10//6 6//6 5//6
"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(obj_content)
    print(f"Created OBJ: {filename}")


def build_mesh_glb(positions, indices, normals=None, name="MeshPart"):
    """Build a binary glTF 2.0 (.glb) container from raw geometry arrays."""
    pos_bytes = struct.pack(f'<{len(positions)}f', *positions)
    idx_bytes = struct.pack(f'<{len(indices)}H', *indices)
    
    pad_idx = (4 - (len(idx_bytes) % 4)) % 4
    idx_bytes += b'\x00' * pad_idx

    min_pos = [
        min(positions[i] for i in range(0, len(positions), 3)),
        min(positions[i+1] for i in range(0, len(positions), 3)),
        min(positions[i+2] for i in range(0, len(positions), 3)),
    ]
    max_pos = [
        max(positions[i] for i in range(0, len(positions), 3)),
        max(positions[i+1] for i in range(0, len(positions), 3)),
        max(positions[i+2] for i in range(0, len(positions), 3)),
    ]

    has_normals = normals is not None and len(normals) == len(positions)
    if has_normals:
        norm_bytes = struct.pack(f'<{len(normals)}f', *normals)
        bin_data = idx_bytes + pos_bytes + norm_bytes
    else:
        bin_data = idx_bytes + pos_bytes

    pad_bin = (4 - (len(bin_data) % 4)) % 4
    bin_data += b'\x00' * pad_bin

    buffer_views = [
        {"buffer": 0, "byteOffset": 0, "byteLength": len(idx_bytes), "target": 34963}, # ELEMENT_ARRAY_BUFFER
        {"buffer": 0, "byteOffset": len(idx_bytes), "byteLength": len(pos_bytes), "target": 34962}, # ARRAY_BUFFER
    ]
    accessors = [
        {
            "bufferView": 0,
            "byteOffset": 0,
            "componentType": 5123, # UNSIGNED_SHORT
            "count": len(indices),
            "type": "SCALAR",
            "max": [max(indices)],
            "min": [min(indices)],
        },
        {
            "bufferView": 1,
            "byteOffset": 0,
            "componentType": 5126, # FLOAT
            "count": len(positions) // 3,
            "type": "VEC3",
            "max": max_pos,
            "min": min_pos,
        }
    ]

    primitives_attr = {"POSITION": 1}

    if has_normals:
        buffer_views.append({
            "buffer": 0,
            "byteOffset": len(idx_bytes) + len(pos_bytes),
            "byteLength": len(norm_bytes),
            "target": 34962
        })
        accessors.append({
            "bufferView": 2,
            "byteOffset": 0,
            "componentType": 5126,
            "count": len(normals) // 3,
            "type": "VEC3",
            "max": [1.0, 1.0, 1.0],
            "min": [-1.0, -1.0, -1.0],
        })
        primitives_attr["NORMAL"] = 2

    gltf_dict = {
        "asset": {"version": "2.0", "generator": "BizMetrics 3D CAD Exporter"},
        "scenes": [{"nodes": [0]}],
        "scene": 0,
        "nodes": [{"mesh": 0, "name": name}],
        "meshes": [{
            "name": name,
            "primitives": [{
                "attributes": primitives_attr,
                "indices": 0,
                "mode": 4, # TRIANGLES
                "material": 0
            }]
        }],
        "materials": [{
            "name": f"{name}Material",
            "pbrMetallicRoughness": {
                "baseColorFactor": [0.05, 0.58, 0.53, 1.0],
                "metallicFactor": 0.85,
                "roughnessFactor": 0.25
            }
        }],
        "buffers": [{"byteLength": len(bin_data)}],
        "bufferViews": buffer_views,
        "accessors": accessors,
    }

    json_str = json.dumps(gltf_dict)
    json_bytes = json_str.encode("utf-8")
    pad_json = (4 - (len(json_bytes) % 4)) % 4
    json_bytes += b' ' * pad_json

    total_len = 12 + 8 + len(json_bytes) + 8 + len(bin_data)
    header = struct.pack('<4sII', b'glTF', 2, total_len)
    json_chunk = struct.pack('<II', len(json_bytes), 0x4E4F534A) + json_bytes
    bin_chunk = struct.pack('<II', len(bin_data), 0x004E4942) + bin_data
    return header + json_chunk + bin_chunk


def generate_flanged_pipe_glb(filename):
    """Generate a detailed 3D flanged pipe model in binary GLB format."""
    positions = []
    normals = []
    indices = []

    # Outer pipe cylinder + 2 flange discs
    def add_cylinder(r_top, r_bot, y_bot, y_top, segs=24):
        base_idx = len(positions) // 3
        # Ring 0 (bottom)
        for i in range(segs):
            a = 2.0 * math.pi * i / segs
            ca, sa = math.cos(a), math.sin(a)
            positions.extend([r_bot * ca, y_bot, r_bot * sa])
            normals.extend([ca, 0.0, sa])
        # Ring 1 (top)
        for i in range(segs):
            a = 2.0 * math.pi * i / segs
            ca, sa = math.cos(a), math.sin(a)
            positions.extend([r_top * ca, y_top, r_top * sa])
            normals.extend([ca, 0.0, sa])

        # Faces
        for i in range(segs):
            n = (i + 1) % segs
            p0 = base_idx + i
            p1 = base_idx + n
            p2 = base_idx + segs + i
            p3 = base_idx + segs + n
            indices.extend([p0, p1, p2, p1, p3, p2])

    # Central pipe
    add_cylinder(0.4, 0.4, -2.0, 2.0, segs=32)
    # Bottom flange
    add_cylinder(0.9, 0.9, -2.2, -1.9, segs=32)
    # Top flange
    add_cylinder(0.9, 0.9, 1.9, 2.2, segs=32)
    # Mid-collar reinforcing ring
    add_cylinder(0.55, 0.55, -0.2, 0.2, segs=32)

    glb_data = build_mesh_glb(positions, indices, normals, name="FlangedSteelPipe")
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "wb") as f:
        f.write(glb_data)
    print(f"Created GLB: {filename} ({len(glb_data)} bytes)")


def generate_valve_glb(filename):
    """Generate an authentic brass / steel gate valve model in binary GLB format."""
    positions = []
    normals = []
    indices = []

    def add_cylinder(r, y_bot, y_top, segs=24):
        base_idx = len(positions) // 3
        for i in range(segs):
            a = 2.0 * math.pi * i / segs
            ca, sa = math.cos(a), math.sin(a)
            positions.extend([r * ca, y_bot, r * sa])
            normals.extend([ca, 0.0, sa])
        for i in range(segs):
            a = 2.0 * math.pi * i / segs
            ca, sa = math.cos(a), math.sin(a)
            positions.extend([r * ca, y_top, r * sa])
            normals.extend([ca, 0.0, sa])
        for i in range(segs):
            n = (i + 1) % segs
            p0 = base_idx + i
            p1 = base_idx + n
            p2 = base_idx + segs + i
            p3 = base_idx + segs + n
            indices.extend([p0, p1, p2, p1, p3, p2])

    # Main Valve Body (Horizontal sphere/cylinder)
    add_cylinder(0.5, -1.2, 1.2, segs=24)
    # Vertical Bonnet Tower
    add_cylinder(0.4, 0.0, 1.6, segs=24)
    # Stem
    add_cylinder(0.12, 1.6, 2.3, segs=16)
    # Control Handwheel disc
    add_cylinder(0.85, 2.2, 2.4, segs=32)

    glb_data = build_mesh_glb(positions, indices, normals, name="IndustrialValve")
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "wb") as f:
        f.write(glb_data)
    print(f"Created GLB: {filename} ({len(glb_data)} bytes)")


def generate_pump_motor_glb(filename):
    """Generate an electric submersible pump / high-torque motor model in binary GLB format."""
    positions = []
    normals = []
    indices = []

    def add_cylinder(r, y_bot, y_top, segs=24):
        base_idx = len(positions) // 3
        for i in range(segs):
            a = 2.0 * math.pi * i / segs
            ca, sa = math.cos(a), math.sin(a)
            positions.extend([r * ca, y_bot, r * sa])
            normals.extend([ca, 0.0, sa])
        for i in range(segs):
            a = 2.0 * math.pi * i / segs
            ca, sa = math.cos(a), math.sin(a)
            positions.extend([r * ca, y_top, r * sa])
            normals.extend([ca, 0.0, sa])
        for i in range(segs):
            n = (i + 1) % segs
            p0 = base_idx + i
            p1 = base_idx + n
            p2 = base_idx + segs + i
            p3 = base_idx + segs + n
            indices.extend([p0, p1, p2, p1, p3, p2])

    # Motor housing
    add_cylinder(0.75, -1.8, 0.8, segs=32)
    # Cooling fin / stage ring 1
    add_cylinder(0.85, -1.2, -1.0, segs=32)
    # Cooling fin / stage ring 2
    add_cylinder(0.85, -0.6, -0.4, segs=32)
    # Cooling fin / stage ring 3
    add_cylinder(0.85, 0.0, 0.2, segs=32)
    # Impeller casing
    add_cylinder(0.65, 0.8, 1.8, segs=32)
    # Discharge nozzle
    add_cylinder(0.28, 1.8, 2.4, segs=24)

    glb_data = build_mesh_glb(positions, indices, normals, name="SubmersiblePumpMotor")
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "wb") as f:
        f.write(glb_data)
    print(f"Created GLB: {filename} ({len(glb_data)} bytes)")


if __name__ == "__main__":
    base_dir = os.path.join(os.path.dirname(__file__), "..", "assets", "3d_models")
    os.makedirs(base_dir, exist_ok=True)
    generate_flanged_pipe_glb(os.path.join(base_dir, "flanged_steel_pipe.glb"))
    generate_valve_glb(os.path.join(base_dir, "industrial_valve.glb"))
    generate_pump_motor_glb(os.path.join(base_dir, "submersible_pump_motor.glb"))
    create_stl_cylinder(os.path.join(base_dir, "industrial_flange.stl"), radius=1.2, height=0.4, radial_segments=36)
    create_obj_bracket(os.path.join(base_dir, "machined_bracket.obj"))
    print("All 3D assets generated successfully!")
