"""Чисті функції оцінки відповідності (без БД) — легко тестуються.

Дві метрики подібності навичок вакансії A та кандидата B:
  * коефіцієнт Жаккара:   J(A, B) = |A ∩ B| / |A ∪ B|  — за множинами назв навичок;
  * косинусна подібність: cos(a, b) = (a · b) / (‖a‖ · ‖b‖) — за векторами рівнів володіння.
"""
import math

Skills = dict[str, tuple[str, int]]   # skill_key -> (назва, рівень)


def jaccard(a: Skills, b: Skills) -> float:
    ka, kb = set(a), set(b)
    union = ka | kb
    return len(ka & kb) / len(union) if union else 0.0


def cosine(a: Skills, b: Skills) -> float:
    keys = set(a) | set(b)
    dot = sum(a.get(k, ('', 0))[1] * b.get(k, ('', 0))[1] for k in keys)
    na = math.sqrt(sum(level ** 2 for _, level in a.values()))
    nb = math.sqrt(sum(level ** 2 for _, level in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def score(metric: str, vacancy: Skills, candidate: Skills) -> float:
    value = cosine(vacancy, candidate) if metric == 'cosine' else jaccard(vacancy, candidate)
    return round(value, 4)


def matched_missing(vacancy: Skills, candidate: Skills) -> tuple[list[str], list[str]]:
    """Збіглися (за вимогами вакансії) і яких вимог кандидат не має."""
    matched = sorted(vacancy[k][0] for k in vacancy if k in candidate)
    missing = sorted(vacancy[k][0] for k in vacancy if k not in candidate)
    return matched, missing


def compare(vacancy: Skills, candidate: Skills):
    """Детальне порівняння для пояснення: matched (з рівнями), missing, extra."""
    matched, missing, extra = [], [], []
    for key, (name, required) in sorted(vacancy.items()):
        if key in candidate:
            actual = candidate[key][1]
            matched.append({'skill': name, 'required': required, 'actual': actual, 'sufficient': actual >= required})
        else:
            missing.append({'skill': name, 'required': required})
    for key, (name, actual) in sorted(candidate.items()):
        if key not in vacancy:
            extra.append({'skill': name, 'actual': actual})
    return matched, missing, extra
