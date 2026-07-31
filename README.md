# Corte de Trajetoria - Documentação do Sistema

Este repositório contém dois scripts Python para trabalhar com nuvens de pontos `LAZ/LAS` e trajetórias de drone em arquivos `.pos`.

## Componentes

### `split_by_trajectory.PY`
Responsável por dividir uma nuvem de pontos em múltiplas saídas de acordo com trajetórias temporais.

#### O que faz
- Localiza um arquivo `*.laz` ou `*.las` na mesma pasta do script.
- Carrega todos os arquivos `.pos` da subpasta `trajetorias/`.
- Para cada `.pos`, extrai o intervalo de tempo do nome do arquivo, por exemplo `393922.217_395164.993.pos`.
- Lê as linhas de dados do `.pos`, ignora cabeçalhos e usa as colunas de GPS (`gx`, `gy`, `gz`) para criar interpoladores de posição com `scipy.interpolate.interp1d`.
- Abre o arquivo LAZ em chunks de até 1.000.000 de pontos.
- Para cada ponto, compara o tempo GPS com o intervalo de cada trajetória e calcula a distância 3D entre o ponto e a posição interpolada dessa trajetória.
- Atribui cada ponto à trajetória mais próxima, quando o tempo está dentro da margem temporal definida.
- Pontos que não se enquadram em nenhuma trajetória são classificados como `orphans`.

#### Configurações principais
- `CHUNK_SIZE = 1_000_000`: controla quantos pontos são processados por vez.
- `TIME_MARGIN = 3.0`: margem em segundos além do intervalo de cada `.pos` para permitir pequenos desalinhamentos.
- `TRAJ_DIR = trajectorias/`: pasta onde os arquivos `.pos` devem estar.

#### Saída
- Gera um arquivo `.laz` para cada trajetória, com o nome base do arquivo original seguido de `__<trajetoria>.laz`.
- Cria também um arquivo `__orphans.laz` com pontos não atribuídos.
- Copia o header completo do LAZ original (`offsets`, `scales`, `vlrs`, projeção, outros metadados) para os arquivos de saída.

#### Detalhes importantes
- Usa `find_files_nocase()` para evitar duplicação de arquivos em Windows, onde `glob` diferencia maiúsculas/minúsculas de forma inconsistente.
- Atribuição é feita por distância quadrada (`dist2`) para eficiência.
- Se houver mais de um arquivo LAZ/LAS na pasta, usa o primeiro encontrado e informa no console.

### `analyze_pointclouds.py`
Faz uma análise simples de atributos em arquivos `*.laz` na pasta atual.

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
