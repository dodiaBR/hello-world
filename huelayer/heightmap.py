"""Conversão de imagem em mapa de alturas quantizado por camada."""

from dataclasses import dataclass

import numpy as np
from PIL import Image

from .filament import luminance


@dataclass(frozen=True)
class PrintSettings:
    width_mm: float = 100.0
    resolution_mm: float = 0.2  # tamanho de cada amostra do mapa no plano XY
    first_layer: float = 0.16
    layer_height: float = 0.08
    base_height: float = 0.48  # espessura mínima (pixels mais escuros)
    max_height: float = 2.0
    invert: bool = False  # True: claro = fino (modo backlit/litofania)

    def layer_top(self, index: np.ndarray | int) -> np.ndarray | float:
        """Altura do topo da camada `index` (0 = primeira camada)."""
        return self.first_layer + np.asarray(index) * self.layer_height

    def layer_index(self, z: float) -> int:
        """Primeira camada cujo topo fica acima de `z`."""
        if z < self.first_layer:
            return 0
        return int(np.floor(round((z - self.first_layer) / self.layer_height, 6))) + 1


def load_luminance(path: str, settings: PrintSettings) -> np.ndarray:
    """Abre a imagem, redimensiona para a resolução de impressão e devolve a
    luminância em [0, 1] (linha 0 = topo da imagem)."""
    image = Image.open(path).convert("RGB")
    columns = max(2, round(settings.width_mm / settings.resolution_mm))
    rows = max(2, round(columns * image.height / image.width))
    image = image.resize((columns, rows), Image.Resampling.LANCZOS)
    return luminance(np.asarray(image, dtype=float) / 255)


def layer_counts(lum: np.ndarray, settings: PrintSettings) -> np.ndarray:
    """Número de camadas impressas em cada pixel.

    Front-lit (padrão): claro = mais alto, pois as camadas claras do topo
    cobrem a base escura. A altura é linear na luminância e arredondada para
    a camada mais próxima."""
    if settings.invert:
        lum = 1 - lum
    heights = settings.base_height + lum * (settings.max_height - settings.base_height)
    counts = np.rint((heights - settings.first_layer) / settings.layer_height) + 1
    return np.maximum(counts, 1).astype(int)


def heights_from_counts(counts: np.ndarray, settings: PrintSettings) -> np.ndarray:
    return settings.layer_top(counts - 1)
