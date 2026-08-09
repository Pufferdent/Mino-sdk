import pytest
from mino_sdk import get_piece_cells, PieceType, Piece, SRS


ALL_TYPES = [
    PieceType.T, PieceType.I, PieceType.L, PieceType.J,
    PieceType.S, PieceType.Z, PieceType.O,
]


class TestGetPieceCells:
    def test_t_piece_spawn(self):
        cells = get_piece_cells(PieceType.T, rotation=0, x=5, y=2)
        assert len(cells) == 4
        assert (2, 5) not in cells  # x,y is bottom-left corner, so cells offset from that
        for r, c in cells:
            assert r >= 2 and c >= 5

    def test_o_piece_origin(self):
        cells = get_piece_cells(PieceType.O, rotation=0, x=0, y=0)
        assert set(cells) == {(0, 0), (0, 1), (1, 0), (1, 1)}

    def test_i_piece_right_rotation(self):
        cells = get_piece_cells(PieceType.I, rotation=1, x=4, y=3)
        assert len(cells) == 4

    def test_invalid_rotation(self):
        with pytest.raises(ValueError, match="Rotation"):
            get_piece_cells(PieceType.T, rotation=5, x=0, y=0)

    def test_invalid_coord_system(self):
        with pytest.raises(ValueError, match="coord_system"):
            get_piece_cells(PieceType.T, rotation=0, x=0, y=0, coord_system="invalid")

    def test_matches_piece_cells(self):
        for pt in ALL_TYPES:
            for rot in range(4):
                p = Piece(pt, rotation=rot, row=3, col=2, system=SRS())
                cells = get_piece_cells(pt, rotation=rot, x=2, y=3)
                assert set(cells) == set(p.cells)

    def test_fumen_coord_system(self):
        cells = get_piece_cells(PieceType.O, rotation=0, x=0, y=0, coord_system="fumen")
        assert set(cells) == {(0, 0), (1, 0), (0, 1), (1, 1)}

    def test_all_piece_types_have_four_cells(self):
        for pt in ALL_TYPES:
            for rot in range(4):
                cells = get_piece_cells(pt, rotation=rot, x=0, y=0)
                assert len(cells) == 4, f"{pt} rotation {rot}"


class TestGetPieceCellsOffset:
    def test_offset_matches_piece(self):
        for pt in ALL_TYPES:
            for rot in range(4):
                origin = get_piece_cells(pt, rotation=rot, x=0, y=0)
                shifted = get_piece_cells(pt, rotation=rot, x=5, y=3)
                assert set(shifted) == {(r + 3, c + 5) for r, c in origin}
