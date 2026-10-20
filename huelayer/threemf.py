"""Exportação 3MF com as trocas de filamento embutidas.

Além da malha, grava o arquivo de "custom G-code por altura" do PrusaSlicer:
ao abrir o 3MF, as trocas já aparecem na barra de camadas como color changes
(M600), cada uma com a cor do filamento seguinte.
"""

import zipfile
from xml.sax.saxutils import quoteattr

import numpy as np

from .filament import Filament

# Tipo 0 = ColorChange no enum CustomGCode::Type do PrusaSlicer.
COLOR_CHANGE = 0

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>
"""

RELATIONSHIPS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""


def indexed_mesh(triangles: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Converte triângulos soltos (N, 3, 3) em vértices únicos + índices."""
    points = triangles.reshape(-1, 3).round(6)
    vertices, inverse = np.unique(points, axis=0, return_inverse=True)
    return vertices, inverse.reshape(-1, 3)


def model_xml(triangles: np.ndarray, name: str) -> str:
    vertices, faces = indexed_mesh(triangles)
    vertex_lines = "\n".join(f'<vertex x="{x:.6g}" y="{y:.6g}" z="{z:.6g}"/>' for x, y, z in vertices)
    face_lines = "\n".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in faces)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
 <metadata name="Application">huelayer</metadata>
 <resources>
  <object id="1" type="model" name={quoteattr(name)}>
   <mesh>
    <vertices>
{vertex_lines}
    </vertices>
    <triangles>
{face_lines}
    </triangles>
   </mesh>
  </object>
 </resources>
 <build>
  <item objectid="1"/>
 </build>
</model>
"""


def prusa_color_changes_xml(changes: list[tuple[float, Filament]]) -> str:
    codes = "\n".join(
        f' <code print_z="{z:.4f}" type="{COLOR_CHANGE}" extruder="1" color="{rgb_to_hex(f.color)}"'
        f" extra={quoteattr(f.name)} gcode=\"M600\"/>"
        for z, f in changes
    )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<custom_gcodes_per_print_z>
{codes}
 <mode value="SingleExtruder"/>
</custom_gcodes_per_print_z>
"""


def prusa_model_config_xml(name: str, layer_height: float, triangle_count: int) -> str:
    """Altura de camada por objeto, para o fatiador cortar nas mesmas alturas
    em que as trocas foram calculadas. (A primeira camada é ajuste de
    impressão, não de objeto: precisa ser configurada no perfil.)

    Quando este arquivo existe, o PrusaSlicer monta os volumes do objeto a
    partir dele; sem o `<volume>` cobrindo todos os triângulos, o objeto
    chega vazio ao fatiamento."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<config>
 <object id="1" instances_count="1">
  <metadata type="object" key="name" value={quoteattr(name)}/>
  <metadata type="object" key="layer_height" value="{layer_height:g}"/>
  <volume firstid="0" lastid="{triangle_count - 1}">
   <metadata type="volume" key="name" value={quoteattr(name)}/>
  </volume>
 </object>
</config>
"""


def rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(c * 255):02X}" for c in rgb)


def write_3mf(
    path: str, triangles: np.ndarray, changes: list[tuple[float, Filament]],
    layer_height: float, name: str = "huelayer",
) -> None:
    """`changes` são pares (Z do topo da primeira camada do novo filamento,
    filamento), em ordem de altura."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("_rels/.rels", RELATIONSHIPS)
        archive.writestr("3D/3dmodel.model", model_xml(triangles, name))
        archive.writestr("Metadata/Slic3r_PE_model.config", prusa_model_config_xml(name, layer_height, len(triangles)))
        archive.writestr("Metadata/Prusa_Slicer_custom_gcode_per_print_z.xml", prusa_color_changes_xml(changes))
