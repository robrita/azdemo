import asyncio
import websockets
import json
import base64
import logging
from utils.model_auth import REALTIME_4O_CONFIGS, REALTIME_4O_MINI_CONFIGS, GA_REALTIME_MINI_CONFIGS
from fastapi import WebSocket
 
# Single connection state
gpt_ws = None
twilio_ws = None
audio_buffer_size = 0
use_direct_mulaw = True
stream_sid = None
CONFIGS = GA_REALTIME_MINI_CONFIGS
MODEL_PROVIDER = "azure"
api_key = CONFIGS[MODEL_PROVIDER]["headers"]['api-key']
 
# Session configuration
session_config = {
    "modalities": ["text", "audio"],
    "instructions": "You are a helpful AI assistant. Keep responses concise and natural for voice conversation.",
    "voice": "sage",
    "input_audio_format": "pcmu",
    "output_audio_format": "pcmu",
    "turn_detection": {
        "type": "server_vad",
        "threshold": 0.5,
        "prefix_padding_ms": 300,
        "silence_duration_ms": 200
    },
    "input_audio_transcription": {
        "model": "whisper-1"
    },
    "temperature": 0.8
}

# Your Azure endpoint
connect_url = "wss://voiceaiagent-swedencent-resource.cognitiveservices.azure.com/openai/v1/realtime?model=gpt-realtime-mini&temperature=0.8"

headers = {
    "api-key": api_key,
    "OpenAI-Beta": "realtime=v1"
}

session_config = {
    "type": "realtime",
    "model": "gpt-realtime-mini",
    "output_modalities": ["audio"],
    "instructions": "You are a helpful AI assistant. Keep responses concise and natural for voice conversation.",
    "audio": {
        "input": {
            "format": {
                "type": "audio/pcmu"
            },
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 200
            },
            "transcription": {
                "model": "whisper-1"
            }
        },
        "output": {
            "format": {
                "type": "audio/pcmu"
            },
            "voice": "sage"
        }
    }
}





async def send_event(event):
    """Send an event to the OpenAI WebSocket"""
    global gpt_ws
    if gpt_ws:
        await gpt_ws.send(json.dumps(event))
        logging.debug(f"Sent event: {event['type']}")
 
 
async def initialize_gpt_connection(api_key):
    """Initialize connection to Azure GPT Real-time"""
    global gpt_ws
   
    try:
        # Your Azure endpoint
        connect_url = "wss://voiceaiagent-swedencent-resource.cognitiveservices.azure.com/openai/v1/realtime?model=gpt-realtime-mini"
       
        headers = {
            "api-key": api_key,
            "OpenAI-Beta": "realtime=v1"
        }
       
        logging.info(f"Connecting to WebSocket: {connect_url}")
       
        # Connect to the WebSocket
        gpt_ws = await websockets.connect(
            connect_url,
            additional_headers=headers
        )
       
        logging.info("Successfully connected to Azure OpenAI Realtime API")
       
        # Configure session
        await send_event({
            "type": "session.update",
            "session": session_config
        })
 
        logging.info("GPT Real-time session created")
       
    except Exception as e:
        logging.error(f"Error initializing GPT connection: {e}")
        raise
 
 
async def handle_twilio_audio(audio_payload: str):
    """Handle incoming audio from Twilio and send to GPT Real-time"""
    global audio_buffer_size, use_direct_mulaw
   
    try:
       
        audio_base64 = audio_payload
        logging.debug("Using direct μ-law audio")
       
        # Track audio buffer size (approximate)
        audio_buffer_size += 20  # milliseconds
       
        # Send to GPT Real-time
        await send_event({
            "type": "input_audio_buffer.append",
            "audio": audio_base64
        })
       
        logging.debug(f"Added audio chunk, buffer size now ~{audio_buffer_size}ms")
       
    except Exception as e:
        logging.error(f"Error handling Twilio audio: {e}")
 
 
async def handle_gpt_messages():
    """Listen for messages from GPT and send audio back to Twilio"""
    global gpt_ws, twilio_ws, stream_sid
   
    try:
        async for message in gpt_ws:
            response = json.loads(message)
            event_type = response.get("type")
           
            logging.debug(f"Received GPT event: {event_type}")
           
            if event_type == "response.output_audio.delta":
                # Send audio back to Twilio
                audio_data = response.get("delta")
                if audio_data and twilio_ws:
                    await twilio_ws.send_json({
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {
                            "payload": audio_data
                        }
                    })
                   
            elif event_type == "response.audio.done":
                logging.info("GPT finished speaking")
               
            elif event_type == "error":
                logging.error(f"GPT error: {response}")
               
    except Exception as e:
        logging.error(f"Error handling GPT messages: {e}")
 
 
async def close_connection():
    """Close the WebSocket connection"""
    global gpt_ws, twilio_ws, audio_buffer_size, stream_sid
   
    if gpt_ws:
        await gpt_ws.close()
        gpt_ws = None
   
    audio_buffer_size = 0
    stream_sid = None
    twilio_ws = None
   
    logging.info("WebSocket connection closed")
 
 
async def handle_media_stream(websocket: WebSocket, identifier_type: str, identifier: str,
                              option_selected: str):
    """Main handler for the media stream WebSocket"""
    global twilio_ws, stream_sid, api_key
   
    # Accept the WebSocket connection
    await websocket.accept()
    twilio_ws = websocket
   
    gpt_task = None
   
    try:
        # Initialize GPT connection
        await initialize_gpt_connection(api_key=api_key)
       
        # Start task to listen for GPT responses
        gpt_task = asyncio.create_task(handle_gpt_messages())
       
        # Handle incoming WebSocket messages from Twilio
        while True:
            data = await websocket.receive_json()
           
            event = data.get("event")
           
            if event == "start":
                stream_sid = data.get("start", {}).get("streamSid")
                logging.info(f"Stream started: {stream_sid}")
               
            elif event == "media":
                # Extract audio payload from Twilio
                audio_payload = data["media"]["payload"]
                await handle_twilio_audio(audio_payload)
           
            elif event == "stop":
                logging.info("Stream stopped")
                break
               
    except Exception as e:
        logging.error(f"Error in media stream: {e}")
    finally:
        # Cancel GPT listener task
        gpt_task.cancel()
        # Clean up connection
        await close_connection()
 