import hashlib


def get_hash(text):

    return hashlib.md5(

        text.lower().encode()

    ).hexdigest()