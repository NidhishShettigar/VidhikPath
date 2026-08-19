import json
import os
import shutil
import stat
from pathlib import Path

from django.conf import settings
from django.core.management.base import CommandError
from django.contrib.staticfiles.storage import staticfiles_storage
from django.contrib.staticfiles.management.commands.collectstatic import (
    Command as DjangoCollectstaticCommand,
)


class Command(DjangoCollectstaticCommand):
    """Project collectstatic override to force a clean static root on each build."""

    def _handle_remove_readonly(self, func, path, exc_info):
        import os
        import stat

        del exc_info
        os.chmod(path, stat.S_IWRITE)
        func(path)

    def handle(self, *args, **options):
        static_root = Path(settings.STATIC_ROOT)
        manifest_file = static_root / "staticfiles.json"

        if static_root.exists():
            shutil.rmtree(static_root, onerror=self._handle_remove_readonly)
            self.stdout.write(
                self.style.WARNING(f"Removed existing STATIC_ROOT: {static_root}")
            )

        if manifest_file.exists():
            manifest_file.unlink()
            self.stdout.write(
                self.style.WARNING(f"Removed existing manifest: {manifest_file}")
            )

        static_root.mkdir(parents=True, exist_ok=True)

        # Also clear stale records in destination storages before collect.
        options["clear"] = True
        result = super().handle(*args, **options)

        copied_count = len(getattr(self, "copied_files", []))
        unmodified_count = len(getattr(self, "unmodified_files", []))
        post_processed_count = len(getattr(self, "post_processed_files", []))

        self.stdout.write(self.style.SUCCESS(f"collectstatic copied_files={copied_count}"))
        self.stdout.write(
            self.style.SUCCESS(f"collectstatic unmodified_files={unmodified_count}")
        )
        self.stdout.write(
            self.style.SUCCESS(f"collectstatic post_processed_files={post_processed_count}")
        )

        if not manifest_file.exists():
            raise CommandError(
                f"Manifest missing after collectstatic: {manifest_file}. "
                "Hashed static assets were not generated."
            )

        with manifest_file.open("r", encoding="utf-8") as file_obj:
            raw_manifest = json.load(file_obj)
        manifest_map = raw_manifest.get("paths", raw_manifest)

        self.stdout.write(
            self.style.SUCCESS(f"collectstatic manifest_entries={len(manifest_map)}")
        )

        required_sources = [
            "css/base.css",
            "css/landing.css",
            "css/login.css",
            "css/dashboard.css",
        ]
        missing_entries = []
        missing_hashed_files = []

        for source_name in required_sources:
            manifest_hashed = manifest_map.get(source_name)
            self.stdout.write(
                self.style.SUCCESS(
                    f"manifest mapping: {source_name} -> {manifest_hashed}"
                )
            )

            if not manifest_hashed:
                missing_entries.append(source_name)
                continue

            hashed_path = static_root / manifest_hashed
            if not hashed_path.exists():
                missing_hashed_files.append(f"{source_name} -> {manifest_hashed}")

            try:
                storage_hashed = staticfiles_storage.hashed_name(source_name)
            except Exception as exc:
                storage_hashed = f"<error: {exc}>"

            self.stdout.write(
                self.style.SUCCESS(
                    f"storage.hashed_name({source_name})={storage_hashed}"
                )
            )

        if missing_entries or missing_hashed_files:
            details = []
            if missing_entries:
                details.append(
                    "missing manifest entries: " + ", ".join(missing_entries)
                )
            if missing_hashed_files:
                details.append(
                    "missing hashed files: " + ", ".join(missing_hashed_files)
                )
            raise CommandError(
                "Static manifest/hash generation failed: " + " | ".join(details)
            )

        return result
