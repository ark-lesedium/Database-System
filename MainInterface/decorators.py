from functools import wraps
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required

def no_cache(view_func):
    """
    Decorator to prevent caching of authenticated pages
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)
        
        # Add no-cache headers
        if isinstance(response, HttpResponse):
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            response['X-Frame-Options'] = 'DENY'
            response['X-Content-Type-Options'] = 'nosniff'
        
        return response
    return wrapper

def secure_view(view_func):
    """
    Combined decorator for secure authenticated views
    """
    @wraps(view_func)
    @login_required
    @no_cache
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return wrapper
