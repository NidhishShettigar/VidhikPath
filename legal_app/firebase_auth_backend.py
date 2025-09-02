from django.contrib.auth.models import User
from firebase_admin import auth as firebase_auth
from django.conf import settings

class FirebaseAuthenticationBackend:
    def authenticate(self, request, firebase_token=None):
        try:
            decoded_token = firebase_auth.verify_id_token(firebase_token)
            uid = decoded_token['uid']

            # Optional: You can sync user info from Firebase to Django User
            # For example, use email as username
            email = decoded_token.get('email', '')
            if not email:
                return None

            user, created = User.objects.get_or_create(username=email, defaults={
                'email': email,
                'password': User.objects.make_random_password(),  # firebase auth managed
            })

            return user
        except Exception as e:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
