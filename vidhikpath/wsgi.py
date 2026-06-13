"""
WSGI config for vidhikpath project.
"""

import os
from pathlib import Path

from django.core.wsgi import get_wsgi_application
from whitenoise import WhiteNoise

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vidhikpath.settings')

from django.conf import settings

application = get_wsgi_application()

# Production safety: ensure static files are served even if middleware path is altered.
if not settings.DEBUG:
	application = WhiteNoise(application, root=str(Path(settings.STATIC_ROOT)))
