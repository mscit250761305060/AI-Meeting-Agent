transcript_callback = None


def register_transcript_callback(callback):

    global transcript_callback

    transcript_callback = callback


def send_transcript(text):
    if transcript_callback:
        transcript_callback(text)

    try:
        from app.services.ws_manager import manager
        manager.broadcast_sync({
            "action": "transcript_update",
            "text": text
        })
    except Exception:
        pass