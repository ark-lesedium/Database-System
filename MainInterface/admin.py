from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils import timezone
from .models import UserProfile, Course, Enrollment, Grade, AcademicCalendar, Announcement, StudyMaterial, Assignment, AssignmentSubmission

# Register your models here.

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'User Profile'
    extra = 0  # Don't show extra forms
    min_num = 1  # Ensure at least one profile exists
    max_num = 1  # Only allow one profile per user

class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_user_type')
    list_filter = UserAdmin.list_filter + ('userprofile__user_type',)
    
    def get_user_type(self, instance):
        try:
            return instance.userprofile.get_user_type_display()
        except UserProfile.DoesNotExist:
            return 'No Profile'
    get_user_type.short_description = 'User Type'

@admin.register(AcademicCalendar)
class AcademicCalendarAdmin(admin.ModelAdmin):
    list_display = ('title', 'event_type', 'start_date', 'end_date', 'semester', 'year', 'is_active')
    list_filter = ('event_type', 'semester', 'year', 'is_active')
    search_fields = ('title', 'description')
    date_hierarchy = 'start_date'
    ordering = ['-start_date']

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('course_code', 'course_name', 'lecturer', 'credits', 'level', 'semester', 'max_students')
    list_filter = ('level', 'semester', 'credits')
    search_fields = ('course_code', 'course_name', 'lecturer__user__username')
    ordering = ['course_code']

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'status', 'enrollment_date')
    list_filter = ('status', 'course__semester')
    search_fields = ('student__username', 'course__course_code', 'course__course_name')
    date_hierarchy = 'enrollment_date'

@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'grade_type', 'grade_value', 'numeric_score', 'date_graded')
    list_filter = ('grade_type', 'grade_value', 'course__semester')
    search_fields = ('student__username', 'course__course_code')
    date_hierarchy = 'date_graded'

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'priority', 'audience', 'course', 'is_pinned', 'is_active', 'created_at')
    list_filter = ('priority', 'audience', 'is_pinned', 'is_active', 'course')
    search_fields = ('title', 'content', 'author__username')
    date_hierarchy = 'created_at'
    ordering = ['-is_pinned', '-created_at']
    list_editable = ('is_pinned', 'is_active')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'content', 'author')
        }),
        ('Settings', {
            'fields': ('priority', 'audience', 'course', 'expires_at')
        }),
        ('Display Options', {
            'fields': ('is_active', 'is_pinned'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating a new announcement
            obj.author = request.user
        super().save_model(request, obj, form, change)

@admin.register(StudyMaterial)
class StudyMaterialAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'material_type', 'uploaded_by', 'file_size', 'download_count', 'is_active', 'created_at')
    list_filter = ('material_type', 'course', 'is_active', 'created_at')
    search_fields = ('title', 'description', 'course__course_code', 'course__course_name')
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    list_editable = ('is_active',)
    readonly_fields = ('download_count', 'file_size', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'material_type', 'file')
        }),
        ('Course Assignment', {
            'fields': ('course', 'uploaded_by')
        }),
        ('Settings', {
            'fields': ('is_active',)
        }),
        ('Statistics', {
            'fields': ('download_count', 'file_size', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating a new material
            obj.uploaded_by = request.user
            # Calculate file size if file is uploaded
            if obj.file:
                obj.file_size = obj.file.size
        super().save_model(request, obj, form, change)

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'due_date', 'max_points', 'status', 'created_by', 'created_at')
    list_filter = ('status', 'course', 'created_at', 'due_date')
    search_fields = ('title', 'description', 'course__course_code', 'course__course_name')
    date_hierarchy = 'due_date'
    ordering = ['-due_date']
    list_editable = ('status',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'course', 'created_by')
        }),
        ('Assignment Settings', {
            'fields': ('due_date', 'max_points', 'status', 'instructions')
        }),
        ('File Upload Settings', {
            'fields': ('allowed_file_types', 'max_file_size'),
            'classes': ('collapse',)
        }),
        ('Late Submission Settings', {
            'fields': ('late_submission_allowed', 'late_penalty_per_day'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating a new assignment
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "course":
            # Filter courses to show only those belonging to lecturers
            if hasattr(request.user, 'userprofile') and request.user.userprofile.user_type == 'lecturer':
                kwargs["queryset"] = Course.objects.filter(lecturer=request.user.userprofile)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ('get_assignment_title', 'get_student_name', 'status', 'submitted_at', 'grade', 'late_submission')
    list_filter = ('status', 'late_submission', 'assignment__course', 'submitted_at', 'graded_at')
    search_fields = ('assignment__title', 'student__username', 'student__first_name', 'student__last_name')
    date_hierarchy = 'submitted_at'
    ordering = ['-submitted_at']
    list_editable = ('grade',)
    readonly_fields = ('submitted_at', 'late_submission', 'late_penalty_applied', 'file_size', 'original_filename', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Submission Information', {
            'fields': ('assignment', 'student', 'status')
        }),
        ('Submission Content', {
            'fields': ('submission_file', 'submission_text', 'original_filename', 'file_size')
        }),
        ('Grading', {
            'fields': ('grade', 'feedback', 'graded_by', 'graded_at')
        }),
        ('Late Submission Info', {
            'fields': ('late_submission', 'late_penalty_applied'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('submitted_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_assignment_title(self, obj):
        return obj.assignment.title
    get_assignment_title.short_description = 'Assignment'
    get_assignment_title.admin_order_field = 'assignment__title'
    
    def get_student_name(self, obj):
        return obj.get_student_name()
    get_student_name.short_description = 'Student'
    get_student_name.admin_order_field = 'student__last_name'
    
    def save_model(self, request, obj, form, change):
        # Set graded_by when grade is being added/updated
        if obj.grade is not None and obj.status != 'graded':
            obj.graded_by = request.user
            obj.graded_at = timezone.now()
            obj.status = 'graded'
        super().save_model(request, obj, form, change)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "assignment":
            # Filter assignments to show only those belonging to the current user's courses
            if hasattr(request.user, 'userprofile') and request.user.userprofile.user_type == 'lecturer':
                kwargs["queryset"] = Assignment.objects.filter(course__lecturer=request.user.userprofile)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

# Unregister the default User admin and register our custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
admin.site.register(UserProfile)
