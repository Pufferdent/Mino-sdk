from __future__ import annotations

from typing import TYPE_CHECKING, Union

from tetris_sdk.solver.expressions import (
    ASTNode,
    parse_expression,
    evaluate_ast,
)

if TYPE_CHECKING:
    from tetris_sdk.solver.core import Solution


def compute_save_percentage(
    solves: list[list[str]] | list["Solution"],
    expression: str | ASTNode,
    *,
    over_solves: bool = False,
) -> float:
    if isinstance(expression, str):
        expression = parse_expression(expression)

    saves_list = _normalize_solves(solves)

    total = len(saves_list)
    if total == 0:
        return 0.0

    if over_solves:
        solvable = sum(1 for saves in saves_list if saves)
        if solvable == 0:
            return 0.0
        denominator = solvable
    else:
        denominator = total

    matching = sum(1 for saves in saves_list if evaluate_ast(expression, saves))
    return (matching / denominator) * 100.0


def filter_solves(
    solves: list[list[str]] | list["Solution"],
    expression: str | ASTNode,
) -> list[list[str]]:
    if isinstance(expression, str):
        expression = parse_expression(expression)

    saves_list = _normalize_solves(solves)
    return [saves for saves in saves_list if evaluate_ast(expression, saves)]


def _normalize_solves(
    solves: list[list[str]] | list["Solution"],
) -> list[list[str]]:
    result: list[list[str]] = []
    for item in solves:
        if hasattr(item, "piece_order"):
            result.append(_build_save_strings(item))
        elif isinstance(item, list):
            result.append(item)
        else:
            raise TypeError(f"Expected list of save strings or Solution, got {type(item)}")
    return result


def _build_save_strings(solution: "Solution") -> list[str]:
    saves: set[str] = set()
    for ptype, _rot, _col, _row in solution.operations:
        saves.add(ptype.name)
    return ["".join(sorted(saves))] if saves else []
