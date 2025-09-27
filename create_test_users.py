#!/usr/bin/env python
"""
Script to create test users for each user type.
Run this script from the project directory with: python create_test_users.py
"""

import os
import sys
import django

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'DatabaseSystemProject.settings')
django.setup()

from django.contrib.auth.models import User
from MainInterface.models import UserProfile

def create_test_users():
    # Test users data
    users_data = [
        {
            'username': 'student1',
            'email': 'student1@example.com',
            'first_name': 'John',
            'last_name': 'Student',
            'password': 'password123',
            'user_type': 'student'
        },
        {
            'username': 'lecturer1',
            'email': 'lecturer1@example.com',
            'first_name': 'Jane',
            'last_name': 'Lecturer',
            'password': 'password123',
            'user_type': 'lecturer'
        },
        {
            'username': 'admin1',
            'email': 'admin1@example.com',
            'first_name': 'Admin',
            'last_name': 'User',
            'password': 'password123',
            'user_type': 'admin'
        }
    ]
    
    for user_data in users_data:
        username = user_data['username']
        
        # Check if user already exists
        if User.objects.filter(username=username).exists():
            print(f"User {username} already exists, skipping...")
            continue
        
        # Create user
        user = User.objects.create_user(
            username=user_data['username'],
            email=user_data['email'],
            password=user_data['password'],
            first_name=user_data['first_name'],
            last_name=user_data['last_name']
        )
        
        # Set user type
        user.userprofile.user_type = user_data['user_type']
        user.userprofile.save()
        
        print(f"Created {user_data['user_type']} user: {username}")
    
    print("\nTest users created successfully!")
    print("\nLogin credentials:")
    print("Student: username=student1, password=password123")
    print("Lecturer: username=lecturer1, password=password123") 
    print("Admin: username=admin1, password=password123")

if __name__ == '__main__':
    create_test_users()
