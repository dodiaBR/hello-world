"""Filamentos e a pilha de trocas de cor."""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DEFAULT_LIBRARY = Path(__file__).with_name("filamentos.json")


@dataclass(frozen=True)
class Filament:
    name: str
    color: tuple[float, float, float]  # RGB em [0, 1]
    td: float  # Transmission Distance em mm

    @classmethod
    def parse(cls, spec: str) -> "Filament":
        """Lê o formato `Nome:#RRGGBB:TD`, ex.: `Preto:#000000:0.6`."""
        try:
            name, hex_color, td = spec.rsplit(":", 2)
            return cls(name, hex_to_rgb(hex_color), float(td))
        except ValueError as error:
            raise ValueError(f"filamento inválido {spec!r}; use Nome:#RRGGBB:TD") from error

    @property
    def luminance(self) -> float:
        return float(luminance(np.array(self.color)))


def load_library(path: str | Path = DEFAULT_LIBRARY) -> list[Filament]:
    """Lê uma lista JSON de `{"name", "color", "td"}` (outros campos, como
    `fonte`, são ignorados). A biblioteca padrão é o PLA Basic da 3D Prime:
    cores aproximadas a partir das fotos do site e TDs estimados, não medidos."""
    entries = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Filament(e["name"], hex_to_rgb(e["color"]), float(e["td"])) for e in entries]


def resolve(spec: str, library: list[Filament]) -> Filament:
    """Aceita `Nome:#RRGGBB:TD` ou só o nome de um filamento da biblioteca."""
    if ":" in spec:
        return Filament.parse(spec)
    for filament in library:
        if filament.name.casefold() == spec.casefold():
            return filament
    raise ValueError(f"filamento {spec!r} não está na biblioteca")


def hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    value = hex_color.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"cor inválida {hex_color!r}")
    return tuple(int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))


def luminance(rgb: np.ndarray) -> np.ndarray:
    """Luma Rec. 709 sobre o último eixo (canais RGB)."""
    return rgb @ np.array([0.2126, 0.7152, 0.0722])


@dataclass(frozen=True)
class Swap:
    filament: Filament
    start_z: float  # altura (mm) a partir da qual este filamento é impresso


def auto_stack(filaments: list[Filament], base_height: float, max_height: float) -> list[Swap]:
    """Ordena do mais escuro ao mais claro e distribui as trocas por igual
    entre a base e a altura máxima — o mesmo ponto de partida que o HueForge
    oferece antes do ajuste manual dos sliders."""
    ordered = sorted(filaments, key=lambda f: f.luminance)
    span = max_height - base_height
    return [
        Swap(filament, 0.0 if i == 0 else base_height + span * i / len(ordered))
        for i, filament in enumerate(ordered)
    ]
