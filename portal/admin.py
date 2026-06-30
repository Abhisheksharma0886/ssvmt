from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User, Profile, StudentProfile, SiteConfig, 
    Attendance, Marks, EditRequest, Timetable, Message, LeaveApplication, GalleryEvent
)

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False

class StudentProfileInline(admin.StackedInline):
    model = StudentProfile
    fk_name = 'user'
    can_delete = False

class CustomUserAdmin(UserAdmin):
    inlines = (ProfileInline, StudentProfileInline)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')

from django.urls import reverse
from django.utils.safestring import mark_safe

class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone_no', 'is_class_teacher_of')
    readonly_fields = ('change_password_link',)
    
    def change_password_link(self, obj):
        if obj.user:
            url = reverse('admin:auth_user_password_change', args=[obj.user.id])
            return mark_safe(f'<a href="{url}" class="button" style="background-color: #FF6600; color: white; padding: 5px 12px; border-radius: 6px; font-weight: bold; text-decoration: none;">Change Password for {obj.user.username}</a>')
        return "No User Linked"
    change_password_link.short_description = "Password Management"

class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'class_name', 'roll_no', 'admission_no', 'status')
    readonly_fields = ('change_password_link',)
    
    def change_password_link(self, obj):
        if obj.user:
            url = reverse('admin:auth_user_password_change', args=[obj.user.id])
            return mark_safe(f'<a href="{url}" class="button" style="background-color: #FF6600; color: white; padding: 5px 12px; border-radius: 6px; font-weight: bold; text-decoration: none;">Change Password for {obj.user.username}</a>')
        return "No User Linked"
    change_password_link.short_description = "Password Management"

admin.site.register(User, CustomUserAdmin)
admin.site.register(Profile, ProfileAdmin)
admin.site.register(StudentProfile, StudentProfileAdmin)
admin.site.register(SiteConfig)
admin.site.register(Attendance)
admin.site.register(Marks)
admin.site.register(EditRequest)
admin.site.register(Timetable)
admin.site.register(Message)
admin.site.register(LeaveApplication)
admin.site.register(GalleryEvent)
