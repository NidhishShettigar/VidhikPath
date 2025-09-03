from django.contrib import admin
from django.contrib.auth.models import User
from .models import UserProfile, ForumPost, ForumReply

# Since we're using PyMongo for our custom models, we can't use Django's admin 
# registration decorators directly. Instead, we can create custom admin views
# or use Django admin for User model only and create custom management commands
# for PyMongo collections.

# You can still manage Django User model through admin
# The PyMongo collections would need custom admin interfaces or management commands

# Example: If you want to view PyMongo data in admin, you'd need to create
# proxy models or custom admin views. For now, keeping it simple with just
# the User model which is still using Django ORM.

# Note: To properly integrate PyMongo with Django admin, you would need to:
# 1. Create proxy models that interface with PyMongo
# 2. Override admin methods to work with PyMongo operations
# 3. Or create custom admin views outside of Django's admin system