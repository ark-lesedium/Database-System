from django.shortcuts import redirect
from django.contrib.auth import logout
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from django.contrib import messages
import time

class SessionTimeoutMiddleware:
    """
    Middleware to handle session timeout and automatic logout
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip timeout check for certain URLs
        exempt_urls = [
            reverse('login'),
            reverse('logout'),
            '/admin/',
            '/static/',
            '/media/',
        ]
        
        # Check if current path should be exempt from timeout
        is_exempt = any(request.path.startswith(url) for url in exempt_urls)
        
        if not is_exempt and request.user.is_authenticated:
            # Get current time
            current_time = time.time()
            
            # Get last activity time from session
            last_activity = request.session.get('last_activity')
            
            if last_activity:
                # Calculate time since last activity
                time_since_activity = current_time - last_activity
                
                # Check if session has expired
                session_timeout = getattr(settings, 'SESSION_COOKIE_AGE', 1800)
                
                if time_since_activity > session_timeout:
                    # Session has expired - logout user
                    logout(request)
                    messages.warning(request, 'Your session has expired due to inactivity. Please log in again.')
                    return redirect('login')
            
            # Update last activity time
            request.session['last_activity'] = current_time
            
            # Set session modified to True to ensure it gets saved
            request.session.modified = True

        response = self.get_response(request)
        return response


class SessionSecurityMiddleware:
    """
    Additional security middleware for session protection
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Prevent session fixation attacks
        if request.user.is_authenticated:
            # Check if this is a fresh login
            if not request.session.get('session_security_initialized'):
                # Cycle session key to prevent session fixation
                old_session_key = request.session.session_key
                request.session.cycle_key()
                request.session['session_security_initialized'] = True
                request.session['login_time'] = time.time()
                
        # Check for suspicious session activity
        if request.user.is_authenticated:
            # Store user agent to detect session hijacking
            current_user_agent = request.META.get('HTTP_USER_AGENT', '')
            stored_user_agent = request.session.get('user_agent')
            
            if stored_user_agent and stored_user_agent != current_user_agent:
                # Potential session hijacking - logout user
                logout(request)
                messages.error(request, 'Suspicious activity detected. Please log in again.')
                return redirect('login')
            
            # Store user agent for future comparison
            request.session['user_agent'] = current_user_agent

        response = self.get_response(request)
        return response
