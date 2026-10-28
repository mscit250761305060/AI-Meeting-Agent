"""
main.py — Root ASGI entry point for AI Meeting Agent

Forwards to app.main:app, allowing uvicorn to be run as:
    python -m uvicorn main:app --reload
or:
    python -m uvicorn app.main:app --reload
"""

from app.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
