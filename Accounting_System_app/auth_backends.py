from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User
from .models import USN_Accounts
from django.contrib.auth.hashers import check_password

class USNAccountsBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        try:
            ua = USN_Accounts.objects.get(usn=username)
        except USN_Accounts.DoesNotExist:
            return None

        # adjust depending on how passwords are stored (hashed recommended)
        if ua.password and check_password(password, ua.password):
            user, _ = User.objects.get_or_create(username=username)
            if _:
                user.set_unusable_password()
                user.save()
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None