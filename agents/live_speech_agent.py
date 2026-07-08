import speech_recognition as sr

from agents.transcript_source_agent import (
    receive_transcript
)


def listen_once():

    recognizer = sr.Recognizer()

    with sr.Microphone() as source:

        print("Listening...")

        recognizer.adjust_for_ambient_noise(
            source,
            duration=1
        )

        try:

            audio = recognizer.listen(

                source,

                timeout=5,

                phrase_time_limit=10

            )

        except sr.WaitTimeoutError:

            print("No Speech")

            return

    print("Recognizing...")

    try:

        text = recognizer.recognize_google(
            audio
        )

        receive_transcript(text)

    except Exception as e:

        print(e)