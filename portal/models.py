from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import json

class User(AbstractUser):
    # Custom User model to allow direct scalability if needed
    pass

class Profile(models.Model):
    ROLE_CHOICES = [
        ('principal', 'Principal'),
        ('vp', 'Vice-Principal'),
        ('teacher', 'Teacher'),
        ('staff', 'Staff'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='teacher')
    phone_no = models.CharField(max_length=15, blank=True, null=True)
    assigned_subjects = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="Comma-separated list of subjects this teacher can teach, e.g.: Hindi, English, Mathematics"
    )
    is_class_teacher_of = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        help_text="Class name if this teacher is a Class Teacher, e.g.: Class X"
    )

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"

    def get_assigned_subjects(self):
        if self.assigned_subjects:
            return [s.strip() for s in self.assigned_subjects.split(',') if s.strip()]
        return []


class StudentProfile(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('vp_pending', 'VP Pending'),
        ('principal_pending', 'Principal Pending'),
        ('active', 'Active'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    roll_no = models.CharField(max_length=20)
    admission_no = models.CharField(max_length=50, unique=True)
    dob = models.DateField(null=True, blank=True)
    father_name = models.CharField(max_length=100)
    mother_name = models.CharField(max_length=100)
    address = models.TextField()
    mobile_no = models.CharField(max_length=15)
    class_name = models.CharField(max_length=50)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='draft')
    class_teacher = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='my_students',
        help_text="The teacher who onboarded this student and acts as their Class Teacher."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.class_name} (Roll: {self.roll_no})"


class SiteConfig(models.Model):
    academic_year = models.CharField(max_length=20, default='2026-27')
    copy_show_flag = models.BooleanField(default=False)
    copy_show_exams = models.CharField(
        max_length=255, 
        blank=True, 
        default='Term-I, Term-II', 
        help_text="Comma-separated list of exam names where Copy Show is enabled, e.g.: Term-I, Term-II"
    )
    results_published = models.BooleanField(default=False)
    school_working_days = models.IntegerField(default=220)
    active_copy_show_exam = models.CharField(max_length=50, default='Term-I')
    active_exam_stage = models.CharField(
        max_length=10, 
        choices=[
            ('PT-01', 'Periodic Test 1 (PT-01)'), 
            ('SA-01', 'Summative Assessment 1 (SA-01)'), 
            ('PT-02', 'Periodic Test 2 (PT-02)'), 
            ('SA-02', 'Summative Assessment 2 (SA-02)')
        ], 
        default='PT-01'
    )
    
    # CMS settings
    logo = models.FileField(upload_to='logo/', blank=True, null=True)
    principal_name = models.CharField(max_length=100, default='Shri Ram Prakash')
    principal_message = models.TextField(
        default="Welcome to Saraswati Shishu Vidya Mandir Tamar. We are committed to building character and value-based education."
    )
    principal_bio = models.TextField(
        default="Serving as the Principal since 2021, with over 20 years of dedication to teaching and academic leadership."
    )
    principal_photo = models.FileField(upload_to='principal/', blank=True, null=True)

    @property
    def logo_url(self):
        if self.logo:
            return self.logo.url
        return None

    @property
    def principal_photo_url(self):
        if self.principal_photo:
            return self.principal_photo.url
        return None

    def __str__(self):
        return f"System Config ({self.academic_year})"


class CarouselImage(models.Model):
    image = models.FileField(upload_to='carousel_images/')
    caption = models.CharField(max_length=255, blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.caption or f"Carousel Image {self.id}"


class Notice(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Attendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
    ]
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    marked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='marked_attendances')

    class Meta:
        unique_together = ('student', 'date')

    def __str__(self):
        return f"{self.student.user.username} - {self.date}: {self.status}"


class Marks(models.Model):
    SUBJECT_CHOICES = [
        ('Hindi', 'Hindi'),
        ('English', 'English'),
        ('Mathematics', 'Mathematics'),
        ('Science', 'Science'),
        ('Social Science', 'Social Science'),
        ('Sanskrit', 'Sanskrit'),
        ('G.K.', 'G.K.'),
        ('Drawing', 'Drawing'),
        ('Computer', 'Computer'),
        ('Physical & Sports', 'Physical & Sports'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_class_teacher', 'Pending Class Teacher Verification'),
        ('pending_vp', 'Pending VP Vetting'),
        ('pending_principal', 'Pending Principal Ultimate Approval'),
        ('approved', 'Approved'),
    ]
    
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='marks_records')
    subject = models.CharField(max_length=50, choices=SUBJECT_CHOICES)
    
    # Term 1 marks (Max 50 total: FA-1 out of 10, SA-1 out of 40)
    term1_fa = models.FloatField(default=0.0)  # Max 10
    term1_sa = models.FloatField(default=0.0)  # Max 40
    
    # Term 2 marks (Max 50 total: FA-2 out of 10, SA-2 out of 40)
    term2_fa = models.FloatField(default=0.0)  # Max 10
    term2_sa = models.FloatField(default=0.0)  # Max 40
    
    scanned_sheet = models.FileField(upload_to='scanned_sheets/', blank=True, null=True)
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='draft')
    
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='recorded_marks')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'subject')
        verbose_name_plural = "Marks"

    def __str__(self):
        return f"{self.student.user.username} - {self.subject} ({self.status})"

    def term1_total(self):
        return self.term1_fa + self.term1_sa

    def term2_total(self):
        return self.term2_fa + self.term2_sa

    def grand_total(self):
        return self.term1_total() + self.term2_total()

    def get_grade_info(self):
        total = self.grand_total()
        if 91 <= total <= 100:
            return 'A1', 10.0
        elif 81 <= total <= 90:
            return 'A2', 9.0
        elif 71 <= total <= 80:
            return 'B1', 8.0
        elif 61 <= total <= 70:
            return 'B2', 7.0
        elif 51 <= total <= 60:
            return 'C1', 6.0
        elif 41 <= total <= 50:
            return 'C2', 5.0
        elif 33 <= total <= 40:
            return 'D', 4.0
        elif 21 <= total <= 32:
            return 'E1', 0.0
        else:
            return 'E2', 0.0

    @property
    def grade(self):
        return self.get_grade_info()[0]

    @property
    def grade_point(self):
        return self.get_grade_info()[1]


class EditRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved & Overridden'),
        ('rejected', 'Rejected'),
    ]
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='edit_requests')
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='raised_edit_requests')
    requested_data = models.TextField(help_text="JSON representation of modified student fields")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def get_data_dict(self):
        try:
            return json.loads(self.requested_data)
        except Exception:
            return {}

    def __str__(self):
        return f"Edit Request by Student {self.student.user.username} ({self.status})"


class Timetable(models.Model):
    DAY_CHOICES = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
    ]
    PERIOD_CHOICES = [(i, f"Period {i}") for i in range(1, 9)]

    class_name = models.CharField(max_length=50)
    day_of_week = models.CharField(max_length=20, choices=DAY_CHOICES)
    period_number = models.IntegerField(choices=PERIOD_CHOICES)
    subject = models.CharField(max_length=100)
    teacher = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True, related_name='timetable_classes')

    class Meta:
        unique_together = ('class_name', 'day_of_week', 'period_number')

    def __str__(self):
        return f"{self.class_name} - {self.day_of_week} (Period {self.period_number}): {self.subject}"


class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Msg from {self.sender.username} to {self.recipient.username} @ {self.timestamp}"


class LeaveApplication(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='leaves')
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leaves')
    created_at = models.DateTimeField(auto_now_add=True)

    def duration_days(self):
        delta = self.end_date - self.start_date
        return delta.days + 1

    def __str__(self):
        return f"Leave for {self.student.user.username} ({self.start_date} to {self.end_date})"


class GalleryEvent(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    image = models.FileField(upload_to='gallery/')
    date = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return self.title


class UserLoginStatus(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='login_status')
    is_logged_in = models.BooleanField(default=False)
    last_login_time = models.DateTimeField(null=True, blank=True)
    last_logout_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "User Login Statuses"

    def __str__(self):
        return f"{self.user.username} - {'Logged In' if self.is_logged_in else 'Logged Out'}"


from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

@receiver(user_logged_in)
def handle_user_login(sender, request, user, **kwargs):
    status, created = UserLoginStatus.objects.get_or_create(user=user)
    status.is_logged_in = True
    status.last_login_time = timezone.now()
    status.save()

@receiver(user_logged_out)
def handle_user_logout(sender, request, user, **kwargs):
    if user:
        status, created = UserLoginStatus.objects.get_or_create(user=user)
        status.is_logged_in = False
        status.last_logout_time = timezone.now()
        status.save()


class SchoolCalendar(models.Model):
    STATUS_CHOICES = [
        ('holiday', 'Holiday / Sunday Off'),
        ('event', 'School Event / Function'),
        ('working_sunday', 'Working Sunday (Override)'),
    ]
    date = models.DateField(unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='holiday')

    def __str__(self):
        return f"{self.date} - {self.title} ({self.get_status_display()})"

