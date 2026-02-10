"""
Multilingual Translation Module

Provides translation, voice commands, and language detection
using Sarvam.ai API for Indic languages.
"""

import os
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from ..ai.sarvam_client import SarvamClient, MockSarvamClient


@dataclass
class TranslationResult:
    """Result of a translation operation."""
    original_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    detected_lang: Optional[str] = None
    is_code_mixed: bool = False


class TranslatorModule:
    """
    High-level translation module for Nexus.
    
    Features:
    - Auto-detect language
    - Translate commands and responses
    - Voice input/output support
    - Code-mixed text handling (Hinglish)
    """
    
    def __init__(self, api_key: Optional[str] = None, use_mock: bool = False):
        """
        Initialize translator module.
        
        Args:
            api_key: Sarvam.ai API key
            use_mock: Use mock client for testing
        """
        if use_mock or not api_key:
            self.client = MockSarvamClient()
            self.enabled = False
            logging.info("Translator: Using mock mode (no API key)")
        else:
            self.client = SarvamClient(api_key=api_key)
            self.enabled = True
            logging.info("Translator: Sarvam.ai client initialized")
        
        # User preferences
        self.user_language = "en"  # Default to English
        self.auto_translate = False  # Auto-translate responses
        
    def set_user_language(self, lang_code: str):
        """Set user's preferred language."""
        if lang_code in ["en"] or lang_code in self.client.LANGUAGES:
            self.user_language = lang_code
            logging.info(f"User language set to: {lang_code}")
        else:
            logging.warning(f"Unsupported language: {lang_code}")
    
    def enable_auto_translate(self, enabled: bool = True):
        """Enable/disable automatic translation."""
        self.auto_translate = enabled
        
    def detect_and_translate(
        self, 
        text: str, 
        target_lang: str = "en"
    ) -> TranslationResult:
        """
        Detect language and translate if needed.
        
        Args:
            text: Input text
            target_lang: Target language (default: English)
            
        Returns:
            TranslationResult with translation details
        """
        # Detect language
        detected_lang = self.client.detect_language(text)
        is_code_mixed = self.client.is_code_mixed(text)
        
        # If already in target language, return as-is
        if detected_lang == target_lang and not is_code_mixed:
            return TranslationResult(
                original_text=text,
                translated_text=text,
                source_lang=detected_lang or target_lang,
                target_lang=target_lang,
                detected_lang=detected_lang,
                is_code_mixed=is_code_mixed
            )
        
        # Translate
        source_lang = detected_lang or "hi-IN"  # Default to Hindi if detection fails
        translated = self.client.translate(
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
            preserve_tech_terms=True
        )
        
        return TranslationResult(
            original_text=text,
            translated_text=translated,
            source_lang=source_lang,
            target_lang=target_lang,
            detected_lang=detected_lang,
            is_code_mixed=is_code_mixed
        )
    
    def translate_to_english(self, text: str) -> str:
        """
        Translate text to English (for command processing).
        
        Args:
            text: Input text in any language
            
        Returns:
            English translation
        """
        result = self.detect_and_translate(text, target_lang="en")
        return result.translated_text
    
    def translate_to_user_language(self, text: str) -> str:
        """
        Translate text to user's preferred language.
        
        Args:
            text: Input text (usually English)
            
        Returns:
            Translated text in user's language
        """
        if self.user_language == "en":
            return text
        
        result = self.detect_and_translate(text, target_lang=self.user_language)
        return result.translated_text
    
    def speech_to_text(
        self, 
        audio_path: str, 
        language: str = "hi-IN"
    ) -> str:
        """
        Convert audio file to text.
        
        Args:
            audio_path: Path to audio file
            language: Language code for recognition
            
        Returns:
            Transcribed text
        """
        try:
            with open(audio_path, "rb") as f:
                audio_data = f.read()
            
            # Determine format from extension
            format = audio_path.split(".")[-1].lower()
            if format not in ["wav", "mp3", "ogg", "flac"]:
                format = "wav"
            
            text = self.client.speech_to_text(
                audio_data=audio_data,
                language=language,
                format=format
            )
            
            return text
        except Exception as e:
            logging.error(f"Speech-to-text failed: {e}")
            return ""
    
    def text_to_speech(
        self,
        text: str,
        output_path: str,
        language: str = "hi-IN",
        speaker: str = "shubh"
    ) -> bool:
        """
        Convert text to speech audio file.
        
        Args:
            text: Text to synthesize
            output_path: Path to save audio file (will be saved as .mp3)
            language: Language code
            speaker: Voice name (shubh for male, meera for female)
            
        Returns:
            True if successful
        """
        try:
            audio_data = self.client.text_to_speech(
                text=text,
                language=language,
                speaker=speaker
            )
            
            if audio_data:
                # Ensure output path has .mp3 extension
                if not output_path.endswith('.mp3'):
                    output_path = output_path.rsplit('.', 1)[0] + '.mp3'
                
                with open(output_path, "wb") as f:
                    f.write(audio_data)
                return True
            return False
        except Exception as e:
            logging.error(f"Text-to-speech failed: {e}")
            return False
    
    def get_supported_languages(self) -> Dict[str, str]:
        """
        Get dictionary of supported languages.
        
        Returns:
            Dict mapping language codes to names
        """
        langs = {"en": "English"}
        for code, lang_obj in self.client.LANGUAGES.items():
            langs[code] = lang_obj.name
        return langs
    
    def format_translation_info(self, result: TranslationResult) -> str:
        """
        Format translation result as readable string.
        
        Args:
            result: TranslationResult object
            
        Returns:
            Formatted string
        """
        source_name = self.client.get_language_name(result.source_lang)
        target_name = self.client.get_language_name(result.target_lang)
        
        info = f"[{source_name} → {target_name}]"
        
        if result.is_code_mixed:
            info += " (Code-mixed)"
        
        if result.detected_lang:
            info += f" [Detected: {self.client.get_language_name(result.detected_lang)}]"
        
        return info


class VoiceCommandHandler:
    """
    Handles voice command input and output.
    """
    
    def __init__(self, translator: TranslatorModule):
        self.translator = translator
        self.recording = False
        
    def record_audio(self, duration: int = 5, output_path: str = "/tmp/voice_input.wav") -> str:
        """
        Record audio from microphone.
        
        Args:
            duration: Recording duration in seconds
            output_path: Path to save recording
            
        Returns:
            Path to recorded file
        """
        try:
            import pyaudio
            import wave
            
            CHUNK = 1024
            FORMAT = pyaudio.paInt16
            CHANNELS = 1
            RATE = 16000
            
            p = pyaudio.PyAudio()
            
            stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )
            
            print(f"🎤 Recording for {duration} seconds...")
            frames = []
            
            for _ in range(0, int(RATE / CHUNK * duration)):
                data = stream.read(CHUNK)
                frames.append(data)
            
            print("✓ Recording complete")
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            # Save as WAV
            wf = wave.open(output_path, 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))
            wf.close()
            
            return output_path
            
        except ImportError:
            logging.error("PyAudio not installed. Run: pip install pyaudio")
            return ""
        except Exception as e:
            logging.error(f"Recording failed: {e}")
            return ""
    
    def process_voice_command(self, audio_path: str, language: str = "hi-IN") -> str:
        """
        Process voice command: STT → Translation → English command.
        
        Args:
            audio_path: Path to audio file
            language: Expected language of speech
            
        Returns:
            English command text
        """
        # Speech to text
        indic_text = self.translator.speech_to_text(audio_path, language)
        
        if not indic_text:
            return ""
        
        # Translate to English for command processing
        english_command = self.translator.translate_to_english(indic_text)
        
        return english_command
    
    def speak_response(self, text: str, language: str = "hi-IN", output_path: str = "/tmp/voice_output.wav") -> bool:
        """
        Convert text response to speech and play it.
        
        Args:
            text: Text to speak
            language: Language for speech
            output_path: Temporary file path
            
        Returns:
            True if successful
        """
        # Generate speech
        success = self.translator.text_to_speech(text, output_path, language)
        
        if not success:
            return False
        
        # Play audio (platform-specific)
        try:
            import platform
            import subprocess
            
            system = platform.system()
            if system == "Linux":
                subprocess.run(["aplay", output_path], check=True, stderr=subprocess.DEVNULL)
            elif system == "Darwin":  # macOS
                subprocess.run(["afplay", output_path], check=True)
            elif system == "Windows":
                import winsound
                winsound.PlaySound(output_path, winsound.SND_FILENAME)
            
            return True
        except Exception as e:
            logging.error(f"Audio playback failed: {e}")
            return False
