#!/usr/bin/env python
"""
Quick test to create sample grades for semester results testing
"""
import os
import sys
import django
from decimal import Decimal

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'DatabaseSystemProject.settings')
sys.path.append('/home/lesedi-skosana/Desktop/Database-System')
django.setup()

from django.contrib.auth.models import User
from MainInterface.models import UserProfile, Course, Enrollment, Grade

def create_sample_grades():
    """Create sample grades for testing semester results"""
    
    # Try to get existing test users
    try:
        student = User.objects.get(username='test_student')
        lecturer = User.objects.get(username='test_lecturer')
        print("Found existing test users")
    except User.DoesNotExist:
        print("Creating test users...")
        # Create test student
        student = User.objects.create_user(
            username='test_student',
            password='password123',
            first_name='John',
            last_name='Doe',
            email='john.doe@university.edu'
        )
        
        # Create test lecturer
        lecturer = User.objects.create_user(
            username='test_lecturer',
            password='password123',
            first_name='Dr. Jane',
            last_name='Smith',
            email='jane.smith@university.edu'
        )
        
        # Create profiles
        UserProfile.objects.create(user=student, user_type='student')
        UserProfile.objects.create(user=lecturer, user_type='lecturer')
    
    # Create a test course for Spring 2025
    course, created = Course.objects.get_or_create(
        course_code='CS101',
        semester='spring',
        year=2025,
        defaults={
            'course_name': 'Introduction to Computer Science',
            'credits': 3,
            'lecturer': lecturer.userprofile,
            'description': 'Fundamental concepts of computer science',
            'is_active': True
        }
    )
    
    if created:
        print(f"Created course: {course.course_code}")
    
    # Enroll student
    enrollment, created = Enrollment.objects.get_or_create(
        student=student,
        course=course,
        defaults={'status': 'enrolled'}
    )
    
    # Clear existing grades for this course
    Grade.objects.filter(student=student, course=course).delete()
    
    # Create detailed grades
    grades_data = [
        {
            'type': 'assignment',
            'description': 'Programming Assignment 1',
            'score': 85,
            'max_points': 100,
            'weight': 0.15
        },
        {
            'type': 'assignment', 
            'description': 'Programming Assignment 2',
            'score': 92,
            'max_points': 100,
            'weight': 0.15
        },
        {
            'type': 'quiz',
            'description': 'Quiz 1: Variables and Data Types',
            'score': 88,
            'max_points': 100,
            'weight': 0.10
        },
        {
            'type': 'quiz',
            'description': 'Quiz 2: Control Structures',
            'score': 95,
            'max_points': 100,
            'weight': 0.10
        },
        {
            'type': 'midterm',
            'description': 'Midterm Examination',
            'score': 87,
            'max_points': 100,
            'weight': 0.25
        },
        {
            'type': 'project',
            'description': 'Final Project: Simple Calculator',
            'score': 91,
            'max_points': 100,
            'weight': 0.15
        },
        {
            'type': 'final',
            'description': 'Final Examination',
            'score': 89,
            'max_points': 100,
            'weight': 0.10
        }
    ]
    
    print("Creating detailed grades...")
    for grade_data in grades_data:
        grade = Grade.objects.create(
            student=student,
            course=course,
            grade_type=grade_data['type'],
            description=grade_data['description'],
            numeric_score=Decimal(str(grade_data['score'])),
            max_points=Decimal(str(grade_data['max_points'])),
            weight=Decimal(str(grade_data['weight'])),
            comments=f"Grade for {grade_data['description']}"
        )
        print(f"  {grade_data['description']}: {grade_data['score']}/{grade_data['max_points']} (Weight: {grade_data['weight']*100}%)")
    
    print(f"\nTest data created successfully!")
    print(f"Student: {student.get_full_name()} ({student.username})")
    print(f"Course: {course.course_code} - {course.course_name}")
    print(f"Semester: {course.semester.title()} {course.year}")
    print(f"Total grades created: {Grade.objects.filter(student=student, course=course).count()}")
    
    # Calculate expected final grade
    total_weighted = sum(g['score'] * g['weight'] for g in grades_data)
    final_percentage = total_weighted
    print(f"Expected final grade: {final_percentage:.1f}%")
    
    if final_percentage >= 90:
        letter_grade = 'A+'
    elif final_percentage >= 85:
        letter_grade = 'A'
    elif final_percentage >= 80:
        letter_grade = 'A-'
    elif final_percentage >= 77:
        letter_grade = 'B+'
    elif final_percentage >= 73:
        letter_grade = 'B'
    elif final_percentage >= 70:
        letter_grade = 'B-'
    else:
        letter_grade = 'C+'
    
    print(f"Expected letter grade: {letter_grade}")

if __name__ == "__main__":
    create_sample_grades()
