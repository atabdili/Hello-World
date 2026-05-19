#!/usr/bin/env python3
"""
Voice cloning TTS using Coqui XTTS-v2.
Clones a voice from a sample file, then synthesizes text with that voice.
"""

import argparse
import sys
from pathlib import Path


def clone_and_speak(voice_sample: str, text: str, output_file: str, language: str = "en") -> None:
    from TTS.api import TTS

    sample_path = Path(voice_sample)
    if not sample_path.exists():
        print(f"Error: voice sample not found: {voice_sample}", file=sys.stderr)
        sys.exit(1)

    print("Loading XTTS-v2 model (first run downloads ~1.8 GB)...")
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")

    print(f"Synthesizing: \"{text}\"")
    tts.tts_to_file(
        text=text,
        speaker_wav=str(sample_path),
        language=language,
        file_path=output_file,
    )
    print(f"Saved to: {output_file}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clone a voice from an audio sample and synthesize speech."
    )
    parser.add_argument(
        "--sample",
        required=True,
        help="Path to the voice sample audio file (WAV recommended, 6-30 seconds).",
    )
    parser.add_argument(
        "--text",
        required=True,
        help="Text to synthesize with the cloned voice.",
    )
    parser.add_argument(
        "--output",
        default="output.wav",
        help="Output WAV file path (default: output.wav).",
    )
    parser.add_argument(
        "--language",
        default="en",
        help=(
            "Language code for synthesis (default: en). "
            "Supported: en, es, fr, de, it, pt, pl, tr, ru, nl, cs, ar, zh-cn, hu, ko, ja, hi."
        ),
    )
    args = parser.parse_args()
    clone_and_speak(args.sample, args.text, args.output, args.language)


if __name__ == "__main__":
    main()
