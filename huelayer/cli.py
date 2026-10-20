"""Linha de comando: imagem -> 3MF/STL + prévia + roteiro de trocas."""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

from .filament import DEFAULT_LIBRARY, Filament, Swap, auto_stack, load_library, luminance, resolve
from .heightmap import PrintSettings, add_border, heights_from_counts, layer_counts, load_image
from .optimize import PixelStats, choose_filaments, optimize_swaps, stack_error
from .simulate import render
from .stl import heightmap_triangles, write_stl
from .threemf import write_3mf


def swap_layers(stack: list[Swap], settings: PrintSettings, total_layers: int) -> list[tuple[int | None, Filament]]:
    """Índice da primeira camada de cada filamento após o primeiro, ou None
    quando ele começaria acima do topo da peça."""
    result = []
    for swap in stack[1:]:
        index = settings.layer_index(swap.start_z)
        result.append((index if index < total_layers else None, swap.filament))
    return result


def swap_instructions(stack: list[Swap], settings: PrintSettings, total_layers: int) -> str:
    # Slot do AMS = posição na pilha (1 = base), para o roteiro e o fatiador usarem a mesma numeração.
    lines = [
        f"Primeira camada: {settings.first_layer:g} mm; demais: {settings.layer_height:g} mm",
        "Slots (AMS): " + ", ".join(f"{slot} = {s.filament.name}" for slot, s in enumerate(stack, 1)),
        f"Comece com: {stack[0].filament.name} (slot 1)",
    ]
    for slot, (index, filament) in enumerate(swap_layers(stack, settings, total_layers), 2):
        if index is None:
            lines.append(f"(ignorado: {filament.name} começaria acima do topo da peça)")
        else:
            z = settings.layer_top(index)
            lines.append(f"Camada {index + 1} (Z={z:.2f} mm): troque para {filament.name} (slot {slot})")
    lines += [
        "",
        "Como aplicar:",
        "- PrusaSlicer: abra o .3mf; as trocas já vêm marcadas.",
        "- Bambu Studio / OrcaSlicer: abra o .3mf (ou .stl), ajuste a altura da primeira",
        "  camada e das demais como acima, fatie e, na barra de camadas da prévia, vá a",
        "  cada camada listada e clique no '+' com o botão direito. Com AMS, escolha a",
        "  troca para o slot indicado; sem AMS, adicione uma pausa e troque à mão.",
        "  Esses fatiadores ignoram trocas vindas de 3MF de outros programas.",
    ]
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
    parser.add_argument("--border-mm", type=float, default=0.0, help="largura da moldura (0 = sem)")
    parser.add_argument("--border-height", type=float, help="altura da moldura (padrão: --max-height)")
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

    error = stack_error(stack, stats, settings)
    border_height = settings.max_height if args.border_height is None else args.border_height
    counts = add_border(counts, settings, args.border_mm, border_height)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    triangles = heightmap_triangles(heights_from_counts(counts, settings), settings.resolution_mm)
    total_layers = int(counts.max())
    changes = [
        (float(settings.layer_top(index)), filament)
        for index, filament in swap_layers(stack, settings, total_layers) if index is not None
    ]
    write_3mf(f"{output}.3mf", triangles, changes, settings.layer_height, name=output.name)
    write_stl(f"{output}.stl", triangles)
    preview = (render(counts, stack, settings) * 255).round().astype(np.uint8)
    Image.fromarray(preview).save(f"{output}_preview.png")
    instructions = swap_instructions(stack, settings, total_layers)
    Path(f"{output}_trocas.txt").write_text(instructions, encoding="utf-8")

    print(instructions, end="")
    print(f"Diferença média de cor (ΔE): {np.sqrt(error):.1f}")
    print(f"Gerado: {output}.3mf, {output}.stl, {output}_preview.png, {output}_trocas.txt")


if __name__ == "__main__":
    main()
