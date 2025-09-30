# Class Schedule Views
@login_required
def view_schedule_view(request):
    """View class schedule for both students and lecturers"""
    import calendar
    from datetime import datetime, timedelta
    
    # Get current date
    today = timezone.now().date()
    current_year = today.year
    current_month = today.month
    
    # Get year and month from query parameters
    year = int(request.GET.get('year', current_year))
    month = int(request.GET.get('month', current_month))
    
    # Initialize schedules variable
    schedules = ClassSchedule.objects.none()
    
    # Get schedules based on user type
    if hasattr(request.user, 'userprofile'):
        if request.user.userprofile.user_type == 'student':
            # Get schedules for courses the student is enrolled in
            enrolled_courses = Course.objects.filter(
                enrollments__student=request.user,
                enrollments__status='enrolled'
            )
            schedules = ClassSchedule.objects.filter(
                course__in=enrolled_courses,
                is_active=True,
                start_datetime__year=year,
                start_datetime__month=month
            ).select_related('course', 'lecturer').order_by('start_datetime')
            
        elif request.user.userprofile.user_type == 'lecturer':
            # Get schedules for courses the lecturer teaches
            lecturer_courses = Course.objects.filter(lecturer=request.user.userprofile)
            schedules = ClassSchedule.objects.filter(
                course__in=lecturer_courses,
                start_datetime__year=year,
                start_datetime__month=month
            ).select_related('course').order_by('start_datetime')
    
    # Create calendar
    cal = calendar.monthcalendar(year, month)
    month_name = calendar.month_name[month]
    
    # Navigation dates
    if month == 1:
        prev_month, prev_year = 12, year - 1
    else:
        prev_month, prev_year = month - 1, year
    
    if month == 12:
        next_month, next_year = 1, year + 1
    else:
        next_month, next_year = month + 1, year
    
    # Organize schedules by date for easy template access
    schedules_by_date = {}
    for schedule in schedules:
        schedule_date = schedule.start_datetime.date()
        if schedule_date.day not in schedules_by_date:
            schedules_by_date[schedule_date.day] = []
        schedules_by_date[schedule_date.day].append(schedule)
    
    # Get upcoming schedules (next 7 days)
    upcoming_schedules = ClassSchedule.objects.filter(
        start_datetime__gte=timezone.now(),
        start_datetime__lte=timezone.now() + timedelta(days=7),
        is_active=True
    )
    
    # Filter based on user type
    if hasattr(request.user, 'userprofile'):
        if request.user.userprofile.user_type == 'student':
            enrolled_courses = Course.objects.filter(
                enrollments__student=request.user,
                enrollments__status='enrolled'
            )
            upcoming_schedules = upcoming_schedules.filter(course__in=enrolled_courses)
        elif request.user.userprofile.user_type == 'lecturer':
            lecturer_courses = Course.objects.filter(lecturer=request.user.userprofile)
            upcoming_schedules = upcoming_schedules.filter(course__in=lecturer_courses)
    
    upcoming_schedules = upcoming_schedules.select_related('course', 'lecturer').order_by('start_datetime')[:5]
    
    context = {
        'calendar': cal,
        'year': year,
        'month': month,
        'month_name': month_name,
        'today': today,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'schedules_by_date': schedules_by_date,
        'upcoming_schedules': upcoming_schedules,
        'all_schedules': schedules,
    }
    
    return render(request, 'MainInterface/view_schedule.html', context)

@login_required
def manage_schedule_view(request):
    """Manage class schedules (lecturer only)"""
    try:
        if request.user.userprofile.user_type != 'lecturer':
            messages.error(request, 'Access denied. Lecturer access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    # Get lecturer's courses
    courses = Course.objects.filter(lecturer=request.user.userprofile, is_active=True)
    
    # Get lecturer's schedules
    schedules = ClassSchedule.objects.filter(
        lecturer=request.user.userprofile
    ).select_related('course').order_by('-start_datetime')
    
    # Apply filters
    course_filter = request.GET.get('course', '')
    status_filter = request.GET.get('status', '')
    
    if course_filter:
        schedules = schedules.filter(course__id=course_filter)
    
    if status_filter:
        if status_filter == 'active':
            schedules = schedules.filter(is_active=True, is_cancelled=False)
        elif status_filter == 'cancelled':
            schedules = schedules.filter(is_cancelled=True)
        elif status_filter == 'past':
            schedules = schedules.filter(end_datetime__lt=timezone.now())
        elif status_filter == 'upcoming':
            schedules = schedules.filter(start_datetime__gte=timezone.now(), is_active=True, is_cancelled=False)
    
    # Calculate statistics
    total_schedules = ClassSchedule.objects.filter(lecturer=request.user.userprofile).count()
    upcoming_schedules = ClassSchedule.objects.filter(
        lecturer=request.user.userprofile,
        start_datetime__gte=timezone.now(),
        is_active=True,
        is_cancelled=False
    ).count()
    cancelled_schedules = ClassSchedule.objects.filter(
        lecturer=request.user.userprofile,
        is_cancelled=True
    ).count()
    
    context = {
        'schedules': schedules,
        'courses': courses,
        'selected_course': course_filter,
        'selected_status': status_filter,
        'total_schedules': total_schedules,
        'upcoming_schedules': upcoming_schedules,
        'cancelled_schedules': cancelled_schedules,
    }
    
    return render(request, 'MainInterface/manage_schedule.html', context)

@login_required
def add_schedule_event_view(request):
    """Add a new class schedule event (lecturer only)"""
    try:
        if request.user.userprofile.user_type != 'lecturer':
            messages.error(request, 'Access denied. Lecturer access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    # Get lecturer's courses
    courses = Course.objects.filter(lecturer=request.user.userprofile, is_active=True)
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        course_id = request.POST.get('course')
        class_type = request.POST.get('class_type', 'lecture')
        start_datetime = request.POST.get('start_datetime', '').strip()
        end_datetime = request.POST.get('end_datetime', '').strip()
        location = request.POST.get('location', '').strip()
        is_online = request.POST.get('is_online') == 'on'
        meeting_url = request.POST.get('meeting_url', '').strip()
        max_attendees = request.POST.get('max_attendees', '').strip()
        required_materials = request.POST.get('required_materials', '').strip()
        notes = request.POST.get('notes', '').strip()
        
        # Validation
        if not all([title, course_id, start_datetime, end_datetime]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'MainInterface/add_schedule_event.html', {
                'courses': courses,
                'class_types': ClassSchedule.CLASS_TYPE_CHOICES
            })
        
        # Validate course belongs to lecturer
        try:
            course = Course.objects.get(id=course_id, lecturer=request.user.userprofile)
        except Course.DoesNotExist:
            messages.error(request, 'Invalid course selected.')
            return render(request, 'MainInterface/add_schedule_event.html', {
                'courses': courses,
                'class_types': ClassSchedule.CLASS_TYPE_CHOICES
            })
        
        # Parse datetime strings
        try:
            from django.utils.dateparse import parse_datetime
            from django.utils import timezone as django_timezone
            from datetime import datetime
            
            start_dt = datetime.strptime(start_datetime, '%Y-%m-%dT%H:%M')
            start_dt = django_timezone.make_aware(start_dt)
            
            end_dt = datetime.strptime(end_datetime, '%Y-%m-%dT%H:%M')
            end_dt = django_timezone.make_aware(end_dt)
            
            if end_dt <= start_dt:
                messages.error(request, 'End time must be after start time.')
                return render(request, 'MainInterface/add_schedule_event.html', {
                    'courses': courses,
                    'class_types': ClassSchedule.CLASS_TYPE_CHOICES
                })
        except ValueError:
            messages.error(request, 'Invalid datetime format.')
            return render(request, 'MainInterface/add_schedule_event.html', {
                'courses': courses,
                'class_types': ClassSchedule.CLASS_TYPE_CHOICES
            })
        
        # Validate max_attendees
        if max_attendees:
            try:
                max_attendees = int(max_attendees)
            except ValueError:
                messages.error(request, 'Maximum attendees must be a number.')
                return render(request, 'MainInterface/add_schedule_event.html', {
                    'courses': courses,
                    'class_types': ClassSchedule.CLASS_TYPE_CHOICES
                })
        else:
            max_attendees = None
        
        try:
            # Create schedule
            schedule = ClassSchedule.objects.create(
                title=title,
                description=description,
                course=course,
                lecturer=request.user.userprofile,
                class_type=class_type,
                start_datetime=start_dt,
                end_datetime=end_dt,
                location=location,
                is_online=is_online,
                meeting_url=meeting_url,
                max_attendees=max_attendees,
                required_materials=required_materials,
                notes=notes
            )
            
            messages.success(request, f'Class schedule "{title}" has been created successfully!')
            return redirect('manage_schedule')
            
        except Exception as e:
            messages.error(request, f'An error occurred while creating the schedule: {str(e)}')
    
    context = {
        'courses': courses,
        'class_types': ClassSchedule.CLASS_TYPE_CHOICES,
    }
    
    return render(request, 'MainInterface/add_schedule_event.html', context)

@login_required
def edit_schedule_event_view(request, schedule_id):
    """Edit a class schedule event (lecturer only)"""
    try:
        if request.user.userprofile.user_type != 'lecturer':
            messages.error(request, 'Access denied. Lecturer access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    schedule = get_object_or_404(ClassSchedule, id=schedule_id, lecturer=request.user.userprofile)
    
    # Get lecturer's courses
    courses = Course.objects.filter(lecturer=request.user.userprofile, is_active=True)
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        course_id = request.POST.get('course')
        class_type = request.POST.get('class_type', 'lecture')
        start_datetime = request.POST.get('start_datetime', '').strip()
        end_datetime = request.POST.get('end_datetime', '').strip()
        location = request.POST.get('location', '').strip()
        is_online = request.POST.get('is_online') == 'on'
        meeting_url = request.POST.get('meeting_url', '').strip()
        max_attendees = request.POST.get('max_attendees', '').strip()
        required_materials = request.POST.get('required_materials', '').strip()
        notes = request.POST.get('notes', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        is_cancelled = request.POST.get('is_cancelled') == 'on'
        cancellation_reason = request.POST.get('cancellation_reason', '').strip()
        
        # Validation
        if not all([title, course_id, start_datetime, end_datetime]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'MainInterface/edit_schedule_event.html', {
                'schedule': schedule,
                'courses': courses,
                'class_types': ClassSchedule.CLASS_TYPE_CHOICES
            })
        
        # Validate course belongs to lecturer
        try:
            course = Course.objects.get(id=course_id, lecturer=request.user.userprofile)
        except Course.DoesNotExist:
            messages.error(request, 'Invalid course selected.')
            return render(request, 'MainInterface/edit_schedule_event.html', {
                'schedule': schedule,
                'courses': courses,
                'class_types': ClassSchedule.CLASS_TYPE_CHOICES
            })
        
        # Parse datetime strings
        try:
            from django.utils.dateparse import parse_datetime
            from django.utils import timezone as django_timezone
            from datetime import datetime
            
            start_dt = datetime.strptime(start_datetime, '%Y-%m-%dT%H:%M')
            start_dt = django_timezone.make_aware(start_dt)
            
            end_dt = datetime.strptime(end_datetime, '%Y-%m-%dT%H:%M')
            end_dt = django_timezone.make_aware(end_dt)
            
            if end_dt <= start_dt:
                messages.error(request, 'End time must be after start time.')
                return render(request, 'MainInterface/edit_schedule_event.html', {
                    'schedule': schedule,
                    'courses': courses,
                    'class_types': ClassSchedule.CLASS_TYPE_CHOICES
                })
        except ValueError:
            messages.error(request, 'Invalid datetime format.')
            return render(request, 'MainInterface/edit_schedule_event.html', {
                'schedule': schedule,
                'courses': courses,
                'class_types': ClassSchedule.CLASS_TYPE_CHOICES
            })
        
        # Validate max_attendees
        if max_attendees:
            try:
                max_attendees = int(max_attendees)
            except ValueError:
                messages.error(request, 'Maximum attendees must be a number.')
                return render(request, 'MainInterface/edit_schedule_event.html', {
                    'schedule': schedule,
                    'courses': courses,
                    'class_types': ClassSchedule.CLASS_TYPE_CHOICES
                })
        else:
            max_attendees = None
        
        try:
            # Update schedule
            schedule.title = title
            schedule.description = description
            schedule.course = course
            schedule.class_type = class_type
            schedule.start_datetime = start_dt
            schedule.end_datetime = end_dt
            schedule.location = location
            schedule.is_online = is_online
            schedule.meeting_url = meeting_url
            schedule.max_attendees = max_attendees
            schedule.required_materials = required_materials
            schedule.notes = notes
            schedule.is_active = is_active
            schedule.is_cancelled = is_cancelled
            schedule.cancellation_reason = cancellation_reason
            schedule.save()
            
            messages.success(request, f'Class schedule "{title}" has been updated successfully!')
            return redirect('manage_schedule')
            
        except Exception as e:
            messages.error(request, f'An error occurred while updating the schedule: {str(e)}')
    
    context = {
        'schedule': schedule,
        'courses': courses,
        'class_types': ClassSchedule.CLASS_TYPE_CHOICES,
    }
    
    return render(request, 'MainInterface/edit_schedule_event.html', context)

@login_required
def delete_schedule_event_view(request, schedule_id):
    """Delete a class schedule event (lecturer only)"""
    try:
        if request.user.userprofile.user_type != 'lecturer':
            messages.error(request, 'Access denied. Lecturer access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    schedule = get_object_or_404(ClassSchedule, id=schedule_id, lecturer=request.user.userprofile)
    
    if request.method == 'POST':
        schedule_title = schedule.title
        schedule.delete()
        messages.success(request, f'Class schedule "{schedule_title}" has been deleted successfully!')
        return redirect('manage_schedule')
    
    context = {
        'schedule': schedule,
    }
    
    return render(request, 'MainInterface/delete_schedule_confirm.html', context)
