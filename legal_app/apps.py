import json
import logging
import sys
from pathlib import Path

from django.conf import settings
from django.apps import AppConfig
from django.contrib.staticfiles.storage import staticfiles_storage


class LegalAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'legal_app'

    def ready(self):
        management_commands_to_skip = {
            "check",
            "collectstatic",
            "createsuperuser",
            "dbshell",
            "makemigrations",
            "migrate",
            "shell",
            "showmigrations",
            "test",
        }
        if len(sys.argv) > 1 and sys.argv[1] in management_commands_to_skip:
            return

        logger = logging.getLogger("legal_app")
        static_root = Path(settings.STATIC_ROOT)
        manifest_file = static_root / "staticfiles.json"
        manifest_map = {}

        if manifest_file.exists():
            try:
                with manifest_file.open("r", encoding="utf-8") as file_obj:
                    raw_manifest = json.load(file_obj)
                manifest_map = raw_manifest.get("paths", raw_manifest)
            except Exception as exc:
                logger.warning("Failed to read static manifest at startup: %s", exc)

        logger.info("Static startup: STATIC_ROOT=%s exists=%s", static_root, static_root.exists())
        logger.info("Static startup: DEBUG=%s", settings.DEBUG)
        logger.info("Static startup: STATIC_URL=%s", settings.STATIC_URL)
        logger.info("Static startup: middleware=%s", settings.MIDDLEWARE)
        logger.info(
            "Static startup: whitenoise_middleware_active=%s",
            "whitenoise.middleware.WhiteNoiseMiddleware" in settings.MIDDLEWARE,
        )
        logger.info(
            "Static startup: staticfiles backend=%s",
            settings.STORAGES.get("staticfiles", {}).get("BACKEND"),
        )
        logger.info(
            "Static startup: manifest_exists=%s manifest_entries=%s",
            manifest_file.exists(),
            len(manifest_map),
        )

        for source_name in ["css/base.css", "css/landing.css"]:
            hashed_name = manifest_map.get(source_name)
            unhashed_exists = (static_root / source_name).exists()
            hashed_exists = bool(hashed_name and (static_root / hashed_name).exists())

            try:
                resolved_url = staticfiles_storage.url(source_name)
            except Exception as exc:
                resolved_url = f"<resolution-error: {exc}>"

            try:
                storage_hashed_name = staticfiles_storage.hashed_name(source_name)
            except Exception as exc:
                storage_hashed_name = f"<hash-error: {exc}>"

            logger.info(
                "Static startup: source=%s unhashed_exists=%s manifest_hashed_name=%s storage_hashed_name=%s hashed_exists=%s resolved_url=%s",
                source_name,
                unhashed_exists,
                hashed_name,
                storage_hashed_name,
                hashed_exists,
                resolved_url,
            )

            if hashed_name:
                logger.info(
                    "Static startup: requested_path=%s exists=%s",
                    f"/static/{hashed_name}",
                    (static_root / hashed_name).exists(),
                )
