"""
split_by_trajectory.py
======================
Divide uma nuvem de pontos LAZ/LAS entre múltiplas trajetórias de drone,
usando GPSTime + distância 3D para atribuir cada ponto à trajetória correta.

Correções v2:
  - Não duplica trajetórias no Windows (glob case-insensitive)
  - Copia o header COMPLETO do LAZ original (VLRs, projeção, offsets, escalas)
  - Arquivos de saída abrem corretamente no LiDAR 360 e outros softwares

Dependências:
    pip install laspy[lazrs] numpy scipy

Uso:
    Coloque o script na mesma pasta do arquivo .laz
    Coloque os .pos na subpasta 'trajetorias/'
    Execute: python split_by_trajectory.py
"""

import os
import re
import sys
import time
import glob
import numpy as np
import laspy
from scipy.interpolate import interp1d


# ─────────────────────────────────────────────────────────────────
# Configurações
# ─────────────────────────────────────────────────────────────────

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
TRAJ_DIR    = os.path.join(SCRIPT_DIR, "trajetorias")
CHUNK_SIZE  = 1_000_000  # pontos por chunk (ajuste conforme RAM disponível)
TIME_MARGIN = 3.0        # segundos de margem além do intervalo do .pos


# ─────────────────────────────────────────────────────────────────
# Busca de arquivos (sem duplicar no Windows)
# ─────────────────────────────────────────────────────────────────

def find_files_nocase(directory, extension):
    """
    Retorna arquivos com a extensão dada, sem duplicar no Windows
    (onde o sistema de arquivos é case-insensitive mas o glob não).
    """
    seen = set()
    result = []
    for f in glob.glob(os.path.join(directory, "*")):
        if f.lower().endswith(extension.lower()):
            canonical = os.path.normcase(os.path.abspath(f))
            if canonical not in seen:
                seen.add(canonical)
                result.append(f)
    return sorted(result)


def find_laz_file():
    """Encontra o LAZ/LAS na pasta do script (sem duplicar)."""
    files = find_files_nocase(SCRIPT_DIR, ".laz") + \
            find_files_nocase(SCRIPT_DIR, ".las")
    # Remove duplicatas que possam vir de ambas as listas
    seen = set()
    unique = []
    for f in files:
        k = os.path.normcase(os.path.abspath(f))
        if k not in seen:
            seen.add(k)
            unique.append(f)
    if not unique:
        sys.exit("ERRO: Nenhum arquivo .laz/.las encontrado na pasta do script.")
    if len(unique) > 1:
        print(f"  Múltiplos arquivos encontrados, usando: {os.path.basename(unique[0])}")
    return unique[0]


# ─────────────────────────────────────────────────────────────────
# Leitura de trajetórias
# ─────────────────────────────────────────────────────────────────

def parse_time_from_filename(filename):
    """Extrai t_start e t_end do nome: 393922.217_395164.993.pos"""
    base = os.path.basename(filename)
    match = re.search(r"([\d]+\.[\d]+)_([\d]+\.[\d]+)", base)
    if not match:
        sys.exit(f"ERRO: Não foi possível extrair intervalo de tempo de: {base}\n"
                 f"      Formato esperado: TSTART_TEND.pos")
    return float(match.group(1)), float(match.group(2))


def load_pos_file(path):
    """Lê .pos e retorna dict com interpoladores de posição."""
    t_start, t_end = parse_time_from_filename(path)
    times, gx, gy, gz = [], [], [], []

    with open(path, "r") as f:
        header_skipped = False
        for line in f:
            line = line.strip()
            if not line:
                continue
            if not header_skipped:
                try:
                    float(line.split(",")[0])
                except ValueError:
                    header_skipped = True
                    continue
            header_skipped = True

            parts = line.split(",")
            if len(parts) < 10:
                continue
            try:
                times.append(float(parts[0]))
                gx.append(float(parts[7]))
                gy.append(float(parts[8]))
                gz.append(float(parts[9]))
            except ValueError:
                continue

    if len(times) < 2:
        sys.exit(f"ERRO: Poucas linhas válidas em {os.path.basename(path)}")

    times = np.array(times)
    gx, gy, gz = np.array(gx), np.array(gy), np.array(gz)

    order = np.argsort(times)
    times, gx, gy, gz = times[order], gx[order], gy[order], gz[order]

    interp_x = interp1d(times, gx, kind="linear", bounds_error=False,
                        fill_value=(gx[0], gx[-1]))
    interp_y = interp1d(times, gy, kind="linear", bounds_error=False,
                        fill_value=(gy[0], gy[-1]))
    interp_z = interp1d(times, gz, kind="linear", bounds_error=False,
                        fill_value=(gz[0], gz[-1]))

    print(f"  ✓ {os.path.basename(path):45s} | "
          f"GPS [{times[0]:.3f} – {times[-1]:.3f}] | {len(times):,} posições")

    return {
        "name"     : os.path.splitext(os.path.basename(path))[0],
        "t_start"  : t_start,
        "t_end"    : t_end,
        "interp_x" : interp_x,
        "interp_y" : interp_y,
        "interp_z" : interp_z,
    }


def load_all_trajectories():
    pos_files = find_files_nocase(TRAJ_DIR, ".pos")
    if not pos_files:
        sys.exit(f"ERRO: Nenhum .pos encontrado em: {TRAJ_DIR}")
    print(f"\n[1/3] Carregando {len(pos_files)} trajetória(s)...\n")
    return [load_pos_file(p) for p in pos_files]


# ─────────────────────────────────────────────────────────────────
# Atribuição por distância 3D
# ─────────────────────────────────────────────────────────────────

def assign_chunk(chunk_pts, chunk_times, trajs):
    n = len(chunk_times)
    best_traj  = np.full(n, -1, dtype=np.int32)
    best_dist2 = np.full(n, np.inf, dtype=np.float64)

    for i, traj in enumerate(trajs):
        mask = ((chunk_times >= traj["t_start"] - TIME_MARGIN) &
                (chunk_times <= traj["t_end"]   + TIME_MARGIN))
        if not np.any(mask):
            continue

        t_sub   = chunk_times[mask]
        pts_sub = chunk_pts[mask]

        dx = traj["interp_x"](t_sub)
        dy = traj["interp_y"](t_sub)
        dz = traj["interp_z"](t_sub)

        diff  = pts_sub - np.column_stack([dx, dy, dz])
        dist2 = (diff * diff).sum(axis=1)

        improve        = mask.copy()
        improve[mask]  = dist2 < best_dist2[mask]
        best_dist2[improve] = dist2[improve[mask]]
        best_traj[improve]  = i

    return best_traj


# ─────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────

def main():
    trajs    = load_all_trajectories()
    laz_path = find_laz_file()
    laz_name = os.path.splitext(os.path.basename(laz_path))[0]

    print(f"\n[2/3] Processando: {os.path.basename(laz_path)}\n")

    with laspy.open(laz_path) as reader:
        src_header = reader.header
        total      = int(src_header.point_count)

        # ── Cria writers copiando o header COMPLETO do original ──
        # Isso preserva: VLRs (projeção WKT/GeoTIFF), offsets,
        # escalas, extra bytes, GUID, system identifier, etc.
        writers   = []
        out_paths = []
        file_handles = []

        for traj in trajs:
            out_path = os.path.join(
                SCRIPT_DIR, f"{laz_name}__{traj['name']}.laz"
            )
            out_paths.append(out_path)

            # Novo header baseado no original
            new_header = laspy.LasHeader(
                point_format=src_header.point_format,
                version=src_header.version,
            )
            # Copia offsets e escalas — essencial para coordenadas corretas
            new_header.offsets = src_header.offsets
            new_header.scales  = src_header.scales

            # Copia todos os VLRs (inclui projeção, WKT, extra bytes)
            new_header.vlrs = src_header.vlrs
            new_header.global_encoding.wkt = True   

            fh = open(out_path, "wb")
            file_handles.append(fh)            
            writers.append(laspy.LasWriter(fh, header=new_header, do_compress=True))

        # Orphan writer
        orphan_out_path = os.path.join(SCRIPT_DIR, f"{laz_name}__orphans.laz")
        orphan_header = laspy.LasHeader(
            point_format=src_header.point_format,
            version=src_header.version,
        )
        orphan_header.offsets = src_header.offsets
        orphan_header.scales = src_header.scales
        orphan_header.vlrs = src_header.vlrs
        orphan_header.global_encoding.wkt = True
        orphan_fh = open(orphan_out_path, "wb")
        orphan_writer = laspy.LasWriter(orphan_fh, header=orphan_header, do_compress=True)

        counts    = [0] * len(trajs)
        orphans   = 0
        processed = 0
        start_time = time.time()
        print(f"Iniciando processamento em: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}\n")

        for chunk in reader.chunk_iterator(CHUNK_SIZE):
            pts = np.column_stack([
                np.array(chunk.x, dtype=np.float64),
                np.array(chunk.y, dtype=np.float64),
                np.array(chunk.z, dtype=np.float64),
            ])
            times = np.array(chunk.gps_time, dtype=np.float64)

            assignment = assign_chunk(pts, times, trajs)

            for i, w in enumerate(writers):
                mask = assignment == i
                if np.any(mask):
                    w.write_points(chunk[mask])
                    counts[i] += int(mask.sum())

            orphans   += int((assignment == -1).sum())
            # Write orphans
            orphan_mask = assignment == -1
            if np.any(orphan_mask):
                orphan_writer.write_points(chunk[orphan_mask])

            processed += len(times)
            elapsed = time.time() - start_time
            progress_ratio = processed / total if total > 0 else 0
            if progress_ratio > 0:
                estimated_total = elapsed / progress_ratio
                remaining = max(0, estimated_total - elapsed)
                eta_seconds = time.time() + remaining
                remaining_mins = int(remaining // 60)
                remaining_secs = int(remaining % 60)
                eta_str = time.strftime("%H:%M:%S", time.localtime(eta_seconds))
                print(f"  {processed:>12,} / {total:,} pontos  "
                      f"({processed/total*100:.1f}%) | {remaining_mins}m {remaining_secs}s restantes | ETA: {eta_str}", end="\r")
            else:
                print(f"  {processed:>12,} / {total:,} pontos  "
                      f"({processed/total*100:.1f}%)", end="\r")

    # Fecha writers e file handles
    for w in writers:
        w.close()
    for fh in file_handles:
        fh.close()
    orphan_writer.close()
    orphan_fh.close()

    # ── Relatório ────────────────────────────────────────────────
    print(f"\n\n[3/3] Concluído!\n")
    print(f"{'Trajetória':<50} {'Pontos':>14}  Arquivo de saída")
    print("-" * 110)
    for i, traj in enumerate(trajs):
        flag = "  ⚠ VAZIO" if counts[i] == 0 else ""
        print(f"{traj['name']:<50} {counts[i]:>14,}  "
              f"{os.path.basename(out_paths[i])}{flag}")
    print(f"{'Orphans':<50} {orphans:>14,}  {os.path.basename(orphan_out_path)}")
    print(f"\n  Total atribuído : {sum(counts):,} pontos")
    print(f"  Total processado: {sum(counts) + orphans:,} pontos")
    print(f"  Arquivos salvos em: {SCRIPT_DIR}\n")
    start_time = time.time()
    print(f"Finalizado em: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}\n")


if __name__ == "__main__":
    main()