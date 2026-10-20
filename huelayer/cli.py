"""Linha de comando: imagem -> STL + prévia + roteiro de trocas."""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

from .filament import DEFAULT_LIBRARY, Swap, auto_stack, load_library, luminance, resolve
from .heightmap import PrintSettings, heights_from_counts, layer_counts, load_image
from .optimize import PixelStats, choose_filaments, optimize_swaps, stack_error
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
        "-f", "--filament", action="append", default=[], metavar="NOME[:#RRGGBB:TD]",
        help="repita para cada filamento (nome da biblioteca ou especificação completa); "
        "a ordem é automática (escuro -> claro)",
    )
    parser.add_argument("--library", default=DEFAULT_LIBRARY, help="biblioteca de filamentos JSON")
    parser.add_argument(
        "--auto", type=int, metavar="N",
        help="escolhe os N filamentos da biblioteca que melhor reproduzem a imagem "
        "(os passados com -f entram sempre)",
    )
    parser.add_argument(
        "--optimize", action="store_true", help="otimiza as alturas de troca pelas cores da imagem"
    )
    parser.add_argument(
        "--swap", action="append", type=float, metavar="Z_MM",
        help="alturas de troca manuais (uma a menos que o número de filamentos)",
    )
    parser.add_argument("-o", "--output", default="saida", help="prefixo dos arquivos gerados")
    defaults = PrintSettings()
    for field in ("width_mm", "resolution_mm", "first_layer", "layer_height", "base_height", "max_height", "gamma"):
        parser.add_argument(f"--{field.replace('_', '-')}", type=float, default=getattr(defaults, field))
    parser.add_argument("--invert", action="store_true", help="claro = fino (backlit)")
    args = parser.parse_args(argv)
    if not args.filament and not args.auto:
        parser.error("informe filamentos com -f ou use --auto N")
    if args.swap and (args.auto or args.optimize):
        parser.error("--swap não combina com --auto/--optimize")
    return args


def build_stack(args: argparse.Namespace, settings: PrintSettings, stats: PixelStats) -> list[Swap]:
    library = load_library(args.library)
    filaments = [resolve(spec, library) for spec in args.filament]
    if args.auto:
        return choose_filaments(library, args.auto, stats, settings, required=filaments)[0]
    ordered = sorted(filaments, key=lambda f: f.luminance)
    if args.optimize:
        return optimize_swaps(ordered, stats, settings)[0]
    stack = auto_stack(filaments, settings.base_height, settings.max_height)
    if args.swap:
        if len(args.swap) != len(stack) - 1:
            raise SystemExit("--swap precisa de exatamente (filamentos - 1) valores")
        stack = [stack[0]] + [Swap(s.filament, z) for s, z in zip(stack[1:], sorted(args.swap))]
    return stack


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    settings = PrintSettings(
        width_mm=args.width_mm, resolution_mm=args.resolution_mm, first_layer=args.first_layer,
        layer_height=args.layer_height, base_height=args.base_height, max_height=args.max_height,
        invert=args.invert, gamma=args.gamma,
    )
    image = load_image(args.image, settings)
    counts = layer_counts(luminance(image), settings)
    stats = PixelStats.from_image(counts, image)
    try:
        stack = build_stack(args, settings, stats)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_stl(f"{output}.stl", heightmap_triangles(heights_from_counts(counts, settings), settings.resolution_mm))
    preview = (render(counts, stack, settings) * 255).round().astype(np.uint8)
    Image.fromarray(preview).save(f"{output}_preview.png")
    instructions = swap_instructions(stack, settings, int(counts.max()))
    Path(f"{output}_trocas.txt").write_text(instructions, encoding="utf-8")

    print(instructions, end="")
    print(f"Diferença média de cor (ΔE): {np.sqrt(stack_error(stack, stats, settings)):.1f}")
    print(f"Gerado: {output}.stl, {output}_preview.png, {output}_trocas.txt")


if __name__ == "__main__":
    main()
