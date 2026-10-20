"""Escolha automática das alturas de troca e dos filamentos.

Como a cor de um pixel só depende do número de camadas dele, basta resumir a
imagem por número de camadas (quantidade de pixels, soma e soma dos
quadrados das cores-alvo). O erro de qualquer pilha vira então uma conta sobre
poucas dezenas de valores, o que permite testar milhares de pilhas.
"""

from dataclasses import dataclass
from itertools import combinations

import numpy as np

from .filament import Filament, Swap
from .heightmap import PrintSettings
from .simulate import color_table


def srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """sRGB em [0, 1] -> CIELAB (D65). Distâncias em Lab acompanham melhor a
    diferença de cor percebida do que distâncias em RGB."""
    linear = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    xyz = linear @ np.array(
        [[0.4124, 0.2126, 0.0193], [0.3576, 0.7152, 0.1192], [0.1805, 0.0722, 0.9505]]
    )
    xyz /= np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack(
        [116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1
    )


@dataclass(frozen=True)
class PixelStats:
    """Cores-alvo (Lab) agrupadas pelo número de camadas de cada pixel."""

    count: np.ndarray  # (max_count + 1,)
    total: np.ndarray  # (max_count + 1, 3)
    squares: np.ndarray  # (max_count + 1,)

    @classmethod
    def from_image(cls, counts: np.ndarray, target_rgb: np.ndarray) -> "PixelStats":
        size = int(counts.max()) + 1
        flat, lab = counts.ravel(), srgb_to_lab(target_rgb).reshape(-1, 3)
        total = np.stack([np.bincount(flat, lab[:, i], size) for i in range(3)], -1)
        return cls(np.bincount(flat, minlength=size), total, np.bincount(flat, (lab**2).sum(1), size))

    @property
    def max_count(self) -> int:
        return len(self.count) - 1

    def error(self, table_lab: np.ndarray) -> float:
        """Erro quadrático médio em Lab: Σ |cor(n) - alvo|² / pixels."""
        squared = self.count * (table_lab**2).sum(1) - 2 * (table_lab * self.total).sum(1) + self.squares
        return float(squared.sum() / self.count.sum())


def stack_from_layers(filaments: list[Filament], starts: list[int], settings: PrintSettings) -> list[Swap]:
    """`starts[i]` é o índice (0 = primeira) da camada em que o filamento
    `i + 1` começa."""
    return [Swap(filaments[0], 0.0)] + [
        Swap(filament, float(settings.layer_top(start - 1))) for filament, start in zip(filaments[1:], starts)
    ]


def stack_error(stack: list[Swap], stats: PixelStats, settings: PrintSettings) -> float:
    return stats.error(srgb_to_lab(color_table(stack, settings, stats.max_count)))


def optimize_swaps(
    filaments: list[Filament], stats: PixelStats, settings: PrintSettings
) -> tuple[list[Swap], float]:
    """Descida por coordenadas: move uma troca de cada vez para a camada que
    mais reduz o erro, mantendo a ordem, até nenhuma troca melhorar.

    Cada filamento ocupa pelo menos uma camada, então a peça precisa ter mais
    camadas que filamentos."""
    swaps, layers = len(filaments) - 1, stats.max_count
    if swaps >= layers:
        raise ValueError(f"a peça tem só {layers} camadas para {len(filaments)} filamentos")
    starts = [round(1 + (layers - 1) * (i + 1) / (swaps + 1)) for i in range(swaps)]
    starts = [min(max(start, 1 + i), layers - swaps + i) for i, start in enumerate(starts)]

    def error_of(candidate: list[int]) -> float:
        return stack_error(stack_from_layers(filaments, candidate, settings), stats, settings)

    best = error_of(starts)
    improved = True
    while improved:
        improved = False
        for i in range(swaps):
            low = starts[i - 1] + 1 if i > 0 else 1
            high = starts[i + 1] - 1 if i < swaps - 1 else layers - 1
            for start in range(low, high + 1):
                candidate = starts[:i] + [start] + starts[i + 1 :]
                error = error_of(candidate)
                if error < best - 1e-9:
                    best, starts, improved = error, candidate, True
    return stack_from_layers(filaments, starts, settings), best


def choose_filaments(
    library: list[Filament], amount: int, stats: PixelStats, settings: PrintSettings,
    required: list[Filament] = (),
) -> tuple[list[Swap], float]:
    """Testa todas as combinações de `amount` filamentos da biblioteca (sempre
    incluindo `required`), cada uma com as trocas otimizadas, e devolve a
    melhor pilha."""
    optional = [f for f in library if f not in required]
    if amount < len(required) or amount > len(required) + len(optional):
        raise ValueError(f"não dá para escolher {amount} filamentos dessa biblioteca")
    best: tuple[list[Swap], float] | None = None
    for extra in combinations(optional, amount - len(required)):
        ordered = sorted([*required, *extra], key=lambda f: f.luminance)
        result = optimize_swaps(ordered, stats, settings)
        if best is None or result[1] < best[1]:
            best = result
    return best
