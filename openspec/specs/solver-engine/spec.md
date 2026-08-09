# Solver Engine

## Purpose

The Solver Engine provides a Python-native API for perfect-clear solving and save analysis by delegating to the community-standard reference tools: `sfinder.jar` for PC path-finding and `pc-saves-get` for expression evaluation and save filtering. The SDK handles subprocess lifecycle, fumen I/O conversion, and result parsing, presenting a clean Python interface without exposing Java CLI details or JVM overhead concerns to consumers.

A native Python perfect-clear solver was prototyped (see `archive/native_solver/`) and correctly implements hold-aware DFS with column-height-indexed placement lookup on a packed-integer bitboard. However, the search-space branching factor (~30 placements per piece × 2 candidates per node) remains too large for CPython to match sfinder's multi-threaded Java bitboard engine. The native solver is correct on trivially-solvable boards but OOM/times out on production 4-line PC setups. The subprocess delegation path is therefore the recommended integration.

## Requirements

### Requirement: PC solving via sfinder
The system SHALL provide a `solve_pc()` function that delegates to `sfinder.jar` via subprocess, passing fumen-encoded board state and queue patterns, and parsing results into structured `Solution` objects.

#### Scenario: Basic 4-line PC solve
- **WHEN** `solve_pc(board=initial_board, queue=['J','I','Z','L','O','S','I'], clear_lines=4)` is called
- **THEN** sfinder's `path` command is invoked with the fumen and pattern, and the returned fumen pages are parsed into a list of `Solution` objects

#### Scenario: No solutions exist
- **WHEN** `solve_pc` is called with a board that cannot be perfectly cleared
- **THEN** it returns an empty list

#### Scenario: sfinder not available
- **WHEN** `sfinder.jar` is not found at the configured path
- **THEN** a `RuntimeError` is raised with guidance on where to place the jar

### Requirement: Solution object structure
Each solution returned by `solve_pc` SHALL contain the piece placement order, cumulative board states decoded from fumen pages, and per-step operations.

#### Scenario: Solution contains piece order
- **WHEN** a solution is returned
- **THEN** `solution.piece_order` is a list of piece type strings in placement order matching draw+hold rules

#### Scenario: Solution contains board states
- **WHEN** a solution is returned
- **THEN** `solution.board_states` is a list of `Board` objects, one after each placement, with the last board being empty (perfect clear)

#### Scenario: Solution contains operations
- **WHEN** a solution is returned
- **THEN** `solution.operations` is a list of `(PieceType, rotation, x, y)` tuples for each placement step

### Requirement: Save analysis via pc-saves-get
The system SHALL provide functions that delegate to `pc-saves-get` for wanted-saves expression evaluation, save percentage computation, and solve filtering.

#### Scenario: Compute save percentage
- **WHEN** `compute_save_percentage(solves, "T")` is called
- **THEN** pc-saves-get evaluates the expression against each solve's saves and returns the matching percentage as a float

#### Scenario: Filter solves by expression
- **WHEN** `filter_solves(solves, "T&&S")` is called
- **THEN** only solves whose saves satisfy the expression are returned

### Requirement: Queue simulation utilities
The system SHALL provide hold-aware queue simulation functions for validating and enumerating placement orders.

#### Scenario: Validate reachable order with hold
- **WHEN** `is_placement_order_valid(draw_queue=['J','I','Z','L','O','S','I'], placement_order=['I','J','Z','O','L','S'], hold_rule='standard')` is called
- **THEN** `True` is returned (the order is reachable with one hold swap)

#### Scenario: Enumerate reachable orders
- **WHEN** `enumerate_placement_orders(draw_queue=['J','I','Z'], hold_rule='standard')` is called
- **THEN** all returned orders respect standard hold rules and consume a valid prefix of the queue
