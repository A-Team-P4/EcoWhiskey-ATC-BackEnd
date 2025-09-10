#!/usr/bin/env python3
"""
Run script for EcoWhiskey ATC Backend
"""
import uvicorn
from app.main import app
from app.config.settings import settings

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )