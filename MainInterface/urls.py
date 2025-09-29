from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('student-dashboard/', views.student_dashboard_view, name='student_dashboard'),
    path('lecturer-dashboard/', views.lecturer_dashboard_view, name='lecturer_dashboard'),
    path('profile-management/', views.profile_management_view, name='profile_management'),
    path('browse-courses/', views.browse_courses_view, name='browse_courses'),
    path('enrolled-courses/', views.enrolled_courses_view, name='enrolled_courses'),
    path('view-grades/', views.view_grades_view, name='view_grades'),
    path('grade-detail/<int:course_id>/', views.grade_detail_view, name='grade_detail'),
    path('academic-progress/', views.academic_progress_view, name='academic_progress'),
    path('academic-calendar/', views.academic_calendar_view, name='academic_calendar'),
    path('announcements/', views.announcements_view, name='announcements'),
    path('study-materials/', views.study_materials_view, name='study_materials'),
    path('manage-courses/', views.manage_courses_view, name='manage_courses'),
    path('add-course/', views.add_course_view, name='add_course'),
    path('edit-course/<int:course_id>/', views.edit_course_view, name='edit_course'),
    path('delete-course/<int:course_id>/', views.delete_course_view, name='delete_course'),
    path('course-detail/<int:course_id>/', views.course_detail_view, name='course_detail'),
    path('enroll-course/<int:course_id>/', views.enroll_course_view, name='enroll_course'),
    path('drop-course/<int:course_id>/', views.drop_course_view, name='drop_course'),
    path('cancel-enrollment/<int:course_id>/', views.cancel_enrollment_view, name='cancel_enrollment'),
    path('join-waitlist/<int:course_id>/', views.join_waitlist_view, name='join_waitlist'),
    path('course-enrollments/<int:course_id>/', views.course_enrollments_view, name='course_enrollments'),
    path('activate-course/<int:course_id>/', views.activate_course_view, name='activate_course'),
    path('deactivate-course/<int:course_id>/', views.deactivate_course_view, name='deactivate_course'),
    path('student-management/', views.student_management_view, name='student_management'),
    path('download-enrollment-report/', views.download_enrollment_report, name='download_enrollment_report'),
    path('approve-enrollment/<int:enrollment_id>/', views.approve_enrollment_view, name='approve_enrollment'),
    path('reject-enrollment/<int:enrollment_id>/', views.reject_enrollment_view, name='reject_enrollment'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    
    # Assignment URLs
    path('assignments/', views.assignments_view, name='assignments'),
    path('assignments/submit/<int:assignment_id>/', views.submit_assignment_view, name='submit_assignment'),
    path('assignments/submissions/', views.view_submissions_view, name='view_submissions'),
    path('assignments/download/<int:submission_id>/', views.download_submission_view, name='download_submission'),
    
    # Lecturer assignment management URLs
    path('lecturer/assignments/', views.lecturer_assignments_view, name='lecturer_assignments'),
    path('lecturer/assignments/<int:assignment_id>/submissions/', views.assignment_submissions_view, name='assignment_submissions'),
    
    # PDF Downloads
    path('download-progress-report/', views.download_progress_report, name='download_progress_report'),
]
