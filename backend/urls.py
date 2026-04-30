from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.admin_login, name='admin_login'),
    path('logout/', views.admin_logout, name='admin_logout'),
    path('forgot-password/', views.admin_forgot_password, name='admin_forgot_password'),
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('reset-password/<str:token>/', views.admin_reset_password, name='admin_reset_password'),
    # Dashboard sections

    # Other URLs
    path('', views.dashboard, name='dashboard'),


    path('companies/', views.companies_view, name='companies'),
    path('companies/add/', views.add_company, name='add_company'),
    path('companies/edit/<int:company_id>/', views.edit_company, name='edit_company'),
    path('companies/delete/<int:company_id>/', views.delete_company, name='delete_company'),
    path('companies/approve/<int:company_id>/', views.approve_company, name='approve_company'),
    path('companies/get-details/', views.get_company_details, name='get_company_details'),
    path('companies/filter/', views.filter_companies, name='filter_companies'),

    path('drivers/', views.drivers_view, name='drivers'),
    path('drivers/add/', views.add_driver, name='add_driver'),
    path('drivers/edit/<int:driver_id>/', views.edit_driver, name='edit_driver'),
    path('drivers/delete/<int:driver_id>/', views.delete_driver, name='delete_driver'),
    path('drivers/get-details/', views.get_driver_details, name='get_driver_details'),
    path('drivers/filter/', views.filter_drivers, name='filter_drivers'),

    path('drivers/approve/<int:driver_id>/', views.approve_driver, name='approve_driver'),
    path('drivers/reject/<int:driver_id>/', views.reject_driver, name='reject_driver'),
    path('vehicles/', views.vehicles_view, name='vehicles'),
    path('vehicles/add/', views.add_vehicle, name='add_vehicle'),
    path('vehicles/edit/<int:vehicle_id>/', views.edit_vehicle, name='edit_vehicle'),
    path('vehicles/delete/<int:vehicle_id>/', views.delete_vehicle, name='delete_vehicle'),
    path('vehicles/get-details/', views.get_vehicle_details, name='get_vehicle_details'),
    path('vehicles/filter/', views.filter_vehicles, name='filter_vehicles'),

    # Vehicle URLs with approval
    path('vehicles/approve/<int:vehicle_id>/', views.approve_vehicle, name='approve_vehicle'),
    path('vehicles/reject/<int:vehicle_id>/', views.reject_vehicle, name='reject_vehicle'),


    path('services/', views.admin_services_view, name='admin_services'),
    path('services/add/', views.add_service, name='add_service'),
    path('services/edit/<int:service_id>/', views.edit_service, name='edit_service'),
    path('services/delete/<int:service_id>/', views.delete_service, name='delete_service'),
    path('services/get-details/', views.get_service_details, name='get_service_details'),

    path('pricing/', views.admin_pricing_view, name='admin_pricing'),
    path('pricing/add/', views.add_pricing_plan, name='add_pricing_plan'),
    path('pricing/edit/<int:plan_id>/', views.edit_pricing_plan, name='edit_pricing_plan'),
    path('pricing/delete/<int:plan_id>/', views.delete_pricing_plan, name='delete_pricing_plan'),
    path('pricing/get-details/', views.get_pricing_plan_details, name='get_pricing_plan_details'),


    path('why-us/', views.admin_why_us_view, name='admin_why_us'),
    path('why-us/update/', views.update_why_us, name='update_why_us'),
    path('why-us/feature/add/', views.add_feature, name='add_feature'),
    path('why-us/feature/edit/<int:feature_id>/', views.edit_feature, name='edit_feature'),
    path('why-us/feature/delete/<int:feature_id>/', views.delete_feature, name='delete_feature'),
    path('why-us/feature/get-details/', views.get_feature_details, name='get_feature_details'),



    path('contact-messages/', views.admin_contact_messages, name='admin_contact_messages'),
    path('contact-messages/update/<int:message_id>/', views.update_message_status, name='update_message_status'),
    path('contact-messages/view/<int:message_id>/', views.get_message_detail, name='get_message_detail'),
    path('contact-messages/delete/<int:message_id>/', views.delete_message, name='delete_message'),

    # Footer Settings URLs
    path('footer-settings/', views.admin_footer_settings, name='admin_footer_settings'),
    path('footer-settings/update/', views.update_footer_settings, name='update_footer_settings'),



    path('settings/', views.admin_settings, name='admin_settings'),
    path('settings/update-profile/', views.update_admin_profile, name='update_admin_profile'),
    path('settings/update-system/', views.update_system_settings, name='update_system_settings'),
    path('settings/update-password/', views.update_password, name='update_password'),
    path('settings/upload-carousel-image/', views.upload_carousel_image, name='upload_carousel_image'),
    path('settings/remove-carousel-image/', views.remove_carousel_image, name='remove_carousel_image'),
    path('analytics/', views.analytics_view, name='analytics'),

    path('subscriptions/history/', views.subscription_history_view, name='subscription_history'),
    path('subscriptions/history/export/', views.export_subscription_history, name='export_subscription_history'),
    path('subscriptions/history/api/<int:subscription_id>/', views.get_subscription_history_api, name='get_subscription_history_api'),

    # Incident URLs
    path('incidents/', views.incidents_view, name='incidents'),
    path('incidents/add/', views.add_incident, name='add_incident'),
    path('incidents/edit/<int:incident_id>/', views.edit_incident, name='edit_incident'),
    path('incidents/delete/<int:incident_id>/', views.delete_incident, name='delete_incident'),
    path('incidents/get-details/', views.get_incident_details, name='get_incident_details'),
    path('incidents/filter/', views.filter_incidents, name='filter_incidents'),

    path('approve-plan-change/<int:subscription_id>/', views.approve_plan_change, name='approve_plan_change'),
    path('reject-plan-change/<int:subscription_id>/', views.reject_plan_change, name='reject_plan_change'),
    path('get-pending-requests/', views.get_pending_requests_api, name='get_pending_requests'),
# Review URLs
   path('adjust-expiry/<int:subscription_id>/', views.adjust_expiry_date, name='adjust_expiry'),
    path('update-expiry/<int:subscription_id>/', views.update_expiry_date, name='update_expiry'),
    path('bulk-extend-expiry/', views.bulk_extend_expiry, name='bulk_extend_expiry'),
    path('reviews/', views.admin_reviews_view, name='admin_reviews'),
    path('reviews/approve/<int:review_id>/', views.approve_review, name='approve_review'),
    path('reviews/unapprove/<int:review_id>/', views.unapprove_review, name='unapprove_review'),
    path('reviews/feature/<int:review_id>/', views.feature_review, name='feature_review'),
    path('reviews/unfeature/<int:review_id>/', views.unfeature_review, name='unfeature_review'),
    path('reviews/delete/<int:review_id>/', views.delete_review_admin, name='delete_review_admin'),
    path('reviews/get-details/', views.get_review_details, name='get_review_details'),
    path('reviews/update/<int:review_id>/', views.update_review, name='update_review'),
    path('reviews/bulk-approve/', views.bulk_approve_reviews, name='bulk_approve_reviews'),
    path('reviews/bulk-delete/', views.bulk_delete_reviews, name='bulk_delete_reviews'),
    
    # Documents
    path("documents/", views.company_documents_admin, name="company_documents_admin"),
    path("documents/rename/<int:doc_id>/", views.rename_document, name="rename_document"),
    path("documents/delete/<int:doc_id>/", views.delete_document, name="delete_document"),
    
    path('companies/change-password/', views.admin_change_company_password, name='admin_change_company_password'),
    # Payments
    path('payment-history/', views.payment_history_view, name='payment_history'),
    path('get-payment-details/<int:payment_id>/', views.get_payment_details, name='get_payment_details'),
]