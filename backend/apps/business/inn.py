"""ИНН check digits (the ФНС algorithm): 10 digits for a company, 12 for an entrepreneur."""

_W10 = (2, 4, 10, 3, 5, 9, 4, 6, 8)
_W11 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
_W12 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)


def _digit(digits: list[int], weights: tuple[int, ...]) -> int:
    return sum(w * d for w, d in zip(weights, digits, strict=False)) % 11 % 10


def inn_is_valid(inn: str) -> bool:
    if not inn.isdigit() or len(inn) not in (10, 12):
        return False
    digits = [int(c) for c in inn]
    if len(digits) == 10:
        return digits[9] == _digit(digits, _W10)
    return digits[10] == _digit(digits, _W11) and digits[11] == _digit(digits, _W12)
