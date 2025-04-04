from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.contrib.auth.decorators import login_required
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.util import random_hex
import qrcode
import qrcode.image.svg
from io import BytesIO
import base64
from .models import BackupCode, Cluster
from django.contrib import messages
from .mongo_models import UserProfile, ClusterDetails, BankDetails, MatchId
from django_otp import devices_for_user
from datetime import datetime, timedelta
import uuid
import secrets

def index(request):
    """
    View for the landing page
    """
    return render(request, "index.html")

@csrf_exempt
def get_pricing(request):
    cluster_name = request.GET.get('cluster_name')

    if not cluster_name:
        return JsonResponse({'success': False, 'error': 'Cluster name is required'}, status=400)

    user = UserProfile.objects(clusters__cluster_name=cluster_name).first()

    if user:
        cluster = next((c for c in user.clusters if c.cluster_name == cluster_name), None)
        if cluster:
            return JsonResponse({
                'success': True,
                'cluster_name': cluster.cluster_name,
                'price': str(cluster.cluster_price),
                'timeline': cluster.cluster_timeline,
                'api_key': cluster.api_key
            })
    
    return JsonResponse({'success': False, 'error': 'Cluster not found'}, status=404)

@csrf_exempt
def check_match_id(request):
    match_id = request.GET.get('match_id', '')
    
    if not match_id:
        return JsonResponse({'success': False, 'error': 'Match ID is required'}, status=400)
    
    match_id_obj = MatchId.objects(match_id=match_id).first()
    
    if match_id_obj:
        user = UserProfile.objects(clusters__cluster_name=match_id_obj.cluster_name).first()
        if user:
            cluster = next((c for c in user.clusters if c.cluster_name == match_id_obj.cluster_name), None)
            if cluster:
                timeline = cluster.cluster_timeline
                days_valid = int(timeline.split()[0]) if timeline and timeline.split()[0].isdigit() else 30
                expiry_date = match_id_obj.timestamp + timedelta(days=days_valid)
                is_active = datetime.now() < expiry_date
                
                return JsonResponse({
                    'success': True,
                    'exists': True,
                    'is_active': is_active,
                    'status': 'Active' if is_active else 'Inactive',
                    'cluster_name': match_id_obj.cluster_name,
                    'price': str(cluster.cluster_price),
                    'timeline': cluster.cluster_timeline,
                    'api_key': match_id_obj.api_key,  # Use the api_key from MatchId
                    'last_paid_date': match_id_obj.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                })
    
    return JsonResponse({
        'success': True,
        'exists': False,
        'status': 'Inactive',
        'is_active': False,
        'last_paid_date': '-'
    })
@csrf_exempt
def generate_match_id(request):
    """
    Generate a new match ID for a cluster
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST method is allowed'}, status=405)
    
    data = json.loads(request.body)
    cluster_name = data.get('cluster_name', '')
    
    if not cluster_name:
        return JsonResponse({'success': False, 'error': 'Cluster name is required'}, status=400)
    
    # Check if the cluster exists
    user = UserProfile.objects(clusters__cluster_name=cluster_name).first()
    if not user:
        return JsonResponse({'success': False, 'error': 'Cluster not found'}, status=404)
    
    # Find the exact cluster from the user's list of clusters
    cluster = next((c for c in user.clusters if c.cluster_name == cluster_name), None)
    if not cluster:
        return JsonResponse({'success': False, 'error': 'Cluster not found'}, status=404)
    
    # Extract the timeline value (assuming it's in the format "X days")
    timeline = cluster.cluster_timeline
    days_valid = int(timeline.split()[0]) if timeline and timeline.split()[0].isdigit() else 30
    
    # Generate a new match ID
    new_match_id = str(uuid.uuid4())[:8].upper()
    
    # Create a new MatchId document, including the api_key
    match_id_obj = MatchId(
        match_id=new_match_id,
        cluster_name=cluster_name,
        timestamp=datetime.now(),
        days_valid=days_valid,
        api_key=cluster.api_key  # Include the api_key from the cluster
    )
    match_id_obj.save()
    
    return JsonResponse({
        'success': True,
        'match_id': new_match_id,
        'is_active': True,
        'api_key': cluster.api_key  # Optionally return the api_key in the response
    })

def check_cluster_name(request):
    """
    AJAX endpoint to check if a cluster name exists in the entire database
    """
    cluster_name = request.GET.get('cluster_name', '')

    # Check in Django model (PostgreSQL)
    django_exists = Cluster.objects.filter(cluster_name=cluster_name).exists()

    # Check in MongoDB (across all users, not just one user)
    mongo_exists = UserProfile.objects(clusters__cluster_name=cluster_name).first() is not None

    exists = django_exists or mongo_exists

    return JsonResponse({'exists': exists})


def get_existing_clusters(request):
    clusters = Cluster.objects.values_list('name', flat=True)
    return JsonResponse({"clusters": list(clusters)})

def pay(request):
    """
    View for the payment page
    """
    return render(request, "pay.html")

@login_required
def home(request):
    user_profile = UserProfile.objects(user_id=str(request.user.id)).first()
    if not user_profile:
        user_profile = UserProfile(
            user_id=str(request.user.id),
            email=request.user.email,
            username=request.user.username
        ).save()
    
    return render(request, "home.html", {
        "clusters": user_profile.clusters,
        "bank_details": user_profile.bank_details
    })

def cluster_details(request):
    return render(request, 'cluster_details.html')

@login_required
def bank_details(request):
    user_profile = UserProfile.objects(user_id=str(request.user.id)).first()
    
    return render(request, 'bank_details.html', {
        "bank_details": user_profile.bank_details if user_profile else None
    })

@login_required
def create_cluster(request):
    if request.method == "POST":
        cluster_name = request.POST.get("cluster_name")
        
        # Check if cluster name already exists in Django model
        django_exists = Cluster.objects.filter(cluster_name=cluster_name).exists()
        
        # Check if cluster name already exists in MongoDB model
        mongo_exists = UserProfile.objects(clusters__cluster_name=cluster_name).first() is not None
        
        if django_exists or mongo_exists:
            messages.error(request, f"Cluster name '{cluster_name}' already exists. Please choose a different name.")
            return render(request, "cluster_details.html", {
                'error': f"Cluster name '{cluster_name}' already exists.",
                'cluster_name': cluster_name,
                'cluster_price': request.POST.get("cluster_price"),
                'cluster_timeline': request.POST.get("cluster_timeline")
            })
        
        # Generate a unique api_key
        while True:
            api_key = secrets.token_hex(16)
            if not UserProfile.objects(clusters__api_key=api_key).first():
                break

        cluster_data = {
            "cluster_name": cluster_name,
            "cluster_price": float(request.POST.get("cluster_price")),
            "cluster_timeline": request.POST.get("cluster_timeline"),
            "api_key": api_key  # Include the api_key in the cluster_data
        }

        user_profile = UserProfile.objects(user_id=str(request.user.id)).first()
        if not user_profile:
            user_profile = UserProfile(
                user_id=str(request.user.id),
                email=request.user.email,
                username=request.user.username
            ).save()

        user_profile.add_cluster(cluster_data)
        
        # Also save to Django model for consistency, including the api_key
        cluster = Cluster(
            cluster_name=cluster_name,
            cluster_id=f"cluster_{cluster_name}",
            cluster_price=request.POST.get("cluster_price"),
            cluster_timeline=request.POST.get("cluster_timeline"),
            api_key=api_key  # Set the same api_key in the Django model
        )
        cluster.save()
        
        messages.success(request, f"Cluster '{cluster_name}' created successfully.")
        return redirect("home")

    return render(request, "cluster_details.html")

@login_required
def bank_details(request):
    return render(request, 'bank_details.html')

@login_required
def add_bank_details(request):
    user_profile = UserProfile.objects(user_id=str(request.user.id)).first()
    
    if request.method == "POST":
        # Get the user profile
        if not user_profile:
            user_profile = UserProfile(
                user_id=str(request.user.id),
                email=request.user.email,
                username=request.user.username
            )

        # Create bank details
        bank_details = BankDetails(
            bank_name=request.POST.get('bank_name'),
            account_number=request.POST.get('account_number'),
            ifsc_code=request.POST.get('ifsc_code'),
            branch_name=request.POST.get('branch_name')
        )

        # Update user profile
        user_profile.bank_details = bank_details
        user_profile.save()
        
        messages.success(request, "Bank details saved successfully!")
        return redirect('home')

    return render(request, "bank_details.html", {
        "bank_details": user_profile.bank_details if user_profile else None
    })

@login_required
def setup_2fa(request):
    # Delete any existing TOTP devices for this user
    TOTPDevice.objects.filter(user=request.user).delete()
    
    # Create a new TOTP device
    device = TOTPDevice.objects.create(
        user=request.user,
        name=f"Default device for {request.user.email}",
        confirmed=False
    )
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    
    # Create the provisioning URI
    provisioning_uri = device.config_url
    
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    
    # Create QR code image
    img_buffer = BytesIO()
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(img_buffer, format='PNG')
    img_str = base64.b64encode(img_buffer.getvalue()).decode()
    
    # Generate backup codes
    backup_codes = BackupCode.generate_codes(request.user, count=10)
    
    context = {
        'qr_code': img_str,
        'secret_key': device.key,
        'backup_codes': backup_codes,
    }
    
    return render(request, '2fa/setup.html', context)


@login_required
def verify_2fa(request):
    if request.method == 'POST':
        token = request.POST.get('token')
        
        # Get the unconfirmed device
        device = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()
        
        if device is None:
            return redirect('setup_2fa')
        
        if device.verify_token(token):
            device.confirmed = True
            device.save()
            return redirect('/')  # Redirect to home page after successful verification
        else:
            return render(request, '2fa/verify.html', {'error': 'Invalid token'})
    
    return render(request, '2fa/verify.html')

@login_required
def verify_2fa_login(request):
    if request.method == 'POST':
        token = request.POST.get('token')
        device = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
        
        if device and device.verify_token(token):
            request.session['2fa_verified'] = True
            return redirect(request.session.get('next', '/'))
        else:
            return render(request, '2fa/login_verify.html', {'error': 'Invalid token'})
    
    request.session['next'] = request.GET.get('next', '/')
    return render(request, '2fa/login_verify.html')

@login_required
def test_protected_view(request):
    return HttpResponse(
        f"Hello {request.user.email}!<br>"
        f"2FA Status: {'Verified' if request.session.get('2fa_verified') else 'Not Verified'}<br>"
        f"Authentication Method: {'Google' if request.user.socialaccount_set.exists() else 'Standard'}"
    )

@login_required
def generate_backup_codes(request):
    if request.method == 'POST':
        codes = BackupCode.generate_codes(request.user)
        return render(request, 'account/backup_codes.html', {'codes': codes})
    return render(request, 'account/backup_codes_confirm.html')

@login_required
def verify_backup_code(request):
    if request.method == 'POST':
        code = request.POST.get('backup_code')
        backup_code = BackupCode.objects.filter(
            user=request.user,
            code=code,
            used=False
        ).first()
        
        if backup_code:
            # Mark code as used
            backup_code.used = True
            backup_code.save()
            
            # Disable current 2FA device
            devices = TOTPDevice.objects.filter(user=request.user)
            for device in devices:
                device.delete()
            
            messages.success(request, 'Backup code accepted. Please set up 2FA again.')
            return redirect('setup_2fa')  # Notice the underscore
        
        messages.error(request, 'Invalid backup code.')
    return render(request, 'account/verify_backup_code.html')

