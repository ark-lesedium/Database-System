from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.utils import timezone
from datetime import timedelta
from MainInterface.models import StudyMaterial, Course, UserProfile
import os

class Command(BaseCommand):
    help = 'Populate the database with sample study materials'

    def handle(self, *args, **options):
        # Clear existing study materials
        StudyMaterial.objects.all().delete()
        
        # Get lecturers and courses
        lecturers = User.objects.filter(userprofile__user_type='lecturer')
        courses = list(Course.objects.all())
        
        if not lecturers.exists() or not courses:
            self.stdout.write(
                self.style.WARNING('No lecturers or courses found. Please create some first.')
            )
            return
        
        # Use first lecturer as uploader
        uploader = lecturers.first()
        
        # Sample study materials data
        materials_data = []
        
        for i, course in enumerate(courses[:5]):  # Limit to first 5 courses
            course_materials = [
                {
                    'title': f'{course.course_code} - Course Syllabus',
                    'description': f'Complete syllabus for {course.course_name} including learning objectives, assessment criteria, and course schedule.',
                    'material_type': 'reference',
                    'course': course,
                    'uploaded_by': uploader,
                    'file_content': f'Course Syllabus for {course.course_name}\n\nThis is a sample syllabus document.\n\nCourse Code: {course.course_code}\nCourse Name: {course.course_name}\nCredits: {course.credits}\nInstructor: {course.get_lecturer_name()}\n\nCourse Description:\n{course.description}\n\nLearning Objectives:\n- Understand fundamental concepts\n- Apply theoretical knowledge\n- Develop practical skills\n\nAssessment:\n- Assignments: 30%\n- Midterm Exam: 25%\n- Final Exam: 35%\n- Participation: 10%',
                    'filename': f'{course.course_code}_syllabus.txt'
                },
                {
                    'title': f'Week 1 Lecture Notes - Introduction to {course.course_name}',
                    'description': 'Introductory lecture covering basic concepts and course overview.',
                    'material_type': 'lecture_notes',
                    'course': course,
                    'uploaded_by': uploader,
                    'file_content': f'Lecture 1: Introduction to {course.course_name}\n\nDate: Week 1\nInstructor: {course.get_lecturer_name()}\n\nTopics Covered:\n1. Course Introduction\n2. Overview of {course.course_name}\n3. Key Concepts\n4. Learning Objectives\n\nKey Points:\n- This course covers fundamental concepts\n- Practical applications will be emphasized\n- Active participation is encouraged\n\nNext Week: We will dive deeper into the first topic',
                    'filename': f'{course.course_code}_lecture1_notes.txt'
                },
                {
                    'title': f'{course.course_code} - Assignment 1',
                    'description': 'First assignment covering introductory concepts. Due in 2 weeks.',
                    'material_type': 'assignment',
                    'course': course,
                    'uploaded_by': uploader,
                    'file_content': f'Assignment 1: {course.course_name}\n\nDue Date: Two weeks from assignment date\nTotal Points: 100\n\nInstructions:\n1. Read the course materials\n2. Answer the following questions\n3. Submit your work online\n\nQuestions:\n1. Explain the main concepts covered in Week 1 (25 points)\n2. Provide examples of practical applications (25 points)\n3. Discuss the importance of this subject (25 points)\n4. Analyze a case study (25 points)\n\nSubmission Guidelines:\n- Submit as PDF or Word document\n- Include your name and student ID\n- Use proper citations\n\nGrading Rubric:\n- Content: 70%\n- Organization: 20%\n- Grammar/Style: 10%',
                    'filename': f'{course.course_code}_assignment1.txt'
                },
                {
                    'title': f'Chapter 1 Reading Material - {course.course_name}',
                    'description': 'Required reading for the first chapter of the course.',
                    'material_type': 'reading',
                    'course': course,
                    'uploaded_by': uploader,
                    'file_content': f'Chapter 1: Fundamentals of {course.course_name}\n\nLearning Objectives:\nAfter reading this chapter, you will be able to:\n- Understand basic principles\n- Identify key concepts\n- Apply knowledge to real-world scenarios\n\nIntroduction:\nThis chapter introduces the fundamental concepts of {course.course_name}. These concepts form the foundation for all subsequent learning in this course.\n\nKey Concepts:\n1. Definition and scope\n2. Historical development\n3. Current applications\n4. Future trends\n\nConclusion:\nThe concepts presented in this chapter are essential for understanding the broader field of {course.course_name}.\n\nReview Questions:\n1. What are the key principles discussed?\n2. How do these concepts apply to real situations?\n3. What are the implications for future study?',
                    'filename': f'{course.course_code}_chapter1_reading.txt'
                },
                {
                    'title': f'Week 2 Presentation Slides - {course.course_name}',
                    'description': 'PowerPoint slides from Week 2 lecture on advanced concepts.',
                    'material_type': 'slides',
                    'course': course,
                    'uploaded_by': uploader,
                    'file_content': f'Week 2 Presentation: Advanced Concepts in {course.course_name}\n\nSlide 1: Title\n- Advanced Concepts in {course.course_name}\n- Week 2 Lecture\n- Instructor: {course.get_lecturer_name()}\n\nSlide 2: Agenda\n- Review of Week 1\n- Introduction to advanced concepts\n- Practical examples\n- Q&A Session\n\nSlide 3: Review\n- Key points from last week\n- Foundation concepts\n- Questions from students\n\nSlide 4: Advanced Concepts\n- Building on basics\n- Complex applications\n- Real-world examples\n\nSlide 5: Summary\n- What we learned today\n- Next week preview\n- Assignment reminders',
                    'filename': f'{course.course_code}_week2_slides.txt'
                },
            ]
            materials_data.extend(course_materials)
        
        # Create the study materials
        created_count = 0
        for i, material_data in enumerate(materials_data):
            # Create file content
            file_content = material_data.pop('file_content')
            filename = material_data.pop('filename')
            
            # Vary creation dates
            created_at = timezone.now() - timedelta(days=i*3)
            
            # Create the material
            material = StudyMaterial.objects.create(
                created_at=created_at,
                **material_data
            )
            
            # Create and attach file
            file_obj = ContentFile(file_content.encode('utf-8'))
            material.file.save(filename, file_obj, save=True)
            material.file_size = len(file_content.encode('utf-8'))
            material.download_count = i % 5  # Vary download counts
            material.save()
            
            created_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {created_count} study materials!'
            )
        )
