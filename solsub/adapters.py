from allauth.account.adapter import DefaultAccountAdapter
from django_otp.plugins.otp_totp.models import TOTPDevice

class CustomAccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        user = request.user
        if not TOTPDevice.objects.filter(user=user, confirmed=True).exists():
            return '/setup-2fa/'
        return '/'  # or your desired default redirect 

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'http' 
