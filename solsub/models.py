from django.db import models
from django.contrib.auth.models import User
from django.utils.crypto import get_random_string
import secrets
from django.core import validators

class Cluster(models.Model):
    cluster_name = models.CharField(max_length=255, unique=True)
    cluster_id = models.CharField(max_length=100, unique=True)
    cluster_price = models.DecimalField(max_digits=10, decimal_places=2)
    timeline_days = models.IntegerField(default=30, validators=[
        validators.MinValueValidator(1),
        validators.MaxValueValidator(30)
    ])
    api_key = models.CharField(max_length=32, unique=True, blank=True)
    trial_period = models.IntegerField(default=0, validators=[
        validators.MinValueValidator(0),
        validators.MaxValueValidator(7)
    ])

    def save(self, *args, **kwargs):
        if not self.api_key:
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
        cls.objects.filter(user=user, used=False).delete()
        return [cls.objects.create(user=user, code=get_random_string(8)) for _ in range(count)]