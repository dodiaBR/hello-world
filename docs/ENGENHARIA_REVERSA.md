# Engenharia reversa do HueForge

## Escopo e método

Esta é uma reimplementação **clean-room**: o comportamento foi deduzido do que
o HueForge mostra publicamente (interface, documentação, arquivos que ele
exporta e vídeos da comunidade). **Nenhum binário foi descompilado** e nenhum
código ou asset do HueForge foi copiado. O HueForge é software comercial; este
projeto não usa o nome dele como marca e não tenta ler os formatos
proprietários dele (`.hfp`).

## Como o HueForge funciona (modelo deduzido)

### 1. Imagem → mapa de alturas

- A imagem é convertida para luminância (tons de cinza).
- Cada pixel vira uma coluna de plástico. No modo padrão (iluminação frontal),
  **pixel claro = coluna alta**: a base é um filamento escuro e as camadas
  claras empilhadas por cima “clareiam” a cor que se vê de cima.
- A altura vai de uma espessura mínima de base até uma altura máxima, sempre
  arredondada para um múltiplo da altura de camada (a primeira camada costuma
  ser mais grossa).
- No modo litofania/backlit a relação se inverte (claro = fino).

Em `huelayer`: `heightmap.py` (`layer_counts`, mapeamento linear).

### 2. Transmission Distance (TD)

A ideia central do HueForge. TD é a espessura, em mm, a partir da qual um
filamento deixa de deixar passar luz de forma perceptível. É medida
imprimindo uma escada de espessuras contra uma luz de fundo.

- Filamento com TD baixa (preto, ~0,6 mm) cobre rápido.
- Filamento com TD alta (amarelo, branco, 2 a 5 mm) é translúcido: várias
  camadas finas deixam a cor de baixo aparecer, criando degradês e cores
  intermediárias que nenhum filamento tem sozinho.

Em `huelayer` a opacidade de uma camada de espessura `t` segue Beer-Lambert:

```
opacidade = 1 - 0,02^(t / TD)
```

ou seja, com espessura igual à TD passa 2% da luz. Esse modelo tem uma
propriedade importante: 10 camadas de 0,1 mm dão exatamente o mesmo resultado
que uma camada de 1 mm. A constante exata que o HueForge usa não é pública;
0,02 foi escolhida por bater visualmente com prévias e impressões reais e pode
ser calibrada (`simulate.TRANSMISSION_AT_TD`).

### 3. Pilha de filamentos e trocas

- Os filamentos são ordenados do mais escuro (base) ao mais claro (topo).
- Cada filamento “começa” numa altura. No HueForge isso são os sliders da
  lista de filamentos; aqui a distribuição inicial é uniforme entre a base e a
  altura máxima (`filament.auto_stack`) e pode ser sobrescrita com `--swap`.
- Uma camada usa o filamento cuja altura de início está abaixo do topo dela.

### 4. Prévia

A cor de cada pixel é calculada compondo as camadas de baixo para cima: a
primeira camada é o fundo opaco e cada camada seguinte é misturada por cima com
a opacidade da etapa 2 (`simulate.render`). É por isso que a prévia mostra
“bandas” de cor — cada banda é uma camada.

### 5. Exportação

- **STL**: o mapa de alturas vira um sólido fechado (topo em relevo, paredes
  laterais e fundo), com normais para fora (`stl.py`). Os testes verificam que
  a malha é estanque.
- **Roteiro de trocas**: em que número de camada e altura Z pausar e trocar o
  filamento. No fatiador (PrusaSlicer, Bambu Studio, Orca) isso vira um
  “color change”/pausa naquela camada.

## O que ficou de fora (próximos passos)

| Recurso do HueForge | Situação |
|---|---|
| Curva de altura não linear / ajuste de contraste | ainda não (mapeamento linear) |
| Pintura manual de regiões / máscaras | não |
| Biblioteca de filamentos com TDs | não (passados por linha de comando) |
| Sugestão automática de filamentos a partir da imagem | não |
| Borda/moldura e texto na peça | não |
| Exportação 3MF com trocas embutidas | não (STL + texto) |
| Interface gráfica com prévia em tempo real | não (CLI) |

## Valores de TD

Os TDs dos exemplos são valores típicos, **não medidas**. TD varia por marca,
cor e até lote; para bons resultados meça os seus filamentos.
