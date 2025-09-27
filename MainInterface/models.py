from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# Create your models here.

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
