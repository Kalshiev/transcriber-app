#!/usr/bin/env python3
"""
Transcriber App — Audio/Video transcription using OpenAI Whisper.
"""

import argparse
import sys

import filetype
import whisper


def parse_args(argv=None):
    """Parse command-line arguments.

    Available Whisper model sizes (in increasing size / accuracy):
      tiny, base, small, medium, large
    """
    parser = argparse.ArgumentParser(
        description="Transcribe audio or video files using OpenAI Whisper.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s recording.mp3\n"
            "  %(prog)s -l en -m small lecture.m4a\n"
            "  %(prog)s --language fr --model large video.mp4\n"
        ),
    )

    parser.add_argument(
        "file",
        nargs="?",
        help="Path to audio or video file to transcribe.",
    )

    parser.add_argument(
        "-l",
        "--language",
        default="es",
        help=(
            "Language of the audio (e.g. en, es, fr, de, pt, it, ja, zh). "
            "Use 'auto' for automatic detection. [default: %(default)s]"
        ),
    )

    parser.add_argument(
        "-m",
        "--model",
        default="medium",
        choices=["tiny", "base", "small", "medium", "large"],
        help=(
            "Whisper model size. Larger models are slower but more accurate. "
            "[default: %(default)s]"
        ),
    )

    return parser.parse_args(argv)


def check_if_audio(file_path):
    """Validate that the given path points to an audio or video file."""
    kind = filetype.guess(file_path)

    if kind is None:
        raise TypeError(f"No file detected at '{file_path}'")

    if kind.mime.startswith("audio") or kind.mime.startswith("video"):
        return file_path
    else:
        raise TypeError(
            f"'{file_path}' is not a valid audio/video file (detected {kind.mime})."
        )


def transcribe_audio(file_path, language, model_name):
    """Load the Whisper model and transcribe the given file."""
    print(f"Loading Whisper model '{model_name}'...")
    model = whisper.load_model(model_name)

    print(f"Transcribing '{file_path}' (language={language})...")
    result = model.transcribe(file_path, language=language, fp16=False)

    # Build output file name — replace original extension with _transcription.txt
    base = file_path.rsplit(".", 1)[0] if "." in file_path else file_path
    out_path = f"{base}_transcription.txt"

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result["text"])

    print(f"Transcription saved to '{out_path}'")


def main():
    args = parse_args()

    if not args.file:
        print("Error: No file provided. Use --help for usage.", file=sys.stderr)
        sys.exit(1)

    try:
        audio_file = check_if_audio(args.file)
    except (TypeError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    transcribe_audio(audio_file, args.language, args.model)


if __name__ == "__main__":
    main()
