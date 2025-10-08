from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Avg, Count, Sum
from django.http import JsonResponse, HttpResponse, Http404
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.exceptions import ValidationError
from .models import UserProfile, Course, Enrollment, Grade, Assignment, AssignmentSubmission, StudyMaterial, AcademicCalendar, Announcement, ClassSchedule
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime
import os

# Create your views here.

def login_view(request):
    if request.user.is_authenticated:
        # Redirect to appropriate dashboard based on user type
        try:
            user_type = request.user.userprofile.user_type
            if user_type == 'student':
                return redirect('student_dashboard')
            else:
                return redirect('dashboard')
        except UserProfile.DoesNotExist:
            return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user_type = request.POST['user_type']
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Check if the user's profile matches the selected user type
            try:
                if user.userprofile.user_type == user_type:
                    login(request, user)
                    messages.success(request, f'Welcome {user.get_full_name() or user.username}!')
                    # Redirect based on user type
                    if user_type == 'student':
                        return redirect('student_dashboard')
                    elif user_type == 'lecturer':
                        return redirect('lecturer_dashboard')
                    else:
                        return redirect('dashboard')
                else:
                    messages.error(request, 'Invalid user type selected.')
            except UserProfile.DoesNotExist:
                # Create profile if it doesn't exist
                UserProfile.objects.create(user=user, user_type=user_type)
                login(request, user)
                messages.success(request, f'Welcome {user.get_full_name() or user.username}!')
                # Redirect based on user type
                if user_type == 'student':
                    return redirect('student_dashboard')
                elif user_type == 'lecturer':
                    return redirect('lecturer_dashboard')
                else:
                    return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'MainInterface/login.html')

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        first_name = request.POST['first_name']
        last_name = request.POST['last_name']
        password1 = request.POST['password1']
        password2 = request.POST['password2']
        user_type = request.POST['user_type']
        
        # Validation
        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'MainInterface/register.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return render(request, 'MainInterface/register.html')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists.')
            return render(request, 'MainInterface/register.html')
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1,
            first_name=first_name,
            last_name=last_name
        )
        
        # Update user profile with user type
        user.userprofile.user_type = user_type
        user.userprofile.save()
        
        messages.success(request, 'Account created successfully! Please log in.')
        return redirect('login')
    
    return render(request, 'MainInterface/register.html')

@login_required
def dashboard_view(request):
    # Redirect students to student dashboard
    try:
        if request.user.userprofile.user_type == 'student':
            return redirect('student_dashboard')
        elif request.user.userprofile.user_type == 'lecturer':
            return redirect('lecturer_dashboard')
    except UserProfile.DoesNotExist:
        pass
    
    return render(request, 'MainInterface/dashboard.html')

@login_required
def student_dashboard_view(request):
    # Ensure only students can access this dashboard
    try:
        if request.user.userprofile.user_type != 'student':
            messages.error(request, 'Access denied. Student access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    # Get student's enrolled courses
    enrolled_courses = Course.objects.filter(
        enrollments__student=request.user,
        enrollments__status='enrolled'
    )
    enrolled_courses_count = enrolled_courses.count()
    
    # Get assignments for enrolled courses
    assignments = Assignment.objects.filter(
        course__in=enrolled_courses,
        status='published'
    ).select_related('course').order_by('due_date')
    
    # Get student's submissions
    submissions = AssignmentSubmission.objects.filter(
        student=request.user
    ).select_related('assignment')
    
    # Create a map of assignment_id -> submission for easy lookup
    submission_map = {sub.assignment.id: sub for sub in submissions}
    
    # Categorize assignments and get pending assignments
    pending_assignments = []
    submitted_assignments = []
    overdue_assignments = []
    
    for assignment in assignments:
        submission = submission_map.get(assignment.id)
        assignment.user_submission = submission
        
        if submission and submission.status == 'submitted':
            submitted_assignments.append(assignment)
        elif assignment.is_overdue() and (not submission or submission.status == 'draft'):
            overdue_assignments.append(assignment)
        else:
            pending_assignments.append(assignment)
    
    # Calculate GPA using new model methods
    user_profile = request.user.userprofile
    current_gpa = user_profile.calculate_overall_gpa()
    gpa_status = user_profile.get_gpa_status()
    
    # Get semester-specific GPA (default to current semester)
    current_semester = 'fall'  # You can get this dynamically
    semester_gpa = user_profile.get_semester_gpa(current_semester)
    
    # Get course-specific GPAs
    course_gpas = {}
    for course in enrolled_courses:
        course_gpa = user_profile.calculate_course_gpa(course)
        if course_gpa is not None:
            course_gpas[course.id] = {
                'gpa': course_gpa,
                'course': course,
                'weights': course.get_assessment_weights()
            }
    
    # Get detailed grade statistics
    all_grades = Grade.objects.filter(student=request.user).select_related('course')
    grade_stats = {
        'total_grades': all_grades.count(),
        'graded_count': all_grades.exclude(grade_value='I').count(),
        'ungraded_count': all_grades.filter(grade_value='I').count(),
        'passing_grades': all_grades.filter(
            grade_value__in=['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-']
        ).count(),
    }
    
    if grade_stats['graded_count'] > 0:
        grade_stats['pass_rate'] = round(
            (grade_stats['passing_grades'] / grade_stats['graded_count']) * 100, 1
        )
    else:
        grade_stats['pass_rate'] = 0
    
    # Get recent grades (including tests and assignments)
    recent_grades = Grade.objects.filter(
        student=request.user,
        numeric_score__isnull=False  # Only graded items
    ).select_related('course').order_by('-date_graded')[:5]
    
    # Get total grade count
    total_grades_count = Grade.objects.filter(
        student=request.user,
        numeric_score__isnull=False
    ).count()
    
    # Get ungraded assessments count
    ungraded_count = Grade.objects.filter(
        student=request.user,
        numeric_score__isnull=True
    ).count()
    
    # Get recent announcements visible to the student
    from datetime import timedelta
    recent_announcements = []
    all_announcements = Announcement.objects.filter(is_active=True).select_related('course', 'author')
    
    for announcement in all_announcements:
        if announcement.is_visible_to_user(request.user):
            recent_announcements.append(announcement)
    
    # Sort by priority and date, get the 3 most recent
    def sort_key(announcement):
        priority_order = {'urgent': 0, 'high': 1, 'medium': 2, 'low': 3}
        return (priority_order.get(announcement.priority, 3), -announcement.created_at.timestamp())
    
    recent_announcements.sort(key=sort_key)
    recent_announcements = recent_announcements[:3]
    
    # Context data for the student dashboard
    context = {
        'user': request.user,
        'enrolled_courses_count': enrolled_courses_count,
        'current_gpa': current_gpa or 'N/A',
        'gpa_status': gpa_status,
        'semester_gpa': semester_gpa,
        'course_gpas': course_gpas,
        'grade_stats': grade_stats,
        'pending_assignments': pending_assignments[:5],  # Show first 5 pending assignments
        'pending_assignments_count': len(pending_assignments),
        'submitted_assignments_count': len(submitted_assignments),
        'overdue_assignments_count': len(overdue_assignments),
        'recent_announcements': recent_announcements,
        'recent_grades': recent_grades,
        'total_grades_count': total_grades_count,
        'ungraded_count': ungraded_count,
        'attendance_percentage': 85,  # Placeholder for attendance
    }
    
    return render(request, 'MainInterface/student_dashboard.html', context)

@login_required
def lecturer_dashboard_view(request):
    # Ensure only lecturers can access this dashboard
    try:
        if request.user.userprofile.user_type != 'lecturer':
            messages.error(request, 'Access denied. Lecturer access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    # Context data for the lecturer dashboard
    context = {
        'user': request.user,
        'total_courses': 0,  # Placeholder - will be populated when Course model is added
        'total_students': 0,  # Placeholder - will be populated when enrollment data is available
        'pending_submissions': 0,  # Placeholder - will be populated when Assignment model is added
        'upcoming_classes': 0,  # Placeholder - will be calculated from schedule data
    }
    
    return render(request, 'MainInterface/lecturer_dashboard.html', context)

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')

@login_required
def profile_management_view(request):
    """Handle profile management for all user types"""
    if request.method == 'POST':
        # Check if this is a password change request
        if 'change_password' in request.POST:
            current_password = request.POST.get('current_password', '').strip()
            new_password = request.POST.get('new_password', '').strip()
            confirm_password = request.POST.get('confirm_password', '').strip()
            
            # Validation
            if not current_password or not new_password or not confirm_password:
                messages.error(request, 'All password fields are required.')
                return render(request, 'MainInterface/profile_management.html')
            
            # Check if current password is correct
            if not request.user.check_password(current_password):
                messages.error(request, 'Current password is incorrect.')
                return render(request, 'MainInterface/profile_management.html')
            
            # Check if new passwords match
            if new_password != confirm_password:
                messages.error(request, 'New passwords do not match.')
                return render(request, 'MainInterface/profile_management.html')
            
            # Check password strength
            if len(new_password) < 8:
                messages.error(request, 'Password must be at least 8 characters long.')
                return render(request, 'MainInterface/profile_management.html')
            
            if new_password == current_password:
                messages.error(request, 'New password must be different from current password.')
                return render(request, 'MainInterface/profile_management.html')
            
            try:
                # Change password
                request.user.set_password(new_password)
                request.user.save()
                
                # Update session to prevent logout
                update_session_auth_hash(request, request.user)
                
                messages.success(request, 'Your password has been changed successfully!')
                
                # Redirect back to appropriate dashboard
                user_type = request.user.userprofile.user_type
                if user_type == 'student':
                    return redirect('student_dashboard')
                elif user_type == 'lecturer':
                    return redirect('lecturer_dashboard')
                else:
                    return redirect('dashboard')
                    
            except Exception as e:
                messages.error(request, f'An error occurred while changing your password: {str(e)}')
        
        else:
            # Handle profile information update
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            
            # Validation
            if not first_name or not last_name or not email:
                messages.error(request, 'All fields are required.')
                return render(request, 'MainInterface/profile_management.html')
            
            # Check if email is already taken by another user
            if User.objects.filter(email=email).exclude(id=request.user.id).exists():
                messages.error(request, 'This email address is already in use by another account.')
                return render(request, 'MainInterface/profile_management.html')
            
            try:
                # Update user information
                user = request.user
                user.first_name = first_name
                user.last_name = last_name
                user.email = email
                user.save()
                
                messages.success(request, 'Your profile has been updated successfully!')
                
                # Redirect back to appropriate dashboard
                user_type = user.userprofile.user_type
                if user_type == 'student':
                    return redirect('student_dashboard')
                elif user_type == 'lecturer':
                    return redirect('lecturer_dashboard')
                else:
                    return redirect('dashboard')
                    
            except Exception as e:
                messages.error(request, f'An error occurred while updating your profile: {str(e)}')
    
    return render(request, 'MainInterface/profile_management.html')

# Course Management Views
@login_required
def browse_courses_view(request):
    """Browse available courses with search and filter functionality"""
    # Get filter parameters
    search_query = request.GET.get('search', '')
    level_filter = request.GET.get('level', '')
    semester_filter = request.GET.get('semester', '')
    
    # Get all courses
    courses = Course.objects.all().select_related('lecturer')
    
    # Apply search filter
    if search_query:
        courses = courses.filter(
            Q(course_code__icontains=search_query) |
            Q(course_name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Apply level filter
    if level_filter:
        courses = courses.filter(level=level_filter)
    
    # Apply semester filter
    if semester_filter:
        courses = courses.filter(semester=semester_filter)
    
    # Get enrollment statistics for the current user
    user_enrollments = {}
    if hasattr(request.user, 'userprofile') and request.user.userprofile.user_type == 'student':
        enrollments = Enrollment.objects.filter(student=request.user).select_related('course')
        user_enrollments = {e.course.id: e.status for e in enrollments}
    
    # Calculate statistics
    total_courses = courses.count()
    available_courses = courses.filter(enrollments__status='enrolled').distinct().count()
    enrolled_count = len([s for s in user_enrollments.values() if s == 'enrolled'])
    pending_count = len([s for s in user_enrollments.values() if s == 'pending'])
    
    context = {
        'courses': courses,
        'total_courses': total_courses,
        'available_courses': available_courses,
        'enrolled_count': enrolled_count,
        'pending_count': pending_count,
        'user_enrollments': user_enrollments,
    }
    
    return render(request, 'MainInterface/browse_courses.html', context)

@login_required
def enrolled_courses_view(request):
    """View enrolled courses for students"""
    # Ensure only students can access
    try:
        if request.user.userprofile.user_type != 'student':
            messages.error(request, 'Access denied. Student access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    
    # Get student's enrollments
    enrollments = Enrollment.objects.filter(student=request.user).select_related('course', 'course__lecturer').order_by('-enrollment_date')
    
    # Apply status filter
    if status_filter:
        enrollments = enrollments.filter(status=status_filter)
    
    # Calculate statistics
    total_enrollments = Enrollment.objects.filter(student=request.user).count()
    enrolled_count = Enrollment.objects.filter(student=request.user, status='enrolled').count()
    pending_count = Enrollment.objects.filter(student=request.user, status='pending').count()
    waitlisted_count = Enrollment.objects.filter(student=request.user, status='waitlisted').count()
    
    # Calculate total credits for enrolled courses
    enrolled_courses = Enrollment.objects.filter(student=request.user, status='enrolled').select_related('course')
    total_credits = sum(enrollment.course.credits for enrollment in enrolled_courses)
    
    context = {
        'enrollments': enrollments,
        'total_enrollments': total_enrollments,
        'enrolled_count': enrolled_count,
        'pending_count': pending_count,
        'waitlisted_count': waitlisted_count,
        'total_credits': total_credits,
    }
    
    return render(request, 'MainInterface/enrolled_courses.html', context)

@login_required
def view_grades_view(request):
    """View grades and GPA for students"""
    # Ensure only students can access
    try:
        if request.user.userprofile.user_type != 'student':
            messages.error(request, 'Access denied. Student access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    # Get filter parameters
    semester_filter = request.GET.get('semester', '')
    grade_filter = request.GET.get('grade_filter', '')
    
    # Get all grades for the student
    grades_query = Grade.objects.filter(student=request.user).select_related('course', 'course__lecturer')
    
    # Apply filters
    if semester_filter:
        grades_query = grades_query.filter(course__semester=semester_filter)
    if grade_filter:
        grades_query = grades_query.filter(grade_value__startswith=grade_filter)
    
    # Group grades by course and get final grades
    course_grades = []
    courses_with_grades = grades_query.values('course').distinct()
    
    for course_info in courses_with_grades:
        course = Course.objects.get(id=course_info['course'])
        course_grade_list = grades_query.filter(course=course).order_by('-date_graded')
        
        # Find final grade (if exists) or latest grade
        final_grade = course_grade_list.filter(grade_type='final_grade').first()
        if not final_grade:
            final_grade = course_grade_list.first()
        
        # Calculate average score
        numeric_grades = course_grade_list.filter(numeric_score__isnull=False)
        avg_score = numeric_grades.aggregate(avg=Avg('numeric_score'))['avg'] or 0
        
        course_grades.append({
            'course': course,
            'final_grade': final_grade.grade_value if final_grade else 'N/A',
            'assignments_count': course_grade_list.count(),
            'average_score': avg_score,
            'recent_grades': course_grade_list[:5],  # Last 5 grades
        })
    
    # Calculate GPA
    def calculate_gpa(grade_list):
        total_points = 0
        total_credits = 0
        for course_data in grade_list:
            if course_data['final_grade'] != 'N/A':
                grade_points = Grade.GRADE_POINTS.get(course_data['final_grade'], 0)
                if grade_points is not None:  # Exclude I, W, P grades from GPA
                    total_points += grade_points * course_data['course'].credits
                    total_credits += course_data['course'].credits
        return round(total_points / total_credits, 2) if total_credits > 0 else 0
    
    current_gpa = calculate_gpa(course_grades)
    
    # Calculate semester GPA (if semester filter is applied)
    semester_gpa = current_gpa if semester_filter else None
    
    # Calculate statistics
    total_courses_with_grades = len(course_grades)
    total_credits_completed = sum(course_data['course'].credits for course_data in course_grades)
    
    # Grade distribution
    grade_distribution = {}
    for grade_letter in ['A', 'B', 'C', 'D', 'F']:
        count = sum(1 for course_data in course_grades 
                   if course_data['final_grade'] and course_data['final_grade'].startswith(grade_letter))
        grade_distribution[grade_letter] = count
    
    context = {
        'course_grades': course_grades,
        'current_gpa': current_gpa,
        'semester_gpa': semester_gpa,
        'total_courses_with_grades': total_courses_with_grades,
        'total_credits_completed': total_credits_completed,
        'grade_distribution': grade_distribution,
    }
    
    return render(request, 'MainInterface/view_grades.html', context)

@login_required
def grade_detail_view(request, course_id):
    """View individual course grade details."""
    if not request.user.is_authenticated:
        return redirect('login')
    
    try:
        user_profile = request.user.userprofile
        if user_profile.user_type != 'student':
            messages.error(request, 'Access denied. Students only.')
            return redirect('dashboard')
        
        # Get course and enrollment
        course = get_object_or_404(Course, id=course_id)
        enrollment = get_object_or_404(Enrollment, user=user_profile, course=course)
        
        # Get all grades for this course
        grades = Grade.objects.filter(enrollment=enrollment).order_by('-date_graded')
        
        # Group grades by type
        grades_by_type = {}
        for grade in grades:
            if grade.grade_type not in grades_by_type:
                grades_by_type[grade.grade_type] = []
            grades_by_type[grade.grade_type].append(grade)
        
        # Calculate statistics
        total_assignments = grades.count()
        
        # Calculate average score
        scored_grades = [g for g in grades if g.numeric_score and g.max_points]
        if scored_grades:
            total_points = sum(g.numeric_score for g in scored_grades)
            max_possible = sum(g.max_points for g in scored_grades)
            average_score = (total_points / max_possible) * 100 if max_possible > 0 else 0
        else:
            average_score = 0
        
        # Get final grade (latest grade marked as 'final')
        final_grade = grades.filter(grade_type='final').first()
        
        context = {
            'course': course,
            'enrollment': enrollment,
            'grades': grades,
            'grades_by_type': grades_by_type,
            'total_assignments': total_assignments,
            'average_score': average_score,
            'final_grade': final_grade,
        }
        
        return render(request, 'MainInterface/grade_detail.html', context)
        
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('login')

@login_required
def manage_courses_view(request):
    """Manage courses for lecturers"""
    # Ensure only lecturers can access
    try:
        if request.user.userprofile.user_type != 'lecturer':
            messages.error(request, 'Access denied. Lecturer access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    # Get lecturer's courses with enrollment counts
    courses = Course.objects.filter(lecturer=request.user.userprofile).prefetch_related('enrollments')
    
    # Add pending enrollment counts to each course
    for course in courses:
        course.pending_count = course.enrollments.filter(status='pending').count()
    
    # Calculate statistics
    total_courses = courses.count()
    active_courses = courses.filter(is_active=True).count()
    total_students = sum(course.get_enrolled_count() for course in courses)
    pending_enrollments = sum(course.enrollments.filter(status='pending').count() for course in courses)
    
    context = {
        'courses': courses,
        'total_courses': total_courses,
        'active_courses': active_courses,
        'total_students': total_students,
        'pending_enrollments': pending_enrollments,
    }
    
    return render(request, 'MainInterface/manage_courses.html', context)

@login_required
def add_course_view(request):
    """Add a new course (lecturer only)"""
    try:
        if request.user.userprofile.user_type != 'lecturer':
            messages.error(request, 'Access denied. Lecturer access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        course_code = request.POST.get('course_code', '').strip().upper()
        course_name = request.POST.get('course_name', '').strip()
        description = request.POST.get('description', '').strip()
        credits = request.POST.get('credits', '3')
        semester = request.POST.get('semester', '1')
        level = request.POST.get('level', '100')
        max_students = request.POST.get('max_students', '50')
        
        # Validation
        if not all([course_code, course_name, description]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'MainInterface/add_course.html')
        
        # Check if course code already exists
        if Course.objects.filter(course_code=course_code).exists():
            messages.error(request, f'Course code "{course_code}" already exists.')
            return render(request, 'MainInterface/add_course.html')
        
        try:
            # Create course
            course = Course.objects.create(
                course_code=course_code,
                course_name=course_name,
                description=description,
                lecturer=request.user.userprofile,
                credits=int(credits),
                semester=semester,
                level=level,
                max_students=int(max_students)
            )
            
            messages.success(request, f'Course "{course_code}" has been created successfully!')
            return redirect('manage_courses')
            
        except ValueError as e:
            messages.error(request, f'Invalid data provided: {str(e)}')
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
    
    return render(request, 'MainInterface/add_course.html')

@login_required
def enroll_course_view(request, course_id):
    """Enroll a student in a course"""
    try:
        if request.user.userprofile.user_type != 'student':
            messages.error(request, 'Only students can enroll in courses.')
            return redirect('browse_courses')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('browse_courses')
    
    course = get_object_or_404(Course, id=course_id)
    
    # Check if already enrolled or has pending enrollment
    existing_enrollment = Enrollment.objects.filter(student=request.user, course=course).first()
    if existing_enrollment:
        if existing_enrollment.status == 'enrolled':
            messages.warning(request, f'You are already enrolled in {course.course_code}.')
        elif existing_enrollment.status == 'pending':
            messages.info(request, f'Your enrollment in {course.course_code} is pending approval.')
        else:
            messages.info(request, f'You have a {existing_enrollment.get_status_display().lower()} status for {course.course_code}.')
        return redirect('browse_courses')
    
    # Create enrollment
    status = 'enrolled' if course.has_space() else 'waitlisted'
    Enrollment.objects.create(
        student=request.user,
        course=course,
        status=status
    )
    
    if status == 'enrolled':
        messages.success(request, f'Successfully enrolled in {course.course_code}!')
    else:
        messages.info(request, f'Added to waitlist for {course.course_code}. You will be notified if a spot becomes available.')
    
    return redirect('browse_courses')

@login_required
def drop_course_view(request, course_id):
    """Drop a course enrollment"""
    try:
        if request.user.userprofile.user_type != 'student':
            messages.error(request, 'Access denied.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    enrollment = get_object_or_404(Enrollment, student=request.user, course_id=course_id)
    course_code = enrollment.course.course_code
    
    enrollment.status = 'dropped'
    enrollment.save()
    
    messages.success(request, f'Successfully dropped {course_code}.')
    return redirect('browse_courses')

@login_required
def cancel_enrollment_view(request, course_id):
    """Cancel a pending enrollment"""
    try:
        if request.user.userprofile.user_type != 'student':
            messages.error(request, 'Access denied.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    enrollment = get_object_or_404(Enrollment, student=request.user, course_id=course_id, status='pending')
    course_code = enrollment.course.course_code
    
    enrollment.delete()
    
    messages.success(request, f'Cancelled enrollment request for {course_code}.')
    return redirect('browse_courses')

@login_required
def join_waitlist_view(request, course_id):
    """Join course waitlist"""
    try:
        if request.user.userprofile.user_type != 'student':
            messages.error(request, 'Access denied.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    course = get_object_or_404(Course, id=course_id)
    
    # Check if already has enrollment record
    existing_enrollment = Enrollment.objects.filter(student=request.user, course=course).first()
    if existing_enrollment:
        messages.warning(request, f'You already have a record for {course.course_code}.')
        return redirect('browse_courses')
    
    # Join waitlist
    Enrollment.objects.create(
        student=request.user,
        course=course,
        status='waitlisted'
    )
    
    messages.info(request, f'Added to waitlist for {course.course_code}.')
    return redirect('browse_courses')

@login_required
def course_detail_view(request, course_id):
    """View detailed course information"""
    course = get_object_or_404(Course, id=course_id)
    
    # Get enrollment status for current user if student
    user_enrollment = None
    user_assignments = []
    user_submissions = []
    user_grades = []
    if hasattr(request.user, 'userprofile') and request.user.userprofile.user_type == 'student':
        user_enrollment = Enrollment.objects.filter(student=request.user, course=course).first()
        
        # Only show detailed info if student is enrolled
        if user_enrollment and user_enrollment.status == 'enrolled':
            # Get assignments for this course
            assignments = Assignment.objects.filter(
                course=course, 
                status='published'
            ).order_by('-due_date')
            
            # Get user's submissions for these assignments
            user_submissions = AssignmentSubmission.objects.filter(
                assignment__course=course,
                student=request.user
            ).select_related('assignment')
            
            # Create a dict for quick lookup of submissions by assignment
            submissions_by_assignment = {sub.assignment.id: sub for sub in user_submissions}
            
            # Add submission info to assignments
            user_assignments = []
            for assignment in assignments:
                assignment.user_submission = submissions_by_assignment.get(assignment.id)
                user_assignments.append(assignment)
            
            # Get user's grades for this course
            user_grades = Grade.objects.filter(
                student=request.user,
                course=course
            ).order_by('-date_graded')
    
    # Get course announcements
    announcements = Announcement.objects.filter(
        Q(course=course) | Q(audience='all', course__isnull=True),
        is_active=True
    ).order_by('-is_pinned', '-created_at')[:5]
    
    # Filter announcements based on user visibility
    visible_announcements = []
    for announcement in announcements:
        if announcement.is_visible_to_user(request.user):
            visible_announcements.append(announcement)
    
    # Get study materials for enrolled students
    study_materials = []
    if user_enrollment and user_enrollment.status == 'enrolled':
        study_materials = StudyMaterial.objects.filter(
            course=course,
            is_active=True
        ).order_by('-created_at')[:10]
    
    # Get class schedule
    upcoming_classes = ClassSchedule.objects.filter(
        course=course,
        is_active=True,
        is_cancelled=False,
        start_datetime__gte=timezone.now()
    ).order_by('start_datetime')[:5]
    
    recent_classes = ClassSchedule.objects.filter(
        course=course,
        is_active=True,
        end_datetime__lt=timezone.now()
    ).order_by('-start_datetime')[:5]
    
    context = {
        'course': course,
        'user_enrollment': user_enrollment,
        'user_assignments': user_assignments,
        'user_grades': user_grades,
        'announcements': visible_announcements,
        'study_materials': study_materials,
        'upcoming_classes': upcoming_classes,
        'recent_classes': recent_classes,
    }
    
    return render(request, 'MainInterface/course_detail.html', context)

# Course management views
@login_required
def edit_course_view(request, course_id):
    """Edit course details (lecturer only)"""
    try:
        if request.user.userprofile.user_type != 'lecturer':
            messages.error(request, 'Access denied. Lecturer access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    try:
        course = Course.objects.get(id=course_id, lecturer=request.user.userprofile)
    except Course.DoesNotExist:
        messages.error(request, 'Course not found or you do not have permission to edit it.')
        return redirect('manage_courses')
    
    if request.method == 'POST':
        # Get form data
        course_code = request.POST.get('course_code', '').strip()
        course_name = request.POST.get('course_name', '').strip()
        description = request.POST.get('description', '').strip()
        credits = request.POST.get('credits')
        level = request.POST.get('level')
        semester = request.POST.get('semester')
        max_students = request.POST.get('max_students')
        
        # Validation
        errors = []
        
        if not course_code:
            errors.append('Course code is required.')
        elif len(course_code) > 20:
            errors.append('Course code must be 20 characters or less.')
        elif Course.objects.filter(course_code=course_code).exclude(id=course.id).exists():
            errors.append('A course with this code already exists.')
            
        if not course_name:
            errors.append('Course name is required.')
        elif len(course_name) > 200:
            errors.append('Course name must be 200 characters or less.')
            
        try:
            credits = int(credits) if credits else 3
            if credits < 1 or credits > 10:
                errors.append('Credits must be between 1 and 10.')
        except ValueError:
            errors.append('Credits must be a valid number.')
            
        try:
            max_students = int(max_students) if max_students else 30
            if max_students < 1 or max_students > 500:
                errors.append('Maximum students must be between 1 and 500.')
            elif max_students < course.get_enrolled_count():
                errors.append(f'Cannot reduce max students below current enrollment count ({course.get_enrolled_count()}).')
        except ValueError:
            errors.append('Maximum students must be a valid number.')
            
        if level not in ['undergraduate', 'graduate', 'postgraduate']:
            errors.append('Invalid level selected.')
            
        if semester not in ['spring', 'summer', 'fall', 'winter']:
            errors.append('Invalid semester selected.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            # Update course
            course.course_code = course_code
            course.course_name = course_name
            course.description = description
            course.credits = credits
            course.level = level
            course.semester = semester
            course.max_students = max_students
            course.save()
            
            messages.success(request, f'Course "{course.course_name}" updated successfully.')
            return redirect('manage_courses')
    
    context = {
        'course': course,
        'level_choices': Course.LEVEL_CHOICES,
        'semester_choices': Course.SEMESTER_CHOICES,
    }
    
    return render(request, 'MainInterface/edit_course.html', context)

@login_required  
def delete_course_view(request, course_id):
    messages.info(request, 'Course deletion functionality will be implemented soon.')
    return redirect('manage_courses')

@login_required
def course_enrollments_view(request, course_id):
    """Manage course enrollments (lecturer only)"""
    try:
        if request.user.userprofile.user_type != 'lecturer':
            messages.error(request, 'Access denied. Lecturer access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    try:
        course = Course.objects.get(id=course_id, lecturer=request.user.userprofile)
    except Course.DoesNotExist:
        messages.error(request, 'Course not found or you do not have permission to manage its enrollments.')
        return redirect('manage_courses')
    
    # Handle POST requests for enrollment actions
    if request.method == 'POST':
        action = request.POST.get('action')
        enrollment_id = request.POST.get('enrollment_id')
        
        try:
            enrollment = Enrollment.objects.get(id=enrollment_id, course=course)
            
            if action == 'approve':
                if course.has_available_slots():
                    enrollment.status = 'enrolled'
                    enrollment.save()
                    messages.success(request, f'Approved enrollment for {enrollment.student.user.get_full_name() or enrollment.student.user.username}.')
                else:
                    messages.error(request, 'Cannot approve enrollment - course is at maximum capacity.')
                    
            elif action == 'reject':
                enrollment.status = 'rejected'
                enrollment.save()
                messages.success(request, f'Rejected enrollment for {enrollment.student.user.get_full_name() or enrollment.student.user.username}.')
                
            elif action == 'unenroll':
                student_name = enrollment.student.user.get_full_name() or enrollment.student.user.username
                enrollment.delete()
                messages.success(request, f'Removed {student_name} from the course.')
                
            elif action == 'reactivate':
                enrollment.status = 'enrolled'
                enrollment.save()
                messages.success(request, f'Reactivated enrollment for {enrollment.student.user.get_full_name() or enrollment.student.user.username}.')
                
        except Enrollment.DoesNotExist:
            messages.error(request, 'Enrollment not found.')
    
    # Get all enrollments for this course
    enrollments = Enrollment.objects.filter(course=course).select_related('student').order_by('-created_at')
    
    # Separate by status
    pending_enrollments = enrollments.filter(status='pending')
    active_enrollments = enrollments.filter(status='enrolled')
    rejected_enrollments = enrollments.filter(status='rejected')
    
    # Calculate statistics
    total_enrollments = enrollments.count()
    enrolled_count = active_enrollments.count()
    pending_count = pending_enrollments.count()
    rejected_count = rejected_enrollments.count()
    available_slots = course.max_students - enrolled_count
    
    context = {
        'course': course,
        'pending_enrollments': pending_enrollments,
        'active_enrollments': active_enrollments,
        'rejected_enrollments': rejected_enrollments,
        'total_enrollments': total_enrollments,
        'enrolled_count': enrolled_count,
        'pending_count': pending_count,
        'rejected_count': rejected_count,
        'available_slots': available_slots,
        'is_full': available_slots <= 0,
    }
    
    return render(request, 'MainInterface/course_enrollments.html', context)

@login_required
def activate_course_view(request, course_id):
    """Activate a course"""
    try:
        # Check if user is a lecturer
        if request.user.userprofile.user_type != 'lecturer':
            messages.error(request, 'Access denied. Lecturer access required.')
            return redirect('dashboard')
        
        # Get the course
        course = get_object_or_404(Course, id=course_id, lecturer=request.user.userprofile)
        
        # Activate the course
        course.is_active = True
        course.save()
        
        messages.success(request, f'Course "{course.course_name}" has been activated successfully.')
        
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
    except Exception as e:
        messages.error(request, f'Error activating course: {str(e)}')
    
    return redirect('manage_courses')

@login_required
def deactivate_course_view(request, course_id):
    """Deactivate a course"""
    try:
        # Check if user is a lecturer
        if request.user.userprofile.user_type != 'lecturer':
            messages.error(request, 'Access denied. Lecturer access required.')
            return redirect('dashboard')
        
        # Get the course
        course = get_object_or_404(Course, id=course_id, lecturer=request.user.userprofile)
        
        # Deactivate the course
        course.is_active = False
        course.save()
        
        messages.success(request, f'Course "{course.course_name}" has been deactivated successfully.')
        
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
    except Exception as e:
        messages.error(request, f'Error deactivating course: {str(e)}')
    
    return redirect('manage_courses')

@login_required
def academic_calendar_view(request):
    """Academic calendar view for students and faculty"""
    from .models import AcademicCalendar
    import calendar
    from datetime import datetime, timedelta
    
    # Get current date
    today = timezone.now().date()
    current_year = today.year
    current_month = today.month
    
    # Get year and month from query parameters
    year = int(request.GET.get('year', current_year))
    month = int(request.GET.get('month', current_month))
    
    # Get all events for the selected month/year
    events = AcademicCalendar.objects.filter(
        is_active=True,
        start_date__year=year,
        start_date__month=month
    ).order_by('start_date')
    
    # Get events that span into this month
    spanning_events = AcademicCalendar.objects.filter(
        is_active=True,
        start_date__lt=datetime(year, month, 1).date(),
        end_date__gte=datetime(year, month, 1).date()
    ).order_by('start_date')
    
    # Combine events
    all_events = list(events) + list(spanning_events)
    
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
    
    # Organize events by date for easy template access
    events_by_date = {}
    for event in all_events:
        event_start = event.start_date
        event_end = event.end_date or event.start_date
        
        # Add event to all dates it spans
        current_date = event_start
        while current_date <= event_end:
            if current_date.year == year and current_date.month == month:
                if current_date.day not in events_by_date:
                    events_by_date[current_date.day] = []
                events_by_date[current_date.day].append(event)
            current_date += timedelta(days=1)
    
    # Get upcoming events (next 30 days)
    upcoming_events = AcademicCalendar.objects.filter(
        is_active=True,
        start_date__gte=today,
        start_date__lte=today + timedelta(days=30)
    ).order_by('start_date')[:5]
    
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
        'events_by_date': events_by_date,
        'upcoming_events': upcoming_events,
        'all_events': all_events,
    }
    
    return render(request, 'MainInterface/academic_calendar.html', context)

@login_required
def announcements_view(request):
    """View all announcements visible to the current user"""
    from .models import Announcement
    
    # Get all active announcements visible to the user
    announcements = Announcement.objects.filter(is_active=True)
    
    # Filter announcements based on user type and visibility
    visible_announcements = []
    for announcement in announcements:
        if announcement.is_visible_to_user(request.user):
            visible_announcements.append(announcement)
    
    # Separate pinned and regular announcements
    pinned_announcements = [a for a in visible_announcements if a.is_pinned]
    regular_announcements = [a for a in visible_announcements if not a.is_pinned]
    
    # Sort by priority and date
    def sort_key(announcement):
        priority_order = {'urgent': 0, 'high': 1, 'medium': 2, 'low': 3}
        return (priority_order.get(announcement.priority, 3), announcement.created_at)
    
    pinned_announcements.sort(key=sort_key, reverse=True)
    regular_announcements.sort(key=sort_key, reverse=True)
    
    # Get recent announcements (last 7 days)
    from datetime import timedelta
    recent_cutoff = timezone.now() - timedelta(days=7)
    recent_announcements = [a for a in visible_announcements if a.created_at >= recent_cutoff]
    
    # Get user's courses for context (if student)
    user_courses = []
    if hasattr(request.user, 'userprofile') and request.user.userprofile.user_type == 'student':
        enrollments = Enrollment.objects.filter(student=request.user, status='enrolled').select_related('course')
        user_courses = [e.course for e in enrollments]
    elif hasattr(request.user, 'userprofile') and request.user.userprofile.user_type == 'lecturer':
        user_courses = Course.objects.filter(lecturer=request.user.userprofile)
    
    context = {
        'pinned_announcements': pinned_announcements,
        'regular_announcements': regular_announcements,
        'recent_announcements': recent_announcements,
        'user_courses': user_courses,
        'total_announcements': len(visible_announcements),
    }
    
    return render(request, 'MainInterface/announcements.html', context)

@login_required
def study_materials_view(request):
    """View study materials for enrolled courses"""
    from .models import StudyMaterial
    from django.http import HttpResponse, Http404
    
    # Handle file download
    if request.GET.get('download'):
        material_id = request.GET.get('download')
        try:
            material = StudyMaterial.objects.get(id=material_id)
            if material.is_accessible_to_user(request.user):
                material.increment_download_count()
                response = HttpResponse(material.file.read(), content_type='application/octet-stream')
                response['Content-Disposition'] = f'attachment; filename="{material.file.name.split("/")[-1]}"'
                return response
            else:
                messages.error(request, "You don't have permission to download this file.")
        except StudyMaterial.DoesNotExist:
            messages.error(request, "File not found.")
        return redirect('study_materials')
    
    # Get filter parameters
    course_filter = request.GET.get('course', '')
    material_type_filter = request.GET.get('type', '')
    search_query = request.GET.get('search', '')
    
    # Get user's enrolled courses
    user_courses = []
    if hasattr(request.user, 'userprofile'):
        if request.user.userprofile.user_type == 'student':
            enrollments = Enrollment.objects.filter(student=request.user, status='enrolled').select_related('course')
            user_courses = [e.course for e in enrollments]
        elif request.user.userprofile.user_type == 'lecturer':
            user_courses = list(Course.objects.filter(lecturer=request.user.userprofile))
    
    # Get study materials for user's courses
    materials = StudyMaterial.objects.filter(
        course__in=user_courses,
        is_active=True
    ).select_related('course', 'uploaded_by').order_by('-created_at')
    
    # Apply filters
    if course_filter:
        materials = materials.filter(course__id=course_filter)
    
    if material_type_filter:
        materials = materials.filter(material_type=material_type_filter)
    
    if search_query:
        materials = materials.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(course__course_name__icontains=search_query) |
            Q(course__course_code__icontains=search_query)
        )
    
    # Group materials by course
    materials_by_course = {}
    for material in materials:
        if material.course not in materials_by_course:
            materials_by_course[material.course] = []
        materials_by_course[material.course].append(material)
    
    # Get recent materials (last 30 days)
    from datetime import timedelta
    recent_cutoff = timezone.now() - timedelta(days=30)
    recent_materials = materials.filter(created_at__gte=recent_cutoff)[:5]
    
    # Get material type choices for filter
    material_types = StudyMaterial.MATERIAL_TYPE_CHOICES
    
    # Calculate statistics
    total_materials = materials.count()
    total_downloads = sum(m.download_count for m in materials)
    
    context = {
        'materials_by_course': materials_by_course,
        'user_courses': user_courses,
        'recent_materials': recent_materials,
        'material_types': material_types,
        'selected_course': course_filter,
        'selected_type': material_type_filter,
        'search_query': search_query,
        'total_materials': total_materials,
        'total_downloads': total_downloads,
        'total_courses': len(user_courses),
    }
    
    return render(request, 'MainInterface/study_materials.html', context)

# Course Materials Management Views
@login_required
def upload_material_view(request):
    """Upload new course material (lecturer only)"""
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
        material_type = request.POST.get('material_type', 'other')
        course_id = request.POST.get('course')
        uploaded_file = request.FILES.get('file')
        
        # Validation
        if not all([title, course_id, uploaded_file]):
            messages.error(request, 'Please fill in all required fields and select a file.')
            return render(request, 'MainInterface/upload_material.html', {'courses': courses})
        
        # Validate course belongs to lecturer
        try:
            course = Course.objects.get(id=course_id, lecturer=request.user.userprofile)
        except Course.DoesNotExist:
            messages.error(request, 'Invalid course selected.')
            return render(request, 'MainInterface/upload_material.html', {'courses': courses})
        
        # File size validation (max 50MB)
        max_size = 50 * 1024 * 1024  # 50MB in bytes
        if uploaded_file.size > max_size:
            messages.error(request, 'File size must be less than 50MB.')
            return render(request, 'MainInterface/upload_material.html', {'courses': courses})
        
        try:
            # Create study material
            material = StudyMaterial.objects.create(
                title=title,
                description=description,
                material_type=material_type,
                course=course,
                uploaded_by=request.user,
                file=uploaded_file,
                file_size=uploaded_file.size
            )
            
            messages.success(request, f'Material "{title}" has been uploaded successfully!')
            return redirect('manage_materials')
            
        except Exception as e:
            messages.error(request, f'An error occurred while uploading the material: {str(e)}')
    
    context = {
        'courses': courses,
        'material_types': StudyMaterial.MATERIAL_TYPE_CHOICES,
    }
    
    return render(request, 'MainInterface/upload_material.html', context)

@login_required
def manage_materials_view(request):
    """Manage uploaded materials (lecturer only)"""
    try:
        if request.user.userprofile.user_type != 'lecturer':
            messages.error(request, 'Access denied. Lecturer access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    # Handle file download
    if request.GET.get('download'):
        material_id = request.GET.get('download')
        try:
            material = StudyMaterial.objects.get(id=material_id)
            # Check if lecturer owns this material's course
            if material.course.lecturer == request.user.userprofile:
                material.increment_download_count()
                response = HttpResponse(material.file.read(), content_type='application/octet-stream')
                response['Content-Disposition'] = f'attachment; filename="{material.file.name.split("/")[-1]}"'
                return response
            else:
                messages.error(request, "You don't have permission to download this file.")
        except StudyMaterial.DoesNotExist:
            messages.error(request, "File not found.")
        return redirect('manage_materials')
    
    # Get lecturer's courses
    courses = Course.objects.filter(lecturer=request.user.userprofile)
    
    # Get materials for lecturer's courses
    materials = StudyMaterial.objects.filter(
        course__in=courses
    ).select_related('course').order_by('-created_at')
    
    # Apply filters
    course_filter = request.GET.get('course', '')
    material_type_filter = request.GET.get('type', '')
    search_query = request.GET.get('search', '')
    
    if course_filter:
        materials = materials.filter(course__id=course_filter)
    
    if material_type_filter:
        materials = materials.filter(material_type=material_type_filter)
    
    if search_query:
        materials = materials.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Group materials by course
    materials_by_course = {}
    for material in materials:
        if material.course not in materials_by_course:
            materials_by_course[material.course] = []
        materials_by_course[material.course].append(material)
    
    # Calculate statistics
    total_materials = materials.count()
    total_downloads = sum(m.download_count for m in materials)
    active_materials = materials.filter(is_active=True).count()
    
    context = {
        'materials_by_course': materials_by_course,
        'courses': courses,
        'material_types': StudyMaterial.MATERIAL_TYPE_CHOICES,
        'selected_course': course_filter,
        'selected_type': material_type_filter,
        'search_query': search_query,
        'total_materials': total_materials,
        'total_downloads': total_downloads,
        'active_materials': active_materials,
    }
    
    return render(request, 'MainInterface/manage_materials.html', context)

@login_required
def edit_material_view(request, material_id):
    """Edit existing material (lecturer only)"""
    try:
        if request.user.userprofile.user_type != 'lecturer':
            messages.error(request, 'Access denied. Lecturer access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    material = get_object_or_404(StudyMaterial, id=material_id)
    
    # Check if lecturer owns this material's course
    if material.course.lecturer != request.user.userprofile:
        messages.error(request, 'You do not have permission to edit this material.')
        return redirect('manage_materials')
    
    # Handle file download
    if request.GET.get('download'):
        if material.file:
            material.increment_download_count()
            response = HttpResponse(material.file.read(), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{material.file.name.split("/")[-1]}"'
            return response
        else:
            messages.error(request, "No file attached to this material.")
            return redirect('edit_material', material_id=material_id)
    
    # Get lecturer's courses
    courses = Course.objects.filter(lecturer=request.user.userprofile, is_active=True)
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        material_type = request.POST.get('material_type', 'other')
        course_id = request.POST.get('course')
        is_active = request.POST.get('is_active') == 'on'
        uploaded_file = request.FILES.get('file')
        
        # Validation
        if not all([title, course_id]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'MainInterface/edit_material.html', {
                'material': material, 'courses': courses
            })
        
        # Validate course belongs to lecturer
        try:
            course = Course.objects.get(id=course_id, lecturer=request.user.userprofile)
        except Course.DoesNotExist:
            messages.error(request, 'Invalid course selected.')
            return render(request, 'MainInterface/edit_material.html', {
                'material': material, 'courses': courses
            })
        
        try:
            # Update material
            material.title = title
            material.description = description
            material.material_type = material_type
            material.course = course
            material.is_active = is_active
            
            # Handle file replacement
            if uploaded_file:
                # File size validation (max 50MB)
                max_size = 50 * 1024 * 1024  # 50MB in bytes
                if uploaded_file.size > max_size:
                    messages.error(request, 'File size must be less than 50MB.')
                    return render(request, 'MainInterface/edit_material.html', {
                        'material': material, 'courses': courses
                    })
                
                material.file = uploaded_file
                material.file_size = uploaded_file.size
            
            material.save()
            
            messages.success(request, f'Material "{title}" has been updated successfully!')
            return redirect('manage_materials')
            
        except Exception as e:
            messages.error(request, f'An error occurred while updating the material: {str(e)}')
    
    context = {
        'material': material,
        'courses': courses,
        'material_types': StudyMaterial.MATERIAL_TYPE_CHOICES,
    }
    
    return render(request, 'MainInterface/edit_material.html', context)

@login_required
def delete_material_view(request, material_id):
    """Delete material (lecturer only)"""
    try:
        if request.user.userprofile.user_type != 'lecturer':
            messages.error(request, 'Access denied. Lecturer access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    material = get_object_or_404(StudyMaterial, id=material_id)
    
    # Check if lecturer owns this material's course
    if material.course.lecturer != request.user.userprofile:
        messages.error(request, 'You do not have permission to delete this material.')
        return redirect('manage_materials')
    
    if request.method == 'POST':
        material_title = material.title
        # Delete the file from filesystem
        if material.file:
            try:
                material.file.delete()
            except:
                pass  # Continue even if file deletion fails
        
        material.delete()
        messages.success(request, f'Material "{material_title}" has been deleted successfully!')
        return redirect('manage_materials')
    
    context = {
        'material': material,
    }
    
    return render(request, 'MainInterface/delete_material_confirm.html', context)

# Assignment Views
@login_required
def assignments_view(request):
    """View available assignments for students"""
    try:
        if request.user.userprofile.user_type != 'student':
            messages.error(request, 'Access denied. Student access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    # Get student's enrolled courses
    enrolled_courses = Course.objects.filter(
        enrollments__student=request.user,
        enrollments__status='enrolled'
    )
    
    # Get assignments for enrolled courses
    assignments = Assignment.objects.filter(
        course__in=enrolled_courses,
        status='published'
    ).select_related('course').order_by('due_date')
    
    # Get student's submissions
    submissions = AssignmentSubmission.objects.filter(
        student=request.user
    ).select_related('assignment')
    
    # Create a map of assignment_id -> submission for easy lookup
    submission_map = {sub.assignment.id: sub for sub in submissions}
    
    # Categorize assignments
    pending_assignments = []
    submitted_assignments = []
    overdue_assignments = []
    
    for assignment in assignments:
        submission = submission_map.get(assignment.id)
        assignment.user_submission = submission
        
        if submission and submission.status == 'submitted':
            submitted_assignments.append(assignment)
        elif assignment.is_overdue() and (not submission or submission.status == 'draft'):
            overdue_assignments.append(assignment)
        else:
            pending_assignments.append(assignment)
    
    context = {
        'pending_assignments': pending_assignments,
        'submitted_assignments': submitted_assignments,
        'overdue_assignments': overdue_assignments,
        'total_assignments': assignments.count(),
        'total_submitted': len(submitted_assignments),
        'total_pending': len(pending_assignments),
        'total_overdue': len(overdue_assignments),
    }
    
    return render(request, 'MainInterface/assignments.html', context)

@login_required
def submit_assignment_view(request, assignment_id):
    """Submit an assignment"""
    try:
        if request.user.userprofile.user_type != 'student':
            messages.error(request, 'Access denied. Student access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    assignment = get_object_or_404(Assignment, id=assignment_id)
    
    # Check if student is enrolled in the course
    if not Enrollment.objects.filter(
        student=request.user, 
        course=assignment.course, 
        status='enrolled'
    ).exists():
        messages.error(request, 'You are not enrolled in this course.')
        return redirect('assignments')
    
    # Get or create submission
    submission, created = AssignmentSubmission.objects.get_or_create(
        assignment=assignment,
        student=request.user,
        defaults={'status': 'draft'}
    )
    
    # Check if assignment is closed for submissions
    if assignment.status == 'closed':
        messages.error(request, 'This assignment is no longer accepting submissions.')
        return redirect('assignments')
    
    # Check if assignment is overdue and late submissions are not allowed
    if assignment.is_overdue() and not assignment.late_submission_allowed:
        messages.error(request, 'This assignment is overdue and late submissions are not allowed.')
        return redirect('assignments')
    
    if request.method == 'POST':
        submission_text = request.POST.get('submission_text', '').strip()
        submitted_file = request.FILES.get('submission_file')
        action = request.POST.get('action')
        
        # Validate file if provided
        if submitted_file:
            # Check file size
            if submitted_file.size > assignment.max_file_size:
                messages.error(request, f'File size exceeds maximum allowed size of {assignment.get_max_file_size_display()}.')
                return render(request, 'MainInterface/submit_assignment.html', {
                    'assignment': assignment,
                    'submission': submission
                })
            
            # Check file type
            file_extension = submitted_file.name.split('.')[-1].lower()
            allowed_types = assignment.get_allowed_file_types_list()
            if file_extension not in allowed_types:
                messages.error(request, f'File type ".{file_extension}" is not allowed. Allowed types: {", ".join(allowed_types)}')
                return render(request, 'MainInterface/submit_assignment.html', {
                    'assignment': assignment,
                    'submission': submission
                })
            
            # Remove old file if exists
            if submission.submission_file:
                old_file_path = submission.submission_file.path
                if os.path.exists(old_file_path):
                    os.remove(old_file_path)
            
            submission.submission_file = submitted_file
        
        # Update submission text
        submission.submission_text = submission_text
        
        # Handle different actions
        if action == 'save_draft':
            submission.status = 'draft'
            submission.save()
            messages.success(request, 'Draft saved successfully.')
        elif action == 'submit':
            if not submitted_file and not submission.submission_file and not submission_text:
                messages.error(request, 'Please provide either a file or text submission.')
                return render(request, 'MainInterface/submit_assignment.html', {
                    'assignment': assignment,
                    'submission': submission
                })
            
            submission.status = 'submitted'
            submission.submitted_at = timezone.now()
            submission.save()
            messages.success(request, 'Assignment submitted successfully!')
            return redirect('assignments')
        
        return render(request, 'MainInterface/submit_assignment.html', {
            'assignment': assignment,
            'submission': submission
        })
    
    context = {
        'assignment': assignment,
        'submission': submission,
        'allowed_file_types': assignment.get_allowed_file_types_list(),
        'max_file_size': assignment.get_max_file_size_display(),
    }
    
    return render(request, 'MainInterface/submit_assignment.html', context)

@login_required
def view_submissions_view(request):
    """View student's assignment submissions"""
    try:
        if request.user.userprofile.user_type != 'student':
            messages.error(request, 'Access denied. Student access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    # Get all submissions by the student
    submissions = AssignmentSubmission.objects.filter(
        student=request.user
    ).select_related('assignment', 'assignment__course').order_by('-submitted_at')
    
    # Filter by status if requested
    status_filter = request.GET.get('status')
    if status_filter:
        submissions = submissions.filter(status=status_filter)
    
    # Group submissions by course
    submissions_by_course = {}
    for submission in submissions:
        course = submission.assignment.course
        if course not in submissions_by_course:
            submissions_by_course[course] = []
        submissions_by_course[course].append(submission)
    
    # Calculate statistics
    total_submissions = submissions.count()
    submitted_count = submissions.filter(status='submitted').count()
    graded_count = submissions.filter(status='graded').count()
    draft_count = submissions.filter(status='draft').count()
    
    context = {
        'submissions_by_course': submissions_by_course,
        'total_submissions': total_submissions,
        'submitted_count': submitted_count,
        'graded_count': graded_count,
        'draft_count': draft_count,
        'selected_status': status_filter,
    }
    
    return render(request, 'MainInterface/view_submissions.html', context)

@login_required
def lecturer_assignments_view(request):
    """View assignments for lecturers to manage"""
    try:
        if request.user.userprofile.user_type != 'lecturer':
            messages.error(request, 'Access denied. Lecturer access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    # Get lecturer's courses
    courses = Course.objects.filter(lecturer=request.user.userprofile)
    
    # Get assignments for lecturer's courses
    assignments = Assignment.objects.filter(
        course__in=courses
    ).select_related('course').order_by('-created_at')
    
    # Get submission statistics for each assignment
    for assignment in assignments:
        assignment.total_submissions = assignment.submissions.count()
        assignment.pending_submissions = assignment.submissions.filter(status='submitted').count()
        assignment.graded_submissions = assignment.submissions.filter(status='graded').count()
    
    # Calculate overall statistics
    total_assignments = assignments.count()
    published_assignments = assignments.filter(status='published').count()
    total_submissions = sum(a.total_submissions for a in assignments)
    pending_grading = sum(a.pending_submissions for a in assignments)
    
    context = {
        'assignments': assignments,
        'courses': courses,
        'total_assignments': total_assignments,
        'published_assignments': published_assignments,
        'total_submissions': total_submissions,
        'pending_grading': pending_grading,
    }
    
    return render(request, 'MainInterface/lecturer_assignments.html', context)

@login_required
def create_assignment_view(request):
    """Create a new assignment (lecturer only)"""
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
        due_date = request.POST.get('due_date', '').strip()
        max_points = request.POST.get('max_points', '100')
        status = request.POST.get('status', 'draft')
        instructions = request.POST.get('instructions', '').strip()
        allowed_file_types = request.POST.get('allowed_file_types', 'pdf,doc,docx,txt').strip()
        max_file_size = request.POST.get('max_file_size', '10485760')
        late_submission_allowed = request.POST.get('late_submission_allowed') == 'on'
        late_penalty_per_day = request.POST.get('late_penalty_per_day', '10.0')
        
        # Validation
        if not all([title, description, course_id, due_date]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'MainInterface/create_assignment.html', {'courses': courses})
        
        # Validate course belongs to lecturer
        try:
            course = Course.objects.get(id=course_id, lecturer=request.user.userprofile)
        except Course.DoesNotExist:
            messages.error(request, 'Invalid course selected.')
            return render(request, 'MainInterface/create_assignment.html', {'courses': courses})
        
        # Parse due date
        try:
            from django.utils.dateparse import parse_datetime
            from django.utils import timezone as django_timezone
            from datetime import datetime
            
            # Parse the datetime string and make it timezone aware
            due_date_obj = datetime.strptime(due_date, '%Y-%m-%dT%H:%M')
            due_date_obj = django_timezone.make_aware(due_date_obj)
        except ValueError:
            messages.error(request, 'Invalid due date format.')
            return render(request, 'MainInterface/create_assignment.html', {'courses': courses})
        
        # Validate numeric fields
        try:
            max_points = float(max_points)
            max_file_size = int(max_file_size)
            late_penalty_per_day = float(late_penalty_per_day)
        except ValueError:
            messages.error(request, 'Invalid numeric values.')
            return render(request, 'MainInterface/create_assignment.html', {'courses': courses})
        
        try:
            # Create assignment
            assignment = Assignment.objects.create(
                title=title,
                description=description,
                course=course,
                created_by=request.user,
                due_date=due_date_obj,
                max_points=max_points,
                status=status,
                instructions=instructions,
                allowed_file_types=allowed_file_types,
                max_file_size=max_file_size,
                late_submission_allowed=late_submission_allowed,
                late_penalty_per_day=late_penalty_per_day
            )
            
            messages.success(request, f'Assignment "{title}" has been created successfully!')
            return redirect('lecturer_assignments')
            
        except Exception as e:
            messages.error(request, f'An error occurred while creating the assignment: {str(e)}')
    
    context = {
        'courses': courses,
    }
    
    return render(request, 'MainInterface/create_assignment.html', context)

@login_required
def assignment_submissions_view(request, assignment_id):
    """View all submissions for a specific assignment (lecturer view)"""
    try:
        if request.user.userprofile.user_type != 'lecturer':
            messages.error(request, 'Access denied. Lecturer access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    assignment = get_object_or_404(Assignment, id=assignment_id)
    
    # Check if lecturer owns this assignment
    if assignment.course.lecturer != request.user.userprofile:
        messages.error(request, 'You do not have permission to view this assignment.')
        return redirect('lecturer_assignments')
    
    # Get all submissions for this assignment
    submissions = AssignmentSubmission.objects.filter(
        assignment=assignment
    ).select_related('student').order_by('-submitted_at')
    
    # Filter by status if requested
    status_filter = request.GET.get('status')
    if status_filter:
        submissions = submissions.filter(status=status_filter)
    
    # Calculate statistics
    total_students = Enrollment.objects.filter(
        course=assignment.course, 
        status='enrolled'
    ).count()
    total_submissions = submissions.count()
    submitted_count = submissions.filter(status='submitted').count()
    graded_count = submissions.filter(status='graded').count()
    late_submissions = submissions.filter(late_submission=True).count()
    
    context = {
        'assignment': assignment,
        'submissions': submissions,
        'total_students': total_students,
        'total_submissions': total_submissions,
        'submitted_count': submitted_count,
        'graded_count': graded_count,
        'late_submissions': late_submissions,
        'selected_status': status_filter,
    }
    
    return render(request, 'MainInterface/assignment_submissions.html', context)

@login_required
def download_submission_view(request, submission_id):
    """Download a submission file"""
    submission = get_object_or_404(AssignmentSubmission, id=submission_id)
    
    # Check permissions
    can_access = False
    if hasattr(request.user, 'userprofile'):
        # Student can download their own submissions
        if request.user.userprofile.user_type == 'student' and submission.student == request.user:
            can_access = True
        # Lecturer can download submissions for their assignments
        elif request.user.userprofile.user_type == 'lecturer' and submission.assignment.course.lecturer == request.user.userprofile:
            can_access = True
        # Admin can download any submission
        elif request.user.userprofile.user_type == 'admin':
            can_access = True
    
    if not can_access:
        messages.error(request, 'You do not have permission to download this file.')
        return redirect('dashboard')
    
    if not submission.submission_file:
        messages.error(request, 'No file attached to this submission.')
        return redirect('view_submissions')
    
    try:
        response = HttpResponse(submission.submission_file.read(), content_type='application/octet-stream')
        filename = submission.original_filename or submission.submission_file.name.split('/')[-1]
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        messages.error(request, 'Error downloading file.')
        return redirect('view_submissions')

@login_required
def grade_submission_view(request, submission_id):
    """Grade an assignment submission (lecturer view)"""
    try:
        if request.user.userprofile.user_type != 'lecturer':
            messages.error(request, 'Access denied. Lecturer access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    submission = get_object_or_404(AssignmentSubmission, id=submission_id)
    
    # Check if lecturer owns this assignment
    if submission.assignment.course.lecturer != request.user.userprofile:
        messages.error(request, 'You do not have permission to grade this submission.')
        return redirect('lecturer_assignments')
    
    if request.method == 'POST':
        try:
            grade = request.POST.get('grade', '').strip()
            feedback = request.POST.get('feedback', '').strip()
            
            # Validate grade
            if grade:
                grade_value = float(grade)
                if grade_value < 0 or grade_value > float(submission.assignment.max_points):
                    messages.error(request, f'Grade must be between 0 and {submission.assignment.max_points}.')
                    return render(request, 'MainInterface/grade_submission.html', {'submission': submission})
                
                # Update submission
                submission.grade = grade_value
                submission.feedback = feedback
                submission.graded_by = request.user
                submission.graded_at = timezone.now()
                submission.status = 'graded'
                submission.save()
                
                messages.success(request, f'Successfully graded submission for {submission.get_student_name()}.')
                return redirect('assignment_submissions', assignment_id=submission.assignment.id)
            else:
                messages.error(request, 'Please enter a valid grade.')
        
        except ValueError:
            messages.error(request, 'Please enter a valid numeric grade.')
        except Exception as e:
            messages.error(request, f'An error occurred while grading: {str(e)}')
    
    context = {
        'submission': submission,
        'assignment': submission.assignment,
    }
    
    return render(request, 'MainInterface/grade_submission.html', context)

@login_required
def academic_progress_view(request):
    """View academic progress for students"""
    try:
        if request.user.userprofile.user_type != 'student':
            messages.error(request, 'Access denied. Student access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    # Get student's enrolled courses
    enrolled_courses = Course.objects.filter(
        enrollments__student=request.user,
        enrollments__status='enrolled'
    ).prefetch_related('grades', 'assignments', 'assignments__submissions')
    
    # Calculate progress for each course
    course_progress = []
    overall_stats = {
        'total_courses': 0,
        'total_credits': 0,
        'completed_credits': 0,
        'total_assignments': 0,
        'completed_assignments': 0,
        'average_grade': 0,
        'gpa': 0
    }
    
    for course in enrolled_courses:
        # Get grades for this course
        course_grades = Grade.objects.filter(
            student=request.user,
            course=course
        ).order_by('-date_graded')
        
        # Get assignments for this course
        course_assignments = Assignment.objects.filter(
            course=course,
            status='published'
        )
        
        # Get submissions for this course
        course_submissions = AssignmentSubmission.objects.filter(
            student=request.user,
            assignment__course=course
        )
        
        # Calculate assignment completion rate
        total_assignments = course_assignments.count()
        completed_assignments = course_submissions.filter(status='submitted').count()
        assignment_completion = (completed_assignments / total_assignments * 100) if total_assignments > 0 else 0
        
        # Calculate grade statistics
        graded_assignments = course_submissions.filter(status='graded', grade__isnull=False)
        if graded_assignments.exists():
            grades_sum = sum(float(sub.grade) for sub in graded_assignments)
            average_grade = grades_sum / graded_assignments.count()
        else:
            average_grade = 0
        
        # Get final grade if available
        final_grade = course_grades.filter(grade_type='final_grade').first()
        final_grade_value = final_grade.grade_value if final_grade else None
        final_grade_points = Grade.GRADE_POINTS.get(final_grade_value, 0) if final_grade_value else 0
        
        # Calculate overall progress based on assignments and grades
        progress_percentage = 0
        if total_assignments > 0:
            # 70% weight for assignment completion, 30% for average grade
            assignment_weight = 0.7
            grade_weight = 0.3
            
            progress_percentage = (
                (assignment_completion * assignment_weight) +
                (average_grade * grade_weight)
            )
            progress_percentage = min(progress_percentage, 100)  # Cap at 100%
        
        # Determine progress status
        if progress_percentage >= 80:
            progress_status = 'excellent'
        elif progress_percentage >= 60:
            progress_status = 'good'
        elif progress_percentage >= 40:
            progress_status = 'average'
        else:
            progress_status = 'needs_improvement'
        
        course_data = {
            'course': course,
            'total_assignments': total_assignments,
            'completed_assignments': completed_assignments,
            'assignment_completion': round(assignment_completion, 1),
            'average_grade': round(average_grade, 1),
            'final_grade': final_grade_value,
            'final_grade_points': final_grade_points,
            'progress_percentage': round(progress_percentage, 1),
            'progress_status': progress_status,
            'recent_grades': course_grades[:5],
            'pending_assignments': course_assignments.filter(
                due_date__gte=timezone.now()
            ).exclude(
                id__in=course_submissions.filter(status='submitted').values_list('assignment_id', flat=True)
            ).count()
        }
        
        course_progress.append(course_data)
        
        # Update overall stats
        overall_stats['total_courses'] += 1
        overall_stats['total_credits'] += course.credits
        if final_grade_value and final_grade_points > 0:
            overall_stats['completed_credits'] += course.credits
        overall_stats['total_assignments'] += total_assignments
        overall_stats['completed_assignments'] += completed_assignments
    
    # Calculate overall GPA
    total_grade_points = 0
    total_credits_with_grades = 0
    for course_data in course_progress:
        if course_data['final_grade_points'] > 0:
            total_grade_points += course_data['final_grade_points'] * course_data['course'].credits
            total_credits_with_grades += course_data['course'].credits
    
    overall_stats['gpa'] = round(total_grade_points / total_credits_with_grades, 2) if total_credits_with_grades > 0 else 0
    overall_stats['average_grade'] = round(
        sum(course_data['average_grade'] for course_data in course_progress) / len(course_progress), 1
    ) if course_progress else 0
    
    # Calculate completion percentage
    completion_percentage = (overall_stats['completed_credits'] / overall_stats['total_credits'] * 100) if overall_stats['total_credits'] > 0 else 0
    overall_stats['completion_percentage'] = round(completion_percentage, 1)
    
    # Get recent activity (recent grades and submissions)
    recent_grades = Grade.objects.filter(
        student=request.user
    ).select_related('course').order_by('-date_graded')[:10]
    
    recent_submissions = AssignmentSubmission.objects.filter(
        student=request.user,
        status='submitted'
    ).select_related('assignment', 'assignment__course').order_by('-submitted_at')[:10]
    
    context = {
        'course_progress': course_progress,
        'overall_stats': overall_stats,
        'recent_grades': recent_grades,
        'recent_submissions': recent_submissions,
    }
    
    return render(request, 'MainInterface/academic_progress.html', context)

@login_required
def download_progress_report(request):
    """Generate and download PDF progress report"""
    try:
        if request.user.userprofile.user_type != 'student':
            messages.error(request, 'Access denied. Student access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    # Get the same data as the progress view
    enrolled_courses = Course.objects.filter(
        enrollments__student=request.user,
        enrollments__status='enrolled'
    ).prefetch_related('grades', 'assignments', 'assignments__submissions')
    
    # Calculate progress for each course (same logic as progress view)
    course_progress = []
    overall_stats = {
        'total_courses': 0,
        'total_credits': 0,
        'completed_credits': 0,
        'total_assignments': 0,
        'completed_assignments': 0,
        'average_grade': 0,
        'gpa': 0
    }
    
    for course in enrolled_courses:
        # Get grades for this course
        course_grades = Grade.objects.filter(
            student=request.user,
            course=course
        ).order_by('-date_graded')
        
        # Get assignments for this course
        course_assignments = Assignment.objects.filter(
            course=course,
            status='published'
        )
        
        # Get submissions for this course
        course_submissions = AssignmentSubmission.objects.filter(
            student=request.user,
            assignment__course=course
        )
        
        # Calculate assignment completion rate
        total_assignments = course_assignments.count()
        completed_assignments = course_submissions.filter(status='submitted').count()
        assignment_completion = (completed_assignments / total_assignments * 100) if total_assignments > 0 else 0
        
        # Calculate grade statistics
        graded_assignments = course_submissions.filter(status='graded', grade__isnull=False)
        if graded_assignments.exists():
            grades_sum = sum(float(sub.grade) for sub in graded_assignments)
            average_grade = grades_sum / graded_assignments.count()
        else:
            average_grade = 0
        
        # Get final grade if available
        final_grade = course_grades.filter(grade_type='final_grade').first()
        final_grade_value = final_grade.grade_value if final_grade else None
        final_grade_points = Grade.GRADE_POINTS.get(final_grade_value, 0) if final_grade_value else 0
        
        # Calculate overall progress
        progress_percentage = 0
        if total_assignments > 0:
            assignment_weight = 0.7
            grade_weight = 0.3
            progress_percentage = (
                (assignment_completion * assignment_weight) +
                (average_grade * grade_weight)
            )
            progress_percentage = min(progress_percentage, 100)
        
        # Determine progress status
        if progress_percentage >= 80:
            progress_status = 'Excellent'
        elif progress_percentage >= 60:
            progress_status = 'Good'
        elif progress_percentage >= 40:
            progress_status = 'Average'
        else:
            progress_status = 'Needs Improvement'
        
        course_data = {
            'course': course,
            'total_assignments': total_assignments,
            'completed_assignments': completed_assignments,
            'assignment_completion': round(assignment_completion, 1),
            'average_grade': round(average_grade, 1),
            'final_grade': final_grade_value,
            'final_grade_points': final_grade_points,
            'progress_percentage': round(progress_percentage, 1),
            'progress_status': progress_status,
            'recent_grades': course_grades[:5],
        }
        
        course_progress.append(course_data)
        
        # Update overall stats
        overall_stats['total_courses'] += 1
        overall_stats['total_credits'] += course.credits
        if final_grade_value and final_grade_points > 0:
            overall_stats['completed_credits'] += course.credits
        overall_stats['total_assignments'] += total_assignments
        overall_stats['completed_assignments'] += completed_assignments
    
    # Calculate overall GPA
    total_grade_points = 0
    total_credits_with_grades = 0
    for course_data in course_progress:
        if course_data['final_grade_points'] > 0:
            total_grade_points += course_data['final_grade_points'] * course_data['course'].credits
            total_credits_with_grades += course_data['course'].credits
    
    overall_stats['gpa'] = round(total_grade_points / total_credits_with_grades, 2) if total_credits_with_grades > 0 else 0
    overall_stats['average_grade'] = round(
        sum(course_data['average_grade'] for course_data in course_progress) / len(course_progress), 1
    ) if course_progress else 0
    
    completion_percentage = (overall_stats['completed_credits'] / overall_stats['total_credits'] * 100) if overall_stats['total_credits'] > 0 else 0
    overall_stats['completion_percentage'] = round(completion_percentage, 1)
    
    # Create PDF
    response = HttpResponse(content_type='application/pdf')
    filename = f"academic_progress_report_{request.user.username}_{datetime.now().strftime('%Y%m%d')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Create PDF document
    doc = SimpleDocTemplate(response, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#007bff')
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        textColor=colors.HexColor('#333333')
    )
    
    # Header
    story.append(Paragraph("Academic Progress Report", title_style))
    story.append(Spacer(1, 12))
    
    # Student information
    student_info = [
        ['Student Name:', f"{request.user.get_full_name() or request.user.username}"],
        ['Student ID:', request.user.username],
        ['Report Date:', datetime.now().strftime('%B %d, %Y')],
        ['Academic Year:', '2025']
    ]
    
    student_table = Table(student_info, colWidths=[2*inch, 3*inch])
    student_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(student_table)
    story.append(Spacer(1, 20))
    
    # Overall Statistics
    story.append(Paragraph("Overall Academic Summary", heading_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#007bff')))
    story.append(Spacer(1, 12))
    
    overall_data = [
        ['Metric', 'Value'],
        ['Current GPA', f"{overall_stats['gpa']}/4.0"],
        ['Completion Rate', f"{overall_stats['completion_percentage']}%"],
        ['Credits Completed', f"{overall_stats['completed_credits']}/{overall_stats['total_credits']}"],
        ['Assignments Completed', f"{overall_stats['completed_assignments']}/{overall_stats['total_assignments']}"],
        ['Average Grade', f"{overall_stats['average_grade']}%"]
    ]
    
    overall_table = Table(overall_data, colWidths=[2.5*inch, 2.5*inch])
    overall_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007bff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(overall_table)
    story.append(Spacer(1, 20))
    
    # Course Progress
    story.append(Paragraph("Course Progress Details", heading_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#007bff')))
    story.append(Spacer(1, 12))
    
    if course_progress:
        course_data = [['Course', 'Progress', 'Assignments', 'Avg Grade', 'Final Grade', 'Status']]
        
        for course_info in course_progress:
            course_data.append([
                f"{course_info['course'].course_code}\n{course_info['course'].course_name}",
                f"{course_info['progress_percentage']}%",
                f"{course_info['completed_assignments']}/{course_info['total_assignments']}",
                f"{course_info['average_grade']}%",
                course_info['final_grade'] or 'N/A',
                course_info['progress_status']
            ])
        
        course_table = Table(course_data, colWidths=[2*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 1*inch])
        course_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007bff')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(course_table)
    else:
        story.append(Paragraph("No courses enrolled.", styles['Normal']))
    
    story.append(Spacer(1, 20))
    
    # Performance Insights
    story.append(Paragraph("Performance Insights", heading_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#007bff')))
    story.append(Spacer(1, 12))
    
    if overall_stats['gpa'] >= 3.5:
        insight_text = f"<b>Excellent Performance!</b> You're maintaining a high GPA of {overall_stats['gpa']}. Keep up the great work!"
        insight_color = colors.HexColor('#28a745')
    elif overall_stats['gpa'] >= 3.0:
        insight_text = f"<b>Good Progress!</b> Your GPA of {overall_stats['gpa']} shows solid academic performance. Consider focusing on areas for improvement."
        insight_color = colors.HexColor('#17a2b8')
    elif overall_stats['gpa'] >= 2.0:
        insight_text = f"<b>Room for Improvement.</b> Your GPA of {overall_stats['gpa']} suggests you should focus more on your studies and seek help if needed."
        insight_color = colors.HexColor('#ffc107')
    elif overall_stats['gpa'] > 0:
        insight_text = f"<b>Needs Attention!</b> Your GPA of {overall_stats['gpa']} requires immediate attention. Consider meeting with academic advisors."
        insight_color = colors.HexColor('#dc3545')
    else:
        insight_text = "No grades available yet. Keep working on your assignments and exams."
        insight_color = colors.HexColor('#6c757d')
    
    insight_style = ParagraphStyle(
        'InsightStyle',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=12,
        leftIndent=20,
        rightIndent=20,
        textColor=insight_color
    )
    
    story.append(Paragraph(insight_text, insight_style))
    story.append(Spacer(1, 12))
    
    # Recommendations
    recommendations = []
    if overall_stats['completed_assignments'] < overall_stats['total_assignments']:
        pending = overall_stats['total_assignments'] - overall_stats['completed_assignments']
        recommendations.append(f"• Complete {pending} pending assignment{'s' if pending > 1 else ''}")
    
    if overall_stats['gpa'] < 3.0:
        recommendations.append("• Consider attending office hours for additional help")
        recommendations.append("• Form study groups with classmates")
        recommendations.append("• Utilize campus tutoring resources")
    
    if overall_stats['completion_percentage'] < 100:
        recommendations.append("• Stay consistent with course attendance")
        recommendations.append("• Keep track of assignment due dates")
    
    if recommendations:
        story.append(Paragraph("Recommendations:", heading_style))
        for rec in recommendations:
            story.append(Paragraph(rec, styles['Normal']))
            story.append(Spacer(1, 6))
    
    # Footer
    story.append(Spacer(1, 30))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_CENTER,
        textColor=colors.grey
    )
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
    story.append(Spacer(1, 12))
    story.append(Paragraph("This report was generated automatically by the Database System.", footer_style))
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", footer_style))
    
    # Build PDF
    doc.build(story)
    
    return response


@login_required
def student_management_view(request):
    """View for lecturers to manage students and view enrollment reports"""
    try:
        # Check if user is a lecturer
        if request.user.userprofile.user_type != 'lecturer':
            messages.error(request, 'Access denied. Lecturer access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    # Get lecturer's courses
    lecturer_courses = Course.objects.filter(lecturer=request.user.userprofile)
    
    # Get all enrollments for lecturer's courses
    enrollments = Enrollment.objects.filter(
        course__in=lecturer_courses
    ).select_related('student', 'course').order_by('course__course_code', 'student__last_name')
    
    # Filter by course if specified
    course_filter = request.GET.get('course')
    if course_filter:
        enrollments = enrollments.filter(course_id=course_filter)
    
    # Filter by status if specified
    status_filter = request.GET.get('status')
    if status_filter:
        enrollments = enrollments.filter(status=status_filter)
    
    # Search by student name
    search_query = request.GET.get('search')
    if search_query:
        enrollments = enrollments.filter(
            student__first_name__icontains=search_query
        ) | enrollments.filter(
            student__last_name__icontains=search_query
        )
    
    # Calculate statistics
    total_students = enrollments.filter(status='enrolled').count()
    pending_enrollments = enrollments.filter(status='pending').count()
    waitlisted_students = enrollments.filter(status='waitlisted').count()
    
    # Group enrollments by course for better organization
    course_enrollments = {}
    for enrollment in enrollments:
        course_code = enrollment.course.course_code
        if course_code not in course_enrollments:
            course_enrollments[course_code] = {
                'course': enrollment.course,
                'enrollments': []
            }
        course_enrollments[course_code]['enrollments'].append(enrollment)
    
    context = {
        'enrollments': enrollments,
        'course_enrollments': course_enrollments,
        'lecturer_courses': lecturer_courses,
        'total_students': total_students,
        'pending_enrollments': pending_enrollments,
        'waitlisted_students': waitlisted_students,
        'course_filter': course_filter,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'MainInterface/student_management.html', context)


@login_required
def download_enrollment_report(request):
    """Generate and download enrollment report as PDF"""
    try:
        # Check if user is a lecturer
        if request.user.userprofile.user_type != 'lecturer':
            messages.error(request, 'Access denied. Lecturer access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    # Create HTTP response with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="enrollment_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
    
    # Create PDF
    doc = SimpleDocTemplate(response, pagesize=letter, 
                          rightMargin=72, leftMargin=72, 
                          topMargin=72, bottomMargin=18)
    
    # Container for the 'Flowable' objects
    story = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#2c3e50')
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        textColor=colors.HexColor('#2c3e50')
    )
    
    # Title
    story.append(Paragraph("Student Enrollment Report", title_style))
    story.append(Paragraph(f"Lecturer: {request.user.get_full_name()}", styles['Normal']))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Get lecturer's courses and enrollments
    lecturer_courses = Course.objects.filter(lecturer=request.user.userprofile)
    
    # Summary statistics
    story.append(Paragraph("Summary Statistics", heading_style))
    
    total_courses = lecturer_courses.count()
    total_enrollments = Enrollment.objects.filter(course__in=lecturer_courses, status='enrolled').count()
    pending_enrollments = Enrollment.objects.filter(course__in=lecturer_courses, status='pending').count()
    waitlisted_students = Enrollment.objects.filter(course__in=lecturer_courses, status='waitlisted').count()
    
    summary_data = [
        ['Metric', 'Count'],
        ['Total Courses', str(total_courses)],
        ['Total Enrolled Students', str(total_enrollments)],
        ['Pending Enrollments', str(pending_enrollments)],
        ['Waitlisted Students', str(waitlisted_students)],
    ]
    
    summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(summary_table)
    story.append(Spacer(1, 20))
    
    # Course-by-course breakdown
    story.append(Paragraph("Enrollment Details by Course", heading_style))
    
    for course in lecturer_courses:
        story.append(Paragraph(f"Course: {course.course_code} - {course.course_name}", styles['Heading3']))
        
        enrollments = Enrollment.objects.filter(course=course).select_related('student')
        
        if enrollments.exists():
            # Create table data
            enrollment_data = [['Student Name', 'Email', 'Status', 'Enrollment Date']]
            
            for enrollment in enrollments:
                student_name = f"{enrollment.student.first_name} {enrollment.student.last_name}"
                enrollment_data.append([
                    student_name,
                    enrollment.student.email,
                    enrollment.status.title(),
                    enrollment.enrollment_date.strftime('%Y-%m-%d')
                ])
            
            # Create table
            enrollment_table = Table(enrollment_data, colWidths=[2*inch, 2.5*inch, 1*inch, 1.5*inch])
            enrollment_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#28a745')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
            ]))
            
            story.append(enrollment_table)
        else:
            story.append(Paragraph("No enrollments for this course.", styles['Normal']))
        
        story.append(Spacer(1, 15))
    
    # Footer
    story.append(Spacer(1, 30))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_CENTER,
        textColor=colors.grey
    )
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
    story.append(Spacer(1, 12))
    story.append(Paragraph("This report was generated automatically by the Database System.", footer_style))
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", footer_style))
    
    # Build PDF
    doc.build(story)
    
    return response


@login_required
def approve_enrollment_view(request, enrollment_id):
    """Approve a pending enrollment"""
    if request.method == 'POST':
        try:
            # Check if user is a lecturer
            if request.user.userprofile.user_type != 'lecturer':
                return JsonResponse({'success': False, 'error': 'Access denied'})
            
            enrollment = get_object_or_404(Enrollment, id=enrollment_id)
            
            # Check if the lecturer owns this course
            if enrollment.course.lecturer != request.user.userprofile:
                return JsonResponse({'success': False, 'error': 'Access denied'})
            
            # Check if course has space
            if enrollment.course.get_enrolled_count() >= enrollment.course.max_students:
                return JsonResponse({'success': False, 'error': 'Course is full'})
            
            # Approve the enrollment
            enrollment.status = 'enrolled'
            enrollment.save()
            
            return JsonResponse({'success': True, 'message': 'Enrollment approved successfully'})
            
        except UserProfile.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User profile not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def reject_enrollment_view(request, enrollment_id):
    """Reject a pending enrollment"""
    if request.method == 'POST':
        try:
            # Check if user is a lecturer
            if request.user.userprofile.user_type != 'lecturer':
                return JsonResponse({'success': False, 'error': 'Access denied'})
            
            enrollment = get_object_or_404(Enrollment, id=enrollment_id)
            
            # Check if the lecturer owns this course
            if enrollment.course.lecturer != request.user.userprofile:
                return JsonResponse({'success': False, 'error': 'Access denied'})
            
            # Reject the enrollment by deleting it
            enrollment.delete()
            
            return JsonResponse({'success': True, 'message': 'Enrollment rejected successfully'})
            
        except UserProfile.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User profile not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def approve_enrollment_view(request, enrollment_id):
    """Approve a pending enrollment"""
    if request.method == 'POST':
        try:
            # Check if user is a lecturer
            if request.user.userprofile.user_type != 'lecturer':
                return JsonResponse({'success': False, 'error': 'Access denied'})
            
            enrollment = get_object_or_404(Enrollment, id=enrollment_id)
            
            # Check if the lecturer owns this course
            if enrollment.course.lecturer != request.user.userprofile:
                return JsonResponse({'success': False, 'error': 'Access denied'})
            
            # Check if course has space
            if enrollment.course.get_enrolled_count() >= enrollment.course.max_students:
                return JsonResponse({'success': False, 'error': 'Course is full'})
            
            # Approve the enrollment
            enrollment.status = 'enrolled'
            enrollment.save()
            
            return JsonResponse({'success': True, 'message': 'Enrollment approved successfully'})
            
        except UserProfile.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User profile not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def reject_enrollment_view(request, enrollment_id):
    """Reject a pending enrollment"""
    if request.method == 'POST':
        try:
            # Check if user is a lecturer
            if request.user.userprofile.user_type != 'lecturer':
                return JsonResponse({'success': False, 'error': 'Access denied'})
            
            enrollment = get_object_or_404(Enrollment, id=enrollment_id)
            
            # Check if the lecturer owns this course
            if enrollment.course.lecturer != request.user.userprofile:
                return JsonResponse({'success': False, 'error': 'Access denied'})
            
            # Reject the enrollment by deleting it
            enrollment.delete()
            
            return JsonResponse({'success': True, 'message': 'Enrollment rejected successfully'})
            
        except UserProfile.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User profile not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})
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


# Academic Reports Views
@login_required
def academic_reports_view(request):
    """
    Academic reports page - allows lecturers to select students and generate reports
    """
    user_profile = request.user.userprofile
    
    # Only allow lecturers and admins
    if user_profile.user_type not in ['lecturer', 'admin']:
        messages.error(request, 'Access denied. Only lecturers can access academic reports.')
        return redirect('dashboard')
    
    # Get all courses taught by this lecturer (or all if admin)
    if user_profile.user_type == 'admin':
        courses = Course.objects.filter(is_active=True).order_by('course_name')
    else:
        courses = Course.objects.filter(lecturer=user_profile, is_active=True).order_by('course_name')
    
    # Get students if a course is selected
    selected_course_id = request.GET.get('course_id')
    students = None
    selected_course = None
    
    if selected_course_id:
        try:
            if user_profile.user_type == 'admin':
                selected_course = Course.objects.get(id=selected_course_id, is_active=True)
            else:
                selected_course = Course.objects.get(id=selected_course_id, lecturer=user_profile, is_active=True)
            
            # Get enrolled students
            enrollments = Enrollment.objects.filter(course=selected_course).select_related('student__userprofile')
            students = [enrollment.student for enrollment in enrollments]
            
        except Course.DoesNotExist:
            messages.error(request, 'Course not found or you do not have access to it.')
    
    context = {
        'courses': courses,
        'selected_course': selected_course,
        'students': students,
        'selected_course_id': selected_course_id,
    }
    
    return render(request, 'MainInterface/academic_reports.html', context)


@login_required
def generate_student_report(request, student_id):
    """
    Generate a comprehensive academic report for a specific student
    """
    user_profile = request.user.userprofile
    
    # Only allow lecturers and admins
    if user_profile.user_type not in ['lecturer', 'admin']:
        messages.error(request, 'Access denied. Only lecturers can generate reports.')
        return redirect('dashboard')
    
    # Get the student
    try:
        student = User.objects.get(id=student_id, userprofile__user_type='student')
    except User.DoesNotExist:
        messages.error(request, 'Student not found.')
        return redirect('academic_reports')
    
    # Get course context (if specified)
    course_id = request.GET.get('course_id')
    selected_course = None
    
    if course_id:
        try:
            if user_profile.user_type == 'admin':
                selected_course = Course.objects.get(id=course_id, is_active=True)
            else:
                selected_course = Course.objects.get(id=course_id, lecturer=user_profile, is_active=True)
        except Course.DoesNotExist:
            messages.error(request, 'Course not found or you do not have access to it.')
            return redirect('academic_reports')
    
    # Verify the lecturer has access to this student
    if user_profile.user_type == 'lecturer':
        if selected_course:
            # Check if student is enrolled in the specific course
            if not Enrollment.objects.filter(student=student, course=selected_course).exists():
                messages.error(request, 'Student is not enrolled in this course.')
                return redirect('academic_reports')
        else:
            # Check if student is enrolled in any course taught by this lecturer
            lecturer_courses = Course.objects.filter(lecturer=user_profile, is_active=True)
            student_enrollments = Enrollment.objects.filter(
                student=student,
                course__in=lecturer_courses
            )
            if not student_enrollments.exists():
                messages.error(request, 'You do not have access to this student\'s records.')
                return redirect('academic_reports')
    
    # Generate the report
    from django.http import HttpResponse
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from datetime import datetime
    
    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="academic_report_{student.username}_{datetime.now().strftime("%Y%m%d")}.pdf"'
    
    # Create the PDF document
    doc = SimpleDocTemplate(response, pagesize=A4, topMargin=1*inch)
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.darkblue
    )
    
    # Story list to hold all elements
    story = []
    
    # Report title
    if selected_course:
        title = f"Academic Report - {student.get_full_name() or student.username}<br/>{selected_course.course_name}"
    else:
        title = f"Comprehensive Academic Report<br/>{student.get_full_name() or student.username}"
    
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 20))
    
    # Student Information
    story.append(Paragraph("Student Information", heading_style))
    
    student_info = [
        ["Full Name:", student.get_full_name() or "N/A"],
        ["Username:", student.username],
        ["Email:", student.email],
        ["User ID:", str(student.id)],
        ["Report Generated:", datetime.now().strftime("%B %d, %Y at %I:%M %p")],
        ["Generated By:", request.user.get_full_name() or request.user.username]
    ]
    
    info_table = Table(student_info, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    story.append(info_table)
    story.append(Spacer(1, 20))
    
    # Course Enrollments and Grades
    if selected_course:
        enrollments = Enrollment.objects.filter(student=student, course=selected_course)
    else:
        enrollments = Enrollment.objects.filter(student=student).select_related('course')
    
    if enrollments.exists():
        story.append(Paragraph("Course Enrollments", heading_style))
        
        enrollment_data = [["Course", "Instructor", "Enrollment Date", "Current Grade"]]
        
        for enrollment in enrollments:
            # Get the latest grade for this course
            latest_grade = Grade.objects.filter(
                student=student,
                course=enrollment.course
            ).order_by('-date_graded').first()
            
            grade_display = f"{latest_grade.grade_value}%" if latest_grade else "No grades recorded"
            
            enrollment_data.append([
                enrollment.course.course_name,
                enrollment.course.lecturer.user.get_full_name() or enrollment.course.lecturer.user.username,
                enrollment.enrollment_date.strftime("%B %d, %Y"),
                grade_display
            ])
        
        enrollment_table = Table(enrollment_data, colWidths=[2*inch, 1.8*inch, 1.2*inch, 1*inch])
        enrollment_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(enrollment_table)
        story.append(Spacer(1, 20))
    
    # Assignment Performance
    if selected_course:
        assignments = Assignment.objects.filter(course=selected_course).order_by('-due_date')
    else:
        # Get assignments from all courses the student is enrolled in
        enrolled_courses = [enrollment.course for enrollment in enrollments]
        assignments = Assignment.objects.filter(course__in=enrolled_courses).order_by('-due_date')
    
    if assignments.exists():
        story.append(Paragraph("Assignment Performance", heading_style))
        
        assignment_data = [["Assignment", "Course", "Due Date", "Submission Status", "Grade"]]
        
        for assignment in assignments[:10]:  # Limit to last 10 assignments
            try:
                submission = AssignmentSubmission.objects.get(assignment=assignment, student=student)
                submission_status = "Submitted" if submission.submission_file else "Submitted (No File)"
                submission_date = submission.submitted_at.strftime("%m/%d/%Y") if submission.submitted_at else "N/A"
            except AssignmentSubmission.DoesNotExist:
                submission_status = "Not Submitted"
                submission_date = "N/A"
            
            # Get grade for this assignment (check by description or assignment type)
            assignment_grade = Grade.objects.filter(
                student=student,
                course=assignment.course,
                grade_type='assignment',
                description__icontains=assignment.title
            ).first()
            
            # If no specific grade found, check for assignment grades in this course
            if not assignment_grade:
                assignment_grade = Grade.objects.filter(
                    student=student,
                    course=assignment.course,
                    grade_type='assignment'
                ).first()
            
            grade_display = f"{assignment_grade.grade_value}%" if assignment_grade else "Not Graded"
            
            assignment_data.append([
                assignment.title[:30] + "..." if len(assignment.title) > 30 else assignment.title,
                assignment.course.course_name[:20] + "..." if len(assignment.course.course_name) > 20 else assignment.course.course_name,
                assignment.due_date.strftime("%m/%d/%Y"),
                submission_status,
                grade_display
            ])
        
        assignment_table = Table(assignment_data, colWidths=[2*inch, 1.5*inch, 1*inch, 1.2*inch, 0.8*inch])
        assignment_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(assignment_table)
        story.append(Spacer(1, 20))
    
    # Grade Summary
    if selected_course:
        grades = Grade.objects.filter(student=student, course=selected_course).order_by('-date_graded')
    else:
        grades = Grade.objects.filter(student=student).order_by('-date_graded')
    
    if grades.exists():
        story.append(Paragraph("Grade Summary", heading_style))
        
        # Calculate average grade
        total_grades = [grade.grade_value for grade in grades if grade.grade_value is not None]
        if total_grades:
            average_grade = sum(total_grades) / len(total_grades)
            story.append(Paragraph(f"<b>Overall Average:</b> {average_grade:.2f}%", styles['Normal']))
            story.append(Spacer(1, 10))
        
        # Recent grades table
        grade_data = [["Course", "Assignment/Exam", "Grade", "Date Recorded"]]
        
        for grade in grades[:15]:  # Last 15 grades
            assignment_name = grade.description if grade.description else f"{grade.get_grade_type_display()}"
            
            grade_data.append([
                grade.course.course_name[:25] + "..." if len(grade.course.course_name) > 25 else grade.course.course_name,
                assignment_name[:30] + "..." if len(assignment_name) > 30 else assignment_name,
                f"{grade.grade_value}%" if grade.grade_value is not None else "N/A",
                grade.date_graded.strftime("%m/%d/%Y")
            ])
        
        grade_table = Table(grade_data, colWidths=[2*inch, 2.5*inch, 0.8*inch, 1*inch])
        grade_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(grade_table)
        story.append(Spacer(1, 20))
    
    # Footer
    story.append(Spacer(1, 30))
    footer_text = f"Report generated on {datetime.now().strftime('%B %d, %Y')} by {request.user.get_full_name() or request.user.username}"
    story.append(Paragraph(footer_text, styles['Normal']))
    
    # Build the PDF
    doc.build(story)
    
    return response

@login_required
def grade_management_view(request):
    """Grade management dashboard for lecturers"""
    try:
        if request.user.userprofile.user_type != 'lecturer':
            messages.error(request, 'Access denied. Lecturer access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    # Get lecturer's courses
    courses = Course.objects.filter(lecturer=request.user.userprofile).prefetch_related('enrollments', 'grades')
    
    # Get selected course for filtering
    selected_course_id = request.GET.get('course')
    selected_course = None
    if selected_course_id:
        try:
            selected_course = courses.get(id=selected_course_id)
        except Course.DoesNotExist:
            pass
    
    # Get grades based on selected course
    if selected_course:
        grades = Grade.objects.filter(course=selected_course).order_by('-date_graded')
        students = User.objects.filter(
            enrollments__course=selected_course,
            enrollments__status='enrolled'
        ).distinct()
    else:
        grades = Grade.objects.filter(course__lecturer=request.user.userprofile).order_by('-date_graded')
        students = User.objects.filter(
            enrollments__course__lecturer=request.user.userprofile,
            enrollments__status='enrolled'
        ).distinct()
    
    # Statistics
    total_students = students.count()
    total_grades = grades.count()
    recent_grades = grades[:10]
    
    # Grade type counts
    grade_types = grades.values('grade_type').annotate(count=Count('grade_type')).order_by('-count')
    
    context = {
        'courses': courses,
        'selected_course': selected_course,
        'grades': recent_grades,
        'students': students[:20],  # Limit to first 20 for display
        'total_students': total_students,
        'total_grades': total_grades,
        'grade_types': grade_types,
    }
    
    return render(request, 'MainInterface/grade_management.html', context)

@login_required
def create_test_view(request):
    """Create a new test/assessment for grading"""
    try:
        if request.user.userprofile.user_type != 'lecturer':
            messages.error(request, 'Access denied. Lecturer access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    # Get lecturer's courses
    courses = Course.objects.filter(lecturer=request.user.userprofile)
    
    if request.method == 'POST':
        course_id = request.POST.get('course')
        test_name = request.POST.get('test_name', '').strip()
        test_type = request.POST.get('test_type', 'quiz')
        max_points = request.POST.get('max_points', '100')
        description = request.POST.get('description', '').strip()
        
        # Validation
        if not all([course_id, test_name, max_points]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'MainInterface/create_test.html', {'courses': courses})
        
        try:
            course = courses.get(id=course_id)
            max_points_float = float(max_points)
            
            if max_points_float <= 0:
                messages.error(request, 'Maximum points must be greater than 0.')
                return render(request, 'MainInterface/create_test.html', {'courses': courses})
            
            # Get all enrolled students in the course
            enrolled_students = User.objects.filter(
                enrollments__course=course,
                enrollments__status='enrolled'
            )
            
            # Create grade entries for all enrolled students
            grades_created = 0
            for student in enrolled_students:
                # Check if grade already exists for this test
                existing_grade = Grade.objects.filter(
                    student=student,
                    course=course,
                    grade_type=test_type,
                    description=test_name
                ).first()
                
                if not existing_grade:
                    Grade.objects.create(
                        student=student,
                        course=course,
                        grade_type=test_type,
                        description=test_name,
                        max_points=max_points_float,
                        grade_value='I',  # Incomplete - to be filled in when grading
                        numeric_score=None,
                        comments=description
                    )
                    grades_created += 1
            
            messages.success(request, f'Test "{test_name}" created successfully for {grades_created} students!')
            return redirect('grade_management')
            
        except Course.DoesNotExist:
            messages.error(request, 'Selected course not found.')
        except ValueError:
            messages.error(request, 'Please enter a valid number for maximum points.')
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
    
    context = {
        'courses': courses,
    }
    
    return render(request, 'MainInterface/create_test.html', context)

@login_required
def grade_test_view(request, course_id):
    """Grade tests for a specific course"""
    try:
        if request.user.userprofile.user_type != 'lecturer':
            messages.error(request, 'Access denied. Lecturer access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    # Get the course
    course = get_object_or_404(Course, id=course_id, lecturer=request.user.userprofile)
    
    # Get filter parameters
    test_filter = request.GET.get('test', '')
    student_filter = request.GET.get('student', '')
    
    # Get all grades for this course
    grades = Grade.objects.filter(course=course).select_related('student')
    
    # Apply filters
    if test_filter:
        grades = grades.filter(description__icontains=test_filter)
    if student_filter:
        grades = grades.filter(
            Q(student__first_name__icontains=student_filter) |
            Q(student__last_name__icontains=student_filter) |
            Q(student__username__icontains=student_filter)
        )
    
    # Get unique test names for filter dropdown
    test_names = Grade.objects.filter(course=course).values_list('description', flat=True).distinct()
    
    # Handle grading form submission
    if request.method == 'POST':
        grade_id = request.POST.get('grade_id')
        numeric_score = request.POST.get('numeric_score', '').strip()
        feedback = request.POST.get('feedback', '').strip()
        
        try:
            grade = Grade.objects.get(id=grade_id, course=course)
            
            if numeric_score:
                score = float(numeric_score)
                if score < 0 or score > float(grade.max_points):
                    messages.error(request, f'Score must be between 0 and {grade.max_points}.')
                else:
                    # Calculate percentage and letter grade
                    percentage = (score / float(grade.max_points)) * 100
                    
                    # Determine letter grade based on percentage
                    if percentage >= 90:
                        letter_grade = 'A+'
                    elif percentage >= 85:
                        letter_grade = 'A'
                    elif percentage >= 80:
                        letter_grade = 'A-'
                    elif percentage >= 77:
                        letter_grade = 'B+'
                    elif percentage >= 73:
                        letter_grade = 'B'
                    elif percentage >= 70:
                        letter_grade = 'B-'
                    elif percentage >= 67:
                        letter_grade = 'C+'
                    elif percentage >= 63:
                        letter_grade = 'C'
                    elif percentage >= 60:
                        letter_grade = 'C-'
                    elif percentage >= 57:
                        letter_grade = 'D+'
                    elif percentage >= 53:
                        letter_grade = 'D'
                    elif percentage >= 50:
                        letter_grade = 'D-'
                    else:
                        letter_grade = 'F'
                    
                    # Update grade
                    grade.numeric_score = score
                    grade.grade_value = letter_grade
                    grade.comments = feedback
                    grade.date_graded = timezone.now()
                    grade.save()
                    
                    messages.success(request, f'Grade updated for {grade.student.get_full_name() or grade.student.username}.')
            else:
                messages.error(request, 'Please enter a numeric score.')
                
        except Grade.DoesNotExist:
            messages.error(request, 'Grade not found.')
        except ValueError:
            messages.error(request, 'Please enter a valid numeric score.')
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
    
    # Paginate grades
    from django.core.paginator import Paginator
    paginator = Paginator(grades.order_by('student__last_name', 'student__first_name', 'description'), 20)
    page_number = request.GET.get('page')
    page_grades = paginator.get_page(page_number)
    
    context = {
        'course': course,
        'grades': page_grades,
        'test_names': test_names,
        'test_filter': test_filter,
        'student_filter': student_filter,
    }
    
    return render(request, 'MainInterface/grade_test.html', context)

@login_required
def weight_management_view(request, course_id):
    """Manage assessment weights for a course"""
    try:
        if request.user.userprofile.user_type != 'lecturer':
            messages.error(request, 'Access denied. Lecturer access required.')
            return redirect('dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('dashboard')
    
    # Get the course and verify lecturer ownership
    try:
        course = Course.objects.get(id=course_id, lecturer=request.user.userprofile)
    except Course.DoesNotExist:
        messages.error(request, 'Course not found or access denied.')
        return redirect('lecturer_dashboard')
    
    if request.method == 'POST':
        # Process weight updates
        weights_updated = False
        total_weight = 0
        
        for key, value in request.POST.items():
            if key.startswith('weight_'):
                try:
                    grade_type = key.replace('weight_', '')
                    weight = float(value)
                    total_weight += weight
                    
                    # Update weights for all grades of this type in the course
                    updated_count = Grade.objects.filter(
                        course=course,
                        grade_type=grade_type
                    ).update(weight=weight)
                    
                    if updated_count > 0:
                        weights_updated = True
                    
                except (ValueError, TypeError):
                    messages.error(request, f'Invalid weight value for {grade_type}')
                    continue
        
        # Validate total weights
        if total_weight > 120:
            messages.warning(request, f'Total weight is {total_weight}% which is higher than recommended (100%)')
        elif total_weight < 80:
            messages.warning(request, f'Total weight is {total_weight}% which is lower than recommended (100%)')
        
        if weights_updated:
            messages.success(request, 'Assessment weights updated successfully!')
        else:
            messages.info(request, 'No weights were updated.')
            
        return redirect('weight_management', course_id=course_id)
    
    # Get current weights and grade types
    current_weights = course.get_assessment_weights()
    default_weights = course.get_default_weights()
    weight_validation = course.validate_total_weights()
    
    # Get all grade types used in this course
    grade_types = list(Grade.objects.filter(course=course).values_list('grade_type', flat=True).distinct())
    
    # Get available grade type choices
    available_grade_types = dict(Grade.GRADE_TYPE_CHOICES)
    
    # Grade distribution stats
    grade_distribution = course.get_grade_distribution()
    course_stats = course.get_student_performance_stats()
    
    context = {
        'course': course,
        'current_weights': current_weights,
        'default_weights': default_weights,
        'weight_validation': weight_validation,
        'grade_types': grade_types,
        'available_grade_types': available_grade_types,
        'grade_distribution': grade_distribution,
        'course_stats': course_stats,
    }
    
    return render(request, 'MainInterface/weight_management.html', context)
