# Announcement Management Views
@login_required
def manage_announcements_view(request):
    """Manage announcements (lecturer and admin only)"""
    try:
        if request.user.userprofile.user_type not in ['lecturer', 'admin']:
            messages.error(request, 'Access denied. Lecturer or admin access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    # Get announcements created by the current user or all if admin
    if request.user.userprofile.user_type == 'admin':
        announcements = Announcement.objects.all().select_related('author', 'course').order_by('-created_at')
    else:
        announcements = Announcement.objects.filter(author=request.user).select_related('course').order_by('-created_at')
    
    # Apply filters
    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    audience_filter = request.GET.get('audience', '')
    
    if status_filter:
        if status_filter == 'active':
            announcements = announcements.filter(is_active=True)
        elif status_filter == 'inactive':
            announcements = announcements.filter(is_active=False)
        elif status_filter == 'pinned':
            announcements = announcements.filter(is_pinned=True)
        elif status_filter == 'expired':
            announcements = announcements.filter(expires_at__lt=timezone.now())
    
    if priority_filter:
        announcements = announcements.filter(priority=priority_filter)
    
    if audience_filter:
        announcements = announcements.filter(audience=audience_filter)
    
    # Calculate statistics
    total_announcements = Announcement.objects.filter(author=request.user).count() if request.user.userprofile.user_type != 'admin' else Announcement.objects.count()
    active_announcements = announcements.filter(is_active=True).count()
    pinned_announcements = announcements.filter(is_pinned=True).count()
    expired_announcements = announcements.filter(expires_at__lt=timezone.now()).count()
    
    context = {
        'announcements': announcements,
        'total_announcements': total_announcements,
        'active_announcements': active_announcements,
        'pinned_announcements': pinned_announcements,
        'expired_announcements': expired_announcements,
        'selected_status': status_filter,
        'selected_priority': priority_filter,
        'selected_audience': audience_filter,
        'priority_choices': Announcement.PRIORITY_CHOICES,
        'audience_choices': Announcement.AUDIENCE_CHOICES,
    }
    
    return render(request, 'MainInterface/manage_announcements.html', context)

@login_required
def create_announcement_view(request):
    """Create a new announcement (lecturer and admin only)"""
    try:
        if request.user.userprofile.user_type not in ['lecturer', 'admin']:
            messages.error(request, 'Access denied. Lecturer or admin access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    # Get lecturer's courses for course-specific announcements
    user_courses = []
    if request.user.userprofile.user_type == 'lecturer':
        user_courses = Course.objects.filter(lecturer=request.user.userprofile, is_active=True)
    elif request.user.userprofile.user_type == 'admin':
        user_courses = Course.objects.filter(is_active=True)
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        priority = request.POST.get('priority', 'medium')
        audience = request.POST.get('audience', 'all')
        course_id = request.POST.get('course', '').strip()
        is_pinned = request.POST.get('is_pinned') == 'on'
        expires_at = request.POST.get('expires_at', '').strip()
        
        # Validation
        if not all([title, content]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'MainInterface/create_announcement.html', {
                'user_courses': user_courses,
                'priority_choices': Announcement.PRIORITY_CHOICES,
                'audience_choices': Announcement.AUDIENCE_CHOICES,
            })
        
        # Validate course selection for course-specific announcements
        course = None
        if audience == 'course_specific':
            if not course_id:
                messages.error(request, 'Please select a course for course-specific announcements.')
                return render(request, 'MainInterface/create_announcement.html', {
                    'user_courses': user_courses,
                    'priority_choices': Announcement.PRIORITY_CHOICES,
                    'audience_choices': Announcement.AUDIENCE_CHOICES,
                })
            try:
                if request.user.userprofile.user_type == 'lecturer':
                    course = Course.objects.get(id=course_id, lecturer=request.user.userprofile)
                else:
                    course = Course.objects.get(id=course_id)
            except Course.DoesNotExist:
                messages.error(request, 'Invalid course selected.')
                return render(request, 'MainInterface/create_announcement.html', {
                    'user_courses': user_courses,
                    'priority_choices': Announcement.PRIORITY_CHOICES,
                    'audience_choices': Announcement.AUDIENCE_CHOICES,
                })
        
        # Parse expiration date
        expires_at_obj = None
        if expires_at:
            try:
                from django.utils.dateparse import parse_datetime
                from django.utils import timezone as django_timezone
                from datetime import datetime
                
                expires_at_obj = datetime.strptime(expires_at, '%Y-%m-%dT%H:%M')
                expires_at_obj = django_timezone.make_aware(expires_at_obj)
                
                if expires_at_obj <= timezone.now():
                    messages.error(request, 'Expiration date must be in the future.')
                    return render(request, 'MainInterface/create_announcement.html', {
                        'user_courses': user_courses,
                        'priority_choices': Announcement.PRIORITY_CHOICES,
                        'audience_choices': Announcement.AUDIENCE_CHOICES,
                    })
            except ValueError:
                messages.error(request, 'Invalid expiration date format.')
                return render(request, 'MainInterface/create_announcement.html', {
                    'user_courses': user_courses,
                    'priority_choices': Announcement.PRIORITY_CHOICES,
                    'audience_choices': Announcement.AUDIENCE_CHOICES,
                })
        
        try:
            # Create announcement
            announcement = Announcement.objects.create(
                title=title,
                content=content,
                author=request.user,
                priority=priority,
                audience=audience,
                course=course,
                is_pinned=is_pinned,
                expires_at=expires_at_obj
            )
            
            messages.success(request, f'Announcement "{title}" has been created successfully!')
            return redirect('manage_announcements')
            
        except Exception as e:
            messages.error(request, f'An error occurred while creating the announcement: {str(e)}')
    
    context = {
        'user_courses': user_courses,
        'priority_choices': Announcement.PRIORITY_CHOICES,
        'audience_choices': Announcement.AUDIENCE_CHOICES,
    }
    
    return render(request, 'MainInterface/create_announcement.html', context)

@login_required
def edit_announcement_view(request, announcement_id):
    """Edit an existing announcement"""
    try:
        if request.user.userprofile.user_type not in ['lecturer', 'admin']:
            messages.error(request, 'Access denied. Lecturer or admin access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    # Get announcement (must be created by current user unless admin)
    if request.user.userprofile.user_type == 'admin':
        announcement = get_object_or_404(Announcement, id=announcement_id)
    else:
        announcement = get_object_or_404(Announcement, id=announcement_id, author=request.user)
    
    # Get lecturer's courses for course-specific announcements
    user_courses = []
    if request.user.userprofile.user_type == 'lecturer':
        user_courses = Course.objects.filter(lecturer=request.user.userprofile, is_active=True)
    elif request.user.userprofile.user_type == 'admin':
        user_courses = Course.objects.filter(is_active=True)
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        priority = request.POST.get('priority', 'medium')
        audience = request.POST.get('audience', 'all')
        course_id = request.POST.get('course', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        is_pinned = request.POST.get('is_pinned') == 'on'
        expires_at = request.POST.get('expires_at', '').strip()
        
        # Validation
        if not all([title, content]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'MainInterface/edit_announcement.html', {
                'announcement': announcement,
                'user_courses': user_courses,
                'priority_choices': Announcement.PRIORITY_CHOICES,
                'audience_choices': Announcement.AUDIENCE_CHOICES,
            })
        
        # Validate course selection for course-specific announcements
        course = None
        if audience == 'course_specific':
            if not course_id:
                messages.error(request, 'Please select a course for course-specific announcements.')
                return render(request, 'MainInterface/edit_announcement.html', {
                    'announcement': announcement,
                    'user_courses': user_courses,
                    'priority_choices': Announcement.PRIORITY_CHOICES,
                    'audience_choices': Announcement.AUDIENCE_CHOICES,
                })
            try:
                if request.user.userprofile.user_type == 'lecturer':
                    course = Course.objects.get(id=course_id, lecturer=request.user.userprofile)
                else:
                    course = Course.objects.get(id=course_id)
            except Course.DoesNotExist:
                messages.error(request, 'Invalid course selected.')
                return render(request, 'MainInterface/edit_announcement.html', {
                    'announcement': announcement,
                    'user_courses': user_courses,
                    'priority_choices': Announcement.PRIORITY_CHOICES,
                    'audience_choices': Announcement.AUDIENCE_CHOICES,
                })
        
        # Parse expiration date
        expires_at_obj = None
        if expires_at:
            try:
                from django.utils.dateparse import parse_datetime
                from django.utils import timezone as django_timezone
                from datetime import datetime
                
                expires_at_obj = datetime.strptime(expires_at, '%Y-%m-%dT%H:%M')
                expires_at_obj = django_timezone.make_aware(expires_at_obj)
            except ValueError:
                messages.error(request, 'Invalid expiration date format.')
                return render(request, 'MainInterface/edit_announcement.html', {
                    'announcement': announcement,
                    'user_courses': user_courses,
                    'priority_choices': Announcement.PRIORITY_CHOICES,
                    'audience_choices': Announcement.AUDIENCE_CHOICES,
                })
        
        try:
            # Update announcement
            announcement.title = title
            announcement.content = content
            announcement.priority = priority
            announcement.audience = audience
            announcement.course = course
            announcement.is_active = is_active
            announcement.is_pinned = is_pinned
            announcement.expires_at = expires_at_obj
            announcement.save()
            
            messages.success(request, f'Announcement "{title}" has been updated successfully!')
            return redirect('manage_announcements')
            
        except Exception as e:
            messages.error(request, f'An error occurred while updating the announcement: {str(e)}')
    
    context = {
        'announcement': announcement,
        'user_courses': user_courses,
        'priority_choices': Announcement.PRIORITY_CHOICES,
        'audience_choices': Announcement.AUDIENCE_CHOICES,
    }
    
    return render(request, 'MainInterface/edit_announcement.html', context)

@login_required
def delete_announcement_view(request, announcement_id):
    """Delete an announcement"""
    try:
        if request.user.userprofile.user_type not in ['lecturer', 'admin']:
            messages.error(request, 'Access denied. Lecturer or admin access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    # Get announcement (must be created by current user unless admin)
    if request.user.userprofile.user_type == 'admin':
        announcement = get_object_or_404(Announcement, id=announcement_id)
    else:
        announcement = get_object_or_404(Announcement, id=announcement_id, author=request.user)
    
    if request.method == 'POST':
        announcement_title = announcement.title
        announcement.delete()
        messages.success(request, f'Announcement "{announcement_title}" has been deleted successfully!')
        return redirect('manage_announcements')
    
    context = {
        'announcement': announcement,
    }
    
    return render(request, 'MainInterface/delete_announcement_confirm.html', context)
