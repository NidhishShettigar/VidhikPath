# views.py - Complete Fixed Forum API endpoints
import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from ..models import ForumPost, ForumReply, User
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@require_http_methods(["POST"])
def like_post_api(request):
    """Like or unlike a post - FIXED"""
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        
        # Validate post_id
        if not post_id:
            return JsonResponse({'error': 'Post ID is required'}, status=400)
        
        # Get Firebase UID from middleware
        firebase_uid = getattr(request, 'firebase_uid', None)
        if not firebase_uid:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        # Get the post
        post = ForumPost.get_by_id(post_id)
        if not post:
            return JsonResponse({'error': 'Post not found'}, status=404)
        
        # Check if user already liked the post
        user_liked = firebase_uid in post.get('likes', [])
        
        if user_liked:
            # Unlike the post
            result = ForumPost.unlike(post_id, firebase_uid)
            if not result:
                return JsonResponse({'error': 'Failed to unlike post'}, status=500)
            liked = False
        else:
            # Like the post
            result = ForumPost.like(post_id, firebase_uid)
            if not result:
                return JsonResponse({'error': 'Failed to like post'}, status=500)
            liked = True
        
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


@require_http_methods(["POST"])
def reply_post_api(request):
    """Create a reply to a post - FIXED"""
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        content = data.get('content', '').strip()
        
        # Validate inputs
        if not post_id:
            return JsonResponse({'error': 'Post ID is required'}, status=400)
        if not content:
            return JsonResponse({'error': 'Reply content is required'}, status=400)
        
        # Get Firebase UID from middleware
        firebase_uid = getattr(request, 'firebase_uid', None)
        if not firebase_uid:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        # Get user info
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
        
        # Get the created reply ID from the result
        # Since we're adding to an array, we need to get the last reply added
        updated_post = ForumPost.get_by_id(post_id)
        if updated_post and updated_post.get('replies'):
            latest_reply = updated_post['replies'][-1]  # Get the last reply
            reply_id = latest_reply.get('reply_id')
        else:
            return JsonResponse({'error': 'Failed to retrieve created reply'}, status=500)
        
        return JsonResponse({
            'success': True,
            'message': 'Reply created successfully',
            'reply_id': reply_id,
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


@require_http_methods(["PUT"])
def edit_reply_api(request):
    """Edit a reply - ENHANCED"""
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        reply_id = data.get('reply_id')
        content = data.get('content', '').strip()
        depth = data.get('depth', 0)
        
        # Validate inputs
        if not post_id or not reply_id:
            return JsonResponse({'error': 'Post ID and Reply ID are required'}, status=400)
        if not content:
            return JsonResponse({'error': 'Reply content is required'}, status=400)
        
        # Get Firebase UID from middleware
        firebase_uid = getattr(request, 'firebase_uid', None)
        if not firebase_uid:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        # Update the reply
        result = ForumReply.update_content(post_id, reply_id, firebase_uid, content)
        if not result or result.modified_count == 0:
            return JsonResponse({'error': 'Failed to update reply or reply not found'}, status=404)
        
        return JsonResponse({
            'success': True,
            'message': 'Reply updated successfully'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error in edit_reply_api: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@require_http_methods(["DELETE"])
def delete_reply_api(request):
    """Delete a reply - ENHANCED"""
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        reply_id = data.get('reply_id')
        depth = data.get('depth', 0)
        
        # Validate inputs
        if not post_id or not reply_id:
            return JsonResponse({'error': 'Post ID and Reply ID are required'}, status=400)
        
        # Get Firebase UID from middleware
        firebase_uid = getattr(request, 'firebase_uid', None)
        if not firebase_uid:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        # Delete the reply
        result = ForumReply.delete_reply(post_id, reply_id, firebase_uid)
        if not result or result.modified_count == 0:
            return JsonResponse({'error': 'Failed to delete reply or reply not found'}, status=404)
        
        return JsonResponse({
            'success': True,
            'message': 'Reply deleted successfully'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error in delete_reply_api: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@require_http_methods(["POST"])
def nested_reply_api(request):
    """Create a nested reply - ENHANCED FOR INFINITE DEPTH"""
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        parent_reply_id = data.get('parent_reply_id')
        content = data.get('content', '').strip()
        depth = data.get('depth', 1)
        
        # Validate inputs
        if not post_id or not parent_reply_id:
            return JsonResponse({'error': 'Post ID and Parent Reply ID are required'}, status=400)
        if not content:
            return JsonResponse({'error': 'Reply content is required'}, status=400)
        
        # Get Firebase UID from middleware
        firebase_uid = getattr(request, 'firebase_uid', None)
        if not firebase_uid:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        # Get user info
        user = User.find_by_firebase_uid(firebase_uid)
        if not user:
            return JsonResponse({'error': 'User not found'}, status=404)
        
        # Verify post exists
        post = ForumPost.get_by_id(post_id)
        if not post:
            return JsonResponse({'error': 'Post not found'}, status=404)
        
        # Create the nested reply
        result = ForumReply.create_nested_reply(post_id, parent_reply_id, firebase_uid, content)
        if not result:
            return JsonResponse({'error': 'Failed to create nested reply'}, status=500)
        
        # Get the created nested reply ID
        # We need to find the reply that was just added
        updated_post = ForumPost.get_by_id(post_id)
        nested_reply_id = None
        
        # Function to recursively search for the nested reply
        def find_nested_reply_id(replies, parent_id):
            for reply in replies:
                if reply.get('reply_id') == parent_id:
                    if reply.get('nested_replies'):
                        return reply['nested_replies'][-1].get('reply_id')
                # Search in nested replies recursively
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
            'reply_id': nested_reply_id,  # For consistency with frontend
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


@require_http_methods(["POST"])
def create_post_api(request):
    """Create a new forum post - ENHANCED"""
    try:
        # Get Firebase UID from middleware
        firebase_uid = getattr(request, 'firebase_uid', None)
        if not firebase_uid:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        # Get user info
        user = User.find_by_firebase_uid(firebase_uid)
        if not user:
            return JsonResponse({'error': 'User not found'}, status=404)
        
        # Handle form data (for file uploads)
        content = request.POST.get('content', '').strip()
        image = request.FILES.get('image')
        
        if not content:
            return JsonResponse({'error': 'Post content is required'}, status=400)
        
        # Handle image upload if present
        image_filename = ''
        if image:
            # You would implement proper image handling here
            # For now, we'll just store the filename
            image_filename = image.name
        
        # Create the post
        result = ForumPost.create(firebase_uid, content, image_filename)
        if not result:
            return JsonResponse({'error': 'Failed to create post'}, status=500)
        
        post_id = str(result.inserted_id)
        
        return JsonResponse({
            'success': True,
            'message': 'Post created successfully',
            'id': post_id,
            'user': user.get('name', 'Unknown User'),
            'content': content,
            'image': image_filename,
            'created_at': datetime.utcnow().strftime('%b %d, %Y %H:%M'),
            'likes_count': 0
        })
        
    except Exception as e:
        logger.error(f"Error in create_post_api: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@require_http_methods(["PUT"])
def edit_post_api(request):
    """Edit a forum post"""
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        content = data.get('content', '').strip()
        
        # Validate inputs
        if not post_id:
            return JsonResponse({'error': 'Post ID is required'}, status=400)
        if not content:
            return JsonResponse({'error': 'Post content is required'}, status=400)
        
        # Get Firebase UID from middleware
        firebase_uid = getattr(request, 'firebase_uid', None)
        if not firebase_uid:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        # Verify post exists and belongs to user
        post = ForumPost.get_by_id(post_id)
        if not post:
            return JsonResponse({'error': 'Post not found'}, status=404)
        
        if post.get('firebase_uid') != firebase_uid:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        # Update the post
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


@require_http_methods(["DELETE"])
def delete_post_api(request):
    """Delete a forum post"""
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        
        # Validate inputs
        if not post_id:
            return JsonResponse({'error': 'Post ID is required'}, status=400)
        
        # Get Firebase UID from middleware
        firebase_uid = getattr(request, 'firebase_uid', None)
        if not firebase_uid:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        # Verify post exists and belongs to user
        post = ForumPost.get_by_id(post_id)
        if not post:
            return JsonResponse({'error': 'Post not found'}, status=404)
        
        if post.get('firebase_uid') != firebase_uid:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        # Delete the post
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


@require_http_methods(["PUT"])
def edit_nested_reply_api(request):
    """Edit a nested reply - FOR INFINITE DEPTH"""
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        parent_reply_id = data.get('parent_reply_id')
        nested_reply_id = data.get('nested_reply_id')
        content = data.get('content', '').strip()
        depth = data.get('depth', 1)
        
        # Validate inputs
        if not all([post_id, parent_reply_id, nested_reply_id]):
            return JsonResponse({'error': 'Post ID, Parent Reply ID, and Nested Reply ID are required'}, status=400)
        if not content:
            return JsonResponse({'error': 'Reply content is required'}, status=400)
        
        # Get Firebase UID from middleware
        firebase_uid = getattr(request, 'firebase_uid', None)
        if not firebase_uid:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        # Update the nested reply
        result = ForumReply.update_nested_reply(post_id, parent_reply_id, nested_reply_id, firebase_uid, content)
        if not result or result.modified_count == 0:
            return JsonResponse({'error': 'Failed to update nested reply or reply not found'}, status=404)
        
        return JsonResponse({
            'success': True,
            'message': 'Nested reply updated successfully'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error in edit_nested_reply_api: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@require_http_methods(["DELETE"])
def delete_nested_reply_api(request):
    """Delete a nested reply - FOR INFINITE DEPTH"""
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        parent_reply_id = data.get('parent_reply_id')
        nested_reply_id = data.get('nested_reply_id')
        depth = data.get('depth', 1)
        
        # Validate inputs
        if not all([post_id, parent_reply_id, nested_reply_id]):
            return JsonResponse({'error': 'Post ID, Parent Reply ID, and Nested Reply ID are required'}, status=400)
        
        # Get Firebase UID from middleware
        firebase_uid = getattr(request, 'firebase_uid', None)
        if not firebase_uid:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        # Delete the nested reply
        result = ForumReply.delete_nested_reply(post_id, parent_reply_id, nested_reply_id, firebase_uid)
        if not result or result.modified_count == 0:
            return JsonResponse({'error': 'Failed to delete nested reply or reply not found'}, status=404)
        
        return JsonResponse({
            'success': True,
            'message': 'Nested reply deleted successfully'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error in delete_nested_reply_api: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)