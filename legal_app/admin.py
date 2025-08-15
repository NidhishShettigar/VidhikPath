from django.contrib import admin
from .models import UserProfile, ForumPost, ForumReply

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_lawyer', 'location', 'lawyer_type']
    list_filter = ['is_lawyer', 'lawyer_type']

@admin.register(ForumPost)
class ForumPostAdmin(admin.ModelAdmin):
    list_display = ['user', 'content', 'created_at']
    list_filter = ['created_at']

@admin.register(ForumReply)
class ForumReplyAdmin(admin.ModelAdmin):
    list_display = ['user', 'post', 'content', 'created_at']
    list_filter = ['created_at']
