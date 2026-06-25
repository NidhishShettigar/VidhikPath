"""Django settings for vidhikpath project."""

import os
from pathlib import Path

import dj_database_url
import firebase_admin
from decouple import config
from dotenv import load_dotenv
from firebase_admin import credentials

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Core security/settings
SECRET_KEY = config("SECRET_KEY", default="django-insecure-change-me")
DEBUG = config("DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = [
    host.strip()
    for host in config(
        "ALLOWED_HOSTS", default=".onrender.com,localhost,127.0.0.1"
    ).split(",")
    if host.strip()
]

render_external_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
if render_external_hostname and render_external_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_external_hostname)

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in config("CSRF_TRUSTED_ORIGINS", default="").split(",")
    if origin.strip()
]
if render_external_hostname:
    csrf_origin = f"https://{render_external_hostname}"
    if csrf_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(csrf_origin)

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "legal_app",
    "django.contrib.staticfiles",
    "corsheaders",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "legal_app.middleware.FirebaseAuthenticationMiddleware",
]

ROOT_URLCONF = "vidhikpath.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "vidhikpath.wsgi.application"

# Relational DB is used by Django sessions and framework tables.
database_url = config("DATABASE_URL", default="")
if database_url:
    DATABASES = {
        "default": dj_database_url.parse(
            database_url,
            conn_max_age=600,
            ssl_require=not DEBUG,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# MongoDB for domain data (env key must exactly match Render variable: MONGO_URI)
MONGO_URI = config("MONGO_URI", default="")
MONGO_DB_NAME = config("MONGO_DB_NAME", default="vidhikpath")

# Firebase (client-side config)
FIREBASE_CONFIG = {
    "apiKey": config("FIREBASE_API_KEY", default=""),
    "authDomain": config("FIREBASE_AUTH_DOMAIN", default=""),
    "projectId": config("FIREBASE_PROJECT_ID", default=""),
    "storageBucket": config("FIREBASE_STORAGE_BUCKET", default=""),
    "messagingSenderId": config("FIREBASE_MESSAGING_SENDER_ID", default=""),
    "appId": config("FIREBASE_APP_ID", default=""),
    "measurementId": config("FIREBASE_MEASUREMENT_ID", default=""),
}

# Firebase Admin init.
#
# Two supported ways to provide credentials on a server like Render where
# you can't commit firebase-service-account.json (it's gitignored, since
# it's a secret):
#
#   1. FIREBASE_CREDENTIALS_JSON - the *entire contents* of the service
#      account JSON file, pasted as the value of a single env var.
#   2. FIREBASE_CREDENTIALS_PATH - a filesystem path to the JSON file
#      (e.g. Render "Secret Files" are mounted under /etc/secrets/...).
#      Defaults to BASE_DIR / "firebase-service-account.json" for local dev.
import json as _json
import logging as _logging

_firebase_logger = _logging.getLogger("legal_app")
firebase_credentials_json = config("FIREBASE_CREDENTIALS_JSON", default="")
firebase_credentials_path = config(
    "FIREBASE_CREDENTIALS_PATH", default=str(BASE_DIR / "firebase-service-account.json")
)

if not firebase_admin._apps:
    cred = None
    cred_source = None
    try:
        if firebase_credentials_json:
            cred = credentials.Certificate(_json.loads(firebase_credentials_json))
            cred_source = "FIREBASE_CREDENTIALS_JSON"
        elif os.path.exists(firebase_credentials_path):
            cred = credentials.Certificate(firebase_credentials_path)
            cred_source = f"file:{firebase_credentials_path}"
    except Exception as exc:
        _firebase_logger.warning("Failed to load Firebase credentials (%s): %s", cred_source, exc)
        cred = None

    if cred is not None:
        try:
            firebase_admin.initialize_app(cred)
            _firebase_logger.info("Firebase Admin SDK initialized from %s", cred_source)
            # Attempt to log project_id and client_email from provided credentials for debugging
            try:
                if firebase_credentials_json:
                    cred_json = _json.loads(firebase_credentials_json)
                elif os.path.exists(firebase_credentials_path):
                    with open(firebase_credentials_path, 'r', encoding='utf-8') as _f:
                        cred_json = _json.load(_f)
                else:
                    cred_json = None

                if cred_json:
                    proj = cred_json.get('project_id')
                    client = cred_json.get('client_email')
                    masked_client = None
                    if client:
                        masked_client = client.split('@')[0] + '@' + client.split('@')[1] if '@' in client else client
                    _firebase_logger.info('Firebase credentials project_id=%s client_email=%s', proj, masked_client)
            except Exception as _exc:
                _firebase_logger.warning('Unable to parse Firebase credentials for debug: %s', _exc)
        except Exception as exc:
            _firebase_logger.warning("Firebase Admin SDK initialize_app failed: %s", exc)
    else:
        _firebase_logger.warning(
            "Firebase Admin SDK NOT initialized: no FIREBASE_CREDENTIALS_JSON env var "
            "and no credentials file found at %s. Firebase token verification will fail.",
            firebase_credentials_path,
        )

PYREBASE_CONFIG = {
    "apiKey": FIREBASE_CONFIG["apiKey"],
    "authDomain": FIREBASE_CONFIG["authDomain"],
    "databaseURL": f"https://{FIREBASE_CONFIG['projectId']}-default-rtdb.firebaseio.com/"
    if FIREBASE_CONFIG["projectId"]
    else "",
    "projectId": FIREBASE_CONFIG["projectId"],
    "storageBucket": FIREBASE_CONFIG["storageBucket"],
    "messagingSenderId": FIREBASE_CONFIG["messagingSenderId"],
    "appId": FIREBASE_CONFIG["appId"],
}

OPENAI_API_KEY = config("OPENAI_API_KEY", default="")
GEMINI_API_KEY = config("GEMINI_API_KEY", default="")

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 86400
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
USE_STATIC_FALLBACK_STORAGE = config(
    "USE_STATIC_FALLBACK_STORAGE", default=False, cast=bool
)
STATICFILES_BACKEND = "whitenoise.storage.CompressedManifestStaticFilesStorage"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": STATICFILES_BACKEND,
    },
}
WHITENOISE_MANIFEST_STRICT = False

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

for directory in [MEDIA_ROOT / "forum_posts", MEDIA_ROOT / "profile_photos", BASE_DIR / "logs"]:
    os.makedirs(directory, exist_ok=True)

FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880
ALLOWED_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".webp"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

FIREBASE_AUTH = {
    "REQUIRE_EMAIL_VERIFICATION": True,
    "AUTO_CREATE_PROFILE": True,
    "LAWYER_VERIFICATION_REQUIRED": True,
    "MAX_FILE_SIZE": 5 * 1024 * 1024,
    "ALLOWED_IMAGE_TYPES": ["image/jpeg", "image/png", "image/jpg"],
    "ALLOWED_DOCUMENT_TYPES": ["application/pdf", "image/jpeg", "image/png"],
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs" / "vidhikpath.log",
        },
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "legal_app": {
            "handlers": ["file", "console"],
            "level": "INFO",
            "propagate": True,
        },
        "django.request": {
            "handlers": ["file", "console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

CORS_ALLOW_ALL_ORIGINS = config("CORS_ALLOW_ALL_ORIGINS", default=DEBUG, cast=bool)
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in config("CORS_ALLOWED_ORIGINS", default="").split(",")
    if origin.strip()
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=not DEBUG, cast=bool)