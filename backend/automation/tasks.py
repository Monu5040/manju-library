"""
Scheduled jobs (Celery Beat; times are India time, see CELERY_BEAT_SCHEDULE):

- run_reminders            hourly 8 AM–8 PM: tidy, add today's reminders, send SMS if set up
- mark_students_left       2:30 AM, only where a branch has turned it on
- purge_old_import_data    2:40 AM: uploaded files and rows read from them, after the undo window
- clear_expired_sessions   2:50 AM
"""

import re
from datetime import timedelta

from celery import shared_task
from django.core.management import call_command
from django.db.models import Exists, OuterRef
from django.utils import timezone

from audit import services as audit
from imports.models import ImportJob, ImportRow
from library.models import Branch
from members.models import Membership, Student, WaitlistEntry

from .models import AutomationSettings
from .monitoring import tracked
from .services import build_reminders, send_by_sms, tidy_reminders

IMPORT_DATA_DAYS = 7  # the import undo window
AADHAAR_IN_WARNING = re.compile(r"Aadhaar '[^']*'")


@shared_task
@tracked("reminders")
def run_reminders() -> dict:
    summary = {}
    for branch in Branch.objects.filter(is_active=True):
        summary[branch.code] = {
            "closed": tidy_reminders(branch),
            "created": build_reminders(branch),
            **send_by_sms(branch),
        }
    return summary


@shared_task
@tracked("mark-students-left")
def mark_students_left() -> dict:
    """
    Students with no membership for the branch's chosen number of days become "left", so
    lists of current students stay accurate. Anyone waiting for a seat is kept. A new
    membership makes a student current again.
    """
    today = timezone.localdate()
    marked = 0
    for conf in AutomationSettings.objects.filter(
        mark_left_after_days__gt=0, branch__is_active=True
    ).select_related("branch"):
        cutoff = today - timedelta(days=conf.mark_left_after_days)
        recent = Membership.objects.not_cancelled().filter(
            student=OuterRef("pk"), end_date__gte=cutoff
        )
        waiting = WaitlistEntry.objects.filter(
            student=OuterRef("pk"), status=WaitlistEntry.Status.WAITING
        )
        students = Student.objects.filter(
            branch=conf.branch, status=Student.Status.ACTIVE, created_at__date__lt=cutoff
        ).filter(~Exists(recent), ~Exists(waiting))
        ids = list(students.values_list("pk", flat=True))
        if not ids:
            continue
        Student.objects.filter(pk__in=ids).update(status=Student.Status.LEFT)
        marked += len(ids)
        audit.record(
            None,
            "student.marked_left",
            entity="student",
            metadata={
                "branch": conf.branch.code,
                "students": ids,
                "rule": f"no membership for {conf.mark_left_after_days} days",
            },
        )
    return {"marked": marked}


@shared_task
@tracked("import-cleanup")
def purge_old_import_data() -> dict:
    """
    An uploaded sheet (with Aadhaar and mobile numbers) is only needed while an import can
    still be checked again or undone. After that the file and the rows read from it are
    deleted; the import's summary and row results stay.
    """
    cutoff = timezone.now() - timedelta(days=IMPORT_DATA_DAYS)
    jobs = ImportJob.objects.filter(created_at__lt=cutoff)
    purged = 0
    for job in jobs.exclude(content=None):
        job.content = None
        job.save(update_fields=["content"])
        purged += 1
    for row in ImportRow.objects.filter(job__in=jobs).exclude(raw={}, values={}):
        row.raw, row.values = {}, {}
        row.warnings = [AADHAAR_IN_WARNING.sub("Aadhaar (number removed)", w) for w in row.warnings]
        row.save(update_fields=["raw", "values", "warnings"])
    return {"files_deleted": purged}


@shared_task
@tracked("session-cleanup")
def clear_expired_sessions() -> dict:
    call_command("clearsessions")
    return {"done": True}
