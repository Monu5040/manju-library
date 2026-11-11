from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from accounts.permissions import AdminArea
from audit import services as audit
from audit.mixins import AuditedViewSetMixin

from .branching import BranchScopedMixin
from .models import Branch, Plan, Seat, Shift
from .serializers import (
    BranchSerializer,
    PlanSerializer,
    SeatRangeSerializer,
    SeatSerializer,
    ShiftSerializer,
)


class BranchViewSet(
    AuditedViewSetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    """Branch settings. Staff can read them; only the Super Admin changes them."""

    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [AdminArea]
    pagination_class = None
    audit_entity = "branch"


class SetupViewSet(BranchScopedMixin, AuditedViewSetMixin, ModelViewSet):
    """Shared base for the setup lists: small, so not paginated; Super Admin edits them."""

    permission_classes = [AdminArea]
    pagination_class = None


class ShiftViewSet(SetupViewSet):
    queryset = Shift.objects.all()
    serializer_class = ShiftSerializer
    audit_entity = "shift"


class SeatViewSet(SetupViewSet):
    queryset = Seat.objects.all()
    serializer_class = SeatSerializer
    audit_entity = "seat"

    @action(detail=False, methods=["post"], url_path="add-range")
    def add_range(self, request):
        """Create seats first..last (for example 1 to 51), skipping numbers that exist."""
        serializer = SeatRangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        branch = self.get_branch()
        existing = set(Seat.objects.filter(branch=branch).values_list("number", flat=True))
        created = [
            Seat.objects.create(branch=branch, number=str(n))
            for n in range(
                serializer.validated_data["first"], serializer.validated_data["last"] + 1
            )
            if str(n) not in existing
        ]
        audit.record(
            request,
            "seat.range_added",
            entity="seat",
            metadata={"created": [s.number for s in created]},
        )
        return Response(
            {"created": len(created), "seats": SeatSerializer(created, many=True).data},
            status=status.HTTP_201_CREATED,
        )


class PlanViewSet(SetupViewSet):
    queryset = Plan.objects.select_related("shift")
    serializer_class = PlanSerializer
    audit_entity = "plan"
