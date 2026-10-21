"""Projeto 3MF para Bambu Studio e OrcaSlicer (A1 e A1 mini com AMS Lite).

Ao abrir, o projeto já vem com impressora, processo e filamentos selecionados
e com as trocas de filamento marcadas na barra de camadas.

Como funciona (lido do código-fonte dos dois fatiadores, `bbs_3mf.cpp`,
`Plater.cpp` e `PresetBundle.cpp`):

- A configuração do projeto só é carregada se o metadado `Application` do
  modelo começar com `BambuStudio-`; sem isso os dois carregam só a geometria.
- `project_settings.config` nomeia os perfis do sistema (`print_settings_id`,
  `printer_settings_id`, `filament_settings_id`). Ao carregar, todo valor que
  não está listado em `different_settings_to_system` é trocado pelo valor do
  perfil oficial instalado. Por isso o arquivo não copia os perfis: vale a
  versão dos perfis de quem abre, e eles abrem sem a marca de modificado.
- As trocas são `ToolChange` (tipo 2) para o filamento N, no modo
  `MultiAsSingle`: um bico, vários filamentos (o AMS troca sozinho).
"""

import json
import uuid
import zipfile
from dataclasses import dataclass
from xml.sax.saxutils import quoteattr

import numpy as np

from .filament import Filament
from .threemf import CONTENT_TYPES, indexed_mesh, rgb_to_hex

# Declarar 2.0.0 evita as migrações de projetos antigos (< 2.0.0) e o aviso de
# "arquivo de versão mais nova" em qualquer Bambu Studio 2.x. No OrcaSlicer,
# projetos até 2.3.2 sem a etiqueta do Orca mantêm a configuração.
BAMBU_FORMAT_VERSION = "02.00.00.00"
TOOL_CHANGE = 2  # CustomGCode::Type::ToolChange
NAMESPACE = uuid.UUID("9b0a5c56-1f5e-4f0e-9a51-4c1f7d0a3e21")


@dataclass(frozen=True)
class Printer:
    model: str
    machine_profile: str
    process_profile: str
    profile_suffix: str  # perfis de filamento são "<perfil> <sufixo>", ex.: "Bambu PLA Basic @BBL A1M"
    bed_mm: tuple[float, float]
    # Alturas do perfil de processo: o relevo é calculado nelas para o perfil
    # abrir sem modificação.
    first_layer: float = 0.2
    layer_height: float = 0.08

    def filament_profile(self, filament: Filament) -> tuple[str, str]:
        """Nome do perfil de filamento do sistema e o id dele."""
        if filament.profile:
            return f"{filament.profile} {self.profile_suffix}", filament.filament_id or ""
        return f"Generic PLA {self.profile_suffix}", "GFL99"


PRINTERS = {
    "a1mini": Printer(
        "Bambu Lab A1 mini", "Bambu Lab A1 mini 0.4 nozzle", "0.08mm High Quality @BBL A1M",
        "@BBL A1M", (180, 180),
    ),
    "a1": Printer(
        "Bambu Lab A1", "Bambu Lab A1 0.4 nozzle", "0.08mm High Quality @BBL A1",
        "@BBL A1", (256, 256),
    ),
}

ROOT_RELATIONSHIPS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""

MODEL_RELATIONSHIPS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/Objects/object_1.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""

MODEL_HEADER = (
    '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"'
    ' xmlns:BambuStudio="http://schemas.bambulab.com/package/2021"'
    ' xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p">'
)


def flush_volumes(filaments: list[Filament]) -> list[str]:
    """Matriz N×N de purga (mm³), de linha = filamento atual para coluna =
    próximo. Estimativa: base de 140 mm³ e até +560 mm³ quando o próximo é
    mais claro, já que o escuro residual aparece mais num filamento claro."""
    matrix = []
    for current in filaments:
        for following in filaments:
            if current is following:
                matrix.append("0")
            else:
                lighter = max(0.0, following.luminance - current.luminance)
                matrix.append(f"{140 + 560 * lighter:.0f}")
    return matrix


def project_settings(printer: Printer, filaments: list[Filament], process_overrides: dict[str, str]) -> dict:
    count = len(filaments)
    profiles = [printer.filament_profile(f) for f in filaments]
    return {
        "name": "project_settings",
        "from": "project",
        "version": BAMBU_FORMAT_VERSION,
        "printer_technology": "FFF",
        "printer_model": printer.model,
        "nozzle_diameter": ["0.4"],
        "printer_settings_id": printer.machine_profile,
        "print_settings_id": printer.process_profile,
        "filament_settings_id": [name for name, _ in profiles],
        "filament_ids": [filament_id for _, filament_id in profiles],
        "filament_type": ["PLA"] * count,
        "filament_colour": [rgb_to_hex(f.color) for f in filaments],
        "layer_height": f"{printer.layer_height:g}",
        "initial_layer_print_height": f"{printer.first_layer:g}",
        **process_overrides,
        # Ordem: processo, cada filamento, impressora.
        "inherits_group": [""] * (count + 2),
        "different_settings_to_system": [";".join(sorted(process_overrides))] + [""] * (count + 1),
        "flush_volumes_matrix": flush_volumes(filaments),
        "flush_volumes_vector": ["140", "140"] * count,
        "flush_multiplier": ["1"],
    }


def object_model(vertices: np.ndarray, faces: np.ndarray) -> str:
    vertex_lines = "\n".join(f'     <vertex x="{x:.6g}" y="{y:.6g}" z="{z:.6g}"/>' for x, y, z in vertices)
    face_lines = "\n".join(f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in faces)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
{MODEL_HEADER}
 <metadata name="BambuStudio:3mfVersion">1</metadata>
 <resources>
  <object id="1" p:UUID="{uuid.uuid5(NAMESPACE, 'mesh')}" type="model">
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
 <build/>
</model>
"""


def root_model(name: str, transform: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
{MODEL_HEADER}
 <metadata name="Application">BambuStudio-{BAMBU_FORMAT_VERSION}</metadata>
 <metadata name="BambuStudio:3mfVersion">1</metadata>
 <metadata name="Title">{name}</metadata>
 <metadata name="Description">Gerado por huelayer</metadata>
 <resources>
  <object id="2" p:UUID="{uuid.uuid5(NAMESPACE, 'object')}" type="model">
   <components>
    <component p:path="/3D/Objects/object_1.model" objectid="1" p:UUID="{uuid.uuid5(NAMESPACE, 'component')}" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>
   </components>
  </object>
 </resources>
 <build p:UUID="{uuid.uuid5(NAMESPACE, 'build')}">
  <item objectid="2" p:UUID="{uuid.uuid5(NAMESPACE, 'item')}" transform="{transform}" printable="1"/>
 </build>
</model>
"""


def model_settings(name: str, transform: str) -> str:
    quoted = quoteattr(name)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<config>
  <object id="2">
    <metadata key="name" value={quoted}/>
    <metadata key="extruder" value="1"/>
    <part id="1" subtype="normal_part">
      <metadata key="name" value={quoted}/>
      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>
      <metadata key="extruder" value="1"/>
    </part>
  </object>
  <plate>
    <metadata key="plater_id" value="1"/>
    <metadata key="plater_name" value=""/>
    <metadata key="locked" value="false"/>
    <model_instance>
      <metadata key="object_id" value="2"/>
      <metadata key="instance_id" value="0"/>
    </model_instance>
  </plate>
  <assemble>
   <assemble_item object_id="2" instance_id="0" transform="{transform}" offset="0 0 0"/>
  </assemble>
</config>
"""


def tool_changes(changes: list[tuple[float, int, Filament]]) -> str:
    """`changes`: (Z do topo da primeira camada do novo filamento, slot 1-based, filamento)."""
    layers = "\n".join(
        f'<layer top_z="{z:.4f}" type="{TOOL_CHANGE}" extruder="{slot}" color="{rgb_to_hex(f.color)}"'
        ' extra="" gcode="tool_change"/>'
        for z, slot, f in changes
    )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<custom_gcodes_per_layer>
<plate>
<plate_info id="1"/>
{layers}
<mode value="MultiAsSingle"/>
</plate>
</custom_gcodes_per_layer>
"""


def write_bambu_3mf(
    path: str, triangles: np.ndarray, filaments: list[Filament], changes: list[tuple[float, int, Filament]],
    printer: Printer, name: str, process_overrides: dict[str, str] | None = None,
) -> None:
    """Grava o projeto. O objeto usa o filamento 1 (base); as trocas levam
    aos demais. `process_overrides` são ajustes do perfil de processo que
    diferem do oficial (ex.: outra altura de camada), marcados como tal."""
    vertices, faces = indexed_mesh(triangles)
    low, high = vertices.min(0), vertices.max(0)
    size = high - low
    if size[0] > printer.bed_mm[0] or size[1] > printer.bed_mm[1]:
        raise ValueError(
            f"a peça ({size[0]:.0f} x {size[1]:.0f} mm) não cabe na mesa da {printer.model} "
            f"({printer.bed_mm[0]} x {printer.bed_mm[1]} mm)"
        )
    vertices = vertices - [low[0] + size[0] / 2, low[1] + size[1] / 2, low[2]]
    cx, cy = printer.bed_mm[0] / 2, printer.bed_mm[1] / 2
    transform = f"1 0 0 0 1 0 0 0 1 {cx:g} {cy:g} 0"
    settings = project_settings(printer, filaments, process_overrides or {})

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("_rels/.rels", ROOT_RELATIONSHIPS)
        archive.writestr("3D/_rels/3dmodel.model.rels", MODEL_RELATIONSHIPS)
        archive.writestr("3D/3dmodel.model", root_model(name, transform))
        archive.writestr("3D/Objects/object_1.model", object_model(vertices, faces))
        archive.writestr("Metadata/model_settings.config", model_settings(name, transform))
        archive.writestr("Metadata/project_settings.config", json.dumps(settings, indent=4, ensure_ascii=False))
        archive.writestr("Metadata/custom_gcode_per_layer.xml", tool_changes(changes))
