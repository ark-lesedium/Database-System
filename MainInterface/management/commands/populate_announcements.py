from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from MainInterface.models import Announcement, Course, UserProfile

class Command(BaseCommand):
    help = 'Populate the database with sample announcements'

    def handle(self, *args, **options):
        # Clear existing announcements
        Announcement.objects.all().delete()
        
        # Get or create a lecturer user for announcements
        admin_user = User.objects.filter(is_staff=True).first()
        if not admin_user:
            admin_user = User.objects.create_user(
                username='admin_announcer',
                email='admin@university.edu',
                first_name='University',
                last_name='Admin',
                is_staff=True
            )
        
        # Get some courses for course-specific announcements
        courses = list(Course.objects.all()[:3])
        
        # Sample announcements
        announcements_data = [
            {
                'title': 'Welcome to Fall 2025 Semester!',
                'content': 'Welcome back to campus! We are excited to start the Fall 2025 semester. Please make sure to complete your course registration by September 15th. The student center will be open extended hours during the first week.',
                'priority': 'high',
                'audience': 'all',
                'is_pinned': True,
            },
            {
                'title': 'Library Extended Hours During Finals',
                'content': 'The university library will be open 24/7 during the final exam period (December 9-16). Additional study spaces will be available in the student center. Group study rooms can be reserved online.',
                'priority': 'medium',
                'audience': 'students',
                'is_pinned': True,
            },
            {
                'title': 'Faculty Meeting - September 30th',
                'content': 'All faculty members are invited to attend the monthly faculty meeting on September 30th at 2:00 PM in the main conference room. We will discuss curriculum updates and upcoming accreditation requirements.',
                'priority': 'high',
                'audience': 'lecturers',
            },
            {
                'title': 'Campus Maintenance - Network Outage',
                'content': 'Scheduled network maintenance will occur on October 5th from 2:00 AM to 6:00 AM. Internet and email services may be temporarily unavailable during this time. Please plan accordingly.',
                'priority': 'urgent',
                'audience': 'all',
            },
            {
                'title': 'Student Health Services Update',
                'content': 'The campus health center has extended its hours and now offers flu vaccinations. Appointments can be scheduled online through the student portal. Mental health counseling services are also available.',
                'priority': 'medium',
                'audience': 'students',
            },
            {
                'title': 'Research Grant Application Deadline',
                'content': 'The deadline for submitting research grant applications for the Spring 2026 funding cycle is November 15th. All application materials must be submitted through the faculty research portal.',
                'priority': 'high',
                'audience': 'lecturers',
            },
            {
                'title': 'Career Fair - October 20th',
                'content': 'The annual career fair will be held on October 20th in the student center from 10:00 AM to 4:00 PM. Over 50 companies will be participating. Students should bring multiple copies of their resume.',
                'priority': 'medium',
                'audience': 'students',
            },
            {
                'title': 'Course Evaluation Period',
                'content': 'Course evaluation forms are now available online. Students are encouraged to provide feedback on their courses and instructors. The evaluation period ends on November 30th.',
                'priority': 'low',
                'audience': 'students',
            },
            {
                'title': 'Emergency Contact Information Update',
                'content': 'Please ensure your emergency contact information is up to date in the student information system. This information is critical for campus safety and communication purposes.',
                'priority': 'medium',
                'audience': 'all',
            },
            {
                'title': 'Holiday Break Schedule',
                'content': 'Classes will not be held from December 17th through January 19th for the winter holiday break. The campus will be closed December 24th-26th and December 31st-January 2nd.',
                'priority': 'medium',
                'audience': 'all',
            },
        ]
        
        # Add course-specific announcements if courses exist
        if courses:
            course_announcements = [
                {
                    'title': f'{courses[0].course_code} - Midterm Exam Schedule',
                    'content': f'The midterm exam for {courses[0].course_name} will be held on October 15th at 2:00 PM in Room 101. The exam will cover chapters 1-5. Study guide has been posted on the course website.',
                    'priority': 'high',
                    'audience': 'course_specific',
                    'course': courses[0],
                },
                {
                    'title': f'{courses[1].course_code} - Assignment Extension',
                    'content': f'Due to technical issues with the submission system, the deadline for Assignment 3 in {courses[1].course_name} has been extended to October 10th at 11:59 PM.',
                    'priority': 'medium',
                    'audience': 'course_specific',
                    'course': courses[1],
                },
            ]
            announcements_data.extend(course_announcements)
        
        # Create the announcements
        created_count = 0
        for i, announcement_data in enumerate(announcements_data):
            # Vary creation dates
            created_at = timezone.now() - timedelta(days=i*2)
            
            announcement = Announcement.objects.create(
                author=admin_user,
                created_at=created_at,
                **announcement_data
            )
            created_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {created_count} sample announcements!'
            )
        )
