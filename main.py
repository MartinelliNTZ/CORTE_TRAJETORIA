#!/usr/bin/env python3
import glob
import os
import sys
import time
from datetime import datetime

import numpy as np

from core.las_manager import LasManager
from core.trajectory_manager import TrajectoryManager

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRAJ_DIR = os.path.join(SCRIPT_DIR, "TRAJETORIAS")
CHUNK_SIZE = 1_000_000
TIME_MARGIN = 3.0
LAZ_EXTENSIONS = [".laz", ".las"]


def get_timestamp():
    """Retorna o horário atual no formato [HH:MM:SS]."""
    return datetime.now().strftime("[%H:%M:%S]")


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
        print(f"{get_timestamp()} ERRO: Nenhum arquivo .laz/.las encontrado na pasta do script.")
        sys.exit(1)

    seen = set()
    unique = []
    for path in files:
        key = os.path.normcase(os.path.abspath(path))
        if key not in seen:
            seen.add(key)
            unique.append(path)

    if len(unique) > 1:
        print(f"{get_timestamp()} ⚠️  Múltiplos arquivos encontrados, usando: {os.path.basename(unique[0])}")

    return unique[0]


def print_statistics(stats, total_points):
    if not stats:
        print(f"{get_timestamp()} ⚠️  Nenhuma estatística disponível.")
        return

    print(f"\n{get_timestamp()} 📊 ESTATÍSTICAS DA NUVEM DE PONTOS:")
    print(f"{get_timestamp()} Total de pontos: {total_points:,}")
    print(f"{get_timestamp()} Total de atributos analisados: {len(stats)}")
    print(f"{get_timestamp()} {'Atributo':<25} {'Média':>12} {'Min':>12} {'Max':>12} {'Tipo':<12}")
    print(f"{get_timestamp()} {'-'*25}{'-'*12}{'-'*12}{'-'*12}{'-'*12}")
    for name in sorted(stats):
        item = stats[name]
        if item["type"] == "numeric":
            min_str = f"{item['min']:,.3f}" if item.get('min') is not None else "-"
            max_str = f"{item['max']:,.3f}" if item.get('max') is not None else "-"
            print(f"{get_timestamp()} {name:<25} {item['mean']:>12.3f} {min_str:>12} {max_str:>12} {item['type']:<12}")
        else:
            print(f"{get_timestamp()} {name:<25} {'-':>12} {'-':>12} {'-':>12} {item['type']:<12} [existe]")


def progress_report(processed, total_points, elapsed):
    progress_ratio = processed / total_points if total_points else 0
    estimated_total = elapsed / progress_ratio if progress_ratio > 0 else float('inf')
    remaining = max(0, estimated_total - elapsed)
    eta_seconds = time.time() + remaining
    remaining_mins = int(remaining // 60)
    remaining_secs = int(remaining % 60)
    eta_str = time.strftime("%H:%M:%S", time.localtime(eta_seconds))
    speed = processed / elapsed if elapsed > 0 else 0
    print(f"{get_timestamp()} ⏱️  {processed:>12,} / {total_points:,} pontos  "
          f"({progress_ratio*100:>5.1f}%) | "
          f"Velocidade: {speed:>10,.0f} pts/s | "
          f"{remaining_mins}m {remaining_secs}s restantes | ETA: {eta_str}")


def main():
    print(f"{get_timestamp()} ╔════════════════════════════════════════════════════════════════╗")
    print(f"{get_timestamp()} ║     CORTE DE TRAJETÓRIA - Sistema de Processamento de Pontos    ║")
    print(f"{get_timestamp()} ╚════════════════════════════════════════════════════════════════╝\n")
    
    # ─── ETAPA 1: CARREGAMENTO DE TRAJETÓRIAS ───
    print(f"{get_timestamp()} [ETAPA 1/4] Carregando trajetórias...")
    print(f"{get_timestamp()} 📂 Diretório de trajetórias: {TRAJ_DIR}")
    
    try:
        trajectory_manager = TrajectoryManager(TRAJ_DIR, time_margin=TIME_MARGIN)
        trajectories = trajectory_manager.load_all_trajectories()
        print(f"{get_timestamp()} ✅ Trajetórias carregadas: {len(trajectories)} arquivo(s)")
        for i, traj in enumerate(trajectories, 1):
            print(f"{get_timestamp()}    {i:2d}. {traj['name']:<45} | "
                  f"GPS [{traj['t_start']:.3f} - {traj['t_end']:.3f}]")
    except Exception as e:
        print(f"{get_timestamp()} ❌ ERRO ao carregar trajetórias: {e}")
        sys.exit(1)

    # ─── ETAPA 2: LOCALIZAÇÃO E ABERTURA DO LAZ ───
    print(f"\n{get_timestamp()} [ETAPA 2/4] Localizando arquivo LAZ/LAS...")
    try:
        laz_path = find_laz_file()
        laz_name = os.path.splitext(os.path.basename(laz_path))[0]
        laz_size_mb = os.path.getsize(laz_path) / (1024 * 1024)
        print(f"{get_timestamp()} ✅ Arquivo encontrado: {os.path.basename(laz_path)}")
        print(f"{get_timestamp()} 📏 Tamanho do arquivo: {laz_size_mb:.2f} MB")
    except Exception as e:
        print(f"{get_timestamp()} ❌ ERRO ao localizar arquivo: {e}")
        sys.exit(1)

    # ─── ETAPA 3: ANÁLISE DE PONTOS E ESTATÍSTICAS ───
    print(f"\n{get_timestamp()} [ETAPA 3/4] Abrindo nuvem de pontos e calculando estatísticas...")
    print(f"{get_timestamp()} ⚙️  Tamanho de chunk: {CHUNK_SIZE:,} pontos")
    print(f"{get_timestamp()} ⚙️  Margem temporal (TIME_MARGIN): {TIME_MARGIN}s")
    
    las_manager = LasManager(laz_path, chunk_size=CHUNK_SIZE)
    print(f"{get_timestamp()} ✅ Arquivo aberto com sucesso")
    print(f"{get_timestamp()} 📍 Total de pontos na nuvem: {las_manager.total_points:,}")

    try:
        print(f"{get_timestamp()} 🔄 Calculando estatísticas dos atributos e processando cortes em uma única passagem...")
        print(f"{get_timestamp()} 🚀 Iniciando processamento combinado (estatísticas + cortes)")
        print(f"{get_timestamp()} {'─' * 82}")

        stats, trajectory_paths, orphan_path, elapsed_total = las_manager.process_with_statistics(
            trajectory_manager,
            output_prefix=laz_name,
            output_dir=SCRIPT_DIR,
            progress_callback=progress_report,
        )

        print(f"{get_timestamp()} {'─' * 82}")
        las_manager.finalize_writers()
        print(f"\n{get_timestamp()} ✅ PROCESSAMENTO CONCLUÍDO COM SUCESSO!")
        print(f"{get_timestamp()} ⏱️  Tempo total: {int(elapsed_total // 60)}m {int(elapsed_total % 60)}s")
        
        # ─── RELATÓRIO FINAL ───
        print(f"\n{get_timestamp()} 📋 RELATÓRIO FINAL:")
        print(f"{get_timestamp()} {'Trajetória':<50} {'Pontos':>14}  Arquivo de saída")
        print(f"{get_timestamp()} {'-' * 110}")
        for idx, traj in enumerate(trajectories):
            count = las_manager.get_trajectory_counts()[idx]
            flag = "  ⚠️  VAZIO" if count == 0 else ""
            print(f"{get_timestamp()} {traj['name']:<50} {count:>14,}  "
                  f"{os.path.basename(trajectory_paths[idx])}{flag}")
        orphan_count = las_manager.get_orphan_count()
        print(f"{get_timestamp()} {'Orphans (não atribuídos)':<50} {orphan_count:>14,}  "
              f"{os.path.basename(orphan_path)}")
        
        total_assigned = sum(las_manager.get_trajectory_counts())
        total_processed = total_assigned + orphan_count
        print(f"{get_timestamp()} {'-' * 110}")
        print(f"{get_timestamp()} Total atribuído: {total_assigned:,} pontos")
        print(f"{get_timestamp()} Total processado: {total_processed:,} pontos")
        print(f"{get_timestamp()} Taxa de atribuição: {(total_assigned / total_processed * 100) if total_processed > 0 else 0:.2f}%")
        print(f"\n{get_timestamp()} 💾 Arquivos salvos em: {SCRIPT_DIR}\n")
        
    except Exception as e:
        print(f"{get_timestamp()} ❌ ERRO durante o processamento: {e}")
        import traceback
        traceback.print_exc()
    finally:
        las_manager.close()
        print(f"{get_timestamp()} ✅ Recursos liberados.\n")


if __name__ == "__main__":
    main()

