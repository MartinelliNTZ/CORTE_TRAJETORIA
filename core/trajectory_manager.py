import glob
import os
import re
import sys

import numpy as np
from scipy.interpolate import interp1d


class TrajectoryManager:
    def __init__(self, traj_dir, time_margin=3.0, extension=".pos"):
        self.traj_dir = traj_dir
        self.time_margin = time_margin
        self.extension = extension
        self.trajectories = []

    def _find_files_nocase(self):
        if not os.path.isdir(self.traj_dir):
            raise FileNotFoundError(f"Diretório não encontrado: {self.traj_dir}")

        seen = set()
        result = []
        for path in glob.glob(os.path.join(self.traj_dir, "*")):
            if path.lower().endswith(self.extension.lower()):
                canonical = os.path.normcase(os.path.abspath(path))
                if canonical not in seen:
                    seen.add(canonical)
                    result.append(path)
        return sorted(result)

    def _parse_time_from_filename(self, path):
        name = os.path.basename(path)
        match = re.search(r"([\d]+\.[\d]+)_([\d]+\.[\d]+)", name)
        if not match:
            raise ValueError(
                f"ERRO: Não foi possível extrair intervalo de tempo de: {name}\n"
                f"      Formato esperado: TSTART_TEND.pos"
            )
        return float(match.group(1)), float(match.group(2))

    def _load_pos_file(self, path):
        # NOTE: prefer to obtain t_start/t_end from the actual .pos content
        # instead of relying on the filename. This avoids mismatches when
        # filenames are imprecise or use different time bases.
        times, gx, gy, gz = [], [], [], []

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
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
            raise ValueError(f"ERRO: Poucas linhas válidas em {os.path.basename(path)}")

        times = np.array(times)
        gx = np.array(gx)
        gy = np.array(gy)
        gz = np.array(gz)

        order = np.argsort(times)
        times = times[order]
        gx = gx[order]
        gy = gy[order]
        gz = gz[order]

        # derive interval from actual data
        t_start = float(times[0])
        t_end = float(times[-1])
        print(f"  ✅ Carregado {os.path.basename(path)} | GPS [{t_start:.3f} - {t_end:.3f}]")

        interp_x = interp1d(times, gx, kind="linear", bounds_error=False, fill_value=(gx[0], gx[-1]))
        interp_y = interp1d(times, gy, kind="linear", bounds_error=False, fill_value=(gy[0], gy[-1]))
        interp_z = interp1d(times, gz, kind="linear", bounds_error=False, fill_value=(gz[0], gz[-1]))

        return {
            "name": os.path.splitext(os.path.basename(path))[0],
            "t_start": t_start,
            "t_end": t_end,
            "interp_x": interp_x,
            "interp_y": interp_y,
            "interp_z": interp_z,
        }

    def load_all_trajectories(self):
        pos_files = self._find_files_nocase()
        if not pos_files:
            raise FileNotFoundError(f"ERRO: Nenhum .pos encontrado em: {self.traj_dir}")

        self.trajectories = []
        for i, path in enumerate(pos_files, 1):
            try:
                traj = self._load_pos_file(path)
                self.trajectories.append(traj)
            except Exception as e:
                print(f"  ⚠️  Erro ao carregar {os.path.basename(path)}: {e}")
        
        return self.trajectories

    def assign_points(self, points, times):
        n = len(times)
        best_traj = np.full(n, -1, dtype=np.int32)
        best_dist2 = np.full(n, np.inf, dtype=np.float64)

        for i, traj in enumerate(self.trajectories):
            mask = ((times >= traj["t_start"] - self.time_margin) &
                    (times <= traj["t_end"] + self.time_margin))
            if not np.any(mask):
                continue

            t_sub = times[mask]
            pts_sub = points[mask]
            dx = traj["interp_x"](t_sub)
            dy = traj["interp_y"](t_sub)
            dz = traj["interp_z"](t_sub)

            diff = pts_sub - np.column_stack([dx, dy, dz])
            dist2 = np.sum(diff * diff, axis=1)

            selected = np.nonzero(mask)[0]
            improved = dist2 < best_dist2[selected]
            indices = selected[improved]
            best_dist2[indices] = dist2[improved]
            best_traj[indices] = i

        return best_traj
