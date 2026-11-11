"""Analytics API, for the Super Admin only: the page's numbers, and every table as a file."""

from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsSuperAdmin
from audit import services as audit
from core.exports import Column, download, file_response, to_xlsx_book
from ledger.services import parse_range
from library.branching import current_branch

from .services import report

MAX_DAYS = 10 * 366
STATE_LABELS = {"taken": "Taken", "partly": "Part", "free": "Free"}


def load(request) -> dict:
    start, end = parse_range(request.query_params)
    grain = request.query_params.get("grain")
    if (end - start).days >= MAX_DAYS:
        raise ValidationError({"from": "Pick a range of at most ten years."})
    if grain == "day" and (end - start).days > 366:
        raise ValidationError({"grain": "Show days for ranges up to a year; use months."})
    return report(current_branch(request), start, end, grain)


class AnalyticsView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        return Response(load(request))


def tables(data: dict) -> dict[str, tuple[str, list[Column], list[dict]]]:
    """Every analytics table, keyed by section, as (sheet title, columns, rows)."""
    k = data["kpis"]
    previous = f"Previous period ({data['previous']['from']:%d-%m-%Y} to "
    previous += f"{data['previous']['to']:%d-%m-%Y})"
    kpi_rows = [
        ("Income (fees and other income)", k["income"]),
        ("Fees collected", k["fees"]),
        ("Expenses", k["expenses"]),
        ("Profit", k["profit"]),
        ("New admissions", k["new_admissions"]),
        (f"Active members on {data['as_of']:%d-%m-%Y}", k["active_members"]),
        ("Occupancy, % of seat-hours sold", k["occupancy_percent"]),
        (f"Seats in use (of {k['seats_in_use']['of']})", k["seats_in_use"]),
        ("Dues outstanding today", k["outstanding_dues"]),
        ("Memberships ending in the next 7 days", k["expiring_in_7_days"]),
    ]
    occupancy = data["occupancy"]
    shift_columns = [
        Column(f"shift_{s['id']}", f"{s['name']} ({s['time_label']})", "text", 18)
        for s in occupancy["shifts"]
    ]
    grid_rows = [
        {
            "seat": row["seat"],
            **{
                col.key: STATE_LABELS[state]
                for col, state in zip(shift_columns, row["cells"], strict=True)
            },
        }
        for row in occupancy["grid"]
    ]
    r = data["retention"]
    mix = data["mix"]
    collections = data["collections"]
    return {
        "kpis": (
            "Key numbers",
            [
                Column("metric", "Measure", "text", 40),
                Column("value", "This period", "number", 14),
                Column("previous", previous, "number", 34),
            ],
            [
                {"metric": m, "value": v["value"], "previous": v.get("previous")}
                for m, v in kpi_rows
            ],
        ),
        "revenue": (
            "Income and expenses",
            [
                Column("label", "Period", "text", 14),
                Column("fees", "Fees", "money", 13),
                Column("other_income", "Other Income", "money", 13),
                Column("income", "Total Income", "money", 13),
                Column("expenses", "Expenses", "money", 13),
                Column("profit", "Profit", "money", 13),
            ],
            data["revenue"],
        ),
        "occupancy": (
            "Occupancy",
            [Column("seat", "Seat", "text", 8), *shift_columns],
            grid_rows,
        ),
        "free_slots": (
            "Free slots",
            [
                Column("name", "Shift", "text", 18),
                Column("time_label", "Time", "text", 22),
                Column("free", "Free Seats", "int", 11),
                Column("seats", "Seat Numbers", "text", 50),
                Column("partly", "Partly Booked", "int", 14),
                Column("taken", "Taken", "int", 8),
            ],
            [{**s, "seats": ", ".join(s["free_seats"])} for s in occupancy["shifts"]],
        ),
        "renewals": (
            "Renewals",
            [Column("measure", "Measure", "text", 52), Column("value", "Value", "number", 10)],
            [
                {"measure": "Memberships that ended", "value": r["ended"]},
                {"measure": "Renewed within 15 days", "value": r["renewed"]},
                {"measure": "Left", "value": r["left"]},
                {"measure": "Undecided (ended less than 15 days ago)", "value": r["undecided"]},
                {"measure": "Renewal rate, %", "value": r["renewal_rate"]},
                {
                    "measure": "Average stay of those who left, months",
                    "value": r["average_stay_months"],
                },
            ],
        ),
        "cohorts": (
            "Cohorts",
            [
                Column("label", "Joined In", "text", 12),
                Column("joined", "Students Joined", "int", 16),
                Column("still_members", "Still Members", "int", 14),
                Column("percent", "% Still Members", "int", 16),
            ],
            r["cohorts"],
        ),
        "mix": (
            "Member mix",
            [
                Column("group", "By", "text", 12),
                Column("label", "Group", "text", 24),
                Column("count", "Members", "int", 10),
            ],
            [
                {"group": group, **row}
                for group, key in (
                    ("Shift", "by_shift"),
                    ("Plan", "by_plan"),
                    ("Gender", "by_gender"),
                )
                for row in mix[key]
            ],
        ),
        "dues": (
            "Dues by age",
            [
                Column("label", "Unpaid For", "text", 14),
                Column("amount", "Amount Due", "money", 13),
                Column("count", "Memberships", "int", 13),
            ],
            collections["dues_by_age"],
        ),
        "modes": (
            "Payment modes",
            [
                Column("label", "Paid By", "text", 16),
                Column("amount", "Amount", "money", 13),
                Column("count", "Payments", "int", 10),
            ],
            collections["payment_modes"],
        ),
    }


class AnalyticsExportView(APIView):
    """?section=kpis|revenue|occupancy|free_slots|renewals|cohorts|mix|dues|modes|all."""

    permission_classes = [IsSuperAdmin]

    def get(self, request):
        section = request.query_params.get("section", "all")
        file_type = request.query_params.get("file_type", "xlsx")
        if file_type not in {"xlsx", "csv"}:
            raise ValidationError({"file_type": "Choose xlsx or csv."})
        data = load(request)
        available = tables(data)
        if section != "all" and section not in available:
            raise ValidationError({"section": f"Choose one of: {', '.join(available)}, all."})
        if section == "all" and file_type == "csv":
            raise ValidationError({"file_type": "A CSV file holds one table. Use Excel for all."})
        audit.record(
            request,
            "export.analytics",
            entity="analytics",
            metadata={"section": section, "from": str(data["from"]), "to": str(data["to"])},
        )
        name = f"analytics-{section}-{data['from']:%Y-%m-%d}-to-{data['to']:%Y-%m-%d}"
        if section == "all":
            return download(to_xlsx_book(list(available.values())), name=name, file_type="xlsx")
        title, columns, rows = available[section]
        return file_response(columns, rows, name=name, file_type=file_type, sheet=title)
