import time
from pathlib import Path

def watch_transcript(file_path, callback):
    """
    Watches the transcript file for new lines and sends them to the callback function.
    """
    path = Path(file_path)
    if not path.exists():
        # Create an empty file if it doesn't exist
        path.parent.mkdir(exist_ok=True)
        path.touch()
        
    print(f"Watcher: Started watching {file_path}...")
    
    # Move to the end of the file initially
    with open(path, "r", encoding="utf-8") as f:
        f.seek(0, 2)
        
        while True:
            line = f.readline()
            if not line:
                time.sleep(1)  # Sleep briefly if no new content
                continue
                
            clean_line = line.strip()
            if clean_line:
                # Trigger the callback function when a new line is found
                callback(clean_line)

def process_new_requirement(text):
    """
    This is a temporary callback function to test the watcher.
    """
    print(f"Watcher Detected New Line -> Processing: '{text}'")

if __name__ == "__main__":
    # Test the watcher independently
    watch_transcript("data/live_transcript.txt", process_new_requirement)