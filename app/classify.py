"""Классификация типа документа по содержимому.
Публичная функция :func:`classify` возвращает пару ``(тип, уверенность)``,
где тип - один из ``contract``, ``spec``, ``invoice``, ``act``, ``unknown``.
Подход: скоринг по ключевым словам/фразам, характерным для каждого типа
документа (простой, прозрачный, не требует обучающей выборки - что уместно
при 6 примерах документов). Уверенность считается как нормализованная доля
скора победителя от суммы скоров всех категорий. Если разрыв между первым
и вторым местом меньше порога - результат считается ненадёжным и
возвращается ``("unknown", confidence)``.
"""
from __future__ import annotations
import re
from typing import Dict, List, Tuple

CONFIDENCE_GAP_THRESHOLD = 0.15

_KEYWORDS: Dict[str, List[Tuple[str, float]]] = {
    "contract": [
        (r"договор\w*\s+поставки", 1.5),
        (r"\bстороны\b", 1.0),
        (r"заключили\s+настоящ\w+\s+договор", 4.0),
        (r"именуем\w+\s+в\s+дальнейшем", 3.0),
        (r"предмет\s+договора", 2.0),
        (r"\bдоговор\b", 0.3),
    ],
    "spec": [
        (r"специфик\w+", 3.5),
        (r"приложени\w+\s*№", 1.5),
        (r"наименование\s+товара", 1.5),
        (r"таблица\s+товаров", 1.5),
    ],
    "invoice": [
        # Название документа "Счёт на оплату" - самый сильный и однозначный
        # сигнал, поэтому у него намного больший вес.
        (r"сч[её]т\s+на\s+оплату", 5.0),
        (r"\bсч[её]т\s*№", 2.0),
        (r"к\s+оплате", 1.0),
        (r"просим\s+оплатить", 2.0),
        (r"срок\s+оплаты", 1.0),
        (r"оплата\s+до", 1.0),
    ],
    "act": [
        (r"акт\s+выполненных\s+работ", 3.5),
        (r"универсальный\s+передаточный\s+документ", 3.5),
        (r"\bупд\b", 2.5),
        (r"товар\s+получен|товар\s+передан|работы\s+приняты|работы\s+выполнены", 2.0),
        (r"\bакт\b", 1.0),
    ],
}

def classify(text: str) -> Tuple[str, float]:
    """Классифицирует тип документа.
    :param text: текст документа.
    :return: кортеж ``(doc_type, confidence)``, где ``doc_type`` - одно из
        ``contract``, ``spec``, ``invoice``, ``act``, ``unknown``, а
        ``confidence`` - число от 0 до 1.
    """
    lowered = text.lower()
    scores: Dict[str, float] = {}
    for doc_type, patterns in _KEYWORDS.items():
        score = 0.0
        for pattern, weight in patterns:
            matches = re.findall(pattern, lowered)
            if matches:
                score += weight
        scores[doc_type] = score
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    total = sum(s for _, s in ranked)
    if total == 0:
        return "unknown", 0.0
    top_type, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    top_share = top_score / total
    second_share = second_score / total
    gap = top_share - second_share
    if gap < CONFIDENCE_GAP_THRESHOLD:
        # Недостаточно уверенный результат - не рискуем ошибочной меткой.
        return "unknown", round(top_share, 2)
    return top_type, round(top_share, 2)
