"""Prévia da cor resultante do empilhamento de filamentos translúcidos."""

import numpy as np

from .filament import Swap
from .heightmap import PrintSettings

# Fração de luz que atravessa uma espessura igual à TD. A TD é medida como a
# espessura em que o filamento "some" contra uma luz de fundo, então 2% de
# transmissão é uma aproximação razoável de opaco.
TRANSMISSION_AT_TD = 0.02


def layer_opacity(thickness: float, td: float) -> float:
    """Opacidade de uma camada pelo modelo de Beer-Lambert: N camadas finas
    somam o mesmo que uma camada grossa da mesma espessura total."""
    return 1 - TRANSMISSION_AT_TD ** (thickness / td)


def filament_at(z: float, stack: list[Swap]) -> Swap:
    current = stack[0]
    for swap in stack:
        if z > swap.start_z:
            current = swap
    return current


def render(counts: np.ndarray, stack: list[Swap], settings: PrintSettings) -> np.ndarray:
    """Compõe as camadas de baixo para cima e devolve RGB em [0, 1].

    A primeira camada é tratada como fundo opaco; cada camada seguinte é
    misturada por cima com a opacidade dada pela sua espessura e TD."""
    image = np.empty(counts.shape + (3,))
    image[:] = filament_at(settings.first_layer, stack).filament.color
    for index in range(1, int(counts.max())):
        top = settings.layer_top(index)
        filament = filament_at(top, stack).filament
        alpha = layer_opacity(settings.layer_height, filament.td)
        printed = counts > index
        image[printed] += alpha * (np.array(filament.color) - image[printed])
    return image
