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

Cada `-f` é `Nome:#RRGGBB:TD` (TD em mm). A ordem é automática, do mais
escuro ao mais claro. Gera:

- `saida/foto.stl` — o modelo para fatiar;
- `saida/foto_preview.png` — prévia simulada da cor impressa;
- `saida/foto_trocas.txt` — em que camada trocar cada filamento.

Opções úteis: `--layer-height`, `--first-layer`, `--base-height`,
`--max-height`, `--resolution-mm`, `--invert` (litofania) e `--swap Z_MM`
(repetido, para escolher as alturas de troca manualmente).

## Testes

```sh
python -m unittest
```
