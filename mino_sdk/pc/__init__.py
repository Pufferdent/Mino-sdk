"""Perfect-clear (PC) mode tooling built on the Mino SDK.

* :mod:`leftover`      — PC rank + bag leftover arithmetic
* :mod:`queue_pattern` — build sfinder patterns from a player's queue
* :mod:`segment`       — split a replay fumen into per-PC state snapshots
* :mod:`sfinder`       — thin wrapper around ``sfinder.jar`` (no native solver)
* :mod:`saves`         — save-percentage math
"""

from mino_sdk.pc.leftover import pc_number, leaves, receives, nonqueued
from mino_sdk.pc.queue_pattern import queue_to_pattern
from mino_sdk.pc.segment import (
    PCState,
    PCGroup,
    ParsedReplay,
    segment_fumen,
    parse_queue_comment,
)
from mino_sdk.pc.sfinder import percent, path, PathResult
from mino_sdk.pc.saves import path_save_percent, combine_save

__all__ = [
    "pc_number",
    "leaves",
    "receives",
    "nonqueued",
    "queue_to_pattern",
    "PCState",
    "PCGroup",
    "ParsedReplay",
    "segment_fumen",
    "parse_queue_comment",
    "percent",
    "path",
    "PathResult",
    "path_save_percent",
    "combine_save",
]
