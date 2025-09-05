import pyrebase
import firebase_admin
from firebase_admin import auth
from django.conf import settings
import json

# Initialize Pyrebase
firebase = pyrebase.initialize_app(settings.PYREBASE_CONFIG)
auth_client = firebase.auth()

class FirebaseAuth:
    @staticmethod
    def create_user_with_email_password(email, password):
        """Create a new user with email and password"""
        try:
            user = auth_client.create_user_with_email_and_password(email, password)
            # Send email verification
            auth_client.send_email_verification(user['idToken'])
            return {
                'success': True,
                'user': user,
                'message': 'User created successfully. Please check your email for verification.'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to create user'
            }

    @staticmethod
    def sign_in_with_email_password(email, password):
        """Sign in user with email and password"""
        try:
            user = auth_client.sign_in_with_email_and_password(email, password)
            return {
                'success': True,
                'user': user,
                'message': 'User signed in successfully'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Invalid credentials'
            }

    @staticmethod
    def verify_id_token(id_token):
        """Verify Firebase ID token"""
        try:
            decoded_token = auth.verify_id_token(id_token)
            return {
                'success': True,
                'decoded_token': decoded_token
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    def send_password_reset_email(email):
        """Send password reset email"""
        try:
            auth_client.send_password_reset_email(email)
            return {
                'success': True,
                'message': 'Password reset email sent'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to send password reset email'
            }

    @staticmethod
    def refresh_token(refresh_token):
        """Refresh Firebase token"""
        try:
            user = auth_client.refresh(refresh_token)
            return {
                'success': True,
                'user': user
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }