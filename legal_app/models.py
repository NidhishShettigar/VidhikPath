# models.py
from .db_connection import db
from datetime import datetime
from bson import ObjectId


# === UserProfile ===
class UserProfile:
    collection = db['user_profiles']

    @staticmethod
    def create(username, is_lawyer=False, phone='', location='',
               lawyer_type='', experience=None, license_document=''):
        profile = {
            "username": username,
            "is_lawyer": is_lawyer,
            "phone": phone,
            "location": location,
            "lawyer_type": lawyer_type,
            "experience": experience,
            "license_document": license_document,
            "created_at": datetime.utcnow()
        }
        return UserProfile.collection.insert_one(profile)

    @staticmethod
    def find_by_username(username):
        return UserProfile.collection.find_one({"username": username})


# === ForumPost ===
class ForumPost:
    collection = db['forum_posts']
    
    @staticmethod
    def create(username, content, image=''):
        """Create a new forum post"""
        post = {
            "username": username,
            "content": content,
            "image": image,
            "likes": [],
            "created_at": datetime.utcnow(),
            "replies": [],
            "updated_at": datetime.utcnow()
        }
        return ForumPost.collection.insert_one(post)
    
    @staticmethod
    def get_by_id(post_id):
        """Get a post by its ID"""
        return ForumPost.collection.find_one({"_id": ObjectId(post_id)})
    
    @staticmethod
    def get_all(limit=20, skip=0):
        """Get all posts with pagination"""
        return list(ForumPost.collection.find()
                   .sort("created_at", -1)
                   .limit(limit)
                   .skip(skip))
    
    @staticmethod
    def like(post_id, username):
        """Add a like to a post"""
        return ForumPost.collection.update_one(
            {"_id": post_id},
            {
                "$addToSet": {"likes": username},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
    
    @staticmethod
    def unlike(post_id, username):
        """Remove a like from a post"""
        return ForumPost.collection.update_one(
            {"_id": post_id},
            {
                "$pull": {"likes": username},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
    
    @staticmethod
    def add_reply(post_id, reply):
        """Add a reply to a post"""
        return ForumPost.collection.update_one(
            {"_id": post_id},
            {
                "$push": {"replies": reply},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
    
    @staticmethod
    def get_likes_count(post_id):
        """Get the number of likes for a post"""
        post = ForumPost.collection.find_one({"_id": ObjectId(post_id)})
        if post:
            return len(post.get('likes', []))
        return 0
    
    @staticmethod
    def is_liked_by_user(post_id, username):
        """Check if a post is liked by a specific user"""
        post = ForumPost.collection.find_one({"_id": ObjectId(post_id)})
        if post:
            return username in post.get('likes', [])
        return False
    
    @staticmethod
    def update_content(post_id, content):
        """Update post content"""
        return ForumPost.collection.update_one(
            {"_id": ObjectId(post_id)},
            {
                "$set": {
                    "content": content,
                    "updated_at": datetime.utcnow()
                }
            }
        )
    
    @staticmethod
    def delete(post_id):
        """Delete a post"""
        return ForumPost.collection.delete_one({"_id": ObjectId(post_id)})
    
    @staticmethod
    def get_posts_by_user(username, limit=20, skip=0):
        """Get posts by a specific user"""
        return list(ForumPost.collection.find({"username": username})
                   .sort("created_at", -1)
                   .limit(limit)
                   .skip(skip))


class ForumReply:
    @staticmethod
    def create(post_id, username, content):
        """Create a new reply to a post"""
        reply = {
            "username": username,
            "content": content,
            "created_at": datetime.utcnow(),
            "reply_id": str(ObjectId())  # Unique ID for each reply
        }
        return ForumPost.add_reply(post_id, reply)
    
    @staticmethod
    def delete_reply(post_id, reply_id):
        """Delete a specific reply from a post"""
        return ForumPost.collection.update_one(
            {"_id": ObjectId(post_id)},
            {
                "$pull": {"replies": {"reply_id": reply_id}},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
    
    @staticmethod
    def get_replies_for_post(post_id):
        """Get all replies for a specific post"""
        post = ForumPost.collection.find_one({"_id": ObjectId(post_id)})
        if post:
            return post.get('replies', [])
        return []
    
    @staticmethod
    def get_replies_count(post_id):
        """Get the number of replies for a post"""
        post = ForumPost.collection.find_one({"_id": ObjectId(post_id)})
        if post:
            return len(post.get('replies', []))
        return 0


# class ForumStats:
#     """Class to handle forum statistics"""
    
#     @staticmethod
#     def get_total_posts():
#         """Get total number of posts"""
#         return ForumPost.collection.count_documents({})
    
#     @staticmethod
#     def get_total_replies():
#         """Get total number of replies across all posts"""
#         pipeline = [
#             {"$project": {"reply_count": {"$size": "$replies"}}},
#             {"$group": {"_id": None, "total": {"$sum": "$reply_count"}}}
#         ]
#         result = list(ForumPost.collection.aggregate(pipeline))
#         return result[0]['total'] if result else 0
    
#     @staticmethod
#     def get_most_liked_posts(limit=5):
#         """Get posts with the most likes"""
#         pipeline = [
#             {"$project": {
#                 "username": 1,
#                 "content": 1,
#                 "created_at": 1,
#                 "like_count": {"$size": "$likes"}
#             }},
#             {"$sort": {"like_count": -1}},
#             {"$limit": limit}
#         ]
#         return list(ForumPost.collection.aggregate(pipeline))
    
#     @staticmethod
#     def get_most_active_users(limit=10):
#         """Get users with the most posts"""
#         pipeline = [
#             {"$group": {"_id": "$username", "post_count": {"$sum": 1}}},
#             {"$sort": {"post_count": -1}},
#             {"$limit": limit}
#         ]
#         return list(ForumPost.collection.aggregate(pipeline))
    
#     @staticmethod
#     def get_recent_activity(limit=10):
#         """Get recent posts and replies activity"""
#         return list(ForumPost.collection.find()
#                    .sort("updated_at", -1)
#                    .limit(limit)
#                    .project({
#                        "username": 1,
#                        "content": {"$substr": ["$content", 0, 100]},
#                        "created_at": 1,
#                        "updated_at": 1,
#                        "likes_count": {"$size": "$likes"},
#                        "replies_count": {"$size": "$replies"}
#                    }))


# # Helper functions for template usage
# def get_forum_context(request, page=1, posts_per_page=10):
#     """
#     Get forum context data for templates
#     """
#     skip = (page - 1) * posts_per_page
#     posts_data = ForumPost.get_all(limit=posts_per_page, skip=skip)
    
#     # Convert MongoDB data to template-friendly format
#     posts = []
#     for post_data in posts_data:
#         # Check if current user liked the post
#         user_liked = False
#         if hasattr(request, 'user') and request.user.is_authenticated:
#             user_liked = request.user.username in post_data.get('likes', [])
        
#         post = {
#             'id': str(post_data['_id']),
#             'user': {
#                 'first_name': post_data.get('username', 'Anonymous'),
#                 'username': post_data.get('username', 'Anonymous')
#             },
#             'content': post_data.get('content', ''),
#             'image': {'url': f"/media/{post_data['image']}"} if post_data.get('image') else None,
#             'created_at': post_data.get('created_at', datetime.utcnow()),
#             'likes': {
#                 'count': len(post_data.get('likes', [])),
#                 'user_liked': user_liked
#             },
#             'replies': {
#                 'all': [
#                     {
#                         'user': {
#                             'first_name': reply.get('username', 'Anonymous'),
#                             'username': reply.get('username', 'Anonymous')
#                         },
#                         'content': reply.get('content', ''),
#                         'created_at': reply.get('created_at', datetime.utcnow())
#                     }
#                     for reply in post_data.get('replies', [])
#                 ]
#             }
#         }
#         posts.append(post)
    
#     return {
#         'posts': posts,
#         'total_posts': ForumStats.get_total_posts(),
#         'current_page': page,
#         'has_next': len(posts_data) == posts_per_page
#     }