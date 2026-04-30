from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import json
import re
from sms_builder.models import *
import logging
import secrets
import string
import stripe
import os
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from sms_builder.models import SystemSettings, AdminProfile, User
import json
from django.db.models import Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.core.mail import send_mail
from django.utils.crypto import get_random_string
import json
from datetime import datetime
# =========================
# USER DASHBOARD (PUBLIC)
# =========================
# views.py - Update dashboard view

@login_required(login_url='admin_login')
def dashboard(request):
    """Admin Dashboard with dynamic data"""
    
    # Get counts
    total_companies = Company.objects.count()
    total_drivers = Driver.objects.count()
    total_vehicles = Vehicle.objects.count()
    open_incidents = 3  # You can create an Incident model for this
    
    # Get recent companies
    recent_companies = Company.objects.select_related('user').order_by('-registration_date')[:5]
    
    # Get subscription stats
    starter_plans = Company.objects.filter(subscription_plan='starter').count()
    professional_plans = Company.objects.filter(subscription_plan='professional').count()
    enterprise_plans = Company.objects.filter(subscription_plan='enterprise').count()
    
    # Calculate monthly recurring revenue
    starter_revenue = starter_plans * 29
    professional_revenue = professional_plans * 59
    enterprise_revenue = enterprise_plans * 99
    total_mrr = starter_revenue + professional_revenue + enterprise_revenue
    
    # Get active subscriptions
    active_subscriptions = CompanySubscription.objects.filter(status='active').count()
    
    # Get unread messages count
    unread_messages = ContactMessage.objects.filter(status='new').count()
    
    # Prepare recent companies data
    recent_companies_data = []
    for company in recent_companies:
        recent_companies_data.append({
            'id': company.id,
            'company_name': company.company_name,
            'abn': company.abn,
            'subscription_plan': company.subscription_plan or 'starter',
            'status': company.status,
            'registration_date': company.registration_date,
            'initials': company.company_name[:2].upper(),
        })
    
    context = {
        'total_companies': total_companies,
        'total_drivers': total_drivers,
        'total_vehicles': total_vehicles,
        'open_incidents': open_incidents,
        'starter_plans': starter_plans,
        'professional_plans': professional_plans,
        'enterprise_plans': enterprise_plans,
        'starter_revenue': starter_revenue,
        'professional_revenue': professional_revenue,
        'enterprise_revenue': enterprise_revenue,
        'total_mrr': total_mrr,
        'active_subscriptions': active_subscriptions,
        'unread_messages': unread_messages,
        'recent_companies': recent_companies_data,
    }
    
    return render(request, 'backend/dashboard/dashboard.html', context)



# =========================
# ADMIN LOGIN
# =========================
@csrf_protect
@never_cache

def admin_login(request):

    if request.user.is_authenticated:
        if request.user.user_type == 'admin':
            return redirect('admin_dashboard')
        return redirect('dashboard')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        remember = request.POST.get('remember')

        if not email or not password:
            messages.error(request, "Please enter both email and password.")
            return redirect('admin_login')

        user = authenticate(request, username=email, password=password)

        if user is None:
            messages.error(request, "Invalid email or password.")
            return redirect('admin_login')

        if user.user_type != 'admin':
            messages.error(request, "Access denied. Admin only.")
            return redirect('admin_login')

        if not user.is_active:
            messages.error(request, "Account is deactivated.")
            return redirect('admin_login')

        login(request, user)

        # session expiry
        if not remember:
            request.session.set_expiry(0)
        else:
            request.session.set_expiry(1209600)

        return redirect('admin_dashboard')

    return render(request, 'backend/login.html')


# =========================
# ADMIN DASHBOARD
# =========================
@login_required(login_url='admin_login')
def admin_dashboard(request):

    if request.user.user_type != 'admin':
        messages.error(request, "Access denied. Admin only.")
        return redirect('dashboard')

    context = {
        'total_companies': Company.objects.count(),
        'pending_companies': Company.objects.filter(status='pending').count(),
        'approved_companies': Company.objects.filter(status='approved').count(),
        'total_users': User.objects.filter(user_type='company').count(),
        'recent_companies': Company.objects.order_by('-registration_date')[:5],
    }

    return render(request, 'backend/dashboard/dashboard.html', context)


# =========================
# ADMIN LOGOUT
# =========================
@login_required(login_url='admin_login')
def admin_logout(request):
    logout(request)
    messages.info(request, "You have been successfully logged out.")
    return redirect('admin_login')


# =========================
# FORGOT PASSWORD
# =========================
# Forgot Password View
def admin_forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        
        if not email:
            messages.error(request, 'Please enter your email address.')
            return render(request, 'backend/forgot_password.html')
        
        try:
            user = User.objects.get(email=email, is_superuser=True)
            
            # Generate reset token
            token = get_random_string(64)  # Increased to 64 for better security
            expiry = timezone.now() + timedelta(hours=24)
            
            # Delete any existing unused tokens for this user
            PasswordResetToken.objects.filter(user=user, used=False).delete()
            
            # Save new token
            reset_obj = PasswordResetToken.objects.create(
                user=user,
                token=token,
                expiry=expiry,
                used=False
            )
            
            # Build reset link - make sure it's a complete URL
            reset_link = request.build_absolute_uri(f'/admin/reset-password/{token}/')
            
            # Send email with proper formatting
            email_subject = 'Password Reset Request - PRODRIVE Compliance'
            email_body = f'''
Hello {user.username},

We received a request to reset your password for your PRODRIVE Compliance account.

Click the link below to reset your password:
{reset_link}

This link will expire in 24 hours.

If you did not request this password reset, please ignore this email. Your password will remain unchanged.

Best regards,
PRODRIVE Team

--
This is an automated message, please do not reply.
'''
            
            send_mail(
                email_subject,
                email_body.strip(),
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            
            # Log success
            print(f"Password reset email sent to {email}")
            print(f"Reset link: {reset_link}")
            
            messages.success(request, 'Password reset link has been sent to your email address.')
            return render(request, 'backend/forgot_password.html', {'email_sent': True})
            
        except User.DoesNotExist:
            # For security, don't reveal that the email doesn't exist
            messages.info(request, 'If an account exists with this email, a reset link will be sent.')
            return render(request, 'backend/forgot_password.html')
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            messages.error(request, f'An error occurred: {str(e)}')
            return render(request, 'backend/forgot_password.html')
    
    return render(request, 'backend/forgot_password.html')


def admin_reset_password(request, token):
    print(f"Reset password attempt with token: {token[:20]}...")  # Debug log
    
    # First, check if token exists and is valid
    try:
        reset_obj = PasswordResetToken.objects.get(token=token, used=False)
        
        # Check if token has expired
        if reset_obj.expiry <= timezone.now():
            messages.error(request, 'This password reset link has expired. Please request a new one.')
            return redirect('admin_forgot_password')
        
        user = reset_obj.user
        print(f"Token valid for user: {user.email}")  # Debug log
        
    except PasswordResetToken.DoesNotExist:
        print(f"Token not found: {token}")  # Debug log
        messages.error(request, 'Invalid or expired reset link. Please request a new one.')
        return redirect('admin_forgot_password')
    
    # Process password reset form
    if request.method == 'POST':
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        # Validation
        if not password:
            messages.error(request, 'Please enter a password.')
            return render(request, 'backend/reset_password.html', {'token': token})
        
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'backend/reset_password.html', {'token': token})
        
        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return render(request, 'backend/reset_password.html', {'token': token})
        
        # Set new password
        user.set_password(password)
        user.save()
        
        # Mark token as used
        reset_obj.used = True
        reset_obj.save()
        
        messages.success(request, 'Password reset successful! Please login with your new password.')
        return redirect('admin_login')
    
    # GET request - show reset password form
    return render(request, 'backend/reset_password.html', {'token': token, 'valid_token': True})

@login_required(login_url='admin_login')
def companies_view(request):
    """Companies management page"""

    # 🔐 Admin check
    if request.user.user_type != 'admin':
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('dashboard')

    # Get all companies with user data
    companies = Company.objects.select_related('user').all().order_by('-registration_date')
    
    # Prepare company data for template
    companies_data = []
    for company in companies:
        companies_data.append({
            'id': company.id,
            'company_name': company.company_name,
            'abn': company.abn,
            'address': company.address,
            'status': company.status,
            'subscription_plan': getattr(company, 'subscription_plan', 'starter'),
            'registration_date': company.registration_date,
            'contact_person': company.user.full_name if company.user.full_name else '-',
            'email': company.user.email,
            'phone': company.user.phone if company.user.phone else '-',
        })
    
    # Debug print to console
    print(f"Number of companies found: {len(companies_data)}")
    for c in companies_data:
        print(f"Company: {c['company_name']}")
    
    context = {
        'companies': companies_data,
    }
    
    return render(request, 'backend/dashboard/company.html', context)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def add_company(request):
    """Add a new company"""
    try:
        # Get form data
        company_name = request.POST.get('company_name', '').strip()
        abn = request.POST.get('abn', '').strip()
        contact_person = request.POST.get('contact_person', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        plan = request.POST.get('plan', '').lower()
        address = request.POST.get('address', '').strip()
        
        # Validation
        if not company_name:
            return JsonResponse({'success': False, 'error': 'Company name is required'}, status=400)
        
        if not abn:
            return JsonResponse({'success': False, 'error': 'ABN is required'}, status=400)
        
        # Clean ABN
        clean_abn = re.sub(r'\s+', '', abn)
        if not clean_abn.isdigit() or len(clean_abn) != 11:
            return JsonResponse({'success': False, 'error': 'Invalid ABN format'}, status=400)
        
        if not email:
            return JsonResponse({'success': False, 'error': 'Email is required'}, status=400)
        
        # Check if email exists
        if User.objects.filter(email=email).exists():
            return JsonResponse({'success': False, 'error': 'Email already exists'}, status=400)
        
        # Check if ABN exists
        if Company.objects.filter(abn=clean_abn).exists():
            return JsonResponse({'success': False, 'error': 'ABN already registered'}, status=400)
        
        # Create user
        name_parts = contact_person.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        # Generate random password
        def generate_random_password(length=12):
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            return ''.join(secrets.choice(alphabet) for _ in range(length))
        
        temp_password = generate_random_password()
        
        user = User.objects.create_user(
            email=email,
            password=temp_password,
            first_name=first_name,
            last_name=last_name,
            full_name=contact_person,
            phone=phone,
            user_type='company',
            is_active=True,
            is_verified=False,
            terms_accepted=True,
            terms_accepted_at=timezone.now()
        )
        
        # Create company
        company = Company.objects.create(
            user=user,
            company_name=company_name,
            abn=clean_abn,
            address=address,
            subscription_plan=plan,
            status='pending'
        )
        
        # TODO: Send welcome email with temp_password
        
        return JsonResponse({
            'success': True, 
            'message': 'Company added successfully',
            'company_id': company.id
        })
        
    except Exception as e:
        logger.error(f"Error in add_company: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def edit_company(request, company_id):
    """Edit company details including pricing plan"""
    try:
        company = get_object_or_404(Company, id=company_id)
        
        # Get form data
        company_name = request.POST.get('company_name', '').strip()
        abn = request.POST.get('abn', '').strip()
        contact_person = request.POST.get('contact_person', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        plan = request.POST.get('plan', '').lower()  # Pricing plan
        address = request.POST.get('address', '').strip()
        status = request.POST.get('status', '').lower()
        
        # Validation
        if not company_name:
            return JsonResponse({'success': False, 'error': 'Company name is required'}, status=400)
        
        # Clean ABN
        clean_abn = re.sub(r'\s+', '', abn)
        if clean_abn and (not clean_abn.isdigit() or len(clean_abn) != 11):
            return JsonResponse({'success': False, 'error': 'Invalid ABN format'}, status=400)
        
        # Check if ABN exists for other companies
        if clean_abn and Company.objects.filter(abn=clean_abn).exclude(id=company_id).exists():
            return JsonResponse({'success': False, 'error': 'ABN already registered to another company'}, status=400)
        
        # Get the old plan for history tracking
        old_plan = None
        if company.subscription_plan:
            try:
                old_plan = PricingPlan.objects.filter(name=company.subscription_plan).first()
            except:
                pass
        
        # Get the new pricing plan
        new_pricing_plan = None
        if plan:
            try:
                new_pricing_plan = PricingPlan.objects.get(name=plan)
            except PricingPlan.DoesNotExist:
                pass
        
        # Update company
        company.company_name = company_name
        if clean_abn:
            company.abn = clean_abn
        company.address = address
        company.subscription_plan = plan if plan else 'starter'
        company.status = status
        company.save()
        
        # Update or create subscription
        if new_pricing_plan:
            subscription, created = CompanySubscription.objects.update_or_create(
                company=company,
                defaults={
                    'plan': new_pricing_plan,
                    'status': 'active' if status == 'approved' else status,
                    'updated_at': timezone.now(),
                }
            )
            
            # Create history record if plan changed
            if old_plan and old_plan != new_pricing_plan:
                action = 'upgraded' if new_pricing_plan.price > old_plan.price else 'downgraded'
                SubscriptionHistory.objects.create(
                    subscription=subscription,
                    old_plan=old_plan,
                    new_plan=new_pricing_plan,
                    action=action,
                    notes=f'Plan changed from {old_plan.display_name} to {new_pricing_plan.display_name}',
                    changed_by=request.user
                )
        
        # Update user
        user = company.user
        if contact_person:
            name_parts = contact_person.split(' ', 1)
            user.first_name = name_parts[0]
            user.last_name = name_parts[1] if len(name_parts) > 1 else ''
            user.full_name = contact_person
        user.email = email
        user.phone = phone
        user.save()
        
        return JsonResponse({
            'success': True, 
            'message': 'Company updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error in edit_company: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


logger = logging.getLogger(__name__)

@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def get_company_details(request):
    """Get company details for editing"""
    try:
        # Log the request
        logger.info("get_company_details called")
        
        # Parse JSON body
        data = json.loads(request.body)
        company_id = data.get('company_id')
        
        logger.info(f"Company ID received: {company_id}")
        
        if not company_id:
            return JsonResponse({'success': False, 'error': 'Company ID is required'}, status=400)
        
        # Get company
        company = get_object_or_404(Company, id=company_id)
        
        logger.info(f"Company found: {company.company_name}")
        
        # Prepare response
        response_data = {
            'success': True,
            'company': {
                'id': company.id,
                'company_name': company.company_name,
                'abn': company.abn,
                'address': company.address if company.address else '',
                'subscription_plan': getattr(company, 'subscription_plan', 'starter'),
                'status': company.status,
                'contact_person': company.user.full_name if company.user.full_name else '',
                'email': company.user.email,
                'phone': company.user.phone if company.user.phone else '',
            }
        }
        
        logger.info(f"Response prepared: {response_data}")
        
        return JsonResponse(response_data)
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
        
    except Company.DoesNotExist as e:
        logger.error(f"Company not found: {str(e)}")
        return JsonResponse({'success': False, 'error': 'Company not found'}, status=404)
        
    except Exception as e:
        logger.error(f"Unexpected error in get_company_details: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def delete_company(request, company_id):
    """Delete/Deactivate company"""
    try:
        company = get_object_or_404(Company, id=company_id)
        
        # Option 1: Hard delete
        # company.user.delete()
        # company.delete()
        
        # Option 2: Soft delete (deactivate)
        company.status = 'inactive'
        company.user.is_active = False
        company.user.save()
        company.save()
        
        return JsonResponse({
            'success': True, 
            'message': 'Company deactivated successfully'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def approve_company(request, company_id):
    """Approve a pending company"""
    try:
        company = get_object_or_404(Company, id=company_id)
        company.status = 'approved'
        company.approved_at = timezone.now()
        company.approved_by = request.user
        company.user.is_verified = True
        company.user.save()
        company.save()
        
        # You can send approval email here
        
        return JsonResponse({
            'success': True, 
            'message': 'Company approved successfully'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@login_required(login_url='admin_login')
def filter_companies(request):
    """AJAX endpoint for filtering companies"""
    status = request.GET.get('status', '')
    plan = request.GET.get('plan', '')
    search = request.GET.get('search', '')
    
    companies = Company.objects.select_related('user').all()
    
    if status:
        companies = companies.filter(status=status.lower())
    
    if plan:
        companies = companies.filter(subscription_plan=plan.lower())
    
    if search:
        companies = companies.filter(
            Q(company_name__icontains=search) |
            Q(abn__icontains=search) |
            Q(user__email__icontains=search) |
            Q(user__full_name__icontains=search)
        )
    
    companies_data = []
    for company in companies:
        companies_data.append({
            'id': company.id,
            'company_name': company.company_name,
            'abn': company.abn,
            'contact_person': company.user.full_name or '-',
            'email': company.user.email,
            'phone': company.user.phone or '-',
            'subscription_plan': company.subscription_plan or 'starter',
            'status': company.status,
            'address': company.address or '',
        })
    
    return JsonResponse({'success': True, 'companies': companies_data})
# ==============================
# DRIVER VIEWS
# ==============================

@login_required(login_url='admin_login')
def drivers_view(request):
    """Drivers management page"""
    
    if request.user.user_type != 'admin':
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('dashboard')
    
    # Get all drivers with company info
    drivers = Driver.objects.select_related('company').all().order_by('-created_at')
    
    # Prepare driver data for template
    drivers_data = []
    for driver in drivers:
        drivers_data.append({
            'id': driver.id,
            'first_name': driver.first_name,
            'last_name': driver.last_name,
            'full_name': driver.full_name,
            'role': driver.role,
            'email': driver.email,
            'phone': driver.phone,
            'licence_number': driver.licence_number,
            'licence_class': driver.licence_class,
            'licence_expiry': driver.licence_expiry,
            'status': driver.status,
            'approval_status': driver.approval_status,
            'company_name': driver.company.company_name,
            'company_id': driver.company.id,
            'address': driver.address,
            'created_at': driver.created_at,
        })
    
    # Get all companies for filter
    companies = Company.objects.filter(status='approved').values('id', 'company_name')
    
    context = {
        'drivers': drivers_data,
        'companies': companies,
        'total_drivers': len(drivers_data),
        'active_drivers': Driver.objects.filter(status='active').count(),
        'review_due_drivers': Driver.objects.filter(status='review_due').count(),
        'pending_approval': Driver.objects.filter(approval_status='pending').count(),
    }
    
    return render(request, 'backend/dashboard/drivers.html', context)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def add_driver(request):
    """Add a new driver"""
    try:
        # Get form data
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        role = request.POST.get('role', '').strip()
        licence_number = request.POST.get('licence_number', '').strip()
        licence_class = request.POST.get('licence_class', '').strip()
        licence_expiry = request.POST.get('licence_expiry', '').strip()
        company_id = request.POST.get('company_id', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        postcode = request.POST.get('postcode', '').strip()
        approval_status = request.POST.get('approval_status', 'pending')
        
        # Validation
        if not first_name:
            return JsonResponse({'success': False, 'error': 'First name is required'}, status=400)
        
        if not last_name:
            return JsonResponse({'success': False, 'error': 'Last name is required'}, status=400)
        
        if not licence_number:
            return JsonResponse({'success': False, 'error': 'Licence number is required'}, status=400)
        
        if not licence_expiry:
            return JsonResponse({'success': False, 'error': 'Licence expiry date is required'}, status=400)
        
        if not company_id:
            return JsonResponse({'success': False, 'error': 'Company is required'}, status=400)
        
        # Check if licence number exists
        if Driver.objects.filter(licence_number=licence_number).exists():
            return JsonResponse({'success': False, 'error': 'Licence number already exists'}, status=400)
        
        # Get company
        company = get_object_or_404(Company, id=company_id)
        
        # Create driver
        driver = Driver.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=email if email else None,
            phone=phone if phone else None,
            role=role if role else None,
            licence_number=licence_number,
            licence_class=licence_class,
            licence_expiry=licence_expiry,
            company=company,
            address=address if address else None,
            city=city if city else None,
            state=state if state else None,
            postcode=postcode if postcode else None,
            status='active',
            approval_status=approval_status,
            created_by=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Driver added successfully',
            'driver_id': driver.id
        })
        
    except Exception as e:
        logger.error(f"Error in add_driver: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def edit_driver(request, driver_id):
    """Edit driver details"""
    try:
        driver = get_object_or_404(Driver, id=driver_id)
        
        # Get form data
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        role = request.POST.get('role', '').strip()
        licence_number = request.POST.get('licence_number', '').strip()
        licence_class = request.POST.get('licence_class', '').strip()
        licence_expiry = request.POST.get('licence_expiry', '').strip()
        company_id = request.POST.get('company_id', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        postcode = request.POST.get('postcode', '').strip()
        status = request.POST.get('status', '').strip()
        approval_status = request.POST.get('approval_status', driver.approval_status)
        
        # Validation
        if not first_name:
            return JsonResponse({'success': False, 'error': 'First name is required'}, status=400)
        
        if not last_name:
            return JsonResponse({'success': False, 'error': 'Last name is required'}, status=400)
        
        if not licence_number:
            return JsonResponse({'success': False, 'error': 'Licence number is required'}, status=400)
        
        # Check if licence number exists for other drivers
        if Driver.objects.filter(licence_number=licence_number).exclude(id=driver_id).exists():
            return JsonResponse({'success': False, 'error': 'Licence number already exists'}, status=400)
        
        # Update driver
        driver.first_name = first_name
        driver.last_name = last_name
        driver.email = email if email else None
        driver.phone = phone if phone else None
        driver.role = role if role else None
        driver.licence_number = licence_number
        driver.licence_class = licence_class
        driver.licence_expiry = licence_expiry
        driver.address = address if address else None
        driver.city = city if city else None
        driver.state = state if state else None
        driver.postcode = postcode if postcode else None
        driver.status = status if status else 'active'
        driver.approval_status = approval_status
        
        if company_id:
            driver.company = get_object_or_404(Company, id=company_id)
        
        driver.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Driver updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error in edit_driver: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def approve_driver(request, driver_id):
    """Approve a driver"""
    try:
        driver = get_object_or_404(Driver, id=driver_id)
        driver.approval_status = 'approved'
        driver.approved_at = timezone.now()
        driver.approved_by = request.user
        driver.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Driver approved successfully'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def reject_driver(request, driver_id):
    """Reject a driver"""
    try:
        driver = get_object_or_404(Driver, id=driver_id)
        driver.approval_status = 'rejected'
        driver.rejection_reason = request.POST.get('rejection_reason', '')
        driver.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Driver rejected successfully'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def get_driver_details(request):
    """Get driver details for editing"""
    try:
        data = json.loads(request.body)
        driver_id = data.get('driver_id')
        driver = get_object_or_404(Driver, id=driver_id)
        
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
                'company_id': driver.company.id,
                'company_name': driver.company.company_name,
                'address': driver.address,
                'city': driver.city,
                'state': driver.state,
                'postcode': driver.postcode,
                'status': driver.status,
                'approval_status': driver.approval_status,
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def delete_driver(request, driver_id):
    """Delete driver"""
    try:
        driver = get_object_or_404(Driver, id=driver_id)
        driver.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Driver deleted successfully'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required(login_url='admin_login')
def filter_drivers(request):
    """AJAX endpoint for filtering drivers"""
    search = request.GET.get('search', '')
    company_id = request.GET.get('company', '')
    licence_class = request.GET.get('licence', '')
    
    drivers = Driver.objects.select_related('company').all()
    
    if search:
        drivers = drivers.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(licence_number__icontains=search) |
            Q(email__icontains=search)
        )
    
    if company_id:
        drivers = drivers.filter(company_id=company_id)
    
    if licence_class:
        drivers = drivers.filter(licence_class=licence_class)
    
    drivers_data = []
    for driver in drivers:
        drivers_data.append({
            'id': driver.id,
            'first_name': driver.first_name,
            'last_name': driver.last_name,
            'full_name': driver.full_name,
            'role': driver.role,
            'licence_number': driver.licence_number,
            'licence_class': driver.licence_class,
            'licence_expiry': driver.licence_expiry.strftime('%Y-%m-%d'),
            'status': driver.status,
            'company_name': driver.company.company_name,
        })
    
    return JsonResponse({'success': True, 'drivers': drivers_data})



@login_required(login_url='admin_login')
def vehicles_view(request):
    """Vehicles management page"""
    
    if request.user.user_type != 'admin':
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('dashboard')
    
    # Get all vehicles with company info
    vehicles = Vehicle.objects.select_related('company').all().order_by('-created_at')
    
    # Prepare vehicle data for template
    vehicles_data = []
    for vehicle in vehicles:
        vehicles_data.append({
            'id': vehicle.id,
            'make': vehicle.make,
            'model': vehicle.model,
            'full_name': vehicle.full_name,
            'year': vehicle.year,
            'vin': vehicle.vin,
            'registration_number': vehicle.registration_number,
            'vehicle_type': vehicle.vehicle_type,
            'registration_expiry': vehicle.registration_expiry,
            'status': vehicle.status,
            'approval_status': vehicle.approval_status,
            'company_name': vehicle.company.company_name,
            'company_id': vehicle.company.id,
        })
    
    # Get all companies for filter
    companies = Company.objects.filter(status='approved').values('id', 'company_name')
    
    context = {
        'vehicles': vehicles_data,
        'companies': companies,
        'total_vehicles': len(vehicles_data),
        'current_vehicles': Vehicle.objects.filter(status='current').count(),
        'expired_vehicles': Vehicle.objects.filter(status='expired').count(),
    }
    
    return render(request, 'backend/dashboard/vehicles.html', context)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def approve_vehicle(request, vehicle_id):
    """Approve a vehicle"""
    try:
        vehicle = get_object_or_404(Vehicle, id=vehicle_id)
        vehicle.approval_status = 'approved'
        vehicle.approved_at = timezone.now()
        vehicle.approved_by = request.user
        vehicle.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Vehicle approved successfully'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def reject_vehicle(request, vehicle_id):
    """Reject a vehicle"""
    try:
        vehicle = get_object_or_404(Vehicle, id=vehicle_id)
        vehicle.approval_status = 'rejected'
        vehicle.rejection_reason = request.POST.get('rejection_reason', '')
        vehicle.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Vehicle rejected successfully'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
@login_required(login_url='admin_login')
@require_http_methods(["POST"])
@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def add_vehicle(request):
    """Add a new vehicle"""
    try:
        # Get form data
        make = request.POST.get('make', '').strip()
        model = request.POST.get('model', '').strip()
        year = request.POST.get('year', '').strip()
        vin = request.POST.get('vin', '').strip().upper()
        registration_number = request.POST.get('registration_number', '').strip().upper()
        vehicle_type = request.POST.get('vehicle_type', '').strip()
        registration_expiry = request.POST.get('registration_expiry', '').strip()
        company_id = request.POST.get('company_id', '').strip()
        approval_status = request.POST.get('approval_status', 'pending')
        
        # Debug print
        print("=== ADD VEHICLE DEBUG ===")
        print(f"make: {make}")
        print(f"model: {model}")
        print(f"year: {year}")
        print(f"vin: {vin}")
        print(f"vin length: {len(vin)}")
        print(f"registration_number: {registration_number}")
        print(f"vehicle_type: {vehicle_type}")
        print(f"registration_expiry: {registration_expiry}")
        print(f"company_id: {company_id}")
        
        # Validation
        if not make:
            return JsonResponse({'success': False, 'error': 'Make is required'}, status=400)
        
        if not model:
            return JsonResponse({'success': False, 'error': 'Model is required'}, status=400)
        
        if not year:
            return JsonResponse({'success': False, 'error': 'Year is required'}, status=400)
        
        # Validate year
        try:
            year_int = int(year)
            current_year = timezone.now().year
            if year_int < 1900 or year_int > current_year + 1:
                return JsonResponse({'success': False, 'error': f'Year must be between 1900 and {current_year + 1}'}, status=400)
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Year must be a valid number'}, status=400)
        
        if not vin:
            return JsonResponse({'success': False, 'error': 'VIN is required'}, status=400)
        
        # Validate VIN length (VIN can be 17 characters, but some older vehicles have less)
        if len(vin) < 10 or len(vin) > 17:
            return JsonResponse({'success': False, 'error': 'VIN must be between 10 and 17 characters'}, status=400)
        
        if not registration_number:
            return JsonResponse({'success': False, 'error': 'Registration number is required'}, status=400)
        
        if not registration_expiry:
            return JsonResponse({'success': False, 'error': 'Registration expiry date is required'}, status=400)
        
        if not company_id:
            return JsonResponse({'success': False, 'error': 'Company is required'}, status=400)
        
        # Check if VIN exists (only if VIN is provided)
        if vin and Vehicle.objects.filter(vin=vin).exists():
            return JsonResponse({'success': False, 'error': 'VIN already exists'}, status=400)
        
        # Check if registration number exists
        if Vehicle.objects.filter(registration_number=registration_number).exists():
            return JsonResponse({'success': False, 'error': 'Registration number already exists'}, status=400)
        
        # Get company
        company = get_object_or_404(Company, id=company_id)
        
        # Create vehicle
        vehicle = Vehicle.objects.create(
            make=make,
            model=model,
            year=year_int,
            vin=vin,
            registration_number=registration_number,
            vehicle_type=vehicle_type,
            registration_expiry=registration_expiry,
            company=company,
            status='current',
            approval_status=approval_status,
            created_by=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Vehicle added successfully',
            'vehicle_id': vehicle.id
        })
        
    except Exception as e:
        print(f"Error in add_vehicle: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def edit_vehicle(request, vehicle_id):
    """Edit vehicle details"""
    try:
        vehicle = get_object_or_404(Vehicle, id=vehicle_id)
        
        # Get form data
        make = request.POST.get('make', '').strip()
        model = request.POST.get('model', '').strip()
        year = request.POST.get('year', '').strip()
        vin = request.POST.get('vin', '').strip().upper()
        registration_number = request.POST.get('registration_number', '').strip().upper()
        vehicle_type = request.POST.get('vehicle_type', '').strip()
        registration_expiry = request.POST.get('registration_expiry', '').strip()
        company_id = request.POST.get('company_id', '').strip()
        status = request.POST.get('status', '').strip()
        approval_status = request.POST.get('approval_status', vehicle.approval_status)
        
        # Validation
        if not make:
            return JsonResponse({'success': False, 'error': 'Make is required'}, status=400)
        
        if not model:
            return JsonResponse({'success': False, 'error': 'Model is required'}, status=400)
        
        if not year:
            return JsonResponse({'success': False, 'error': 'Year is required'}, status=400)
        
        # Validate year
        try:
            year_int = int(year)
            current_year = timezone.now().year
            if year_int < 1900 or year_int > current_year + 1:
                return JsonResponse({'success': False, 'error': f'Year must be between 1900 and {current_year + 1}'}, status=400)
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Year must be a valid number'}, status=400)
        
        if not vin:
            return JsonResponse({'success': False, 'error': 'VIN is required'}, status=400)
        
        # Validate VIN length (VIN can be 17 characters, but some older vehicles have less)
        if len(vin) < 10 or len(vin) > 17:
            return JsonResponse({'success': False, 'error': 'VIN must be between 10 and 17 characters'}, status=400)
        
        if not registration_number:
            return JsonResponse({'success': False, 'error': 'Registration number is required'}, status=400)
        
        # Check if VIN exists for other vehicles
        if Vehicle.objects.filter(vin=vin).exclude(id=vehicle_id).exists():
            return JsonResponse({'success': False, 'error': 'VIN already exists'}, status=400)
        
        # Check if registration number exists for other vehicles
        if Vehicle.objects.filter(registration_number=registration_number).exclude(id=vehicle_id).exists():
            return JsonResponse({'success': False, 'error': 'Registration number already exists'}, status=400)
        
        # Update vehicle
        vehicle.make = make
        vehicle.model = model
        vehicle.year = year_int
        vehicle.vin = vin
        vehicle.registration_number = registration_number
        vehicle.vehicle_type = vehicle_type
        vehicle.registration_expiry = registration_expiry
        vehicle.status = status if status else 'current'
        vehicle.approval_status = approval_status
        
        if company_id:
            vehicle.company = get_object_or_404(Company, id=company_id)
        
        vehicle.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Vehicle updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error in edit_vehicle: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def delete_vehicle(request, vehicle_id):
    """Delete vehicle"""
    try:
        vehicle = get_object_or_404(Vehicle, id=vehicle_id)
        vehicle.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Vehicle deleted successfully'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def get_vehicle_details(request):
    """Get vehicle details for editing"""
    try:
        data = json.loads(request.body)
        vehicle_id = data.get('vehicle_id')
        vehicle = get_object_or_404(Vehicle, id=vehicle_id)
        
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
                'company_id': vehicle.company.id,
                'company_name': vehicle.company.company_name,
                'status': vehicle.status,
                'approval_status': vehicle.approval_status,
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
def filter_vehicles(request):
    """AJAX endpoint for filtering vehicles"""
    search = request.GET.get('search', '')
    company_id = request.GET.get('company', '')
    vehicle_type = request.GET.get('type', '')
    
    vehicles = Vehicle.objects.select_related('company').all()
    
    if search:
        vehicles = vehicles.filter(
            Q(registration_number__icontains=search) |
            Q(vin__icontains=search) |
            Q(make__icontains=search) |
            Q(model__icontains=search)
        )
    
    if company_id:
        vehicles = vehicles.filter(company_id=company_id)
    
    if vehicle_type:
        vehicles = vehicles.filter(vehicle_type=vehicle_type)
    
    vehicles_data = []
    for vehicle in vehicles:
        vehicles_data.append({
            'id': vehicle.id,
            'make': vehicle.make,
            'model': vehicle.model,
            'full_name': vehicle.full_name,
            'year': vehicle.year,
            'vin': vehicle.vin,
            'registration_number': vehicle.registration_number,
            'vehicle_type': vehicle.vehicle_type,
            'registration_expiry': vehicle.registration_expiry.strftime('%Y-%m-%d'),
            'status': vehicle.status,
            'approval_status': vehicle.approval_status,
            'company_name': vehicle.company.company_name,
        })
    
    return JsonResponse({'success': True, 'vehicles': vehicles_data})




@login_required(login_url='admin_login')
def admin_services_view(request):
    """Admin services management"""
    if request.user.user_type != 'admin':
        messages.error(request, "Access denied.")
        return redirect('dashboard')
    
    services = Service.objects.all().order_by('order')
    return render(request, 'backend/dashboard/services.html', {'services': services})


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def add_service(request):
    """Add new service via AJAX"""
    try:
        icon = request.POST.get('icon', 'bi-truck')
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        order = request.POST.get('order', 0)
        is_active = request.POST.get('is_active') == 'on'
        
        if not title or not description:
            return JsonResponse({'success': False, 'error': 'Title and description are required'}, status=400)
        
        service = Service.objects.create(
            icon=icon,
            title=title,
            description=description,
            order=int(order),
            is_active=is_active
        )
        
        return JsonResponse({'success': True, 'message': 'Service added successfully', 'service_id': service.id})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def edit_service(request, service_id):
    """Edit service via AJAX"""
    try:
        service = get_object_or_404(Service, id=service_id)
        
        icon = request.POST.get('icon', service.icon)
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        order = request.POST.get('order', service.order)
        is_active = request.POST.get('is_active') == 'on'
        
        if not title or not description:
            return JsonResponse({'success': False, 'error': 'Title and description are required'}, status=400)
        
        service.icon = icon
        service.title = title
        service.description = description
        service.order = int(order)
        service.is_active = is_active
        service.save()
        
        return JsonResponse({'success': True, 'message': 'Service updated successfully'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def delete_service(request, service_id):
    """Delete service via AJAX"""
    try:
        service = get_object_or_404(Service, id=service_id)
        service.delete()
        return JsonResponse({'success': True, 'message': 'Service deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def get_service_details(request):
    """Get service details for editing"""
    try:
        data = json.loads(request.body)
        service_id = data.get('service_id')
        service = get_object_or_404(Service, id=service_id)
        
        return JsonResponse({
            'success': True,
            'service': {
                'id': service.id,
                'icon': service.icon,
                'title': service.title,
                'description': service.description,
                'order': service.order,
                'is_active': service.is_active,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    






# ==============================
# ADMIN PRICING MANAGEMENT VIEWS
# ==============================

@login_required(login_url='admin_login')
def admin_pricing_view(request):
    """Admin pricing management page"""
    if request.user.user_type != 'admin':
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('dashboard')
    
    plans = PricingPlan.objects.all().order_by('order', 'price')
    
    context = {
        'plans': plans,
        'total_plans': plans.count(),
        'active_plans': plans.filter(is_active=True).count(),
    }
    return render(request, 'backend/dashboard/pricing.html', context)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def add_pricing_plan(request):
    """Add a new pricing plan via AJAX"""
    try:
        # Get form data
        name = request.POST.get('name')
        display_name = request.POST.get('display_name')
        description = request.POST.get('description', '')
        price = request.POST.get('price')
        price_period = request.POST.get('price_period', 'month')
        
        # Get features as list (comma separated or array)
        features_str = request.POST.get('features', '')
        features = [f.strip() for f in features_str.split(',') if f.strip()]
        
        disabled_features_str = request.POST.get('disabled_features', '')
        disabled_features = [f.strip() for f in disabled_features_str.split(',') if f.strip()]
        
        is_popular = request.POST.get('is_popular') == 'on'
        is_active = request.POST.get('is_active') == 'on'
        order = request.POST.get('order', 0)
        button_text = request.POST.get('button_text', 'Get Started')
        button_class = request.POST.get('button_class', 'btn-outline-primary')
        
        # Validation
        if not name:
            return JsonResponse({'success': False, 'error': 'Plan name is required'}, status=400)
        
        if not display_name:
            return JsonResponse({'success': False, 'error': 'Display name is required'}, status=400)
        
        if not price:
            return JsonResponse({'success': False, 'error': 'Price is required'}, status=400)

        try:
            price_value = Decimal(price)
            if price_value < 0:
                return JsonResponse({'success': False, 'error': 'Price cannot be negative'}, status=400)
        except (InvalidOperation, TypeError):
            return JsonResponse({'success': False, 'error': 'Price must be a valid number'}, status=400)
        
        # Check if plan name exists
        if PricingPlan.objects.filter(name=name).exists():
            return JsonResponse({'success': False, 'error': 'Plan name already exists'}, status=400)
        
        # Create plan
        plan = PricingPlan.objects.create(
            name=name,
            display_name=display_name,
            description=description,
            price=price_value,
            price_period=price_period,
            features=features,
            disabled_features=disabled_features,
            is_popular=is_popular,
            is_active=is_active,
            order=int(order),
            button_text=button_text,
            button_class=button_class
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Pricing plan added successfully',
            'plan_id': plan.id
        })
        
    except Exception as e:
        logger.error(f"Error in add_pricing_plan: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def edit_pricing_plan(request, plan_id):
    """Edit pricing plan via AJAX"""
    try:
        plan = get_object_or_404(PricingPlan, id=plan_id)
        
        # Get form data
        name = request.POST.get('name')
        display_name = request.POST.get('display_name')
        description = request.POST.get('description', '')
        price = request.POST.get('price')
        price_period = request.POST.get('price_period', 'month')
        
        # Get features as list
        features_str = request.POST.get('features', '')
        features = [f.strip() for f in features_str.split(',') if f.strip()]
        
        disabled_features_str = request.POST.get('disabled_features', '')
        disabled_features = [f.strip() for f in disabled_features_str.split(',') if f.strip()]
        
        is_popular = request.POST.get('is_popular') == 'on'
        is_active = request.POST.get('is_active') == 'on'
        order = request.POST.get('order', 0)
        button_text = request.POST.get('button_text', 'Get Started')
        button_class = request.POST.get('button_class', 'btn-outline-primary')
        
        # Validation
        if not name:
            return JsonResponse({'success': False, 'error': 'Plan name is required'}, status=400)
        
        if not display_name:
            return JsonResponse({'success': False, 'error': 'Display name is required'}, status=400)
        
        if not price:
            return JsonResponse({'success': False, 'error': 'Price is required'}, status=400)

        try:
            price_value = Decimal(price)
            if price_value < 0:
                return JsonResponse({'success': False, 'error': 'Price cannot be negative'}, status=400)
        except (InvalidOperation, TypeError):
            return JsonResponse({'success': False, 'error': 'Price must be a valid number'}, status=400)
        
        # Check if plan name exists for other plans
        if PricingPlan.objects.filter(name=name).exclude(id=plan_id).exists():
            return JsonResponse({'success': False, 'error': 'Plan name already exists'}, status=400)
        
        # Update plan
        plan.name = name
        plan.display_name = display_name
        plan.description = description
        plan.price = price_value
        plan.price_period = price_period
        plan.features = features
        plan.disabled_features = disabled_features
        plan.is_popular = is_popular
        plan.is_active = is_active
        plan.order = int(order)
        plan.button_text = button_text
        plan.button_class = button_class
        plan.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Pricing plan updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error in edit_pricing_plan: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def delete_pricing_plan(request, plan_id):
    """Delete pricing plan"""
    try:
        plan = get_object_or_404(PricingPlan, id=plan_id)
        
        # Check if any subscriptions use this plan
        if CompanySubscription.objects.filter(plan=plan).exists():
            return JsonResponse({
                'success': False, 
                'error': 'Cannot delete plan that has active subscriptions'
            }, status=400)
        
        plan.delete()
        return JsonResponse({'success': True, 'message': 'Plan deleted successfully'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def get_pricing_plan_details(request):
    """Get pricing plan details for editing"""
    try:
        data = json.loads(request.body)
        plan_id = data.get('plan_id')
        plan = get_object_or_404(PricingPlan, id=plan_id)
        
        return JsonResponse({
            'success': True,
            'plan': {
                'id': plan.id,
                'name': plan.name,
                'display_name': plan.display_name,
                'description': plan.description,
                'price': str(plan.price),
                'price_period': plan.price_period,
                'features': plan.features,
                'disabled_features': plan.disabled_features,
                'is_popular': plan.is_popular,
                'is_active': plan.is_active,
                'order': plan.order,
                'button_text': plan.button_text,
                'button_class': plan.button_class,
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    


@login_required(login_url='admin_login')
@login_required(login_url='admin_login')
def admin_why_us_view(request):
    """Admin Why Us management page"""
    if request.user.user_type != 'admin':
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('dashboard')
    
    # Fetch the latest data from database
    why_us = WhyUs.objects.first()
    features = WhyUsFeature.objects.all().order_by('order')
    
    # If no WhyUs exists, create one with defaults
    if not why_us:
        why_us = WhyUs.objects.create()
    
    context = {
        'why_us': why_us,
        'features': features,
    }
    return render(request, 'backend/dashboard/whyus.html', context)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def update_why_us(request):
    """Update Why Us section"""
    try:
        print("="*50)
        print("UPDATE WHY US CALLED")
        print("="*50)
        print("POST data:", request.POST)
        
        why_us = WhyUs.objects.first()
        if not why_us:
            why_us = WhyUs.objects.create()
        
        why_us.eyebrow = request.POST.get('eyebrow', 'Why PRODRIVE')
        why_us.title = request.POST.get('title', 'Built for the Road Ahead')
        why_us.description = request.POST.get('description', '')
        why_us.video_url = request.POST.get('video_url', 'Cm6eMeOg-KU')
        why_us.is_active = request.POST.get('is_active') == 'on'
        why_us.save()
        
        print(f"Saved - Eyebrow: {why_us.eyebrow}")
        print(f"Saved - Title: {why_us.title}")
        print(f"Saved - Description: {why_us.description[:50]}...")
        
        return JsonResponse({'success': True, 'message': 'Why Us section updated successfully!'})
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def add_feature(request):
    """Add a new feature"""
    try:
        why_us = WhyUs.objects.first()
        if not why_us:
            why_us = WhyUs.objects.create()
        
        text = request.POST.get('text', '').strip()
        icon = request.POST.get('icon', 'bi-check-circle-fill')
        order = request.POST.get('order', 0)
        
        if not text:
            return JsonResponse({'success': False, 'error': 'Feature text is required'}, status=400)
        
        feature = WhyUsFeature.objects.create(
            why_us=why_us,
            text=text,
            icon=icon,
            order=int(order),
            is_active=True
        )
        
        return JsonResponse({'success': True, 'message': 'Feature added successfully', 'feature_id': feature.id})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def edit_feature(request, feature_id):
    """Edit a feature"""
    try:
        feature = get_object_or_404(WhyUsFeature, id=feature_id)
        
        feature.text = request.POST.get('text', '').strip()
        feature.icon = request.POST.get('icon', 'bi-check-circle-fill')
        feature.order = int(request.POST.get('order', 0))
        feature.is_active = request.POST.get('is_active') == 'on'
        feature.save()
        
        return JsonResponse({'success': True, 'message': 'Feature updated successfully'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def delete_feature(request, feature_id):
    """Delete a feature"""
    try:
        feature = get_object_or_404(WhyUsFeature, id=feature_id)
        feature.delete()
        return JsonResponse({'success': True, 'message': 'Feature deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def get_feature_details(request):
    """Get feature details for editing"""
    try:
        data = json.loads(request.body)
        feature_id = data.get('feature_id')
        feature = get_object_or_404(WhyUsFeature, id=feature_id)
        
        return JsonResponse({
            'success': True,
            'feature': {
                'id': feature.id,
                'text': feature.text,
                'icon': feature.icon,
                'order': feature.order,
                'is_active': feature.is_active,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    
@login_required(login_url='admin_login')
def company_documents_admin(request):
    documents = CompanyDocument.objects.select_related("company").all()

    return render(request, "backend/dashboard/company_documents.html", {
        "documents": documents
    })
    


@login_required(login_url='admin_login')
def rename_document(request, doc_id):
    if request.method == "POST":
        doc = CompanyDocument.objects.get(id=doc_id)
        data = json.loads(request.body)

        new_name = data.get("name", "").strip()

        if not new_name:
            return JsonResponse({
                "status": "error",
                "message": "Name cannot be empty"
            }, status=400)

        # ✅ ALWAYS keep original extension
        ext = os.path.splitext(doc.file.name)[1]

        # ✅ Ensure extension is not duplicated or removed
        full_name = new_name + ext if not new_name.endswith(ext) else new_name

        # ✅ DUPLICATE CHECK (same company)
        if CompanyDocument.objects.filter(
            company=doc.company,
            name=full_name
        ).exclude(id=doc.id).exists():
            return JsonResponse({
                "status": "error",
                "message": "A document with this name already exists"
            }, status=400)

        # ✅ SAVE
        doc.name = full_name
        doc.save(update_fields=["name"])

        return JsonResponse({
            "status": "success",
            "message": "Document renamed successfully",
            "new_name": doc.name,
            "base_name": full_name.replace(ext, "")
        })
        
        
@login_required(login_url='admin_login')
def delete_document(request, doc_id):
    if request.method == "POST":
        doc = CompanyDocument.objects.get(id=doc_id)

        doc.file.delete(save=False)
        doc.delete()

        return JsonResponse({
            "status": "success",
            "message": "Document deleted successfully"
        })



# Admin views for managing contact messages
@login_required(login_url='admin_login')
def admin_contact_messages(request):
    """View all contact messages in admin panel"""
    if request.user.user_type != 'admin':
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('dashboard')
    
    # Fetch all messages
    messages_list = ContactMessage.objects.all().order_by('-created_at')
    
    # Debug: print to console
    print(f"Total messages found: {messages_list.count()}")
    for msg in messages_list:
        print(f"Message: {msg.name} - {msg.email} - {msg.created_at}")
    
    # Get counts for stats
    total_messages = messages_list.count()
    new_messages = messages_list.filter(status='new').count()
    read_messages = messages_list.filter(status='read').count()
    replied_messages = messages_list.filter(status='replied').count()
    
    context = {
        'messages': messages_list,
        'total_messages': total_messages,
        'new_messages': new_messages,
        'read_messages': read_messages,
        'replied_messages': replied_messages,
    }
    
    return render(request, 'backend/dashboard/messages.html', context)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def update_message_status(request, message_id):
    """Update message status"""
    try:
        message = get_object_or_404(ContactMessage, id=message_id)
        status = request.POST.get('status')
        
        if status in ['new', 'read', 'replied', 'archived']:
            message.status = status
            message.save()
            return JsonResponse({'success': True, 'message': 'Status updated'})
        
        return JsonResponse({'success': False, 'error': 'Invalid status'}, status=400)
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
def get_message_detail(request, message_id):
    """Get message details for viewing"""
    try:
        message = get_object_or_404(ContactMessage, id=message_id)
        
        # Mark as read if viewing
        if message.status == 'new':
            message.status = 'read'
            message.save()
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': message.id,
                'name': message.name,
                'email': message.email,
                'message': message.message,
                'status': message.status,
                'ip_address': message.ip_address,
                'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def delete_message(request, message_id):
    """Delete a message"""
    try:
        message = get_object_or_404(ContactMessage, id=message_id)
        message.delete()
        return JsonResponse({'success': True, 'message': 'Message deleted'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# Admin Footer Settings
@login_required(login_url='admin_login')
def admin_footer_settings(request):
    """Footer settings management"""
    if request.user.user_type != 'admin':
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('dashboard')
    
    footer = FooterSettings.objects.first()
    if not footer:
        footer = FooterSettings.objects.create()
    
    context = {'footer': footer}
    return render(request, 'backend/footer/settings.html', context)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def update_footer_settings(request):
    """Update footer settings"""
    try:
        footer = FooterSettings.objects.first()
        if not footer:
            footer = FooterSettings.objects.create()
        
        footer.email = request.POST.get('email', 'info@prodrivecompliance.com')
        footer.phone = request.POST.get('phone', '+61 4XX XXX XXX')
        footer.address = request.POST.get('address', 'Sydney, Australia')
        footer.facebook_url = request.POST.get('facebook_url', '')
        footer.linkedin_url = request.POST.get('linkedin_url', '')
        footer.instagram_url = request.POST.get('instagram_url', '')
        footer.twitter_url = request.POST.get('twitter_url', '')
        footer.tagline = request.POST.get('tagline', '')
        footer.copyright_text = request.POST.get('copyright_text', '')
        footer.is_active = request.POST.get('is_active') == 'on'
        
        # Handle compliance logos (comma separated)
        compliance_logos = request.POST.get('compliance_logos', '')
        footer.compliance_logos = [logo.strip() for logo in compliance_logos.split(',') if logo.strip()]
        
        # Handle membership logos
        membership_logos = request.POST.get('membership_logos', '')
        footer.membership_logos = [logo.strip() for logo in membership_logos.split(',') if logo.strip()]
        
        footer.save()
        
        messages.success(request, "Footer settings updated successfully!")
        return redirect('admin_footer_settings')
        
    except Exception as e:
        messages.error(request, f"Error: {str(e)}")
        return redirect('admin_footer_settings')

# sms_builder/views.py


@login_required(login_url='admin_login')
def admin_settings(request):
    """Admin settings page"""
    if request.user.user_type != 'admin':
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('dashboard')
    
    # Get or create system settings
    system_settings, created = SystemSettings.objects.get_or_create(id=1)
    
    # Get or create admin profile
    admin_profile, created = AdminProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'Super Administrator',
            'phone': request.user.phone or '+61 4XX XXX XXX',
            'location': 'Sydney, NSW'
        }
    )
    
    context = {
        'system_settings': system_settings,
        'admin_profile': admin_profile,
        'admin_user': request.user,
    }
    
    return render(request, 'backend/dashboard/settings.html', context)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def update_admin_profile(request):
    """Update admin profile via AJAX"""
    try:
        data = json.loads(request.body)
        
        admin_profile = AdminProfile.objects.get(user=request.user)
        admin_profile.role = data.get('role', admin_profile.role)
        admin_profile.phone = data.get('phone', admin_profile.phone)
        admin_profile.location = data.get('location', admin_profile.location)
        admin_profile.save()
        
        # Update user model
        user = request.user
        user.full_name = data.get('full_name', user.full_name)
        user.save()
        
        return JsonResponse({'success': True, 'message': 'Profile updated successfully'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def update_system_settings(request):
    """Update system settings including hero section"""
    try:
        data = json.loads(request.body)
        print("Received data:", data)  # Debug print
        
        system_settings = SystemSettings.objects.get(id=1)
        
        # Update Hero Section Settings
        system_settings.hero_badge = data.get('hero_badge', system_settings.hero_badge)
        system_settings.hero_title = data.get('hero_title', system_settings.hero_title)
        system_settings.hero_description = data.get('hero_description', system_settings.hero_description)
        system_settings.hero_button_text = data.get('hero_button_text', system_settings.hero_button_text)
        system_settings.hero_button_link = data.get('hero_button_link', system_settings.hero_button_link)
        system_settings.hero_video_url = data.get('hero_video_url', system_settings.hero_video_url)
        
        # Update Trust Items
        system_settings.trust_item_1 = data.get('trust_item_1', system_settings.trust_item_1)
        system_settings.trust_item_2 = data.get('trust_item_2', system_settings.trust_item_2)
        system_settings.trust_item_3 = data.get('trust_item_3', system_settings.trust_item_3)
        
        # Update Carousel Images
        carousel_images = data.get('carousel_images', [])
        if carousel_images:
            system_settings.carousel_images = carousel_images
        else:
            system_settings.carousel_images = []
        
        # Update Notification Settings
        system_settings.email_notifications = data.get('email_notifications', system_settings.email_notifications)
        system_settings.new_registration_alerts = data.get('new_registration_alerts', system_settings.new_registration_alerts)
        system_settings.incident_notifications = data.get('incident_notifications', system_settings.incident_notifications)
        system_settings.compliance_reminders = data.get('compliance_reminders', system_settings.compliance_reminders)
        system_settings.maintenance_mode = data.get('maintenance_mode', system_settings.maintenance_mode)
        
        system_settings.save()
        
        print("Settings saved successfully!")  # Debug print
        print(f"Carousel images: {system_settings.carousel_images}")  # Debug print
        
        return JsonResponse({'success': True, 'message': 'Settings updated successfully'})
        
    except Exception as e:
        print(f"Error: {str(e)}")  # Debug print
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def update_password(request):
    """Update admin password"""
    try:
        data = json.loads(request.body)
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        user = request.user
        
        # Check current password
        if not user.check_password(current_password):
            return JsonResponse({'success': False, 'error': 'Current password is incorrect'}, status=400)
        
        # Check new password length
        if len(new_password) < 8:
            return JsonResponse({'success': False, 'error': 'Password must be at least 8 characters'}, status=400)
        
        # Check password match
        if new_password != confirm_password:
            return JsonResponse({'success': False, 'error': 'Passwords do not match'}, status=400)
        
        # Update password
        user.set_password(new_password)
        user.save()
        
        return JsonResponse({'success': True, 'message': 'Password updated successfully'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    


def upload_carousel_image(request):
    """Upload carousel image"""
    try:
        if request.user.user_type != 'admin':
            return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
        
        image = request.FILES.get('image')
        if not image:
            return JsonResponse({'success': False, 'error': 'No image provided'}, status=400)
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        if image.content_type not in allowed_types:
            return JsonResponse({'success': False, 'error': 'Invalid file type. Only JPG, PNG, GIF, WEBP allowed.'}, status=400)
        
        # Validate file size (max 5MB)
        if image.size > 5 * 1024 * 1024:
            return JsonResponse({'success': False, 'error': 'File too large. Max 5MB.'}, status=400)
        
        # Save file
        file_path = default_storage.save(f'carousel/{image.name}', ContentFile(image.read()))
        file_url = default_storage.url(file_path)
        
        return JsonResponse({'success': True, 'image_url': file_url})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def remove_carousel_image(request):
    """Remove carousel image"""
    try:
        if request.user.user_type != 'admin':
            return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
        
        data = json.loads(request.body)
        image_url = data.get('image_url')
        
        if not image_url:
            return JsonResponse({'success': False, 'error': 'No image URL provided'}, status=400)
        
        # Extract relative path from URL
        relative_path = image_url.replace(settings.MEDIA_URL, '')
        
        # Delete file if exists
        if default_storage.exists(relative_path):
            default_storage.delete(relative_path)
        
        return JsonResponse({'success': True, 'message': 'Image removed successfully'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    


@login_required(login_url='admin_login')
@login_required(login_url='admin_login')
def analytics_view(request):
    """Analytics dashboard with dynamic data"""
    
    if request.user.user_type != 'admin':
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('dashboard')
    
    # Get current month and previous month data
    now = timezone.now()
    current_month = now.month
    current_year = now.year
    last_month = now - timedelta(days=30)
    
    # Calculate MoM Revenue Growth
    current_month_revenue = CompanySubscription.objects.filter(
        status='active',
        start_date__month=current_month,
        start_date__year=current_year
    ).aggregate(total=Sum('amount_paid'))['total'] or 0
    
    last_month_revenue = CompanySubscription.objects.filter(
        status='active',
        start_date__gte=last_month,
        start_date__lt=now
    ).aggregate(total=Sum('amount_paid'))['total'] or 0
    
    if last_month_revenue > 0:
        mom_growth = round(((current_month_revenue - last_month_revenue) / last_month_revenue) * 100)
    else:
        mom_growth = 18
    
    # Get signups by month for the last 6 months
    months = []
    signups_data = []
    
    for i in range(5, -1, -1):
        month_date = now - timedelta(days=30 * i)
        month_name = month_date.strftime('%b')
        month_count = Company.objects.filter(
            registration_date__month=month_date.month,
            registration_date__year=month_date.year
        ).count()
        months.append(month_name)
        signups_data.append(month_count)
    
    # Get compliance scores for companies
    companies = Company.objects.select_related('user').all()
    compliance_scores = []
    
    for company in companies:
        drivers_count = company.drivers.count()
        vehicles_count = company.vehicles.count()
        
        if drivers_count > 0 and vehicles_count > 0:
            score = min(95, 60 + (drivers_count * 2) + (vehicles_count))
        else:
            score = 45
        
        compliance_scores.append({
            'company_name': company.company_name,
            'score': score,
            'status': 'green' if score >= 80 else ('amber' if score >= 60 else 'red')
        })
    
    compliance_scores.sort(key=lambda x: x['score'], reverse=True)
    
    # Calculate average compliance score
    if compliance_scores:
        avg_compliance = round(sum(c['score'] for c in compliance_scores) / len(compliance_scores))
    else:
        avg_compliance = 96
    
    avg_onboarding_time = 4.2
    
    total_companies = Company.objects.count()
    active_companies = Company.objects.filter(status='approved').count()
    if total_companies > 0:
        retention_rate = round((active_companies / total_companies) * 100)
    else:
        retention_rate = 89
    
    # Calculate max signup for chart scaling
    max_signups = max(signups_data) if signups_data else 1
    
    context = {
        'mom_growth': mom_growth,
        'avg_onboarding_time': avg_onboarding_time,
        'avg_compliance': avg_compliance,
        'retention_rate': retention_rate,
        'months': months,
        'signups_data': signups_data,
        'compliance_scores': compliance_scores,
        'max_signups': max_signups,
    }
    
    return render(request, 'backend/dashboard/analytics.html', context)

@login_required(login_url='admin_login')
def subscription_history_view(request):
    """View all subscription history with pending requests"""
    if request.user.user_type != 'admin':
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('dashboard')
    
    # Get all history with related data
    history = SubscriptionHistory.objects.select_related(
        'subscription', 
        'subscription__company',
        'old_plan', 
        'new_plan',
        'changed_by'
    ).all()
    
    # Apply filters
    action_filter = request.GET.get('action', '')
    company_filter = request.GET.get('company', '')
    
    if action_filter:
        history = history.filter(action=action_filter)
    
    if company_filter:
        history = history.filter(subscription__company__company_name__icontains=company_filter)
    
    # Get pending change requests - include both pending_change and pending status
    pending_requests = CompanySubscription.objects.filter(
        status__in=['pending_change', 'pending']
    ).select_related('company', 'plan').order_by('-updated_at')
    
    # Pagination
    paginator = Paginator(history, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get statistics
    total_actions = history.count()
    
    # Group by action type
    action_counts = {}
    for action_code, action_name in SubscriptionHistory.ACTION_CHOICES:
        action_counts[action_code] = SubscriptionHistory.objects.filter(action=action_code).count()
    
    # Add pending count
    pending_count = pending_requests.count()
    
    context = {
        'history': page_obj,
        'total_actions': total_actions,
        'action_counts': action_counts,
        'pending_requests': pending_requests,
        'pending_count': pending_count,
        'current_action': action_filter,
        'current_company': company_filter,
    }
    
    return render(request, 'backend/dashboard/history.html', context)


@login_required(login_url='admin_login')
def approve_plan_change(request, subscription_id):
    """Admin approve a pending plan change request"""
    if request.user.user_type != 'admin':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Unauthorized'})
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('dashboard')
    
    try:
        subscription = CompanySubscription.objects.get(
            id=subscription_id
        )
    except CompanySubscription.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Subscription not found'})
        messages.error(request, 'Subscription not found')
        return redirect('subscription_history')
    
    # Check if already active
    if subscription.status == 'active':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True, 
                'message': f'Subscription is already active for {subscription.company.company_name}'
            })
        messages.info(request, f'Subscription is already active for {subscription.company.company_name}')
        return redirect('subscription_history')
    
    # Check if not pending_change
    if subscription.status not in ['pending_change', 'pending']:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False, 
                'error': f'Cannot approve subscription with status: {subscription.status}'
            })
        messages.error(request, f'Cannot approve subscription with status: {subscription.status}')
        return redirect('subscription_history')
    
    # Get the original plan from change request history
    last_request = SubscriptionHistory.objects.filter(
        subscription=subscription,
        action='change_requested'
    ).order_by('-changed_at').first()
    
    old_plan = None
    if last_request:
        old_plan = last_request.old_plan
    elif subscription.plan:
        # Try to get from company's current plan
        old_plan_name = subscription.company.subscription_plan
        if old_plan_name:
            old_plan = PricingPlan.objects.filter(name=old_plan_name).first()
    
    # Determine change type
    is_same_plan = False
    is_upgrade = False
    is_downgrade = False
    
    if old_plan and subscription.plan:
        if old_plan.name == subscription.plan.name:
            is_same_plan = True
        elif subscription.plan.price > old_plan.price:
            is_upgrade = True
        else:
            is_downgrade = True
    
    # Activate the subscription
    subscription.status = 'active'
    
    # Only update dates if not already set or if it's a real change
    if not subscription.start_date or not is_same_plan:
        subscription.start_date = timezone.now()
    
    # Set end date based on plan period
    if subscription.plan:
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
    company.subscription_plan = subscription.plan.name if subscription.plan else None
    company.subscription_status = 'active'
    company.subscription_end_date = subscription.end_date
    company.save()
    
    # Create history record based on change type
    if is_same_plan:
        action_type = 'renewed'
        notes = f'Plan renewal approved by admin {request.user.email}. User renewed {subscription.plan.display_name} plan.'
    elif is_upgrade:
        action_type = 'upgraded'
        notes = f'Plan upgrade approved by admin {request.user.email}. From {old_plan.display_name if old_plan else "None"} to {subscription.plan.display_name}'
    elif is_downgrade:
        action_type = 'downgraded'
        notes = f'Plan downgrade approved by admin {request.user.email}. From {old_plan.display_name if old_plan else "None"} to {subscription.plan.display_name}'
    else:
        action_type = 'created'
        notes = f'New subscription approved by admin {request.user.email}. Plan: {subscription.plan.display_name}'
    
    SubscriptionHistory.objects.create(
        subscription=subscription,
        old_plan=old_plan,
        new_plan=subscription.plan,
        action=action_type,
        notes=notes,
        changed_by=request.user
    )
    
    # Update the original change request record
    if last_request:
        last_request.notes = f"{last_request.notes} - APPROVED by {request.user.email} on {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
        last_request.save()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True, 
            'message': f'Plan {action_type} approved for {company.company_name}',
            'action': action_type
        })
    
    messages.success(request, f'Plan {action_type} approved for {company.company_name}')
    return redirect('subscription_history')


@login_required(login_url='admin_login')
def reject_plan_change(request, subscription_id):
    """Admin reject a pending plan change request"""
    if request.user.user_type != 'admin':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Unauthorized'})
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('dashboard')
    
    try:
        subscription = CompanySubscription.objects.get(
            id=subscription_id
        )
    except CompanySubscription.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Subscription not found'})
        messages.error(request, 'Subscription not found')
        return redirect('subscription_history')
    
    # Check if already active
    if subscription.status == 'active':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False, 
                'error': 'Cannot reject an already active subscription'
            })
        messages.error(request, 'Cannot reject an already active subscription')
        return redirect('subscription_history')
    
    # Check if not pending_change
    if subscription.status not in ['pending_change', 'pending']:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False, 
                'error': f'Cannot reject subscription with status: {subscription.status}'
            })
        messages.error(request, f'Cannot reject subscription with status: {subscription.status}')
        return redirect('subscription_history')
    
    # Get the requested plan
    requested_plan = subscription.plan
    
    # Get the original plan from change request
    last_request = SubscriptionHistory.objects.filter(
        subscription=subscription,
        action='change_requested'
    ).order_by('-changed_at').first()
    
    # Get the last successful plan change
    last_successful = SubscriptionHistory.objects.filter(
        subscription=subscription,
        action__in=['upgraded', 'downgraded', 'created', 'renewed']
    ).order_by('-changed_at').first()
    
    # Determine what to revert to
    reverted_plan = None
    
    if last_request and last_request.old_plan:
        # Revert to the plan before the request
        subscription.plan = last_request.old_plan
        subscription.status = 'active' if last_request.old_plan else 'expired'
        reverted_plan = last_request.old_plan
    elif last_successful and last_successful.new_plan:
        # Revert to the last successful plan
        subscription.plan = last_successful.new_plan
        subscription.status = 'active'
        reverted_plan = last_successful.new_plan
    else:
        # No previous plan, check company's current plan
        old_plan_name = subscription.company.subscription_plan
        if old_plan_name:
            existing_plan = PricingPlan.objects.filter(name=old_plan_name).first()
            if existing_plan:
                subscription.plan = existing_plan
                subscription.status = 'active'
                reverted_plan = existing_plan
            else:
                subscription.status = 'expired'
                subscription.plan = None
        else:
            subscription.status = 'expired'
            subscription.plan = None
    
    subscription.save()
    
    # Update company
    company = subscription.company
    company.subscription_status = subscription.status
    company.subscription_plan = subscription.plan.name if subscription.plan else None
    
    if subscription.plan and subscription.status == 'active':
        if not company.subscription_end_date:
            if subscription.plan.price_period == 'month':
                company.subscription_end_date = timezone.now() + timezone.timedelta(days=30)
            elif subscription.plan.price_period == 'year':
                company.subscription_end_date = timezone.now() + timezone.timedelta(days=365)
    company.save()
    
    # Create history record for rejection
    rejection_notes = f'Plan change request rejected by admin {request.user.email}. '
    rejection_notes += f'User requested: {requested_plan.display_name if requested_plan else "None"}. '
    
    if reverted_plan:
        rejection_notes += f'Reverted to: {reverted_plan.display_name}.'
    else:
        rejection_notes += 'Subscription set to expired.'
    
    SubscriptionHistory.objects.create(
        subscription=subscription,
        old_plan=requested_plan,
        new_plan=subscription.plan,
        action='change_rejected',
        notes=rejection_notes,
        changed_by=request.user
    )
    
    # Update the original change request record
    if last_request:
        last_request.notes = f"{last_request.notes} - REJECTED by {request.user.email} on {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
        last_request.save()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True, 
            'message': f'Plan change rejected for {company.company_name}. Reverted to {subscription.plan.display_name if subscription.plan else "no plan"}.'
        })
    
    messages.warning(request, f'Plan change rejected for {company.company_name}')
    return redirect('subscription_history')


@login_required(login_url='admin_login')
def get_pending_requests_api(request):
    """API endpoint to get pending requests (for AJAX polling)"""
    if request.user.user_type != 'admin':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    pending_requests = CompanySubscription.objects.filter(
        status__in=['pending_change', 'pending']
    ).select_related('company', 'plan').order_by('-updated_at')
    
    data = []
    for req in pending_requests:
        # Get the original plan from history
        last_request = SubscriptionHistory.objects.filter(
            subscription=req,
            action='change_requested'
        ).order_by('-changed_at').first()
        
        current_plan = req.company.subscription_plan or 'None'
        requested_plan = req.plan.display_name if req.plan else 'None'
        
        # Determine request type
        request_type = 'new'
        if current_plan != 'None' and requested_plan != 'None':
            if current_plan == requested_plan:
                request_type = 'renewal'
            elif req.plan and req.company.subscription_plan:
                current_plan_obj = PricingPlan.objects.filter(name=current_plan).first()
                if current_plan_obj and req.plan.price > current_plan_obj.price:
                    request_type = 'upgrade'
                elif current_plan_obj and req.plan.price < current_plan_obj.price:
                    request_type = 'downgrade'
        
        data.append({
            'id': req.id,
            'company_name': req.company.company_name,
            'current_plan': current_plan,
            'requested_plan': requested_plan,
            'requested_at': req.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            'request_type': request_type,
            'price': float(req.plan.price) if req.plan else 0,
            'price_period': req.plan.price_period if req.plan else 'month',
        })
    
    return JsonResponse({
        'pending_count': len(data), 
        'requests': data
    })

@login_required(login_url='admin_login')
def adjust_expiry_date(request, subscription_id):
    """Adjust subscription expiry date by days"""
    if request.user.user_type != 'admin':
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    try:
        data = json.loads(request.body)
        days = data.get('days', 0)
        reason = data.get('reason', '')
        
        subscription = CompanySubscription.objects.get(id=subscription_id)
        company = subscription.company
        
        old_expiry = subscription.end_date
        
        if days > 0:
            subscription.end_date = timezone.now() + timezone.timedelta(days=days)
        else:
            subscription.end_date += timezone.timedelta(days=days)
        
        subscription.next_renewal_date = subscription.end_date
        subscription.save()
        
        # Update company
        company.subscription_end_date = subscription.end_date
        company.save()
        
        # Create history record
        SubscriptionHistory.objects.create(
            subscription=subscription,
            action='renewed',
            notes=f'Expiry date adjusted by {abs(days)} days {"increased" if days > 0 else "decreased"} by admin {request.user.email}. Reason: {reason}',
            changed_by=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Expiry date adjusted by {abs(days)} days. New expiry: {subscription.end_date.strftime("%Y-%m-%d")}',
            'new_expiry': subscription.end_date.strftime('%Y-%m-%d')
        })
        
    except CompanySubscription.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Subscription not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
def update_expiry_date(request, subscription_id):
    """Update subscription expiry date to a specific date"""
    if request.user.user_type != 'admin':
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    try:
        data = json.loads(request.body)
        new_expiry_date = data.get('new_expiry_date')
        reason = data.get('reason', '')
        
        if not new_expiry_date:
            return JsonResponse({'success': False, 'error': 'New expiry date is required'}, status=400)
        
        subscription = CompanySubscription.objects.get(id=subscription_id)
        company = subscription.company
        
        old_expiry = subscription.end_date
        new_expiry = datetime.strptime(new_expiry_date, '%Y-%m-%d').date()
        
        subscription.end_date = timezone.make_aware(datetime.combine(new_expiry, datetime.min.time()))
        subscription.next_renewal_date = subscription.end_date
        subscription.save()
        
        # Update company
        company.subscription_end_date = subscription.end_date
        company.save()
        
        # Create history record
        SubscriptionHistory.objects.create(
            subscription=subscription,
            action='renewed',
            notes=f'Expiry date updated from {old_expiry.strftime("%Y-%m-%d") if old_expiry else "None"} to {new_expiry_date} by admin {request.user.email}. Reason: {reason}',
            changed_by=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Expiry date updated to {new_expiry_date}',
            'new_expiry': new_expiry_date
        })
        
    except CompanySubscription.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Subscription not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
def bulk_extend_expiry(request):
    """Bulk extend expiry dates for multiple subscriptions"""
    if request.user.user_type != 'admin':
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    try:
        data = json.loads(request.body)
        subscription_ids = data.get('subscription_ids', [])
        days = data.get('days', 30)
        reason = data.get('reason', '')
        
        if not subscription_ids:
            return JsonResponse({'success': False, 'error': 'No subscriptions selected'}, status=400)
        
        updated_count = 0
        for sub_id in subscription_ids:
            try:
                subscription = CompanySubscription.objects.get(id=sub_id)
                subscription.end_date += timezone.timedelta(days=days)
                subscription.next_renewal_date = subscription.end_date
                subscription.save()
                
                # Update company
                subscription.company.subscription_end_date = subscription.end_date
                subscription.company.save()
                
                # Create history record
                SubscriptionHistory.objects.create(
                    subscription=subscription,
                    action='renewed',
                    notes=f'Bulk expiry extension: +{days} days by admin {request.user.email}. Reason: {reason}',
                    changed_by=request.user
                )
                updated_count += 1
            except:
                continue
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully extended {updated_count} subscriptions by {days} days'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
@login_required(login_url='admin_login')
def get_subscription_history_api(request, subscription_id):
    """Get subscription history for a specific subscription (AJAX)"""
    try:
        history = SubscriptionHistory.objects.filter(
            subscription_id=subscription_id
        ).select_related('old_plan', 'new_plan', 'changed_by').order_by('-changed_at')
        
        history_data = []
        for record in history:
            history_data.append({
                'id': record.id,
                'action': record.action,
                'action_display': record.get_action_display(),
                'old_plan': record.old_plan.display_name if record.old_plan else None,
                'new_plan': record.new_plan.display_name if record.new_plan else None,
                'notes': record.notes,
                'changed_by': record.changed_by.email if record.changed_by else 'System',
                'changed_at': record.changed_at.strftime('%Y-%m-%d %H:%M:%S'),
                'changed_at_formatted': record.changed_at.strftime('%b %d, %Y %I:%M %p'),
            })
        
        return JsonResponse({'success': True, 'history': history_data})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
def export_subscription_history(request):
    """Export subscription history as CSV"""
    if request.user.user_type != 'admin':
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('dashboard')
    
    import csv
    from django.http import HttpResponse
    from datetime import datetime
    
    response = HttpResponse(content_type='text/csv')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = f'attachment; filename="subscription_history_{timestamp}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Date', 'Company', 'Action', 'Old Plan', 'New Plan', 'Changed By', 'Notes'])
    
    history = SubscriptionHistory.objects.select_related(
        'subscription__company', 'old_plan', 'new_plan', 'changed_by'
    ).order_by('-changed_at')
    
    for record in history:
        writer.writerow([
            record.changed_at.strftime('%Y-%m-%d %H:%M:%S'),
            record.subscription.company.company_name,
            record.get_action_display(),
            record.old_plan.display_name if record.old_plan else '-',
            record.new_plan.display_name if record.new_plan else '-',
            record.changed_by.email if record.changed_by else 'System',
            record.notes or '-',
        ])
    
    return response




@login_required(login_url='admin_login')
def incidents_view(request):
    """Incidents management page"""
    if request.user.user_type != 'admin':
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('dashboard')
    
    # Get all incidents with company info
    incidents = IncidentRecord.objects.select_related('company').all().order_by('-incident_date')
    
    # Get filter parameters
    incident_type_filter = request.GET.get('type', '')
    company_filter = request.GET.get('company', '')
    search_query = request.GET.get('search', '')
    
    # Apply filters
    if incident_type_filter:
        incidents = incidents.filter(incident_type=incident_type_filter)
    if company_filter:
        incidents = incidents.filter(company_id=company_filter)
    if search_query:
        incidents = incidents.filter(
            Q(description__icontains=search_query) |
            Q(incident_type__icontains=search_query) |
            Q(company__company_name__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(incidents, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get statistics
    total_incidents = IncidentRecord.objects.count()
    
    # Get unique companies for filter
    companies = Company.objects.filter(status='approved').values('id', 'company_name')
    
    context = {
        'incidents': page_obj,
        'total_incidents': total_incidents,
        'companies': companies,
    }
    
    return render(request, 'backend/dashboard/incidents.html', context)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def add_incident(request):
    """Add a new incident"""
    try:
        data = json.loads(request.body)
        
        incident = IncidentRecord.objects.create(
            company_id=data.get('company_id'),
            incident_type=data.get('incident_type'),
            description=data.get('description'),
            incident_date=data.get('incident_date'),
            outcome=data.get('outcome', ''),
        )
        
        return JsonResponse({'success': True, 'message': 'Incident added successfully', 'incident_id': incident.id})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def edit_incident(request, incident_id):
    """Edit incident details"""
    try:
        incident = get_object_or_404(IncidentRecord, id=incident_id)
        data = json.loads(request.body)
        
        incident.incident_type = data.get('incident_type', incident.incident_type)
        incident.description = data.get('description', incident.description)
        incident.incident_date = data.get('incident_date', incident.incident_date)
        incident.outcome = data.get('outcome', incident.outcome)
        
        if data.get('company_id'):
            incident.company_id = data.get('company_id')
        
        incident.save()
        
        return JsonResponse({'success': True, 'message': 'Incident updated successfully'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def delete_incident(request, incident_id):
    """Delete an incident"""
    try:
        incident = get_object_or_404(IncidentRecord, id=incident_id)
        incident.delete()
        return JsonResponse({'success': True, 'message': 'Incident deleted successfully'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def get_incident_details(request):
    """Get incident details for editing"""
    try:
        data = json.loads(request.body)
        incident_id = data.get('incident_id')
        incident = get_object_or_404(IncidentRecord, id=incident_id)
        
        return JsonResponse({
            'success': True,
            'incident': {
                'id': incident.id,
                'company_id': incident.company_id,
                'company_name': incident.company.company_name,
                'incident_type': incident.incident_type,
                'description': incident.description,
                'incident_date': incident.incident_date.strftime('%Y-%m-%d'),
                'outcome': incident.outcome,
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
def filter_incidents(request):
    """AJAX endpoint for filtering incidents"""
    incident_type = request.GET.get('type', '')
    company_id = request.GET.get('company', '')
    search = request.GET.get('search', '')
    
    incidents = IncidentRecord.objects.select_related('company').all()
    
    if incident_type:
        incidents = incidents.filter(incident_type=incident_type)
    if company_id:
        incidents = incidents.filter(company_id=company_id)
    if search:
        incidents = incidents.filter(
            Q(description__icontains=search) |
            Q(incident_type__icontains=search) |
            Q(company__company_name__icontains=search)
        )
    
    incidents_data = []
    for incident in incidents:
        incidents_data.append({
            'id': incident.id,
            'incident_type': incident.incident_type,
            'description': incident.description,
            'incident_date': incident.incident_date.strftime('%Y-%m-%d'),
            'outcome': incident.outcome,
            'company_name': incident.company.company_name,
        })
    
    return JsonResponse({'success': True, 'incidents': incidents_data})



@login_required(login_url='admin_login')
def admin_reviews_view(request):
    """Admin Reviews management page"""
    if request.user.user_type != 'admin':
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('dashboard')
    
    # Get all reviews with company and user info
    reviews = Review.objects.select_related('company', 'user').all().order_by('-created_at')
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    rating_filter = request.GET.get('rating', '')
    company_filter = request.GET.get('company', '')
    search_query = request.GET.get('search', '')
    
    # Apply filters
    if status_filter == 'approved':
        reviews = reviews.filter(is_approved=True)
    elif status_filter == 'pending':
        reviews = reviews.filter(is_approved=False)
    
    if rating_filter:
        reviews = reviews.filter(rating=int(rating_filter))
    
    if company_filter:
        reviews = reviews.filter(company_id=company_filter)
    
    if search_query:
        reviews = reviews.filter(
            Q(reviewer_name__icontains=search_query) |
            Q(review_text__icontains=search_query) |
            Q(title__icontains=search_query) |
            Q(company__company_name__icontains=search_query) |
            Q(user__email__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(reviews, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get statistics
    total_reviews = Review.objects.count()
    approved_reviews = Review.objects.filter(is_approved=True).count()
    pending_reviews = Review.objects.filter(is_approved=False).count()
    featured_reviews = Review.objects.filter(is_featured=True).count()
    
    # Get average rating
    avg_rating = Review.objects.filter(is_approved=True).aggregate(Avg('rating'))['rating__avg'] or 0
    
    # Get rating distribution
    rating_distribution = {}
    for i in range(1, 6):
        rating_distribution[i] = Review.objects.filter(rating=i, is_approved=True).count()
    
    # Get companies for filter
    companies = Company.objects.filter(status='approved').values('id', 'company_name')
    
    context = {
        'reviews': page_obj,
        'total_reviews': total_reviews,
        'approved_reviews': approved_reviews,
        'pending_reviews': pending_reviews,
        'featured_reviews': featured_reviews,
        'avg_rating': round(avg_rating, 1),
        'rating_distribution': rating_distribution,
        'companies': companies,
    }
    
    return render(request, 'backend/dashboard/reviews.html', context)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def approve_review(request, review_id):
    """Approve a review"""
    try:
        review = get_object_or_404(Review, id=review_id)
        review.is_approved = True
        review.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Review approved successfully'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def unapprove_review(request, review_id):
    """Unapprove a review"""
    try:
        review = get_object_or_404(Review, id=review_id)
        review.is_approved = False
        review.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Review unapproved successfully'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def feature_review(request, review_id):
    """Feature a review (show on homepage)"""
    try:
        review = get_object_or_404(Review, id=review_id)
        review.is_featured = True
        review.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Review featured successfully'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def unfeature_review(request, review_id):
    """Unfeature a review"""
    try:
        review = get_object_or_404(Review, id=review_id)
        review.is_featured = False
        review.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Review unfeatured successfully'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def delete_review_admin(request, review_id):
    """Delete a review"""
    try:
        review = get_object_or_404(Review, id=review_id)
        review.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Review deleted successfully'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def get_review_details(request):
    """Get review details for editing"""
    try:
        data = json.loads(request.body)
        review_id = data.get('review_id')
        review = get_object_or_404(Review, id=review_id)
        
        return JsonResponse({
            'success': True,
            'review': {
                'id': review.id,
                'company_id': review.company.id,
                'company_name': review.company.company_name,
                'user_id': review.user.id,
                'user_name': review.user.full_name or review.user.email,
                'rating': review.rating,
                'title': review.title,
                'review_text': review.review_text,
                'is_approved': review.is_approved,
                'is_featured': review.is_featured,
                'reviewer_name': review.reviewer_name,
                'reviewer_role': review.reviewer_role,
                'reviewer_company': review.reviewer_company,
                'company_response': review.company_response,
                'created_at': review.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def update_review(request, review_id):
    """Update review details"""
    try:
        review = get_object_or_404(Review, id=review_id)
        data = json.loads(request.body)
        
        review.rating = data.get('rating', review.rating)
        review.title = data.get('title', review.title)
        review.review_text = data.get('review_text', review.review_text)
        review.reviewer_name = data.get('reviewer_name', review.reviewer_name)
        review.reviewer_role = data.get('reviewer_role', review.reviewer_role)
        review.reviewer_company = data.get('reviewer_company', review.reviewer_company)
        review.company_response = data.get('company_response', review.company_response)
        review.is_approved = data.get('is_approved', review.is_approved)
        review.is_featured = data.get('is_featured', review.is_featured)
        
        if data.get('company_response'):
            review.response_date = timezone.now()
        
        review.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Review updated successfully'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def bulk_approve_reviews(request):
    """Bulk approve selected reviews"""
    try:
        data = json.loads(request.body)
        review_ids = data.get('review_ids', [])
        
        if not review_ids:
            return JsonResponse({'success': False, 'error': 'No reviews selected'}, status=400)
        
        count = Review.objects.filter(id__in=review_ids).update(is_approved=True)
        
        return JsonResponse({
            'success': True,
            'message': f'{count} reviews approved successfully'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def bulk_delete_reviews(request):
    """Bulk delete selected reviews"""
    try:
        data = json.loads(request.body)
        review_ids = data.get('review_ids', [])
        
        if not review_ids:
            return JsonResponse({'success': False, 'error': 'No reviews selected'}, status=400)
        
        count = Review.objects.filter(id__in=review_ids).delete()
        
        return JsonResponse({
            'success': True,
            'message': f'{count[0]} reviews deleted successfully'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    
@login_required(login_url='admin_login')
def payment_history_view(request):
    """View all payment transactions from Stripe"""
    if request.user.user_type != 'admin':
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('dashboard')

    # Get all payment-related history
    payment_actions = ['payment_succeeded', 'payment_failed', 'payment_refunded',
                       'invoice_paid', 'invoice_payment_failed']

    payments = SubscriptionHistory.objects.filter(
        action__in=payment_actions
    ).select_related(
        'subscription',
        'subscription__company',
        'new_plan',
        'changed_by'
    ).order_by('-changed_at')

    # Apply filters
    status_filter = request.GET.get('status', '')
    company_filter = request.GET.get('company', '')

    if status_filter:
        payments = payments.filter(action=status_filter)

    if company_filter:
        payments = payments.filter(subscription__company__company_name__icontains=company_filter)

    # Pagination
    paginator = Paginator(payments, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Statistics
    stats = {
        'total_payments': payments.count(),
        'successful': payments.filter(action='payment_succeeded').count(),
        'failed': payments.filter(action='payment_failed').count(),
        'refunded': payments.filter(action='payment_refunded').count(),
        'total_amount': payments.aggregate(total=models.Sum('amount'))['total'] or 0,
    }

    context = {
        'payments': page_obj,
        'stats': stats,
        'current_status': status_filter,
        'current_company': company_filter,
    }

    return render(request, 'backend/dashboard/payments.html', context)


@login_required(login_url='admin_login')
def payment_history_view(request):
    """View all payment transactions from Stripe"""
    if request.user.user_type != 'admin':
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('dashboard')

    # Get all payment-related history
    payment_actions = ['payment_succeeded', 'payment_failed', 'payment_refunded',
                       'invoice_paid', 'invoice_payment_failed']

    payments = SubscriptionHistory.objects.filter(
        action__in=payment_actions
    ).select_related(
        'subscription',
        'subscription__company',
        'new_plan',
        'changed_by'
    ).order_by('-changed_at')

    # Apply filters
    status_filter = request.GET.get('status', '')
    company_filter = request.GET.get('company', '')

    if status_filter:
        payments = payments.filter(action=status_filter)

    if company_filter:
        payments = payments.filter(subscription__company__company_name__icontains=company_filter)

    # Pagination
    paginator = Paginator(payments, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Statistics
    stats = {
        'total_payments': payments.count(),
        'successful': payments.filter(action='payment_succeeded').count(),
        'failed': payments.filter(action='payment_failed').count(),
        'refunded': payments.filter(action='payment_refunded').count(),
        'total_amount': payments.aggregate(total=Sum('amount'))['total'] or 0,
    }

    context = {
        'payments': page_obj,
        'stats': stats,
        'current_status': status_filter,
        'current_company': company_filter,
    }

    return render(request, 'backend/dashboard/payments.html', context)


@login_required(login_url='admin_login')
def get_payment_details(request, payment_id):
    """Get detailed payment information from Stripe"""
    if request.user.user_type != 'admin':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        history = SubscriptionHistory.objects.get(id=payment_id)
        
        # Get Stripe payment details if available
        payment_details = {}
        if history.stripe_event_id:
            try:
                # Retrieve from Stripe
                event = stripe.Event.retrieve(history.stripe_event_id)
                payment_details = {
                    'event_type': event.type,
                    'created': datetime.fromtimestamp(event.created).strftime('%Y-%m-%d %H:%M:%S'),
                    'data': event.data.object if hasattr(event.data, 'object') else {}
                }
            except:
                payment_details = {'error': 'Could not retrieve from Stripe'}
        
        return JsonResponse({
            'success': True,
            'payment': {
                'id': history.id,
                'action': history.get_action_display(),
                'amount': str(history.amount) if history.amount else 'N/A',
                'company': history.subscription.company.company_name,
                'plan': history.new_plan.display_name if history.new_plan else 'N/A',
                'date': history.changed_at.strftime('%Y-%m-%d %H:%M:%S'),
                'notes': history.notes,
                'stripe_details': payment_details
            }
        })
    except SubscriptionHistory.DoesNotExist:
        return JsonResponse({'error': 'Payment not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
    
    



@login_required(login_url='admin_login')
@require_http_methods(["POST"])
def admin_change_company_password(request):
    """Admin change company user password"""
    if request.user.user_type != 'admin':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        data = json.loads(request.body)
        company_id = data.get('company_id')
        user_id = data.get('user_id')
        new_password = data.get('new_password')
        
        # Validation
        if not new_password or len(new_password) < 8:
            return JsonResponse({'error': 'Password must be at least 8 characters'})
        
        if not any(c.isupper() for c in new_password):
            return JsonResponse({'error': 'Password must contain at least one uppercase letter'})
        
        if not any(c.islower() for c in new_password):
            return JsonResponse({'error': 'Password must contain at least one lowercase letter'})
        
        if not any(c.isdigit() for c in new_password):
            return JsonResponse({'error': 'Password must contain at least one number'})
        
        # Get the user
        user = User.objects.get(id=user_id)
        
        # Update password
        user.set_password(new_password)
        user.save()
        
        # Create history record
        SubscriptionHistory.objects.create(
            action='change_password',
            notes=f'Password changed by admin for company {company_id}',
            changed_by=request.user
        )
        
        return JsonResponse({'success': True, 'message': 'Password changed successfully'})
        
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)