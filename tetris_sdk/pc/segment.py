"""Segment a multi-page fumen into per-PC groups with per-placement snapshots.

A Jstris PC replay, once rendered to a multi-page fumen (one page per placement,
each page's field being the cumulative board *after* that many pieces), is split
here into :class:`PCGroup` objects. Each group is one perfect clear: a sequence
of :class:`PCState` board snapshots from the empty start through nine placements,
plus the per-PC rank, cumulative piece count, and the sfinder queue patterns for
the 3p/4p/5p setup states.

Per-state line bookkeeping (``all_lines``/``line_map``/``cleared_rows``) tracks a
stable id for each of the four window rows across clears, so the viewer can
reconstruct the exact pre-clear board and which lines vanished — mirroring
PCReview v2's ``parse_replay.js``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from tetris_sdk.fumen.decoder import FUMEN_COLS, FUMEN_TO_CELL, decode_fumen
from tetris_sdk.pc.fumen_ops import apply_operation_detailed
from tetris_sdk.pc.fumen_ops import _OP_TYPE_TO_LETTER
from tetris_sdk.pc.leftover import pc_number
from tetris_sdk.pc.queue_pattern import queue_to_pattern
from tetris_sdk.pc.quiz import Quiz

# Fumen field is 24 rows tall (row 0 = top). The visible playfield's bottom data
# row is index 22; the PC window is the bottom four rows 19..22 (top -> bottom).
_FUMEN_BOTTOM = 22
_WINDOW_TOP = _FUMEN_BOTTOM - 3  # = 19
_COLS = FUMEN_COLS

# raw fumen field value -> board-string char (via FUMEN_TO_CELL -> Cell int)
_CELLINT_TO_CHAR = {0: "N", 1: "T", 2: "I", 3: "L", 4: "J", 5: "S", 6: "Z",
                    7: "O", 8: "X", 9: "X"}
_VALUE_TO_CHAR = [_CELLINT_TO_CHAR[FUMEN_TO_CELL[v]] for v in range(9)]

_QUEUE_HOLD_RE = re.compile(r"^#Q=\[(\w*)\]\((\w)\)(.+)")
_QUEUE_RE = re.compile(r"^#Q=\((\w)\)(.+)")

_EMPTY_ROW = "N" * _COLS


@dataclass
class PCState:
    """One placement snapshot within a PC."""

    board: str          # 40-char window, row 0 = top
    queue: str          # parsed lookahead: hold + current + next
    placed_blocks: int  # global piece ordinal (= cumulative pieces at this state)
    cleared_rows: list | None = None  # [{rowIndex,id,cells}] or None
    all_lines: dict = field(default_factory=dict)  # id -> {cells, cleared}
    line_map: list = field(default_factory=list)   # window rows top->bottom -> id
    bag_pieces: str = ""
    bag_placed: int = 0

    def to_dict(self) -> dict:
        return {
            "board": self.board,
            "queue": self.queue,
            "placedBlocks": self.placed_blocks,
            "clearedRows": self.cleared_rows,
            "allLines": {str(k): v for k, v in self.all_lines.items()},
            "lineMap": self.line_map,
            "bagPieces": self.bag_pieces,
            "bagPlaced": self.bag_placed,
        }


@dataclass
class PCGroup:
    """One perfect clear: the ordered states plus derived PC metadata."""

    pc_number: int
    rank: int | None
    states: list[PCState] = field(default_factory=list)
    cumulative_pieces: int = 0
    queue3p: str | None = None
    queue4p: str | None = None
    queue5p: str | None = None
    completed: list = field(default_factory=list)  # [{cells,cleared,src}]
    placed_types: list[str | None] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "PCNumber": self.pc_number,
            "PCLoopIndicator": self.rank,
            "stateArray": [s.to_dict() for s in self.states],
            "cumulativePieces": self.cumulative_pieces,
            "queue3p": self.queue3p,
            "queue4p": self.queue4p,
            "queue5p": self.queue5p,
            "completed": self.completed,
            "placedTypes": self.placed_types,
        }


@dataclass
class ParsedReplay:
    """The full segmented result."""

    full_sequence: str
    pc_groups: list[PCGroup]

    def to_dict(self) -> dict:
        return {
            "fullSequence": self.full_sequence,
            "pcGroups": [g.to_dict() for g in self.pc_groups],
        }


def _values_to_window(values: list[int]) -> str:
    return "".join(_VALUE_TO_CHAR[v] if 0 <= v < 9 else "X" for v in values)


def _field_window(field_arr: list[int]) -> str:
    vals = []
    for wr in range(4):
        base = (_WINDOW_TOP + wr) * _COLS
        vals.extend(field_arr[base:base + _COLS])
    return _values_to_window(vals)


def _rows(window: str) -> list[str]:
    return [window[r * _COLS:(r + 1) * _COLS] for r in range(4)]


def parse_queue_comment(comment: str) -> str:
    """Extract the lookahead queue (hold + current + next) from a ``#Q=`` comment."""
    m = _QUEUE_HOLD_RE.match(comment)
    if m:
        hold, current, nxt = m.group(1), m.group(2), m.group(3)
        if hold:
            return hold + current + nxt[:5]
        return current + nxt[:6]
    m2 = _QUEUE_RE.match(comment)
    if m2:
        return m2.group(1) + m2.group(2)[:6]
    return ""


class _LineTracker:
    """Per-PC window-row id bookkeeping, mirroring parse_replay.js."""

    def __init__(self) -> None:
        self.win_ids = [0, 1, 2, 3]
        self.next_id = 4
        self.all_lines: dict[int, dict] = {}
        self.line_src: dict[int, list] = {}

    def start(self, board: str) -> tuple[dict, list]:
        rows = _rows(board)
        self.win_ids = [0, 1, 2, 3]
        self.next_id = 4
        self.all_lines = {}
        self.line_src = {}
        for r in range(4):
            self.all_lines[self.win_ids[r]] = {"cells": rows[r], "cleared": False}
            self.line_src[self.win_ids[r]] = [None] * _COLS
        return self._snapshot(), list(self.win_ids)

    def _snapshot(self) -> dict:
        return {k: {"cells": v["cells"], "cleared": v["cleared"]}
                for k, v in self.all_lines.items()}

    def transition(self, prev_board: str, cur_board: str, pre_rows: list[str],
                   cleared_idx: list[int], ord_: int):
        """Advance one placement; returns (allLines snapshot, lineMap, clearedRows,
        placed_type)."""
        cur_rows = _rows(cur_board)

        # provenance: tag cells this piece just added, by their pre-clear line id
        placed_type = None
        for r in range(4):
            for c in range(_COLS):
                ch = pre_rows[r][c]
                if ch != "N" and prev_board[r * _COLS + c] == "N":
                    pid = self.win_ids[r]
                    self.line_src.setdefault(pid, [None] * _COLS)
                    self.line_src[pid][c] = ord_
                    placed_type = ch

        if not cleared_idx:
            for r in range(4):
                self.all_lines[self.win_ids[r]] = {"cells": cur_rows[r], "cleared": False}
            return self._snapshot(), list(self.win_ids), None, placed_type

        cleared_set = set(cleared_idx)
        cleared_list = []
        survivor_ids = []
        for r in range(4):
            wid = self.win_ids[r]
            if r in cleared_set:
                self.all_lines[wid] = {"cells": pre_rows[r], "cleared": True}
                cleared_list.append({"rowIndex": r, "id": wid, "cells": pre_rows[r]})
            else:
                survivor_ids.append(wid)

        new_ids = []
        for _ in range(len(cleared_idx)):
            nid = self.next_id
            self.next_id += 1
            new_ids.append(nid)
            self.line_src[nid] = [None] * _COLS
        new_ids.extend(survivor_ids)

        self.win_ids = new_ids
        for r in range(4):
            self.all_lines[self.win_ids[r]] = {"cells": cur_rows[r], "cleared": False}
        return self._snapshot(), list(self.win_ids), (cleared_list or None), placed_type

    def completed(self) -> list:
        out = []
        for wid in range(4):
            line = self.all_lines.get(wid, {"cells": _EMPTY_ROW, "cleared": False})
            src = list(self.line_src.get(wid, [None] * _COLS))
            out.append({"cells": line["cells"], "cleared": bool(line["cleared"]), "src": src})
        return out


def _deal_from_seed(seed, count: int) -> str:
    """Reconstruct the piece deal order from a Jstris RNG seed."""
    from tetris_sdk.sim.queue import Queue
    from tetris_sdk.sim.rng import JstrisRng
    q = Queue(JstrisRng(seed))
    return "".join(q.next().name for _ in range(count))


def segment_fumen(fumen_str: str, *, seed=None) -> ParsedReplay:
    """Segment a multi-page replay fumen into PC groups (v2-compatible output).

    ``seed`` (the Jstris replay seed) is used to reconstruct the full piece deal
    for the queue/pattern data. Prefer it: the fumen's ``#Q=`` lookahead comment
    is capped at ~4095 chars, so on long replays it truncates and the hold quiz
    would otherwise run out mid-parse. Without a seed, the comment is used and the
    quiz degrades gracefully (empty queues) once it's exhausted.
    """
    raw = decode_fumen(fumen_str)

    # Replay the operation stream to recover, per page, the cumulative board
    # *before* that page's piece, plus each placement's pre-clear window and the
    # window-rows it cleared.
    field = [0] * (24 * _COLS)
    windows: list[str] = []
    queues: list[str] = []
    pre_windows: list[str] = []       # pre-clear window of placement i
    cleared_idx: list[list[int]] = []  # window rows cleared by placement i

    # Prefer the fumen's #Q= comment (authoritative, exact). Only fall back to the
    # seed-reconstructed deal when the comment is truncated (its lookahead is
    # shorter than the number of placements) — which is what crashes long uploads.
    quiz = Quiz.from_comment(raw[0]["comment"]) if raw else Quiz("", "", "")
    if seed is not None and raw:
        comment_deal = (1 if quiz.current else 0) + len(quiz.rest)
        placements = sum(1 for pg in raw
                         if pg["piece"]["type"] in _OP_TYPE_TO_LETTER)
        if comment_deal < placements:
            deal = _deal_from_seed(seed, len(raw) + 14)
            quiz = Quiz("", deal[:1], deal[1:])
    for page in raw:
        windows.append(_field_window(field))
        queues.append(quiz.queue_str())
        op = page["piece"]
        letter = _OP_TYPE_TO_LETTER.get(op["type"])
        _, pre_vals, rows_cleared = apply_operation_detailed(
            field, op["type"], op["rotation"], op["position"])
        pre_windows.append(_values_to_window(pre_vals))
        cleared_idx.append(rows_cleared)
        if letter is not None:
            try:
                quiz = quiz.operate(letter)
            except ValueError:
                # Comment lookahead exhausted (or desync): stop tracking the
                # queue rather than aborting the whole parse.
                quiz = Quiz("", "", "")

    groups: list[PCGroup] = []
    current: PCGroup | None = None
    tracker = _LineTracker()

    for i in range(len(raw)):
        is_empty = set(windows[i]) <= {"N"}
        if is_empty and current is not None and current.states:
            current.completed = tracker.completed()
            groups.append(current)
            current = None
        if current is None:
            current = PCGroup(pc_number=len(groups) + 1, rank=None)
            all_lines, line_map = tracker.start(windows[i])
            current.states.append(PCState(
                board=windows[i], queue=queues[i], placed_blocks=i,
                cleared_rows=None, all_lines=all_lines, line_map=line_map))
            continue

        prev = current.states[-1]
        # clears entering this state came from the previous placement (i-1)
        idx = cleared_idx[i - 1]
        pre_rows = _rows(pre_windows[i - 1]) if idx else _rows(windows[i])
        ord_ = len(current.states) - 1
        all_lines, line_map, cleared_list, placed_type = tracker.transition(
            prev.board, windows[i], pre_rows, idx, ord_)
        current.placed_types.append(placed_type)
        current.states.append(PCState(
            board=windows[i], queue=queues[i], placed_blocks=i,
            cleared_rows=cleared_list, all_lines=all_lines, line_map=line_map))

    if current is not None and current.states:
        current.completed = tracker.completed()
        groups.append(current)

    _attach_metadata(groups)
    full_sequence = _build_full_sequence(groups)
    _attach_bag_info(groups, full_sequence)
    _attach_patterns(groups, full_sequence)
    return ParsedReplay(full_sequence=full_sequence, pc_groups=groups)


def _attach_metadata(groups: list[PCGroup]) -> None:
    cum = 0
    for g in groups:
        g.cumulative_pieces = cum
        g.rank = pc_number(cum)
        cum += len(g.states)


def _build_full_sequence(groups: list[PCGroup]) -> str:
    states = [s for g in groups for s in g.states]
    seq: list[str] = []
    for idx, s in enumerate(states):
        q = s.queue
        if idx == 0:
            seq.extend(list(q))
        elif q:
            seq.append(q[-1])
    return "".join(seq)


def _attach_bag_info(groups: list[PCGroup], full_sequence: str) -> None:
    for s in (s for g in groups for s in g.states):
        current_idx = s.placed_blocks + 1
        bag_start = (current_idx // 7) * 7
        s.bag_pieces = full_sequence[bag_start:bag_start + 7]
        s.bag_placed = max(0, s.placed_blocks - bag_start)


def _attach_patterns(groups: list[PCGroup], full_sequence: str) -> None:
    for g in groups:
        for n, attr in ((3, "queue3p"), (4, "queue4p"), (5, "queue5p")):
            if len(g.states) > n:
                st = g.states[n]
                setattr(g, attr, queue_to_pattern(
                    full_sequence, st.placed_blocks, st.queue))
