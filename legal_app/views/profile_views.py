from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.conf import settings
import os
from ..db_connection import db
from ..models import User
from .base_views import firebase_login_required

@firebase_login_required
def user_profile(request):
    user = request.firebase_user
    
    if request.method == 'POST':
        # Handle profile update
        update_data = {
            'name': request.POST.get('name', user.get('name', '')),
            'phone': request.POST.get('phone', user.get('phone', '')),
            'location': request.POST.get('location', user.get('location', ''))
        }
        
        # Handle profile photo upload
        if 'profile_photo' in request.FILES:
            file = request.FILES['profile_photo']
            file_path = default_storage.save(f'profiles/{file.name}', file)
            update_data['profile_photo'] = file_path
        
        # Update lawyer-specific fields if user is a lawyer
        if user.get('user_type') == 'lawyer':
            update_data.update({
                'lawyer_type': request.POST.get('lawyer_type', user.get('lawyer_type', '')),
                'experience': int(request.POST.get('experience', user.get('experience', 0))),
                'license_number': request.POST.get('license_number', user.get('license_number', '')),
                'education': request.POST.get('education', user.get('education', '')),
            })
            # Handle languages (assuming it's a comma-separated string)
            languages_str = request.POST.get('languages_spoken', '')
            if languages_str:
                update_data['languages_spoken'] = [l.strip() for l in languages_str.split(',')]
        
        # Update in MongoDB
        User.update_profile(request.firebase_uid, update_data)
        
        # Refresh user data
        request.firebase_user = User.find_by_firebase_uid(request.firebase_uid)
    
    return render(request, 'profile.html', {
        'user': request.firebase_user
    })

@firebase_login_required
def update_profile(request):
    if request.method == "POST":
        try:
            firebase_uid = request.session.get("firebase_uid")
            if not firebase_uid:
                return JsonResponse({"success": False, "error": "User not authenticated"})

            name = request.POST.get("name")
            phone = request.POST.get("phone")
            location = request.POST.get("location")
            profile_photo = request.FILES.get("profile_photo")

            update_data = {
                "name": name,
                "phone": phone,
                "location": location
            }

            # Handle photo upload
            if profile_photo:
                photo_path = os.path.join("media/profile_photos", profile_photo.name)
                with open(photo_path, "wb+") as destination:
                    for chunk in profile_photo.chunks():
                        destination.write(chunk)
                update_data["profile_photo"] = photo_path

            # Update MongoDB
            db.users.update_one(
                {"firebase_uid": firebase_uid},
                {"$set": update_data}
            )

            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    return JsonResponse({"success": False, "error": "Invalid request"})
