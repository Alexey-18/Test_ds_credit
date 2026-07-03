"""Тесты для функции check_subject()."""
import os
import pytest
from app.subject_check import check_subject

DATASET_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset")

def _load_subjects_test_file():
    path = os.path.join(DATASET_DIR, "subjects_test.txt")
    cases = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        status, subject = [p.strip() for p in line.split("|", 1)]
        cases.append((status, subject))
    return cases

@pytest.mark.parametrize("status, subject", _load_subjects_test_file())
def test_check_subject_against_dataset(status, subject):
    matches, confidence, reason = check_subject(subject)
    assert isinstance(matches, bool)
    assert 0.0 <= confidence <= 1.0
    assert isinstance(reason, str) and reason
    if status == "PASS":
        assert matches is True
        assert confidence >= 0.6
    elif status == "FAIL":
        assert matches is False
    elif status == "EDGE":
        # Пограничные случаи: не требуем конкретного matches, но ожидаем,что уверенность отразит неоднозначность (не должна быть "уверенно ошибочной" - то есть не должна быть >= 0.6 в сторону, о которой заявляет reason, если сам кейс задуман как спорный).
        assert confidence < 0.6

def test_check_subject_returns_expected_tuple_shape():
    result = check_subject("Поставка минеральных удобрений")
    assert len(result) == 3
    matches, confidence, reason = result
    assert isinstance(matches, bool)
    assert isinstance(confidence, float)
    assert isinstance(reason, str)
