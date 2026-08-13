"""Which rules the reachability tests run under.

The bitboard search is defined for any :class:`~mino_sdk.pieces.RotationSystem`
and for both descent modes, but a run checks **one** combination — the one
asked for — rather than sweeping them. Unasked, that is the opener package's
own default: TETR.IO's SRS+, full reachability.

    pytest tests --system srs --mode instant
"""

import pytest

from mino_sdk.pieces import SRS, SRSPlus

SYSTEMS = {"srs": SRS, "srs+": SRSPlus}
MODES = ("full", "instant")


def pytest_addoption(parser):
    parser.addoption(
        "--system", action="store", default="srs+", choices=sorted(SYSTEMS),
        help="rotation system to check against the engine (default: srs+)",
    )
    parser.addoption(
        "--mode", action="store", default="full", choices=MODES,
        help="descent mode: full soft drop, or an instant one (default: full)",
    )


@pytest.fixture(scope="session")
def system(request):
    """The rotation system this run was asked for."""
    return SYSTEMS[request.config.getoption("--system")]()


@pytest.fixture(scope="session")
def instant(request):
    """True when this run was asked for the instant-soft-drop mode."""
    return request.config.getoption("--mode") == "instant"
