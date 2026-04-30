from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone
from .models import *

# ==========================================
# 1. USER ADMIN (Custom User)
# ==========================================
@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    ordering = ['-created_at']
    list_display = ['email', 'full_name', 'user_type', 'is_active', 'is_verified', 'created_at']
    list_filter = ['user_type', 'is_active', 'is_verified', 'is_staff']
    search_fields = ['email', 'full_name', 'phone']

    fieldsets = (
        ('Login Credentials', {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'first_name', 'last_name', 'phone', 'role')}),
        ('Account Status', {'fields': ('user_type', 'is_active', 'is_verified', 'terms_accepted', 'terms_accepted_at')}),
        ('Permissions', {'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'last_login_ip')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password', 'user_type', 'full_name', 'phone'),
        }),
    )


# ==========================================
# 2. COMPANY INLINES
# ==========================================
class CompanyOperationInline(admin.StackedInline):
    model = CompanyOperation
    can_delete = False

class CompanyFleetInline(admin.StackedInline):
    model = CompanyFleet
    can_delete = False

class CompanyRiskProfileInline(admin.StackedInline):
    model = CompanyRiskProfile
    can_delete = False

class CompanySubcontractorProfileInline(admin.StackedInline):
    model = CompanySubcontractorProfile
    can_delete = False

class CompanyIncidentProfileInline(admin.StackedInline):
    model = CompanyIncidentProfile
    can_delete = False

class RiskHazardInline(admin.TabularInline):
    model = RiskHazard
    extra = 1

class SubcontractorRecordInline(admin.TabularInline):
    model = SubcontractorRecord
    extra = 1

class IncidentRecordInline(admin.TabularInline):
    model = IncidentRecord
    extra = 1

class ReviewInline(admin.TabularInline):
    model = Review
    extra = 0
    fields = ('reviewer_name', 'rating', 'is_approved', 'created_at')
    readonly_fields = ('created_at',)
    show_change_link = True


# ==========================================
# 3. COMPANY ADMIN
# ==========================================
@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'abn', 'user', 'status', 'registration_date', 'is_approved']
    list_filter = ['status', 'declaration_accepted', 'registration_date']
    search_fields = ['company_name', 'abn', 'user__email', 'contact_email']
    readonly_fields = ['registration_date', 'last_updated', 'approved_at']

    fieldsets = (
        ('Core Details', {
            'fields': ('user', 'status', 'declaration_accepted', 'approved_by', 'approved_at')
        }),
        ('Company Details', {
            'fields': ('company_name', 'abn', 'address_street', 'city', 'state', 'postcode')
        }),
        ('Contact Details', {
            'fields': ('contact_person', 'contact_role', 'contact_email', 'contact_phone')
        }),
        ('Timestamps', {
            'fields': ('registration_date', 'last_updated'),
            'classes': ('collapse',)
        }),
    )

    inlines = [
        CompanyOperationInline,
        CompanyFleetInline,
        CompanyRiskProfileInline,
        RiskHazardInline,
        CompanySubcontractorProfileInline,
        SubcontractorRecordInline,
        CompanyIncidentProfileInline,
        IncidentRecordInline,
        ReviewInline,
    ]

    def save_model(self, request, obj, form, change):
        if change and 'status' in form.changed_data:
            if obj.status == 'approved' and not obj.approved_at:
                obj.approved_at = timezone.now()
                obj.approved_by = request.user
        super().save_model(request, obj, form, change)


# ==========================================
# 4. DRIVER ADMIN
# ==========================================
@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'licence_number', 'licence_class', 'company', 'status', 'approval_status', 'licence_expiry']
    list_filter = ['status', 'approval_status', 'licence_class', 'company']
    search_fields = ['first_name', 'last_name', 'licence_number', 'email', 'company__company_name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('first_name', 'last_name', 'email', 'phone', 'role', 'company')
        }),
        ('Licence Information', {
            'fields': ('licence_number', 'licence_class', 'licence_expiry', 'licence_document')
        }),
        ('Address', {
            'fields': ('address', 'city', 'state', 'postcode')
        }),
        ('Medical Information', {
            'fields': ('medical_expiry', 'has_medical_certificate', 'medical_document')
        }),
        ('Training Information', {
            'fields': ('induction_date', 'last_training_date', 'next_training_due')
        }),
        ('Status', {
            'fields': ('status', 'approval_status', 'rejection_reason', 'approved_at', 'approved_by')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:  # New object
            obj.created_by = request.user
        if change and 'approval_status' in form.changed_data:
            if obj.approval_status == 'approved' and not obj.approved_at:
                obj.approved_at = timezone.now()
                obj.approved_by = request.user
        super().save_model(request, obj, form, change)


# ==========================================
# 5. VEHICLE ADMIN
# ==========================================
@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'registration_number', 'vin', 'vehicle_type', 'company', 'status', 'approval_status']
    list_filter = ['status', 'approval_status', 'vehicle_type', 'company', 'year']
    search_fields = ['make', 'model', 'vin', 'registration_number', 'company__company_name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('make', 'model', 'year', 'vin', 'registration_number', 'vehicle_type', 'company')
        }),
        ('Registration Details', {
            'fields': ('registration_expiry', 'inspection_due_date', 'cof_expiry', 'rego_document', 'cof_document')
        }),
        ('Insurance', {
            'fields': ('insurance_company', 'insurance_policy_number', 'insurance_expiry', 'insurance_document')
        }),
        ('Technical Specifications', {
            'fields': ('gross_vehicle_mass', 'tare_weight', 'load_capacity', 'fuel_type')
        }),
        ('Status', {
            'fields': ('status', 'approval_status', 'rejection_reason', 'approved_at', 'approved_by')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:  # New object
            obj.created_by = request.user
        if change and 'approval_status' in form.changed_data:
            if obj.approval_status == 'approved' and not obj.approved_at:
                obj.approved_at = timezone.now()
                obj.approved_by = request.user
        super().save_model(request, obj, form, change)


# ==========================================
# 6. SERVICE ADMIN
# ==========================================
@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['title', 'icon', 'order', 'is_active', 'is_featured', 'created_at']
    list_filter = ['is_active', 'is_featured', 'created_at']
    search_fields = ['title', 'description']
    list_editable = ['order', 'is_active', 'is_featured']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('icon', 'title', 'description')
        }),
        ('Display Settings', {
            'fields': ('order', 'is_active', 'is_featured')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']


# ==========================================
# 7. PRICING PLAN ADMIN
# ==========================================
@admin.register(PricingPlan)
class PricingPlanAdmin(admin.ModelAdmin):
    list_display = ['display_name',  'price', 'price_period', 'is_popular', 'is_active', 'order']
    list_filter = [ 'price_period', 'is_active', 'is_popular']
    search_fields = ['display_name', 'description']
    list_editable = ['price', 'is_popular', 'is_active', 'order']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'display_name', 'description', 'price', 'price_period')
        }),
        ('Features', {
            'fields': ('features', 'disabled_features')
        }),
        ('Display Settings', {
            'fields': ('is_popular', 'is_active', 'order', 'button_text', 'button_class')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def plan_type(self, obj):
        return obj.get_name_display()
    plan_type.short_description = 'Plan Type'


# ==========================================
# 8. COMPANY SUBSCRIPTION ADMIN
# ==========================================
@admin.register(CompanySubscription)
class CompanySubscriptionAdmin(admin.ModelAdmin):
    list_display = ['company', 'plan_display', 'status', 'start_date', 'end_date', 'is_active']
    list_filter = ['status', 'auto_renew', 'plan']
    search_fields = ['company__company_name', 'transaction_id']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Company & Plan', {
            'fields': ('company', 'plan')
        }),
        ('Subscription Dates', {
            'fields': ('start_date', 'end_date', 'last_renewal_date', 'next_renewal_date')
        }),
        ('Payment Details', {
            'fields': ('amount_paid', 'payment_method', 'transaction_id')
        }),
        ('Status', {
            'fields': ('status', 'auto_renew')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def plan_display(self, obj):
        return obj.plan.display_name if obj.plan else 'No Plan'
    plan_display.short_description = 'Plan'
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ==========================================
# 9. SUBSCRIPTION HISTORY ADMIN
# ==========================================
@admin.register(SubscriptionHistory)
class SubscriptionHistoryAdmin(admin.ModelAdmin):
    list_display = ['subscription', 'action', 'old_plan', 'new_plan', 'changed_by', 'changed_at']
    list_filter = ['action', 'changed_at']
    search_fields = ['subscription__company__company_name', 'notes']
    readonly_fields = ['changed_at']
    
    fieldsets = (
        ('Subscription', {
            'fields': ('subscription',)
        }),
        ('Plan Changes', {
            'fields': ('old_plan', 'new_plan')
        }),
        ('Action Details', {
            'fields': ('action', 'notes', 'changed_by')
        }),
        ('Timestamp', {
            'fields': ('changed_at',)
        }),
    )


# ==========================================
# 10. WHY US ADMIN
# ==========================================
class WhyUsFeatureInline(admin.TabularInline):
    model = WhyUsFeature
    extra = 1
    fields = ['icon', 'text', 'order', 'is_active']

@admin.register(WhyUs)
class WhyUsAdmin(admin.ModelAdmin):
    list_display = ['title', 'eyebrow', 'is_active', 'updated_at']
    list_filter = ['is_active']
    search_fields = ['title', 'description', 'eyebrow']
    
    fieldsets = (
        ('Section Settings', {
            'fields': ('eyebrow', 'title', 'description', 'is_active', 'order')
        }),
        ('Video', {
            'fields': ('video_url',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [WhyUsFeatureInline]
    readonly_fields = ['created_at', 'updated_at']


@admin.register(WhyUsFeature)
class WhyUsFeatureAdmin(admin.ModelAdmin):
    list_display = ['text', 'icon', 'why_us', 'order', 'is_active']
    list_filter = ['is_active', 'why_us']
    search_fields = ['text']
    list_editable = ['order', 'is_active']


# ==========================================
# 11. CONTACT MESSAGE ADMIN
# ==========================================
@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'message_preview', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'email', 'message']
    list_editable = ['status']
    
    fieldsets = (
        ('Sender Information', {
            'fields': ('name', 'email', 'message')
        }),
        ('Technical Information', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('status', 'is_agreed')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'ip_address', 'user_agent']
    
    def message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_preview.short_description = 'Message'


# ==========================================
# 12. REVIEW ADMIN
# ==========================================
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['id', 'reviewer_name', 'company', 'star_rating', 'is_approved', 'is_featured', 'created_at']
    list_filter = ['rating', 'is_approved', 'is_featured', 'created_at']
    search_fields = ['reviewer_name', 'review_text', 'company__company_name', 'user__email']
    list_editable = ['is_approved', 'is_featured']
    readonly_fields = ['created_at', 'updated_at']
    
    actions = ['approve_reviews']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('company', 'user', 'rating')
        }),
        ('Review Content', {
            'fields': ('title', 'review_text')
        }),
        ('Reviewer Info', {
            'fields': ('reviewer_name', 'reviewer_role', 'reviewer_company')
        }),
        ('Status', {
            'fields': ('is_approved', 'is_featured')
        }),
        ('Company Response', {
            'fields': ('company_response', 'response_date')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def star_rating(self, obj):
        return obj.star_display
    star_rating.short_description = 'Stars'
    
    def approve_reviews(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'{updated} review(s) approved successfully.')
    approve_reviews.short_description = "Approve selected reviews"


# ==========================================
# 13. FOOTER SETTINGS ADMIN
# ==========================================
@admin.register(FooterSettings)
class FooterSettingsAdmin(admin.ModelAdmin):
    list_display = ['email', 'phone', 'is_active', 'updated_at']
    
    def has_add_permission(self, request):
        # Only allow one instance
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)
    
    fieldsets = (
        ('Contact Information', {
            'fields': ('email', 'phone', 'address')
        }),
        ('Social Links', {
            'fields': ('facebook_url', 'linkedin_url', 'instagram_url', 'twitter_url')
        }),
        ('Content', {
            'fields': ('tagline', 'compliance_logos', 'membership_logos', 'copyright_text')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )


# ==========================================
# 14. SYSTEM SETTINGS ADMIN
# ==========================================
@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ['site_name', 'version', 'environment', 'maintenance_mode', 'updated_at']
    
    def has_add_permission(self, request):
        # Only allow one instance
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)
    
    fieldsets = (
        ('Hero Section', {
            'fields': ('hero_badge', 'hero_title', 'hero_description', 'hero_button_text', 'hero_button_link', 'hero_video_url')
        }),
        ('Trust Indicators', {
            'fields': ('trust_item_1', 'trust_item_2', 'trust_item_3')
        }),
        ('Carousel', {
            'fields': ('carousel_images',)
        }),
        ('System Information', {
            'fields': ('site_name', 'site_tagline', 'version', 'environment')
        }),
        ('Notification Settings', {
            'fields': ('email_notifications', 'new_registration_alerts', 'incident_notifications', 'compliance_reminders', 'maintenance_mode')
        }),
        ('System Status', {
            'fields': ('last_backup', 'database_status', 'uptime')
        }),
    )
    
    readonly_fields = ['updated_at']


# ==========================================
# 15. ADMIN PROFILE ADMIN
# ==========================================
@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'phone', 'location']
    search_fields = ['user__email', 'user__full_name', 'role']
    
    fieldsets = (
        ('User Association', {
            'fields': ('user',)
        }),
        ('Profile Information', {
            'fields': ('role', 'phone', 'location')
        }),
    )


# ==========================================
# 16. COMPANY FLEET ADMIN (Standalone)
# ==========================================
@admin.register(CompanyFleet)
class CompanyFleetAdmin(admin.ModelAdmin):
    list_display = ['company', 'total_vehicles', 'max_gvm', 'average_vehicle_age']
    search_fields = ['company__company_name']
    readonly_fields = ['flat_nhvr_configs']


# ==========================================
# 17. RISK HAZARD ADMIN (Standalone)
# ==========================================
@admin.register(RiskHazard)
class RiskHazardAdmin(admin.ModelAdmin):
    list_display = ['hazard_description', 'company', 'likelihood', 'consequence']
    list_filter = ['likelihood', 'consequence']
    search_fields = ['hazard_description', 'company__company_name']


# ==========================================
# 18. SUBCONTRACTOR RECORD ADMIN (Standalone)
# ==========================================
@admin.register(SubcontractorRecord)
class SubcontractorRecordAdmin(admin.ModelAdmin):
    list_display = ['subcontractor_name', 'company', 'abn', 'licence_type', 'contract_expiry']
    list_filter = ['company']
    search_fields = ['subcontractor_name', 'abn', 'company__company_name']
    date_hierarchy = 'contract_expiry'


# ==========================================
# 19. INCIDENT RECORD ADMIN (Standalone)
# ==========================================
@admin.register(IncidentRecord)
class IncidentRecordAdmin(admin.ModelAdmin):
    list_display = ['incident_type', 'company', 'incident_date', 'description_preview']
    list_filter = ['incident_type', 'company', 'incident_date']
    search_fields = ['description', 'outcome', 'company__company_name']
    date_hierarchy = 'incident_date'
    
    def description_preview(self, obj):
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
    description_preview.short_description = 'Description'


# ==========================================
# 20. OTHER PROFILE MODELS ADMIN (Optional)
# ==========================================
@admin.register(CompanyOperation)
class CompanyOperationAdmin(admin.ModelAdmin):
    list_display = ['company', 'num_drivers', 'operating_hours']
    search_fields = ['company__company_name']


@admin.register(CompanyRiskProfile)
class CompanyRiskProfileAdmin(admin.ModelAdmin):
    list_display = ['company', 'safety_policies_count']
    search_fields = ['company__company_name']
    
    def safety_policies_count(self, obj):
        return len(obj.safety_policies) if obj.safety_policies else 0
    safety_policies_count.short_description = 'Safety Policies'


@admin.register(CompanySubcontractorProfile)
class CompanySubcontractorProfileAdmin(admin.ModelAdmin):
    list_display = ['company', 'engages_subcontractors', 'active_subcontractors', 'primary_engagement_type']
    list_filter = ['engages_subcontractors']
    search_fields = ['company__company_name']


@admin.register(CompanyIncidentProfile)
class CompanyIncidentProfileAdmin(admin.ModelAdmin):
    list_display = ['company', 'incidents_last_12_months', 'incidents_last_3_years', 'injuries_resulting']
    search_fields = ['company__company_name']