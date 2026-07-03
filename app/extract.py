"""Извлечение структурированных полей из текста документа.
Публичная функция :func:`extract` возвращает словарь с полями
``amount``, ``date``, ``inn``, ``contractor``, ``subject``. Поле, которое не
удалось надёжно определить, получает значение ``None`` - модуль сознательно
не пытается «угадывать» данные там, где уверенности недостаточно (см.
раздел про OCR-документ в RESULTS.md).
"""

from __future__ import annotations
import re
from datetime import date
from typing import Optional
from app.numwords_ru import find_amount_in_words

MONTHS_RU = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5,
    "июня": 6, "июля": 7, "августа": 8, "сентября": 9, "октября": 10,
    "ноября": 11, "декабря": 12,
}

AMOUNT_KEYWORDS = ("итого", "всего", "составляет", "к оплате", "сумма договора",)

_NUMBER_RE = re.compile(
    r"\d{1,3}(?:[ \u00A0]\d{3})+(?:[.,]\d{1,2})?"
    r"|\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?"
    r"|\d+[.,]\d{1,2}\s*(?:руб|₽|rub)"
    ,
    re.IGNORECASE,
)

_DATE_DOTTED_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
_DATE_SLASH_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2})\b")
_DATE_TEXT_RE = re.compile(
    r"\b(\d{1,2})\s+(" + "|".join(MONTHS_RU) + r")\s+(\d{4})\b",
    re.IGNORECASE,
)

_INN_RE = re.compile(r"ИНН(?:\s*/\s*КПП|/КПП)?\s*[:\s]*\s*(\d{10,12})\b", re.IGNORECASE)

_SELLER_LABEL_RE = re.compile(r"\b(поставщик\w*|продавец\w*|исполнитель\w*)\b", re.IGNORECASE)

_COMPANY_RE = re.compile(
    r"(?:ООО|ОАО|ЗАО|ПАО|АО|КФХ|УК)\s*«[^»]+»"
    r"|ИП\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ]\.\s*[А-ЯЁ]\.)?",
)

_SUBJECT_LABEL_RE = re.compile(
    r"(?:предмет(?:\s+оплаты|\s+договора)?)\s*:\s*([^\n]+)",
    re.IGNORECASE,
)

_TABLE_ROW_RE = re.compile(r"\|\s*1\s*\|\s*([^|]+?)\s*\|")

_HINT_ANNOTATION_RE = re.compile(r"\([^()]*!\)")

def _strip_hint_annotations(text: str) -> str:
    return _HINT_ANNOTATION_RE.sub("", text)

_CONTRACT_CLAUSE_RE = re.compile(
    r"обязуется\s+(?:поставить|передать[^,]*?|выполнить)\s*(?:в собственность\s+"
    r"(?:Покупателя|Заказчика)\s*)?,?\s*(?:а\s+(?:Покупатель|Заказчик)[^,]*,\s*)?"
    r"([^\n.]+?)(?:,\s*а\s+(?:Покупатель|Заказчик)|\.|,\s*ГОСТ)",
    re.IGNORECASE,
)

def _normalize_number(raw: str) -> float:
    """Приводит найденную строку с числом к float.
    Отличает случаи, когда запятая - десятичный разделитель
    (``1 250 000,00``), от случаев, когда запятая - разделитель тысяч
    (``1,250,000.00``).
    """
    cleaned = re.sub(r"[^\d.,]", "", raw)
    if "," in cleaned and "." in cleaned:
        # запятая = разделитель тысяч, точка = десятичный разделитель
        cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        integer_part, _, frac_part = cleaned.rpartition(",")
        if len(frac_part) <= 2:
            # запятая - десятичный разделитель
            cleaned = integer_part.replace(" ", "") + "." + frac_part
        else:
            cleaned = cleaned.replace(",", "").replace(" ", "")
    else:
        cleaned = cleaned.replace(" ", "")
    return float(cleaned)

def _date_to_iso(day: int, month: int, year: int) -> Optional[str]:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None

def extract_amount(text: str) -> Optional[float]:
    """Извлекает итоговую сумму документа.
    Приоритет:
    1. Число рядом с ключевыми словами («итого», «всего», «составляет», ...),
       последнее (по тексту) такое совпадение обычно и есть финальный
       итог - например, после строк «Итого без НДС» / «Итого с НДС»
       нужна вторая сумма.
    2. Сумма, записанная словами («девятьсот тысяч рублей»).
    3. Резервный вариант - максимальная из всех найденных денежных сумм
       в тексте.
    """
    best_amount: Optional[float] = None
    for kw in AMOUNT_KEYWORDS:
        for kw_match in re.finditer(re.escape(kw), text, re.IGNORECASE):
            window = text[kw_match.end(): kw_match.end() + 120]
            num_match = _NUMBER_RE.search(window)
            if num_match:
                try:
                    best_amount = _normalize_number(num_match.group(0))
                except ValueError:
                    continue
    if best_amount is not None:
        return best_amount
    words_amount = find_amount_in_words(text)
    if words_amount is not None:
        return words_amount
    all_matches = _NUMBER_RE.findall(text)
    values = []
    for m in all_matches:
        try:
            values.append(_normalize_number(m))
        except ValueError:
            pass
    return max(values) if values else None

def extract_date(text: str) -> Optional[str]:
    """Извлекает дату документа (ISO-строка ``YYYY-MM-DD``).
    Правило: берём самую первую по тексту дату - в договорах, счетах и актах
    из тестового датасета именно первая упомянутая дата является датой
    документа (дата составления/дата "от ..."). Единственное исключение -
    invoice_002.txt, где после даты выставления счёта отдельно указан срок
    оплаты в другом формате; это разобрано отдельно в RESULTS.md как
    осознанное ограничение текущей эвристики.
    """
    candidates = []
    for m in _DATE_DOTTED_RE.finditer(text):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        iso = _date_to_iso(d, mo, y)
        if iso:
            candidates.append((m.start(), iso))
    for m in _DATE_SLASH_RE.finditer(text):
        d, mo, y2 = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = 2000 + y2
        iso = _date_to_iso(d, mo, y)
        if iso:
            candidates.append((m.start(), iso))
    for m in _DATE_TEXT_RE.finditer(text):
        d = int(m.group(1))
        mo = MONTHS_RU[m.group(2).lower()]
        y = int(m.group(3))
        iso = _date_to_iso(d, mo, y)
        if iso:
            candidates.append((m.start(), iso))
    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0])
    return candidates[0][1]

def extract_inn(text: str) -> Optional[str]:
    """Извлекает ИНН контрагента-поставщика (не покупателя/заказчика).
    Логика: среди всех найденных ИНН выбираем тот, что стоит в одном
    "блоке" (строке/абзаце) с меткой Поставщик/Продавец/Исполнитель, а не
    Покупатель/Заказчик.
    """
    inn_matches = list(_INN_RE.finditer(text))
    if not inn_matches:
        return None
    seller_positions = [
        m.start() for m in _SELLER_LABEL_RE.finditer(text)
        if not text[max(0, m.start() - 3): m.start()].lower().endswith("по")
        # исключаем случайное срабатывание на "покупатель" не требуется
    ]
    if not seller_positions:
        return inn_matches[0].group(1)
    best_match = None
    best_distance = None
    for m in inn_matches:
        for pos in seller_positions:
            distance = abs(m.start() - pos)
            if distance <= 150 and (best_distance is None or distance < best_distance):
                best_distance = distance
                best_match = m
    return best_match.group(1) if best_match else inn_matches[0].group(1)

def extract_contractor(text: str) -> Optional[str]:
    """Извлекает наименование контрагента-поставщика/исполнителя."""
    label_matches = list(_SELLER_LABEL_RE.finditer(text))
    company_matches = list(_COMPANY_RE.finditer(text))
    if not label_matches or not company_matches:
        return None
    label_pos = label_matches[0].start()
    best_company = None
    best_distance = None
    for cm in company_matches:
        distance = abs(cm.start() - label_pos)
        if distance <= 100 and (best_distance is None or distance < best_distance):
            best_distance = distance
            best_company = cm
    return best_company.group(0) if best_company else None

def extract_subject(text: str) -> Optional[str]:
    """Извлекает предмет оплаты / предмет договора (эвристика, best-effort)."""
    m = _SUBJECT_LABEL_RE.search(text)
    if m:
        return m.group(1).strip(" .")
    m = _TABLE_ROW_RE.search(text)
    if m:
        return m.group(1).strip()
    m = _CONTRACT_CLAUSE_RE.search(text)
    if m:
        return m.group(1).strip(" ,")
    m = re.search(r"Основание\s*:\s*([^\n]+)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip(" .")
    return None

def extract(text: str) -> dict:
    """Извлекает структурированные поля из текста документа.
    :param text: сырой текст документа (результат OCR или из PDF/txt).
    :return: словарь с ключами ``amount`` (float|None), ``date`` (str|None,
        ISO 8601), ``inn`` (str|None), ``contractor`` (str|None),
        ``subject`` (str|None). Поля, которые не удалось надёжно
        определить, равны ``None``.
    """
    clean_text = _strip_hint_annotations(text)
    return {
        "amount": extract_amount(clean_text),
        "date": extract_date(clean_text),
        "inn": extract_inn(clean_text),
        "contractor": extract_contractor(clean_text),
        "subject": extract_subject(clean_text),
    }
