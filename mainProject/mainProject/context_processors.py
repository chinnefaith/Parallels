from django.conf import settings


def branding(request):
    return {
        'seastem_logo': settings.SEASTEM_LOGO,
    }
