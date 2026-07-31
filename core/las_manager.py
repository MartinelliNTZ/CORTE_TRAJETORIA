import os

import laspy
import numpy as np


class LasManager:
    def __init__(self, path, chunk_size=1_000_000):
        self.path = path
        self.chunk_size = chunk_size
        self.reader = laspy.open(path)
        self.header = self.reader.header
        self.total_points = int(self.header.point_count)
        self._writers = []
        self._handles = []
        self._trajectory_paths = []
        self._trajectory_counts = []
        self._orphan_writer = None
        self._orphan_handle = None
        self._orphans = 0

    def close(self):
        if self.reader is not None:
            self.reader.close()
            self.reader = None

    def chunk_iterator(self):
        return self.reader.chunk_iterator(self.chunk_size)

    def compute_statistics(self):
        if self.total_points == 0:
            return {}

        stats = {}
        first_chunk = True
        text_like_dims = {
            "synthetic_flag",
            "keypoint_flag",
            "withheld_flag",
            "overlap_flag",
            "scanner_channel",
            "classification_flags",
            "wave_packet_descriptor_index",
        }

        for chunk in self.chunk_iterator():
            if first_chunk:
                if hasattr(chunk.point_format, "dimension_names"):
                    all_names = list(chunk.point_format.dimension_names)
                else:
                    all_names = [dim.name for dim in chunk.point_format.dimensions]

                numeric_names = [name for name in all_names if name not in text_like_dims]
                for name in numeric_names:
                    stats[name] = {"sum": 0.0, "count": 0}
                for name in all_names:
                    if name in text_like_dims:
                        stats[name] = {"type": "text", "exists": True}
                first_chunk = False

            for name, data in list(stats.items()):
                if data.get("type") == "text":
                    continue
                try:
                    values = getattr(chunk, name)
                except AttributeError:
                    continue

                values_float = np.asarray(values, dtype=np.float64)
                valid = np.isfinite(values_float)
                stats[name]["sum"] += float(np.nansum(values_float[valid]))
                stats[name]["count"] += int(np.sum(valid))

        result = {}
        for name, data in stats.items():
            if data.get("type") == "text":
                result[name] = {"type": "text", "exists": True}
            else:
                count = data["count"]
                mean = data["sum"] / count if count else 0.0
                result[name] = {"type": "numeric", "mean": mean, "count": count}

        return result

    def _copy_header(self):
        new_header = laspy.LasHeader(
            point_format=self.header.point_format,
            version=self.header.version,
        )
        new_header.offsets = self.header.offsets
        new_header.scales = self.header.scales
        new_header.vlrs = self.header.vlrs
        new_header.global_encoding.wkt = True
        return new_header

    def prepare_trajectory_writers(self, trajectories, output_prefix, output_dir=None):
        output_dir = output_dir or os.path.dirname(self.path)
        self._trajectory_paths = []
        self._trajectory_counts = []
        self._writers = []
        self._handles = []

        for traj in trajectories:
            out_path = os.path.join(output_dir, f"{output_prefix}__{traj['name']}.laz")
            self._trajectory_paths.append(out_path)
            self._trajectory_counts.append(0)
            handle = open(out_path, "wb")
            self._handles.append(handle)
            writer = laspy.LasWriter(handle, header=self._copy_header(), do_compress=True)
            self._writers.append(writer)

        orphan_path = os.path.join(output_dir, f"{output_prefix}__orphans.laz")
        self._orphan_handle = open(orphan_path, "wb")
        self._orphan_writer = laspy.LasWriter(self._orphan_handle, header=self._copy_header(), do_compress=True)
        self._orphans = 0

        return self._trajectory_paths, orphan_path

    def write_assignments(self, chunk, assignments):
        for idx, writer in enumerate(self._writers):
            mask = assignments == idx
            if np.any(mask):
                writer.write_points(chunk[mask])
                self._trajectory_counts[idx] += int(np.sum(mask))

        orphan_mask = assignments == -1
        if np.any(orphan_mask):
            self._orphan_writer.write_points(chunk[orphan_mask])
            self._orphans += int(np.sum(orphan_mask))

    def finalize_writers(self):
        for writer in self._writers:
            writer.close()
        for handle in self._handles:
            handle.close()
        if self._orphan_writer is not None:
            self._orphan_writer.close()
        if self._orphan_handle is not None:
            self._orphan_handle.close()

    def get_trajectory_counts(self):
        return list(self._trajectory_counts)

    def get_orphan_count(self):
        return self._orphans
