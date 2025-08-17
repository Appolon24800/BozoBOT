import os
import base64
import time
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict
from urllib.parse import quote, unquote

import fastapi
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import asyncio
import dotenv

# Load environment variables
dotenv.load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Bozobot Media Server",
    description="Unified FastAPI server for Discord bot media streaming and file serving",
    version="3.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models
class AudioData(BaseModel):
    audio_url: str = Field(..., description="URL to the audio file to stream")
    volume: Optional[float] = Field(0.5, ge=0, le=1, description="Volume level 0-1")
    loop: Optional[bool] = Field(None, description="Loop mode")


class VideoData(BaseModel):
    video_url: str = Field(..., description="URL to the video file to stream")
    volume: Optional[float] = Field(0.5, ge=0, le=1, description="Volume level 0-1")


# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.media_states: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.media_states[websocket] = "null"
        logger.info(f"Client connected. Total connections: {len(self.active_connections)}")
        logger.info(f"Active connections: {[str(conn) for conn in self.active_connections]}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            if websocket in self.media_states:
                del self.media_states[websocket]
            logger.info(f"Client disconnected. Total connections: {len(self.active_connections)}")
        else:
            logger.warning(f"Tried to disconnect a websocket that wasn't in active_connections")

    async def handle_message(self, websocket: WebSocket, data: dict):
        if data.get("type") == "media_state":
            self.media_states[websocket] = data.get("state", "null")
            logger.info(f"Media state updated: {data.get('state', 'null')}")

    async def broadcast_audio(self, data: dict):
        """Broadcast audio data to all connected clients"""
        logger.info(f"Broadcasting audio to {len(self.active_connections)} connections")

        if not self.active_connections:
            logger.warning("No active connections to broadcast to")
            return

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(data))
                logger.info(f"Successfully sent audio data to connection")
            except Exception as e:
                logger.warning(f"Failed to send to client: {e}")
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)

        logger.info(f"Broadcast complete. {len(self.active_connections)} connections remaining")

    async def broadcast_video(self, data):
        logger.info(f"Broadcasting video to {len(self.active_connections)} connections")

        if not self.active_connections:
            logger.warning("No active connections to broadcast to")
            return

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(data))
                logger.info(f"Successfully sent video data to connection")
            except Exception as e:
                logger.warning(f"Failed to send to client: {e}")
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)

        logger.info(f"Video broadcast complete. {len(self.active_connections)} connections remaining")

    async def broadcast_command(self, command: str):
        """Broadcast control commands (pause, stop) to all clients"""
        logger.info(f"Broadcasting command '{command}' to {len(self.active_connections)} connections")

        if not self.active_connections:
            logger.warning("No active connections to broadcast command to")
            return

        command_data = {
            "command": command,
            "timestamp": time.time()
        }

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(command_data))
                logger.info(f"Successfully sent command to connection")
            except Exception as e:
                logger.warning(f"Failed to send command to client: {e}")
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)

        logger.info(f"Command broadcast complete. {len(self.active_connections)} connections remaining")


manager = ConnectionManager()

# Media paths
MEDIA_FOLDER = Path(os.getenv('MEDIA_PATH'))
sounds_path = MEDIA_FOLDER / "Musique"
videos_path = MEDIA_FOLDER / "Video"


# Bridge functionality - these will be used by the Discord bot
class FastAPIMediaBridge_Singleton:
    """Internal bridge functionality within the same FastAPI server"""

    def __init__(self):
        self.bot = None

    async def trigger_audio_playback(self, file_path: Path, loop=False):
        """
        Trigger audio playback using internal manager

        Args:
            file_path: Path to the audio file
            loop: Whether to loop forever
        """
        try:
            # Get relative path from the media folder for the URL
            relative_path = file_path.relative_to(Path(os.getenv('MEDIA_PATH')))
            encoded_path = quote(str(relative_path).replace('\\', '/'))

            # Use the server's own URL
            server_port = int(os.getenv('PORT_FASTAPI', 8000))
            server_ip = os.getenv('IP_FASTAPI', 'localhost')
            audio_url = f"http://{server_ip}:{server_port}/media/{encoded_path}"

            # Create broadcast data
            broadcast_data = {
                "audio_url": audio_url,
                "volume": 1,
                "timestamp": time.time(),
                "action": "play",
                "loop": loop,
                "metadata": audio_url.replace("/media/Musique", "/metadata")
            }

            logger.info(f"Triggering audio playback for: {relative_path}")
            logger.info(f"Current active connections: {len(manager.active_connections)}")

            # Directly await the broadcast
            await manager.broadcast_audio(broadcast_data)

            logger.info(f"Audio playback triggered: {relative_path} to {len(manager.active_connections)} clients")
            return len(manager.active_connections) > 0

        except Exception as e:
            logger.error(f"Error triggering audio playback: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def trigger_video_playback(self, file_path: Path):
        """
        Trigger video playback using internal manager

        Args:
            file_path: Path to the video file
        """
        try:
            # Get relative path from the media folder for the URL
            relative_path = file_path.relative_to(Path(os.getenv('MEDIA_PATH')))
            encoded_path = quote(str(relative_path).replace('\\', '/'))

            # Use the server's own URL
            server_port = int(os.getenv('PORT_FASTAPI', 8000))
            server_ip = os.getenv('IP_FASTAPI', 'localhost')
            video_url = f"http://{server_ip}:{server_port}/media/{encoded_path}"

            # Create broadcast data
            broadcast_data = {
                "video_url": video_url,
                "volume": 1,
                "timestamp": time.time(),
                "action": "play"
            }

            logger.info(f"Triggering video playback for: {relative_path}")
            logger.info(f"Current active connections: {len(manager.active_connections)}")

            # Directly await the broadcast
            await manager.broadcast_video(broadcast_data)

            logger.info(f"Video playback triggered: {relative_path} to {len(manager.active_connections)} clients")
            return len(manager.active_connections) > 0

        except Exception as e:
            logger.error(f"Error triggering video playback: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_server_status(self):
        """Check server status using internal manager"""
        try:
            media_state = "null"
            if manager.active_connections:
                first_connection = manager.active_connections[0]
                media_state = manager.media_states.get(first_connection, "null")
            logger.info(f"Server status check: {len(manager.active_connections)} connections, state: {media_state}")
            return True, media_state
        except Exception as e:
            logger.error(f"Error checking server status: {e}")
            return False, "unknown"

    async def pause_media(self):
        """Pause current playing media using internal manager"""
        try:
            await manager.broadcast_command("pause")
            return True, "success"
        except Exception as e:
            logger.error(f"Error pausing media: {e}")
            return False, "error"

    async def stop_media(self):
        """Stop current playing media using internal manager"""
        try:
            await manager.broadcast_command("stop")
            return True, "success"
        except Exception as e:
            logger.error(f"Error stopping media: {e}")
            return False, "error"

    def get_active_connections(self):
        """Get number of active web clients"""
        count = len(manager.active_connections)
        logger.info(f"Active connections count: {count}")
        return count


# Create the bridge instance
FastAPIMediaBridge = FastAPIMediaBridge_Singleton()


# Web Interface Routes
@app.get("/", response_class=HTMLResponse)
async def get():
    return FileResponse("index.html", media_type="text/html")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                await manager.handle_message(websocket, message)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received from websocket: {data}")
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected normally")
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# Media Playback Routes
@app.post("/play")
async def play_audio(audio_data: AudioData):
    """Trigger audio playback on all connected clients"""
    broadcast_data = {
        "audio_url": audio_data.audio_url,
        "volume": audio_data.volume,
        "timestamp": time.time(),
        "action": "play",
        "loop": audio_data.loop,
        "metadata": audio_data.audio_url.replace("/media/Musique", "/metadata")
    }

    await manager.broadcast_audio(broadcast_data)
    logger.info(f"Broadcasting audio: {audio_data.audio_url}")

    return {
        "status": "success",
        "message": "Audio playback triggered",
        "clients_notified": len(manager.active_connections),
        "data": broadcast_data
    }


@app.post("/vplay")
async def play_video(video_data: VideoData):
    """Trigger video playback on all connected clients"""
    broadcast_data = {
        "video_url": video_data.video_url,
        "volume": video_data.volume,
        "timestamp": time.time(),
        "action": "play"
    }

    await manager.broadcast_video(broadcast_data)
    logger.info(f"Broadcasting video: {video_data.video_url}")

    return {
        "status": "success",
        "message": "Video playback triggered",
        "clients_notified": len(manager.active_connections),
        "data": broadcast_data
    }


# Control Routes
@app.post("/pause")
async def pause_media():
    """Pause current media playback"""
    await manager.broadcast_command("pause")
    return {
        "status": "success",
        "message": "Pause command sent",
        "clients_notified": len(manager.active_connections)
    }


@app.post("/stop")
async def stop_media():
    """Stop current media playback"""
    await manager.broadcast_command("stop")
    return {
        "status": "success",
        "message": "Stop command sent",
        "clients_notified": len(manager.active_connections)
    }


# Status Routes
@app.get("/health")
async def health_check():
    media_state = "null"
    if manager.active_connections:
        first_connection = manager.active_connections[0]
        media_state = manager.media_states.get(first_connection, "null")

    return {
        "media_status": media_state,
        "status": "success",
        "active_connections": len(manager.active_connections),
        "timestamp": time.time()
    }


@app.get("/connections")
async def get_connections():
    return {
        "active_connections": len(manager.active_connections),
        "timestamp": time.time()
    }


# File Serving Routes
@app.get("/media/{file_path:path}")
async def serve_file(request: Request, file_path: str):
    """Serve media files from subdirectories"""
    decoded_path = unquote(file_path)
    full_path = MEDIA_FOLDER / decoded_path

    logger.info(f"Serving file: {full_path}")

    if full_path.exists() and full_path.is_file():
        if '/Musique/' in str(full_path):
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
        raise HTTPException(status_code=404, detail=f"Media file not found: {full_path}")


@app.get("/metadata/{file_path:path}")
async def get_metadata(request: Request, file_path: str):
    """Extract and return metadata from audio files"""
    logger.info(f"Getting metadata for: {file_path}")
    try:
        full_path = sounds_path / file_path
        logger.info(f"Full path: {full_path}")

        if not full_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        # Load the audio file with mutagen
        from mutagen import File
        from mutagen.id3 import APIC
        import mimetypes

        audio_file = File(str(full_path))
        if audio_file is None:
            raise HTTPException(status_code=400, detail="Unsupported file format")

        # Helper function to get tag value
        def get_tag_value(tags, *keys):
            """Get the first non-None value from multiple possible tag keys"""
            if not tags:
                return None
            for key in keys:
                value = tags.get(key)
                if value:
                    return value[0] if isinstance(value, list) and value else value

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
            "track_total": None,
            "disc": get_tag_value(tags, "TPOS", "DISCNUMBER", "discnumber", "disc", "disk"),
            "disc_total": None,
            "duration": info.length if info else None,
            "bitrate": getattr(info, 'bitrate', None),
            "samplerate": getattr(info, 'sample_rate', None),
            "channels": getattr(info, 'channels', None),
            "filesize": full_path.stat().st_size,
            "albumart": None
        }

        # Parse track and disc numbers, year, and extract album art
        # (keeping all the existing parsing logic...)

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
                metadata["disc_total"] = int(disc_parts[1]) if len(disc_parts) > 1 and disc_parts[1].isdigit() else None
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
            logger.warning(f"Error extracting album art: {e}")

        return JSONResponse(content={"metadata": metadata})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting metadata: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error extracting metadata: {str(e)}")


# Discord Webhook Routes
@app.get("/webhook")
async def discord_webhook_test():
    if FastAPIMediaBridge.bot:
        try:
            channel = await FastAPIMediaBridge.bot.fetch_channel(1116010901586321448)
            if channel:
                await channel.send(f"👍 Webhook connected")
                logger.info(f"Test message sent to {channel}")
                return {"status": "success", "message": "Test message sent"}
            else:
                logger.error(f"Could not find channel")
                return {"status": "error", "message": "Could not find channel"}
        except Exception as e:
            logger.error(f"Error sending webhook test: {e}")
            return {"status": "error", "message": str(e)}
    else:
        logger.error(f"Bot not connected")
        return {"status": "error", "message": "Bot not connected"}


@app.post("/webhook")
async def discord_webhook(request: Request):
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
        try:
            channel = FastAPIMediaBridge.bot.get_channel(1116010901586321448)
            if channel:
                await channel.send(final_content)
            else:
                logger.error(f"Could not find channel")
        except Exception as e:
            logger.error(f"Error sending webhook message: {e}")
    else:
        logger.error(f"Bot not connected")

    logger.info(f"Webhook content: {final_content}")

    return {"status": "success"}


if __name__ == "__main__":
    import uvicorn

    # Get port from environment variable
    port = int(os.getenv('PORT_FASTAPI', 8000))

    logger.info(f"Starting Bozobot Media Server on port {port}")
    logger.info(f"Media folder: {MEDIA_FOLDER}")

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")