"""Проверка соответствия предмета оплаты условиям льготной программы.
Публичная функция :func:`check_subject` реализована без обращения к
внешним LLM API (вариант 1 из задания: список разрешённых категорий +
keyword/fuzzy matching), чтобы код гарантированно работал локально без
ключей. При желании подключить LLM-подход, сохранив fallback - см.
раздел «Возможные улучшения» в RESULTS.md.
"""
from __future__ import annotations
import difflib
import re
from typing import Dict, List, Tuple

ALLOWED_CATEGORIES: Dict[str, List[str]] = {
    "агрохимия / удобрения / СЗР": [
        "удобрен", "агрохим", "средства защиты растений", "сзр",
        "фунгицид", "гербицид", "пестицид", "инсектицид", "карбамид",
        "кас-32", "кас32",
    ],
    "семена": ["семена", "семян", "посевн", "посевная партия"],
    "техника: обслуживание / ремонт / запчасти": [
        "ремонт", "техническое обслуживание", "обслуживание техники",
        "запасн", "запчаст", "комбайн", "трактор",
        "сельскохозяйствен", "сельхозтехник", "агротехник",
    ],
    "топливо / ГСМ": ["топливо", "дизель", "гсм", "бензин"],
    "полевые работы": [
        "агрохимические работы", "внесение удобрений", "полевые работы",
        "обработка почвы", "предпосевная обработка", "посевная",
        "уборка урожая",
    ],
    "страхование урожая": ["страхование урожая", "страховани"],
}

# Слова-маркеры, указывающие, что речь идёт скорее об услуге/аренде/сопровождении, а не о прямой поставке товара или выполнении сельхоз-работ. Наличие такого маркера рядом с разрешённым словом снижает уверенность (см. EDGE-кейсы).
AMBIGUOUS_SERVICE_MARKERS = [
    "транспортн", "доставк", "перевозк", "аренда", "консультац",
    "консультант",
]

# Явно неподходящие категории - используются только для объяснения отказа.
EXCLUDED_CATEGORIES: Dict[str, List[str]] = {
    "аренда офисной/коммерческой недвижимости": ["аренда офис", "офисного помещения"],
    "юридические/консультационные услуги": ["юридическ", "сопровождение сделки", "консультационные услуги"],
    "офисные товары": ["офисной мебели", "канцеляр"],
    "IT/маркетинг": ["сайта", "seo", "продвижение", "разработка корпоративного"],
    "клининг": ["клининг", "уборка административного"],
    "обучение персонала": ["обучение", "тренинг", "механизаторов работе"],
}

MATCH_THRESHOLD = 0.6
EDGE_LOW = 0.4
EDGE_HIGH = 0.6

def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()

def _best_keyword_score(text: str, keywords: List[str]) -> float:
    """Возвращает лучший скор совпадения текста с одним из ключевых слов.
    1.0 - точное вхождение подстроки; иначе - оценка нечёткого сходства
    (``difflib.SequenceMatcher``), которая покрывает опечатки/словоформы,
    не предусмотренные явно в списке ключевых слов.
    """
    best = 0.0
    for kw in keywords:
        if kw in text:
            return 1.0
        # нечёткое сравнение ключевого слова с каждым словом текста
        for word in text.split():
            ratio = difflib.SequenceMatcher(None, kw, word).ratio()
            best = max(best, ratio)
    return best

def _best_category_match(text: str, categories: Dict[str, List[str]]) -> Tuple[str, float]:
    best_category = ""
    best_score = 0.0
    for category, keywords in categories.items():
        score = _best_keyword_score(text, keywords)
        if score > best_score:
            best_score = score
            best_category = category
    return best_category, best_score

def check_subject(subject: str) -> Tuple[bool, float, str]:
    """Проверяет, относится ли предмет оплаты к льготной сельхоз-программе.
    :param subject: текстовое описание предмета оплаты.
    :return: кортеж ``(matches, confidence, reason)``, где ``matches`` -
        соответствует ли предмет программе, ``confidence`` - уверенность
        (0..1), ``reason`` - человекочитаемое объяснение вывода.
    """
    text = _normalize(subject)
    allowed_category, allowed_score = _best_category_match(text, ALLOWED_CATEGORIES)
    excluded_category, excluded_score = _best_category_match(text, EXCLUDED_CATEGORIES)
    has_ambiguous_marker = any(marker in text for marker in AMBIGUOUS_SERVICE_MARKERS)
    # Явное соответствие разрешённой категории, без признаков "услуги/аренды".
    if allowed_score >= MATCH_THRESHOLD and not has_ambiguous_marker and allowed_score >= excluded_score:
        return (
            True,
            round(allowed_score, 2),
            f"предмет относится к категории «{allowed_category}»",
        )
    # Явное соответствие исключённой категории.
    if excluded_score >= MATCH_THRESHOLD and excluded_score > allowed_score:
        return (
            False,
            round(excluded_score, 2),
            f"предмет не относится к сельхоз-деятельности "
            f"(похоже на категорию «{excluded_category}»)",
        )
    # Разрешённое слово есть, но есть и признак "услуги/аренды/консультации" - пограничный случай: не поставка/работа напрямую, а сопутствующая услуга.
    if allowed_score >= MATCH_THRESHOLD and has_ambiguous_marker:
        # Уверенность намеренно ограничена значением ниже MATCH_THRESHOLD это пограничный случай ("услуга", а не прямая поставка/работа), и его не следует автоматически засчитывать как явное совпадение.
        confidence = min(allowed_score, MATCH_THRESHOLD - 0.05)
        return (
            False,
            round(max(confidence, EDGE_LOW), 2),
            f"содержит признаки категории «{allowed_category}», но описывает услугу/аренду, а не прямую поставку товара или выполнение сельхоз-работ - требуется ручная проверка",
        )
    # Ничего явного не найдено - низкая уверенность в любую сторону.
    if allowed_score > excluded_score:
        return (
            False,
            round(max(allowed_score, EDGE_LOW), 2),
            "слабое совпадение с разрешёнными категориями, уверенности недостаточно - требуется ручная проверка",
        )
    return (
        False,
        round(max(excluded_score, 0.3), 2),
        "не найдено явного соответствия ни одной из разрешённых категорий льготной программы",
    )
