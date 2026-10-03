import csv
import io

LABELS = {"pro": "Жақтаймын", "con": "Қарсымын"}


def summary_rows(counts):
    total = sum(counts.values())
    return [{"Нұсқа": LABELS[key], "Дауыс саны": counts[key],
             "Үлес (%)": round(counts[key] / total * 100, 1) if total else 0.0}
            for key in LABELS]


def safe_cell(value):
    value = str(value)
    # Prevent spreadsheet formula execution, including whitespace-prefixed formulas.
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return value


def csv_bytes(rows, fields):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: safe_cell(row.get(key, "")) for key in fields})
    return output.getvalue().encode("utf-8-sig")
