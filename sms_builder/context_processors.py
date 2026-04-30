# sms_builder/context_processors.py

from .models import SystemSettings, FooterSettings

def system_settings(request):
    """Add system settings to all templates"""
    try:
        settings = SystemSettings.objects.first()
        if not settings:
            settings = SystemSettings.objects.create()
    except:
        settings = None
    
    return {
        'system_settings': settings,
    }

def footer_settings(request):
    """Add footer settings to all templates"""
    try:
        footer = FooterSettings.objects.first()
        if not footer:
            footer = FooterSettings.objects.create()
    except:
        footer = None
    
    return {
        'footer_settings': footer,
    }