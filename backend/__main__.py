import argparse
import logging
import os

import uvicorn

from backend.app import create_app


def env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


parser = argparse.ArgumentParser(description="Serve the Granovo pilot application")
parser.add_argument("--host", default=os.environ.get("GRANOVO_HOST", "127.0.0.1"))
parser.add_argument("--port", type=int, default=int(os.environ.get("GRANOVO_PORT", "8000")))
parser.add_argument("--allow-http", action="store_true", default=env_flag("GRANOVO_ALLOW_HTTP"),
                    help="Disable Secure cookies only for isolated local development")
parser.add_argument("--forwarded-allow-ips", default=os.environ.get("GRANOVO_FORWARDED_ALLOW_IPS", "127.0.0.1"),
                    help="Comma-separated proxy addresses trusted to set forwarded headers")
args = parser.parse_args()
logging.basicConfig(level=logging.INFO, format="%(message)s")
uvicorn.run(create_app(secure_cookies=not args.allow_http), host=args.host, port=args.port,
            proxy_headers=True, forwarded_allow_ips=args.forwarded_allow_ips)
