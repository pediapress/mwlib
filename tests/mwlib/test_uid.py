import pytest

from mwlib.utils.unorganized import uid


def test_uid_length():
    """Test that uid() returns a string with a maximum length of the specified value."""
    for length in range(1, 20):
        assert len(uid(length)) <= length

def test_uid_uniqueness():
    """Test that uid() returns unique values."""
    uids = set()
    for _ in range(100):
        new_uid = uid()
        assert new_uid not in uids
        uids.add(new_uid)

def test_uid_default_length():
    """Test that uid() uses the default max length of 10 when no length is specified."""
    assert len(uid()) <= 10
