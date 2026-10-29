import argparse
import logging

import uvicorn

from backend.app import create_app

parser = argparse.ArgumentParser(description="Serve the Granovo pilot application")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=8000)
parser.add_argument("--allow-http", action="store_true", help="Disable Secure cookies only for isolated local development")
args = parser.parse_args()
logging.basicConfig(level=logging.INFO, format="%(message)s")
uvicorn.run(create_app(secure_cookies=not args.allow_http), host=args.host, port=args.port, proxy_headers=True, forwarded_allow_ips="127.0.0.1")
