## ADDED Requirements

### Requirement: Native perfect-clear solver
The system SHALL provide a `solve_pc()` function that finds all valid perfect-clear solutions for a given board state and draw queue, without shelling out to external processes.

#### Scenario: Basic 4-line PC solve
- **WHEN** `solve_pc(board=initial_board, queue=['J','I','Z','L','O','S','I'], clear_lines=4)` is called
- **THEN** it returns a list of solution objects, each with a placement order, board states after each placement, and per-step operations

#### Scenario: Solver respects draw queue order
- **WHEN** `solve_pc` is called with `hold='standard'` and queue `['I','O','T','S','Z','J','L']`
- **THEN** every solution's placement order is reachable from the given queue with standard hold rules

#### Scenario: No solutions exist
- **WHEN** `solve_pc` is called with a board that cannot be perfectly cleared with the given queue
- **THEN** it returns an empty list

#### Scenario: Solver enforces hold-once-per-piece
- **WHEN** `solve_pc` is called with `hold='standard'`
- **THEN** no placement order requires holding twice consecutively without placing a piece

#### Scenario: Solver supports no-hold mode
- **WHEN** `solve_pc` is called with `hold='none'`
- **THEN** no solution uses the hold slot

#### Scenario: Max solutions limit
- **WHEN** `solve_pc` is called with `max_solutions=5`
- **THEN** at most 5 solutions are returned

#### Scenario: Pre-held piece at start
- **WHEN** `solve_pc` is called with `head_hold='T'`
- **THEN** the solver treats the hold slot as initially containing a T-piece

### Requirement: Solution object structure
Each solution returned by `solve_pc` SHALL contain the piece placement order, cumulative board states, per-step operations, unused pieces, and all valid topological orderings.

#### Scenario: Solution contains piece order
- **WHEN** a solution is returned
- **THEN** `solution.piece_order` is a list of piece type strings in placement order matching draw+hold rules

#### Scenario: Solution contains board states
- **WHEN** a solution is returned
- **THEN** `solution.board_states` is a list of `Board` objects, one after each placement, with the last board being empty (perfect clear)

#### Scenario: Solution contains operations
- **WHEN** a solution is returned
- **THEN** `solution.operations` is a list of `(PieceType, rotation, x, y)` tuples for each placement step

#### Scenario: Solution contains unused pieces
- **WHEN** a solution is returned and not all queue pieces were used
- **THEN** `solution.unused_pieces` lists the pieces that remain in queue

#### Scenario: Solution contains topological orderings
- **WHEN** a solution is returned
- **THEN** `solution.topological_orderings` contains at least one valid ordering; all orderings respect piece physics (no cell overlap, support below each piece's minimum row per column)

### Requirement: Wanted-saves expression parser
The system SHALL provide a parser for the wanted-saves expression language supporting boolean logic, avoiders, piece literals, regex matching, and queue constraints.

#### Scenario: Parse simple piece literal
- **WHEN** the expression `"T"` is parsed
- **THEN** the AST represents "must save T in at least one save"

#### Scenario: Parse AND expression
- **WHEN** the expression `"T&&S"` is parsed
- **THEN** the AST represents "both T and S must be saveable"

#### Scenario: Parse OR expression
- **WHEN** the expression `"T||S"` is parsed
- **THEN** the AST represents "at least one of T or S must be saveable"

#### Scenario: Parse NOT expression
- **WHEN** the expression `"!T"` is parsed
- **THEN** the AST represents "T cannot be saveable"

#### Scenario: Parse avoider expression
- **WHEN** the expression `"^S"` is parsed
- **THEN** the AST represents "possible to avoid saving S (at least one save without S)"

#### Scenario: Parse nested expression
- **WHEN** the expression `"!(T&&S)||L"` is parsed
- **THEN** the AST has correct precedence: NOT applies to the AND, then OR with L

#### Scenario: Parse regex expression
- **WHEN** the expression `"/T[ISZO]/"` is parsed
- **THEN** the AST contains a regex literal node with the pattern `T[ISZO]`

#### Scenario: Parse queue expression (multi-character piece literal)
- **WHEN** the expression `"LSZ"` is parsed
- **THEN** the AST represents "all of L, S, Z must appear across the saves"

#### Scenario: Parse expression with whitespace
- **WHEN** `"T && S || L"` is parsed
- **THEN** the AST is identical to parsing `"T&&S||L"`

#### Scenario: Invalid expression
- **WHEN** an expression with invalid syntax is parsed (e.g., `"T&&"`)
- **THEN** a `ValueError` is raised

### Requirement: Wanted-saves expression evaluation
The system SHALL provide an evaluator that tests whether a list of saves satisfies a wanted-saves AST.

#### Scenario: Piece literal matches
- **WHEN** the expression `"T"` is evaluated against saves `["TI", "SZ"]`
- **THEN** the result is `True` (T appears in "TI")

#### Scenario: Piece literal does not match
- **WHEN** the expression `"T"` is evaluated against saves `["LI", "SZ"]`
- **THEN** the result is `False`

#### Scenario: AND with both true
- **WHEN** `"T&&S"` is evaluated against saves `["TI", "SZ"]`
- **THEN** the result is `True`

#### Scenario: AND with one false
- **WHEN** `"T&&S"` is evaluated against saves `["TI", "LZ"]`
- **THEN** the result is `False`

#### Scenario: NOT inverts
- **WHEN** `"!T"` is evaluated against saves `["LI", "SZ"]`
- **THEN** the result is `True`

#### Scenario: Avoider with possible avoidance
- **WHEN** `"^S"` is evaluated against saves `["TI", "LZ"]`
- **THEN** the result is `True` (save "LZ" avoids S)

#### Scenario: Avoider with no avoidance possible
- **WHEN** `"^S"` is evaluated against saves `["TS", "SZ"]`
- **THEN** the result is `False` (every save contains S)

#### Scenario: Regex matches
- **WHEN** `"/T./"` is evaluated against saves `["TI", "SZ"]`
- **THEN** the result is `True` (save "TI" matches the pattern)

#### Scenario: Queue all must appear
- **WHEN** `"TSZ"` is evaluated against saves `["TI", "SZ"]`
- **THEN** the result is `True` (T, S, Z all appear across saves)

### Requirement: Save percentage computation
The system SHALL provide a function to compute the percentage of solves where a given wanted-saves expression is satisfied.

#### Scenario: Compute percentage
- **WHEN** save percentage is computed for expression `"T"` across 100 solves where 75 have T saveable
- **THEN** the result is 75.0

#### Scenario: Compute percentage with no matching solves
- **WHEN** save percentage is computed for expression `"I"` across solves where no solve saves I
- **THEN** the result is 0.0

#### Scenario: Percentage with over-solves mode
- **WHEN** `over_solves=True` and only 80 of 100 setups are solvable
- **THEN** the denominator is 80 (only solvable setups count)

### Requirement: Hold-aware queue simulation
The system SHALL provide functions to validate whether a placement order is reachable from a draw queue with standard hold rules, and to enumerate all reachable placement orders.

#### Scenario: Validate reachable order with hold
- **WHEN** `is_placement_order_valid(draw_queue=['J','I','Z','L','O','S','I'], placement_order=['I','J','Z','O','L','S'], hold_rule='standard')` is called
- **THEN** `True` is returned (the order is reachable with one hold swap)

#### Scenario: Validate unreachable order
- **WHEN** a placement order requires holding twice without placing (standard rule violation)
- **THEN** `False` is returned

#### Scenario: Enumerate reachable orders
- **WHEN** `enumerate_placement_orders(draw_queue=['J','I','Z'], hold_rule='standard')` is called
- **THEN** all returned orders respect standard hold rules and consume a valid prefix of the queue

#### Scenario: sfinder hold mode (unlimited)
- **WHEN** `hold_rule='sfinder'` is specified
- **THEN** the hold slot can be swapped multiple times without placing
