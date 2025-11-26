import asyncio
import os
import sys
from uuid import uuid4

# Add project root to path so we can import app
sys.path.append(os.getcwd())

from app.services.transcribe import get_transcribe_service, TranscriptionError

async def main():
    service = get_transcribe_service()
    
    # Use the existing out.mp3 in the root if available
    file_path = "out.mp3"
    if len(sys.argv) > 1:
        file_path = sys.argv[1]

    if not os.path.exists(file_path):
        print(f"File '{file_path}' not found. Please provide a path to an audio file.")
        print("Usage: python scripts/test_transcribe.py [path/to/audio.mp3]")
        return

    print(f"Reading {file_path}...")
    with open(file_path, "rb") as f:
        audio_bytes = f.read()

    print(f"Transcribing {len(audio_bytes)} bytes using Amazon Transcribe Streaming...")
    try:
        session_id = uuid4()
        # Content type is passed but our new service converts everything via ffmpeg
        result = await service.transcribe_session_audio(session_id, audio_bytes, "audio/mpeg")
        
        print("\n--- Transcript Result ---")
        print(result.transcript)
        print("-------------------------")
        
    except TranscriptionError as e:
        print(f"\nTranscription Error: {e}")
    except Exception as e:
        print(f"\nUnexpected Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
