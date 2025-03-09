from django.shortcuts import redirect
from django.urls import reverse
from django_otp.plugins.otp_totp.models import TOTPDevice

class Require2FAMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            exempt_paths = [
                reverse('setup_2fa'),  # Notice the underscore
                reverse('verify_2fa'),
                reverse('verify_2fa_login'),
                reverse('verify_backup_code'),
                reverse('generate_backup_codes'),
                '/admin/',
            ]

            if not any(request.path.startswith(path) for path in exempt_paths):
                device = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
                
                if not device:
                    return redirect('setup_2fa')  # Notice the underscore
                
                if not request.session.get('2fa_verified'):
                    return redirect('verify_2fa_login')

        response = self.get_response(request)
        return response
