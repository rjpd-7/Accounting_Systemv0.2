from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone

from .models import UserProfile


class ForcePasswordChangeMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        super().__init__(get_response)
        self.allowed_view_names = {
            'AccountingSystem:force_password_change',
            'AccountingSystem:change_own_password',
            'AccountingSystem:logout',
        }

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated:
            return None

        resolver_match = getattr(request, 'resolver_match', None)
        if resolver_match and resolver_match.view_name in self.allowed_view_names:
            return None

        profile, _ = UserProfile.objects.get_or_create(user=request.user, defaults={'role': 'student'})
        if not profile.requires_password_change:
            return None

        if profile.temporary_password_expires_at and timezone.now() >= profile.temporary_password_expires_at:
            request.user.set_unusable_password()
            request.user.save(update_fields=['password'])
            profile.temporary_password_expires_at = None
            profile.requires_password_change = False
            profile.save(update_fields=['temporary_password_expires_at', 'requires_password_change'])
            logout(request)
            messages.error(request, 'Your temporary password expired before you changed it. Request a new temporary password.')
            return redirect('AccountingSystem:login_view')

        if resolver_match and resolver_match.view_name != 'AccountingSystem:force_password_change':
            return redirect('AccountingSystem:force_password_change')

        return None