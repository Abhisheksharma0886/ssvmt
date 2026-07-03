from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponse, JsonResponse
from django.db import IntegrityError
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator
from .models import (
    User, Profile, StudentProfile, SiteConfig, Attendance, 
    Marks, EditRequest, Timetable, Message, LeaveApplication, CarouselImage, Notice,
    GalleryEvent, UserLoginStatus, SchoolCalendar
)
import json
import calendar

def generate_username(first_name):
    base = "".join(c for c in first_name.lower() if c.isalnum())
    if not base:
        base = "user"
    suffix = ".ssvmt"
    candidate = f"{base}{suffix}"
    counter = 2
    while User.objects.filter(username=candidate).exists():
        candidate = f"{base}{counter}{suffix}"
        counter += 1
    return candidate

# Decorator to restrict views by user role
def role_required(allowed_roles):
    def decorator(view_func):
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            has_access = False
            if hasattr(request.user, 'profile'):
                if request.user.profile.role in allowed_roles:
                    has_access = True
            
            if 'student' in allowed_roles and hasattr(request.user, 'student_profile'):
                has_access = True
                
            if not has_access:
                return HttpResponseForbidden("You are not authorized to view this page.")
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

# Get Site Config helper
def get_site_config():
    config, created = SiteConfig.objects.get_or_create(id=1)
    return config

# PUBLIC WEBSITE VIEWS
def home_view(request):
    config = get_site_config()
    carousel_images = CarouselImage.objects.all().order_by('order')[:5]
    notices = Notice.objects.filter(is_active=True).order_by('-created_at')
    gallery_events = GalleryEvent.objects.all().order_by('-date')
    
    context = {
        'config': config,
        'carousel_images': carousel_images,
        'notices': notices,
        'gallery_events': gallery_events,
    }
    return render(request, 'portal/index.html', context)

# AUTHENTICATION
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        user = authenticate(request, username=u, password=p)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password.")
    return render(request, 'portal/login.html')

def logout_view(request):
    logout(request)
    messages.info(request, "Logged out successfully.")
    return redirect('home')

# DASHBOARD ROUTER & BOOTSTRAP SCREEN
@login_required
def dashboard_view(request):
    config = get_site_config()
    
    # 1. Superuser Scope (Bootstrapper Only)
    if request.user.is_superuser:
        # Check if Principal account exists
        principal_exists = Profile.objects.filter(role='principal').exists()
        principal_user = None
        if principal_exists:
            principal_user = Profile.objects.filter(role='principal').first().user
            
        context = {
            'config': config,
            'principal_exists': principal_exists,
            'principal_user': principal_user,
        }
        return render(request, 'portal/dashboards/bootstrap.html', context)
        
    # 2. Institutional Roles
    if hasattr(request.user, 'profile'):
        role = request.user.profile.role
        if role == 'principal':
            return principal_dashboard(request, config)
        elif role == 'vp':
            return vp_dashboard(request, config)
        elif role == 'teacher':
            return teacher_dashboard(request, config)
            
    if hasattr(request.user, 'student_profile'):
        return student_dashboard(request, config)
        
    return render(request, 'portal/dashboards/unassigned.html')


# SUPERUSER BOOTSTRAP PRINCIPAL VIEW
@login_required
def bootstrap_principal_view(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Only the Superuser can bootstrap the Principal account.")
        
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        phone_no = request.POST.get('phone_no')
        
        username = generate_username(first_name)
        
        # Guard: Ensure no principal exists
        if Profile.objects.filter(role='principal').exists():
            messages.error(request, "Principal account already exists.")
            return redirect('dashboard')
            
        try:
            user = User.objects.create_user(
                username=username,
                password=password,
                email=email,
                first_name=first_name,
                last_name=last_name
            )
            Profile.objects.create(
                user=user,
                role='principal',
                phone_no=phone_no,
                assigned_subjects='Hindi, English, Mathematics',
                is_class_teacher_of='Class X'
            )
            messages.success(request, f"Bootstrapping complete! Principal account '{username}' created successfully.")
        except IntegrityError:
            messages.error(request, "Username already exists.")
            
    return redirect('dashboard')

@login_required
def toggle_principal_status_view(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Only Super Admin can toggle Principal status.")
    principal_profile = Profile.objects.filter(role='principal').first()
    if principal_profile:
        p_user = principal_profile.user
        p_user.is_active = not p_user.is_active
        p_user.save()
        status = "Activated" if p_user.is_active else "Deactivated"
        messages.success(request, f"Principal account '{p_user.username}' has been successfully {status}.")
    else:
        messages.error(request, "No Principal account exists to toggle.")
    return redirect('dashboard')


# PRINCIPAL DASHBOARD (With CMS and Approvals)
def principal_dashboard(request, config):
    pending_students = StudentProfile.objects.filter(status__in=['vp_pending', 'principal_pending'])
    pending_edits = EditRequest.objects.filter(status='pending')
    pending_marks = Marks.objects.filter(status__in=['pending_principal', 'pending_vp', 'pending_class_teacher'])
    employees = Profile.objects.exclude(role='principal')
    leaves = LeaveApplication.objects.all().order_by('-created_at')[:10]
    
    # CMS data
    notices = Notice.objects.all()
    carousel_slides = CarouselImage.objects.all().order_by('order')
    gallery_events = GalleryEvent.objects.all().order_by('-date')
    
    # New: Class Results Manager Table
    classes_list = ['Class I', 'Class II', 'Class III', 'Class IV', 'Class V', 'Class VI', 'Class VII', 'Class VIII', 'Class IX', 'Class X']
    selected_class = request.GET.get('result_class', '')
    class_students_results = []
    
    if selected_class:
        students = StudentProfile.objects.filter(class_name=selected_class, status='active')
        for student in students:
            student_marks = Marks.objects.filter(student=student)
            approved_count = student_marks.filter(status='approved').count()
            subjects_status = {m.subject: m.status for m in student_marks}
            
            class_students_results.append({
                'student': student,
                'approved_count': approved_count,
                'subjects_status': subjects_status,
                'marks_list': student_marks,
            })
            
    # For Principal Calendar Manager:
    import datetime
    today = timezone.localdate()
    if today.month >= 4:
        acad_start_year = today.year
    else:
        acad_start_year = today.year - 1

    selected_month = request.GET.get('calendar_month', '')
    if selected_month.isdigit():
        selected_month = int(selected_month)
    else:
        selected_month = today.month

    if selected_month >= 4:
        calendar_year = acad_start_year
    else:
        calendar_year = acad_start_year + 1

    first_weekday, num_days = calendar.monthrange(calendar_year, selected_month)
    
    month_calendar_events = SchoolCalendar.objects.filter(
        date__year=calendar_year,
        date__month=selected_month
    )
    calendar_events_by_day = {evt.date.day: evt for evt in month_calendar_events}
    
    calendar_days = []
    for _ in range(first_weekday):
        calendar_days.append({
            'day': '',
            'status': 'empty',
            'date_str': '',
            'event_id': '',
            'event_title': '',
            'event_desc': '',
            'event_status': ''
        })
        
    for d in range(1, num_days + 1):
        date_obj = datetime.date(calendar_year, selected_month, d)
        day_event = calendar_events_by_day.get(d)
        is_sunday = (date_obj.weekday() == 6)
        
        date_str = date_obj.strftime("%Y-%m-%d")
        
        event_title = ""
        event_desc = ""
        event_id = ""
        event_status = ""
        
        if is_sunday:
            status = 'holiday'
        else:
            status = 'upcoming'
            
        if day_event:
            event_id = day_event.id
            event_title = day_event.title
            event_desc = day_event.description or ""
            event_status = day_event.status
            if day_event.status == 'holiday':
                status = 'holiday'
            elif day_event.status == 'event':
                status = 'event'
            elif day_event.status == 'working_sunday':
                status = 'working_sunday'
                
        calendar_days.append({
            'day': d,
            'status': status,
            'date_str': date_str,
            'event_id': event_id,
            'event_title': event_title,
            'event_desc': event_desc,
            'event_status': event_status
        })
        
    months_choices = [
        (4, 'April'), (5, 'May'), (6, 'June'), (7, 'July'),
        (8, 'August'), (9, 'September'), (10, 'October'), (11, 'November'),
        (12, 'December'), (1, 'January'), (2, 'February'), (3, 'March')
    ]
    
    selected_date_obj = datetime.date(calendar_year, selected_month, 1)
    current_month_name = selected_date_obj.strftime("%B %Y")

    context = {
        'config': config,
        'pending_students': pending_students,
        'pending_edits': pending_edits,
        'pending_marks': pending_marks,
        'employees': employees,
        'leaves': leaves,
        'notices': notices,
        'carousel_slides': carousel_slides,
        'gallery_events': gallery_events,
        'classes_list': classes_list,
        'selected_result_class': selected_class,
        'class_students_results': class_students_results,
        'calendar_days': calendar_days,
        'current_month_name': current_month_name,
        'selected_month': selected_month,
        'months_choices': months_choices,
        'active_tab': 'principal'
    }
    return render(request, 'portal/dashboards/principal.html', context)


# PRINCIPAL CMS ACTIONS
@role_required(['principal'])
def cms_update_settings_view(request):
    if request.method == 'POST':
        config = get_site_config()
        config.principal_name = request.POST.get('principal_name', config.principal_name)
        config.principal_message = request.POST.get('principal_message', config.principal_message)
        config.principal_bio = request.POST.get('principal_bio', config.principal_bio)
        
        # Dynamic Logo upload
        if request.FILES.get('logo'):
            config.logo = request.FILES.get('logo')
            
        # Principal Photo (will render aspect ratio 1:1)
        if request.FILES.get('principal_photo'):
            config.principal_photo = request.FILES.get('principal_photo')
            
        config.save()
        messages.success(request, "Principal Desk CMS settings updated successfully.")
    return redirect('dashboard')


@role_required(['principal'])
def cms_upload_carousel_view(request):
    if request.method == 'POST':
        order = request.POST.get('order', 1)
        caption = request.POST.get('caption', '')
        image = request.FILES.get('carousel_image')
        
        if image:
            # Overwrite or create Carousel slot
            CarouselImage.objects.update_or_create(
                order=order,
                defaults={'image': image, 'caption': caption}
            )
            messages.success(request, f"Carousel Slide #{order} updated successfully.")
        else:
            messages.error(request, "No image file provided.")
    return redirect('dashboard')


@role_required(['principal'])
def cms_add_notice_view(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        if title and content:
            Notice.objects.create(title=title, content=content, is_active=True)
            messages.success(request, "Notice board circular posted successfully.")
    return redirect('dashboard')


@role_required(['principal'])
def cms_delete_notice_view(request, notice_id):
    notice = get_object_or_404(Notice, id=notice_id)
    notice.delete()
    messages.success(request, "Notice deleted successfully.")
    return redirect('dashboard')


@role_required(['principal'])
def cms_delete_logo_view(request):
    config = get_site_config()
    if config.logo:
        try:
            config.logo.delete(save=False)
        except Exception:
            pass
        config.logo = None
        config.save()
        messages.success(request, "School Logo deleted successfully. Reverted to static fallback.")
    else:
        messages.info(request, "No custom logo currently uploaded.")
    
    referer = request.META.get('HTTP_REFERER', 'dashboard')
    return redirect(referer)


@role_required(['principal'])
def cms_delete_principal_photo_view(request):
    config = get_site_config()
    if config.principal_photo:
        try:
            config.principal_photo.delete(save=False)
        except Exception:
            pass
        config.principal_photo = None
        config.save()
        messages.success(request, "Principal Photo deleted successfully. Reverted to static fallback.")
    else:
        messages.info(request, "No custom Principal photo currently uploaded.")
        
    referer = request.META.get('HTTP_REFERER', 'dashboard')
    return redirect(referer)


@role_required(['principal'])
def cms_delete_carousel_view(request, slide_id):
    slide = get_object_or_404(CarouselImage, id=slide_id)
    try:
        slide.image.delete(save=False)
    except Exception:
        pass
    slide.delete()
    messages.success(request, f"Carousel Slide #{slide.order} deleted successfully.")
    
    referer = request.META.get('HTTP_REFERER', 'dashboard')
    return redirect(referer)


# VP DASHBOARD
def vp_dashboard(request, config):
    timetables = Timetable.objects.all().order_by('class_name', 'day_of_week', 'period_number')
    pending_students = StudentProfile.objects.filter(status='vp_pending')
    pending_marks = Marks.objects.filter(status='pending_vp')
    leaves = LeaveApplication.objects.all().order_by('-created_at')[:10]
    teachers = Profile.objects.filter(role='teacher')
    classes = ['Class I', 'Class II', 'Class III', 'Class IV', 'Class V', 'Class VI', 'Class VII', 'Class VIII', 'Class IX', 'Class X']
    
    context = {
        'config': config,
        'timetables': timetables,
        'pending_students': pending_students,
        'pending_marks': pending_marks,
        'leaves': leaves,
        'teachers': teachers,
        'classes': classes,
        'active_tab': 'vp'
    }
    return render(request, 'portal/dashboards/vp.html', context)


# TEACHER DASHBOARD
def teacher_dashboard(request, config):
    profile = request.user.profile
    is_class_teacher = bool(profile.is_class_teacher_of)
    my_class = profile.is_class_teacher_of
    
    class_students = []
    pending_class_onboarding = []
    leaves_to_approve = []
    edit_requests_to_review = []
    attendance_marked_today = False
    
    if is_class_teacher:
        class_students = StudentProfile.objects.filter(class_name=my_class, status='active')
        today = timezone.localdate()
        for student in class_students:
            att = Attendance.objects.filter(student=student, date=today).first()
            student.today_status = att.status if att else 'present'
        pending_class_onboarding = StudentProfile.objects.filter(class_name=my_class).exclude(status='active')
        leaves_to_approve = LeaveApplication.objects.filter(student__class_name=my_class, status='pending')
        edit_requests_to_review = EditRequest.objects.filter(student__class_name=my_class, status='pending')
        attendance_marked_today = Attendance.objects.filter(student__class_name=my_class, date=timezone.localdate()).exists()

    assigned_subs = profile.get_assigned_subjects()
    received_msgs = Message.objects.filter(recipient=request.user).order_by('-timestamp')[:5]
    
    context = {
        'config': config,
        'profile': profile,
        'is_class_teacher': is_class_teacher,
        'my_class': my_class,
        'class_students': class_students,
        'pending_class_onboarding': pending_class_onboarding,
        'leaves_to_approve': leaves_to_approve,
        'edit_requests_to_review': edit_requests_to_review,
        'assigned_subs': assigned_subs,
        'received_msgs': received_msgs,
        'attendance_marked_today': attendance_marked_today,
        'active_tab': 'teacher'
    }
    return render(request, 'portal/dashboards/teacher.html', context)


# STUDENT DASHBOARD
def student_dashboard(request, config):
    student = request.user.student_profile
    leaves = LeaveApplication.objects.filter(student=student).order_by('-created_at')
    timetable = Timetable.objects.filter(class_name=student.class_name).order_by('day_of_week', 'period_number')
    
    marks = []
    cgpa = 0.0
    overall_percentage = 0.0
    total_obtained = 0.0
    total_max = 0.0
    rank = 1
    
    if config.results_published and student.status == 'active':
        marks = Marks.objects.filter(student=student, status='approved')
        gps = [m.grade_point for m in marks]
        if gps:
            cgpa = sum(gps) / len(gps)
        total_obtained = sum(m.grand_total() for m in marks)
        total_max = len(marks) * 100.0
        if total_max > 0:
            overall_percentage = (total_obtained / total_max) * 100
        rank = get_class_rank(student)

    import datetime
    today = timezone.localdate()
    if today.month >= 4:
        acad_start_year = today.year
    else:
        acad_start_year = today.year - 1
    acad_start = datetime.date(acad_start_year, 4, 1)

    total_working = Attendance.objects.filter(student=student, date__gte=acad_start, date__lte=today).count()
    # Count "Late" as present inside dashboards
    attended = Attendance.objects.filter(student=student, date__gte=acad_start, date__lte=today, status__in=['present', 'late']).count()
    attendance_percentage = (attended / total_working * 100) if total_working > 0 else 0.0

    # Monthly calendar days logic
    selected_month = request.GET.get('calendar_month', '')
    if selected_month.isdigit():
        selected_month = int(selected_month)
    else:
        selected_month = today.month

    if selected_month >= 4:
        calendar_year = acad_start_year
    else:
        calendar_year = acad_start_year + 1

    first_weekday, num_days = calendar.monthrange(calendar_year, selected_month)

    # Get SchoolCalendar overrides and events for the selected month/year
    month_calendar_events = SchoolCalendar.objects.filter(
        date__year=calendar_year,
        date__month=selected_month
    )
    calendar_events_by_day = {evt.date.day: evt for evt in month_calendar_events}

    # Get monthly student attendance
    month_attendance = Attendance.objects.filter(
        student=student,
        date__year=calendar_year,
        date__month=selected_month
    )
    attendance_by_day = {att.date.day: att.status for att in month_attendance}

    calendar_days = []
    # Prepend empty blocks to align starting weekday (0 = Monday, 6 = Sunday)
    for _ in range(first_weekday):
        calendar_days.append({
            'day': '',
            'status': 'empty',
            'title': '',
            'desc': ''
        })

    for d in range(1, num_days + 1):
        date_obj = datetime.date(calendar_year, selected_month, d)
        day_event = calendar_events_by_day.get(d)
        is_sunday = (date_obj.weekday() == 6)

        event_title = ""
        event_desc = ""

        if is_sunday:
            status = 'holiday'
        else:
            status = 'upcoming'

        if day_event:
            event_title = day_event.title
            event_desc = day_event.description or ""
            if day_event.status == 'holiday':
                status = 'holiday'
            elif day_event.status == 'event':
                status = 'event'
            elif day_event.status == 'working_sunday':
                status = 'upcoming'

        # If in the past, attendance takes precedence
        if date_obj <= today:
            if d in attendance_by_day:
                status = attendance_by_day[d] # present, absent, late

        calendar_days.append({
            'day': d,
            'status': status,
            'title': event_title,
            'desc': event_desc
        })

    months_choices = [
        (4, 'April'), (5, 'May'), (6, 'June'), (7, 'July'),
        (8, 'August'), (9, 'September'), (10, 'October'), (11, 'November'),
        (12, 'December'), (1, 'January'), (2, 'February'), (3, 'March')
    ]

    selected_date_obj = datetime.date(calendar_year, selected_month, 1)
    current_month_name = selected_date_obj.strftime("%B %Y")

    context = {
        'config': config,
        'student': student,
        'leaves': leaves,
        'timetable': timetable,
        'marks': marks,
        'cgpa': round(cgpa, 2),
        'overall_percentage': round(overall_percentage, 2),
        'rank': rank,
        'attended': attended,
        'total_working': total_working,
        'attendance_percentage': round(attendance_percentage, 2),
        'calendar_days': calendar_days,
        'current_month_name': current_month_name,
        'selected_month': selected_month,
        'months_choices': months_choices,
        'active_tab': 'student'
    }
    return render(request, 'portal/dashboards/student.html', context)


# Class Rank calculation helper
def get_class_rank(student_profile):
    students_in_class = StudentProfile.objects.filter(class_name=student_profile.class_name, status='active')
    student_totals = []
    for s in students_in_class:
        m_rec = Marks.objects.filter(student=s, status='approved')
        total = sum(m.grand_total() for m in m_rec)
        student_totals.append((s.id, total))
    
    student_totals.sort(key=lambda x: x[1], reverse=True)
    
    for rank, (sid, _) in enumerate(student_totals, 1):
        if sid == student_profile.id:
            return rank
    return 1


# ONBOARDING EMPLOYEES (Principal Action)
@role_required(['principal'])
def onboard_employee_view(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        role = request.POST.get('role')
        phone_no = request.POST.get('phone_no')
        assigned_subjects = request.POST.getlist('assigned_subjects')
        is_class_teacher_of = request.POST.get('is_class_teacher_of', '')
        
        username = generate_username(first_name)
        assigned_subjects_str = ", ".join(assigned_subjects)
        
        if role == 'class_teacher':
            role = 'teacher'
            if not is_class_teacher_of:
                messages.error(request, "Please specify which class this Class Teacher is assigned to.")
                return redirect('dashboard')
        else:
            is_class_teacher_of = None
            
        if is_class_teacher_of:
            already_assigned = Profile.objects.filter(is_class_teacher_of=is_class_teacher_of).exists()
            if already_assigned:
                messages.error(request, f"{is_class_teacher_of} Class Teacher already assigned.")
                return redirect('dashboard')
                
        try:
            user = User.objects.create_user(
                username=username,
                password=password,
                email=email,
                first_name=first_name,
                last_name=last_name
            )
            Profile.objects.create(
                user=user,
                role=role,
                phone_no=phone_no,
                assigned_subjects=assigned_subjects_str,
                is_class_teacher_of=is_class_teacher_of
            )
            messages.success(request, f"Successfully onboarded employee: {user.get_full_name()} (Username: {username})")
        except IntegrityError:
            messages.error(request, "Username already exists.")
            
    return redirect('dashboard')


# ONBOARDING STUDENTS (Class Teacher Action)
@role_required(['teacher'])
def onboard_student_view(request):
    profile = request.user.profile
    if not profile.is_class_teacher_of:
        return HttpResponseForbidden("Only Class Teachers can onboard students.")
        
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        roll_no = request.POST.get('roll_no')
        admission_no = request.POST.get('admission_no')
        dob = request.POST.get('dob')
        father_name = request.POST.get('father_name')
        mother_name = request.POST.get('mother_name')
        address = request.POST.get('address')
        mobile_no = request.POST.get('mobile_no')
        
        username = generate_username(first_name)
        try:
            user = User.objects.create_user(
                username=username,
                password=password,
                email=email,
                first_name=first_name,
                last_name=last_name
            )
            
            student = StudentProfile.objects.create(
                user=user,
                roll_no=roll_no,
                admission_no=admission_no,
                dob=dob if dob else None,
                father_name=father_name,
                mother_name=mother_name,
                address=address,
                mobile_no=mobile_no,
                class_name=profile.is_class_teacher_of,
                class_teacher=request.user,
                status='draft'
            )
            
            # Pre-populate empty Marks sheets for 10 core subjects
            subjects = [c[0] for c in Marks.SUBJECT_CHOICES]
            for sub in subjects:
                Marks.objects.create(student=student, subject=sub, status='draft', updated_by=request.user)
                
            messages.success(request, f"Student Draft created for {user.get_full_name()} (Username: {username}). Marks sheet initialized.")
        except IntegrityError:
            messages.error(request, "Username or Admission Number already exists.")
            
    return redirect('dashboard')


# ONBOARDING APPROVAL & OVERRIDES (VP / Principal)
@role_required(['vp', 'principal'])
def approve_student_view(request, student_id):
    student = get_object_or_404(StudentProfile, id=student_id)
    user_role = request.user.profile.role if hasattr(request.user, 'profile') else 'admin'
    
    if request.method == 'POST' or request.GET.get('action') == 'submit':
        action = request.POST.get('action') or request.GET.get('action')
        
        if action == 'submit_to_vp':
            student.status = 'vp_pending'
            student.save()
            messages.success(request, f"Student profile of {student.user.get_full_name()} submitted to VP for vetting.")
            
        elif action == 'approve':
            if request.user.is_superuser or user_role == 'principal':
                # Principal Override: Short-circuit VP approval and convert directly to Active
                student.status = 'active'
                student.save()
                messages.success(request, f"Principal Override: Student {student.user.get_full_name()} is now active.")
            elif user_role == 'vp':
                if student.status == 'vp_pending':
                    student.status = 'principal_pending'
                    student.save()
                    messages.success(request, f"VP Approved. Forwarded {student.user.get_full_name()} to Principal.")
                else:
                    messages.error(request, "Student not in VP pending queue.")
                    
        elif action == 'override_active':
            if request.user.is_superuser or user_role == 'principal':
                student.status = 'active'
                student.save()
                messages.success(request, f"Activated Student profile for {student.user.get_full_name()}.")
                
    return redirect('dashboard')


@role_required(['vp', 'principal', 'teacher'])
def reject_student_view(request, student_id):
    student = get_object_or_404(StudentProfile, id=student_id)
    student.status = 'draft'
    student.save()
    messages.warning(request, f"Returned student {student.user.get_full_name()} to Draft status.")
    return redirect('dashboard')


# TIMETABLE VIEW & COPY TOOL
@role_required(['vp', 'principal'])
def timetable_view(request):
    if request.method == 'POST':
        class_name = request.POST.get('class_name')
        day_of_week = request.POST.get('day_of_week')
        period_number = int(request.POST.get('period_number'))
        subject = request.POST.get('subject')
        teacher_id = request.POST.get('teacher_id')
        
        teacher = get_object_or_404(Profile, id=teacher_id)
        
        try:
            Timetable.objects.update_or_create(
                class_name=class_name,
                day_of_week=day_of_week,
                period_number=period_number,
                defaults={'subject': subject, 'teacher': teacher}
            )
            messages.success(request, f"Timetable slot saved for {class_name} - {day_of_week} Period {period_number}.")
        except Exception as e:
            messages.error(request, f"Failed to save slot: {str(e)}")
            
    return redirect('dashboard')


@role_required(['vp', 'principal'])
def copy_timetable_view(request):
    if request.method == 'POST':
        class_name = request.POST.get('class_name')
        source_day = request.POST.get('source_day')
        target_day = request.POST.get('target_day')
        
        if source_day == target_day:
            messages.error(request, "Source and Target days must be different.")
            return redirect('dashboard')
            
        source_slots = Timetable.objects.filter(class_name=class_name, day_of_week=source_day)
        
        if not source_slots.exists():
            messages.warning(request, f"No timetable slots found for {class_name} on {source_day} to copy.")
            return redirect('dashboard')
            
        Timetable.objects.filter(class_name=class_name, day_of_week=target_day).delete()
        
        for slot in source_slots:
            Timetable.objects.create(
                class_name=class_name,
                day_of_week=target_day,
                period_number=slot.period_number,
                subject=slot.subject,
                teacher=slot.teacher
            )
            
        messages.success(request, f"Timetable for {class_name} on {target_day} copied same as {source_day} successfully!")
        
    return redirect('dashboard')


# STUDENT PROFILE EDIT REQUEST SYSTEM
@role_required(['student', 'teacher', 'principal'])
def edit_profile_request_view(request):
    if request.method == 'POST':
        if hasattr(request.user, 'student_profile'):
            student = request.user.student_profile
            data = {
                'roll_no': request.POST.get('roll_no', student.roll_no),
                'dob': request.POST.get('dob', str(student.dob)),
                'father_name': request.POST.get('father_name', student.father_name),
                'mother_name': request.POST.get('mother_name', student.mother_name),
                'address': request.POST.get('address', student.address),
                'mobile_no': request.POST.get('mobile_no', student.mobile_no),
                'first_name': request.POST.get('first_name', request.user.first_name),
                'last_name': request.POST.get('last_name', request.user.last_name),
            }
            
            EditRequest.objects.create(
                student=student,
                requested_by=request.user,
                requested_data=json.dumps(data),
                status='pending'
            )
            messages.success(request, "Profile edit request submitted. Awaiting Class Teacher forwarding to Principal.")
            return redirect('dashboard')
            
        elif request.user.profile.role == 'teacher':
            req_id = request.POST.get('request_id')
            edit_req = get_object_or_404(EditRequest, id=req_id)
            messages.success(request, f"Forwarded edit request for {edit_req.student.user.get_full_name()} directly to Principal.")
            
    return redirect('dashboard')


@role_required(['principal'])
def approve_edit_request_view(request, request_id):
    edit_req = get_object_or_404(EditRequest, id=request_id)
    student = edit_req.student
    data = edit_req.get_data_dict()
    
    if 'roll_no' in data:
        student.roll_no = data['roll_no']
    if 'dob' in data and data['dob'] != 'None':
        student.dob = data['dob']
    if 'father_name' in data:
        student.father_name = data['father_name']
    if 'mother_name' in data:
        student.mother_name = data['mother_name']
    if 'address' in data:
        student.address = data['address']
    if 'mobile_no' in data:
        student.mobile_no = data['mobile_no']
    
    if 'first_name' in data:
        student.user.first_name = data['first_name']
    if 'last_name' in data:
        student.user.last_name = data['last_name']
    student.user.save()
    student.save()
    
    edit_req.status = 'approved'
    edit_req.save()
    
    messages.success(request, f"Database Override Complete: Student profile updated for {student.user.get_full_name()}.")
    return redirect('dashboard')


@role_required(['principal', 'teacher'])
def reject_edit_request_view(request, request_id):
    edit_req = get_object_or_404(EditRequest, id=request_id)
    edit_req.status = 'rejected'
    edit_req.save()
    messages.warning(request, f"Rejected profile edit request for {edit_req.student.user.get_full_name()}.")
    return redirect('dashboard')


# LEAVE APPLICATIONS
@role_required(['student'])
def apply_leave_view(request):
    if request.method == 'POST':
        student = request.user.student_profile
        start_str = request.POST.get('start_date')
        end_str = request.POST.get('end_date')
        reason = request.POST.get('reason')
        
        from datetime import datetime
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
            today = timezone.localdate()
            
            if start_date < today:
                messages.error(request, "Error: You can only apply for leave on future dates (today or later).")
                return redirect('dashboard')
            if end_date < start_date:
                messages.error(request, "Error: End date cannot be earlier than start date.")
                return redirect('dashboard')
                
            LeaveApplication.objects.create(
                student=student,
                start_date=start_date,
                end_date=end_date,
                reason=reason,
                status='pending'
            )
            messages.success(request, "Leave Application submitted successfully. Updated dashboards.")
        except Exception as e:
            messages.error(request, f"Error parsing dates: {e}")
            
    return redirect('dashboard')


@role_required(['teacher', 'vp', 'principal'])
def approve_leave_view(request, leave_id):
    leave = get_object_or_404(LeaveApplication, id=leave_id)
    leave.status = 'approved'
    leave.approved_by = request.user
    leave.save()
    messages.success(request, f"Approved leave application for {leave.student.user.get_full_name()}.")
    return redirect('dashboard')


@role_required(['teacher', 'vp', 'principal'])
def reject_leave_view(request, leave_id):
    leave = get_object_or_404(LeaveApplication, id=leave_id)
    leave.status = 'rejected'
    leave.save()
    messages.warning(request, f"Rejected leave application for {leave.student.user.get_full_name()}.")
    return redirect('dashboard')


@login_required
def print_leave_slip_view(request, leave_id):
    leave = get_object_or_404(LeaveApplication, id=leave_id)
    if leave.status != 'approved':
        return HttpResponseForbidden("Leave slip can only be generated for approved leave applications.")
    
    if hasattr(request.user, 'student_profile') and leave.student.user != request.user:
        return HttpResponseForbidden("You are not authorized to view this leave slip.")
        
    return render(request, 'portal/leave_slip.html', {'leave': leave})


# VERIFIED MESSAGING CHAT
@login_required
def chat_inbox_view(request):
    sent_to_me = Message.objects.filter(recipient=request.user)
    sent_by_me = Message.objects.filter(sender=request.user)
    
    contacts = []
    if hasattr(request.user, 'student_profile'):
        student = request.user.student_profile
        if student.class_teacher:
            contacts.append(student.class_teacher)
        class_teachers = Profile.objects.filter(role='teacher')
        for ct in class_teachers:
            if ct.user != student.class_teacher:
                contacts.append(ct.user)
    else:
        contacts = list(User.objects.exclude(id=request.user.id))
        
    contacts = list(set(contacts))
    for contact in contacts:
        contact.unread_count = Message.objects.filter(sender=contact, recipient=request.user, is_read=False).count()
    
    return render(request, 'portal/chat.html', {
        'contacts': contacts,
        'active_contact': None,
        'messages': []
    })


@login_required
def chat_detail_view(request, user_id):
    recipient = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            Message.objects.create(
                sender=request.user,
                recipient=recipient,
                content=content
            )
            return redirect('chat_detail', user_id=user_id)
            
    Message.objects.filter(sender=recipient, recipient=request.user).update(is_read=True)
    
    chat_messages = Message.objects.filter(
        Q(sender=request.user, recipient=recipient) |
        Q(sender=recipient, recipient=request.user)
    ).order_by('timestamp')
    
    contacts = []
    if hasattr(request.user, 'student_profile'):
        student = request.user.student_profile
        if student.class_teacher:
            contacts.append(student.class_teacher)
        class_teachers = Profile.objects.filter(role='teacher')
        for ct in class_teachers:
            contacts.append(ct.user)
    else:
        contacts = list(User.objects.exclude(id=request.user.id))
        
    contacts = list(set(contacts))
    for contact in contacts:
        contact.unread_count = Message.objects.filter(sender=contact, recipient=request.user, is_read=False).count()
    
    return render(request, 'portal/chat.html', {
        'contacts': contacts,
        'active_contact': recipient,
        'chat_messages': chat_messages
    })


# SUBJECT-SPECIFIC MARKS ENTRY RESTRICTIONS & PIPELINE
@role_required(['teacher', 'vp', 'principal'])
def marks_entry_view(request):
    profile = request.user.profile if hasattr(request.user, 'profile') else None
    config = get_site_config()
    
    selected_class = request.GET.get('class_name', '')
    selected_subject = request.GET.get('subject', '')
    
    classes = ['Class I', 'Class II', 'Class III', 'Class IV', 'Class V', 'Class VI', 'Class VII', 'Class VIII', 'Class IX', 'Class X']
    subjects = [c[0] for c in Marks.SUBJECT_CHOICES]
    
    if profile and profile.role == 'teacher':
        allowed_subjects = profile.get_assigned_subjects()
        assigned_classes = set()
        if profile.is_class_teacher_of:
            assigned_classes.add(profile.is_class_teacher_of)
        # Fetch from Timetable
        t_classes = Timetable.objects.filter(teacher=profile).values_list('class_name', flat=True).distinct()
        for tc in t_classes:
            if tc:
                assigned_classes.add(tc)
        classes = sorted(list(assigned_classes))
    else:
        allowed_subjects = subjects
        
    students = []
    marks_records = []
    
    if selected_class and selected_subject:
        if profile and profile.role == 'teacher' and selected_subject not in allowed_subjects:
            return HttpResponseForbidden(f"You are strictly restricted from entering marks for {selected_subject}.")
            
        students = StudentProfile.objects.filter(class_name=selected_class, status='active')
        for student in students:
            marks, created = Marks.objects.get_or_create(
                student=student, 
                subject=selected_subject,
                defaults={'status': 'draft', 'updated_by': request.user}
            )
            marks_records.append(marks)

    if request.method == 'POST':
        for record in marks_records:
            t1_fa = request.POST.get(f"t1_fa_{record.id}")
            t1_sa = request.POST.get(f"t1_sa_{record.id}")
            t2_fa = request.POST.get(f"t2_fa_{record.id}")
            t2_sa = request.POST.get(f"t2_sa_{record.id}")
            
            if t1_fa is not None: record.term1_fa = float(t1_fa)
            if t1_sa is not None: record.term1_sa = float(t1_sa)
            if t2_fa is not None: record.term2_fa = float(t2_fa)
            if t2_sa is not None: record.term2_sa = float(t2_sa)
            
            record.updated_by = request.user
            record.save()
            
        messages.success(request, f"Marks saved successfully for {selected_subject} ({selected_class}).")
        return redirect(f"/marks/?class_name={selected_class}&subject={selected_subject}")

    return render(request, 'portal/marks_entry.html', {
        'config': config,
        'classes': classes,
        'assigned_classes': classes,
        'subjects': subjects,
        'allowed_subjects': allowed_subjects,
        'selected_class': selected_class,
        'selected_subject': selected_subject,
        'marks_records': marks_records
    })


# Marks Pipeline transitions
@role_required(['teacher'])
def submit_marks_view(request, marks_id):
    marks = get_object_or_404(Marks, id=marks_id)
    if marks.status == 'draft':
        marks.status = 'pending_class_teacher'
        marks.save()
        messages.success(request, f"Submitted {marks.subject} marks for {marks.student.user.get_full_name()} to Class Teacher.")
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


@role_required(['teacher'])
def verify_marks_view(request, marks_id):
    marks = get_object_or_404(Marks, id=marks_id)
    if marks.student.class_teacher != request.user:
        return HttpResponseForbidden("Only the designated Class Teacher can verify these marks.")
        
    if marks.status == 'pending_class_teacher':
        marks.status = 'pending_vp'
        marks.save()
        messages.success(request, f"Verified marks for {marks.student.user.get_full_name()} and forwarded to VP.")
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


@role_required(['vp'])
def vet_marks_view(request, marks_id):
    marks = get_object_or_404(Marks, id=marks_id)
    if marks.status == 'pending_vp':
        marks.status = 'pending_principal'
        marks.save()
        messages.success(request, f"Vetted marks for {marks.student.user.get_full_name()} and forwarded to Principal.")
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


@role_required(['principal'])
def approve_marks_view(request, marks_id):
    marks = get_object_or_404(Marks, id=marks_id)
    user_role = request.user.profile.role if hasattr(request.user, 'profile') else 'admin'
    
    if request.user.is_superuser or user_role == 'principal':
        marks.status = 'approved'
        marks.save()
        messages.success(request, f"Principal Override Approved: {marks.subject} marks for {marks.student.user.get_full_name()} are now Approved.")
        
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


# DYNAMIC UPLOAD OF SCANNED ANSWER SHEETS (Copy Show Config)
@role_required(['teacher'])
def upload_scanned_sheet_view(request, marks_id):
    marks = get_object_or_404(Marks, id=marks_id)
    config = get_site_config()
    
    if not config.copy_show_flag:
        return HttpResponseForbidden("Copy Show feature is currently disabled by the Principal.")
        
    if request.method == 'POST' and request.FILES.get('scanned_sheet'):
        marks.scanned_sheet = request.FILES.get('scanned_sheet')
        marks.save()
        messages.success(request, "Scanned answer sheet uploaded successfully.")
        
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


# CONFIG FLAGS (Principal Control)
@role_required(['principal'])
def publish_results_view(request):
    config = get_site_config()
    approved_marks_exist = Marks.objects.filter(status='approved').exists()
    
    if not config.results_published:
        if not approved_marks_exist:
            messages.error(request, "Cannot publish results: No marks records have been approved by the Principal yet.")
            return redirect('dashboard')
            
    config.results_published = not config.results_published
    config.save()
    status = "Published" if config.results_published else "Hidden"
    messages.success(request, f"Results status updated: {status}")
    return redirect('dashboard')


@role_required(['principal'])
def copy_show_config_view(request):
    config = get_site_config()
    config.copy_show_flag = not config.copy_show_flag
    config.save()
    status = "Enabled" if config.copy_show_flag else "Disabled"
    messages.success(request, f"Copy Show Config status updated: {status}")
    return redirect('dashboard')


# DIGITAL REPORT CARD ENGINE (2-page print & download layout)
@login_required
def report_card_view(request, student_id):
    student = get_object_or_404(StudentProfile, id=student_id)
    config = get_site_config()
    
    is_authorized = False
    if request.user.is_superuser:
        is_authorized = True
    elif hasattr(request.user, 'profile'):
        role = request.user.profile.role
        if role in ['principal', 'vp']:
            is_authorized = True
        elif role == 'teacher':
            if student.class_teacher == request.user or student.class_name == request.user.profile.is_class_teacher_of:
                is_authorized = True
    elif hasattr(request.user, 'student_profile') and request.user.student_profile == student:
        if config.results_published:
            is_authorized = True
            
    if not is_authorized:
        return HttpResponseForbidden("You are not authorized to view this report card, or the results have not been published yet.")
        
    marks = Marks.objects.filter(student=student).order_by('subject')
    
    subjects = [c[0] for c in Marks.SUBJECT_CHOICES]
    if marks.count() < 10:
        for sub in subjects:
            Marks.objects.get_or_create(student=student, subject=sub, defaults={'status':'approved'})
        marks = Marks.objects.filter(student=student).order_by('subject')
        
    total_obtained = sum(m.grand_total() for m in marks)
    total_max = len(marks) * 100.0
    overall_percentage = (total_obtained / total_max * 100) if total_max > 0 else 0.0
    
    gps = [m.grade_point for m in marks]
    cgpa = sum(gps) / len(gps) if gps else 0.0
    
    rank = get_class_rank(student)
    
    total_working = config.school_working_days
    attended = Attendance.objects.filter(student=student, status='present').count()
    
    context = {
        'config': config,
        'student': student,
        'marks': marks,
        'total_obtained': total_obtained,
        'total_max': total_max,
        'overall_percentage': round(overall_percentage, 2),
        'cgpa': round(cgpa, 2),
        'rank': rank,
        'attended': attended,
    }
    return render(request, 'portal/report_card.html', context)


# ATTENDANCE VIEW
@role_required(['teacher'])
def mark_attendance_view(request):
    profile = request.user.profile
    if not profile.is_class_teacher_of:
        return HttpResponseForbidden("Only Class Teachers can mark attendance.")
        
    if request.method == 'POST':
        class_name = profile.is_class_teacher_of
        students = StudentProfile.objects.filter(class_name=class_name, status='active')
        date_today = timezone.localdate()
        
        for student in students:
            status = request.POST.get(f"attendance_{student.id}")
            if status:
                Attendance.objects.update_or_create(
                    student=student,
                    date=date_today,
                    defaults={'status': status, 'marked_by': request.user}
                )
        messages.success(request, f"Daily attendance marked successfully for {class_name}.")
    return redirect('dashboard')

@role_required(['teacher'])
def submit_student_to_vp_view(request, student_id):
    student = get_object_or_404(StudentProfile, id=student_id)
    if student.class_teacher != request.user:
        return HttpResponseForbidden("You are not the designated Class Teacher for this student.")
    if student.status == 'draft':
        student.status = 'vp_pending'
        student.save()
        messages.success(request, f"Student profile of {student.user.get_full_name()} submitted to VP for vetting.")
    else:
        messages.error(request, "Student is not in Draft status.")
    return redirect('dashboard')

@role_required(['principal'])
def manage_content_view(request):
    config = get_site_config()
    active_tab = request.GET.get('tab', 'logo')
    
    context = {
        'config': config,
        'active_tab': active_tab,
        'carousel_slides': CarouselImage.objects.all().order_by('order'),
        'notices': Notice.objects.all(),
        'students': StudentProfile.objects.all().order_by('class_name', 'roll_no'),
        'employees': Profile.objects.exclude(role='principal').order_by('role', 'user__username'),
        'classes': ['Class I', 'Class II', 'Class III', 'Class IV', 'Class V', 'Class VI', 'Class VII', 'Class VIII', 'Class IX', 'Class X'],
        'subjects': [c[0] for c in Marks.SUBJECT_CHOICES],
        'gallery_events': GalleryEvent.objects.all().order_by('-date'),
    }
    return render(request, 'portal/dashboards/manage_content.html', context)

@role_required(['principal'])
def edit_student_view(request, student_id):
    student = get_object_or_404(StudentProfile, id=student_id)
    if request.method == 'POST':
        student.roll_no = request.POST.get('roll_no')
        student.admission_no = request.POST.get('admission_no')
        student.dob = request.POST.get('dob') or None
        student.father_name = request.POST.get('father_name')
        student.mother_name = request.POST.get('mother_name')
        student.address = request.POST.get('address')
        student.mobile_no = request.POST.get('mobile_no')
        student.class_name = request.POST.get('class_name')
        student.status = request.POST.get('status')
        
        student.user.first_name = request.POST.get('first_name')
        student.user.last_name = request.POST.get('last_name')
        student.user.email = request.POST.get('email')
        
        student.user.save()
        student.save()
        messages.success(request, f"Updated student profile details for {student.user.get_full_name()}.")
        return redirect('/cms/manage-content/?tab=students')
        
    classes = ['Class I', 'Class II', 'Class III', 'Class IV', 'Class V', 'Class VI', 'Class VII', 'Class VIII', 'Class IX', 'Class X']
    return render(request, 'portal/dashboards/edit_student.html', {
        'student': student,
        'classes': classes
    })

@role_required(['principal'])
def edit_employee_view(request, employee_id):
    profile = get_object_or_404(Profile, id=employee_id)
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone_no = request.POST.get('phone_no')
        role = request.POST.get('role')
        assigned_subjects = request.POST.getlist('assigned_subjects')
        is_class_teacher_of = request.POST.get('is_class_teacher_of', '')
        
        assigned_subjects_str = ", ".join(assigned_subjects)
        
        if role == 'class_teacher':
            role = 'teacher'
            if not is_class_teacher_of:
                messages.error(request, "Please specify which class this Class Teacher is assigned to.")
                return redirect(f'/cms/edit-employee/{employee_id}/')
        else:
            is_class_teacher_of = None
            
        if is_class_teacher_of:
            duplicate = Profile.objects.filter(is_class_teacher_of=is_class_teacher_of).exclude(id=profile.id).exists()
            if duplicate:
                messages.error(request, f"{is_class_teacher_of} Class Teacher already assigned.")
                return redirect(f'/cms/edit-employee/{employee_id}/')
                
        profile.user.first_name = first_name
        profile.user.last_name = last_name
        profile.user.email = email
        profile.user.save()
        
        profile.role = role
        profile.phone_no = phone_no
        profile.assigned_subjects = assigned_subjects_str
        profile.is_class_teacher_of = is_class_teacher_of
        profile.save()
        
        messages.success(request, f"Updated profile details for employee {profile.user.get_full_name()}.")
        return redirect('/cms/manage-content/?tab=employees')
        
    classes = ['Class I', 'Class II', 'Class III', 'Class IV', 'Class V', 'Class VI', 'Class VII', 'Class VIII', 'Class IX', 'Class X']
    subjects = [c[0] for c in Marks.SUBJECT_CHOICES]
    current_subjects = profile.get_assigned_subjects()
    
    return render(request, 'portal/dashboards/edit_employee.html', {
        'employee': profile,
        'classes': classes,
        'subjects': subjects,
        'current_subjects': current_subjects
    })

@role_required(['principal'])
def cms_add_gallery_event_view(request):
    if request.method == 'POST' and request.FILES.get('image'):
        title = request.POST.get('title')
        description = request.POST.get('description')
        date = request.POST.get('date')
        image = request.FILES.get('image')
        
        GalleryEvent.objects.create(
            title=title,
            description=description,
            date=date or timezone.localdate(),
            image=image
        )
        messages.success(request, "Gallery Event uploaded successfully.")
    return redirect('/cms/manage-content/?tab=gallery')

@role_required(['principal'])
def cms_delete_gallery_event_view(request, event_id):
    event = get_object_or_404(GalleryEvent, id=event_id)
    event.delete()
    messages.success(request, "Gallery Event deleted successfully.")
    return redirect('/cms/manage-content/?tab=gallery')

@role_required(['principal'])
def update_active_exam_stage_view(request):
    if request.method == 'POST':
        stage = request.POST.get('active_exam_stage')
        if stage in ['PT-01', 'SA-01', 'PT-02', 'SA-02']:
            config = get_site_config()
            config.active_exam_stage = stage
            config.save()
            messages.success(request, f"Active exam stage updated to {config.get_active_exam_stage_display()}.")
    return redirect('dashboard')

@role_required(['principal'])
def update_active_copy_show_exam_view(request):
    if request.method == 'POST':
        exam = request.POST.get('active_copy_show_exam')
        config = get_site_config()
        config.active_copy_show_exam = exam
        config.save()
        messages.success(request, f"Active Copy Show Exam set to {exam}.")
    return redirect('dashboard')

@role_required(['principal'])
def approve_class_results_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        class_name = request.POST.get('class_name')
        student_ids = request.POST.getlist('student_ids')
        
        if action == 'approve_all' and class_name:
            students = StudentProfile.objects.filter(class_name=class_name)
            for student in students:
                Marks.objects.filter(student=student).update(status='approved')
            messages.success(request, f"Successfully approved all student marks and generated results for {class_name}.")
            
        elif action == 'approve_selected' and student_ids:
            for s_id in student_ids:
                try:
                    student = StudentProfile.objects.get(id=s_id)
                    Marks.objects.filter(student=student).update(status='approved')
                except StudentProfile.DoesNotExist:
                    pass
            messages.success(request, "Successfully approved selected student marks and generated results.")
            
    return redirect('/dashboard/')


@role_required(['principal'])
def login_status_list_view(request):
    # Ensure every user has a UserLoginStatus
    existing_users_without_status = User.objects.filter(login_status__isnull=True)
    if existing_users_without_status.exists():
        for u in existing_users_without_status:
            UserLoginStatus.objects.get_or_create(user=u)

    statuses_list = UserLoginStatus.objects.all().select_related(
        'user', 'user__profile', 'user__student_profile'
    ).order_by('-is_logged_in', '-last_login_time')
    
    paginator = Paginator(statuses_list, 30)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'portal/login_status_list.html', {
        'page_obj': page_obj
    })


@role_required(['principal'])
def save_calendar_event_view(request):
    if request.method == 'POST':
        dates_raw = request.POST.get('dates', '')
        date_single = request.POST.get('date', '')
        title = request.POST.get('title', 'Holiday')
        description = request.POST.get('description', '')
        status = request.POST.get('status', 'holiday')
        
        dates_to_process = []
        if dates_raw:
            dates_to_process = [d.strip() for d in dates_raw.split(',') if d.strip()]
        elif date_single:
            dates_to_process = [date_single]
            
        if not dates_to_process:
            messages.error(request, "No dates selected.")
            return redirect(request.META.get('HTTP_REFERER', 'dashboard'))
            
        import datetime
        success_count = 0
        for date_str in dates_to_process:
            try:
                date_val = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                SchoolCalendar.objects.update_or_create(
                    date=date_val,
                    defaults={
                        'title': title,
                        'description': description,
                        'status': status
                    }
                )
                success_count += 1
            except ValueError:
                pass
                
        if success_count > 1:
            messages.success(request, f"Successfully saved calendar entry for {success_count} dates.")
        else:
            messages.success(request, "Calendar entry saved successfully.")
            
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


@role_required(['principal'])
def delete_calendar_event_view(request, event_id):
    event = get_object_or_404(SchoolCalendar, id=event_id)
    date_str = event.date.strftime("%Y-%m-%d")
    event.delete()
    messages.success(request, f"Deleted custom calendar entry for {date_str}.")
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))
