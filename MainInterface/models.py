from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

# Create your models here.

class AcademicCalendar(models.Model):
    EVENT_TYPE_CHOICES = [
        ('semester_start', 'Semester Start'),
        ('semester_end', 'Semester End'),
        ('registration_start', 'Registration Start'),
        ('registration_end', 'Registration End'),
        ('exam_period', 'Exam Period'),
        ('holiday', 'Holiday'),
        ('break', 'Break'),
        ('deadline', 'Important Deadline'),
        ('event', 'Special Event'),
    ]
    
    SEMESTER_CHOICES = [
        ('spring', 'Spring'),
        ('summer', 'Summer'),
        ('fall', 'Fall'),
        ('winter', 'Winter'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    semester = models.CharField(max_length=20, choices=SEMESTER_CHOICES)
    year = models.IntegerField(default=2025)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['start_date']
        verbose_name = "Academic Calendar Event"
        verbose_name_plural = "Academic Calendar Events"
    
    def __str__(self):
        return f"{self.title} - {self.start_date}"
    
    def is_multi_day(self):
        return self.end_date and self.end_date != self.start_date

class UserProfile(models.Model):
    USER_TYPE_CHOICES = [
        ('student', 'Student'),
        ('lecturer', 'Lecturer'),
        ('admin', 'Admin'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='student')
    
    def __str__(self):
        return f"{self.user.username} - {self.get_user_type_display()}"

class Course(models.Model):
    LEVEL_CHOICES = [
        ('undergraduate', 'Undergraduate'),
        ('graduate', 'Graduate'),
        ('postgraduate', 'Postgraduate'),
    ]
    
    SEMESTER_CHOICES = [
        ('spring', 'Spring'),
        ('summer', 'Summer'),
        ('fall', 'Fall'),
        ('winter', 'Winter'),
    ]
    
    course_code = models.CharField(max_length=20, unique=True)
    course_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    credits = models.IntegerField(default=3)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='undergraduate')
    semester = models.CharField(max_length=20, choices=SEMESTER_CHOICES, default='spring')
    max_students = models.IntegerField(default=30)
    is_active = models.BooleanField(default=True)
    lecturer = models.ForeignKey(UserProfile, on_delete=models.CASCADE, 
                               limit_choices_to={'user_type': 'lecturer'})
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.course_code} - {self.course_name}"
    
    def get_enrolled_count(self):
        return self.enrollments.filter(status='enrolled').count()
    
    def has_available_slots(self):
        return self.get_enrolled_count() < self.max_students
    
    def get_lecturer_name(self):
        """Get the full name of the lecturer."""
        if self.lecturer.user.first_name or self.lecturer.user.last_name:
            return f"{self.lecturer.user.first_name} {self.lecturer.user.last_name}".strip()
        return self.lecturer.user.username
    
    class Meta:
        ordering = ['course_code']

class Enrollment(models.Model):
    STATUS_CHOICES = [
        ('enrolled', 'Enrolled'),
        ('pending', 'Pending Approval'),
        ('waitlisted', 'Waitlisted'),
        ('dropped', 'Dropped'),
        ('completed', 'Completed'),
    ]
    
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={'userprofile__user_type': 'student'},
        related_name='enrollments'
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    enrollment_date = models.DateTimeField(default=timezone.now)
    last_updated = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, null=True, help_text="Additional notes about enrollment")
    
    class Meta:
        unique_together = ['student', 'course']
        ordering = ['-enrollment_date']
        verbose_name = "Enrollment"
        verbose_name_plural = "Enrollments"
    
    def __str__(self):
        return f"{self.student.username} - {self.course.course_code} ({self.get_status_display()})"
    
    def get_student_name(self):
        """Get student's full name or username"""
        return self.student.get_full_name() or self.student.username

class Grade(models.Model):
    GRADE_CHOICES = [
        ('A+', 'A+ (90-100)'),
        ('A', 'A (85-89)'),
        ('A-', 'A- (80-84)'),
        ('B+', 'B+ (77-79)'),
        ('B', 'B (73-76)'),
        ('B-', 'B- (70-72)'),
        ('C+', 'C+ (67-69)'),
        ('C', 'C (63-66)'),
        ('C-', 'C- (60-62)'),
        ('D+', 'D+ (57-59)'),
        ('D', 'D (53-56)'),
        ('D-', 'D- (50-52)'),
        ('F', 'F (0-49)'),
        ('I', 'Incomplete'),
        ('W', 'Withdrawal'),
        ('P', 'Pass'),
        ('NP', 'No Pass'),
    ]
    
    GRADE_TYPE_CHOICES = [
        ('assignment', 'Assignment'),
        ('quiz', 'Quiz'),
        ('midterm', 'Midterm Exam'),
        ('final', 'Final Exam'),
        ('project', 'Project'),
        ('participation', 'Participation'),
        ('final_grade', 'Final Course Grade'),
    ]
    
    # Grade point mapping for GPA calculation
    GRADE_POINTS = {
        'A+': 4.0, 'A': 4.0, 'A-': 3.7,
        'B+': 3.3, 'B': 3.0, 'B-': 2.7,
        'C+': 2.3, 'C': 2.0, 'C-': 1.7,
        'D+': 1.3, 'D': 1.0, 'D-': 0.7,
        'F': 0.0, 'I': None, 'W': None, 'P': None, 'NP': 0.0
    }
    
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={'userprofile__user_type': 'student'},
        related_name='grades'
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='grades')
    grade_type = models.CharField(max_length=15, choices=GRADE_TYPE_CHOICES, default='assignment')
    grade_value = models.CharField(max_length=3, choices=GRADE_CHOICES)
    numeric_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Numeric score (0-100)"
    )
    max_points = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=100,
        help_text="Maximum possible points"
    )
    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1.0,
        help_text="Weight of this grade in final calculation"
    )
    description = models.CharField(max_length=200, blank=True, help_text="Assignment or exam name")
    date_graded = models.DateTimeField(default=timezone.now)
    comments = models.TextField(blank=True, help_text="Instructor feedback")
    
    class Meta:
        ordering = ['-date_graded']
        verbose_name = "Grade"
        verbose_name_plural = "Grades"
    
    def __str__(self):
        return f"{self.student.username} - {self.course.course_code} - {self.grade_value}"
    
    def get_grade_points(self):
        """Get grade points for GPA calculation"""
        return self.GRADE_POINTS.get(self.grade_value, 0.0)
    
    def get_percentage(self):
        """Calculate percentage if numeric score is available"""
        if self.numeric_score is not None and self.max_points > 0:
            return round((float(self.numeric_score) / float(self.max_points)) * 100, 2)
        return None
    
    def get_student_name(self):
        """Get student's full name or username"""
        return self.student.get_full_name() or self.student.username

class Announcement(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    AUDIENCE_CHOICES = [
        ('all', 'All Users'),
        ('students', 'Students Only'),
        ('lecturers', 'Lecturers Only'),
        ('course_specific', 'Course Specific'),
    ]
    
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='announcements')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default='all')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, null=True, blank=True, 
                             help_text="Select course for course-specific announcements")
    is_active = models.BooleanField(default=True)
    is_pinned = models.BooleanField(default=False, help_text="Pinned announcements appear at the top")
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Announcement will be hidden after this date")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_pinned', '-created_at']
        verbose_name = "Announcement"
        verbose_name_plural = "Announcements"
    
    def __str__(self):
        return f"{self.title} - {self.get_priority_display()}"
    
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def get_author_name(self):
        """Get author's full name or username"""
        if self.author.first_name or self.author.last_name:
            return f"{self.author.first_name} {self.author.last_name}".strip()
        return self.author.username
    
    def is_visible_to_user(self, user):
        """Check if announcement is visible to a specific user"""
        if not self.is_active or self.is_expired():
            return False
        
        if self.audience == 'all':
            return True
        elif self.audience == 'students' and hasattr(user, 'userprofile'):
            return user.userprofile.user_type == 'student'
        elif self.audience == 'lecturers' and hasattr(user, 'userprofile'):
            return user.userprofile.user_type == 'lecturer'
        elif self.audience == 'course_specific' and self.course and hasattr(user, 'userprofile'):
            if user.userprofile.user_type == 'student':
                return Enrollment.objects.filter(student=user, course=self.course, status='enrolled').exists()
            elif user.userprofile.user_type == 'lecturer':
                return self.course.lecturer == user.userprofile
        
        return False

class StudyMaterial(models.Model):
    MATERIAL_TYPE_CHOICES = [
        ('lecture_notes', 'Lecture Notes'),
        ('slides', 'Presentation Slides'),
        ('assignment', 'Assignment'),
        ('reading', 'Reading Material'),
        ('reference', 'Reference Document'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('other', 'Other'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    material_type = models.CharField(max_length=20, choices=MATERIAL_TYPE_CHOICES, default='other')
    file = models.FileField(upload_to='study_materials/%Y/%m/%d/')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='study_materials')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_materials')
    file_size = models.PositiveIntegerField(null=True, blank=True, help_text="File size in bytes")
    download_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Study Material"
        verbose_name_plural = "Study Materials"
    
    def __str__(self):
        return f"{self.title} - {self.course.course_code}"
    
    def get_file_size_display(self):
        """Convert file size to human readable format"""
        if self.file_size:
            if self.file_size < 1024:
                return f"{self.file_size} B"
            elif self.file_size < 1024 * 1024:
                return f"{self.file_size / 1024:.1f} KB"
            elif self.file_size < 1024 * 1024 * 1024:
                return f"{self.file_size / (1024 * 1024):.1f} MB"
            else:
                return f"{self.file_size / (1024 * 1024 * 1024):.1f} GB"
        return "Unknown"
    
    def get_file_extension(self):
        """Get file extension"""
        if self.file:
            return self.file.name.split('.')[-1].lower()
        return ""
    
    def get_uploader_name(self):
        """Get uploader's full name or username"""
        if self.uploaded_by.first_name or self.uploaded_by.last_name:
            return f"{self.uploaded_by.first_name} {self.uploaded_by.last_name}".strip()
        return self.uploaded_by.username
    
    def is_accessible_to_user(self, user):
        """Check if material is accessible to a specific user"""
        if not self.is_active:
            return False
        
        # Uploader can always access
        if self.uploaded_by == user:
            return True
        
        # Check if user is enrolled in the course (for students)
        if hasattr(user, 'userprofile') and user.userprofile.user_type == 'student':
            return Enrollment.objects.filter(student=user, course=self.course, status='enrolled').exists()
        
        # Lecturers can access materials for their courses
        elif hasattr(user, 'userprofile') and user.userprofile.user_type == 'lecturer':
            return self.course.lecturer == user.userprofile
        
        return False
    
    def increment_download_count(self):
        """Increment download counter"""
        self.download_count += 1
        self.save(update_fields=['download_count'])

class Assignment(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('closed', 'Closed'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='assignments')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_assignments')
    due_date = models.DateTimeField()
    max_points = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    instructions = models.TextField(blank=True, help_text="Detailed instructions for students")
    allowed_file_types = models.CharField(
        max_length=200, 
        default='pdf,doc,docx,txt',
        help_text="Comma-separated list of allowed file extensions"
    )
    max_file_size = models.PositiveIntegerField(
        default=10485760,  # 10MB in bytes
        help_text="Maximum file size in bytes"
    )
    late_submission_allowed = models.BooleanField(default=True)
    late_penalty_per_day = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=10.0,
        help_text="Percentage penalty per day late"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-due_date']
        verbose_name = "Assignment"
        verbose_name_plural = "Assignments"
    
    def __str__(self):
        return f"{self.course.course_code} - {self.title}"
    
    def is_overdue(self):
        """Check if assignment is past due date"""
        return timezone.now() > self.due_date
    
    def days_until_due(self):
        """Calculate days until due date"""
        if self.is_overdue():
            return 0
        delta = self.due_date - timezone.now()
        return delta.days
    
    def get_allowed_file_types_list(self):
        """Get list of allowed file types"""
        return [ext.strip().lower() for ext in self.allowed_file_types.split(',')]
    
    def get_max_file_size_display(self):
        """Convert max file size to human readable format"""
        if self.max_file_size < 1024:
            return f"{self.max_file_size} B"
        elif self.max_file_size < 1024 * 1024:
            return f"{self.max_file_size / 1024:.1f} KB"
        elif self.max_file_size < 1024 * 1024 * 1024:
            return f"{self.max_file_size / (1024 * 1024):.1f} MB"
        else:
            return f"{self.max_file_size / (1024 * 1024 * 1024):.1f} GB"
    
    def get_submission_count(self):
        """Get number of submissions for this assignment"""
        return self.submissions.count()

class AssignmentSubmission(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('graded', 'Graded'),
        ('returned', 'Returned'),
    ]
    
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={'userprofile__user_type': 'student'},
        related_name='assignment_submissions'
    )
    submission_file = models.FileField(upload_to='assignment_submissions/%Y/%m/%d/')
    submission_text = models.TextField(blank=True, help_text="Optional text submission")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    submitted_at = models.DateTimeField(null=True, blank=True)
    grade = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True, help_text="Instructor feedback")
    graded_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='graded_submissions'
    )
    graded_at = models.DateTimeField(null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    late_submission = models.BooleanField(default=False)
    late_penalty_applied = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.0,
        help_text="Penalty percentage applied for late submission"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['assignment', 'student']
        ordering = ['-submitted_at']
        verbose_name = "Assignment Submission"
        verbose_name_plural = "Assignment Submissions"
    
    def __str__(self):
        return f"{self.student.username} - {self.assignment.title} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        # Set submitted_at when status changes to submitted
        if self.status == 'submitted' and not self.submitted_at:
            self.submitted_at = timezone.now()
            # Check if submission is late
            if self.submitted_at > self.assignment.due_date:
                self.late_submission = True
                # Calculate late penalty
                days_late = (self.submitted_at - self.assignment.due_date).days
                if days_late > 0:
                    self.late_penalty_applied = min(
                        days_late * self.assignment.late_penalty_per_day,
                        100.0  # Maximum 100% penalty
                    )
        
        # Set file size and original filename if file is provided
        if self.submission_file:
            self.file_size = self.submission_file.size
            self.original_filename = self.submission_file.name
        
        super().save(*args, **kwargs)
    
    def get_final_grade(self):
        """Calculate final grade after applying late penalty"""
        if self.grade is not None:
            final_grade = float(self.grade) - (float(self.grade) * float(self.late_penalty_applied) / 100)
            return max(0, final_grade)  # Ensure grade doesn't go below 0
        return None
    
    def get_file_size_display(self):
        """Convert file size to human readable format"""
        if self.file_size:
            if self.file_size < 1024:
                return f"{self.file_size} B"
            elif self.file_size < 1024 * 1024:
                return f"{self.file_size / 1024:.1f} KB"
            elif self.file_size < 1024 * 1024 * 1024:
                return f"{self.file_size / (1024 * 1024):.1f} MB"
            else:
                return f"{self.file_size / (1024 * 1024 * 1024):.1f} GB"
        return "Unknown"
    
    def is_late(self):
        """Check if submission was made after due date"""
        return self.late_submission
    
    def get_student_name(self):
        """Get student's full name or username"""
        return self.student.get_full_name() or self.student.username

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # Only create UserProfile if it doesn't already exist
        UserProfile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    # Only save if UserProfile exists
    if hasattr(instance, 'userprofile'):
        instance.userprofile.save()
    else:
        # Create UserProfile if it doesn't exist
        UserProfile.objects.get_or_create(user=instance)
