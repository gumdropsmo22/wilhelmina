import json
import pathlib
from cogs.oracles import _is_prime, _lore_for_number

DATA = pathlib.Path("data")


def test_roll_lore_json_exists_and_has_minimum():
    p = DATA / "roll_lore.json"
    j = json.loads(p.read_text(encoding="utf-8"))
    assert isinstance(j, dict)
    assert "1" in j and "20" in j


def test_is_prime_basic_cases():
    assert _is_prime(2)
    assert _is_prime(3)
    assert not _is_prime(1)
    assert not _is_prime(4)
    assert _is_prime(29)


def test_lore_for_number_specials_and_parity():
    s13 = _lore_for_number(13)
    assert isinstance(s13, str) and s13
    even = _lore_for_number(8)
    odd = _lore_for_number(9)
    assert isinstance(even, str) and isinstance(odd, str)
