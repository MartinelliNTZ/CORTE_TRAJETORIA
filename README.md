# Corte de Trajetoria - Documentação do Sistema

Este repositório contém dois scripts Python para trabalhar com nuvens de pontos `LAZ/LAS` e trajetórias de drone em arquivos `.pos`.

## Componentes

### `core/las_manager.py`
Classe `LasManager` responsável por abrir um arquivo `LAZ/LAS`, calcular estatísticas e criar arquivos de saída para cada trajetória.

#### O que faz
- Abre a nuvem de pontos com `laspy` usando o mesmo header do arquivo original.
- Itera o arquivo em chunks definidos por `CHUNK_SIZE`.
- Calcula média de atributos numéricos e detecta atributos de texto/flags.
- Prepara writers para cada trajetória e para pontos órfãos.
- Escreve pontos atribuídos em arquivos separados conforme o resultado de `TrajectoryManager`.

### `core/trajectory_manager.py`
Classe `TrajectoryManager` responsável por carregar arquivos `.pos` e atribuir pontos a trajetórias.

#### O que faz
- Encontra arquivos `.pos` em `trajetorias/` sem duplicações caso o Windows seja case-insensitive.
- Extrai intervalo de tempo do nome do arquivo (`TSTART_TEND.pos`).
- Lê as colunas de tempo e posição GPS e cria interpoladores de posição (`x`, `y`, `z`).
- Para cada ponto de nuvem, compara o tempo GPS e calcula a distância 3D até cada trajetória válida.
- Retorna o índice da trajetória mais próxima ou `-1` para órfãos.

### `main.py`
Ponto de entrada do sistema.

#### O que faz
- Define constantes do sistema (`CHUNK_SIZE`, `TIME_MARGIN`, `TRAJ_DIR`).
- Instancia `TrajectoryManager` e `LasManager`.
- Carrega trajetórias e analisa a nuvem de pontos.
- Executa a atribuição de pontos e salva arquivos separados para cada trajetória e para órfãos.

### `core/analyze_pointclouds.py`
Módulo que reúne a lógica de análise de nuvem de pontos em um pacote reutilizável.

#### O que faz
- Expõe `PointCloudAnalyzer`, que usa `LasManager` para calcular estatísticas de um arquivo `LAZ`.
- Pode ser usado diretamente em outros scripts ou via o wrapper `analyze_pointclouds.py`.

#### Observações
- Não altera nem salva nada quando usado apenas para análise.
- Depende de `laspy[lazrs]`, `numpy` e `scipy`.

#### O que faz
- Encontra todos os arquivos `*.laz` no diretório de execução.
- Para cada arquivo, abre com `laspy` e conta o total de pontos.
- Itera o arquivo em chunks e identifica atributos numéricos presentes no primeiro chunk.
- Calcula a média de cada atributo numérico válido.
- Marca atributos de texto/flag como existentes, sem cálculo de média.

#### Resultado
- Exibe no console:
  - total de pontos
  - número de atributos numéricos detectados
  - média de cada atributo numérico
  - atributos de texto/flags encontrados

#### Observações
- Não altera nem salva nada.
- Depende de `laspy[lazrs]` e `numpy`.

## Dependências

Instale as bibliotecas necessárias antes de executar os scripts:

```bash
pip install laspy[lazrs] numpy scipy
```

Para `analyze_pointclouds.py`, basta:

```bash
pip install laspy[lazrs] numpy
```

## Uso

### Dividir por trajetória
1. Coloque o arquivo `*.laz` ou `*.las` na mesma pasta de `split_by_trajectory.PY`.
2. Coloque os arquivos `.pos` em `trajetorias/`.
3. Execute:

```bash
python split_by_trajectory.py
```

### Analisar nuvens de pontos
Simplesmente execute:

```bash
python analyze_pointclouds.py
```

## Fluxo de processamento

1. `split_by_trajectory.PY` carrega trajetórias e cria interpoladores de posição temporal.
2. Ele abre o LAZ original em chunks e extrai coordenadas `(x, y, z)` e `gps_time`.
3. Para cada chunk, calcula a melhor trajetória para cada ponto com base em distância 3D e tempo GPS.
4. Escreve os pontos atribuídos em arquivos separados e os não atribuídos em `__orphans.laz`.
5. `analyze_pointclouds.py` permite verificar rapidamente quantos pontos e atributos existem nos arquivos `.laz`.

## Avisos

- A precisão da atribuição depende da qualidade dos tempos GPS nos arquivos `.pos` e no LAZ.
- O uso de `TIME_MARGIN` ajuda a capturar pontos próximos do início/fim de uma trajetória.
- Se um ponto estiver dentro da janela temporal de várias trajetórias, ele será atribuído à mais próxima em distância 3D.
