import speech_recognition as sr


def transcribe_microphone():

    recognizer = sr.Recognizer()

    with sr.Microphone() as source:

        print("Listening...")

        recognizer.adjust_for_ambient_noise(
            source,
            duration=5
        )

        audio = recognizer.listen(source)

    try:

        text = recognizer.recognize_google(
            audio
        )

        return {
            "success": True,
            "transcript": text
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }