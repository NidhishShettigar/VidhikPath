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
        try:
            if isinstance(post_id, str):
                post_id = ObjectId(post_id)
            return ForumPost.collection.find_one({"_id": post_id})
        except Exception:
            return None
    
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
        try:
            if isinstance(post_id, str):
                post_id = ObjectId(post_id)
            return ForumPost.collection.update_one(
                {"_id": post_id},
                {
                    "$addToSet": {"likes": username},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
        except Exception:
            return None
    
    @staticmethod
    def unlike(post_id, username):
        """Remove a like from a post"""
        try:
            if isinstance(post_id, str):
                post_id = ObjectId(post_id)
            return ForumPost.collection.update_one(
                {"_id": post_id},
                {
                    "$pull": {"likes": username},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
        except Exception:
            return None
    
    @staticmethod
    def add_reply(post_id, reply):
        """Add a reply to a post"""
        try:
            if isinstance(post_id, str):
                post_id = ObjectId(post_id)
            return ForumPost.collection.update_one(
                {"_id": post_id},
                {
                    "$push": {"replies": reply},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
        except Exception:
            return None
    
    @staticmethod
    def get_likes_count(post_id):
        """Get the number of likes for a post"""
        post = ForumPost.get_by_id(post_id)
        if post:
            return len(post.get('likes', []))
        return 0
    
    @staticmethod
    def is_liked_by_user(post_id, username):
        """Check if a post is liked by a specific user"""
        post = ForumPost.get_by_id(post_id)
        if post:
            return username in post.get('likes', [])
        return False


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
        try:
            if isinstance(post_id, str):
                post_id = ObjectId(post_id)
            return ForumPost.collection.update_one(
                {"_id": post_id},
                {
                    "$pull": {"replies": {"reply_id": reply_id}},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
        except Exception:
            return None