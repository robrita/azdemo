import os
import json
import base64
import logging
import asyncio
import audioop
from typing import Dict
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response
from openai import AsyncAzureOpenAI
import websockets
# Audio format constants
TWILIO_SAMPLE_RATE = 8000
GPT_REALTIME_SAMPLE_RATE = 24000

# Initialize FastAPI app
app = FastAPI()

# Store active sessions
active_sessions: Dict[str, 'TwilioGPTRealtimeBridge'] = {}

# Your server's domain (loaded from environment or default)
YOUR_SERVER_URL = os.environ.get("YOUR_SERVER_URL", "https://93954ea244ab.ngrok-free.app")

class TwilioGPTRealtimeBridge:
    """Bridges Twilio WebSocket with Azure GPT Real-time WebSocket"""
    
    def __init__(self, call_sid: str, twilio_websocket: WebSocket):
        self.call_sid = call_sid
        self.twilio_websocket = twilio_websocket
        self.gpt_connection = None
        self.stream_sid = None
        self.stop_event = asyncio.Event()
        self.gpt_receive_task = None
        # Add response tracking
        self.response_in_progress = False
        self.audio_buffer_size = 0  # Track audio buffer size
        
        # Audio format configuration - Change this to switch formats
        self.use_direct_mulaw = True  # Set to False to use PCM16 conversion
        
        # Load Azure OpenAI configuration (will be refreshed on each connection)
        # self.api_version = "2024-10-01-preview"
        self.deployment_name = "gpt-realtime-mini"

        # # SSL Configuration (for WebSocket)
        # self.ssl_context = ssl.create_default_context()
        # self.ssl_context.check_hostname = False
        # self.ssl_context.verify_mode = ssl.CERT_NONE
        
        # Session configuration
        self.session_config = {
            "modalities": ["text", "audio"],
            "instructions": "You are a helpful AI assistant. Keep responses concise and natural for voice conversation.",
            "voice": "alloy",
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
                
        
    def refresh_config(self):
        """Refresh configuration from environment variables"""
        load_dotenv("./.env", override=True)
        self.azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        self.api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        base_url = self.azure_endpoint.replace("https://", "wss://")
        self.websocket_url = f"{base_url}/openai/v1/realtime?model={self.deployment_name}&api-key={self.api_key}"
     
        
    async def initialize_gpt_connection(self):
        """Initialize connection to Azure GPT Real-time"""
        try:
            # Refresh config to get latest values
            self.refresh_config()
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "OpenAI-Beta": "realtime=v1"
            }
            connect_url = self.websocket_url
            
            logging.info(f"Connecting to WebSocket: {connect_url}")            
            # Connect to the WebSocket
            self.ws = await websockets.connect(
                connect_url,
                extra_headers=headers,
                ssl=self.ssl_context
            )
            
            # # Connect to the WebSocket
            # self.ws = await websockets.connect(
            #     connect_url,
            #     extra_headers=headers,
            #     ssl=self.ssl_context
            # )
            
            logging.info("Successfully connected to OpenAI Realtime API")
            
            # Configure session
            await self.send_event({
                "type": "session.update",
                "session": self.session_config
            })

            logging.info(f"GPT Real-time session created for call {self.call_sid}")
            
        except Exception as e:
            logging.error(f"Error initializing GPT connection: {e}")
            raise
    
    async def send_event(self, event):
        """Send an event to the OpenAI WebSocket"""
        if self.ws:
            await self.ws.send(json.dumps(event))
            logging.debug(f"Sent event: {event['type']}")
    
    def convert_mulaw_to_pcm(self, mulaw_data: bytes) -> bytes:
        """Convert mulaw 8000Hz to PCM 16-bit 24000Hz for GPT Real-time"""
        # Decode mulaw to PCM
        pcm_data = audioop.ulaw2lin(mulaw_data, 2)
        # Resample from 8000Hz to 24000Hz
        pcm_resampled = audioop.ratecv(pcm_data, 2, 1, TWILIO_SAMPLE_RATE, GPT_REALTIME_SAMPLE_RATE, None)[0]
        return pcm_resampled
    
    def convert_pcm_to_mulaw(self, pcm_data: bytes) -> bytes:
        """Convert PCM 16-bit 24000Hz from GPT Real-time to mulaw 8000Hz"""
        # Resample from 24000Hz to 8000Hz
        pcm_resampled = audioop.ratecv(pcm_data, 2, 1, GPT_REALTIME_SAMPLE_RATE, TWILIO_SAMPLE_RATE, None)[0]
        # Encode to mulaw
        mulaw_data = audioop.lin2ulaw(pcm_resampled, 2)
        return mulaw_data
    
    async def handle_twilio_audio(self, audio_payload: str):
        """Handle incoming audio from Twilio and send to GPT Real-time"""
        try:
            if self.use_direct_mulaw:
                # Direct μ-law mode - send Twilio's base64 μ-law directly
                audio_base64 = audio_payload
                logging.debug("Using direct μ-law audio")
            else:
                # Conversion mode - convert μ-law to PCM16
                mulaw_audio = base64.b64decode(audio_payload)
                pcm_audio = self.convert_mulaw_to_pcm(mulaw_audio)
                audio_base64 = base64.b64encode(pcm_audio).decode("utf-8")
                logging.debug("Converting μ-law to PCM16")
            
            # Track audio buffer size (approximate)
            # Twilio sends 20ms chunks, so each chunk adds ~20ms
            self.audio_buffer_size += 20  # milliseconds
            
            # Send to GPT Real-time
            # Send to GPT Real-time using direct WebSocket
            await self.send_event({
                "type": "input_audio_buffer.append",
                "audio": audio_base64
            })
            
            logging.debug(f"Added audio chunk, buffer size now ~{self.audio_buffer_size}ms")
            
        except Exception as e:
            logging.error(f"Error handling Twilio audio: {e}")
    
    async def commit_audio_buffer(self):
        """Commit the audio buffer to trigger a response"""
        try:
            # Check if we have enough audio (at least 100ms)
            if self.audio_buffer_size < 100:
                logging.warning(f"Audio buffer too small ({self.audio_buffer_size}ms), skipping commit")
                return
            
            # Check if response is already in progress
            if self.response_in_progress:
                logging.warning("Response already in progress, skipping new response creation")
                return
            
            # Mark response as in progress
            self.response_in_progress = True
            
            logging.info(f"Committing audio buffer with ~{self.audio_buffer_size}ms of audio")
            await self.gpt_connection.input_audio_buffer.commit()
            await self.gpt_connection.response.create()
            
            # Reset audio buffer size
            self.audio_buffer_size = 0
            
        except Exception as e:
            logging.error(f"Error committing audio buffer: {e}")
            self.response_in_progress = False  # Reset on error
    
    async def process_gpt_events(self):
        """Process events from GPT Real-time in async loop"""
        try:
            async for event in self.gpt_connection:
                if self.stop_event.is_set():
                    break
                    
                event_type = event.type
                
                if event_type == "session.created":
                    logging.info(f"GPT Real-time session created for call {self.call_sid}")
                
                elif event_type == "conversation.item.input_audio_transcription.completed":
                    transcript = getattr(event, 'transcript', '')
                    logging.info(f"User said: {transcript}")
                
                # elif event_type == "response.audio_transcript.delta":
                #     text = getattr(event, 'text', '')
                #     logging.info(f"Assistant text: {text}")
                
                elif event_type == "response.audio_transcript.done":
                    transcript = getattr(event, 'transcript', '')
                    logging.info(f"Assistant said: {transcript}")
                
                elif event_type == "response.audio.delta":
                    # Handle audio response from GPT Real-time
                    audio_delta = getattr(event, 'delta', '')
                    if audio_delta:
                        if self.use_direct_mulaw:
                            # Direct μ-law mode - audio_delta is base64-encoded μ-law data
                            # Don't decode it, pass the base64 string directly
                            logging.info(f"Sending μ-law audio delta (base64 length: {len(audio_delta)}) to Twilio")
                            await self.send_audio_to_twilio(audio_delta)
                        else:
                            # PCM16 mode - audio_delta is base64-encoded PCM16 data
                            pcm_data = base64.b64decode(audio_delta)
                            logging.info(f"Sending {len(pcm_data)} bytes of PCM16 audio to Twilio")
                            await self.send_audio_to_twilio(pcm_data)
                
                elif event_type == "input_audio_buffer.speech_started":
                    # Clear any pending audio when user starts speaking
                    await self.send_clear_to_twilio()
                
                elif event_type == "input_audio_buffer.speech_stopped":
                    # Commit audio buffer and generate response when user stops speaking
                    await self.commit_audio_buffer()
                
                elif event_type == "error":
                    error_details = getattr(event, 'error', {})
                    error_code = getattr(error_details, 'code', 'unknown')
                    logging.error(f"GPT Real-time error: {error_details}")
                                        # Handle specific error types
                    if error_code == "input_audio_buffer_commit_empty":
                        logging.warning("Attempted to commit empty audio buffer")
                        self.audio_buffer_size = 0  # Reset buffer size
                    elif error_code == "conversation_already_has_active_response":
                        logging.warning("Attempted to create response while one is active")
                        # Don't reset response_in_progress here as it's still valid
                    else:
                        logging.error(f"GPT Real-time error: {error_details}")
                        
                    # Reset response flag for certain errors
                    if error_code in ["input_audio_buffer_commit_empty"]:
                        self.response_in_progress = False
                    
        except Exception as e:
            logging.error(f"Error in GPT Real-time event processing: {e}")
    
    async def send_audio_to_twilio(self, audio_data: bytes):
        """Send audio data from GPT Real-time to Twilio"""
        try:
            if self.use_direct_mulaw:
                # Direct μ-law mode - audio_data is already base64-encoded μ-law
                if isinstance(audio_data, str):
                    # It's already a base64 string, use it directly
                    audio_base64 = audio_data
                else:
                    # It's bytes, encode to base64
                    audio_base64 = base64.b64encode(audio_data).decode("utf-8")
                logging.debug("Using direct μ-law audio output")
            else:
                # Conversion mode - convert PCM16 to μ-law
                if isinstance(audio_data, str):
                    # It's base64, decode first
                    audio_data = base64.b64decode(audio_data)
                # Conversion mode - convert PCM16 to μ-law
                mulaw_data = self.convert_pcm_to_mulaw(audio_data)
                audio_base64 = base64.b64encode(mulaw_data).decode("utf-8")
                logging.debug("Converting PCM16 to μ-law")
            
            # Send to Twilio using their streaming protocol
            media_message = {
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {
                    "payload": audio_base64
                }
            }
            await self.twilio_websocket.send_text(json.dumps(media_message))
            
        except Exception as e:
            logging.error(f"Error sending audio to Twilio: {e}")
    
    async def send_clear_to_twilio(self):
        """Send clear message to Twilio to stop current audio playback"""
        try:
            clear_message = {
                "event": "clear",
                "streamSid": self.stream_sid
            }
            await self.twilio_websocket.send_text(json.dumps(clear_message))
        except Exception as e:
            logging.error(f"Error sending clear to Twilio: {e}")
    
    async def start_gpt_processing(self):
        """Start processing GPT Real-time events"""
        self.gpt_receive_task = asyncio.create_task(self.process_gpt_events())
    
    async def stop(self):
        """Stop the bridge and clean up"""
        self.stop_event.set()
        
        # Cancel GPT processing task
        if self.gpt_receive_task:
            self.gpt_receive_task.cancel()
            try:
                await self.gpt_receive_task
            except asyncio.CancelledError:
                pass
        
        # Close WebSocket connection
        if self.ws:
            try:
                await self.ws.close()
                logging.info("WebSocket connection closed")
            except Exception as e:
                logging.error(f"Error closing WebSocket: {e}")

@app.get("/health")
async def health_check():
    """Health check endpoint that shows current configuration"""
    load_environment_config()  # Refresh env vars
    return {
        "status": "healthy",
        "server_url": YOUR_SERVER_URL,
        "websocket_url": f"wss://{YOUR_SERVER_URL.replace('https://', '').replace('http://', '')}/ws",
        "azure_endpoint": os.environ.get("AZURE_OPENAI_ENDPOINT", "Not configured"),
        "has_api_key": bool(os.environ.get("AZURE_OPENAI_API_KEY")),
        "active_sessions": len(active_sessions)
    }

@app.get("/reload-config")
async def reload_config():
    """Manually reload configuration from .env file"""
    try:
        old_url = YOUR_SERVER_URL
        load_environment_config()
        return {
            "status": "success", 
            "message": "Configuration reloaded",
            "old_server_url": old_url,
            "new_server_url": YOUR_SERVER_URL
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/twiml")
async def twiml_endpoint():
    """Provide TwiML instructions to Twilio"""
    # Reload environment to get latest SERVER_URL
    load_environment_config()
    
    # Use Stream instead of ConversationRelay for audio streaming
    server_domain = YOUR_SERVER_URL.replace('https://', '').replace('http://', '')
    xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Connect>
            <Stream url="wss://{server_domain}/ws" />
        </Connect>
    </Response>"""
    logging.info(f"TwiML response sent to Twilio using server: {server_domain}")
    return Response(content=xml_response, media_type="text/xml")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    print("WebSocket connection request received")

    """WebSocket endpoint that Twilio connects to"""
    await websocket.accept()
    
    bridge = None
    call_sid = None
    
    try:
        while True:
            data = await websocket.receive_text()
            # print(data)
            message = json.loads(data)
            event_type = message.get("event")
            
            if event_type == "connected":
                logging.info("Twilio WebSocket connected")
            
            elif event_type == "start":
                # Twilio stream started
                stream_data = message.get("start", {})
                call_sid = stream_data.get("callSid")
                stream_sid = stream_data.get("streamSid")
                
                logging.info(f"Stream started for call: {call_sid}, stream: {stream_sid}")
                
                # Create bridge instance
                bridge = TwilioGPTRealtimeBridge(call_sid, websocket)
                bridge.stream_sid = stream_sid
                
                # Initialize connection to GPT Real-time
                await bridge.initialize_gpt_connection()
                
                # Start processing GPT events
                await bridge.start_gpt_processing()
                
                # Store active session
                active_sessions[call_sid] = bridge
            
            elif event_type == "media":
                # Audio data from Twilio
                if bridge and bridge.gpt_connection:
                    media_data = message.get("media", {})
                    audio_payload = media_data.get("payload", "")
                    if audio_payload:
                        await bridge.handle_twilio_audio(audio_payload)
            
            elif event_type == "stop":
                logging.info(f"Stream stopped for call: {call_sid}")
                break
            
    except WebSocketDisconnect:
        logging.info(f"Twilio WebSocket disconnected for call: {call_sid}")
    except Exception as e:
        logging.error(f"Error in Twilio WebSocket handler: {e}")
    finally:
        # Clean up
        if bridge:
            await bridge.stop()
        if call_sid and call_sid in active_sessions:
            del active_sessions[call_sid]

def load_environment_config():
    """Load and refresh environment configuration"""
    load_dotenv("./.env", override=True)
    global YOUR_SERVER_URL
    YOUR_SERVER_URL = os.environ.get("YOUR_SERVER_URL", "https://93954ea244ab.ngrok-free.app")
    logging.info(f"Server URL updated to: {YOUR_SERVER_URL}")

if __name__ == "__main__":
    # Initial load of environment variables
    load_environment_config()
    
    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s:%(name)s:%(levelname)s:%(message)s',
    )
    
    logging.info("Starting Twilio-GPT Real-time Bridge with auto-reload enabled")
    logging.info("Press Ctrl+C to stop the server")
    
    # Run the FastAPI app with auto-reload enabled
    import uvicorn
    uvicorn.run(
        "twilio_voicelive_bridge:app", 
        host="0.0.0.0", 
        port=8000,
        reload=True,
        reload_dirs=["."],
        reload_includes=["*.py", "*.env"]
    )