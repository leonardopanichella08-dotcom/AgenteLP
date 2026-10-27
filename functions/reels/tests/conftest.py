import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="session")
def podcast(tmp_path_factory):
    from app.demo import make_podcast
    return make_podcast(tmp_path_factory.mktemp("podcast"))


@pytest.fixture(scope="session")
def script_project(tmp_path_factory):
    from app.demo import make_script_project
    return make_script_project(tmp_path_factory.mktemp("script"))


@pytest.fixture(scope="session")
def long_video(tmp_path_factory):
    from app.demo import make_long
    return make_long(tmp_path_factory.mktemp("long"))


class BoxDetector:
    """Rileva i volti-cartone alle posizioni vere (il rilevatore reale è Haar)."""
    def __init__(self, boxes):
        self.boxes = list(boxes.values())

    def detect(self, frame):
        return self.boxes
