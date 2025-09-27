from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import UserProfile

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
    
    # Context data for the student dashboard
    context = {
        'user': request.user,
        'enrolled_courses_count': 0,  # Placeholder - will be populated when Course model is added
        'current_gpa': 'N/A',  # Placeholder - will be calculated when Grade model is added
        'pending_assignments': 0,  # Placeholder - will be populated when Assignment model is added
        'attendance_percentage': 0,  # Placeholder - will be calculated when Attendance model is added
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
