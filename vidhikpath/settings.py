"""
Django settings for vidhikpath project - Firebase-only authentication
"""

from pathlib import Path
import os
from decouple import config
import firebase_admin
from firebase_admin import credentials
from dotenv import load_dotenv


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'your-secret-key-here'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# Application definition
INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'legal_app',
]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'legal_app.middleware.FirebaseAuthenticationMiddleware',  # Custom Firebase middleware
    # Remove 'django.contrib.auth.middleware.AuthenticationMiddleware'
]

ROOT_URLCONF = 'vidhikpath.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.messages.context_processors.messages',
                # Remove 'django.contrib.auth.context_processors.auth'
            ],
        },
    },
]

WSGI_APPLICATION = 'vidhikpath.wsgi.application'

# Database (Optional - only needed if you want to use Django admin or some Django features)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# MongoDB Configuration
MONGODB_URI = 'mongodb+srv://vidhikpath:vidhikpath@cluster0.m2j80to.mongodb.net/'

# Firebase Configuration - CLIENT SIDE
FIREBASE_CONFIG = {
    'apiKey': "AIzaSyDFXCASnsC1Yi_bpwDuwhkicYNNzhR-v9s",
    'authDomain': "vidhikpath-e9e56.firebaseapp.com",
    'projectId': "vidhikpath-e9e56",
    'storageBucket': "vidhikpath-e9e56.firebasestorage.app",
    'messagingSenderId': "1028848699647",
    'appId': "1:1028848699647:web:f3e9567bd975a03b4064ca",
    'measurementId': "G-H129B0J3HP"
}


# Initialize Firebase Admin SDK
try:
    cred = credentials.Certificate("firebase-service-account.json")
    firebase_admin.initialize_app(cred)
    print("Firebase Admin SDK initialized successfully")
except Exception as e:
    print(f"Firebase Admin initialization error: {e}")

# PyreBase4 Configuration for client-side operations (if needed)
PYREBASE_CONFIG = {
    'apiKey': FIREBASE_CONFIG['apiKey'],
    'authDomain': FIREBASE_CONFIG['authDomain'],
    'databaseURL': f"https://{FIREBASE_CONFIG['projectId']}-default-rtdb.firebaseio.com/",
    'projectId': FIREBASE_CONFIG['projectId'],
    'storageBucket': FIREBASE_CONFIG['storageBucket'],
    'messagingSenderId': FIREBASE_CONFIG['messagingSenderId'],
    'appId': FIREBASE_CONFIG['appId']
}

# API Keys
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Session Configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# Remove password validation since we're using Firebase
AUTH_PASSWORD_VALIDATORS = []

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'  # For production

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Create media directory structure if it doesn't exist
MEDIA_DIRS = [
    os.path.join(MEDIA_ROOT, 'forum_posts'),
    os.path.join(MEDIA_ROOT, 'profile_photos'),
]

for directory in MEDIA_DIRS:
    if not os.path.exists(directory):
        os.makedirs(directory)

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB

# Allowed file extensions
ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom settings for Firebase authentication
FIREBASE_AUTH = {
    'REQUIRE_EMAIL_VERIFICATION': True,
    'AUTO_CREATE_PROFILE': True,
    'LAWYER_VERIFICATION_REQUIRED': True,
    'MAX_FILE_SIZE': 5 * 1024 * 1024,  # 5MB
    'ALLOWED_IMAGE_TYPES': ['image/jpeg', 'image/png', 'image/jpg'],
    'ALLOWED_DOCUMENT_TYPES': ['application/pdf', 'image/jpeg', 'image/png'],
}

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'vidhikpath.log',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'legal_app': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# Create logs directory if it doesn't exist
import os
logs_dir = BASE_DIR / 'logs'
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)
    
    
DEBUG = True