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
from django.utils.http import content_disposition_header
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
    kind: str = "text"  # text | int | number | money | date
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
    writer.writerow([safe_text(c.title) for c in columns])
    for row in rows:
        writer.writerow([_plain(row.get(c.key), c.kind) for c in columns])
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def _fill_sheet(sheet, columns: list[Column], rows: list[dict]) -> None:
    sheet.append([safe_text(c.title) for c in columns])
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
            elif isinstance(value, str):
                # Text is never written as a formula, whatever the column's kind.
                try:
                    is_number = c.kind in {"money", "number"} and value != ""
                    values.append(float(value) if is_number else safe_text(value))
                except ValueError:
                    values.append(safe_text(value))
            elif c.kind in {"money", "number"}:
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


def to_xlsx(columns: list[Column], rows: list[dict], sheet_title: str) -> bytes:
    return to_xlsx_book([(sheet_title, columns, rows)])


def to_xlsx_book(sheets: list[tuple[str, list[Column], list[dict]]]) -> bytes:
    """One workbook with a sheet per table, for example every analytics section."""
    workbook = Workbook()
    workbook.remove(workbook.active)
    for title, columns, rows in sheets:
        _fill_sheet(workbook.create_sheet(title[:31]), columns, rows)
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def download(content: bytes, *, name: str, file_type: str) -> HttpResponse:
    content_type = "text/csv; charset=utf-8" if file_type == "csv" else XLSX_TYPE
    response = HttpResponse(content, content_type=content_type)
    # Escaped properly: names come from uploaded files and may hold quotes or Hindi.
    response["Content-Disposition"] = content_disposition_header(True, f"{name}.{file_type}")
    response["Cache-Control"] = "no-store"
    return response


def file_response(
    columns: list[Column], rows: list[dict], *, name: str, file_type: str, sheet: str = "Data"
) -> HttpResponse:
    if file_type == "csv":
        return download(to_csv(columns, rows), name=name, file_type="csv")
    return download(to_xlsx(columns, rows, sheet), name=name, file_type="xlsx")
