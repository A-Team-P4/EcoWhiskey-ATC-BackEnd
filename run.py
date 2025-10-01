#!/usr/bin/env python3
"""
Run script for EcoWhiskey ATC Backend
"""
import uvicorn

from app.config.settings import settings
from app.main import app

if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port, reload=settings.debug)
