from django.http import HttpRequest, HttpResponse, FileResponse, Http404
from docx import Document
import shutil
from django.conf import settings
import tempfile
from django.core.files.storage import default_storage
from django.core.files import File
import time
import os
import subprocess
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.utils.crypto import get_random_string
from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
from django.http import JsonResponse
from django.db import transaction
from django.urls import reverse
from django.core.exceptions import ObjectDoesNotExist
import re
import json
from .models import User, Company,Service,PricingPlan,WhyUs,ContactMessage
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import User, Company, Driver, Vehicle,SystemSettings,FooterSettings,ContactMessage
from datetime import datetime
import json
import re
# Create your views here.
import json
from django.shortcuts import render
from .models import Service, PricingPlan, WhyUs, SystemSettings, FooterSettings
from django.db.models import Q, Sum, Count, Avg
import json
import re
from django.shortcuts import render
from .models import *
from .utils import (
    format_step1_data,
    format_step2_data,
    format_step3_data,
    format_step4_static_data,
    format_step4_dynamic_data,
    format_step5_static_data,
    format_step5_dynamic_data,
    format_step6_static_data,
    format_step6_dynamic_data,
    generate_company_document_for_company
)






User = get_user_model()



# =========================
# HERO VIDEO (FULL URL)
# =========================
def get_hero_video_embed(url):
    if not url:
        return "https://www.youtube-nocookie.com/embed/Cm6eMeOg-KU"

    match = re.search(r'(?:v=|youtu\.be/|embed/)([^?&]+)', url)
    if match:
        return f"https://www.youtube-nocookie.com/embed/{match.group(1)}"

    return "https://www.youtube-nocookie.com/embed/Cm6eMeOg-KU"


# =========================
# WHY US VIDEO (ONLY ID)
# =========================
def get_whyus_video_embed(video_id):
    if not video_id:
        video_id = "Cm6eMeOg-KU"

    return f"https://www.youtube-nocookie.com/embed/{video_id}"


# =========================
# INDEX VIEW
# =========================
def index(request):
    # -----------------
    # SERVICES
    # -----------------
    services = Service.objects.filter(is_active=True).order_by('order')
    pricing_plans = PricingPlan.objects.filter(is_active=True).order_by('order', 'price')

    # -----------------
    # WHY US
    # -----------------
    why_us = WhyUs.objects.filter(is_active=True).first()
    features = why_us.features.filter(is_active=True).order_by('order') if why_us else []

    # -----------------
    # REVIEWS - Fetch only approved reviews
    # -----------------
    approved_reviews = Review.objects.filter(
        is_approved=True
    ).select_related('company', 'user').order_by('-created_at')[:6]

    # -----------------
    # SYSTEM SETTINGS
    # -----------------
    system_settings = SystemSettings.objects.first()
    if not system_settings:
        system_settings = SystemSettings.objects.create()

    # -----------------
    # HERO VIDEO
    # -----------------
    hero_video_url = get_hero_video_embed(system_settings.hero_video_url)

    # -----------------
    # WHY US VIDEO (ONLY ID)
    # -----------------
    why_us_video_url = get_whyus_video_embed(
        why_us.video_url if why_us and why_us.video_url else None
    )

    # -----------------
    # CAROUSEL FIX
    # -----------------
    carousel_images = []

    if system_settings.carousel_images:
        data = system_settings.carousel_images

        if isinstance(data, list):
            carousel_images = data
        else:
            try:
                carousel_images = json.loads(data)
            except:
                carousel_images = [i.strip() for i in str(data).split(',') if i.strip()]

    # -----------------
    # FOOTER
    # -----------------
    footer_settings = FooterSettings.objects.first()
    if not footer_settings:
        footer_settings = FooterSettings.objects.create()

    # -----------------
    # USER SUBSCRIPTION (if logged in)
    # -----------------
    current_subscription = None
    if request.user.is_authenticated and hasattr(request.user, 'company_profile'):
        try:
            current_subscription = CompanySubscription.objects.filter(
                company=request.user.company_profile,
                status__in=['active', 'pending', 'trial']
            ).first()
        except:
            pass

    # -----------------
    # DEBUG (OPTIONAL)
    # -----------------
    print("=" * 50)
    print("Hero Video:", hero_video_url)
    print("Why Us Video:", why_us_video_url)
    print("Carousel:", carousel_images)
    print("Approved Reviews:", approved_reviews.count())
    print("=" * 50)

    # -----------------
    # CONTEXT
    # -----------------
    context = {
        'services': services,
        'pricing_plans': pricing_plans,
        'why_us': why_us,
        'features': features,
        'system_settings': system_settings,

        # videos
        'video_url': hero_video_url,
        'why_us_video_url': why_us_video_url,

        # carousel
        'carousel_images': carousel_images,

        # footer
        'footer_settings': footer_settings,
        
        # reviews
        'reviews': approved_reviews,
        
        # subscription
        'current_subscription': current_subscription,
    }

    return render(request, 'sms_builder/index.html', context)


@login_required
@login_required
def select_plan(request, plan_name):
    """Select and save a plan as pending for the logged-in company"""
    
    # Check if user has a company profile
    if not hasattr(request.user, 'company_profile'):
        messages.error(request, 'Please complete your company registration first.')
        return redirect('company_registration')
    
    company = request.user.company_profile
    
    # Get the selected plan
    try:
        plan = PricingPlan.objects.get(name=plan_name, is_active=True)
    except PricingPlan.DoesNotExist:
        messages.error(request, 'Selected plan not found.')
        return redirect('index')
    
    # Check if company already has an active subscription
    existing_subscription = CompanySubscription.objects.filter(
        company=company,
        status='active'
    ).first()
    
    if existing_subscription:
        messages.warning(request, f'You already have an active {existing_subscription.plan.display_name} plan.')
        return redirect('dashboard')
    
    # Try to get existing subscription (including pending, cancelled, etc.)
    subscription = CompanySubscription.objects.filter(company=company).first()
    
    if subscription:
        # Update existing subscription instead of creating new one
        old_plan = subscription.plan
        old_status = subscription.status
        
        subscription.plan = plan
        subscription.status = 'pending'
        subscription.amount_paid = plan.price
        subscription.auto_renew = False
        subscription.updated_at = timezone.now()
        subscription.save()
        
        # Create history record
        SubscriptionHistory.objects.create(
            subscription=subscription,
            old_plan=old_plan,
            new_plan=plan,
            action='upgraded' if old_plan and plan.price > old_plan.price else 'downgraded',
            notes=f'Plan changed from {old_plan.display_name if old_plan else "None"} to {plan.display_name}. Previous status: {old_status}',
            changed_by=request.user
        )
        
        messages.success(request, f'Plan updated to {plan.display_name} and saved as pending.')
    else:
        # Create new subscription (this won't happen if OneToOne exists, but just in case)
        subscription = CompanySubscription.objects.create(
            company=company,
            plan=plan,
            amount_paid=plan.price,
            status='pending',
            auto_renew=False,
            created_by=request.user
        )
        
        # Create history record
        SubscriptionHistory.objects.create(
            subscription=subscription,
            new_plan=plan,
            action='created',
            notes=f'Pending subscription created for {plan.display_name} plan',
            changed_by=request.user
        )
        
        messages.success(request, f'You have selected the {plan.display_name} plan. It has been saved as pending.')
    
    # Update company's subscription fields
    company.subscription_plan = plan.name
    company.subscription_status = 'pending'
    company.save()
    
    return redirect('profile')


@login_required
def activate_plan(request, subscription_id):
    """Manually activate a pending plan (admin or company owner)"""
    
    try:
        subscription = CompanySubscription.objects.get(
            id=subscription_id,
            company=request.user.company_profile,
            status='pending'
        )
    except CompanySubscription.DoesNotExist:
        messages.error(request, 'Pending subscription not found.')
        return redirect('dashboard')
    
    # Activate the subscription
    subscription.status = 'active'
    subscription.start_date = timezone.now()
    
    # Set end date based on plan period
    if subscription.plan.price_period == 'month':
        subscription.end_date = timezone.now() + timezone.timedelta(days=30)
    elif subscription.plan.price_period == 'year':
        subscription.end_date = timezone.now() + timezone.timedelta(days=365)
    else:
        subscription.end_date = None
    
    subscription.last_renewal_date = timezone.now()
    subscription.next_renewal_date = subscription.end_date
    subscription.save()
    
    # Update company
    company = subscription.company
    company.subscription_status = 'active'
    company.subscription_end_date = subscription.end_date
    company.save()
    
    # Create history record
    SubscriptionHistory.objects.create(
        subscription=subscription,
        new_plan=subscription.plan,
        action='created',
        notes='Subscription activated manually',
        changed_by=request.user
    )
    
    messages.success(request, f'Your {subscription.plan.display_name} plan has been activated!')
    
    return redirect('profile')


@login_required
def cancel_pending_plan(request, subscription_id):
    """Cancel a pending plan"""
    
    try:
        subscription = CompanySubscription.objects.get(
            id=subscription_id,
            company=request.user.company_profile,
            status='pending'
        )
    except CompanySubscription.DoesNotExist:
        messages.error(request, 'Pending subscription not found.')
        return redirect('dashboard')
    
    # Delete the pending subscription
    plan_name = subscription.plan.display_name
    subscription.delete()
    
    # Update company
    company = request.user.company_profile
    company.subscription_plan = None
    company.subscription_status = 'pending'
    company.save()
    
    messages.success(request, f'Your pending {plan_name} plan has been cancelled.')
    
    return redirect('index')

def signup(request):
    if request.method == 'POST':
        # Get form data
        company_name = request.POST.get('company_name', '').strip()
        abn = request.POST.get('abn', '').strip()
        address = request.POST.get('address', '').strip()
        full_name = request.POST.get('full_name', '').strip()
        role = request.POST.get('role', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        terms_check = request.POST.get('termsCheck')  # Check if terms accepted

        # ========== NULL/VALIDATION CHECKS ==========
        if not company_name:
            messages.error(request, "Company name is required!")
            return redirect('signup')
        
        if not abn:
            messages.error(request, "ABN is required!")
            return redirect('signup')
        
        if not full_name:
            messages.error(request, "Full name is required!")
            return redirect('signup')
        
        if not email:
            messages.error(request, "Email address is required!")
            return redirect('signup')
        
        if not password:
            messages.error(request, "Password is required!")
            return redirect('signup')
        
        # ========== TERMS AND CONDITIONS VALIDATION ==========
        if not terms_check:
            messages.error(request, "You must agree to the Terms of Service and Privacy Policy!")
            return redirect('signup')

        # ========== ABN VALIDATION ==========
        # Remove spaces from ABN
        clean_abn = re.sub(r'\s+', '', abn)
        if not clean_abn.isdigit():
            messages.error(request, "ABN must contain only numbers!")
            return redirect('signup')
        
        if len(clean_abn) != 11:
            messages.error(request, "ABN must be exactly 11 digits!")
            return redirect('signup')

        # ========== EMAIL VALIDATION ==========
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Please enter a valid email address!")
            return redirect('signup')

        # ========== PASSWORD VALIDATION ==========
        if password != confirm_password:
            messages.error(request, "Passwords do not match!")
            return redirect('signup')
        
        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters!")
            return redirect('signup')
        
        # Optional: Check password strength (warning only, not error)
        if password.lower() == password or password.upper() == password:
            messages.warning(request, "For better security, use a mix of uppercase, lowercase, numbers, and special characters!")

        # ========== CHECK IF EMAIL EXISTS ==========
        if User.objects.filter(email=email).exists():
            messages.error(request, "An account with this email already exists!")
            return redirect('signup')

        # ========== CHECK IF ABN EXISTS ==========
        if Company.objects.filter(abn=clean_abn).exists():
            messages.error(request, "A company with this ABN is already registered!")
            return redirect('signup')

        # ========== CREATE USER ==========
        try:
            # Split full_name into first_name and last_name
            name_parts = full_name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            # Create user using custom User model
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                full_name=full_name,
                phone=phone,
                role=role,
                user_type='company',
                is_active=True,
                is_verified=False,  # Set to False until admin approval
                terms_accepted=True,
                terms_accepted_at=timezone.now()
            )
            
            # ========== CREATE COMPANY PROFILE ==========
            company = Company.objects.create(
                user=user,
                company_name=company_name,
                abn=clean_abn,
                address=address if address else None,
                status='pending'  # Pending admin approval
            )
            
            # Success message
            messages.success(request, f"Thank you {full_name}! Your company account has been created and is pending admin approval. You will receive an email once approved.")
            
            return redirect('signin')  # Redirect to signin page
            
        except Exception as e:
            messages.error(request, f"Registration failed: {str(e)}")
            return redirect('signup')
    
    # GET request - show registration form
    return render(request, 'sms_builder/signup.html')
def signin(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        # ❌ EMPTY FIELD CHECK
        if not email or not password:
            messages.error(request, "Email and password required!")
            return redirect('signin')

        user = authenticate(request, username=email, password=password)

        # ❌ WRONG LOGIN
        if user is None:
            messages.error(request, "Invalid email or password!")
            return redirect('signin')

        # ✅ SUCCESS LOGIN
        login(request, user)
        messages.success(request, "Login successful!")
        return redirect('signin')

    return render(request, 'sms_builder/signin.html')




@login_required(login_url='signin')
@require_http_methods(["POST"])
def update_profile(request):
    """Update company profile via AJAX"""
    try:
        data = json.loads(request.body)
        
        company = get_object_or_404(Company, user=request.user)
        user = request.user
        
        # Update company fields
        company.company_name = data.get('company_name', company.company_name)
        company.address = data.get('address', company.address)
        company.save()
        
        # Update user fields
        user.full_name = data.get('contact_person', user.full_name)
        user.email = data.get('email', user.email)
        user.phone = data.get('phone', user.phone)
        user.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Profile updated successfully'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def logout_view(request):
    logout(request)
    return redirect('signin')


import logging
logger = logging.getLogger(__name__)

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
import json
import re
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
@csrf_exempt  # remove later when using proper CSRF
@require_POST
def submit_contact(request):
    try:
        # Parse JSON body safely
        try:
            data = json.loads(request.body.decode('utf-8'))
        except Exception:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)

        # Get data
        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        message = data.get('message', '').strip()
        agreed = data.get('agreed', False)

        # ✅ Validation
        if not name:
            return JsonResponse({'success': False, 'error': 'Name is required'}, status=400)

        if not email:
            return JsonResponse({'success': False, 'error': 'Email is required'}, status=400)

        email_regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if not re.match(email_regex, email):
            return JsonResponse({'success': False, 'error': 'Invalid email'}, status=400)

        if not message or len(message) < 20:
            return JsonResponse({'success': False, 'error': 'Message must be at least 20 characters'}, status=400)

        if not agreed:
            return JsonResponse({'success': False, 'error': 'Please accept privacy policy'}, status=400)

        # ✅ Get IP
        ip_address = request.META.get('HTTP_X_FORWARDED_FOR')
        if ip_address:
            ip_address = ip_address.split(',')[0]
        else:
            ip_address = request.META.get('REMOTE_ADDR')

        user_agent = request.META.get('HTTP_USER_AGENT', '')

        # ✅ SAVE TO DATABASE
        contact = ContactMessage.objects.create(
            name=name,
            email=email,
            message=message,
            ip_address=ip_address,
            user_agent=user_agent,
            is_agreed=agreed,
            status='new'
        )

        print(f"Saved successfully ID: {contact.id}")

        return JsonResponse({
            'success': True,
            'message': 'Message sent successfully!',
            'message_id': contact.id
        })

    except Exception as e:
        print("ERROR:", str(e))
        return JsonResponse({
            'success': False,
            'error': 'Server error'
        }, status=500)
    
def sms_builder_form(request):
    context = {}
    
    if request.user and request.user.is_authenticated:
        print(f"Authenticated user: {request.user}")
        
        # Try to fetch the existing company profile using the related_name
        try:
            context['company'] = request.user.company_profile
        except ObjectDoesNotExist:
            # If they don't have a company profile yet, that's perfectly fine.
            context['company'] = None

    return render(request, 'sms_builder/sms_builder_form/form.html', context)



@transaction.atomic
def save_company_profile(request):
    # REMOVED: @login_required and the initial is_authenticated check
        
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Extract Step 1 data first to check for contact details
            step1_formatted = format_step1_data(data)
            
            # --- NEW: HANDLE USER CREATION/AUTHENTICATION ---
            user = request.user
            
            if not user.is_authenticated:
                email = step1_formatted.get('contact_email')
                
                if not email:
                    return JsonResponse({
                        'status': 'error', 
                        'message': 'An email address is required to create your account.'
                    }, status=400)
                
                # Check if a user with this email already exists
                if User.objects.filter(email=email).exists():
                    return JsonResponse({
                        'status': 'error', 
                        'message': 'An account with this email already exists. Please log in first.'
                    }, status=400)
                
                # Generate a random 12-character password
                random_password = get_random_string(length=12)
                
                # Create the new user mapping frontend data to User model fields
                user = User.objects.create_user(
                    email=email,
                    password=random_password,
                    full_name=step1_formatted.get('contact_person', ''),
                    phone=step1_formatted.get('contact_phone', ''),
                    role=step1_formatted.get('contact_role', ''),
                    user_type='company',
                    is_active=True,
                    terms_accepted=step1_formatted.get('declaration_accepted', False)
                )
                
                if step1_formatted.get('declaration_accepted'):
                    user.terms_accepted_at = timezone.now()
                    user.save()
                
                # Automatically log the user in so their session is active for the redirect
                login(request, user)
                
                # Optional: You might want to email the user their `random_password` here
                # send_welcome_email(user.email, random_password)

            # --- STEP 1: COMPANY ---
            # Update user=request.user to user=user (dynamically resolved above)
            company, created = Company.objects.update_or_create(
                user=user,
                defaults=step1_formatted
            )

            # --- STEP 2: OPERATIONS ---
            step2_formatted = format_step2_data(data)
            CompanyOperation.objects.update_or_create(
                company=company,
                defaults=step2_formatted
            )

            # --- STEP 3: FLEET ---
            step3_formatted = format_step3_data(data)
            CompanyFleet.objects.update_or_create(
                company=company,
                defaults=step3_formatted
            )

            # --- STEP 4: RISK (STATIC FIELDS) ---
            step4_static = format_step4_static_data(data)
            CompanyRiskProfile.objects.update_or_create(
                company=company,
                defaults=step4_static
            )

            # --- STEP 4: RISK (DYNAMIC HAZARDS) ---
            hazards_data = format_step4_dynamic_data(data)
            RiskHazard.objects.filter(company=company).delete()
            
            if hazards_data:
                hazards_to_create = []
                for hazard in hazards_data:
                    hazards_to_create.append(RiskHazard(
                        company=company,
                        hazard_description=hazard.get('hazard_description', ''),
                        likelihood=hazard.get('likelihood', ''),
                        consequence=hazard.get('consequence', ''),
                        control_measures=hazard.get('control_measures', '')
                    ))
                RiskHazard.objects.bulk_create(hazards_to_create)

            # --- STEP 5: SUBCONTRACTORS (STATIC FIELDS) ---
            step5_static = format_step5_static_data(data)
            CompanySubcontractorProfile.objects.update_or_create(
                company=company,
                defaults=step5_static
            )

            # --- STEP 5: SUBCONTRACTORS (DYNAMIC RECORDS) ---
            sub_records_data = format_step5_dynamic_data(data)
            SubcontractorRecord.objects.filter(company=company).delete()
            
            if sub_records_data:
                subs_to_create = []
                for sub in sub_records_data:
                    expiry = sub.get('contract_expiry')
                    if not expiry or str(expiry).strip() == "":
                        expiry = None
                        
                    subs_to_create.append(SubcontractorRecord(
                        company=company,
                        subcontractor_name=sub.get('subcontractor_name', ''),
                        abn=sub.get('abn', ''),
                        licence_type=sub.get('licence_type', ''),
                        contract_expiry=expiry
                    ))
                SubcontractorRecord.objects.bulk_create(subs_to_create)

            # --- STEP 6: INCIDENTS (STATIC FIELDS) ---
            step6_static = format_step6_static_data(data)
            CompanyIncidentProfile.objects.update_or_create(
                company=company,
                defaults=step6_static
            )

            # --- STEP 6: INCIDENTS (DYNAMIC RECORDS) ---
            incident_records_data = format_step6_dynamic_data(data)
            IncidentRecord.objects.filter(company=company).delete()
            
            if incident_records_data:
                incidents_to_create = []
                for inc in incident_records_data:
                    inc_date = inc.get('incident_date')
                    if not inc_date or str(inc_date).strip() == "":
                        inc_date = None
                        
                    incidents_to_create.append(IncidentRecord(
                        company=company,
                        incident_date=inc_date,
                        description=inc.get('description', ''),
                        incident_type=inc.get('incident_type', ''),
                        outcome=inc.get('outcome', '')
                    ))
                IncidentRecord.objects.bulk_create(incidents_to_create)

            generate_company_document_for_company(company)
            
            redirect_url = reverse('profile')
            
            return JsonResponse({
                'status': 'success', 
                'message': 'Profile saved successfully!',
                'redirect_url': redirect_url
            })

        except Exception as e:
            print("Submission error:", e)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Invalid method.'}, status=405)


def sms_manual(request):
    context = {}
    
    if request.user and request.user.is_authenticated:
        print(f"Authenticated user: {request.user}")
        
        # Try to fetch the existing company profile using the related_name
        try:
            context['company'] = request.user.company_profile
        except ObjectDoesNotExist:
            # If they don't have a company profile yet, that's perfectly fine.
            context['company'] = None

    return render(request, 'sms_builder/sms_manual/sms-manual.html', context)

@login_required(login_url='signin')
def profile(request):
    """Company profile page with all dynamic data"""
    
    # Get the logged-in user's company
    try:
        company = Company.objects.get(user=request.user)
    except Company.DoesNotExist:
        messages.error(request, "Company profile not found.")
        return redirect('dashboard')
    
    # ── 1. FLEET VEHICLES ──
    vehicles = Vehicle.objects.filter(company=company)
    total_vehicles = vehicles.count()
    pending_vehicles = vehicles.filter(approval_status='pending').count()
    approved_vehicles = vehicles.filter(approval_status='approved').count()
    recent_vehicles = vehicles.order_by('-created_at')[:5]
    
    # ── 2. DRIVERS ──
    drivers = Driver.objects.filter(company=company)
    num_drivers = drivers.count()
    pending_drivers = drivers.filter(approval_status='pending').count()
    approved_drivers = drivers.filter(approval_status='approved').count()
    recent_drivers = drivers.order_by('-created_at')[:5]
    
    # ── 3. INCIDENTS ──
    incident_profile = getattr(company, 'incident_profile', None)
    incidents_12m = incident_profile.incidents_last_12_months if incident_profile else 0
    incidents_3y = incident_profile.incidents_last_3_years if incident_profile else 0
    incident_records_count = IncidentRecord.objects.filter(company=company).count()
    total_incidents = max(incidents_12m + incidents_3y, incident_records_count)
    recent_incidents = IncidentRecord.objects.filter(company=company).order_by('-incident_date')[:5]
    
    # ── 4. REVIEWS ──
    reviews = Review.objects.filter(company=company).order_by('-created_at')[:5]
    total_reviews = Review.objects.filter(company=company).count()
    avg_rating_data = Review.objects.filter(company=company).aggregate(Avg('rating'))
    avg_rating = avg_rating_data['rating__avg'] or 0
    
    # ── 5. SUBSCRIPTION DETAILS ──
    subscription = getattr(company, 'subscription', None)
    current_plan = subscription.plan.display_name if subscription and subscription.plan else company.subscription_plan.title() if company.subscription_plan else "Professional"
    
    # Get all available plans for upgrade/downgrade
    available_plans = PricingPlan.objects.filter(is_active=True).exclude(
        name=company.subscription_plan if company.subscription_plan else ''
    ).order_by('price')
    
    # Get subscription history
    subscription_history = SubscriptionHistory.objects.filter(
        subscription=subscription
    ).order_by('-changed_at')[:10] if subscription else []
    
    # ── 6. COMPLIANCE SCORE ──
    compliance_score = 82
    
    # ── 7. VEHICLE TYPES SUMMARY ──
    vehicle_types = {}
    for vehicle in vehicles:
        vehicle_type = vehicle.get_vehicle_type_display()
        vehicle_types[vehicle_type] = vehicle_types.get(vehicle_type, 0) + 1
        
    generated_documents = CompanyDocument.objects.filter(company=company).order_by('-created_at')
    latest_document = generated_documents.first()
    
    context = {
        'company': company,
        'user': request.user,
        'company_name_initials': company.company_name[:2].upper() if company.company_name else 'CO',
        
        # Fleet stats
        'vehicles': vehicles,
        'total_vehicles': total_vehicles,
        'pending_vehicles': pending_vehicles,
        'approved_vehicles': approved_vehicles,
        'recent_vehicles': recent_vehicles,
        'vehicle_types': vehicle_types,
        
        # Driver stats
        'drivers': drivers,
        'num_drivers': num_drivers,
        'pending_drivers': pending_drivers,
        'approved_drivers': approved_drivers,
        'recent_drivers': recent_drivers,
        
        # Incident stats
        'total_incidents': total_incidents,
        'incidents_12m': incidents_12m,
        'incidents_3y': incidents_3y,
        'recent_incidents': recent_incidents,
        
        # Compliance
        'compliance_score': compliance_score,
        
        # Subscription
        'current_plan': current_plan,
        'subscription_status': company.subscription_status or 'active',
        'subscription': subscription,
        'available_plans': available_plans,
        'subscription_history': subscription_history,
        
        # Reviews
        'reviews': reviews,
        'total_reviews': total_reviews,
        'avg_rating': round(avg_rating, 1),
        
        # DOCUMENTS (NEW)
        'generated_documents': generated_documents,
        'latest_document': latest_document,
    }
    
    return render(request, 'sms_builder/profile/profile.html', context)


@login_required
def request_plan_change(request):
    """Request to change subscription plan - Redirects to Stripe Checkout"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})

    try:
        data = json.loads(request.body)
        new_plan_name = data.get('plan_name')
        change_reason = data.get('reason', '')

        # Get company
        company = Company.objects.get(user=request.user)

        # Get new plan
        try:
            new_plan = PricingPlan.objects.get(name=new_plan_name, is_active=True)
        except PricingPlan.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Selected plan not found'})

        # Check if plan has Stripe price ID
        if not new_plan.stripe_price_id:
            return JsonResponse({'success': False, 'error': 'Payment not configured for this plan. Please contact support.'})

        # Create or get Stripe customer
        if not company.stripe_customer_id:
            customer = stripe.Customer.create(
                email=request.user.email,
                name=company.company_name,
                phone=request.user.phone or '',
                metadata={
                    'company_id': company.id,
                    'company_name': company.company_name,
                    'user_id': request.user.id,
                }
            )
            company.stripe_customer_id = customer.id
            company.save()
            print(f"✅ Created Stripe customer: {customer.id}")

        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=company.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': new_plan.stripe_price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=request.build_absolute_uri(reverse('checkout_success')) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.build_absolute_uri(reverse('profile')) + '?payment=cancelled',
            metadata={
                'company_id': company.id,
                'plan_name': new_plan.name,
                'user_id': request.user.id
            }
        )

        print(f"✅ Created checkout session: {checkout_session.id}")
        print(f"   Success URL: {checkout_session.success_url}")

        return JsonResponse({
            'success': True,
            'checkout_url': checkout_session.url,
            'checkout_session_id': checkout_session.id,
        })

    except Company.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Company not found'})
    except stripe.error.StripeError as e:
        print(f"❌ Stripe error: {e}")
        return JsonResponse({'success': False, 'error': f'Payment error: {str(e)}'})
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def handle_checkout_success(request):
    """Handle successful checkout from Stripe"""
    print("=" * 60)
    print("HANDLE_CHECKOUT_SUCCESS - CALLED")
    print(f"GET parameters: {dict(request.GET)}")
    print(f"User: {request.user.email}")
    print("=" * 60)

    session_id = request.GET.get('session_id')

    if not session_id:
        print("❌ No session_id found")
        messages.error(request, 'Invalid checkout session - no session ID')
        return redirect('profile')

    print(f"✅ Session ID: {session_id}")

    try:
        # Retrieve the checkout session from Stripe
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        print(f"✅ Checkout session retrieved")
        print(f"   Payment status: {checkout_session.payment_status}")
        print(f"   Customer: {checkout_session.customer}")
        print(f"   Subscription: {checkout_session.subscription}")

        # Get the amount paid (convert from cents to dollars)
        amount_paid = 0
        if checkout_session.amount_total:
            amount_paid = checkout_session.amount_total / 100
            print(f"   Amount paid: ${amount_paid}")

        # Check if payment was successful
        if checkout_session.payment_status != 'paid':
            print(f"⚠️ Payment status is not paid: {checkout_session.payment_status}")
            messages.error(request, 'Payment was not completed successfully.')
            return redirect('profile')

        # Check if metadata exists
        if not hasattr(checkout_session, 'metadata') or not checkout_session.metadata:
            print("❌ No metadata found in checkout session")
            messages.error(request, 'Payment information incomplete')
            return redirect('profile')

        # Access metadata directly as attributes
        company_id = getattr(checkout_session.metadata, 'company_id', None)
        new_plan_name = getattr(checkout_session.metadata, 'plan_name', None)

        print(f"Company ID from metadata: {company_id}")
        print(f"Plan name from metadata: {new_plan_name}")

        if not company_id:
            print("❌ No company_id in metadata")
            messages.error(request, 'Company information not found')
            return redirect('profile')

        # Get company
        try:
            company = Company.objects.get(id=company_id, user=request.user)
            print(f"✅ Company found: {company.company_name}")
        except Company.DoesNotExist:
            print(f"❌ Company not found with id={company_id}")
            messages.error(request, 'Company not found')
            return redirect('profile')

        if not new_plan_name:
            print("❌ No plan_name in metadata")
            messages.error(request, 'Plan information not found')
            return redirect('profile')

        try:
            new_plan = PricingPlan.objects.get(name=new_plan_name, is_active=True)
            print(f"✅ Plan found: {new_plan.display_name} (${new_plan.price})")
        except PricingPlan.DoesNotExist:
            print(f"❌ Plan not found: {new_plan_name}")
            messages.error(request, 'Plan not found')
            return redirect('profile')

        # Update or create subscription
        subscription, created = CompanySubscription.objects.update_or_create(
            company=company,
            defaults={
                'plan': new_plan,
                'status': 'active',
                'stripe_subscription_id': checkout_session.subscription,
                'stripe_customer_id': checkout_session.customer,
                'amount_paid': amount_paid,  # Use actual amount from Stripe
                'auto_renew': True,
                'start_date': timezone.now(),
                'end_date': timezone.now() + timezone.timedelta(days=30 if new_plan.price_period == 'month' else 365),
            }
        )

        if created:
            print(f"✅ New subscription created (ID: {subscription.id})")
            # Create subscription created history
            SubscriptionHistory.objects.create(
                subscription=subscription,
                new_plan=new_plan,
                action='created',
                notes=f'Subscription created via Stripe checkout. Session: {session_id}',
                changed_by=request.user,
                amount=amount_paid  # Add amount
            )
        else:
            print(f"✅ Existing subscription updated (ID: {subscription.id})")
            old_plan = subscription.plan
            # Create upgrade/downgrade history
            action = 'upgraded' if new_plan.price > old_plan.price else 'downgraded'
            SubscriptionHistory.objects.create(
                subscription=subscription,
                old_plan=old_plan,
                new_plan=new_plan,
                action=action,
                notes=f'Plan changed via Stripe checkout. Session: {session_id}',
                changed_by=request.user,
                amount=amount_paid  # Add amount
            )

        # ✅ CREATE PAYMENT RECORD (This is what you need for payment_history)
        SubscriptionHistory.objects.create(
            subscription=subscription,
            new_plan=new_plan,
            action='payment_succeeded',  # Payment action
            notes=f'Payment of ${amount_paid} received via Stripe. Session: {session_id}',
            changed_by=request.user,
            amount=amount_paid,  # Store the payment amount
            stripe_event_id=session_id  # Store Stripe event ID
        )
        print(f"✅ Payment record created with amount: ${amount_paid}")

        # Update company status
        company.subscription_plan = new_plan.name
        company.subscription_status = 'active'
        company.stripe_customer_id = checkout_session.customer
        company.save()
        print(f"✅ Company updated: plan={new_plan.name}, status=active")

        messages.success(request, f'Successfully subscribed to {new_plan.display_name} plan! Payment of ${amount_paid} received.')
        print("✅ SUCCESS - Subscription and payment record saved to database")

    except stripe.error.StripeError as e:
        print(f"❌ Stripe error: {str(e)}")
        messages.error(request, f'Payment verification error: {str(e)}')
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        messages.error(request, f'Error: {str(e)}')

    print("=" * 60)
    print("REDIRECTING TO PROFILE")
    print("=" * 60)
    return redirect('profile')

@login_required
def create_portal_session(request):
    """Create Stripe Customer Portal session for managing subscription"""
    try:
        company = Company.objects.get(user=request.user)

        if not company.stripe_customer_id:
            return JsonResponse({'error': 'No payment method found'}, status=400)

        portal_session = stripe.billing_portal.Session.create(
            customer=company.stripe_customer_id,
            return_url=request.build_absolute_uri(reverse('profile'))
        )

        return JsonResponse({'url': portal_session.url})

    except Company.DoesNotExist:
        return JsonResponse({'error': 'Company not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def cancel_plan_change(request):
    """Cancel a pending plan change request"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        company = Company.objects.get(user=request.user)
        subscription = getattr(company, 'subscription', None)
        
        if not subscription or subscription.status != 'pending_change':
            return JsonResponse({'success': False, 'error': 'No pending change request found'})
        
        # Revert to previous status
        old_status = 'active' if subscription.end_date and subscription.end_date > timezone.now() else 'expired'
        subscription.status = old_status
        
        # If there was an old plan, revert to it
        last_history = SubscriptionHistory.objects.filter(
            subscription=subscription,
            action__in=['upgrade_requested', 'downgrade_requested']
        ).first()
        
        if last_history and last_history.old_plan:
            subscription.plan = last_history.old_plan
        
        subscription.save()
        
        # Update company status
        company.subscription_status = old_status
        company.save()
        
        # Create cancellation record
        SubscriptionHistory.objects.create(
            subscription=subscription,
            action='change_cancelled',
            notes='Plan change request cancelled by user',
            changed_by=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Plan change request has been cancelled.'
        })
        
    except Company.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Company not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def cancel_subscription(request):
    """Cancel current subscription"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        company = Company.objects.get(user=request.user)
        subscription = getattr(company, 'subscription', None)
        
        if not subscription:
            return JsonResponse({'success': False, 'error': 'No active subscription found'})
        
        # Update subscription
        old_status = subscription.status
        subscription.status = 'cancelled'
        subscription.auto_renew = False
        subscription.save()
        
        # Update company
        company.subscription_status = 'cancelled'
        company.save()
        
        # Create history record
        SubscriptionHistory.objects.create(
            subscription=subscription,
            action='cancelled',
            notes=f'Subscription cancelled by user. Previous status: {old_status}',
            changed_by=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Your subscription has been cancelled.'
        })
        
    except Company.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Company not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

# ==============================
# VEHICLE MANAGEMENT (AJAX)
# ==============================

@login_required(login_url='signin')
@require_http_methods(["POST"])
def add_vehicle_ajax(request):
    """Add a new vehicle via AJAX"""
    try:
        company = get_object_or_404(Company, user=request.user)
        
        data = json.loads(request.body)
        
        make = data.get('make', '').strip()
        model = data.get('model', '').strip()
        year = data.get('year', '').strip()
        vin = data.get('vin', '').strip().upper()
        registration_number = data.get('registration_number', '').strip().upper()
        vehicle_type = data.get('vehicle_type', '').strip()
        registration_expiry = data.get('registration_expiry', '').strip()
        
        if not make:
            return JsonResponse({'success': False, 'error': 'Make is required'})
        
        if not model:
            return JsonResponse({'success': False, 'error': 'Model is required'})
        
        if not vin:
            return JsonResponse({'success': False, 'error': 'VIN is required'})
        
        if Vehicle.objects.filter(vin=vin).exists():
            return JsonResponse({'success': False, 'error': 'VIN already exists'})
        
        vehicle = Vehicle.objects.create(
            company=company,
            make=make,
            model=model,
            year=int(year) if year else 2024,
            vin=vin,
            registration_number=registration_number,
            vehicle_type=vehicle_type,
            registration_expiry=registration_expiry,
            status='current',
            approval_status='pending',
            created_by=request.user
        )
        
        return JsonResponse({'success': True, 'message': 'Vehicle added successfully! Pending admin approval.', 'vehicle_id': vehicle.id})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required(login_url='signin')
@require_http_methods(["POST"])
def edit_vehicle_ajax(request, vehicle_id):
    """Edit vehicle via AJAX"""
    try:
        company = get_object_or_404(Company, user=request.user)
        vehicle = get_object_or_404(Vehicle, id=vehicle_id, company=company)
        
        data = json.loads(request.body)
        
        vehicle.make = data.get('make', vehicle.make)
        vehicle.model = data.get('model', vehicle.model)
        vehicle.year = int(data.get('year', vehicle.year))
        vehicle.vin = data.get('vin', vehicle.vin).upper()
        vehicle.registration_number = data.get('registration_number', vehicle.registration_number).upper()
        vehicle.vehicle_type = data.get('vehicle_type', vehicle.vehicle_type)
        vehicle.registration_expiry = data.get('registration_expiry', vehicle.registration_expiry)
        
        # Reset approval status
        if vehicle.approval_status == 'approved':
            vehicle.approval_status = 'pending'
        
        vehicle.save()
        
        return JsonResponse({'success': True, 'message': 'Vehicle updated successfully! Pending admin approval.'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required(login_url='signin')
@require_http_methods(["POST"])
def delete_vehicle_ajax(request, vehicle_id):
    """Delete vehicle via AJAX"""
    try:
        company = get_object_or_404(Company, user=request.user)
        vehicle = get_object_or_404(Vehicle, id=vehicle_id, company=company)
        vehicle.delete()
        return JsonResponse({'success': True, 'message': 'Vehicle deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required(login_url='signin')
def get_vehicle_details_ajax(request, vehicle_id):
    """Get vehicle details via AJAX"""
    try:
        company = get_object_or_404(Company, user=request.user)
        vehicle = get_object_or_404(Vehicle, id=vehicle_id, company=company)
        
        return JsonResponse({
            'success': True,
            'vehicle': {
                'id': vehicle.id,
                'make': vehicle.make,
                'model': vehicle.model,
                'year': vehicle.year,
                'vin': vehicle.vin,
                'registration_number': vehicle.registration_number,
                'vehicle_type': vehicle.vehicle_type,
                'registration_expiry': vehicle.registration_expiry.strftime('%Y-%m-%d'),
                'approval_status': vehicle.approval_status,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ==============================
# DRIVER MANAGEMENT (AJAX)
# ==============================

@login_required(login_url='signin')
@require_http_methods(["POST"])
def add_driver_ajax(request):
    """Add a new driver via AJAX"""
    try:
        company = get_object_or_404(Company, user=request.user)
        
        data = json.loads(request.body)
        
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        email = data.get('email', '').strip()
        phone = data.get('phone', '').strip()
        role = data.get('role', '').strip()
        licence_number = data.get('licence_number', '').strip()
        licence_class = data.get('licence_class', '').strip()
        licence_expiry = data.get('licence_expiry', '').strip()
        
        if not first_name:
            return JsonResponse({'success': False, 'error': 'First name is required'})
        
        if not last_name:
            return JsonResponse({'success': False, 'error': 'Last name is required'})
        
        if not licence_number:
            return JsonResponse({'success': False, 'error': 'Licence number is required'})
        
        if Driver.objects.filter(licence_number=licence_number).exists():
            return JsonResponse({'success': False, 'error': 'Licence number already exists'})
        
        driver = Driver.objects.create(
            company=company,
            first_name=first_name,
            last_name=last_name,
            email=email if email else None,
            phone=phone if phone else None,
            role=role if role else None,
            licence_number=licence_number,
            licence_class=licence_class,
            licence_expiry=licence_expiry,
            status='active',
            approval_status='pending',
            created_by=request.user
        )
        
        return JsonResponse({'success': True, 'message': 'Driver added successfully! Pending admin approval.', 'driver_id': driver.id})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required(login_url='signin')
@require_http_methods(["POST"])
def edit_driver_ajax(request, driver_id):
    """Edit driver via AJAX"""
    try:
        company = get_object_or_404(Company, user=request.user)
        driver = get_object_or_404(Driver, id=driver_id, company=company)
        
        data = json.loads(request.body)
        
        driver.first_name = data.get('first_name', driver.first_name)
        driver.last_name = data.get('last_name', driver.last_name)
        driver.email = data.get('email', driver.email)
        driver.phone = data.get('phone', driver.phone)
        driver.role = data.get('role', driver.role)
        driver.licence_number = data.get('licence_number', driver.licence_number)
        driver.licence_class = data.get('licence_class', driver.licence_class)
        driver.licence_expiry = data.get('licence_expiry', driver.licence_expiry)
        
        # Reset approval status
        if driver.approval_status == 'approved':
            driver.approval_status = 'pending'
        
        driver.save()
        
        return JsonResponse({'success': True, 'message': 'Driver updated successfully! Pending admin approval.'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required(login_url='signin')
@require_http_methods(["POST"])
def delete_driver_ajax(request, driver_id):
    """Delete driver via AJAX"""
    try:
        company = get_object_or_404(Company, user=request.user)
        driver = get_object_or_404(Driver, id=driver_id, company=company)
        driver.delete()
        return JsonResponse({'success': True, 'message': 'Driver deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required(login_url='signin')
def get_driver_details_ajax(request, driver_id):
    """Get driver details via AJAX"""
    try:
        company = get_object_or_404(Company, user=request.user)
        driver = get_object_or_404(Driver, id=driver_id, company=company)
        
        return JsonResponse({
            'success': True,
            'driver': {
                'id': driver.id,
                'first_name': driver.first_name,
                'last_name': driver.last_name,
                'full_name': driver.full_name,
                'email': driver.email,
                'phone': driver.phone,
                'role': driver.role,
                'licence_number': driver.licence_number,
                'licence_class': driver.licence_class,
                'licence_expiry': driver.licence_expiry.strftime('%Y-%m-%d'),
                'approval_status': driver.approval_status,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='signin')
def add_review(request):
    """Add a review for a company"""
    if request.method == 'POST':
        try:
            company_id = request.POST.get('company_id')
            rating = request.POST.get('rating')
            review_text = request.POST.get('review_text')
            reviewer_name = request.POST.get('reviewer_name', request.user.full_name)
            reviewer_role = request.POST.get('reviewer_role', '')
            title = request.POST.get('title', '')
            
            # Validation
            if not company_id:
                messages.error(request, "Company is required.")
                return redirect('profile')
            
            if not rating:
                messages.error(request, "Please select a rating.")
                return redirect('profile')
            
            if not review_text:
                messages.error(request, "Please write a review.")
                return redirect('profile')
            
            if len(review_text) < 20:
                messages.error(request, "Review must be at least 20 characters.")
                return redirect('profile')
            
            company = get_object_or_404(Company, id=company_id)
            
            # Create review
            review = Review.objects.create(
                company=company,
                user=request.user,
                rating=int(rating),
                title=title,
                review_text=review_text,
                reviewer_name=reviewer_name,
                reviewer_role=reviewer_role,
                reviewer_company=company.company_name,
                is_approved=False  # Requires admin approval
            )
            
            messages.success(request, "Thank you for your review! It will be visible after admin approval.")
            return redirect('profile')
            
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect('profile')
    
    return redirect('profile')


@login_required(login_url='signin')
def delete_review(request, review_id):
    """Delete a review"""
    try:
        review = get_object_or_404(Review, id=review_id, user=request.user)
        review.delete()
        messages.success(request, "Review deleted successfully.")
        return redirect('profile')
    except Exception as e:
        messages.error(request, f"Error: {str(e)}")
        return redirect('profile')
    

@login_required
def generate_company_documents(request):

    # 1. Get company
    try:
        company = request.user.company_profile
    except:
        raise Http404("You do not have an associated company profile.")

    doc_obj = generate_company_document_for_company(company)

    safe_name = (company.company_name or "Company").replace(" ", "_")
    file_name = f"{safe_name}_SMS_Document.pdf"

    return JsonResponse({
        "status": "success",
        "message": "Document generated successfully",
        "file_url": doc_obj.file.url if doc_obj and doc_obj.file else "",
        "file_name": file_name,
        "uploaded_on": doc_obj.created_at.strftime("%b %d, %Y") if doc_obj else ""
    })
    
    
@login_required(login_url='signin')
@require_http_methods(["POST"])
def change_password_ajax(request):
    """Change user password via AJAX"""
    try:
        data = json.loads(request.body)
        current_password = data.get('current_password')
        new_password = data.get('new_password')

        # Validate current password
        if not request.user.check_password(current_password):
            return JsonResponse({'success': False, 'error': 'Current password is incorrect'})

        # Validate new password length
        if len(new_password) < 8:
            return JsonResponse({'success': False, 'error': 'New password must be at least 8 characters long'})

        # Validate uppercase
        if not any(c.isupper() for c in new_password):
            return JsonResponse({'success': False, 'error': 'New password must contain at least one uppercase letter'})

        # Validate lowercase
        if not any(c.islower() for c in new_password):
            return JsonResponse({'success': False, 'error': 'New password must contain at least one lowercase letter'})

        # Validate number
        if not any(c.isdigit() for c in new_password):
            return JsonResponse({'success': False, 'error': 'New password must contain at least one number'})

        # Validate password is different from current
        if request.user.check_password(new_password):
            return JsonResponse({'success': False, 'error': 'New password must be different from your current password'})

        # Update password
        request.user.set_password(new_password)
        request.user.save()

        # Update session to keep user logged in (optional - can also force logout)
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, request.user)

        return JsonResponse({'success': True, 'message': 'Password changed successfully'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})







import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

def create_stripe_prices_for_plans():
    """Create Stripe Price objects for all active pricing plans"""
    from .models import PricingPlan

    plans = PricingPlan.objects.filter(is_active=True)

    for plan in plans:
        try:
            # Check if price already exists
            if plan.stripe_price_id:
                print(f"Plan {plan.name} already has Stripe price ID: {plan.stripe_price_id}")
                continue

            # Create or get product
            product = None
            if plan.stripe_product_id:
                try:
                    product = stripe.Product.retrieve(plan.stripe_product_id)
                except:
                    product = None

            if not product:
                # Create product in Stripe
                product = stripe.Product.create(
                    name=plan.display_name,
                    description=f"{plan.display_name} Plan - Heavy Vehicle Compliance",
                    metadata={
                        'plan_name': plan.name,
                        'plan_display_name': plan.display_name
                    }
                )
                plan.stripe_product_id = product.id

            # Create price for the plan
            price = stripe.Price.create(
                product=product.id,
                unit_amount=int(plan.price * 100),  # Convert to cents
                currency='aud',
                recurring={
                    'interval': plan.price_period,  # 'month' or 'year'
                },
                metadata={
                    'plan_name': plan.name
                }
            )

            plan.stripe_price_id = price.id
            plan.save()

            print(f"✅ Created Stripe price for {plan.display_name}: {price.id}")

        except Exception as e:
            print(f"❌ Error creating Stripe price for {plan.name}: {str(e)}")
    