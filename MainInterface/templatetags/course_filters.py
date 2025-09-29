from django import template
from ..models import Enrollment

register = template.Library()

@register.filter
def get_enrollment_status(user, course):
    """Get the enrollment status of a user for a specific course"""
    try:
        enrollment = Enrollment.objects.filter(student=user, course=course).first()
        return enrollment.status if enrollment else None
    except:
        return None
