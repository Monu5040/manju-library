from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

from .models import normalize_mobile


class EmailOrMobileBackend(ModelBackend):
    """
    Password login with either an email address or a mobile number. Students have no
    usable password, so this backend never lets them in; they use the SMS code flow.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        user_model = get_user_model()
        identifier = str(username).strip()
        if "@" in identifier:
            lookup = {"email__iexact": identifier}
        else:
            mobile = normalize_mobile(identifier)
            if not mobile:
                return None
            lookup = {"mobile": mobile}
        try:
            user = user_model.objects.get(**lookup)
        except user_model.DoesNotExist:
            # Run the hasher anyway so a missing account takes as long as a wrong password.
            user_model().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
