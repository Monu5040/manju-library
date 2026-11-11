"""
Read an uploaded spreadsheet (.xlsx, .xls or .csv) into rows of cell values.

The format comes from the file's bytes, not its name. CSV encoding and separator are
detected (Excel writes UTF-8 with or without a BOM, Windows-1252 or UTF-16 depending on
how the file was saved).
"""

import csv
import io
import zipfile
from dataclasses import dataclass, field
from datetime import datetime

import openpyxl
import xlrd
from charset_normalizer import from_bytes

MAX_ROWS = 10_000
MAX_UNZIPPED_BYTES = 100 * 1024 * 1024  # refuse "zip bombs" disguised as .xlsx


class UnreadableFile(ValueError):
    pass


@dataclass
class Table:
    file_format: str
    sheets: list[str]
    sheet: str
    rows: list[list] = field(default_factory=list)
    encoding: str = ""
    delimiter: str = ""


def _trim(rows: list[list]) -> list[list]:
    """Drop fully empty trailing rows and columns (Excel sheets often carry thousands)."""

    def blank(value) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())

    while rows and all(blank(v) for v in rows[-1]):
        rows.pop()
    width = max((i + 1 for row in rows for i, v in enumerate(row) if not blank(v)), default=0)
    return [list(row[:width]) + [None] * (width - len(row[:width])) for row in rows]


def _read_xlsx(content: bytes, sheet: str | None) -> Table:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if sum(info.file_size for info in archive.infolist()) > MAX_UNZIPPED_BYTES:
                raise UnreadableFile("This file is too large once unpacked.")
    except zipfile.BadZipFile as exc:
        raise UnreadableFile("This does not look like a valid .xlsx file.") from exc
    workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    try:
        names = workbook.sheetnames
        chosen = sheet if sheet in names else names[0]
        rows = []
        for row in workbook[chosen].iter_rows(values_only=True):
            rows.append(list(row))
            if len(rows) > MAX_ROWS + 50:
                break
    finally:
        workbook.close()
    return Table("xlsx", names, chosen, _trim(rows))


def _read_xls(content: bytes, sheet: str | None) -> Table:
    try:
        book = xlrd.open_workbook(file_contents=content)
    except Exception as exc:  # xlrd raises several error types for damaged files
        raise UnreadableFile("This .xls file could not be read.") from exc
    names = book.sheet_names()
    chosen = sheet if sheet in names else names[0]
    sh = book.sheet_by_name(chosen)
    rows = []
    for r in range(min(sh.nrows, MAX_ROWS + 50)):
        row = []
        for c in range(sh.ncols):
            cell = sh.cell(r, c)
            if cell.ctype == xlrd.XL_CELL_DATE:
                row.append(xlrd.xldate_as_datetime(cell.value, book.datemode))
            elif cell.ctype == xlrd.XL_CELL_NUMBER and float(cell.value).is_integer():
                row.append(int(cell.value))
            else:
                row.append(cell.value if cell.value != "" else None)
        rows.append(row)
    return Table("xls", names, chosen, _trim(rows))


def _decode(content: bytes) -> tuple[str, str]:
    for bom, encoding in (
        (b"\xef\xbb\xbf", "utf-8-sig"),
        (b"\xff\xfe", "utf-16"),
        (b"\xfe\xff", "utf-16"),
    ):
        if content.startswith(bom):
            return content.decode(encoding), encoding
    try:
        return content.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        best = from_bytes(content).best()
        if best is None:
            raise UnreadableFile("The text encoding of this CSV could not be worked out.") from None
        return str(best), best.encoding


def _read_csv(content: bytes) -> Table:
    text, encoding = _decode(content)
    sample = text[:8192]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = ","
    rows = []
    for row in csv.reader(io.StringIO(text), delimiter=delimiter):
        rows.append([value if value != "" else None for value in row])
        if len(rows) > MAX_ROWS + 50:
            break
    return Table("csv", ["CSV"], "CSV", _trim(rows), encoding=encoding, delimiter=delimiter)


def read_table(content: bytes, sheet: str | None = None) -> Table:
    if content.startswith(b"PK\x03\x04"):
        table = _read_xlsx(content, sheet)
    elif content.startswith(b"\xd0\xcf\x11\xe0"):
        table = _read_xls(content, sheet)
    else:
        table = _read_csv(content)
    if len(table.rows) > MAX_ROWS + 50:
        raise UnreadableFile(
            f"This sheet has more than {MAX_ROWS:,} rows. Split it into smaller files."
        )
    return table


def display(value) -> str:
    """How a cell reads to a person, for previews and error files."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d-%m-%Y")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()
