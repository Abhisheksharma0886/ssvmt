from django.urls import path
from . import views

urlpatterns = [
    # Public home page
    path('', views.home_view, name='home'),
    
    # Dashboards and auth
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Superuser bootstrap Principal
    path('bootstrap-principal/', views.bootstrap_principal_view, name='bootstrap_principal'),
    path('bootstrap-principal/toggle/', views.toggle_principal_status_view, name='toggle_principal_status'),
    
    # Onboarding sequential approval & overrides
    path('onboard-student/', views.onboard_student_view, name='onboard_student'),
    path('approve-student/<int:student_id>/', views.approve_student_view, name='approve_student'),
    path('reject-student/<int:student_id>/', views.reject_student_view, name='reject_student'),
    
    # Timetable management & copy tool
    path('timetable/', views.timetable_view, name='timetable'),
    path('timetable/copy/', views.copy_timetable_view, name='copy_timetable'),
    
    # Profile edit request system
    path('edit-profile-request/', views.edit_profile_request_view, name='edit_profile_request'),
    path('approve-edit-request/<int:request_id>/', views.approve_edit_request_view, name='approve_edit_request'),
    path('reject-edit-request/<int:request_id>/', views.reject_edit_request_view, name='reject_edit_request'),
    
    # Leave application & slips
    path('leave/apply/', views.apply_leave_view, name='apply_leave'),
    path('leave/approve/<int:leave_id>/', views.approve_leave_view, name='approve_leave'),
    path('leave/reject/<int:leave_id>/', views.reject_leave_view, name='reject_leave'),
    path('leave/slip/<int:leave_id>/', views.print_leave_slip_view, name='print_leave_slip'),
    
    # Attendance marking
    path('attendance/mark/', views.mark_attendance_view, name='mark_attendance'),
    
    # Chat engine
    path('chat/', views.chat_inbox_view, name='chat_inbox'),
    path('chat/<int:user_id>/', views.chat_detail_view, name='chat_detail'),
    
    # Marks entry & pipelines
    path('marks/', views.marks_entry_view, name='marks_entry'),
    path('marks/submit/<int:marks_id>/', views.submit_marks_view, name='submit_marks'),
    path('marks/verify/<int:marks_id>/', views.verify_marks_view, name='verify_marks'),
    path('marks/vet/<int:marks_id>/', views.vet_marks_view, name='vet_marks'),
    path('marks/approve/<int:marks_id>/', views.approve_marks_view, name='approve_marks'),
    path('marks/publish/', views.publish_results_view, name='publish_results'),
    path('marks/copy-show-config/', views.copy_show_config_view, name='copy_show_config'),
    path('marks/upload-sheet/<int:marks_id>/', views.upload_scanned_sheet_view, name='upload_scanned_sheet'),
    
    # Report card view
    path('report-card/<int:student_id>/', views.report_card_view, name='report_card'),
    
    # Onboard employee (Principal Action)
    path('onboard-employee/', views.onboard_employee_view, name='onboard_employee'),
    path('cms/login-status/', views.login_status_list_view, name='login_status_list'),
    
    # Principal CMS Panel Actions
    path('cms/update-settings/', views.cms_update_settings_view, name='cms_update_settings'),
    path('cms/upload-carousel/', views.cms_upload_carousel_view, name='cms_upload_carousel'),
    path('cms/add-notice/', views.cms_add_notice_view, name='cms_add_notice'),
    path('cms/delete-notice/<int:notice_id>/', views.cms_delete_notice_view, name='cms_delete_notice'),
    path('cms/delete-logo/', views.cms_delete_logo_view, name='cms_delete_logo'),
    path('cms/delete-principal-photo/', views.cms_delete_principal_photo_view, name='cms_delete_principal_photo'),
    path('cms/delete-carousel/<int:slide_id>/', views.cms_delete_carousel_view, name='cms_delete_carousel'),
    
    # Principal CMS Management Sub-options & student onboarding
    path('submit-student-to-vp/<int:student_id>/', views.submit_student_to_vp_view, name='submit_student_to_vp'),
    path('cms/manage-content/', views.manage_content_view, name='manage_content'),
    path('cms/edit-student/<int:student_id>/', views.edit_student_view, name='edit_student'),
    path('cms/edit-employee/<int:employee_id>/', views.edit_employee_view, name='edit_employee'),
    
    # Principal Gallery management actions
    path('cms/add-gallery/', views.cms_add_gallery_event_view, name='cms_add_gallery'),
    path('cms/delete-gallery/<int:event_id>/', views.cms_delete_gallery_event_view, name='cms_delete_gallery'),
    
    # Active Exam Stage & Copy Show Selector updates
    path('marks/update-stage/', views.update_active_exam_stage_view, name='update_active_exam_stage'),
    path('marks/update-copy-show-exam/', views.update_active_copy_show_exam_view, name='update_active_copy_show_exam'),
    path('marks/approve-class/', views.approve_class_results_view, name='approve_class_results'),
]
