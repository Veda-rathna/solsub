"""
URL configuration for solsub project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('', views.home, name='home'),
    path('cluster-details/', views.cluster_details, name='cluster_details'),
    path('create-cluster/', views.create_cluster, name='create_cluster'),
    path('add-bank-details/<int:cluster_index>/', views.add_bank_details_for_cluster, name='add_bank_details_for_cluster'),
    path('setup-2fa/', views.setup_2fa, name='setup_2fa'),
    path('verify-2fa/', views.verify_2fa, name='verify_2fa'),
    path('verify-2fa-login/', views.verify_2fa_login, name='verify_2fa_login'),
    path('test-protected/', views.test_protected_view, name='test_protected'),
    path('backup-codes/generate/', views.generate_backup_codes, name='generate_backup_codes'),
    path('backup-codes/verify/', views.verify_backup_code, name='verify_backup_code'),
    path('cluster/create/', views.create_cluster, name='create_cluster'),
    path('bank-details/', views.add_bank_details, name='add_bank_details'),
]

