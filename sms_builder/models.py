from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import RegexValidator, MinLengthValidator
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils import timezone
import re

# Custom User Manager
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email address is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('user_type', 'admin')
        extra_fields.setdefault('is_verified', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)

# Custom User Model
class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('admin', 'Administrator'),
        ('company', 'Company User'),
    )
    
    username = None  # Remove username field, use email instead
    email = models.EmailField(unique=True, db_index=True)
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='company')
    
    # Fields from your form - Contact Person Info
    full_name = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=100, blank=True, null=True, help_text="Role/Position in company")
    
    # Account status
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    terms_accepted = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # Email is required, full_name is optional
    
    objects = CustomUserManager()
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.full_name or self.email} ({self.email})"
    
    def save(self, *args, **kwargs):
        # If full_name is provided but first_name/last_name are empty, try to split
        if self.full_name and not self.first_name and not self.last_name:
            name_parts = self.full_name.split(' ', 1)
            self.first_name = name_parts[0]
            self.last_name = name_parts[1] if len(name_parts) > 1 else ''
        super().save(*args, **kwargs)
    
    @property
    def is_admin_user(self):
        return self.user_type == 'admin'
    
    @property
    def is_company_user(self):
        return self.user_type == 'company'


# 1. Module-level ABN Validator (Combines both your logic safely)
def validate_abn(value):
    if value:
        abn = re.sub(r'\s+', '', str(value))
        if not abn.isdigit():
            raise ValidationError('ABN must contain only numbers')
        if len(abn) != 11:
            raise ValidationError('ABN must be 11 digits')
        
    
# 2. Merged Company Model
class Company(models.Model):
    COMPANY_STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('suspended', 'Suspended'),
        ('rejected', 'Rejected'),
        ('inactive', 'Inactive'),
    )
    
    # ── CORE ──
    user = models.OneToOneField('User', on_delete=models.CASCADE, related_name='company_profile')
    status = models.CharField(max_length=20, choices=COMPANY_STATUS_CHOICES, default='pending')
    registration_date = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    approved_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_companies')
    
    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True, help_text="Stripe Customer ID")
    stripe_default_payment_method_id = models.CharField(max_length=100, blank=True, null=True, help_text="Default payment method")
    
    # Dev 1: Declaration
    declaration_accepted = models.BooleanField(default=False, help_text="User declared info is accurate")
    
    

    # ── COMPANY DETAILS ──
    company_name = models.CharField(max_length=255, db_index=True)
    abn = models.CharField(max_length=11, unique=True, validators=[validate_abn], help_text="11-digit Australian Business Number")
    
    # Dev 1: Split Address Fields
    address_street = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=10, blank=True, null=True)
    postcode = models.CharField(max_length=10, blank=True, null=True)
    
    # Dev 2: Single Address Field (Kept to prevent partner's code from breaking)
    address = models.TextField(blank=True, null=True)
    
    # Dev 1: Contact Details
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    contact_role = models.CharField(max_length=100, blank=True, null=True)

    # Dev 2: Subscription Details
    subscription_plan = models.CharField(max_length=50, blank=True, null=True, default='starter')
    subscription_status = models.CharField(max_length=20, default='pending')
    subscription_end_date = models.DateTimeField(blank=True, null=True)
    trial_ends_at = models.DateTimeField(blank=True, null=True)
    
    # ── DOCUMENTS ──
    company_document = models.FileField(
        upload_to='company_docs/%Y/%m/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
        help_text="Upload a related company document (PDF only)"
    )

    class Meta:
        db_table = 'companies'
        verbose_name = 'Company'
        verbose_name_plural = 'Companies'
        ordering = ['-registration_date']
    
    def __str__(self):
        return self.company_name
    
    def save(self, *args, **kwargs):
        if self.abn:
            self.abn = re.sub(r'\s+', '', self.abn)
        super().save(*args, **kwargs)
    
    @property
    def is_approved(self):
        return self.status == 'approved'
    

class CompanyDocument(models.Model):
    DOCUMENT_TYPE_CHOICES = [
        ("FULL_DOC", "Full Document"),
        ("RISK_DOC", "Risk Document"),
        ("OTHER", "Other"),
    ]
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="documents")
    file = models.FileField(upload_to="company_docs/%Y/%m/")
    name = models.CharField(max_length=255)
    doc_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPE_CHOICES,
        null=True,
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name
    
    
class PaymentMethod(models.Model):
    """Store payment method information from Stripe"""

    PAYMENT_TYPE_CHOICES = (
        ('card', 'Card'),
        ('bank_account', 'Bank Account'),
    )

    CARD_BRAND_CHOICES = (
        ('visa', 'Visa'),
        ('mastercard', 'Mastercard'),
        ('amex', 'American Express'),
        ('discover', 'Discover'),
        ('jcb', 'JCB'),
        ('diners', 'Diners Club'),
        ('unionpay', 'UnionPay'),
        ('unknown', 'Unknown'),
    )

    # Relationships
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='payment_methods')

    # Stripe Details
    stripe_payment_method_id = models.CharField(max_length=100, unique=True)
    stripe_customer_id = models.CharField(max_length=100)

    # Payment Method Details
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='card')
    is_default = models.BooleanField(default=False)

    # Card Details (if payment_type is 'card')
    card_brand = models.CharField(max_length=20, choices=CARD_BRAND_CHOICES, blank=True, null=True)
    card_last4 = models.CharField(max_length=4, blank=True, null=True)
    card_exp_month = models.IntegerField(blank=True, null=True)
    card_exp_year = models.IntegerField(blank=True, null=True)
    cardholder_name = models.CharField(max_length=255, blank=True, null=True)

    # Bank Account Details (if payment_type is 'bank_account')
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    bank_last4 = models.CharField(max_length=4, blank=True, null=True)
    bank_account_type = models.CharField(max_length=50, blank=True, null=True)

    # Status
    is_active = models.BooleanField(default=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payment_methods'
        verbose_name = 'Payment Method'
        verbose_name_plural = 'Payment Methods'
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        if self.payment_type == 'card':
            return f"{self.card_brand} •••• {self.card_last4} - {self.company.company_name}"
        else:
            return f"Bank Account •••• {self.bank_last4} - {self.company.company_name}"

    @property
    def display_name(self):
        """Return a display-friendly name for the payment method"""
        if self.payment_type == 'card':
            return f"{self.card_brand.upper()} ending in {self.card_last4}"
        return f"Bank Account ending in {self.bank_last4}"
    


# 3. Dev 1's Model: Fleet Summary (High-Level Profile)
class CompanyFleet(models.Model):
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='fleet')
    
    total_vehicles = models.PositiveIntegerField(default=0, blank=True, null=True)
    max_gvm = models.CharField(max_length=50, blank=True, null=True)
    average_vehicle_age = models.CharField(max_length=50, blank=True, null=True)
    
    vehicle_types = models.JSONField(default=list, blank=True)
    special_cargo = models.JSONField(default=list, blank=True)
    nhvr_configurations = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'company_fleets'
        verbose_name = 'Company Fleet'
        verbose_name_plural = 'Company Fleets'

    def __str__(self):
        return f"Fleet for {self.company.company_name}"
    
    @property
    def flat_nhvr_configs(self):
        if isinstance(self.nhvr_configurations, dict):
            return [item for sublist in self.nhvr_configurations.values() for item in sublist]
        elif isinstance(self.nhvr_configurations, list):
            return self.nhvr_configurations
        return []


class Driver(models.Model):
    LICENCE_CHOICES = (
        ('LR', 'Light Rigid'),
        ('MR', 'Medium Rigid'),
        ('HR', 'Heavy Rigid'),
        ('HC', 'Heavy Combination'),
        ('MC', 'Multi Combination'),
    )
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('review_due', 'Review Due'),
        ('expired', 'Expired'),
        ('suspended', 'Suspended'),
    )
    
    APPROVAL_STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('inactive', 'Inactive'),
    )
    
    # Basic Information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., Fleet Manager, Senior Driver")
    
    # Licence Information
    licence_number = models.CharField(max_length=50, unique=True)
    licence_class = models.CharField(max_length=2, choices=LICENCE_CHOICES, default='HR')
    licence_expiry = models.DateField()
    
    # Address
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=50, blank=True, null=True)
    postcode = models.CharField(max_length=10, blank=True, null=True)
    
    # Medical Information
    medical_expiry = models.DateField(blank=True, null=True)
    has_medical_certificate = models.BooleanField(default=False)
    
    # Training Information
    induction_date = models.DateField(blank=True, null=True)
    last_training_date = models.DateField(blank=True, null=True)
    next_training_due = models.DateField(blank=True, null=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Approval Status
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    approved_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_drivers')
    
    # Relationships
    company = models.ForeignKey('Company', on_delete=models.CASCADE, related_name='drivers')
    
    # Documents
    licence_document = models.FileField(upload_to='driver_licences/', blank=True, null=True)
    medical_document = models.FileField(upload_to='driver_medical/', blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_drivers')
    
    class Meta:
        db_table = 'drivers'
        verbose_name = 'Driver'
        verbose_name_plural = 'Drivers'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.licence_number}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_expired(self):
        from django.utils import timezone
        return self.licence_expiry < timezone.now().date()
    
    @property
    def days_until_expiry(self):
        if self.licence_expiry:
            return (self.licence_expiry - timezone.now().date()).days
        return None


class Vehicle(models.Model):
    VEHICLE_TYPE_CHOICES = (
        ('rigid_lt_4_5t', 'Rigid Trucks (<4.5t)'),
        ('rigid_4_5_12t', 'Rigid Trucks (4.5t–12t)'),
        ('rigid_gt_12t', 'Rigid Trucks (>12t)'),
        ('b_doubles', 'B-Doubles'),
        ('tankers', 'Tankers'),
        ('tippers', 'Tippers'),
        ('road_trains', 'Road Trains'),
        ('flatbeds', 'Flatbeds'),
        ('prime_movers', 'Prime Movers'),
        ('refrigerated', 'Refrigerated Vehicles'),
    )
    
    STATUS_CHOICES = (
        ('current', 'Current'),
        ('expired', 'Expired'),
        ('due_soon', 'Due Soon'),
        ('suspended', 'Suspended'),
    )
    
    APPROVAL_STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('inactive', 'Inactive'),
    )
    
    # Basic Information
    make = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    year = models.IntegerField()
    vin = models.CharField(max_length=17, unique=True, help_text="17-character Vehicle Identification Number")
    registration_number = models.CharField(max_length=20, unique=True)
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPE_CHOICES, default='rigid_lt_4_5t')
    
    # Registration Details
    registration_expiry = models.DateField()
    inspection_due_date = models.DateField(blank=True, null=True)
    cof_expiry = models.DateField(blank=True, null=True)
    
    # Insurance
    insurance_company = models.CharField(max_length=100, blank=True, null=True)
    insurance_policy_number = models.CharField(max_length=100, blank=True, null=True)
    insurance_expiry = models.DateField(blank=True, null=True)
    
    # Technical Specifications
    gross_vehicle_mass = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="in kg")
    tare_weight = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="in kg")
    load_capacity = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="in kg")
    fuel_type = models.CharField(max_length=50, blank=True, null=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='current')
    
    # Approval Status
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    approved_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_vehicles')
    
    # Relationships
    company = models.ForeignKey('Company', on_delete=models.CASCADE, related_name='vehicles')
    
    # Documents
    rego_document = models.FileField(upload_to='vehicle_rego/', blank=True, null=True)
    cof_document = models.FileField(upload_to='vehicle_cof/', blank=True, null=True)
    insurance_document = models.FileField(upload_to='vehicle_insurance/', blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_vehicles')
    
    class Meta:
        db_table = 'vehicles'
        verbose_name = 'Vehicle'
        verbose_name_plural = 'Vehicles'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.make} {self.model} - {self.registration_number}"
    
    @property
    def full_name(self):
        return f"{self.make} {self.model}"
    
    @property
    def is_expired(self):
        if not self.registration_expiry:
            return False
        return self.registration_expiry < timezone.now().date()
    
    @property
    def days_until_expiry(self):
        if self.registration_expiry:
            return (self.registration_expiry - timezone.now().date()).days
        return None
class CompanyOperation(models.Model):
    # Link strictly to one company
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='operations')
    
    # ── STEP 2: OPERATIONS ──
    work_types = models.JSONField(default=list, blank=True)
    accreditations = models.JSONField(default=list, blank=True)
    
    audit_date_none = models.DateField(blank=True, null=True)
    audit_date_trucksafe = models.DateField(blank=True, null=True)
    audit_date_wahva = models.DateField(blank=True, null=True)
    
    operating_areas = models.JSONField(default=list, blank=True)
    
    operating_hours = models.CharField(max_length=50, blank=True, null=True)
    num_drivers = models.PositiveIntegerField(default=0, blank=True, null=True)

    class Meta:
        db_table = 'company_operations'
        verbose_name = 'Company Operation'
        verbose_name_plural = 'Company Operations'

    def __str__(self):
        return f"Operations for {self.company.company_name}"
    
    
# ── STEP 4: RISK (STATIC FIELDS) ──
class CompanyRiskProfile(models.Model):
    # Link strictly to one company
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='risk_profile')
    
    # Array of checkboxes for safety policies
    safety_policies = models.JSONField(default=list, blank=True)
    
    # Textarea
    additional_notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'company_risk_profiles'
        verbose_name = 'Company Risk Profile'
        verbose_name_plural = 'Company Risk Profiles'

    def __str__(self):
        return f"Risk Profile for {self.company.company_name}"


# ── STEP 4: RISK (DYNAMIC TABLE ROWS) ──
class RiskHazard(models.Model):
    # Link to Company using ForeignKey because a company can have MULTIPLE hazards
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='risk_hazards')
    
    hazard_description = models.CharField(max_length=255)
    
    # Using choices to match the JS arrays
    LIKELIHOOD_CHOICES = [
        ('Rare', 'Rare'), ('Unlikely', 'Unlikely'), ('Possible', 'Possible'), 
        ('Likely', 'Likely'), ('Almost Certain', 'Almost Certain')
    ]
    likelihood = models.CharField(max_length=20, choices=LIKELIHOOD_CHOICES)
    
    CONSEQUENCE_CHOICES = [
        ('Insignificant', 'Insignificant'), ('Minor', 'Minor'), ('Moderate', 'Moderate'), 
        ('Major', 'Major'), ('Catastrophic', 'Catastrophic')
    ]
    consequence = models.CharField(max_length=20, choices=CONSEQUENCE_CHOICES)
    
    control_measures = models.CharField(max_length=500, blank=True, null=True)
    
    class Meta:
        db_table = 'company_risk_hazards'
        verbose_name = 'Risk Hazard'
        verbose_name_plural = 'Risk Hazards'

    def __str__(self):
        return f"{self.hazard_description} ({self.company.company_name})"
    
    
# ── STEP 5: SUBCONTRACTORS (STATIC FIELDS) ──
class CompanySubcontractorProfile(models.Model):
    # Link strictly to one company
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='subcontractor_profile')
    
    # Subcontractor Use (Maps to subYes / subNo)
    engages_subcontractors = models.BooleanField(default=False)
    
    # Checkbox array for compliance practices
    compliance_practices = models.JSONField(default=list, blank=True)
    
    # Form details
    active_subcontractors = models.PositiveIntegerField(default=0, blank=True, null=True)
    primary_engagement_type = models.CharField(max_length=100, blank=True, null=True)
    review_frequency = models.CharField(max_length=50, blank=True, null=True)
    
    # Textarea for CoR
    cor_procedures = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'company_subcontractor_profiles'
        verbose_name = 'Subcontractor Profile'
        verbose_name_plural = 'Subcontractor Profiles'

    def __str__(self):
        return f"Subcontractor Profile for {self.company.company_name}"


# ── STEP 5: SUBCONTRACTORS (DYNAMIC ROWS) ──
class SubcontractorRecord(models.Model):
    # Link using ForeignKey because a company can have multiple subcontractors
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='subcontractor_records')
    
    # Dynamic JS row fields
    subcontractor_name = models.CharField(max_length=255)
    abn = models.CharField(max_length=20, blank=True, null=True)
    licence_type = models.CharField(max_length=100, blank=True, null=True)
    contract_expiry = models.DateField(blank=True, null=True)

    class Meta:
        db_table = 'company_subcontractor_records'
        verbose_name = 'Subcontractor Record'
        verbose_name_plural = 'Subcontractor Records'

    def __str__(self):
        return f"{self.subcontractor_name} ({self.company.company_name})"


# ── STEP 6: INCIDENTS (STATIC FIELDS) ──
class CompanyIncidentProfile(models.Model):
    # Link strictly to one company
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='incident_profile')
    
    # Checkbox array for incident reporting process
    reporting_process = models.JSONField(default=list, blank=True)
    
    # Number inputs
    incidents_last_12_months = models.PositiveIntegerField(default=0, blank=True, null=True)
    incidents_last_3_years = models.PositiveIntegerField(default=0, blank=True, null=True)
    injuries_resulting = models.PositiveIntegerField(default=0, blank=True, null=True)
    
    # Textarea
    improvement_actions = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'company_incident_profiles'
        verbose_name = 'Incident Profile'
        verbose_name_plural = 'Incident Profiles'

    def __str__(self):
        return f"Incident Profile for {self.company.company_name}"


# ── STEP 6: INCIDENTS (DYNAMIC ROWS) ──
class IncidentRecord(models.Model):
    # Link using ForeignKey because a company can have multiple incidents
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='incident_records')
    
    # Dynamic JS row fields
    incident_date = models.DateField(blank=True, null=True)
    description = models.CharField(max_length=255)
    
    INCIDENT_TYPE_CHOICES = [
        ('Accident', 'Accident'),
        ('Near-Miss', 'Near-Miss'),
        ('Injury', 'Injury'),
        ('Property Damage', 'Property Damage'),
        ('Dangerous Goods', 'Dangerous Goods')
    ]
    incident_type = models.CharField(max_length=50, choices=INCIDENT_TYPE_CHOICES, blank=True, null=True)
    outcome = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'company_incident_records'
        verbose_name = 'Incident Record'
        verbose_name_plural = 'Incident Records'
        ordering = ['-incident_date']

    def __str__(self):
        return f"{self.incident_type} on {self.incident_date} ({self.company.company_name})"



class Service(models.Model):
    """Service model for Our Services section"""
    
    ICON_CHOICES = (
        ('bi-file-earmark-text', 'Document'),
        ('bi-shield-check', 'Shield Check'),
        ('bi-truck', 'Truck'),
        ('bi-exclamation-triangle', 'Warning'),
        ('bi-bar-chart-line', 'Chart'),
        ('bi-person-lock', 'User Lock'),
        ('bi-building', 'Building'),
        ('bi-clock-history', 'History'),
        ('bi-graph-up', 'Graph'),
        ('bi-phone', 'Phone'),
        ('bi-envelope', 'Email'),
        ('bi-gear', 'Settings'),
        ('bi-star', 'Star'),
        ('bi-heart', 'Heart'),
        ('bi-cpu', 'CPU'),
        ('bi-cloud', 'Cloud'),
        ('bi-people', 'People'),
        ('bi-chat', 'Chat'),
        ('bi-calendar', 'Calendar'),
        ('bi-tools', 'Tools'),
        ('bi-headset', 'Support'),
    )
    
    # Basic Information
    icon = models.CharField(max_length=50, choices=ICON_CHOICES, default='bi-truck')
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    # Display Order
    order = models.IntegerField(default=0, help_text="Lower numbers appear first")
    
    # Status
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'services'
        verbose_name = 'Service'
        verbose_name_plural = 'Services'
        ordering = ['order', 'created_at']
    
    def __str__(self):
        return self.title
    









class PricingPlan(models.Model):
    """Pricing Plan Model for subscriptions"""

    PLAN_TYPES = (
        ('starter', 'Starter'),
        ('professional', 'Professional'),
        ('enterprise', 'Enterprise'),
    )

    PRICE_PERIOD = (
        ('month', 'Per Month'),
        ('year', 'Per Year'),
        ('one_time', 'One Time'),
    )

    # Basic Information
    name = models.CharField(max_length=50, choices=PLAN_TYPES, unique=True)
    display_name = models.CharField(max_length=100)
    description = models.CharField(max_length=200, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_period = models.CharField(max_length=20, choices=PRICE_PERIOD, default='month')

    # Features (store as JSON)
    features = models.JSONField(default=list, help_text="List of included features")
    disabled_features = models.JSONField(default=list, help_text="List of disabled features")

    # Display Settings
    is_popular = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0, help_text="Lower numbers appear first")

    # Button Settings
    button_text = models.CharField(max_length=50, default='Get Started')
    button_class = models.CharField(max_length=50, default='btn-outline-primary')

    # === STRIPE INTEGRATION FIELDS ===
    stripe_price_id = models.CharField(max_length=100, blank=True, null=True, help_text="Stripe Price ID for this plan")
    stripe_product_id = models.CharField(max_length=100, blank=True, null=True, help_text="Stripe Product ID for this plan")
    stripe_lookup_key = models.CharField(max_length=100, blank=True, null=True, help_text="Stripe lookup key for this plan")

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pricing_plans'
        verbose_name = 'Pricing Plan'
        verbose_name_plural = 'Pricing Plans'
        ordering = ['order', 'price']

    def __str__(self):
        return f"{self.display_name} - ${self.price}/{self.price_period}"

    def get_features_list(self):
        """Return features as list"""
        if isinstance(self.features, list):
            return self.features
        return []
# ==============================
# COMPANY SUBSCRIPTION MODEL
# ==============================

class CompanySubscription(models.Model):
    """Company Subscription Model"""

    SUBSCRIPTION_STATUS = (
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('pending', 'Pending'),
        ('trial', 'Trial'),
        ('past_due', 'Past Due'),
        ('incomplete', 'Incomplete'),
        ('incomplete_expired', 'Incomplete Expired'),
        ('trialing', 'Trialing'),
        ('unpaid', 'Unpaid'),
    )

    # Relationships
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(PricingPlan, on_delete=models.SET_NULL, null=True, related_name='subscriptions')

    # Subscription Details
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    last_renewal_date = models.DateTimeField(null=True, blank=True)
    next_renewal_date = models.DateTimeField(null=True, blank=True)

    # Payment Details
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    transaction_id = models.CharField(max_length=255, blank=True, null=True)

    # Status
    status = models.CharField(max_length=20, choices=SUBSCRIPTION_STATUS, default='pending')
    auto_renew = models.BooleanField(default=False)

    # === STRIPE INTEGRATION FIELDS ===
    stripe_subscription_id = models.CharField(max_length=100, blank=True, null=True, help_text="Stripe Subscription ID")
    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True, help_text="Stripe Customer ID")
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True, null=True, help_text="Stripe Payment Intent ID")
    stripe_setup_intent_id = models.CharField(max_length=100, blank=True, null=True, help_text="Stripe Setup Intent ID")

    # Trial Information
    trial_start = models.DateTimeField(blank=True, null=True)
    trial_end = models.DateTimeField(blank=True, null=True)

    # Cancellation Information
    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancel_at_period_end = models.BooleanField(default=False)

    # Payment Status
    last_payment_status = models.CharField(max_length=50, blank=True, null=True)
    last_payment_date = models.DateTimeField(blank=True, null=True)
    last_payment_error = models.TextField(blank=True, null=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_subscriptions')

    class Meta:
        db_table = 'company_subscriptions'
        verbose_name = 'Company Subscription'
        verbose_name_plural = 'Company Subscriptions'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.company.company_name} - {self.plan.display_name if self.plan else 'No Plan'}"

    @property
    def is_active(self):
        from django.utils import timezone
        return self.status in ['active', 'trialing'] and (self.end_date is None or self.end_date > timezone.now())

    @property
    def days_remaining(self):
        from django.utils import timezone
        if self.end_date:
            return (self.end_date - timezone.now()).days
        return None

    @property
    def is_on_trial(self):
        from django.utils import timezone
        return self.status == 'trialing' and self.trial_end and self.trial_end > timezone.now()

# ==============================
# SUBSCRIPTION HISTORY MODEL
# ==============================

class SubscriptionHistory(models.Model):
    """Track subscription changes history"""

    ACTION_CHOICES = (
        ('created', 'Created'),
        ('upgraded', 'Upgraded'),
        ('downgraded', 'Downgraded'),
        ('renewed', 'Renewed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
        ('change_requested', 'Change Requested'),
        ('change_approved', 'Change Approved'),
        ('change_rejected', 'Change Rejected'),
        ('change_cancelled', 'Change Cancelled'),
        # === STRIPE SPECIFIC ACTIONS ===
        ('payment_succeeded', 'Payment Succeeded'),
        ('payment_failed', 'Payment Failed'),
        ('payment_refunded', 'Payment Refunded'),
        ('invoice_paid', 'Invoice Paid'),
        ('invoice_payment_failed', 'Invoice Payment Failed'),
        ('subscription_updated', 'Subscription Updated'),
        ('subscription_deleted', 'Subscription Deleted'),
        ('trial_started', 'Trial Started'),
        ('trial_ended', 'Trial Ended'),
        ('past_due', 'Past Due'),
    )

    subscription = models.ForeignKey(CompanySubscription, on_delete=models.CASCADE, related_name='history')
    old_plan = models.ForeignKey(PricingPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    new_plan = models.ForeignKey(PricingPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    notes = models.TextField(blank=True, null=True)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='subscription_changes')
    changed_at = models.DateTimeField(auto_now_add=True)

    # === STRIPE SPECIFIC FIELDS ===
    stripe_event_id = models.CharField(max_length=100, blank=True, null=True, help_text="Stripe Event ID")
    stripe_invoice_id = models.CharField(max_length=100, blank=True, null=True, help_text="Stripe Invoice ID")
    amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    class Meta:
        db_table = 'subscription_history'
        verbose_name = 'Subscription History'
        verbose_name_plural = 'Subscription Histories'
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.subscription.company.company_name} - {self.action} at {self.changed_at}"

class StripeWebhookEvent(models.Model):
    """Track all Stripe webhook events for debugging and auditing"""

    EVENT_TYPES = (
        ('customer.subscription.created', 'Subscription Created'),
        ('customer.subscription.updated', 'Subscription Updated'),
        ('customer.subscription.deleted', 'Subscription Deleted'),
        ('invoice.paid', 'Invoice Paid'),
        ('invoice.payment_failed', 'Invoice Payment Failed'),
        ('payment_intent.succeeded', 'Payment Succeeded'),
        ('payment_intent.payment_failed', 'Payment Failed'),
        ('checkout.session.completed', 'Checkout Session Completed'),
        ('customer.updated', 'Customer Updated'),
        ('customer.deleted', 'Customer Deleted'),
    )

    event_id = models.CharField(max_length=100, unique=True, help_text="Stripe Event ID")
    event_type = models.CharField(max_length=100, choices=EVENT_TYPES)
    api_version = models.CharField(max_length=50, blank=True, null=True)
    data = models.JSONField(help_text="Full event data from Stripe")
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'stripe_webhook_events'
        verbose_name = 'Stripe Webhook Event'
        verbose_name_plural = 'Stripe Webhook Events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_id']),
            models.Index(fields=['event_type']),
            models.Index(fields=['processed']),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.event_id}"
    



class WhyUs(models.Model):
    """Why Us section - Features and benefits"""
    
    # Section Settings
    eyebrow = models.CharField(max_length=100, default='Why PRODRIVE', help_text="Small text above title")
    title = models.CharField(max_length=200, default='Built for the Road Ahead')
    description = models.TextField(default='Our system is designed for usability, compliance support, and efficient document workflows.')
    
    # YouTube Video
    video_url = models.CharField(max_length=255, default='Cm6eMeOg-KU', help_text="YouTube video ID")
    
    # Display Settings
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'why_us'
        verbose_name = 'Why Us Section'
        verbose_name_plural = 'Why Us Sections'
    
    def __str__(self):
        return self.title


class WhyUsFeature(models.Model):
    """Individual features in Why Us section"""
    
    why_us = models.ForeignKey(WhyUs, on_delete=models.CASCADE, related_name='features')
    icon = models.CharField(max_length=50, default='bi-check-circle-fill')
    text = models.CharField(max_length=255)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'why_us_features'
        verbose_name = 'Why Us Feature'
        verbose_name_plural = 'Why Us Features'
        ordering = ['order']
    
    def __str__(self):
        return self.text
    


class ContactMessage(models.Model):
    """Contact form messages"""
    
    STATUS_CHOICES = (
        ('new', 'New'),
        ('read', 'Read'),
        ('replied', 'Replied'),
        ('archived', 'Archived'),
    )
    
    name = models.CharField(max_length=255)
    email = models.EmailField()
    message = models.TextField()
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    is_agreed = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'contact_messages'
        verbose_name = 'Contact Message'
        verbose_name_plural = 'Contact Messages'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.email}"



class FooterSettings(models.Model):
    """Dynamic footer settings"""
    
    # Contact Info
    email = models.CharField(max_length=255, default='info@prodrivecompliance.com')
    phone = models.CharField(max_length=50, default='+61 4XX XXX XXX')
    address = models.CharField(max_length=255, default='Sydney, Australia')
    
    # Social Links
    facebook_url = models.URLField(blank=True, null=True)
    linkedin_url = models.URLField(blank=True, null=True)
    instagram_url = models.URLField(blank=True, null=True)
    twitter_url = models.URLField(blank=True, null=True)
    
    # Tagline
    tagline = models.TextField(default="Let's build a safer and smarter compliance system for your business.")
    
    # Compliance Logos (JSON)
    compliance_logos = models.JSONField(default=list, help_text="List of logo URLs")
    
    # Membership Logos (JSON)
    membership_logos = models.JSONField(default=list, help_text="List of membership logo URLs")
    
    # Copyright Text
    copyright_text = models.CharField(max_length=255, default='© 2026 PRODRIVE Compliance. All rights reserved.')
    
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'footer_settings'
        verbose_name = 'Footer Setting'
    
    def __str__(self):
        return "Footer Settings"


class SystemSettings(models.Model):
    """System wide settings for hero section and general settings"""
    
    # Hero Section Settings
    hero_badge = models.CharField(max_length=255, default='Web-Based Compliance Platform')
    hero_title = models.CharField(max_length=500, default='Smarter Safety Management for Heavy Vehicle Operations')
    hero_description = models.TextField(default='Build, manage, and monitor Safety Management System documents with a professional, responsive, and user-friendly web platform.')
    hero_button_text = models.CharField(max_length=100, default='Get Started Free')
    hero_button_link = models.CharField(max_length=255, default='../../form.html')
    hero_video_url = models.CharField(max_length=255, default='https://www.youtube.com/embed/Cm6eMeOg-KU')
    
    # Trust Items
    trust_item_1 = models.CharField(max_length=255, default='No credit card required')
    trust_item_2 = models.CharField(max_length=255, default='NHVR aligned')
    trust_item_3 = models.CharField(max_length=255, default='Setup in 15 minutes')
    
    # Carousel Images (store as JSON)
    carousel_images = models.JSONField(default=list, help_text='List of image URLs for carousel')
    
    # System Settings
    site_name = models.CharField(max_length=255, default='PRODRIVE')
    site_tagline = models.CharField(max_length=255, default='SMS Builder')
    version = models.CharField(max_length=50, default='v2.4.1')
    environment = models.CharField(max_length=20, default='Production')
    
    # Notification Settings
    email_notifications = models.BooleanField(default=True)
    new_registration_alerts = models.BooleanField(default=True)
    incident_notifications = models.BooleanField(default=True)
    compliance_reminders = models.BooleanField(default=True)
    maintenance_mode = models.BooleanField(default=False)
    
    # System Info
    last_backup = models.DateTimeField(blank=True, null=True)
    database_status = models.CharField(max_length=50, default='Healthy')
    uptime = models.CharField(max_length=20, default='99.97%')
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'system_settings'
    
    def __str__(self):
        return "System Settings"


class AdminProfile(models.Model):
    """Admin profile settings - linked to existing User model"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    role = models.CharField(max_length=100, default='Super Administrator')
    phone = models.CharField(max_length=20, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    
    class Meta:
        db_table = 'admin_profiles'
    
    def __str__(self):
        return f"Admin: {self.user.full_name or self.user.email}"
    
    
    
class Review(models.Model):
    """Client reviews for companies"""
    
    RATING_CHOICES = (
        (1, '1 Star'),
        (2, '2 Stars'),
        (3, '3 Stars'),
        (4, '4 Stars'),
        (5, '5 Stars'),
    )
    
    # Relationships
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    
    # Review Details
    rating = models.IntegerField(choices=RATING_CHOICES, default=5)
    title = models.CharField(max_length=200, blank=True, null=True)
    review_text = models.TextField()
    
    # Display Settings
    is_approved = models.BooleanField(default=False, help_text="Approve to show on website")
    is_featured = models.BooleanField(default=False)
    
    # Response from company
    company_response = models.TextField(blank=True, null=True)
    response_date = models.DateTimeField(blank=True, null=True)
    
    # Metadata
    reviewer_name = models.CharField(max_length=100)
    reviewer_role = models.CharField(max_length=100, blank=True, null=True)
    reviewer_company = models.CharField(max_length=200, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'reviews'
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.reviewer_name} - {self.rating} stars - {self.company.company_name}"
    
    @property
    def star_display(self):
        return '★' * self.rating + '☆' * (5 - self.rating)



class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True)
    expiry = models.DateTimeField()
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.token[:20]}"
    
    class Meta:
        verbose_name = "Password Reset Token"
        verbose_name_plural = "Password Reset Tokens"