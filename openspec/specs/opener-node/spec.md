# Opener Node

## Purpose

Define the node key of the opener graph — the state openers are discovered in.
A node stores only what cannot be recomputed: a canonical fumen of the stack,
and the pieces still to come. Bag structure, coverage, spins, event names,
damage and opener identity are all calculated from those two, never stored
alongside them.

## Requirements

### Requirement: Node identity
The system SHALL provide an immutable, hashable `Node` carrying exactly a `fumen` string and a `queue` of piece types. Back-to-back state, combo state, piece colours, move history and accumulated damage SHALL NOT be node state. Two nodes with equal fumen and queue SHALL compare and hash equal, so that distinct build orders reaching the same state converge on one node.

#### Scenario: Equal state collapses to one node
- **WHEN** two nodes are built from boards with identical occupancy and equal queues
- **THEN** they compare equal and collapse to a single entry in a set

#### Scenario: Different occupancy is a different node
- **WHEN** two nodes are built from boards whose filled cells differ
- **THEN** they do not compare equal

### Requirement: Canonical uncolored fumen
A node SHALL encode its stack as a fumen in which every filled cell is painted a single fixed colour, so that the encoding depends only on occupancy. Building a node from a board SHALL apply that normalisation. Decoding a node's fumen SHALL reproduce its occupancy exactly.

#### Scenario: Colour is normalised away
- **WHEN** two boards with identical occupancy but different piece colours are used to build nodes
- **THEN** the resulting fumen strings are equal

#### Scenario: The fumen round-trips
- **WHEN** a node's fumen is decoded back to a board
- **THEN** the filled cells match those the node was built from

### Requirement: Bag structure recovered by multiplicity
A known queue SHALL span at most two bags, so a piece type SHALL appear at most twice; a queue violating this SHALL be rejected. The system SHALL recover the bag split by counting rather than storing it: repeatedly extracting the distinct types of the remaining queue yields at most two sets, reported smallest first, each in canonical `T I L J S Z O` order. The result SHALL depend only on the queue's contents, not its order.

#### Scenario: A full bag is one set
- **WHEN** the bag structure of a seven-distinct-piece queue is recovered
- **THEN** it is a single set of all seven in canonical order

#### Scenario: A duplicate splits the queue into two sets
- **WHEN** the bag structure of queue `TTOIL` is recovered
- **THEN** it is the sets `T` and `TILO`

#### Scenario: Recovery is order-independent
- **WHEN** two queues with the same contents in different orders have their bag structure recovered
- **THEN** the results are equal

#### Scenario: A queue spanning more than two bags is rejected
- **WHEN** a queue containing three copies of one type is constructed
- **THEN** the operation raises `ValueError`

### Requirement: Pattern rendering
A node SHALL render its queue as an sfinder pattern string of comma-separated terms, one per recovered set. A term over all seven types SHALL render as `*pN`; any other term SHALL render as `[<letters>]pN` in canonical order. This splits duplicates across terms, since sfinder draws each type at most once per term.

#### Scenario: A full bag renders as a wildcard
- **WHEN** a seven-distinct-piece queue is rendered
- **THEN** the pattern is `*p7`

#### Scenario: A partial bag names its pieces
- **WHEN** a queue of only Z and O is rendered
- **THEN** the pattern is `[ZO]p2`

#### Scenario: A duplicate leads its own term
- **WHEN** queue `TTOIL` is rendered
- **THEN** the pattern is `[T]p1,[TILO]p4`

### Requirement: Future enumeration
A node SHALL lazily enumerate every distinct order its queue could arrive in. Orderings SHALL NOT repeat: duplicated types are interchangeable, and yielding an ordering twice would bias coverage measured over the node.

#### Scenario: Every ordering is enumerated
- **WHEN** a three-distinct-piece queue is enumerated
- **THEN** six orderings are yielded

#### Scenario: A duplicate does not repeat orderings
- **WHEN** queue `TTI` is enumerated
- **THEN** exactly three distinct orderings are yielded

### Requirement: Hold as the queue head
A held piece SHALL be the first element of `queue`, with no separate hold field. The pieces placeable at a node SHALL be the first two queue entries, deduplicated by type. Consuming index 0 SHALL play the head; consuming index 1 SHALL play the second entry and leave the head in front, which is exactly hold semantics. Consuming any index beyond 1 SHALL be rejected.

#### Scenario: Both head entries are placeable
- **WHEN** a queue begins with two distinct types
- **THEN** both are reported as placeable

#### Scenario: A repeated head deduplicates
- **WHEN** the first two queue entries are the same type
- **THEN** exactly one placeable type is reported

#### Scenario: Consuming the second entry holds the first
- **WHEN** index 1 is consumed from queue `TIL`
- **THEN** the resulting queue is `TL`, with T still in front as the held piece

#### Scenario: Deeper queue entries are not placeable
- **WHEN** an index greater than 1 is consumed
- **THEN** the operation raises `ValueError`

### Requirement: Transition
Consuming a piece SHALL produce a new node from the resulting board, applying the canonical normalisation, and SHALL optionally accept a newly revealed piece appended to the queue tail.

#### Scenario: A revealed piece extends the queue
- **WHEN** a piece is consumed and a new type is revealed
- **THEN** the new type is appended to the resulting node's queue

#### Scenario: The new board becomes the node's stack
- **WHEN** a piece is consumed onto a board differing from the current stack
- **THEN** the resulting node's fumen differs from the original's

### Requirement: Stack metrics
A node SHALL report a `holes` count of empty cells with at least one filled cell above them in the same column, and a `mirrored` reflection of its stack across the playfield with the queue unchanged. Mirroring SHALL be an involution.

#### Scenario: Covered cells are holes
- **WHEN** a stack has one empty cell with a filled cell above it
- **THEN** the hole count is 1

#### Scenario: Mirroring reflects and preserves the queue
- **WHEN** a node is mirrored
- **THEN** the stack is reflected left-to-right and the queue is unchanged

#### Scenario: Mirroring twice is the identity
- **WHEN** a node is mirrored twice
- **THEN** the result equals the original
