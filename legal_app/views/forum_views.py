from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from bson import ObjectId
from datetime import datetime
import json
from .base_views import firebase_login_required
from ..models import ForumPost, ForumReply


@csrf_exempt
@firebase_login_required
def create_post_api(request):
    """API endpoint to create a new forum post"""
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        
        if not content:
            return JsonResponse({'error': 'Content is required'}, status=400)
        
        if len(content) > 5000:
            return JsonResponse({'error': 'Content too long. Maximum 5000 characters allowed.'}, status=400)
        
        image_path = ''
        if 'image' in request.FILES:
            file = request.FILES['image']
            
            if not file.content_type.startswith('image/'):
                return JsonResponse({'error': 'Invalid file type. Please upload an image.'}, status=400)
            
            if file.size > 5 * 1024 * 1024:
                return JsonResponse({'error': 'File too large. Maximum 5MB allowed.'}, status=400)
            
            try:
                file_path = default_storage.save(f'forum_images/{file.name}', file)
                image_path = file_path
            except Exception as e:
                return JsonResponse({'error': f'Error saving image: {str(e)}'}, status=500)
        
        try:
            result = ForumPost.create(
                firebase_uid=request.firebase_uid,
                content=content,
                image=image_path
            )
            
            return JsonResponse({
                'id': str(result.inserted_id),
                'content': content,
                'user': request.firebase_user.get('name', 'Unknown User'),
                'firebase_uid': request.firebase_uid,
                'created_at': datetime.utcnow().strftime('%b %d, %Y %H:%M'),
                'likes_count': 0,
                'image': image_path,
                'status': 'success'
            })
            
        except Exception as e:
            print(f"Error creating post: {e}")
            return JsonResponse({'error': f'Error creating post: {str(e)}'}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)


@csrf_exempt
@firebase_login_required
def like_post_api(request):
    """API endpoint to like/unlike a forum post"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            post_id = data.get('post_id')
            
            if not post_id:
                return JsonResponse({'error': 'Post ID is required'}, status=400)
            
            try:
                post_object_id = ObjectId(post_id)
            except Exception:
                return JsonResponse({'error': 'Invalid post ID format'}, status=400)
            
            post = ForumPost.get_by_id(post_object_id)
            if not post:
                return JsonResponse({'error': 'Post not found'}, status=404)
            
            likes = post.get('likes', [])
            firebase_uid = request.firebase_uid
            
            if firebase_uid in likes:
                result = ForumPost.unlike(post_object_id, firebase_uid)
                if result and result.modified_count > 0:
                    liked = False
                    likes_count = len(likes) - 1
                else:
                    return JsonResponse({'error': 'Failed to remove like'}, status=500)
            else:
                result = ForumPost.like(post_object_id, firebase_uid)
                if result and result.modified_count > 0:
                    liked = True
                    likes_count = len(likes) + 1
                else:
                    return JsonResponse({'error': 'Failed to add like'}, status=500)
            
            return JsonResponse({
                'liked': liked,
                'likes_count': likes_count,
                'status': 'success'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            print(f"Error in like_post_api: {e}")
            return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)


@csrf_exempt
@firebase_login_required
def reply_post_api(request):
    """API endpoint to reply to a forum post"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            post_id = data.get('post_id')
            content = data.get('content', '').strip()
            
            if not post_id or not content:
                return JsonResponse({'error': 'Post ID and content are required'}, status=400)
            
            if len(content) > 1000:
                return JsonResponse({'error': 'Reply too long. Maximum 1000 characters allowed.'}, status=400)
            
            try:
                post_object_id = ObjectId(post_id)
            except Exception:
                return JsonResponse({'error': 'Invalid post ID format'}, status=400)
            
            post = ForumPost.get_by_id(post_object_id)
            if not post:
                return JsonResponse({'error': 'Post not found'}, status=404)
            
            result = ForumReply.create(post_object_id, request.firebase_uid, content)
            
            if result and result.modified_count > 0:
                return JsonResponse({
                    'content': content,
                    'user': request.firebase_user.get('name', 'Unknown User'),
                    'firebase_uid': request.firebase_uid,
                    'created_at': datetime.utcnow().strftime('%b %d, %H:%M'),
                    'status': 'success'
                })
            else:
                return JsonResponse({'error': 'Failed to create reply'}, status=500)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            print(f"Error in reply_post_api: {e}")
            return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)
