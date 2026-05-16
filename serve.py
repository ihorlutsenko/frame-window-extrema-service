from __future__ import annotations

import os

from waitress import serve

from app import create_app


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    serve(create_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
