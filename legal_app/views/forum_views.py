# FIXED views.py - Corrected permissions and image URL handling
import json
import os
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings
from ..models import ForumPost, ForumReply, User
from datetime import datetime
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import logging

logger = logging.getLogger(__name__)

def create_post_api(request):
    """Create a new forum post - FIXED to return firebase_uid"""
    try:
        firebase_uid = getattr(request, 'firebase_uid', None)
        if not firebase_uid:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        user = User.find_by_firebase_uid(firebase_uid)
        if not user:
            return JsonResponse({'error': 'User not found'}, status=404)
        
        content = request.POST.get('content', '').strip()
        image = request.FILES.get('image')
        
        if not content and not image:
            return JsonResponse({'error': 'Post content or image is required'}, status=400)
        
        # Handle image upload with ABSOLUTE URLs
        image_url = ''
        if image:
            try:
                timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                file_extension = os.path.splitext(image.name)[1]
                filename = f"forum_posts/{firebase_uid}_{timestamp}{file_extension}"
                
                # Save file using Django's storage system
                path = default_storage.save(filename, ContentFile(image.read()))
                
                # FIXED: Generate absolute URL for cross-device access
                # Get the request's domain
                request_host = request.get_host()
                request_scheme = 'https' if request.is_secure() else 'http'
                
                # Build absolute URL
                if hasattr(settings, 'MEDIA_URL'):
                    if settings.MEDIA_URL.startswith('http'):
                        # MEDIA_URL is already absolute
                        image_url = f"{settings.MEDIA_URL}{path}"
                    else:
                        # Make it absolute
                        image_url = f"{request_scheme}://{request_host}{settings.MEDIA_URL}{path}"
                else:
                    image_url = f"{request_scheme}://{request_host}/media/{path}"
                    
                logger.info(f"Image saved to: {path}, Absolute URL: {image_url}")
                    
            except Exception as e:
                logger.error(f"Error uploading image: {str(e)}")
                return JsonResponse({'error': 'Failed to upload image'}, status=500)
        
        # Create the post
        result = ForumPost.create(firebase_uid, content, image_url)
        if not result:
            return JsonResponse({'error': 'Failed to create post'}, status=500)
        
        post_id = str(result.inserted_id)
        
        return JsonResponse({
            'success': True,
            'message': 'Post created successfully',
            'id': post_id,
            'firebase_uid': firebase_uid,
            'user': user.get('name', 'Unknown User'),
            'content': content,
            'image': image_url,
            'created_at': datetime.utcnow().strftime('%b %d, %Y %H:%M'),
            'likes_count': 0
        })
        
    except Exception as e:
        logger.error(f"Error in create_post_api: {str(e)}")
        return JsonResponse({'error': f'Internal server error: {str(e)}'}, status=500)

def like_post_api(request):
    """Like or unlike a post - FIXED to handle string post_id properly"""
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        
        if not post_id:
            logger.error("No post_id provided")
            return JsonResponse({'error': 'Valid Post ID is required'}, status=400)
        
        post_id = str(post_id).strip()
        
        if not post_id or post_id == 'undefined' or post_id == 'null' or post_id == '':
            logger.error(f"Invalid post_id received: {post_id}")
            return JsonResponse({'error': 'Valid Post ID is required'}, status=400)
        
        # Get Firebase UID from middleware
        firebase_uid = getattr(request, 'firebase_uid', None)
        if not firebase_uid:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        # Get the post - get_by_id handles ObjectId conversion
        post = ForumPost.get_by_id(post_id)
        if not post:
            logger.error(f"Post not found: {post_id}")
            return JsonResponse({'error': 'Post not found'}, status=404)
        
        # Check if user already liked the post
        user_liked = firebase_uid in post.get('likes', [])
        
        if user_liked:
            result = ForumPost.unlike(post_id, firebase_uid)
            liked = False
        else:
            result = ForumPost.like(post_id, firebase_uid)
            liked = True
        
        if not result:
            return JsonResponse({'error': 'Failed to update like'}, status=500)
        
        # Get updated post to return current like count
        updated_post = ForumPost.get_by_id(post_id)
        likes_count = len(updated_post.get('likes', []))
        
        return JsonResponse({
            'liked': liked,
            'likes_count': likes_count,
            'success': True
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error in like_post_api: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)

def reply_post_api(request):
    """Create a reply to a post"""
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        content = data.get('content', '').strip()
        
        if not post_id:
            return JsonResponse({'error': 'Post ID is required'}, status=400)
        
        post_id = str(post_id).strip()
        
        if not content:
            return JsonResponse({'error': 'Reply content is required'}, status=400)
        
        firebase_uid = getattr(request, 'firebase_uid', None)
        if not firebase_uid:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        user = User.find_by_firebase_uid(firebase_uid)
        if not user:
            return JsonResponse({'error': 'User not found'}, status=404)
        
        # Verify post exists
        post = ForumPost.get_by_id(post_id)
        if not post:
            return JsonResponse({'error': 'Post not found'}, status=404)
        
        # Create the reply
        result = ForumReply.create(post_id, firebase_uid, content)
        if not result:
            return JsonResponse({'error': 'Failed to create reply'}, status=500)
        
        # Get the created reply ID
        updated_post = ForumPost.get_by_id(post_id)
        if updated_post and updated_post.get('replies'):
            latest_reply = updated_post['replies'][-1]
            reply_id = latest_reply.get('reply_id')
        else:
            return JsonResponse({'error': 'Failed to retrieve created reply'}, status=500)
        
        return JsonResponse({
            'success': True,
            'message': 'Reply created successfully',
            'reply_id': reply_id,
            'firebase_uid': firebase_uid,
            'user': user.get('name', 'Unknown User'),
            'content': content,
            'created_at': datetime.utcnow().strftime('%b %d, %H:%M'),
            'post_id': post_id
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error in reply_post_api: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)

def nested_reply_api(request):
    """Create a nested reply"""
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        parent_reply_id = data.get('parent_reply_id')
        content = data.get('content', '').strip()
        depth = data.get('depth', 1)
        
        if not post_id or not parent_reply_id:
            return JsonResponse({'error': 'Post ID and Parent Reply ID are required'}, status=400)
        
        post_id = str(post_id).strip()
        parent_reply_id = str(parent_reply_id).strip()
        
        if not content:
            return JsonResponse({'error': 'Reply content is required'}, status=400)
        
        firebase_uid = getattr(request, 'firebase_uid', None)
        if not firebase_uid:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        user = User.find_by_firebase_uid(firebase_uid)
        if not user:
            return JsonResponse({'error': 'User not found'}, status=404)
        
        # Verify post exists
        post = ForumPost.get_by_id(post_id)
        if not post:
            return JsonResponse({'error': 'Post not found'}, status=404)
        
        result = ForumReply.create_nested_reply(post_id, parent_reply_id, firebase_uid, content)
        if not result:
            return JsonResponse({'error': 'Failed to create nested reply'}, status=500)
        
        # Find nested reply ID
        updated_post = ForumPost.get_by_id(post_id)
        nested_reply_id = None
        
        def find_nested_reply_id(replies, parent_id):
            for reply in replies:
                if reply.get('reply_id') == parent_id:
                    if reply.get('nested_replies'):
                        return reply['nested_replies'][-1].get('reply_id')
                if reply.get('nested_replies'):
                    result = find_nested_reply_id(reply['nested_replies'], parent_id)
                    if result:
                        return result
            return None
        
        if updated_post and updated_post.get('replies'):
            nested_reply_id = find_nested_reply_id(updated_post['replies'], parent_reply_id)
        
        if not nested_reply_id:
            return JsonResponse({'error': 'Failed to retrieve created nested reply'}, status=500)
        
        return JsonResponse({
            'success': True,
            'message': 'Nested reply created successfully',
            'nested_reply_id': nested_reply_id,
            'reply_id': nested_reply_id,
            'firebase_uid': firebase_uid,
            'user': user.get('name', 'Unknown User'),
            'content': content,
            'created_at': datetime.utcnow().strftime('%b %d, %H:%M'),
            'post_id': post_id,
            'parent_reply_id': parent_reply_id,
            'depth': depth
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error in nested_reply_api: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)

# ... existing code here ...



def edit_post_api(request):
    """Edit a forum post - Only owner can edit (this is correct)"""
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        content = data.get('content', '').strip()
        
        if not post_id:
            return JsonResponse({'error': 'Post ID is required'}, status=400)
        
        firebase_uid = getattr(request, 'firebase_uid', None)
        if not firebase_uid:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        # Verify post exists and belongs to user (CORRECT - only owner can edit)
        post = ForumPost.get_by_id(post_id)
        if not post:
            return JsonResponse({'error': 'Post not found'}, status=404)
        
        if post.get('firebase_uid') != firebase_uid:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        result = ForumPost.update_content(post_id, content)
        if not result or result.modified_count == 0:
            return JsonResponse({'error': 'Failed to update post'}, status=500)
        
        return JsonResponse({
            'success': True,
            'message': 'Post updated successfully'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error in edit_post_api: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


def delete_post_api(request):
    """Delete a forum post - Only owner can delete (this is correct)"""
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        
        if not post_id:
            return JsonResponse({'error': 'Post ID is required'}, status=400)
        
        firebase_uid = getattr(request, 'firebase_uid', None)
        if not firebase_uid:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        # Verify post exists and belongs to user (CORRECT - only owner can delete)
        post = ForumPost.get_by_id(post_id)
        if not post:
            return JsonResponse({'error': 'Post not found'}, status=404)
        
        if post.get('firebase_uid') != firebase_uid:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        result = ForumPost.delete(post_id)
        if not result or result.deleted_count == 0:
            return JsonResponse({'error': 'Failed to delete post'}, status=500)
        
        return JsonResponse({
            'success': True,
            'message': 'Post deleted successfully'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error in delete_post_api: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


def edit_reply_api(request):
    """Edit a reply - Only owner can edit (this is correct)"""
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        reply_id = data.get('reply_id')
        content = data.get('content', '').strip()
        
        if not post_id or not reply_id:
            return JsonResponse({'error': 'Post ID and Reply ID are required'}, status=400)
        if not content:
            return JsonResponse({'error': 'Reply content is required'}, status=400)
        
        firebase_uid = getattr(request, 'firebase_uid', None)
        if not firebase_uid:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        # Update the reply (ownership check is in the model method)
        result = ForumReply.update_content(post_id, reply_id, firebase_uid, content)
        if not result or result.modified_count == 0:
            return JsonResponse({'error': 'Failed to update reply or permission denied'}, status=404)
        
        return JsonResponse({
            'success': True,
            'message': 'Reply updated successfully'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error in edit_reply_api: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


def delete_reply_api(request):
    """Delete a reply - Only owner can delete (this is correct)"""
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        reply_id = data.get('reply_id')
        
        if not post_id or not reply_id:
            return JsonResponse({'error': 'Post ID and Reply ID are required'}, status=400)
        
        firebase_uid = getattr(request, 'firebase_uid', None)
        if not firebase_uid:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        # Delete the reply (ownership check is in the model method)
        result = ForumReply.delete_reply(post_id, reply_id, firebase_uid)
        if not result or result.modified_count == 0:
            return JsonResponse({'error': 'Failed to delete reply or permission denied'}, status=404)
        
        return JsonResponse({
            'success': True,
            'message': 'Reply deleted successfully'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error in delete_reply_api: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


def edit_nested_reply_api(request):
    """Edit a nested reply - Only owner can edit (this is correct)"""
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        parent_reply_id = data.get('parent_reply_id')
        nested_reply_id = data.get('nested_reply_id')
        content = data.get('content', '').strip()
        
        if not all([post_id, parent_reply_id, nested_reply_id]):
            return JsonResponse({'error': 'Post ID, Parent Reply ID, and Nested Reply ID are required'}, status=400)
        if not content:
            return JsonResponse({'error': 'Reply content is required'}, status=400)
        
        firebase_uid = getattr(request, 'firebase_uid', None)
        if not firebase_uid:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        # Update the nested reply using recursive update (ownership check is in the model method)
        result = ForumReply.update_content(post_id, nested_reply_id, firebase_uid, content)
        if not result or result.modified_count == 0:
            return JsonResponse({'error': 'Failed to update nested reply or permission denied'}, status=404)
        
        return JsonResponse({
            'success': True,
            'message': 'Nested reply updated successfully'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error in edit_nested_reply_api: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


def delete_nested_reply_api(request):
    """Delete a nested reply - Only owner can delete (this is correct)"""
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        parent_reply_id = data.get('parent_reply_id')
        nested_reply_id = data.get('nested_reply_id')
        
        if not all([post_id, parent_reply_id, nested_reply_id]):
            return JsonResponse({'error': 'Post ID, Parent Reply ID, and Nested Reply ID are required'}, status=400)
        
        firebase_uid = getattr(request, 'firebase_uid', None)
        if not firebase_uid:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        # Delete the nested reply using recursive delete (ownership check is in the model method)
        result = ForumReply.delete_reply(post_id, nested_reply_id, firebase_uid)
        if not result or result.modified_count == 0:
            return JsonResponse({'error': 'Failed to delete nested reply or permission denied'}, status=404)
        
        return JsonResponse({
            'success': True,
            'message': 'Nested reply deleted successfully'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error in delete_nested_reply_api: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)