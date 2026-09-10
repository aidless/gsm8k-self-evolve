import math

def mcnemar_two_sided(better: int, worse: int) -> float:
    n = better + worse
    if n == 0:
        return 1.0
    k = min(better, worse)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)

def ledger_ok(total_a: int, total_b: int, better: int, worse: int) -> bool:
    return (total_b - total_a) == (better - worse)
