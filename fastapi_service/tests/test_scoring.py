"""Юніт-тести чистих функцій оцінки (без БД і HTTP)."""
import pytest

from app.services import scoring

A = {'python': ('Python', 4), 'django': ('Django', 3), 'docker': ('Docker', 2)}
B = {'python': ('Python', 5), 'django': ('Django', 4), 'excel': ('Excel', 5)}


def test_jaccard_basic():
    # перетин {python, django} = 2; об'єднання {python, django, docker, excel} = 4
    assert scoring.jaccard(A, B) == pytest.approx(0.5)


def test_jaccard_identical_and_disjoint():
    assert scoring.jaccard(A, A) == 1.0
    assert scoring.jaccard(A, {'excel': ('Excel', 1)}) == 0.0
    assert scoring.jaccard({}, {}) == 0.0


def test_cosine_basic_and_empty():
    assert scoring.cosine(A, A) == pytest.approx(1.0)
    assert 0 < scoring.cosine(A, B) < 1
    assert scoring.cosine(A, {}) == 0.0


def test_matched_missing_and_compare():
    matched, missing = scoring.matched_missing(A, B)
    assert matched == ['Django', 'Python'] and missing == ['Docker']
    ok, miss, extra = scoring.compare(A, B)
    assert {m['skill']: m['sufficient'] for m in ok} == {'Python': True, 'Django': True}
    assert [m['skill'] for m in miss] == ['Docker'] and [m['skill'] for m in extra] == ['Excel']
