from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from MainInterface.models import AcademicCalendar

class Command(BaseCommand):
    help = 'Populate the academic calendar with sample events'

    def handle(self, *args, **options):
        # Clear existing events
        AcademicCalendar.objects.all().delete()
        
        # Current date for reference
        today = date.today()
        current_year = today.year
        
        # Sample events for the current academic year
        events = [
            # Fall 2025 Semester
            {
                'title': 'Fall 2025 Semester Begins',
                'description': 'First day of classes for Fall 2025',
                'event_type': 'semester_start',
                'start_date': date(2025, 9, 1),
                'semester': 'fall',
                'year': 2025,
            },
            {
                'title': 'Fall Registration Deadline',
                'description': 'Last day to register for Fall 2025 courses',
                'event_type': 'registration_end',
                'start_date': date(2025, 9, 15),
                'semester': 'fall',
                'year': 2025,
            },
            {
                'title': 'Labor Day Holiday',
                'description': 'University closed for Labor Day',
                'event_type': 'holiday',
                'start_date': date(2025, 9, 1),
                'semester': 'fall',
                'year': 2025,
            },
            {
                'title': 'Fall Break',
                'description': 'Mid-semester break',
                'event_type': 'break',
                'start_date': date(2025, 10, 14),
                'end_date': date(2025, 10, 18),
                'semester': 'fall',
                'year': 2025,
            },
            {
                'title': 'Thanksgiving Break',
                'description': 'Thanksgiving holiday break',
                'event_type': 'holiday',
                'start_date': date(2025, 11, 27),
                'end_date': date(2025, 11, 29),
                'semester': 'fall',
                'year': 2025,
            },
            {
                'title': 'Fall Final Exams',
                'description': 'Final examination period',
                'event_type': 'exam_period',
                'start_date': date(2025, 12, 9),
                'end_date': date(2025, 12, 16),
                'semester': 'fall',
                'year': 2025,
            },
            {
                'title': 'Fall 2025 Semester Ends',
                'description': 'Last day of Fall 2025 semester',
                'event_type': 'semester_end',
                'start_date': date(2025, 12, 16),
                'semester': 'fall',
                'year': 2025,
            },
            
            # Spring 2026 Semester
            {
                'title': 'Spring Registration Opens',
                'description': 'Registration opens for Spring 2026',
                'event_type': 'registration_start',
                'start_date': date(2025, 11, 1),
                'semester': 'spring',
                'year': 2026,
            },
            {
                'title': 'Spring 2026 Semester Begins',
                'description': 'First day of classes for Spring 2026',
                'event_type': 'semester_start',
                'start_date': date(2026, 1, 20),
                'semester': 'spring',
                'year': 2026,
            },
            {
                'title': 'Martin Luther King Jr. Day',
                'description': 'University closed for MLK Day',
                'event_type': 'holiday',
                'start_date': date(2026, 1, 19),
                'semester': 'spring',
                'year': 2026,
            },
            {
                'title': 'Spring Registration Deadline',
                'description': 'Last day to register for Spring 2026 courses',
                'event_type': 'registration_end',
                'start_date': date(2026, 2, 3),
                'semester': 'spring',
                'year': 2026,
            },
            {
                'title': "President's Day",
                'description': "University closed for President's Day",
                'event_type': 'holiday',
                'start_date': date(2026, 2, 16),
                'semester': 'spring',
                'year': 2026,
            },
            {
                'title': 'Spring Break',
                'description': 'Mid-semester spring break',
                'event_type': 'break',
                'start_date': date(2026, 3, 16),
                'end_date': date(2026, 3, 20),
                'semester': 'spring',
                'year': 2026,
            },
            {
                'title': 'Course Drop Deadline',
                'description': 'Last day to drop courses without penalty',
                'event_type': 'deadline',
                'start_date': date(2026, 3, 1),
                'semester': 'spring',
                'year': 2026,
            },
            {
                'title': 'Spring Final Exams',
                'description': 'Final examination period',
                'event_type': 'exam_period',
                'start_date': date(2026, 5, 4),
                'end_date': date(2026, 5, 11),
                'semester': 'spring',
                'year': 2026,
            },
            {
                'title': 'Spring 2026 Semester Ends',
                'description': 'Last day of Spring 2026 semester',
                'event_type': 'semester_end',
                'start_date': date(2026, 5, 11),
                'semester': 'spring',
                'year': 2026,
            },
            {
                'title': 'Graduation Ceremony',
                'description': 'Spring 2026 Commencement',
                'event_type': 'event',
                'start_date': date(2026, 5, 15),
                'semester': 'spring',
                'year': 2026,
            },
            
            # Summer 2026 Session
            {
                'title': 'Summer Session Registration',
                'description': 'Registration opens for Summer 2026',
                'event_type': 'registration_start',
                'start_date': date(2026, 3, 15),
                'semester': 'summer',
                'year': 2026,
            },
            {
                'title': 'Summer 2026 Session Begins',
                'description': 'First day of Summer 2026 classes',
                'event_type': 'semester_start',
                'start_date': date(2026, 6, 1),
                'semester': 'summer',
                'year': 2026,
            },
            {
                'title': 'Independence Day',
                'description': 'University closed for July 4th',
                'event_type': 'holiday',
                'start_date': date(2026, 7, 4),
                'semester': 'summer',
                'year': 2026,
            },
            {
                'title': 'Summer 2026 Session Ends',
                'description': 'Last day of Summer 2026 session',
                'event_type': 'semester_end',
                'start_date': date(2026, 8, 15),
                'semester': 'summer',
                'year': 2026,
            },
        ]
        
        # Create the events
        created_count = 0
        for event_data in events:
            event, created = AcademicCalendar.objects.get_or_create(
                title=event_data['title'],
                start_date=event_data['start_date'],
                defaults=event_data
            )
            if created:
                created_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {created_count} academic calendar events!'
            )
        )
