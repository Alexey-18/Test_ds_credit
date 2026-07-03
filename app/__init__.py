"""Пакет с модулями интеллектуальной обработки документов.
Содержит три независимых модуля, покрывающих части тестового задания:
- ``extract``      — извлечение структурированных полей из текста документа;
- ``classify``     — классификация типа документа;
- ``subject_check`` — проверка соответствия предмета оплаты льготной программе.
"""
from app.extract import extract
from app.classify import classify
from app.subject_check import check_subject

__all__ = ["extract", "classify", "check_subject"]
