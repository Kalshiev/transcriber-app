import whisper
import sys
import filetype

model = whisper.load_model("medium")

def check_if_audio():
    if len(sys.argv) < 2:
        raise Exception("Please provide a file to transcribe.")
    
    kind = filetype.guess(sys.argv[1])

    if kind is None:
        raise TypeError("No file detected")
    
    if kind.mime.startswith("audio") or kind.mime.startswith("video"):
        return sys.argv[1]
    else:
        raise TypeError("Not a valid file.")
    
def transcribe_audio():
    audio_file = check_if_audio()

    result = model.transcribe(audio_file, language="es", fp16=False)

    with open(f"{audio_file[:-4]}_transcription.txt", "w", encoding="utf-8") as f:
        f.write(result["text"])

def main():
    transcribe_audio()

if __name__ == "__name__":
    main()