"""
Sarvam.ai Integration Client

Provides translation, speech-to-text, and text-to-speech capabilities
for Indic languages using Sarvam.ai API.
"""

import requests
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass


@dataclass
class SarvamLanguage:
    """Represents a supported language."""
    code: str  # e.g., "hi-IN", "ta-IN"
    name: str  # e.g., "Hindi", "Tamil"
    has_stt: bool = True
    has_tts: bool = True
    has_translation: bool = True


class SarvamClient:
    """
    Client for Sarvam.ai API.
    
    Features:
    - Translation (English ↔ Indic languages)
    - Speech-to-Text (Indic languages)
    - Text-to-Speech (Indic languages)
    - Language Detection
    """
    
    # Supported languages
    LANGUAGES = {
        "hi-IN": SarvamLanguage("hi-IN", "Hindi"),
        "ta-IN": SarvamLanguage("ta-IN", "Tamil"),
        "te-IN": SarvamLanguage("te-IN", "Telugu"),
        "bn-IN": SarvamLanguage("bn-IN", "Bengali"),
        "ml-IN": SarvamLanguage("ml-IN", "Malayalam"),
        "kn-IN": SarvamLanguage("kn-IN", "Kannada"),
        "gu-IN": SarvamLanguage("gu-IN", "Gujarati"),
        "mr-IN": SarvamLanguage("mr-IN", "Marathi"),
        "pa-IN": SarvamLanguage("pa-IN", "Punjabi"),
    }
    
    def __init__(self, api_key: str, base_url: str = "https://api.sarvam.ai"):
        """
        Initialize Sarvam client.
        
        Args:
            api_key: Sarvam.ai API key
            base_url: API base URL
        """
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "api-subscription-key": api_key,  # Sarvam uses this header
            "Content-Type": "application/json"
        })
    
    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        preserve_tech_terms: bool = True
    ) -> str:
        """
        Translate text between languages using Sarvam.ai
        
        Args:
            text: Text to translate
            source_lang: Source language code (e.g., "hi-IN", "en-IN")
            target_lang: Target language code (e.g., "en-IN", "ta-IN")
            preserve_tech_terms: Keep technical terms (Docker, MySQL) untranslated
            
        Returns:
            Translated text
        """
        try:
            endpoint = f"{self.base_url}/translate"
            
            # Map to Sarvam's language codes if needed
            source_lang_code = source_lang if source_lang != "en" else "en-IN"
            target_lang_code = target_lang if target_lang != "en" else "en-IN"
            
            payload = {
                "input": text,
                "source_language_code": source_lang_code,
                "target_language_code": target_lang_code,
                "speaker_gender": "Male",
                "mode": "formal",
                "model": "mayura:v1",
                "enable_preprocessing": True
            }
            
            response = self.session.post(endpoint, json=payload)
            response.raise_for_status()
            
            data = response.json()
            return data.get("translated_text", text)
            
        except Exception as e:
            logging.error(f"Sarvam translation failed: {e}")
            return text  # Return original text on failure
    
    def speech_to_text(
        self,
        audio_data: bytes,
        language: str = "hi-IN",
        format: str = "wav"
    ) -> str:
        """
        Convert speech to text using Sarvam.ai SDK (async job-based)
        
        Note: Sarvam.ai STT uses an async job-based API which requires:
        1. Creating a job
        2. Uploading audio file
        3. Starting the job
        4. Polling for completion
        5. Downloading results
        
        For real-time voice commands, this may take 30-60 seconds.
        Consider using a simpler STT service for interactive voice.
        
        Args:
            audio_data: Audio file bytes
            language: Language code (e.g., "en-IN", "hi-IN")
            format: Audio format (wav, mp3, etc.)
            
        Returns:
            Transcribed text (empty string if fails or takes too long)
        """
        try:
            # Try using sarvamai SDK if available
            try:
                from sarvamai import SarvamAI
                import tempfile
                import os
                import time
                
                # Create temp file for audio
                with tempfile.NamedTemporaryFile(mode='wb', suffix=f'.{format}', delete=False) as tmp:
                    tmp.write(audio_data)
                    tmp_path = tmp.name
                
                try:
                    # Initialize client
                    client = SarvamAI(api_subscription_key=self.api_key)
                    
                    # Create STT job
                    job = client.speech_to_text_job.create_job(
                        language_code=language,
                        model="saaras:v3",
                        with_timestamps=False,
                        with_diarization=False
                    )
                    
                    # Upload audio file
                    job.upload_files(file_paths=[tmp_path])
                    
                    # Start job
                    job.start()
                    
                    # Wait for completion (max 60 seconds)
                    timeout = 60
                    start_time = time.time()
                    
                    while time.time() - start_time < timeout:
                        status = job.get_status()
                        if status == "COMPLETED":
                            break
                        elif status == "FAILED":
                            logging.error("STT job failed")
                            return ""
                        time.sleep(2)
                    
                    if job.is_failed():
                        return ""
                    
                    # Download and parse results
                    output_dir = tempfile.mkdtemp()
                    job.download_outputs(output_dir=output_dir)
                    
                    # Read transcript from output
                    import json
                    for file in os.listdir(output_dir):
                        if file.endswith('.json'):
                            with open(os.path.join(output_dir, file)) as f:
                                data = json.load(f)
                                transcript = data.get('transcript', '')
                                return transcript
                    
                    return ""
                    
                finally:
                    # Cleanup temp file
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                    
            except ImportError:
                logging.warning("sarvamai SDK not installed. Install with: pip install sarvamai")
                logging.info("STT requires async job processing. Skipping...")
                return ""
            
        except Exception as e:
            logging.error(f"Sarvam STT failed: {e}")
            return ""
    
    def text_to_speech(
        self,
        text: str,
        language: str = "hi-IN",
        speaker: str = "shubh",  # Male voice (meera, shubh, etc.)
        speed: float = 1.1
    ) -> bytes:
        """
        Convert text to speech using Sarvam.ai streaming API
        
        Args:
            text: Text to synthesize
            language: Language code (hi-IN, ta-IN, etc.)
            speaker: Voice name (shubh for male, meera for female)
            speed: Speech pace (0.5-2.0)
            
        Returns:
            Audio bytes (MP3 format)
        """
        try:
            # Use streaming endpoint for TTS
            endpoint = f"{self.base_url}/text-to-speech/stream"
            
            payload = {
                "text": text,
                "target_language_code": language,
                "speaker": speaker,
                "model": "bulbul:v3",
                "pace": speed,
                "speech_sample_rate": 22050,
                "temperature": 0.6,
                "output_audio_codec": "mp3",
                "enable_preprocessing": True
            }
            
            # Stream the response
            response = self.session.post(endpoint, json=payload, stream=True)
            response.raise_for_status()
            
            # Collect audio chunks
            audio_data = b""
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    audio_data += chunk
            
            return audio_data
            
        except Exception as e:
            logging.error(f"Sarvam TTS failed: {e}")
            return b""
    
    def detect_language(self, text: str) -> Optional[str]:
        """
        Detect language of input text.
        
        Uses simple heuristic-based detection since Sarvam.ai
        may not have a dedicated language detection endpoint.
        
        Args:
            text: Text to analyze
            
        Returns:
            Language code (e.g., "hi-IN") or None
        """
        # Use heuristic detection based on Unicode ranges
        text_sample = text[:200]  # Check first 200 chars
        
        # Check for Indic scripts
        if any('\u0900' <= c <= '\u097F' for c in text_sample):
            return "hi-IN"  # Devanagari (Hindi)
        elif any('\u0B80' <= c <= '\u0BFF' for c in text_sample):
            return "ta-IN"  # Tamil
        elif any('\u0C00' <= c <= '\u0C7F' for c in text_sample):
            return "te-IN"  # Telugu
        elif any('\u0980' <= c <= '\u09FF' for c in text_sample):
            return "bn-IN"  # Bengali
        elif any('\u0D00' <= c <= '\u0D7F' for c in text_sample):
            return "ml-IN"  # Malayalam
        elif any('\u0C80' <= c <= '\u0CFF' for c in text_sample):
            return "kn-IN"  # Kannada
        elif any('\u0A80' <= c <= '\u0AFF' for c in text_sample):
            return "gu-IN"  # Gujarati
        elif any('\u0A00' <= c <= '\u0A7F' for c in text_sample):
            return "pa-IN"  # Punjabi
        
        # Default to English for Latin script
        return "en"
    
    def is_code_mixed(self, text: str) -> bool:
        """
        Check if text is code-mixed (e.g., Hinglish).
        
        Simple heuristic: Contains both Indic script and Latin script.
        """
        has_indic = any('\u0900' <= c <= '\u097F' or  # Devanagari (Hindi)
                       '\u0B80' <= c <= '\u0BFF' or    # Tamil
                       '\u0C00' <= c <= '\u0C7F' or    # Telugu
                       '\u0980' <= c <= '\u09FF' or    # Bengali
                       '\u0D00' <= c <= '\u0D7F' or    # Malayalam
                       '\u0C80' <= c <= '\u0CFF'       # Kannada
                       for c in text)
        
        has_latin = any('a' <= c.lower() <= 'z' for c in text)
        
        return has_indic and has_latin
    
    @classmethod
    def get_supported_languages(cls) -> List[str]:
        """Get list of supported language codes."""
        return list(cls.LANGUAGES.keys())
    
    @classmethod
    def get_language_name(cls, code: str) -> str:
        """Get language name from code."""
        lang = cls.LANGUAGES.get(code)
        return lang.name if lang else code


# Mock client for testing without API key
class MockSarvamClient(SarvamClient):
    """Mock Sarvam client for testing."""
    
    def __init__(self):
        self.api_key = "mock"
        self.base_url = "mock"
    
    def translate(self, text: str, source_lang: str, target_lang: str, preserve_tech_terms: bool = True) -> str:
        return f"[Translated from {source_lang} to {target_lang}]: {text}"
    
    def speech_to_text(self, audio_data: bytes, language: str = "hi-IN", format: str = "wav") -> str:
        return "[Mock STT]: Speech recognized"
    
    def text_to_speech(self, text: str, language: str = "hi-IN", speaker: str = "meera", speed: float = 1.0) -> bytes:
        return b"[Mock TTS audio]"
    
    def detect_language(self, text: str) -> Optional[str]:
        # Simple detection: Hindi if contains Devanagari
        if any('\u0900' <= c <= '\u097F' for c in text):
            return "hi-IN"
        return "en"
