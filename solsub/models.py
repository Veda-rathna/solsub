from django.db import models
from django.contrib.auth.models import User
from django.utils.crypto import get_random_string
import secrets

class Cluster(models.Model):
    cluster_name = models.CharField(max_length=255, unique=True)
    cluster_id = models.CharField(max_length=100, unique=True)
    cluster_price = models.DecimalField(max_digits=10, decimal_places=2)
    cluster_timeline = models.CharField(max_length=255)
    api_key = models.CharField(max_length=32, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.api_key:
            # Generate a unique API key
            while True:
                key = secrets.token_hex(16)
                if not Cluster.objects.filter(api_key=key).exists():
                    self.api_key = key
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return self.cluster_name

class BackupCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=10)
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def generate_codes(cls, user, count=10):
        # Delete existing unused codes
        cls.objects.filter(user=user, used=False).delete()
        
        # Generate new codes
        codes = []
        for _ in range(count):
            code = cls.objects.create(
                user=user,
                code=get_random_string(8)
            )
            codes.append(code)
        return codes

