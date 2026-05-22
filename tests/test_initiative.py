from __future__ import annotations

from factory.initiative import generate_initiative_id


def test_generate_initiative_id_length():
    iid = generate_initiative_id()
    assert len(iid) == 12
    assert iid.isalnum()


def test_generate_initiative_id_unique():
    ids = {generate_initiative_id() for _ in range(100)}
    assert len(ids) == 100
