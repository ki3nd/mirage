from mirage.core.mem0.scope import detect
from mirage.types import PathSpec


def test_root():
    s = detect(PathSpec(original="/mem", directory="/mem", prefix="/mem"))
    assert s.level == "root"
    assert s.memory_id is None


def test_memory_file():
    p = PathSpec(original="/mem/abc.json", directory="/mem", prefix="/mem")
    s = detect(p)
    assert s.level == "memory"
    assert s.memory_id == "abc"


def test_hidden_is_invalid():
    p = PathSpec(original="/mem/.secret", directory="/mem", prefix="/mem")
    s = detect(p)
    assert s.level == "invalid"
