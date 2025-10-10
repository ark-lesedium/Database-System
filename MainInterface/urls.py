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
    
    # Course Materials Management URLs
    path('materials/upload/', views.upload_material_view, name='upload_material'),
    path('materials/manage/', views.manage_materials_view, name='manage_materials'),
    path('materials/edit/<int:material_id>/', views.edit_material_view, name='edit_material'),
    path('materials/delete/<int:material_id>/', views.delete_material_view, name='delete_material'),
    
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
    path('lecturer/assignments/create/', views.create_assignment_view, name='create_assignment'),
    path('lecturer/assignments/<int:assignment_id>/submissions/', views.assignment_submissions_view, name='assignment_submissions'),
    path('lecturer/assignments/grade/<int:submission_id>/', views.grade_submission_view, name='grade_submission'),
    
    # Grade Management URLs
    path('lecturer/grades/', views.grade_management_view, name='grade_management'),
    path('lecturer/grades/create-test/', views.create_test_view, name='create_test'),
    path('lecturer/grades/course/<int:course_id>/', views.grade_test_view, name='grade_test'),
    path('lecturer/grades/weights/<int:course_id>/', views.weight_management_view, name='weight_management'),
    path('lecturer/submissions/<int:submission_id>/grade/', views.grade_submission_view, name='grade_submission'),
    path('lecturer/grades/exam-marks/', views.manage_exam_marks, name='manage_exam_marks'),
    
    # Class Schedule URLs
    path('schedule/', views.view_schedule_view, name='view_schedule'),
    path('schedule/manage/', views.manage_schedule_view, name='manage_schedule'),
    path('schedule/add/', views.add_schedule_event_view, name='add_schedule_event'),
    path('schedule/edit/<int:schedule_id>/', views.edit_schedule_event_view, name='edit_schedule_event'),
    path('schedule/delete/<int:schedule_id>/', views.delete_schedule_event_view, name='delete_schedule_event'),
    
    # Announcement Management URLs
    path('announcements/manage/', views.manage_announcements_view, name='manage_announcements'),
    path('announcements/create/', views.create_announcement_view, name='create_announcement'),
    path('announcements/edit/<int:announcement_id>/', views.edit_announcement_view, name='edit_announcement'),
    path('announcements/delete/<int:announcement_id>/', views.delete_announcement_view, name='delete_announcement'),
    
    # Academic Reports URLs
    path('academic-reports/', views.academic_reports_view, name='academic_reports'),
    path('academic-reports/generate/<int:student_id>/', views.generate_student_report, name='generate_student_report'),
    path('academic-reports/semester-results/<int:student_id>/', views.generate_semester_results, name='generate_semester_results'),
    path('academic-reports/academic-record/<int:student_id>/', views.generate_academic_record, name='generate_academic_record'),
    path('academic-reports/full-transcript/<int:student_id>/', views.generate_full_transcript, name='generate_full_transcript'),
    
    # PDF Downloads
    path('download-progress-report/', views.download_progress_report, name='download_progress_report'),
]
