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
- Uma curva (`--gamma`) redistribui as camadas: gamma > 1 dá mais camadas aos
  tons claros, gamma < 1 aos escuros — o papel dos ajustes de contraste/curva
  do HueForge.
- No modo litofania/backlit a relação se inverte (claro = fino).

Em `huelayer`: `heightmap.py` (`layer_counts`).

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

### 4. Otimização automática

O HueForge sugere filamentos e posições de troca; aqui isso é feito por
otimização (`optimize.py`):

- **Observação-chave:** a cor de um pixel depende só do número de camadas dele.
  A imagem é resumida, por número de camadas, em quantidade de pixels, soma e
  soma dos quadrados das cores-alvo. Com isso o erro de uma pilha é calculado
  sobre ~25 valores, não sobre milhões de pixels.
- O erro é a diferença de cor média em **CIELAB** (ΔE), que segue melhor a
  percepção humana do que RGB.
- `--optimize`: descida por coordenadas nas alturas de troca — move uma troca
  por vez para a camada que mais reduz o erro, até estabilizar.
- `--auto N`: testa todas as combinações de N filamentos da biblioteca
  (`filamentos.json` ou `--library`), cada uma com trocas otimizadas, e fica
  com a melhor. Filamentos passados com `-f` entram sempre.

Limitação estrutural (compartilhada com o HueForge): a altura vem só da
luminância. Regiões de cores diferentes mas mesmo brilho recebem o mesmo
número de camadas e, portanto, a mesma cor impressa.

### 5. Prévia

A cor de cada pixel é calculada compondo as camadas de baixo para cima: a
primeira camada é o fundo opaco e cada camada seguinte é misturada por cima com
a opacidade da etapa 2 (`simulate.render`). É por isso que a prévia mostra
“bandas” de cor — cada banda é uma camada.

### 6. Exportação

- **STL**: o mapa de alturas vira um sólido fechado (topo em relevo, paredes
  laterais e fundo), com normais para fora (`stl.py`). Os testes verificam que
  a malha é estanque.
- **3MF com trocas embutidas** (`threemf.py`): além da malha, o arquivo leva
  `Metadata/Prusa_Slicer_custom_gcode_per_print_z.xml`, onde cada troca é um
  color change (`type="0"`, `M600`) na altura Z do topo da primeira camada do
  novo filamento, com a cor dele. Também leva `Metadata/Slic3r_PE_model.config`
  com a altura de camada **por objeto**, para o fatiador cortar exatamente nas
  alturas usadas no cálculo, qualquer que seja o perfil escolhido. Esse
  arquivo precisa declarar o `<volume>` cobrindo todos os triângulos; sem isso
  o PrusaSlicer monta o objeto vazio (“No outline can be derived”).
  Os nomes de arquivo e atributos foram conferidos nas strings do próprio
  binário do PrusaSlicer 2.7.2, e o teste `test_prusaslicer_inserts_color_changes`
  fatia o 3MF e confere no G-code que cada `;COLOR_CHANGE` cai na camada e na
  cor certas.
  A **primeira camada** é ajuste de impressão, não de objeto: o perfil do
  fatiador precisa usar a mesma (`--first-layer`, padrão 0,16 mm).
- **Roteiro de trocas** (`_trocas.txt`): o mesmo plano em texto, com o passo
  a passo para fatiadores em que o 3MF não traz as trocas.

### Por que o 3MF não traz as trocas no Bambu Studio e no OrcaSlicer

Conclusão da leitura do código-fonte dos dois (`src/libslic3r/Format/bbs_3mf.cpp`,
`src/libslic3r/Model.cpp` e `src/slic3r/GUI/Plater.cpp`):

- As trocas ficam em `Metadata/custom_gcode_per_layer.xml`
  (`<custom_gcodes_per_layer><plate><plate_info id="1"/><layer top_z=… type="0" …/>`).
- A interface só copia as trocas lidas para o projeto quando também carrega a
  configuração do arquivo (`load_config`); fora disso o bloco é ignorado.
- **Bambu Studio:** `load_config` só fica ativo quando o metadado `Application`
  começa com `BambuStudio-`. Senão o arquivo é tratado como “not from Bambu
  Lab” e só a geometria é carregada.
- **OrcaSlicer:** para um 3MF de terceiros (`From_Other`), `load_config` é
  desligado quando o arquivo não traz `project_settings.config`. Se trouxesse,
  essa configuração passaria a valer como perfil do projeto, substituindo a
  impressora e os filamentos de quem abre.
- O caminho de 3MF “do PrusaSlicer” dos dois (`From_Prusa`) tem a leitura de
  `Prusa_Slicer_custom_gcode_per_print_z.xml` comentada.

Por isso, sem `--printer`, as trocas são inseridas à mão na barra de camadas
seguindo o `_trocas.txt` (a numeração é a mesma da barra: camada 1 = primeira
camada).

### Projeto nativo (`--printer a1` / `--printer a1mini`, `bambu.py`)

Quando se quer que o projeto já abra configurado, o arquivo segue o formato
de projeto do Bambu Studio, que o OrcaSlicer também lê:

- `Application` = `BambuStudio-02.00.00.00`. É a condição para a configuração
  ser carregada. 2.0.0 fica acima do limite das migrações de projetos antigos
  (< 2.0.0) e abaixo de qualquer versão atual (sem aviso de “arquivo mais
  novo”). No Orca, projetos até 2.3.2 sem a etiqueta do Orca mantêm a
  configuração. A descrição do modelo registra que o arquivo foi gerado pelo
  huelayer.
- Malha em `3D/Objects/object_1.model`, referenciada por componente no
  `3D/3dmodel.model`, com `3D/_rels/3dmodel.model.rels`. Esse arquivo também
  impede que o 3MF seja tomado por um do PrusaSlicer
  (`PrusaFileParser::check_3mf_from_prusa`).
- `Metadata/model_settings.config`: objeto no filamento 1, placa 1, centrado na
  mesa.
- `Metadata/project_settings.config` (JSON de strings / listas de strings):
  nomeia os perfis do sistema (`printer_settings_id`, `print_settings_id`,
  `filament_settings_id`). Em `PresetCollection::load_external_preset`, todo
  valor fora de `different_settings_to_system` é substituído pelo do perfil
  instalado (`update_non_diff_values_to_base_config`), e o perfil é
  selecionado sem marca de modificado. Assim o arquivo não copia os perfis da
  Bambu e sempre usa a versão instalada. Ajustes intencionais (ex.:
  `--first-layer 0.16`) são listados ali e aparecem como modificados.
  `filament_colour` e a matriz de purga são configurações do projeto
  (`s_project_options`) e não alteram os perfis.
- `Metadata/custom_gcode_per_layer.xml`: cada troca é `ToolChange` (`type="2"`)
  para o filamento N, no modo `MultiAsSingle` (um bico, vários filamentos: o
  AMS troca sozinho), em `top_z` = topo da primeira camada do novo filamento.

O que não foi possível verificar aqui: abrir o arquivo nas interfaces do
Bambu Studio e do OrcaSlicer (não há binário deles neste ambiente). O formato
foi derivado do código-fonte e os testes conferem cada regra acima.
- **Moldura** (`--border-mm`, `--border-height`): faixa de altura fixa em volta
  da imagem.

## Cobertura em relação ao HueForge

| Recurso do HueForge | Situação |
|---|---|
| Curva de altura não linear / ajuste de contraste | gamma (`--gamma`) |
| Pintura manual de regiões / máscaras | não |
| Biblioteca de filamentos com TDs | sim (`filamentos.json`, `--library`) |
| Sugestão automática de filamentos a partir da imagem | sim (`--auto N`, `--optimize`) |
| Borda/moldura | sim (`--border-mm`) |
| Texto na peça | não |
| Exportação 3MF com trocas embutidas | PrusaSlicer (verificado fatiando); Bambu Studio/OrcaSlicer como projeto nativo com `--printer` |
| Interface gráfica com prévia em tempo real | não (CLI) |

## Valores de TD

A biblioteca padrão traz as 19 cores do PLA Basic da 3D Prime. As cores foram
amostradas das fotos dos carretéis no site (Cinza Escuro e Azul Bebê são
estimadas). A 3D Prime não publica TD, então os TDs são **estimativas** por
tipo de cor, **não medidas**. TD varia por marca,
cor e até lote; para bons resultados meça os seus filamentos.
