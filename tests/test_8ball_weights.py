from collections import Counter
import random

def pick():
    r = random.random()
    if r < 0.50: return "A"
    elif r < 0.75: return "V"
    else: return "N"

def test_weights():
    random.seed(42)
    N = 100_000
    c = Counter(pick() for _ in range(N))
    assert 0.48 <= c["A"]/N <= 0.52
    assert 0.23 <= c["V"]/N <= 0.27
    assert 0.23 <= c["N"]/N <= 0.27
