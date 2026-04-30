from django.urls import path
from . import views

urlpatterns = [
    path('', views.index),
    path('signin/', views.signin , name='signin'),
    path('signup/', views.signup , name='signup'),
    path('index/', views.index, name='index'),
    path('profile/', views.profile, name='profile'),
    path('submit-contact/', views.submit_contact, name='submit_contact'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/update/', views.update_profile, name='update_profile'),

    
    # SMS Manual form
    path('sms-builder-form/', views.sms_builder_form, name='sms_builder_form'),
    path('api/save-company-profile/', views.save_company_profile, name='save_company_profile'),
    path('sms-manual/', views.sms_manual, name='sms_manual'),
    
    # Reviews
    path('add-review/', views.add_review, name='add_review'),
    path('delete-review/<int:review_id>/', views.delete_review, name='delete_review'),

    # Vehicle URLs
    path('vehicles/add/', views.add_vehicle_ajax, name='add_vehicle_ajax'),
    path('vehicles/edit/<int:vehicle_id>/', views.edit_vehicle_ajax, name='edit_vehicle_ajax'),
    path('vehicles/delete/<int:vehicle_id>/', views.delete_vehicle_ajax, name='delete_vehicle_ajax'),
    path('vehicles/get/<int:vehicle_id>/', views.get_vehicle_details_ajax, name='get_vehicle_details_ajax'),
    
    path('plan/<str:plan_name>/', views.select_plan, name='select_plan'),
    path('activate-plan/<int:subscription_id>/', views.activate_plan, name='activate_plan'),
    path('cancel-pending/<int:subscription_id>/', views.cancel_pending_plan, name='cancel_pending_plan'),


    path('plan/<str:plan_name>/', views.select_plan, name='select_plan'),
    path('request-plan-change/', views.request_plan_change, name='request_plan_change'),
    path('cancel-plan-change/', views.cancel_plan_change, name='cancel_plan_change'),
    path('cancel-subscription/', views.cancel_subscription, name='cancel_subscription'),
    
    # Driver URLs
    path('drivers/add/', views.add_driver_ajax, name='add_driver_ajax'),
    path('drivers/edit/<int:driver_id>/', views.edit_driver_ajax, name='edit_driver_ajax'),
    path('drivers/delete/<int:driver_id>/', views.delete_driver_ajax, name='delete_driver_ajax'),
    path('drivers/get/<int:driver_id>/', views.get_driver_details_ajax, name='get_driver_details_ajax'),

    path('generate-documents/', views.generate_company_documents, name='generate_company_documents'),
    
    path('change-password/', views.change_password_ajax, name='change_password_ajax'),
    
   path('checkout-success/', views.handle_checkout_success, name='checkout_success'),  # ← ADD THIS
    path('create-portal-session/', views.create_portal_session, name='create_portal_session'),
]