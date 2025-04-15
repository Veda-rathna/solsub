from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django_otp.plugins.otp_totp.models import TOTPDevice
from django.contrib import messages
from .models import BackupCode, Cluster
from .mongo_models import UserProfile, BankDetails, MatchId
from datetime import datetime, timedelta
import json
import qrcode
import base64
from io import BytesIO
import uuid
import secrets
import logging

logger = logging.getLogger(__name__)

# ----------------------
# Helper Functions
# ----------------------

def _get_cluster_from_user(cluster_name):
    """Retrieve cluster from UserProfile by cluster_name."""
    user = UserProfile.objects(clusters__cluster_name=cluster_name).first()
    if not user:
        return None, None
    cluster = next((c for c in user.clusters if c.cluster_name == cluster_name), None)
    return user, cluster

def _create_match_id(cluster_name, match_id=None, is_user_defined=False, is_admin_created=False):
    """Create a new MatchId object."""
    user, cluster = _get_cluster_from_user(cluster_name)
    if not user or not cluster:
        return None, JsonResponse({'success': False, 'error': 'Cluster not found'}, status=404)

    # Allow admin-created Match IDs to bypass user-defined restrictions
    if is_user_defined and not is_admin_created and getattr(cluster, 'match_id_type', 'admin_generated') != 'user_created':
        return None, JsonResponse({'success': False, 'error': 'User-created match IDs not allowed'}, status=403)

    now = datetime.now()
    trial_period = getattr(cluster, 'trial_period', 0)
    match_id = match_id or str(uuid.uuid4())[:8].upper()

    if MatchId.objects(match_id=match_id).first():
        return None, JsonResponse({
            'success': True, 'match_id': match_id, 'exists': True,
            'message': 'Match ID already exists and is ready to use'
        })

    match_id_obj = MatchId(
        match_id=match_id,
        cluster_name=cluster_name,
        created_on=now,
        last_paid_on=now,
        valid_till=now + timedelta(days=trial_period) if trial_period > 0 else None,
        is_trial=trial_period > 0
    )

    if match_id_obj.is_trial and not match_id_obj.valid_till:
        logger.error("Cannot create MatchId with is_trial=True and valid_till=None")
        return None, JsonResponse({'success': False, 'error': 'Invalid MatchId state'}, status=400)

    match_id_obj.save()
    return match_id_obj, None

def _build_match_id_response(match_id_obj, cluster):
    """Build JSON response for MatchId details."""
    now = datetime.now()
    trial_period = getattr(cluster, 'trial_period', 0)
    trial_end_date = match_id_obj.created_on + timedelta(days=trial_period) if trial_period > 0 else None

    if match_id_obj.is_trial and trial_end_date and now > trial_end_date:
        match_id_obj.is_trial = False
        match_id_obj.save()

    is_active = match_id_obj.valid_till and now <= match_id_obj.valid_till
    status = ("Trial Active" if is_active and match_id_obj.is_trial and now <= trial_end_date else
              "Paid Active" if is_active and not match_id_obj.is_trial else "Inactive")

    response = {
        'success': True,
        'match_id': match_id_obj.match_id,  # Explicitly include match_id
        'exists': True,
        'is_active': is_active,
        'status': status,
        'cluster_name': match_id_obj.cluster_name,
        'price': str(cluster.cluster_price),
        'timeline': f"{cluster.timeline_days} days",
        'created_on': match_id_obj.created_on.strftime('%Y-%m-%d')
    }

    if match_id_obj.valid_till:
        response['valid_till'] = match_id_obj.valid_till.strftime('%Y-%m-%d')
    if match_id_obj.last_paid_on:
        response['last_paid_on'] = match_id_obj.last_paid_on.strftime('%Y-%m-%d')
    if match_id_obj.is_trial and trial_end_date:
        response['trial_days'] = trial_period
        response['trial_end_date'] = trial_end_date.strftime('%Y-%m-%d')

    return JsonResponse(response)

# ----------------------
# Public Views
# ----------------------

def index(request):
    return render(request, "index.html")

def pay(request):
    return render(request, "pay.html")

def cluster_details(request):
    return render(request, 'cluster_details.html')

# ----------------------
# API Endpoints
# ----------------------

@csrf_exempt
def get_cluster_details(request):
    cluster_name = request.GET.get('cluster_name', '')
    if not cluster_name:
        return JsonResponse({'success': False, 'error': 'Cluster name is required'}, status=400)

    user, cluster = _get_cluster_from_user(cluster_name)
    if not user or not cluster:
        if Cluster.objects.filter(cluster_name=cluster_name).exists():
            return JsonResponse({'success': False, 'error': 'Cluster found in Django but not MongoDB'}, status=500)
        return JsonResponse({'success': True, 'exists': False})

    return JsonResponse({
        'success': True,
        'exists': True,
        'cluster_name': cluster.cluster_name,
        'price': str(cluster.cluster_price),
        'timeline': f"{cluster.timeline_days} days",
        'api_key': cluster.api_key,
        'match_id_type': getattr(cluster, 'match_id_type', 'admin_generated'),
        'trial_period': getattr(cluster, 'trial_period', 0)
    })

@csrf_exempt
def check_match_id(request):
    match_id = request.GET.get('match_id', '')
    if not match_id:
        return JsonResponse({'success': False, 'error': 'Match ID is required'}, status=400)

    match_id_obj = MatchId.objects(match_id=match_id).first()
    if not match_id_obj:
        return JsonResponse({
            'success': True,
            'exists': False,
            'status': 'Inactive',
            'is_active': False,
            'created_on': '-'
        })

    user, cluster = _get_cluster_from_user(match_id_obj.cluster_name)
    if not user or not cluster:
        return JsonResponse({
            'success': True,
            'exists': True,
            'is_active': False,
            'status': 'Inactive',
            'cluster_name': match_id_obj.cluster_name,
            'created_on': match_id_obj.created_on.strftime('%Y-%m-%d')
        })

    if match_id_obj.is_trial and not match_id_obj.valid_till:
        logger.warning(f"Inconsistent MatchId {match_id}: is_trial=True but valid_till is None")
        return JsonResponse({
            'success': False,
            'error': 'Invalid MatchId state: Trial period indicated but no expiry date set',
            'exists': True,
            'is_active': False,
            'status': 'Invalid',
            'cluster_name': match_id_obj.cluster_name,
            'created_on': match_id_obj.created_on.strftime('%Y-%m-%d')
        }, status=400)

    return _build_match_id_response(match_id_obj, cluster)

@csrf_exempt
def generate_match_id(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST method is allowed'}, status=405)

    try:
        data = json.loads(request.body)
        cluster_name = data.get('cluster_name', '')
        match_id = data.get('match_id', '')
        if not cluster_name:
            return JsonResponse({'success': False, 'error': 'Cluster name is required'}, status=400)
        if not match_id:
            return JsonResponse({'success': False, 'error': 'Match ID is required'}, status=400)

        match_id_obj, error_response = _create_match_id(cluster_name, match_id)
        if error_response:
            return error_response

        response = {
            'success': True,
            'match_id': match_id_obj.match_id,
            'is_active': bool(match_id_obj.valid_till),
            'status': 'Trial Active' if match_id_obj.is_trial else 'Inactive',
            'created_on': match_id_obj.created_on.strftime('%Y-%m-%d')
        }

        if match_id_obj.valid_till:
            response['valid_till'] = match_id_obj.valid_till.strftime('%Y-%m-%d')
        if match_id_obj.is_trial:
            response['trial_days'] = getattr(_get_cluster_from_user(cluster_name)[1], 'trial_period', 0)

        return JsonResponse(response)
    except Exception as e:
        logger.error(f"Error generating match ID: {str(e)}")
        return JsonResponse({'success': False, 'error': 'Error generating match ID'}, status=500)

@csrf_exempt
def create_user_match_id(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST method is allowed'}, status=405)

    try:
        data = json.loads(request.body)
        cluster_name = data.get('cluster_name', '')
        match_id = data.get('match_id', '')
        is_admin_created = data.get('is_admin_created', False)  # New flag from frontend
        if not cluster_name:
            return JsonResponse({'success': False, 'error': 'Cluster name is required'}, status=400)

        # Allow empty match_id for admin auto-generation
        if not match_id and is_admin_created:
            match_id = str(uuid.uuid4())[:8].upper()

        match_id_obj, error_response = _create_match_id(cluster_name, match_id, is_user_defined=not is_admin_created, is_admin_created=is_admin_created)
        if error_response:
            return error_response

        user, cluster = _get_cluster_from_user(cluster_name)
        response = _build_match_id_response(match_id_obj, cluster).content.decode('utf-8')
        return JsonResponse(json.loads(response) | {'match_id': match_id_obj.match_id})
    except Exception as e:
        logger.error(f"Error creating match ID: {str(e)}")
        return JsonResponse({'success': False, 'error': 'Error creating match ID'}, status=500)

@csrf_exempt
def process_payment(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST method is allowed'}, status=405)

    try:
        data = json.loads(request.body)
        match_id = data.get('match_id', '')
        cluster_name = data.get('cluster_name', '')
        if not match_id or not cluster_name:
            return JsonResponse({'success': False, 'error': 'Match ID and Cluster name are required'}, status=400)

        match_id_obj = MatchId.objects(match_id=match_id).first()
        if not match_id_obj:
            return JsonResponse({'success': False, 'error': 'Match ID not found'}, status=404)

        user, cluster = _get_cluster_from_user(cluster_name)
        if not user or not cluster:
            return JsonResponse({'success': False, 'error': 'Cluster not found'}, status=404)

        now = datetime.now()
        match_id_obj.last_paid_on = now

        if match_id_obj.is_trial and match_id_obj.valid_till and now < match_id_obj.valid_till:
            match_id_obj.valid_till = match_id_obj.valid_till + timedelta(days=cluster.timeline_days)
        else:
            match_id_obj.is_trial = False
            match_id_obj.valid_till = now + timedelta(days=cluster.timeline_days)

        match_id_obj.save()

        return JsonResponse({
            'success': True,
            'match_id': match_id,
            'is_trial': match_id_obj.is_trial,
            'status': 'Trial Active' if match_id_obj.is_trial else 'Paid Active',
            'last_paid_on': match_id_obj.last_paid_on.strftime('%Y-%m-%d'),
            'valid_till': match_id_obj.valid_till.strftime('%Y-%m-%d')
        })
    except Exception as e:
        logger.error(f"Error processing payment: {str(e)}")
        return JsonResponse({'success': False, 'error': 'Error processing payment'}, status=500)

@csrf_exempt
def get_existing_clusters(request):
    return JsonResponse({"clusters": list(Cluster.objects.values_list('cluster_name', flat=True))})

@csrf_exempt
def check_cluster_name(request):
    cluster_name = request.GET.get('cluster_name', '')
    if not cluster_name:
        return JsonResponse({'success': False, 'error': 'Cluster name is required'}, status=400)

    exists = (UserProfile.objects(clusters__cluster_name=cluster_name).first() is not None or
              Cluster.objects.filter(cluster_name=cluster_name).exists())
    return JsonResponse({'success': True, 'exists': exists})

# ----------------------
# Protected Views
# ----------------------

@login_required
def home(request):
    user_profile = UserProfile.objects(user_id=str(request.user.id)).first()
    if not user_profile:
        user_profile = UserProfile(user_id=str(request.user.id), email=request.user.email, username=request.user.username).save()
    return render(request, "home.html", {"clusters": user_profile.clusters, "bank_details": user_profile.bank_details})

@login_required
def bank_details(request):
    user_profile = UserProfile.objects(user_id=str(request.user.id)).first()
    if request.method != "POST":
        return render(request, "bank_details.html", {"bank_details": user_profile.bank_details if user_profile else None})

    try:
        if not user_profile:
            user_profile = UserProfile(user_id=str(request.user.id), email=request.user.email, username=request.user.username)
        user_profile.bank_details = BankDetails(
            bank_name=request.POST.get('bank_name'),
            account_number=request.POST.get('account_number'),
            ifsc_code=request.POST.get('ifsc_code'),
            branch_name=request.POST.get('branch_name')
        )
        user_profile.save()
        messages.success(request, "Bank details saved successfully!")
        return redirect('home')
    except Exception as e:
        logger.error(f"Error saving bank details: {str(e)}")
        messages.error(request, "Error saving bank details")
        return render(request, "bank_details.html", {"bank_details": user_profile.bank_details if user_profile else None})

@login_required
def create_cluster(request):
    if request.method != "POST":
        return render(request, "cluster_details.html")

    cluster_name = request.POST.get("cluster_name")
    match_id_type = request.POST.get("match_id_type", "admin_generated")

    try:
        trial_period = int(request.POST.get("trial_period", 0))
        if not 0 <= trial_period <= 7:
            raise ValueError("Trial period must be between 0 and 7 days")
    except ValueError:
        messages.error(request, "Trial period must be between 0 and 7 days")
        return render(request, "cluster_details.html", {'cluster_name': cluster_name})

    try:
        timeline_days = int(request.POST.get("timeline_days", 0))
        if not 1 <= timeline_days <= 30:
            raise ValueError("Timeline days must be between 1 and 30 days")
    except ValueError:
        messages.error(request, "Timeline days must be between 1 and 30 days")
        return render(request, "cluster_details.html", {'cluster_name': cluster_name})

    if (Cluster.objects.filter(cluster_name=cluster_name).exists() or
            UserProfile.objects(clusters__cluster_name=cluster_name).first()):
        messages.error(request, f"Cluster name '{cluster_name}' already exists")
        return render(request, "cluster_details.html", {'cluster_name': cluster_name})

    try:
        cluster_price = float(request.POST.get("cluster_price", 0))
        if cluster_price < 0:
            raise ValueError("Price cannot be negative")
    except ValueError:
        messages.error(request, "Invalid price value")
        return render(request, "cluster_details.html", {'cluster_name': cluster_name})

    api_key = secrets.token_hex(16)
    for _ in range(10):
        if not UserProfile.objects(clusters__api_key=api_key).first():
            break
        api_key = secrets.token_hex(16)
    else:
        messages.error(request, "Failed to generate a unique API key")
        return render(request, "cluster_details.html", {'cluster_name': cluster_name})

    cluster_data = {
        "cluster_name": cluster_name,
        "cluster_price": cluster_price,
        "timeline_days": timeline_days,
        "api_key": api_key,
        "match_id_type": match_id_type,
        "trial_period": trial_period
    }

    try:
        user_profile = UserProfile.objects(user_id=str(request.user.id)).first()
        if not user_profile:
            user_profile = UserProfile(user_id=str(request.user.id), email=request.user.email, username=request.user.username).save()
        user_profile.add_cluster(cluster_data)
        Cluster(
            cluster_name=cluster_name,
            cluster_id=f"cluster_{cluster_name}",
            cluster_price=cluster_price,
            timeline_days=timeline_days,
            api_key=api_key,
            trial_period=trial_period
        ).save()
        messages.success(request, f"Cluster '{cluster_name}' created successfully")
        return redirect("home")
    except Exception as e:
        logger.error(f"Error creating cluster: {str(e)}")
        messages.error(request, "Error creating cluster")
        return render(request, "cluster_details.html", {'cluster_name': cluster_name})

# ----------------------
# 2FA Views
# ----------------------

@login_required
def setup_2fa(request):
    TOTPDevice.objects.filter(user=request.user).delete()
    device = TOTPDevice.objects.create(user=request.user, name=f"Default device for {request.user.email}", confirmed=False)
    
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(device.config_url)
    qr.make(fit=True)
    
    img_buffer = BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(img_buffer, format='PNG')
    
    return render(request, '2fa/setup.html', {
        'qr_code': base64.b64encode(img_buffer.getvalue()).decode(),
        'secret_key': device.key,
        'backup_codes': BackupCode.generate_codes(request.user)
    })

@login_required
def verify_2fa(request):
    if request.method != 'POST':
        return render(request, '2fa/verify.html')

    token = request.POST.get('token')
    device = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()
    
    if device and device.verify_token(token):
        device.confirmed = True
        device.save()
        return redirect('/')
    
    return render(request, '2fa/verify.html', {'error': 'Invalid token' if device else 'Setup required'})

@login_required
def verify_2fa_login(request):
    if request.method != 'POST':
        request.session['next'] = request.GET.get('next', '/')
        return render(request, '2fa/login_verify.html')

    token = request.POST.get('token')
    device = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
    
    if device and device.verify_token(token):
        request.session['2fa_verified'] = True
        return redirect(request.session.get('next', '/'))
    
    return render(request, '2fa/login_verify.html', {'error': 'Invalid token'})

@login_required
def generate_backup_codes(request):
    if request.method != 'POST':
        return render(request, 'account/backup_codes_confirm.html')
    
    codes = BackupCode.generate_codes(request.user)
    return render(request, 'account/backup_codes.html', {'codes': codes})

@login_required
def verify_backup_code(request):
    if request.method != 'POST':
        return render(request, 'account/verify_backup_code.html')

    code = request.POST.get('backup_code')
    backup_code = BackupCode.objects.filter(user=request.user, code=code, used=False).first()
    
    if backup_code:
        backup_code.used = True
        backup_code.save()
        TOTPDevice.objects.filter(user=request.user).delete()
        messages.success(request, 'Backup code accepted. Please set up 2FA again.')
        return redirect('setup_2fa')
    
    messages.error(request, 'Invalid backup code')
    return render(request, 'account/verify_backup_code.html')