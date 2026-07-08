import numpy as np

from canitplaydoom.ascii_encoder import LabelInfo, encode


def test_encode_shape():
    labels_buffer = np.zeros((240, 320), dtype=np.int32)
    grid = encode(labels_buffer, labels=[], rows=32, cols=64)
    lines = grid.split("\n")
    assert len(lines) == 32
    assert all(len(line) == 64 for line in lines)


def test_encode_marks_enemy():
    labels_buffer = np.zeros((240, 320), dtype=np.int32)
    # Fill a block with label value 5 = Zombieman.
    labels_buffer[0:8, 0:5] = 5
    grid = encode(
        labels_buffer,
        labels=[LabelInfo(value=5, object_name="Zombieman")],
        rows=32,
        cols=64,
    )
    assert grid.split("\n")[0][0] == "Z"


def test_encode_player_marker_present():
    labels_buffer = np.zeros((240, 320), dtype=np.int32)
    grid = encode(labels_buffer, labels=[], rows=32, cols=64)
    assert grid.split("\n")[-1][32] == "^"


def test_encode_wall_from_depth():
    labels_buffer = np.zeros((16, 16), dtype=np.int32)
    depth = np.full((16, 16), 10, dtype=np.uint8)  # very close -> wall
    grid = encode(labels_buffer, labels=[], depth_buffer=depth, rows=4, cols=4,
                  wall_depth_threshold=32)
    # At least some cells should be walls (excluding the player marker cell).
    assert "#" in grid
