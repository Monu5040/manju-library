"""
Student portal API (/api/portal/...). A login (one mobile number) can own several student
profiles, for example siblings; every query is limited to the profiles of that login.
"""

from django.db.models import Prefetch
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from accounts.permissions import AdminArea, IsStudent
from audit import services as audit
from audit.mixins import AuditedViewSetMixin, snapshot
from billing.models import Payment
from library.branching import BranchScopedMixin
from library.models import Plan, Shift
from members.models import Membership, Student

from .models import Notice
from .serializers import (
    NoticeSerializer,
    PortalMembershipSerializer,
    PortalNoticeSerializer,
    PortalPaymentSerializer,
    PortalPlanSerializer,
    PortalProfileUpdateSerializer,
    PortalShiftSerializer,
    PortalStudentSerializer,
)


def my_students(user):
    memberships = Membership.objects.with_totals().select_related("seat", "shift", "plan")
    return (
        Student.objects.filter(account=user)
        .select_related("branch")
        .prefetch_related(Prefetch("memberships", queryset=memberships.order_by("-end_date")))
        .order_by("roll_no")
    )


def my_student(user, pk) -> Student:
    student = my_students(user).filter(pk=pk).first()
    if student is None:
        raise Http404
    return student


class PortalHomeView(APIView):
    """Everything the dashboard needs in one call."""

    permission_classes = [IsStudent]

    def get(self, request):
        students = list(my_students(request.user))
        branch = students[0].branch if students else None
        library = None
        notices, shifts, plans = [], [], []
        if branch is not None:
            library = {"name": branch.name, "address": branch.address, "phone": branch.phone}
            notices = PortalNoticeSerializer(
                Notice.objects.filter(branch=branch).live(), many=True
            ).data
            shifts = PortalShiftSerializer(
                Shift.objects.filter(branch=branch, is_active=True), many=True
            ).data
            plans = PortalPlanSerializer(
                Plan.objects.filter(branch=branch, is_active=True).select_related("shift"),
                many=True,
            ).data
        return Response(
            {
                "profiles": PortalStudentSerializer(students, many=True).data,
                "library": library,
                "notices": notices,
                "shifts": shifts,
                "plans": plans,
            }
        )


class PortalStudentView(APIView):
    permission_classes = [IsStudent]

    def get(self, request, pk):
        student = my_student(request.user, pk)
        payments = Payment.objects.filter(student=student).order_by("-paid_on", "-receipt_no")
        return Response(
            {
                **PortalStudentSerializer(student).data,
                "memberships": PortalMembershipSerializer(
                    [
                        m
                        for m in student.memberships.all()
                        if m.status != Membership.Status.CANCELLED
                    ],
                    many=True,
                ).data,
                "payments": PortalPaymentSerializer(payments, many=True).data,
            }
        )

    def patch(self, request, pk):
        student = my_student(request.user, pk)
        before = snapshot(student)
        serializer = PortalProfileUpdateSerializer(student, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        changed = {
            k: v for k, v in snapshot(student).items() if before.get(k) != v and k != "updated_at"
        }
        if changed:
            audit.record(
                request,
                "portal.profile_updated",
                entity="student",
                entity_id=student.pk,
                before={k: before.get(k) for k in changed},
                after=changed,
            )
        return Response(PortalStudentSerializer(my_student(request.user, pk)).data)


class PortalReceiptView(APIView):
    permission_classes = [IsStudent]

    def get(self, request, pk):
        payment = (
            Payment.objects.filter(pk=pk, student__account=request.user)
            .select_related("student", "branch")
            .first()
        )
        if payment is None:
            raise Http404
        branch = payment.branch
        return Response(
            {
                **PortalPaymentSerializer(payment).data,
                "student_name": payment.student.full_name,
                "roll_no": payment.student.roll_no,
                "library": {"name": branch.name, "address": branch.address, "phone": branch.phone},
            },
            status=status.HTTP_200_OK,
        )


class NoticeViewSet(BranchScopedMixin, AuditedViewSetMixin, ModelViewSet):
    """Admin side: staff post and edit notices; only the Super Admin deletes them."""

    queryset = Notice.objects.select_related("created_by")
    serializer_class = NoticeSerializer
    permission_classes = [AdminArea]
    staff_actions = {"create", "update", "partial_update"}
    pagination_class = None
    audit_entity = "notice"

    def get_save_kwargs(self) -> dict:
        return {**super().get_save_kwargs(), "created_by": self.request.user}

    def perform_update(self, serializer):
        before = snapshot(serializer.instance)
        instance = serializer.save()
        after = snapshot(instance)
        changed = [k for k in after if after[k] != before.get(k) and k != "updated_at"]
        if changed:
            self.record_audit(
                "updated",
                instance,
                before={k: before.get(k) for k in changed},
                after={k: after[k] for k in changed},
            )
