from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_lawyer = models.BooleanField(default=False)
    phone = models.CharField(max_length=15, blank=True)
    location = models.CharField(max_length=100, blank=True)
    profile_photo = models.ImageField(upload_to='profiles/', blank=True)
    
    # Lawyer specific fields
    lawyer_type = models.CharField(max_length=50, blank=True)
    experience = models.IntegerField(null=True, blank=True)
    license_document = models.FileField(upload_to='licenses/', blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {'Lawyer' if self.is_lawyer else 'User'}"

class ForumPost(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    image = models.ImageField(upload_to='forum_images/', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    likes = models.ManyToManyField(User, related_name='liked_posts', blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.content[:50]}"

class ForumReply(models.Model):
    post = models.ForeignKey(ForumPost, on_delete=models.CASCADE, related_name='replies')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Reply by {self.user.username}"
