# models.py - Updated for Firebase-only authentication with MongoDB
from .db_connection import db
from datetime import datetime
from bson import ObjectId
import firebase_admin
from firebase_admin import auth


# === User Model (MongoDB Collection) ===
class User:
    collection = db['users']

    @staticmethod
    def create(firebase_uid, email, name, user_type="user", **kwargs):
        """Create a new user profile in MongoDB"""
        user_data = {
            "firebase_uid": firebase_uid,
            "email": email,
            "name": name,
            "user_type": user_type,  # "user" or "lawyer"
            "phone": kwargs.get("phone", ""),
            "location": kwargs.get("location", ""),
            "profile_photo": kwargs.get("profile_photo", ""),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_active": True
        }
        
        # Add lawyer-specific fields if user_type is "lawyer"
        if user_type == "lawyer":
            user_data.update({
                "lawyer_type": kwargs.get("lawyer_type", ""),
                "experience": kwargs.get("experience", 0),
                "license_number": kwargs.get("license_number", ""),
                "license_document": kwargs.get("license_document", ""),
                "languages_spoken": kwargs.get("languages_spoken", []),
                "education": kwargs.get("education", ""),
                "verified": False,  # Admin verification for lawyers
                "rating": 0.0,
                "total_reviews": 0
            })
        
        return User.collection.insert_one(user_data)

    @staticmethod
    def find_by_firebase_uid(firebase_uid):
        """Find user by Firebase UID"""
        return User.collection.find_one({"firebase_uid": firebase_uid})

    @staticmethod
    def find_by_email(email):
        """Find user by email"""
        return User.collection.find_one({"email": email})

    @staticmethod
    def update_profile(firebase_uid, update_data):
        """Update user profile"""
        update_data["updated_at"] = datetime.utcnow()
        return User.collection.update_one(
            {"firebase_uid": firebase_uid},
            {"$set": update_data}
        )

    @staticmethod
    def find_lawyers(location=None, lawyer_type=None, specialization=None):
        """Find lawyers with filters"""
        query = {"user_type": "lawyer", "is_active": True}
        
        if location:
            query["location"] = {"$regex": location, "$options": "i"}
        
        if lawyer_type:
            query["lawyer_type"] = {"$regex": lawyer_type, "$options": "i"}
            
        if specialization:
            query["specializations"] = {"$in": [specialization]}
        
        return list(User.collection.find(query))

    @staticmethod
    def verify_lawyer(firebase_uid, verified=True):
        """Verify or unverify a lawyer"""
        return User.collection.update_one(
            {"firebase_uid": firebase_uid, "user_type": "lawyer"},
            {"$set": {"verified": verified, "updated_at": datetime.utcnow()}}
        )


# === Session Management ===
class UserSession:
    collection = db['user_sessions']

    @staticmethod
    def create_session(firebase_uid, firebase_token, refresh_token):
        """Store Firebase session data"""
        session_data = {
            "firebase_uid": firebase_uid,
            "firebase_token": firebase_token,
            "refresh_token": refresh_token,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow(),  # You can calculate expiry
            "is_active": True
        }
        return UserSession.collection.insert_one(session_data)

    @staticmethod
    def update_session(firebase_uid, firebase_token, refresh_token):
        """Update existing session"""
        return UserSession.collection.update_one(
            {"firebase_uid": firebase_uid},
            {
                "$set": {
                    "firebase_token": firebase_token,
                    "refresh_token": refresh_token,
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )

    @staticmethod
    def invalidate_session(firebase_uid):
        """Invalidate user session"""
        return UserSession.collection.update_one(
            {"firebase_uid": firebase_uid},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
        )


# === ForumPost (Updated to work with Firebase UIDs) ===
class ForumPost:
    collection = db['forum_posts']
    
    @staticmethod
    def create(firebase_uid, content, image=''):
        """Create a new forum post"""
        post = {
            "firebase_uid": firebase_uid,
            "content": content,
            "image": image,
            "likes": [],  # List of firebase_uids who liked
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
    def get_all_with_user_info(limit=20, skip=0):
        """Get all posts with user information"""
        posts = list(ForumPost.collection.find()
                    .sort("created_at", -1)
                    .limit(limit)
                    .skip(skip))
        
        # Populate user info for each post
        for post in posts:
            user = User.find_by_firebase_uid(post['firebase_uid'])
            post['user'] = {
                'name': user.get('name', 'Unknown User') if user else 'Unknown User',
                'user_type': user.get('user_type', 'user') if user else 'user'
            }
            
            # Populate user info for replies
            for reply in post.get('replies', []):
                reply_user = User.find_by_firebase_uid(reply['firebase_uid'])
                reply['user'] = {
                    'name': reply_user.get('name', 'Unknown User') if reply_user else 'Unknown User'
                }
                
                # Populate user info for nested replies
                for nested_reply in reply.get('nested_replies', []):
                    nested_user = User.find_by_firebase_uid(nested_reply['firebase_uid'])
                    nested_reply['user'] = {
                        'name': nested_user.get('name', 'Unknown User') if nested_user else 'Unknown User'
                    }
        
        return posts
    
    @staticmethod
    def update_content(post_id, content):
        """Update post content"""
        try:
            if isinstance(post_id, str):
                post_id = ObjectId(post_id)
            return ForumPost.collection.update_one(
                {"_id": post_id},
                {
                    "$set": {
                        "content": content,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
        except Exception:
            return None
    
    @staticmethod
    def like(post_id, firebase_uid):
        """Add a like to a post"""
        try:
            if isinstance(post_id, str):
                post_id = ObjectId(post_id)
            return ForumPost.collection.update_one(
                {"_id": post_id},
                {
                    "$addToSet": {"likes": firebase_uid},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
        except Exception:
            return None
    
    @staticmethod
    def unlike(post_id, firebase_uid):
        """Remove a like from a post"""
        try:
            if isinstance(post_id, str):
                post_id = ObjectId(post_id)
            return ForumPost.collection.update_one(
                {"_id": post_id},
                {
                    "$pull": {"likes": firebase_uid},
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
    def delete(post_id):
        """Delete a post"""
        try:
            if isinstance(post_id, str):
                post_id = ObjectId(post_id)
            return ForumPost.collection.delete_one({"_id": post_id})
        except Exception:
            return None


# Enhanced ForumReply class for infinite nested replies
class ForumReply:
    @staticmethod
    def create(post_id, firebase_uid, content, reply_id=None):
        """Create a new reply to a post"""
        if not reply_id:
            reply_id = str(ObjectId())
            
        reply = {
            "firebase_uid": firebase_uid,
            "content": content,
            "created_at": datetime.utcnow(),
            "reply_id": reply_id,
            "nested_replies": []
        }
        return ForumPost.add_reply(post_id, reply)
    
    @staticmethod
    def update_content(post_id, reply_id, firebase_uid, content):
        """Update reply content - Enhanced for nested replies"""
        try:
            if isinstance(post_id, str):
                post_id = ObjectId(post_id)
            
            # First try to update in main replies
            result = ForumPost.collection.update_one(
                {
                    "_id": post_id,
                    "replies.reply_id": reply_id,
                    "replies.firebase_uid": firebase_uid
                },
                {
                    "$set": {
                        "replies.$.content": content,
                        "replies.$.updated_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                return result
            
            # If not found in main replies, try nested replies
            # This handles infinite depth by searching through all nested levels
            return ForumReply._update_nested_reply_recursive(post_id, reply_id, firebase_uid, content)
            
        except Exception:
            return None
    
    @staticmethod
    def _update_nested_reply_recursive(post_id, reply_id, firebase_uid, content, path="replies"):
        """Recursively update nested replies at any depth"""
        try:
            # Build dynamic query for nested replies
            query = {"_id": post_id}
            update_path = path
            
            # Try different nesting levels dynamically
            for depth in range(1, 20):  # Support up to 20 levels deep
                nested_path = path
                for i in range(depth):
                    nested_path += ".nested_replies"
                
                query_key = f"{nested_path}.reply_id"
                uid_key = f"{nested_path}.firebase_uid"
                
                query[query_key] = reply_id
                query[uid_key] = firebase_uid
                
                result = ForumPost.collection.update_one(
                    query,
                    {
                        "$set": {
                            f"{nested_path}.$.content": content,
                            f"{nested_path}.$.updated_at": datetime.utcnow(),
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                
                if result.modified_count > 0:
                    return result
                
                # Reset query for next iteration
                query = {"_id": post_id}
            
            return None
            
        except Exception:
            return None
    
    @staticmethod
    def delete_reply(post_id, reply_id, firebase_uid):
        """Delete a reply - Enhanced for nested replies"""
        try:
            if isinstance(post_id, str):
                post_id = ObjectId(post_id)
            
            # First try to delete from main replies
            result = ForumPost.collection.update_one(
                {"_id": post_id},
                {
                    "$pull": {
                        "replies": {
                            "reply_id": reply_id,
                            "firebase_uid": firebase_uid
                        }
                    },
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
            
            if result.modified_count > 0:
                return result
            
            # If not found in main replies, try nested replies
            return ForumReply._delete_nested_reply_recursive(post_id, reply_id, firebase_uid)
            
        except Exception:
            return None
    
    @staticmethod
    def _delete_nested_reply_recursive(post_id, reply_id, firebase_uid, path="replies"):
        """Recursively delete nested replies at any depth"""
        try:
            # Try different nesting levels dynamically
            for depth in range(1, 20):  # Support up to 20 levels deep
                nested_path = path
                for i in range(depth):
                    nested_path += ".nested_replies"
                
                result = ForumPost.collection.update_one(
                    {"_id": post_id},
                    {
                        "$pull": {
                            f"{nested_path}": {
                                "reply_id": reply_id,
                                "firebase_uid": firebase_uid
                            }
                        },
                        "$set": {"updated_at": datetime.utcnow()}
                    }
                )
                
                if result.modified_count > 0:
                    return result
            
            return None
            
        except Exception:
            return None
    
    @staticmethod
    def create_nested_reply(post_id, parent_reply_id, firebase_uid, content, nested_reply_id=None):
        """Create a nested reply - Enhanced for infinite depth"""
        if not nested_reply_id:
            nested_reply_id = str(ObjectId())
            
        nested_reply = {
            "firebase_uid": firebase_uid,
            "content": content,
            "created_at": datetime.utcnow(),
            "reply_id": nested_reply_id,
            "nested_replies": []  # Allow further nesting
        }
        
        try:
            if isinstance(post_id, str):
                post_id = ObjectId(post_id)
            
            # First try to add to main replies
            result = ForumPost.collection.update_one(
                {
                    "_id": post_id,
                    "replies.reply_id": parent_reply_id
                },
                {
                    "$push": {"replies.$.nested_replies": nested_reply},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
            
            if result.modified_count > 0:
                return result
            
            # If not found in main replies, search nested replies recursively
            return ForumReply._add_nested_reply_recursive(post_id, parent_reply_id, nested_reply)
            
        except Exception:
            return None
    
    @staticmethod
    def _add_nested_reply_recursive(post_id, parent_reply_id, nested_reply, path="replies"):
        """Recursively add nested reply at any depth"""
        try:
            # Try different nesting levels dynamically
            for depth in range(1, 20):  # Support up to 20 levels deep
                nested_path = path
                for i in range(depth):
                    nested_path += ".nested_replies"
                
                result = ForumPost.collection.update_one(
                    {
                        "_id": post_id,
                        f"{nested_path}.reply_id": parent_reply_id
                    },
                    {
                        "$push": {f"{nested_path}.$.nested_replies": nested_reply},
                        "$set": {"updated_at": datetime.utcnow()}
                    }
                )
                
                if result.modified_count > 0:
                    return result
            
            return None
            
        except Exception:
            return None
    
    @staticmethod
    def update_nested_reply(post_id, parent_reply_id, nested_reply_id, firebase_uid, content):
        """Update nested reply content - Enhanced for infinite depth"""
        try:
            if isinstance(post_id, str):
                post_id = ObjectId(post_id)
            
            # Try different nesting levels dynamically
            for depth in range(1, 20):  # Support up to 20 levels deep
                nested_path = "replies"
                for i in range(depth):
                    nested_path += ".nested_replies"
                
                # Build the query to find the specific nested reply
                query = {
                    "_id": post_id,
                    f"{nested_path}.reply_id": nested_reply_id,
                    f"{nested_path}.firebase_uid": firebase_uid
                }
                
                # Use positional operator to update the specific nested reply
                result = ForumPost.collection.update_one(
                    query,
                    {
                        "$set": {
                            f"{nested_path}.$.content": content,
                            f"{nested_path}.$.updated_at": datetime.utcnow(),
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                
                if result.modified_count > 0:
                    return result
            
            return None
            
        except Exception:
            return None
    
    @staticmethod
    def delete_nested_reply(post_id, parent_reply_id, nested_reply_id, firebase_uid):
        """Delete a nested reply - Enhanced for infinite depth"""
        try:
            if isinstance(post_id, str):
                post_id = ObjectId(post_id)
            
            # Try different nesting levels dynamically
            for depth in range(1, 20):  # Support up to 20 levels deep
                nested_path = "replies"
                for i in range(depth):
                    nested_path += ".nested_replies"
                
                result = ForumPost.collection.update_one(
                    {"_id": post_id},
                    {
                        "$pull": {
                            f"{nested_path}": {
                                "reply_id": nested_reply_id,
                                "firebase_uid": firebase_uid
                            }
                        },
                        "$set": {"updated_at": datetime.utcnow()}
                    }
                )
                
                if result.modified_count > 0:
                    return result
            
            return None
            
        except Exception:
            return None
    
    @staticmethod
    def delete_by_post_id(post_id):
        """Delete all replies for a post (when post is deleted)"""
        # This is automatically handled when the post is deleted
        # since replies are embedded in the post document
        pass

# === Firebase Token Verification Utility ===
class FirebaseTokenManager:
    @staticmethod
    def verify_token(id_token):
        """Verify Firebase ID token and return user data"""
        try:
            decoded_token = auth.verify_id_token(id_token)
            return {
                'success': True,
                'firebase_uid': decoded_token['uid'],
                'email': decoded_token.get('email'),
                'email_verified': decoded_token.get('email_verified', False),
                'name': decoded_token.get('name', ''),
                'picture': decoded_token.get('picture', '')
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }