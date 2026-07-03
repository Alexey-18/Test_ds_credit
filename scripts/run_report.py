"""Скрипт для прогона пайплайна по всему датасету и построения отчёта.

Запуск:
    python scripts/run_report.py

Выводит в консоль таблицы результатов extract()/classify()/check_subject()
и сохраняет график confidence по документам в reports/confidence_chart.png.
"""

from __future__ import annotations
import glob
import os
import matplotlib.pyplot as plt
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.extract import extract
from app.classify import classify
from app.subject_check import check_subject

plt.use("Agg")

DATASET_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset")
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")

extract_ex = {
    "contract_001.txt": {"amount": 1_250_000.0, "date": "2025-03-01", "inn": "7701234567"},
    "invoice_001.txt": {"amount": 1_250_000.0, "date": "2025-03-03", "inn": "7701234567"},
    "invoice_002.txt": {"amount": 900_000.0, "date": "2025-02-28", "inn": "5047123456"},
    "act_001.txt": {"amount": 1_250_000.0, "date": "2025-03-24", "inn": "7701234567"},
    "act_002.txt": {"amount": 500_000.0, "date": "2025-04-01", "inn": "504712345678"},
}

types_ex = {
    "contract_001.txt": "contract",
    "spec_001.txt": "spec",
    "invoice_001.txt": "invoice",
    "invoice_002.txt": "invoice",
    "act_001.txt": "act",
    "act_002.txt": "act",
    "scan_ocr_001.txt": "unknown",
}

def _mark(ok: bool) -> str:
    return "OK " if ok else "DIFF"

def report_extract():
    print("1) extract() результаты по датасету")
    header = f"{'файл':<20}{'amount':>14}{'date':>14}{'inn':>16}{'contractor':<20}{'subject':<30}"
    print(header)
    print("-" * len(header))
    for path in sorted(glob.glob(os.path.join(DATASET_DIR, "*.txt"))):
        name = os.path.basename(path)
        if name == "subjects_test.txt":
            continue
        text = open(path, encoding="utf-8").read()
        res = extract(text)
        subject_str = str(res.get('subject')) if res.get('subject') else "None"
        print(
            f"{name:<20}{str(res['amount']):>14}{str(res['date']):>14}"
            f"{str(res['inn']):>16}{str(res['contractor']):<20}{subject_str:<30}"
        )
    print("Сверка с ожидаемыми значениями (dataset/README.md):")
    total, correct = 0, 0
    for name, expected in extract_ex.items():
        path = os.path.join(DATASET_DIR, name)
        text = open(path, encoding="utf-8").read()
        res = extract(text)
        for field in ("amount", "date", "inn", "subject"):
            total += 1
            ok = res[field] == expected[field]
            correct += int(ok)
            if not ok:
                print(f"  {_mark(ok)} {name}: {field} = {res[field]!r} (ожидалось {expected[field]!r})")
    print(f"Совпало полей: {correct}/{total}")

def report_classify():
    print("2) classify() результаты по датасету")
    correct, total = 0, 0
    for path in sorted(glob.glob(os.path.join(DATASET_DIR, "*.txt"))):
        name = os.path.basename(path)
        if name == "subjects_test.txt":
            continue
        text = open(path, encoding="utf-8").read()
        doc_type, confidence = classify(text)
        expected = types_ex.get(name)
        ok = doc_type == expected
        total += 1
        correct += int(ok)
        print(f"  {_mark(ok):5}{name:<20}-> {doc_type:<10} confidence={confidence:.2f}  (ожидалось: {expected})")
    print(f"  Совпало: {correct}/{total}")
    print()

def report_subjects():
    print("3) check_subject() результаты по subjects_test.txt")
    path = os.path.join(DATASET_DIR, "subjects_test.txt")
    correct, total = 0, 0
    rows = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        status, subject = [p.strip() for p in line.split("|", 1)]
        matches, confidence, reason = check_subject(subject)
        if status == "PASS":
            predicted = "PASS" if (matches and confidence >= 0.6) else ("EDGE" if confidence < 0.6 else "FAIL")
        elif status == "FAIL":
            predicted = "FAIL" if not matches else "PASS"
        else:
            predicted = "EDGE" if confidence < 0.6 else ("PASS" if matches else "FAIL")
        ok = predicted == status
        total += 1
        correct += int(ok)
        rows.append((ok, status, predicted, matches, confidence, subject, reason))
        print(
            f"{_mark(ok):5}ожидание={status:<5} matches={str(matches):<5} "
            f"conf={confidence:.2f}  {subject}"
        )
        print(f"reason: {reason}")
    print(f"Совпало с ожидаемой категорией PASS/FAIL/EDGE: {correct}/{total}")
    return rows

def save_confidence_chart(rows):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    labels = [r[5][:28] + ("…" if len(r[5]) > 28 else "") for r in rows]
    confidences = [r[4] for r in rows]
    colors = []
    for r in rows:
        status = r[1]
        if status == "PASS":
            colors.append("#3a9d5d")
        elif status == "FAIL":
            colors.append("#c0392b")
        else:
            colors.append("#e0a300")
    fig, ax = plt.subplots(figsize=(10, 8))
    y_pos = range(len(labels))
    ax.barh(y_pos, confidences, color=colors)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.axvline(0.6, color="gray", linestyle="--", linewidth=1)
    ax.set_xlabel("confidence")
    ax.set_title("check_subject(): уверенность по каждому предмету оплаты (зелёный=ожидание PASS, красный=FAIL, жёлтый=EDGE)")
    ax.set_xlim(0, 1.05)
    fig.tight_layout()
    out_path = os.path.join(REPORTS_DIR, "confidence_chart.png")
    fig.savefig(out_path, dpi=150)
    print(f"График: {out_path}")

if __name__ == "__main__":
    report_extract()
    report_classify()
    rows = report_subjects()
    save_confidence_chart(rows)
