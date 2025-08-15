# models.py
from .db_connection import db
from datetime import datetime

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
        post = {
            "username": username,
            "content": content,
            "image": image,
            "likes": [],
            "created_at": datetime.utcnow(),
            "replies": []
        }
        return ForumPost.collection.insert_one(post)

    @staticmethod
    def like(post_id, username):
        return ForumPost.collection.update_one(
            {"_id": post_id},
            {"$addToSet": {"likes": username}}
        )

    @staticmethod
    def add_reply(post_id, reply):
        return ForumPost.collection.update_one(
            {"_id": post_id},
            {"$push": {"replies": reply}}
        )


# === ForumReply ===
class ForumReply:
    @staticmethod
    def create(post_id, username, content):
        reply = {
            "username": username,
            "content": content,
            "created_at": datetime.utcnow()
        }
        return ForumPost.add_reply(post_id, reply)
