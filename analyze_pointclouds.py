#!/usr/bin/env python3
"""
Wrapper simples para o analisador que vive em `core/analyze_pointclouds.py`.
"""

import glob
import os
from datetime import datetime

from core.analyze_pointclouds import PointCloudAnalyzer


def get_timestamp():
    """Retorna o horário atual no formato [HH:MM:SS]."""
    return datetime.now().strftime("[%H:%M:%S]")


def main():
    cwd = os.path.abspath(os.path.dirname(__file__))
    laz_files = sorted(glob.glob(os.path.join(cwd, "*.laz")))

    print(f"{get_timestamp()} 🔍 Encontrados {len(laz_files)} arquivo(s) .laz\n")

    if not laz_files:
        print(f"{get_timestamp()} ⚠️  Nenhum arquivo .laz encontrado no diretório: {cwd}\n")
        return

    for idx, filepath in enumerate(laz_files, 1):
        print(f"\n{get_timestamp()} {'='*80}")
        print(f"{get_timestamp()} Arquivo {idx}/{len(laz_files)}: {os.path.basename(filepath):^76}")
        print(f"{get_timestamp()} {'='*80}")

        try:
            print(f"{get_timestamp()} 📂 Caminho completo: {filepath}")
            file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
            print(f"{get_timestamp()} 📏 Tamanho do arquivo: {file_size_mb:.2f} MB")
            
            print(f"{get_timestamp()} 🔄 Abrindo e analisando...")
            analyzer = PointCloudAnalyzer(filepath)
            try:
                stats = analyzer.analyze()
            finally:
                analyzer.close()

            print(f"{get_timestamp()} ✅ Análise concluída com sucesso!")
            print(f"{get_timestamp()} 📊 Atributos encontrados: {len(stats)}")
            print(f"{get_timestamp()} {'Atributo':<25} {'Média':>12} {'Min':>12} {'Max':>12} {'Tipo':<12}")
            print(f"{get_timestamp()} {'-'*25}{'-'*12}{'-'*12}{'-'*12}{'-'*12}")
            
            numeric_count = 0
            text_count = 0
            for name in sorted(stats):
                item = stats[name]
                if item["type"] == "numeric":
                    min_str = f"{item['min']:,.3f}" if item.get('min') is not None else "-"
                    max_str = f"{item['max']:,.3f}" if item.get('max') is not None else "-"
                    print(f"{get_timestamp()} {name:<25} {item['mean']:>12.3f} {min_str:>12} {max_str:>12} {item['type']:<12}")
                    numeric_count += 1
                else:
                    print(f"{get_timestamp()} {name:<25} {'-':>12} {'-':>12} {'-':>12} {item['type']:<12} [existe]")
                    text_count += 1
            
            print(f"{get_timestamp()} {'-'*25}{'_'*15}{'-'*12}")
            print(f"{get_timestamp()} Resumo: {numeric_count} numéricos + {text_count} texto/flags = {len(stats)} total")
            print(f"{get_timestamp()} {'_'*80}")
        except Exception as e:
            print(f"{get_timestamp()} ❌ Erro ao processar {os.path.basename(filepath)}: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{get_timestamp()} ✅ Análise finalizada!\n")


if __name__ == '__main__':
    main()

