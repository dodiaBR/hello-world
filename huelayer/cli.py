"""Linha de comando: imagem -> STL + prévia + roteiro de trocas."""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

from .filament import Filament, Swap, auto_stack
from .heightmap import PrintSettings, heights_from_counts, layer_counts, load_luminance
from .simulate import render
from .stl import heightmap_triangles, write_stl


def swap_instructions(stack: list[Swap], settings: PrintSettings, total_layers: int) -> str:
    lines = [f"Comece com: {stack[0].filament.name}"]
    for swap in stack[1:]:
        index = settings.layer_index(swap.start_z)
        if index >= total_layers:
            lines.append(f"(ignorado: {swap.filament.name} começaria acima do topo da peça)")
            continue
        z = settings.layer_top(index)
        lines.append(f"Camada {index + 1} (Z={z:.2f} mm): troque para {swap.filament.name}")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="huelayer", description=__doc__)
    parser.add_argument("image")
    parser.add_argument(
        "-f", "--filament", action="append", required=True, metavar="NOME:#RRGGBB:TD",
        help="repita para cada filamento; a ordem é automática (escuro -> claro)",
    )
    parser.add_argument(
        "--swap", action="append", type=float, metavar="Z_MM",
        help="alturas de troca manuais (uma a menos que o número de filamentos)",
    )
    parser.add_argument("-o", "--output", default="saida", help="prefixo dos arquivos gerados")
    defaults = PrintSettings()
    for field in ("width_mm", "resolution_mm", "first_layer", "layer_height", "base_height", "max_height"):
        parser.add_argument(f"--{field.replace('_', '-')}", type=float, default=getattr(defaults, field))
    parser.add_argument("--invert", action="store_true", help="claro = fino (backlit)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    settings = PrintSettings(
        args.width_mm, args.resolution_mm, args.first_layer, args.layer_height,
        args.base_height, args.max_height, args.invert,
    )
    filaments = [Filament.parse(spec) for spec in args.filament]
    stack = auto_stack(filaments, settings.base_height, settings.max_height)
    if args.swap:
        if len(args.swap) != len(stack) - 1:
            raise SystemExit("--swap precisa de exatamente (filamentos - 1) valores")
        stack = [stack[0]] + [Swap(s.filament, z) for s, z in zip(stack[1:], sorted(args.swap))]

    counts = layer_counts(load_luminance(args.image, settings), settings)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    write_stl(f"{output}.stl", heightmap_triangles(heights_from_counts(counts, settings), settings.resolution_mm))
    preview = (render(counts, stack, settings) * 255).round().astype(np.uint8)
    Image.fromarray(preview).save(f"{output}_preview.png")
    instructions = swap_instructions(stack, settings, int(counts.max()))
    Path(f"{output}_trocas.txt").write_text(instructions, encoding="utf-8")

    print(instructions, end="")
    print(f"Gerado: {output}.stl, {output}_preview.png, {output}_trocas.txt")


if __name__ == "__main__":
    main()
