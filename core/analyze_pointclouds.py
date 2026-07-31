import glob
import os

from .las_manager import LasManager


class PointCloudAnalyzer:
    def __init__(self, path, chunk_size=1_000_000):
        self.manager = LasManager(path, chunk_size=chunk_size)

    def analyze(self):
        return self.manager.compute_statistics()

    def close(self):
        self.manager.close()


def main():
    cwd = os.path.abspath(os.path.dirname(__file__))
    laz_files = sorted(glob.glob(os.path.join(cwd, "*.laz")))

    print(f"🔍 Encontrados {len(laz_files)} arquivos .laz")

    for filepath in laz_files:
        print("\n" + "=" * 80)
        print(f"{os.path.basename(filepath):^80}")
        print("=" * 80)

        analyzer = PointCloudAnalyzer(filepath)
        try:
            stats = analyzer.analyze()
        finally:
            analyzer.close()

        total = sum(item.get("count", 0) for item in stats.values() if item["type"] == "numeric")
        print(f"Total de atributos avaliados: {len(stats)}")
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


if __name__ == "__main__":
    main()
