"""Which branch a request works on. One branch today; the header allows more later."""

from rest_framework.exceptions import NotFound

from .models import Branch


def current_branch(request) -> Branch:
    branch_id = request.headers.get("X-Branch-Id") or request.query_params.get("branch")
    branches = Branch.objects.filter(is_active=True)
    if branch_id:
        branch = branches.filter(pk=branch_id).first() if str(branch_id).isdigit() else None
    else:
        branch = branches.order_by("id").first()
    if branch is None:
        raise NotFound("No active branch is set up.")
    return branch


class BranchScopedMixin:
    """Limits a view to the current branch and stamps new records with it."""

    def get_branch(self) -> Branch:
        if not hasattr(self, "_branch"):
            self._branch = current_branch(self.request)
        return self._branch

    def get_queryset(self):
        return super().get_queryset().filter(branch=self.get_branch())

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["branch"] = self.get_branch()
        return context

    def get_save_kwargs(self) -> dict:
        return {"branch": self.get_branch()}
