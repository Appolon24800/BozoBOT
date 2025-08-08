import fastapi
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import asyncio
import json
import time
from typing import List, Optional, Dict
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Real-time Audio Stream Server",
    description="FastAPI server for streaming real-time audio data to web clients",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic model for audio data
class AudioData(BaseModel):
    audio_url: str = Field(..., description="URL to the audio file to stream")
    volume: Optional[float] = Field(0.5, ge=0, le=1, description="Volume level 0-1")
    loop: Optional[bool] = Field(None, description="Loop mode")

class VideoData(BaseModel):
    video_url: str = Field(..., description="URL to the video file to stream")
    volume: Optional[float] = Field(0.5, ge=0, le=1, description="Volume level 0-1")


# Store active WebSocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.media_states: Dict[WebSocket, str] = {}  # Track media state per connection

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.media_states[websocket] = "null"  # Initialize state
        logger.info(f"Client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            if websocket in self.media_states:
                del self.media_states[websocket]
            logger.info(f"Client disconnected. Total connections: {len(self.active_connections)}")

    async def handle_message(self, websocket: WebSocket, data: dict):
        if data.get("type") == "media_state":
            self.media_states[websocket] = data.get("state", "null")

    async def broadcast_audio(self, data: dict):
        """Broadcast audio data to all connected clients"""
        if not self.active_connections:
            return

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(data))
            except Exception as e:
                logger.warning(f"Failed to send to client: {e}")
                disconnected.append(connection)

        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_video(self, data):
        if not self.active_connections:
            return

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(data))
            except Exception as e:
                logger.warning(f"Failed to send to client: {e}")
                disconnected.append(connection)

        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_command(self, command: str):
        """Broadcast control commands (pause, stop) to all clients"""
        if not self.active_connections:
            return

        command_data = {
            "command": command,
            "timestamp": time.time()
        }

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(command_data))
            except Exception as e:
                logger.warning(f"Failed to send command to client: {e}")
                disconnected.append(connection)

        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


# Serve the main HTML page with audio streaming
@app.get("/", response_class=HTMLResponse)
async def get():
    return FileResponse("index.html", media_type="text/html")


# WebSocket endpoint for real-time communication
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Listen for incoming messages from client
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                await manager.handle_message(websocket, message)
            except json.JSONDecodeError:
                pass  # Ignore invalid JSON
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# API endpoint to trigger audio playback
@app.post("/play")
async def play_audio(audio_data: AudioData):
    """
    Trigger audio playback on all connected clients

    Example usage:
    POST /play
    {
        "audio_url": "http://example.com/song.mp3",
        "volume": 0.7
    }
    """

    # Prepare data for broadcast
    broadcast_data = {
        "audio_url": audio_data.audio_url,
        "volume": audio_data.volume,
        "timestamp": time.time(),
        "action": "play",
        "loop": audio_data.loop,
        "metadata": audio_data.audio_url.replace("/media/Musique", "/metadata")
    }

    # Broadcast to all connected clients
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
    """
    Trigger video playback on all connected clients

    Example usage:
    POST /vplay
    {
        "video_url": "http://example.com/video.mp4",
        "volume": 0.7
    }
    """

    # Prepare data for broadcast
    broadcast_data = {
        "video_url": video_data.video_url,
        "volume": video_data.volume,
        "timestamp": time.time(),
        "action": "play"
    }

    # Broadcast to all connected clients
    await manager.broadcast_video(broadcast_data)

    logger.info(f"Broadcasting video: {video_data.video_url}")

    return {
        "status": "success",
        "message": "Video playback triggered",
        "clients_notified": len(manager.active_connections),
        "data": broadcast_data
    }


# Control endpoints
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


# Health check endpoint
@app.get("/health")
async def health_check():
    # Get the first connection's media state, or "null" if no connections
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


# Get connection info
@app.get("/connections")
async def get_connections():
    return {
        "active_connections": len(manager.active_connections),
        "timestamp": time.time()
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3069, log_level="info")