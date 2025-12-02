from django.http import HttpResponse
from django.shortcuts import redirect
from functools import wraps

def unauthenticated_user(view_func):
    def wrapper_func(request, *args, **kwargs):

        return view_func(request, *args, **kwargs)
    
    return wrapper_func

def role_required(allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('AccountingSystem:login_view')
            profile = getattr(request.user, 'profile', None)
            if not profile or profile.role not in allowed_roles:
                return redirect('AccountingSystem:forbidden')   # create a simple forbidden page or change this
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator