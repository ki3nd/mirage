from mirage.ops.mem0 import OPS


def test_ops_registered():
    names = set()
    for fn in OPS:
        for ro in fn._registered_ops:
            names.add((ro.name, ro.resource))
    assert ("readdir", "mem0") in names
    assert ("read", "mem0") in names
    assert ("stat", "mem0") in names
