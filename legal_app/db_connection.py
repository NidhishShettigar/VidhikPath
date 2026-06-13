import logging
import os
import time
from urllib.parse import urlparse

import certifi
import dns.resolver
from pymongo import MongoClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

logger = logging.getLogger(__name__)


class _NullMongoCursor:
    def sort(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def skip(self, *args, **kwargs):
        return self

    def __iter__(self):
        return iter(())


class _NullMongoResult:
    acknowledged = False
    inserted_id = None
    matched_count = 0
    modified_count = 0
    deleted_count = 0
    upserted_id = None


class _NullMongoCollection:
    def __init__(self, name):
        self.name = name

    def find(self, *args, **kwargs):
        return _NullMongoCursor()

    def find_one(self, *args, **kwargs):
        return None

    def insert_one(self, *args, **kwargs):
        return _NullMongoResult()

    def update_one(self, *args, **kwargs):
        return _NullMongoResult()

    def delete_one(self, *args, **kwargs):
        return _NullMongoResult()

    def aggregate(self, *args, **kwargs):
        return _NullMongoCursor()


class _NullMongoDatabase:
    def __getitem__(self, item):
        return _NullMongoCollection(item)

    def __getattr__(self, item):
        if item.startswith("__"):
            raise AttributeError(item)
        return _NullMongoCollection(item)


def _safe_uri_for_logs(uri):
    """Redact credentials while still indicating whether a URI was loaded."""
    try:
        if "@" in uri:
            return uri.split("@", 1)[1]
        return uri
    except Exception:
        return "<unavailable>"


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _extract_srv_host(uri):
    parsed = urlparse(uri)
    netloc = parsed.netloc.rsplit("@", 1)[-1]
    return netloc.split(":", 1)[0].strip()


def _is_render_runtime():
    return bool(os.getenv("RENDER")) or bool(os.getenv("RENDER_EXTERNAL_URL"))


def _validate_srv_dns(host):
    srv_record = f"_mongodb._tcp.{host}"
    try:
        answers = dns.resolver.resolve(srv_record, "SRV")
        count = len(list(answers))
        logger.info("Atlas SRV lookup succeeded for %s (%s records).", srv_record, count)
    except Exception as exc:
        logger.warning("Atlas SRV lookup failed for %s: %s", srv_record, exc)

    try:
        txt_answers = dns.resolver.resolve(host, "TXT")
        txt_count = len(list(txt_answers))
        logger.info("Atlas TXT lookup succeeded for %s (%s records).", host, txt_count)
    except Exception as exc:
        logger.warning("Atlas TXT lookup failed for %s: %s", host, exc)


def _build_client_options():
    options = {
        "tls": True,
        "tlsCAFile": certifi.where(),
        "serverSelectionTimeoutMS": _env_int("MONGO_SERVER_SELECTION_TIMEOUT_MS", 7000),
        "connectTimeoutMS": _env_int("MONGO_CONNECT_TIMEOUT_MS", 7000),
        "socketTimeoutMS": _env_int("MONGO_SOCKET_TIMEOUT_MS", 10000),
        "retryWrites": True,
    }

    allow_invalid = _env_bool("MONGO_TLS_ALLOW_INVALID_CERTS", False)
    if allow_invalid and _is_render_runtime():
        options["tlsAllowInvalidCertificates"] = True
        logger.warning(
            "MONGO_TLS_ALLOW_INVALID_CERTS is enabled on Render. This is for troubleshooting only and should be disabled in production."
        )

    return options


def _degraded_db(reason):
    logger.error("MongoDB degraded mode enabled: %s", reason)
    return {
        "connected": False,
        "degraded": True,
        "reason": reason,
    }, _NullMongoDatabase(), None


def _connect_with_retry(mongo_uri, mongo_db_name, client_options):
    max_retries = _env_int("MONGO_CONNECT_MAX_RETRIES", 3)
    backoff_seconds = max(1, _env_int("MONGO_CONNECT_RETRY_BACKOFF_SECONDS", 2))

    for attempt in range(1, max_retries + 1):
        try:
            client = MongoClient(mongo_uri, **client_options)
            client.admin.command("ping")
            logger.info("MongoDB Atlas ping successful for database '%s'.", mongo_db_name)
            return (
                {
                    "connected": True,
                    "degraded": False,
                    "reason": "",
                },
                client[mongo_db_name],
                client,
            )
        except ServerSelectionTimeoutError as exc:
            logger.error(
                "MongoDB server selection timed out (attempt %s/%s): %s",
                attempt,
                max_retries,
                exc,
            )
        except PyMongoError as exc:
            logger.error(
                "MongoDB connection error (attempt %s/%s): %s",
                attempt,
                max_retries,
                exc,
            )

        if attempt < max_retries:
            wait_seconds = backoff_seconds * attempt
            logger.info("Retrying MongoDB connection in %s seconds...", wait_seconds)
            time.sleep(wait_seconds)

    return _degraded_db("Unable to connect to MongoDB Atlas after retries.")


raw_mongo_uri = os.getenv("MONGO_URI")
logger.info("MONGO_URI loaded from environment: %s", bool(raw_mongo_uri))

mongo_status = {
    "connected": False,
    "degraded": True,
    "reason": "MongoDB not initialized yet.",
}
db = _NullMongoDatabase()
client = None

if raw_mongo_uri is None or not raw_mongo_uri.strip():
    mongo_status, db, client = _degraded_db(
        "MONGO_URI is missing. Set Render environment variable 'MONGO_URI'."
    )
else:
    # Guard against common env formatting mistakes like wrapped quotes.
    mongo_uri = raw_mongo_uri.strip().strip('"').strip("'")
    mongo_db_name = os.getenv("MONGO_DB_NAME", "vidhikpath").strip() or "vidhikpath"

    if not mongo_uri.startswith("mongodb+srv://"):
        mongo_status, db, client = _degraded_db(
            "Invalid MONGO_URI scheme. Expected URI starting with 'mongodb+srv://'."
        )
    else:
        atlas_host = _extract_srv_host(mongo_uri)
        logger.info("MONGO_URI accepted for Atlas host: %s", _safe_uri_for_logs(mongo_uri))
        logger.info("Atlas cluster host parsed from SRV URI: %s", atlas_host)
        _validate_srv_dns(atlas_host)

        client_options = _build_client_options()
        mongo_status, db, client = _connect_with_retry(mongo_uri, mongo_db_name, client_options)


def is_mongo_available():
    return mongo_status.get("connected", False)


def get_mongo_status():
    return dict(mongo_status)