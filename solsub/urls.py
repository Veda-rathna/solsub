from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('', views.index, name='index'),
    path('dashboard/', views.home, name='home'),
    path('pay/', views.pay, name='pay'),
    path('get-clusters/', views.get_existing_clusters, name='get_clusters'),
    path('get-pricing/', views.get_pricing, name='get_pricing'),
    path('check-cluster-name/', views.check_cluster_name, name='check_cluster_name'),
    path('check-match-id/', views.check_match_id, name='check_match_id'),
    path('generate-match-id/', views.generate_match_id, name='generate_match_id'),
    path('cluster-details/', views.cluster_details, name='cluster_details'),
    path('create-cluster/', views.create_cluster, name='create_cluster'),
    path('setup-2fa/', views.setup_2fa, name='setup_2fa'),
    path('cluster/create/', views.create_cluster, name='create_cluster'),
    path('bank-details/', views.add_bank_details, name='add_bank_details'),
    path('bank-details/', views.bank_details, name='bank_details'),
    path('create-user-match-id/', views.create_user_match_id, name='create_user_match_id'),
    
    #2FA routes
    path('verify-2fa/', views.verify_2fa, name='verify_2fa'),
    path('verify-2fa-login/', views.verify_2fa_login, name='verify_2fa_login'),
    path('test-protected/', views.test_protected_view, name='test_protected'),
    path('backup-codes/generate/', views.generate_backup_codes, name='generate_backup_codes'),
    path('backup-codes/verify/', views.verify_backup_code, name='verify_backup_code'), 
]

