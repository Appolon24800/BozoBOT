import base64
import time

import requests
import asyncio
from pathlib import Path
from urllib.parse import quote
import logging
import os
import dotenv

from fastapi import HTTPException

from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

dotenv.load_dotenv()

class FastAPIMediaBridge_Singleton:
    """Bridge between Discord bot and FastAPI audio server"""

    def __init__(self, fastapi_url=f"http://{os.getenv('IP')}:3069", file_server_url=f"http://{os.getenv('IP')}:3096"):
        self.fastapi_url = fastapi_url
        self.file_server_url = file_server_url
        self.session = requests.Session()
        self.bot = None

    def trigger_audio_playback(self, file_path: Path, loop=False):
        """
        Trigger audio playbook on the FastAPI server

        Args:
            file_path: Path to the audio file
            loop: Whether to loop forever
        """
        try:
            # Get relative path from the sounds folder for the URL
            # This preserves the folder structure in the URL
            relative_path = file_path.relative_to(Path(os.getenv('MEDIA_PATH')))
            encoded_path = quote(str(relative_path).replace('\\', '/'))
            audio_url = f"{self.file_server_url}/media/{encoded_path}"

            # Send request to FastAPI server
            response = self.session.post(
                f"{self.fastapi_url}/play",
                json={
                    "audio_url": audio_url,
                    "volume": 1,
                    "loop": loop,
                },
                timeout=5
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"Audio playback triggered: {relative_path} to {result['clients_notified']} clients")
                return True
            else:
                logger.error(f"Failed to trigger playback: {response.status_code} - {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Error communicating with FastAPI server: {e}")
            return False
        except ValueError as e:
            logger.error(f"Path error: {e}")
            return False

    def trigger_video_playback(self, file_path: Path):
        """
        Trigger video playbook on the FastAPI server

        Args:
            file_path: Path to the video file
        """
        try:
            # Get relative path from the sounds folder for the URL
            # This preserves the folder structure in the URL
            relative_path = file_path.relative_to(Path(os.getenv('MEDIA_PATH')))
            encoded_path = quote(str(relative_path).replace('\\', '/'))
            video_url = f"{self.file_server_url}/media/{encoded_path}"
            print(video_url)

            # Send request to FastAPI server
            response = self.session.post(
                f"{self.fastapi_url}/vplay",
                json={
                    "video_url": video_url,
                    "volume": 1
                },
                timeout=5
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"Video playback triggered: {relative_path} to {result['clients_notified']} clients")
                return True
            else:
                logger.error(f"Failed to trigger playback: {response.status_code} - {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Error communicating with FastAPI server: {e}")
            return False
        except ValueError as e:
            logger.error(f"Path error: {e}")
            return False

    def get_server_status(self):
        """Check if the FastAPI server is running"""
        try:
            response = self.session.get(f"{self.fastapi_url}/health", timeout=5)
            return response.status_code == 200, response.json()['media_status']
        except requests.exceptions.RequestException:
            return False

    def pause_media(self):
        """Pause current playing media"""
        try:
            response = self.session.post(f"{self.fastapi_url}/pause", timeout=5)
            return response.status_code == 200, response.json()['status']
        except requests.exceptions.RequestException:
            return False

    def stop_media(self):
        """Stop current playing media"""
        try:
            response = self.session.post(f"{self.fastapi_url}/stop", timeout=5)
            return response.status_code == 200, response.json()['status']
        except requests.exceptions.RequestException:
            return False

    def get_active_connections(self):
        """Get number of active web clients"""
        try:
            response = self.session.get(f"{self.fastapi_url}/connections", timeout=5)
            if response.status_code == 200:
                return response.json().get("active_connections", 0)
        except requests.exceptions.RequestException:
            pass
        return 0

FastAPIMediaBridge = FastAPIMediaBridge_Singleton()

# Simple file server to serve your OGG files
# Fix the create_file_server function
def create_file_server(media_folder, port=3096):
    """Create a simple HTTP file server for serving audio files"""

    from fastapi import FastAPI, Request
    from fastapi.responses import FileResponse
    from fastapi.middleware.cors import CORSMiddleware

    file_app = FastAPI(title="Bozobot API")

    # Add CORS
    file_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    sounds_path = Path(media_folder) / "Musique"
    videos_path = Path(media_folder) / "Video"

    @file_app.get("/webhook")
    async def discord_webhook_test():
        print(FastAPIMediaBridge.bot)
        if FastAPIMediaBridge.bot:
            # Example: Send the webhook content to a specific Discord channel
            # Replace CHANNEL_ID with your actual channel ID
            channel = FastAPIMediaBridge.bot.fetch_channel(1116010901586321448)
            if channel:
                await channel.send(f"👍 Webhook connected")
                logger.info(f"Test message sent to {channel}")
                return "Test message sent"
            else:
                logger.error(f"Could not find channel")
                return "Could not find channel"
        else:
            logger.error(f"Bot not connected")
            return "Bot not connected"

    @file_app.post("/webhook")
    async def discord_webhook(request: Request):
        print(FastAPIMediaBridge.bot)

        payload = await request.json()

        # Get message content
        content = payload.get('content', '')

        # Process embeds if they exist
        embeds = payload.get('embeds', [])
        embed_text = ''

        for embed in embeds:
            if embed.get('title'):
                embed_text += f"**{embed['title']}**\n"
            if embed.get('description'):
                embed_text += f"{embed['description']}\n"
            if embed.get('url'):
                embed_text += f"Link: {embed['url']}\n"
            embed_text += "\n"

        # Combine content and embed text
        final_content = content
        if embed_text:
            final_content += f"\n{embed_text}"

        # Now you can use the bot instance and final_content
        if FastAPIMediaBridge.bot:
            # Example: Send the webhook content to a specific Discord channel
            # Replace CHANNEL_ID with your actual channel ID
            channel = FastAPIMediaBridge.bot.get_channel(1116010901586321448)
            if channel:
                await channel.send(final_content)
            else:
                logger.error(f"Could not find channel")
        else:
            logger.error(f"Bot not connected")

        # Log the content for debugging
        logger.info(f"Webhook content: {final_content}")

        return {"status": "success"}

    @file_app.get("/metadata/{file_path:path}")
    async def get_metadata(request: Request, file_path: str):
        print("Getting metadata for:", file_path)
        try:
            full_path = sounds_path / file_path
            print(f"Full path: {full_path}")

            # Check if file exists
            if not full_path.exists():
                raise HTTPException(status_code=404, detail="File not found")

            # Load the audio file with mutagen
            from mutagen import File
            from mutagen.id3 import APIC
            import mimetypes

            audio_file = File(str(full_path))
            if audio_file is None:
                raise HTTPException(status_code=400, detail="Unsupported file format")

            print(f"File info: {audio_file.info}")
            print(f"Available tags: {list(audio_file.keys()) if audio_file else 'No tags'}")
            print(f"All tag data: {dict(audio_file) if audio_file else 'No tags'}")

            # Helper function to get tag value
            def get_tag_value(tags, *keys):
                """Get the first non-None value from multiple possible tag keys"""
                if not tags:
                    return None
                for key in keys:
                    # Try exact match first
                    value = tags.get(key)
                    if value:
                        return value[0] if isinstance(value, list) and value else value

                    # Try case-insensitive match for Vorbis comments
                    for tag_key in tags.keys():
                        if tag_key.upper() == key.upper():
                            value = tags[tag_key]
                            return value[0] if isinstance(value, list) and value else value
                return None

            # Extract basic metadata
            tags = dict(audio_file) if audio_file else {}
            info = audio_file.info if audio_file else None

            metadata = {
                "title": get_tag_value(tags, "TIT2", "TITLE", "title", "\xa9nam"),
                "artist": get_tag_value(tags, "TPE1", "ARTIST", "artist", "\xa9ART"),
                "album": get_tag_value(tags, "TALB", "ALBUM", "album", "\xa9alb"),
                "albumartist": get_tag_value(tags, "TPE2", "ALBUMARTIST", "albumartist", "aART"),
                "year": get_tag_value(tags, "TDRC", "DATE", "date", "year", "\xa9day"),
                "genre": get_tag_value(tags, "TCON", "GENRE", "genre", "\xa9gen"),
                "track": get_tag_value(tags, "TRCK", "TRACKNUMBER", "tracknumber", "track", "trkn"),
                "track_total": None,  # Will be extracted from track if present
                "disc": get_tag_value(tags, "TPOS", "DISCNUMBER", "discnumber", "disc", "disk"),
                "disc_total": None,  # Will be extracted from disc if present
                "duration": info.length if info else None,
                "bitrate": getattr(info, 'bitrate', None),
                "samplerate": getattr(info, 'sample_rate', None),
                "channels": getattr(info, 'channels', None),
                "filesize": full_path.stat().st_size,
                "albumart": None
            }

            # Parse track number (format: "1/12" or just "1")
            if metadata["track"]:
                track_str = str(metadata["track"])
                if "/" in track_str:
                    track_parts = track_str.split("/")
                    metadata["track"] = int(track_parts[0]) if track_parts[0].isdigit() else None
                    metadata["track_total"] = int(track_parts[1]) if len(track_parts) > 1 and track_parts[
                        1].isdigit() else None
                elif track_str.isdigit():
                    metadata["track"] = int(track_str)

            # Parse disc number (format: "1/2" or just "1")
            if metadata["disc"]:
                disc_str = str(metadata["disc"])
                if "/" in disc_str:
                    disc_parts = disc_str.split("/")
                    metadata["disc"] = int(disc_parts[0]) if disc_parts[0].isdigit() else None
                    metadata["disc_total"] = int(disc_parts[1]) if len(disc_parts) > 1 and disc_parts[
                        1].isdigit() else None
                elif disc_str.isdigit():
                    metadata["disc"] = int(disc_str)

            # Parse year (might be full date)
            if metadata["year"]:
                year_str = str(metadata["year"])
                if len(year_str) >= 4:
                    metadata["year"] = int(year_str[:4]) if year_str[:4].isdigit() else None

            # Handle album art
            try:
                album_art = None

                # Different file formats store artwork differently
                if hasattr(audio_file, 'tags') and audio_file.tags:
                    # ID3 tags (MP3)
                    if "APIC:" in str(audio_file.tags.keys()):
                        for key in audio_file.tags.keys():
                            if key.startswith("APIC:"):
                                apic = audio_file.tags[key]
                                if hasattr(apic, 'data'):
                                    album_art = apic.data
                                    break
                    # MP4 tags
                    elif "covr" in audio_file.tags:
                        cover = audio_file.tags["covr"][0]
                        album_art = bytes(cover)
                    # Vorbis comments (OGG, FLAC)
                    elif "METADATA_BLOCK_PICTURE" in audio_file.tags:
                        import base64
                        from mutagen.flac import Picture
                        pic_data = audio_file.tags["METADATA_BLOCK_PICTURE"][0]
                        pic = Picture(base64.b64decode(pic_data))
                        album_art = pic.data

                if album_art:
                    # Detect MIME type
                    mime_type = "image/jpeg"  # Default
                    if album_art.startswith(b'\x89PNG'):
                        mime_type = "image/png"
                    elif album_art.startswith(b'GIF'):
                        mime_type = "image/gif"
                    elif album_art.startswith(b'\xff\xd8\xff'):
                        mime_type = "image/jpeg"

                    base64_image = base64.b64encode(album_art).decode('utf-8')
                    metadata["albumart"] = f"data:{mime_type};base64,{base64_image}"

            except Exception as e:
                print(f"Error extracting album art: {e}")

            return JSONResponse(content={"metadata": metadata})

        except HTTPException:
            raise
        except Exception as e:
            print(f"Error extracting metadata: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Error extracting metadata: {str(e)}")

    @file_app.get("/media/{file_path:path}")
    async def serve_file(request: Request, file_path: str):
        """Serve media files from subdirectories"""
        from urllib.parse import unquote
        decoded_path = unquote(file_path)

        full_path = Path(media_folder) / decoded_path
        print(full_path)

        if full_path.exists() and full_path.is_file():
            if '/Musique/' in full_path.name:
                return FileResponse(
                    path=str(full_path),
                    media_type="audio/*",
                    headers={"Accept-Ranges": "bytes"}
                )
            else:
                return FileResponse(
                    path=str(full_path),
                    media_type="video/*",
                    headers={"Accept-Ranges": "bytes"}
                )
        else:
            raise HTTPException(status_code=404, detail="Media file not found")

    return file_app, port


# Fix the main execution part
if __name__ == "__main__":
    import uvicorn
    from threading import Thread

    MEDIA_FOLDER = os.getenv('MEDIA_PATH')

    file_app, file_port = create_file_server(MEDIA_FOLDER)

    # Start file server in a separate thread
    def run_file_server():
        uvicorn.run(file_app, host="0.0.0.0", port=file_port, log_level="info")

    file_server_thread = Thread(target=run_file_server, daemon=True)
    file_server_thread.start()

    print(f"File server started on port {file_port}")
    print(f"Media files served recursively from: {MEDIA_FOLDER}")

    # Keep the script running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")