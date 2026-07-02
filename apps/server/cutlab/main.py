"""Server entrypoint: `python -m cutlab.main` (or `uvicorn cutlab.main:app`)."""
from __future__ import annotations

import logging

from . import config
from .api import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

config.verify_ffmpeg()
config.ensure_dirs()
app = create_app(verify_ffmpeg=False)


def main() -> None:
    import uvicorn

    uvicorn.run(app, host=config.SERVER_HOST, port=config.SERVER_PORT, log_level="info")


if __name__ == "__main__":
    main()
