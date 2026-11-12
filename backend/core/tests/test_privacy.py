import json
import logging

import pytest

from core.logging import JsonFormatter

pytestmark = pytest.mark.django_db


def test_api_answers_are_never_cached(api, owner_api):
    response = owner_api.get("/api/admin/students/")
    assert "no-store" in response["Cache-Control"]
    assert "no-store" in api.get("/api/health/")["Cache-Control"]


def test_logs_keep_the_path_but_not_the_query(rf):
    request = rf.get("/api/admin/students/", {"q": "9876543210"})
    record = logging.makeLogRecord({"msg": "Not Found", "request": request, "status_code": 404})
    line = json.loads(JsonFormatter().format(record))
    assert line["request"] == "GET /api/admin/students/"
    assert "9876543210" not in json.dumps(line)


def test_exports_never_write_formulas_and_escape_file_names():
    import io

    from openpyxl import load_workbook

    from core.exports import Column, download, to_xlsx

    columns = [Column("n", "=HYPERLINK(1)", "int"), Column("d", "When", "date")]
    book = load_workbook(io.BytesIO(to_xlsx(columns, [{"n": "=1+1", "d": "Total"}], "S")))
    sheet = book.active
    assert sheet["A1"].value == "'=HYPERLINK(1)" and sheet["A2"].value == "'=1+1"
    assert sheet["B2"].value == "Total"
    response = download(b"x", name='errors-a"b माह', file_type="csv")
    assert 'filename="errors-a\\"b' not in response["Content-Disposition"]
    assert "filename*=utf-8''" in response["Content-Disposition"]
