#!/usr/bin/env python3
import glob
import os
import sys
import time

import numpy as np

from core.las_manager import LasManager
from core.trajectory_manager import TrajectoryManager

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRAJ_DIR = os.path.join(SCRIPT_DIR, "trajetorias")
CHUNK_SIZE = 1_000_000
TIME_MARGIN = 3.0
LAZ_EXTENSIONS = [".laz", ".las"]


def find_files_nocase(directory, extension):
    seen = set()
    result = []
    for path in glob.glob(os.path.join(directory, "*")):
        if path.lower().endswith(extension.lower()):
            canonical = os.path.normcase(os.path.abspath(path))
            if canonical not in seen:
                seen.add(canonical)
                result.append(path)
    return sorted(result)


def find_laz_file():
    files = []
    for extension in LAZ_EXTENSIONS:
        files.extend(find_files_nocase(SCRIPT_DIR, extension))

    if not files:
        sys.exit("ERRO: Nenhum arquivo .laz/.las encontrado na pasta do script.")

    seen = set()
    unique = []
    for path in files:
        key = os.path.normcase(os.path.abspath(path))
        if key not in seen:
            seen.add(key)
            unique.append(path)

    if len(unique) > 1:
        print(f"  Múltiplos arquivos encontrados, usando: {os.path.basename(unique[0])}")

    return unique[0]


def print_statistics(stats):
    if not stats:
        print("Nenhuma estatística disponível.")
        return

    print(f"{'Atributo':<25} {'Média':>15} {'Tipo':<12}")
    print(f"{'-'*25}{'_'*15}{'-'*12}")
    for name in sorted(stats):
        item = stats[name]
        if item["type"] == "numeric":
            print(f"{name:<25} {item['mean']:>15.3f} {item['type']:<12}")
        else:
            print(f"{name:<25} {'0.000':>15} {item['type']:<12} [existe]")


def main():
    print("[1/3] Carregando trajetórias...")
    trajectory_manager = TrajectoryManager(TRAJ_DIR, time_margin=TIME_MARGIN)
    trajectories = trajectory_manager.load_all_trajectories()

    laz_path = find_laz_file()
    laz_name = os.path.splitext(os.path.basename(laz_path))[0]

    print(f"\n[2/3] Processando nuvem de pontos: {os.path.basename(laz_path)}\n")
    las_manager = LasManager(laz_path, chunk_size=CHUNK_SIZE)

    try:
        stats = las_manager.compute_statistics()
        print_statistics(stats)

        print(f"\n[3/3] Iniciando divisão por trajetórias...\n")
        trajectory_paths, orphan_path = las_manager.prepare_trajectory_writers(
            trajectories, output_prefix=laz_name, output_dir=SCRIPT_DIR
        )

        processed = 0
        start_time = time.time()
        for chunk in las_manager.chunk_iterator():
            pts = np.column_stack([
                np.array(chunk.x, dtype=np.float64),
                np.array(chunk.y, dtype=np.float64),
                np.array(chunk.z, dtype=np.float64),
            ])
            times = np.array(chunk.gps_time, dtype=np.float64)
            assignment = trajectory_manager.assign_points(pts, times)
            las_manager.write_assignments(chunk, assignment)

            processed += len(times)
            elapsed = time.time() - start_time
            progress_ratio = processed / las_manager.total_points if las_manager.total_points else 0
            if progress_ratio > 0:
                estimated_total = elapsed / progress_ratio
                remaining = max(0, estimated_total - elapsed)
                eta_seconds = time.time() + remaining
                remaining_mins = int(remaining // 60)
                remaining_secs = int(remaining % 60)
                eta_str = time.strftime("%H:%M:%S", time.localtime(eta_seconds))
                print(f"  {processed:>12,} / {las_manager.total_points:,} pontos  "
                      f"({processed / las_manager.total_points * 100:.1f}%) | {remaining_mins}m {remaining_secs}s restantes | ETA: {eta_str}", end="\r")
            else:
                print(f"  {processed:>12,} / {las_manager.total_points:,} pontos  "
                      f"({processed / las_manager.total_points * 100:.1f}%)", end="\r")

        las_manager.finalize_writers()
        print("\n\nConcluído!\n")
        for idx, traj in enumerate(trajectories):
            count = las_manager.get_trajectory_counts()[idx]
            print(f"{traj['name']:<50} {count:>14,}  {os.path.basename(trajectory_paths[idx])}")
        print(f"{'Orphans':<50} {las_manager.get_orphan_count():>14,}  {os.path.basename(orphan_path)}")
        print(f"\nArquivo salvo em: {SCRIPT_DIR}\n")
    finally:
        las_manager.close()


if __name__ == "__main__":
    main()
