"""Exportação do mapa de alturas como sólido fechado em STL binário."""

import struct

import numpy as np


def heightmap_triangles(heights: np.ndarray, pixel_mm: float) -> np.ndarray:
    """Triângulos (N, 3, 3) de um sólido com topo em relevo, paredes e fundo.

    A linha 0 do mapa (topo da imagem) fica no maior Y, para a peça não sair
    espelhada no fatiador."""
    rows, columns = heights.shape
    xs = np.arange(columns) * pixel_mm
    ys = (rows - 1 - np.arange(rows)) * pixel_mm
    x, y = np.meshgrid(xs, ys)
    top = np.stack([x, y, heights], axis=-1)
    bottom = np.stack([x, y, np.zeros_like(heights)], axis=-1)

    def grid_quads(grid: np.ndarray, flip: bool) -> list[np.ndarray]:
        a, b = grid[:-1, :-1], grid[:-1, 1:]
        c, d = grid[1:, :-1], grid[1:, 1:]
        first, second = np.stack([a, c, b], -2), np.stack([b, c, d], -2)
        if flip:
            first, second = first[..., ::-1, :], second[..., ::-1, :]
        return [first.reshape(-1, 3, 3), second.reshape(-1, 3, 3)]

    def wall(upper: np.ndarray, lower: np.ndarray, flip: bool) -> list[np.ndarray]:
        a, b, c, d = upper[:-1], upper[1:], lower[:-1], lower[1:]
        first, second = np.stack([a, c, b], -2), np.stack([b, c, d], -2)
        if flip:
            first, second = first[:, ::-1], second[:, ::-1]
        return [first, second]

    parts = grid_quads(top, flip=False) + grid_quads(bottom, flip=True)
    parts += wall(top[0], bottom[0], flip=True)  # borda de Y máximo
    parts += wall(top[-1], bottom[-1], flip=False)  # borda de Y mínimo
    parts += wall(top[:, 0], bottom[:, 0], flip=False)  # borda de X mínimo
    parts += wall(top[:, -1], bottom[:, -1], flip=True)  # borda de X máximo
    return np.concatenate(parts)


def write_stl(path: str, triangles: np.ndarray) -> None:
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.divide(normals, lengths, out=np.zeros_like(normals), where=lengths > 0)

    record = np.zeros(
        len(triangles), dtype=[("normal", "<f4", 3), ("vertices", "<f4", (3, 3)), ("attr", "<u2")]
    )
    record["normal"] = normals
    record["vertices"] = triangles
    with open(path, "wb") as file:
        file.write(b"huelayer heightmap".ljust(80, b"\0"))
        file.write(struct.pack("<I", len(triangles)))
        file.write(record.tobytes())
