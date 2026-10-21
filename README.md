# huelayer

Reimplementação clean-room, open-source, do fluxo de “pintura com filamentos”
popularizado pelo HueForge: transforma uma imagem num relevo para impressora 3D
FDM que, impresso trocando de filamento em camadas específicas, reproduz a
imagem graças à translucidez de cada filamento.

A análise de como o processo funciona está em
[docs/ENGENHARIA_REVERSA.md](docs/ENGENHARIA_REVERSA.md).

## Instalação

```sh
pip install -r requirements.txt
```

## Uso

```sh
python -m huelayer foto.jpg \
  -f "Preto:#111111:0.6" -f "Azul:#1f4fbf:1.2" \
  -f "Amarelo:#f2d21b:3.0" -f "Branco:#ffffff:2.5" \
  --width-mm 100 -o saida/foto
```

Cada `-f` é `Nome:#RRGGBB:TD` (TD em mm) ou só o nome de um filamento da
biblioteca (`huelayer/filamentos.json`: as 19 cores do PLA Basic da 3D Prime,
com cores aproximadas a partir das fotos do site e TDs estimados). A ordem é
automática, do mais escuro ao mais claro. Gera:

- `saida/foto.3mf` — o modelo com as trocas de filamento já marcadas
  (PrusaSlicer: abra e fatie; as trocas aparecem como color changes `M600`
  com a altura de camada certa; use primeira camada de 0,16 mm ou a de
  `--first-layer`);
- `saida/foto.stl` — só a malha, para outros fatiadores. Para o Bambu Studio e
  o OrcaSlicer use `--printer` (abaixo); sem ele, as trocas são adicionadas à
  mão na barra de camadas (detalhes em
  [docs/ENGENHARIA_REVERSA.md](docs/ENGENHARIA_REVERSA.md));
- `saida/foto_preview.png` — prévia simulada da cor impressa;
- `saida/foto_trocas.txt` — em que camada trocar cada filamento.

### Bambu Lab A1 / A1 mini (Bambu Studio e OrcaSlicer)

```sh
python -m huelayer foto.jpg -f Preto --auto 4 --printer a1mini -o saida/foto
```

Com `--printer a1` ou `--printer a1mini`, o `.3mf` vira um projeto do Bambu
Studio/OrcaSlicer: ao abrir, já vêm a impressora (`Bambu Lab A1 mini 0.4
nozzle`), o processo (`0.08mm High Quality @BBL A1M`, com velocidades e
larguras de linha oficiais), os filamentos com as cores certas e as trocas
pelo AMS marcadas na barra de camadas. O relevo é calculado nas alturas desse
perfil (primeira camada de 0,2 mm). Os perfis vêm da instalação de quem abre;
o arquivo só os nomeia. Os filamentos usam o perfil `Generic PLA`; troque
para o seu perfil de filamento se tiver um. Antes de imprimir, confira os
volumes de purga em “Volumes de descarga” (o arquivo traz uma estimativa).

### Deixar o programa escolher

```sh
# Otimiza as alturas de troca para os filamentos dados
python -m huelayer foto.jpg -f Preto -f Vermelho -f Laranja -f Amarelo --optimize

# Escolhe os 4 filamentos da biblioteca que melhor reproduzem a imagem
# (Preto entra sempre)
python -m huelayer foto.jpg -f Preto --auto 4
```

O programa informa a diferença média de cor (ΔE em CIELAB) entre a prévia e a
imagem: quanto menor, mais fiel.

Opções úteis: `--gamma` (curva de altura: >1 dá mais camadas aos claros),
`--border-mm` (moldura), `--layer-height`, `--first-layer`, `--base-height`,
`--max-height`, `--resolution-mm`, `--invert` (litofania) e `--swap Z_MM`
(repetido, para escolher as alturas de troca manualmente).

## Testes

```sh
python -m unittest
```

Se o PrusaSlicer estiver instalado (`prusa-slicer` no PATH), um teste extra
fatia o 3MF gerado e confere as trocas no G-code.
