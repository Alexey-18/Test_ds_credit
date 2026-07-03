"""Тесты для функции classify()."""

import glob
import os
import pytest
from app.classify import classify

DATASET_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset")

def test_classify_invoice_example_from_spec():
    doc_type, confidence = classify("Счёт на оплату №12 от 01.03.2025 ...")
    assert doc_type == "invoice"
    assert confidence > 0.5

EXPECTED_TYPES = {
    "contract_001.txt": "contract",
    "spec_001.txt": "spec",
    "invoice_001.txt": "invoice",
    "invoice_002.txt": "invoice",
    "act_001.txt": "act",
    "act_002.txt": "act",
}

@pytest.mark.parametrize("filename, expected_type", sorted(EXPECTED_TYPES.items()))
def test_classify_on_dataset_documents(filename, expected_type):
    path = os.path.join(DATASET_DIR, filename)
    text = open(path, encoding="utf-8").read()
    doc_type, confidence = classify(text)
    assert doc_type == expected_type
    assert 0.0 <= confidence <= 1.0

def test_classify_ocr_garbage_is_unknown():
    """На нечитаемом OCR-документе классификатор не должен уверенно врать."""
    path = os.path.join(DATASET_DIR, "scan_ocr_001.txt")
    text = open(path, encoding="utf-8").read()
    doc_type, confidence = classify(text)
    assert doc_type == "unknown"

def test_classify_empty_text_is_unknown():
    doc_type, confidence = classify("")
    assert doc_type == "unknown"
    assert confidence == 0.0
