from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import UserProfile

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

# Unregister the default User admin and register our custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
admin.site.register(UserProfile)
