"""Тесты для функции extract()."""
import glob
import os
import pytest
from app.extract import extract

DATASET_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset")

def test_amount_ru_format_with_comma():
    assert extract("Сумма: 1 250 000,00 руб.")["amount"] == 1_250_000.0

def test_inn_extraction():
    assert extract("ИНН 7701234567")["inn"] == "7701234567"

def test_amount_none_when_no_digits():
    assert extract("без цифр")["amount"] is None

@pytest.mark.parametrize(
    "text, expected",
    [
        ("Цена: 1250000.00 ₽", 1_250_000.0),
        ("К оплате 1,250,000.00 RUB", 1_250_000.0),
        ("Итого: 500000.00 ₽", 500_000.0),
        ("Итого: 1 250 000 руб.", 1_250_000.0),
    ],
)
def test_amount_formats(text, expected):
    assert extract(text)["amount"] == expected

@pytest.mark.parametrize(
    "text, expected_iso",
    [
        ("Дата: 01.03.2025", "2025-03-01"),
        ("Дата: 1 марта 2025 г.", "2025-03-01"),
        ("Дата: 03/01/25", "2025-01-03"),
    ],
)
def test_date_formats(text, expected_iso):
    assert extract(text)["date"] == expected_iso

def test_amount_in_words():
    text = "Стоимость услуг составляет девятьсот тысяч рублей 00/100."
    assert extract(text)["amount"] == 900_000.0

EXPECTED = {
    "contract_001.txt": {"amount": 1_250_000.0, "date": "2025-03-01", "inn": "7701234567"},
    "invoice_001.txt": {"amount": 1_250_000.0, "date": "2025-03-03", "inn": "7701234567"},
    "act_001.txt": {"amount": 1_250_000.0, "date": "2025-03-24", "inn": "7701234567"},
    "act_002.txt": {"amount": 500_000.0, "date": "2025-04-01", "inn": "504712345678"},
}

@pytest.mark.parametrize("filename", sorted(EXPECTED.keys()))
def test_extract_on_dataset_documents(filename):
    """Сверяем extract() с ожидаемыми результатами из dataset/README.md.
    invoice_002.txt намеренно не входит в этот список - см. обсуждение
    неоднозначности дат (дата выставления vs. срок оплаты) в RESULTS.md.
    """
    path = os.path.join(DATASET_DIR, filename)
    text = open(path, encoding="utf-8").read()
    result = extract(text)
    expected = EXPECTED[filename]
    assert result["amount"] == expected["amount"]
    assert result["date"] == expected["date"]
    assert result["inn"] == expected["inn"]

def test_extract_on_ocr_document_is_honest_about_uncertainty():
    """На "OCR-мусоре" функция не должна выдавать случайные значения.
    Дополнительно: раздел (не 01.03.2025!) в тестовом файле - это пометка
    для проверяющего, а не то что должен видеть/выдавать OCR-конвейер.
    Поэтому extract() отфильтровывает подобные аннотации перед разбором.
    """
    path = os.path.join(DATASET_DIR, "scan_ocr_001.txt")
    text = open(path, encoding="utf-8").read()
    result = extract(text)
    assert result["inn"] is None
    assert result["contractor"] is None

def test_all_dataset_files_are_readable():
    files = glob.glob(os.path.join(DATASET_DIR, "*.txt"))
    assert len(files) >= 7