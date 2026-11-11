"""
Excel (.xlsx) and CSV files for download.

- Text that starts with = + - @ is prefixed with ' so spreadsheet apps never run it as a
  formula (people type their own names and addresses).
- CSV is UTF-8 with a BOM so Excel shows Hindi names and ₹ correctly; dates are YYYY-MM-DD
  and amounts plain numbers, which every program reads the same way.
- Long numbers such as Aadhaar are written as text so Excel cannot turn them into 2.2E+11.
"""

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@dataclass(frozen=True)
class Column:
    key: str
    title: str
    kind: str = "text"  # text | int | money | date
    width: int = 16
    choices: tuple[str, ...] = ()  # dropdown in Excel templates


def safe_text(value: str) -> str:
    return "'" + value if value.startswith(FORMULA_START) else value


def _plain(value, kind: str):
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return f"{value.normalize():f}" if value == value.to_integral() else f"{value:.2f}"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, str):
        return safe_text(value)
    return value


def to_csv(columns: list[Column], rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow([c.title for c in columns])
    for row in rows:
        writer.writerow([_plain(row.get(c.key), c.kind) for c in columns])
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def to_xlsx(columns: list[Column], rows: list[dict], sheet_title: str) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_title[:31]
    sheet.append([c.title for c in columns])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="E8F1F0")
        cell.alignment = Alignment(vertical="center")
    for row in rows:
        values = []
        for c in columns:
            value = row.get(c.key)
            if isinstance(value, datetime):
                value = value.date()
            if value is None:
                values.append(None)
            elif c.kind == "money" and value != "":
                values.append(float(value))
            elif c.kind in {"date", "int"} or isinstance(value, (int, float, date)):
                values.append(value)
            else:
                values.append(safe_text(str(value)))
        sheet.append(values)
    for index, c in enumerate(columns, start=1):
        letter = get_column_letter(index)
        sheet.column_dimensions[letter].width = c.width
        for cell in sheet[letter][1:]:
            if c.kind == "date":
                cell.number_format = "DD-MM-YYYY"
            elif c.kind == "money":
                cell.number_format = "#,##0.00"
            elif c.kind == "text":
                cell.number_format = "@"
        if c.choices:
            rule = DataValidation(
                type="list", formula1='"' + ",".join(c.choices) + '"', allow_blank=True
            )
            sheet.add_data_validation(rule)
            rule.add(f"{letter}2:{letter}2000")
    sheet.freeze_panes = "A2"
    if rows:
        sheet.auto_filter.ref = sheet.dimensions
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def file_response(
    columns: list[Column], rows: list[dict], *, name: str, file_type: str, sheet: str = "Data"
) -> HttpResponse:
    if file_type == "csv":
        content, content_type, extension = to_csv(columns, rows), "text/csv; charset=utf-8", "csv"
    else:
        content, content_type, extension = to_xlsx(columns, rows, sheet), XLSX_TYPE, "xlsx"
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{name}.{extension}"'
    response["Cache-Control"] = "no-store"
    return response
