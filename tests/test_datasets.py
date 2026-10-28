import numpy as np
import pytest

scipy_io = pytest.importorskip("scipy.io")

from crowdshield.datasets import load_shanghaitech  # noqa: E402


def write_sample(split_dir, stem, points, gt_folder="ground-truth"):
    """Write an image placeholder and a .mat file shaped like ShanghaiTech's."""
    (split_dir / "images").mkdir(parents=True, exist_ok=True)
    (split_dir / gt_folder).mkdir(parents=True, exist_ok=True)
    (split_dir / "images" / f"{stem}.jpg").write_bytes(b"")

    record = np.zeros((1, 1), dtype=[("location", "O"), ("number", "O")])
    record[0, 0]["location"] = np.asarray(points, dtype=float).reshape(-1, 2)
    record[0, 0]["number"] = np.array([[len(points)]], dtype=float)
    info = np.empty((1, 1), dtype=object)
    info[0, 0] = record
    scipy_io.savemat(split_dir / gt_folder / f"GT_{stem}.mat", {"image_info": info})


@pytest.mark.parametrize("part_folder,gt_folder", [
    ("part_A", "ground-truth"),        # Kaggle mirror layout
    ("part_A_final", "ground_truth"),  # original release layout
])
def test_loads_head_points_in_natural_order(tmp_path, part_folder, gt_folder):
    test_dir = tmp_path / "ShanghaiTech" / part_folder / "test_data"
    write_sample(test_dir, "IMG_10", [[5, 6]], gt_folder)
    write_sample(test_dir, "IMG_2", [[1, 2], [3, 4], [7, 8]], gt_folder)

    samples = load_shanghaitech(tmp_path, "A", "test")

    assert [path.name for path, _ in samples] == ["IMG_2.jpg", "IMG_10.jpg"]
    assert [len(points) for _, points in samples] == [3, 1]
    assert samples[0][1][0].tolist() == [1.0, 2.0]


def test_missing_part_is_reported(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_shanghaitech(tmp_path, "B", "test")
