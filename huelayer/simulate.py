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


def color_table(stack: list[Swap], settings: PrintSettings, max_count: int) -> np.ndarray:
    """Cor vista de cima para cada número de camadas: `table[n]` é a cor de
    uma coluna com `n` camadas (`table[0]` não é usado).

    A primeira camada é tratada como fundo opaco; cada camada seguinte é
    misturada por cima com a opacidade dada pela sua espessura e TD. Como a
    cor só depende do número de camadas, a imagem inteira sai desta tabela."""
    table = np.zeros((max_count + 1, 3))
    table[1] = filament_at(settings.first_layer, stack).filament.color
    for count in range(2, max_count + 1):
        filament = filament_at(settings.layer_top(count - 1), stack).filament
        alpha = layer_opacity(settings.layer_height, filament.td)
        table[count] = table[count - 1] + alpha * (np.array(filament.color) - table[count - 1])
    return table


def render(counts: np.ndarray, stack: list[Swap], settings: PrintSettings) -> np.ndarray:
    """Prévia RGB em [0, 1] do relevo `counts` impresso com `stack`."""
    return color_table(stack, settings, int(counts.max()))[counts]
