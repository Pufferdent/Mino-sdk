"""Tests for the tetris_sdk.pc perfect-clear tooling."""

import os

import pytest

from tetris_sdk.pc import (
    pc_number,
    leaves,
    receives,
    nonqueued,
    queue_to_pattern,
    segment_fumen,
    combine_save,
)
from tetris_sdk.pc.quiz import Quiz
from tetris_sdk.pc.fumen_ops import operation_cells

FIXTURE = os.path.join(os.path.dirname(__file__), "pc_replay_fixture.fumen")


# --- leftover math ---------------------------------------------------------

def test_pc_number_cycle():
    assert pc_number(0) == 1
    assert pc_number(10) == 2
    assert pc_number(20) == 3
    assert pc_number(30) == 4
    assert pc_number(5) == 5
    assert pc_number(15) == 6
    assert pc_number(25) == 7
    assert pc_number(35) == 1  # wraps every 35
    assert pc_number(3) is None  # off the PC grid


def test_leaves_and_receives():
    # leaves(rank) = (rank*4) % 7 or 7
    assert [leaves(r) for r in range(1, 8)] == [4, 1, 5, 2, 6, 3, 7]
    # receives(rank) = ((rank*4)+2) % 7 + 1
    assert [receives(r) for r in range(1, 8)] == [7, 4, 1, 5, 2, 6, 3]


def test_nonqueued():
    # PC#4 needs 6 pieces: leaves=2, unused_from_queue=1, nonqueued=1? per AGENTS
    assert nonqueued(4, 6) == leaves(4) - (7 - 6)


# --- queue -> pattern ------------------------------------------------------

def test_queue_to_pattern_all_unique():
    seq = "TILJSZO" * 3
    # no hold, placed 0: full fresh bag -> *p7
    assert queue_to_pattern(seq, 0, "TILJSZ") == "*p7"


def test_queue_to_pattern_partial_bag_with_hold():
    # held piece from previous bag leads as [X]p1
    pat = queue_to_pattern("TILJSZOTILJSZO", placed_blocks=5, queue_str="OTILJSZ")
    assert pat is not None and pat.endswith("p7") is False  # sums to 7
    assert sum(int(p.split("p")[1]) for p in pat.split(",")) == 7


# --- quiz hold state -------------------------------------------------------

def test_quiz_direct_and_hold():
    q = Quiz.from_comment("#Q=[](T)ZOIJSL")
    assert q.hold == "" and q.current == "T" and q.rest == "ZOIJSL"
    # hold T (place Z = next): Stock
    q2 = q.operate("Z")
    assert q2.hold == "T" and q2.current == "O"


# --- fumen operation geometry ---------------------------------------------

def test_operation_cells_z_spawn():
    # raw type 4 = Z, rotation 2 = spawn, position 217 -> x=7,y=0
    cells = set(operation_cells(4, 2, 217))
    assert cells == {(22, 7), (22, 8), (21, 6), (21, 7)}


# --- end-to-end segmentation ----------------------------------------------

@pytest.mark.skipif(not os.path.exists(FIXTURE), reason="fixture missing")
def test_segment_fumen_fixture():
    parsed = segment_fumen(open(FIXTURE).read())
    assert len(parsed.pc_groups) == 101
    assert len(parsed.full_sequence) == 1015
    assert parsed.full_sequence.startswith("TZOIJSLSZL")

    g0 = parsed.pc_groups[0]
    assert g0.rank == 1
    assert g0.cumulative_pieces == 0
    assert g0.states[3].board == "INNNNNNNNNINNNNNNNNNIOONNNZZNNIOONNNNZZN"
    assert g0.queue3p == "[JSLT]p4,*p3"
    assert g0.queue4p == "[SLJ]p3,*p4"


def test_combine_save_bounds():
    # path_save 100% and solve 100% -> save 100%
    assert combine_save(100.0, 100.0, 4, 6) == pytest.approx(100.0)
    # path_save 0 with nonzero non-queued leftover still contributes
    nq = nonqueued(4, 6)
    s = combine_save(100.0, 0.0, 4, 6)
    assert s == pytest.approx(100.0 * (nq / 7))
