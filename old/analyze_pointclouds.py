#!/usr/bin/env python3
"""
Wrapper simples para o analisador que vive em `core/analyze_pointclouds.py`.
"""

import glob
import os

from core.analyze_pointclouds import PointCloudAnalyzer


def main():
    cwd = os.path.abspath(os.path.dirname(__file__))
    laz_files = sorted(glob.glob(os.path.join(cwd, "*.laz")))

    print(f"🔍 Encontrados {len(laz_files)} arquivos .laz")
    print()

    for filepath in laz_files:
        print("\n" + "=" * 80)
        print(f"{os.path.basename(filepath):^80}")
        print("=" * 80)

        analyzer = PointCloudAnalyzer(filepath)
        try:
            stats = analyzer.analyze()
        finally:
            analyzer.close()

        print(f"Total de atributos: {len(stats)}")
        print(f"{'Atributo':<25} {'Média':>15} {'Tipo':<12}")
        print(f"{'-'*25}{'_'*15}{'-'*12}")
        for name in sorted(stats):
            item = stats[name]
            if item["type"] == "numeric":
                print(f"{name:<25} {item['mean']:>15.3f} {item['type']:<12}")
            else:
                print(f"{name:<25} {'0.000':>15} {item['type']:<12} [existe]")

        print("_" * 80)
        print(f"✓ Análise completa: {len(stats)} atributos.")


if __name__ == '__main__':
    main()

