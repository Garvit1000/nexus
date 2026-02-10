# Sarvam.ai Integration Guide

## Overview

Nexus now includes comprehensive multilingual support powered by **Sarvam.ai**, providing:

- 🌐 **Translation** between English and 9 Indic languages
- 🎤 **Speech-to-Text** (Voice Commands)
- 🔊 **Text-to-Speech** (Voice Responses)
- 🔍 **Language Detection** (Auto-detect user's language)
- 🎨 **Multilingual UI** (Beautiful language display)

## Supported Languages

| Language | Code | Features |
|----------|------|----------|
| Hindi | hi-IN | ✅ Translation, STT, TTS |
| Tamil | ta-IN | ✅ Translation, STT, TTS |
| Telugu | te-IN | ✅ Translation, STT, TTS |
| Bengali | bn-IN | ✅ Translation, STT, TTS |
| Malayalam | ml-IN | ✅ Translation, STT, TTS |
| Kannada | kn-IN | ✅ Translation, STT, TTS |
| Gujarati | gu-IN | ✅ Translation, STT, TTS |
| Marathi | mr-IN | ✅ Translation, STT, TTS |
| Punjabi | pa-IN | ✅ Translation, STT, TTS |
| English | en | ✅ Default |

## Setup

### 1. Get Sarvam.ai API Key

1. Visit [https://sarvam.ai](https://sarvam.ai)
2. Sign up for an account
3. Generate your API key from the dashboard

### 2. Configure Environment

Add your API key to `.env`:

```bash
SARVAM_API_KEY=your_sarvam_api_key_here
```

### 3. Install Audio Dependencies (Optional for Voice)

For voice command support, install PyAudio:

```bash
# Ubuntu/Debian
sudo apt-get install portaudio19-dev python3-pyaudio

# macOS
brew install portaudio
pip install pyaudio

# Then install Python dependencies
pip install -r requirements.txt
```

## Usage Examples

### Command Line Interface

#### 1. Translation

```bash
# Translate from Hindi to English (auto-detect)
nexus translate "नमस्ते, मैं कैसे मदद कर सकता हूं?"

# Translate to specific language
nexus translate "Hello, how are you?" --to hi-IN

# Translate technical content (preserves terms like Docker, MySQL)
nexus translate "Install Docker and MySQL" --to ta-IN
```

#### 2. Text-to-Speech

```bash
# Generate Hindi speech
nexus speak "नमस्ते, मैं नेक्सस हूं" --lang hi-IN

# Generate Tamil speech
nexus speak "வணக்கம், நான் நெக்ஸஸ்" --lang ta-IN

# Custom output path
nexus speak "Hello" --lang hi-IN --output /tmp/greeting.wav
```

#### 3. Voice Commands

```bash
# Record 5 seconds of Hindi voice input
nexus voice --lang hi-IN --duration 5

# Record Tamil voice command
nexus voice --lang ta-IN --duration 10
```

#### 4. Set Preferred Language

```bash
# Set default language to Hindi
nexus lang hi-IN

# Set to Tamil
nexus lang ta-IN

# Back to English
nexus lang en
```

#### 5. View Supported Languages

```bash
nexus langs
```

### Interactive TUI Mode

Launch the TUI:

```bash
nexus
```

#### Translation Commands

```
> /translate मुझे सिस्टम अपडेट करना है
[Detects Hindi, translates to English]

> /translate Hello --to hi-IN
[Translates to Hindi]
```

#### Voice Commands

```
> /voice --lang hi-IN --duration 5
[Records 5 seconds, transcribes, and executes command]

> /speak नमस्ते --lang hi-IN
[Generates and plays Hindi speech]
```

#### Language Settings

```
> /lang hi-IN
[Sets Hindi as default, enables auto-translation]

> /langs
[Shows all supported languages with status]

> /help
[Shows all commands including translation]
```

### Automatic Translation Mode

When you set a non-English language, Nexus automatically:

1. **Detects** your input language
2. **Translates** to English for processing
3. **Translates responses** back to your language

Example:

```bash
# Set Hindi as preferred language
nexus lang hi-IN

# Now chat in Hindi
nexus
> अभी क्या समय है?
[Auto-detects Hindi, processes, responds in Hindi]
```

## Architecture

### Module Structure

```
src/jarvis/
├── ai/
│   └── sarvam_client.py          # Core Sarvam.ai API client
├── modules/
│   └── translator.py             # High-level translation module
└── ui/
    └── multilingual_ui.py        # Multilingual UI components
```

### Key Components

#### 1. SarvamClient ([`sarvam_client.py`](src/jarvis/ai/sarvam_client.py:24))

Low-level API client for Sarvam.ai:

```python
from jarvis.ai.sarvam_client import SarvamClient

client = SarvamClient(api_key="your_key")

# Translate
text = client.translate("Hello", "en", "hi-IN")

# Speech-to-Text
transcript = client.speech_to_text(audio_bytes, "hi-IN")

# Text-to-Speech
audio = client.text_to_speech("नमस्ते", "hi-IN")

# Detect Language
lang = client.detect_language("नमस्ते")
```

#### 2. TranslatorModule ([`translator.py`](src/jarvis/modules/translator.py:24))

High-level translation orchestration:

```python
from jarvis.modules.translator import TranslatorModule

translator = TranslatorModule(api_key="your_key")

# Auto-detect and translate
result = translator.detect_and_translate("नमस्ते", target_lang="en")

# Voice commands
text = translator.speech_to_text("audio.wav", "hi-IN")
translator.text_to_speech("Hello", "output.wav", "hi-IN")
```

#### 3. MultilingualUI ([`multilingual_ui.py`](src/jarvis/ui/multilingual_ui.py:14))

Beautiful UI for multilingual display:

```python
from jarvis.ui.multilingual_ui import MultilingualUI

ui = MultilingualUI(console)

# Display translation result
ui.print_translation(result, show_original=True)

# Show language selector
ui.print_language_selector(languages, current="hi-IN")

# Display voice status
ui.print_voice_status("Recording...", "hi-IN")
```

## Features

### 1. Language Detection

Automatically detects:
- **Script-based detection** (Devanagari, Tamil, etc.)
- **Code-mixed text** (e.g., Hinglish: "Main kal aaunga")
- **Latin script** (English)

### 2. Technical Term Preservation

When translating commands, technical terms are preserved:

```
Input:  "Docker container को install करो"
Output: "Install Docker container"
         (Docker preserved as-is)
```

### 3. Context-Aware Translation

Integrates with Nexus memory system to provide context-aware translations.

### 4. Fallback Modes

- **Mock Mode**: Works without API key (for testing)
- **Graceful Degradation**: Falls back to English if translation fails
- **Error Recovery**: Continues operation even if voice features unavailable

## Integration Points

### 1. Main Application ([`main.py`](src/jarvis/main.py:152))

```python
# Translator initialization
translator = TranslatorModule(api_key=sarvam_key)
multilingual_ui = MultilingualUI(console)
voice_handler = VoiceCommandHandler(translator)
```

### 2. Console App ([`console_app.py`](src/jarvis/ui/console_app.py:18))

```python
# Automatic input translation
if translator.enabled:
    detected_lang = translator.client.detect_language(text)
    text = translator.translate_to_english(text)

# Automatic response translation
if translator.auto_translate:
    translated = translator.translate_to_user_language(response)
    multilingual_ui.print_multilingual_response(english, translated)
```

### 3. Decision Engine ([`decision_engine.py`](src/jarvis/ai/decision_engine.py:14))

Multilingual input is translated to English before intent analysis, ensuring consistent command processing.

## Configuration Options

### User Preferences

```python
# Set preferred language
translator.set_user_language("hi-IN")

# Enable auto-translation
translator.enable_auto_translate(True)

# Get supported languages
langs = translator.get_supported_languages()
```

### Voice Settings

```python
# Record with custom duration
voice_handler.record_audio(duration=10)

# Custom voice for TTS
translator.text_to_speech(text, "out.wav", speaker="meera")
```

## Advanced Usage

### Custom Translation Pipeline

```python
# Detect language first
result = translator.detect_and_translate(
    text="आपका नाम क्या है?",
    target_lang="en"
)

print(f"Original: {result.original_text}")
print(f"Translated: {result.translated_text}")
print(f"Source: {result.source_lang}")
print(f"Detected: {result.detected_lang}")
print(f"Code-mixed: {result.is_code_mixed}")
```

### Voice Command Processing

```python
# Full voice command pipeline
audio_path = voice_handler.record_audio(duration=5)
command = voice_handler.process_voice_command(audio_path, "hi-IN")

# Command is now in English and ready for execution
execute_command(command)
```

### Bilingual Display

```python
# Show response in both languages
multilingual_ui.print_multilingual_response(
    english_text="System updated successfully",
    translated_text="सिस्टम सफलतापूर्वक अपडेट किया गया",
    target_lang="hi-IN",
    show_both=True  # Side-by-side display
)
```

## Troubleshooting

### API Key Issues

```bash
# Check if key is set
echo $SARVAM_API_KEY

# Verify in app
nexus langs  # Should show "Translation Activated"
```

### Voice Not Working

```bash
# Install audio dependencies
sudo apt-get install portaudio19-dev
pip install pyaudio

# Test microphone
arecord -d 5 test.wav
aplay test.wav
```

### Translation Errors

- **Fallback**: System continues in English if translation fails
- **Logs**: Check console for error messages
- **Mock Mode**: Use for testing without API key

## Performance

- **Translation**: ~200-500ms per request
- **STT**: ~1-2s for 5s audio
- **TTS**: ~500ms-1s for typical text
- **Language Detection**: ~50-100ms

## Best Practices

1. **Set Language Early**: Use `/lang <code>` at start of session
2. **Use Voice for Natural Input**: `/voice` for hands-free operation
3. **Check Supported Languages**: Not all features available for all languages
4. **Preserve Technical Terms**: Enabled by default in translations
5. **Mock Mode for Testing**: Develop without API key using mock client

## Examples in Action

### Example 1: System Update (Hindi)

```bash
nexus
> /lang hi-IN
> सिस्टम को अपडेट करो
[Detects Hindi → Translates to "Update system" → Executes → Responds in Hindi]
```

### Example 2: Voice Command (Tamil)

```bash
nexus voice --lang ta-IN
[Records voice: "கணினியை புதுப்பிக்கவும்"]
[Transcribes → Translates → Executes system update]
```

### Example 3: Mixed Language Chat

```bash
nexus
> Install docker और mysql
[Detects code-mixed Hinglish]
[Preserves "docker" and "mysql"]
[Executes: apt install docker mysql]
```

## API Reference

See detailed API documentation in:
- [`sarvam_client.py`](src/jarvis/ai/sarvam_client.py) - Core client
- [`translator.py`](src/jarvis/modules/translator.py) - Translation module
- [`multilingual_ui.py`](src/jarvis/ui/multilingual_ui.py) - UI components

## Contributing

To add support for new languages:

1. Update [`LANGUAGES`](src/jarvis/ai/sarvam_client.py:36) dict in `SarvamClient`
2. Add language display in [`lang_styles`](src/jarvis/ui/multilingual_ui.py:19)
3. Test with `/translate` and `/voice` commands

## License

This integration uses Sarvam.ai API. See their terms of service at https://sarvam.ai
