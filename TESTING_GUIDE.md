# 🧪 Sarvam.ai Testing Guide

## Quick Testing Checklist

### 1️⃣ **Setup (One-time)**

```bash
# Add your Sarvam API key to .env file
echo "SARVAM_API_KEY=your_actual_api_key_here" >> .env

# Install dependencies
pip install -r requirements.txt

# For voice features (optional)
sudo apt-get install portaudio19-dev python3-pyaudio
pip install pyaudio
```

---

## 2️⃣ **Testing Hinglish in TUI** 🗣️

### Launch TUI:
```bash
nexus
```

### Test Hinglish Input:

The system **automatically detects** if you're writing in Hinglish or any Indic language!

**Example 1: Pure Hindi**
```
> मुझे सिस्टम अपडेट करना है
```
✅ **Auto-detects Hindi** → Translates to English → Processes command → Responds

**Example 2: Hinglish (Code-mixed)**
```
> System ko update karo
```
✅ **Detects code-mixed text** → Processes → Executes

**Example 3: Technical Terms in Hindi**
```
> Docker aur MySQL install karo
```
✅ **Preserves "Docker" and "MySQL"** → Executes installation

**How it works:**
- Type anything in the TUI prompt
- System detects language automatically
- Translates to English for processing
- Executes the command
- (Optional) Responds in your language if set

---

## 3️⃣ **Speech-to-Text (STT) - Voice Input** 🎤

### Method 1: TUI Command

```bash
nexus
> /voice --lang hi-IN --duration 5
```

**What happens:**
1. 🎤 Records 5 seconds of audio from your microphone
2. 🔄 Converts speech to text (Hindi)
3. 🌐 Translates to English
4. ✅ Shows you the recognized command
5. ❓ Asks if you want to execute it

### Method 2: CLI Command

```bash
# Record and process Hindi voice command
nexus voice --lang hi-IN --duration 5

# Record Tamil voice command for 10 seconds
nexus voice --lang ta-IN --duration 10
```

### Supported Languages for STT:
- `hi-IN` - Hindi
- `ta-IN` - Tamil
- `te-IN` - Telugu
- `bn-IN` - Bengali
- `ml-IN` - Malayalam
- `kn-IN` - Kannada
- `gu-IN` - Gujarati
- `mr-IN` - Marathi
- `pa-IN` - Punjabi

### Example Voice Test:

1. **Start recording:**
   ```
   > /voice --lang hi-IN --duration 5
   ```

2. **Speak into microphone:**
   > "System ko update karo"

3. **System outputs:**
   ```
   🔍 Detected Language: 🇮🇳 हिंदी
   Translated input: Update the system
   🎤 Recognized Command:
   Update the system
   
   Execute this command? [y/n]
   ```

4. **Type `y` to execute!**

---

## 4️⃣ **Text-to-Speech (TTS) - Voice Output** 🔊

### Method 1: TUI Command

```bash
nexus
> /speak नमस्ते, मैं नेक्सस हूं --lang hi-IN
```

**What happens:**
1. 🔊 Generates Hindi audio
2. 💾 Saves to `/tmp/nexus_speech.wav`
3. 🎵 Automatically plays the audio (if `aplay` available)

### Method 2: CLI Command

```bash
# Generate and play Hindi speech
nexus speak "नमस्ते, मैं आपकी मदद के लिए यहाँ हूं" --lang hi-IN

# Generate Tamil speech to custom file
nexus speak "வணக்கம்" --lang ta-IN --output /tmp/greeting.wav
```

### Quick TTS Tests:

**Hindi:**
```
> /speak आपका दिन शुभ हो --lang hi-IN
```

**Tamil:**
```
> /speak நல்ல பயணம் --lang ta-IN
```

**Telugu:**
```
> /speak శుభోదయం --lang te-IN
```

---

## 5️⃣ **Set Your Preferred Language** 🌍

Once you set a language, **all responses are auto-translated!**

### In TUI:

```bash
nexus
> /lang hi-IN
✓ Language set to: hi-IN
Auto-translation: enabled

# Now chat normally
> What time is it?
```

**Result:** Response will be automatically translated to Hindi!

### All Commands for Language:

```
> /lang hi-IN          # Set to Hindi
> /lang ta-IN          # Set to Tamil
> /lang en             # Back to English
> /langs               # View all languages
```

---

## 6️⃣ **Translation Commands** 🌐

### In TUI:

**Translate to English (auto-detect source):**
```
> /translate मैं खुश हूं
```
Output:
```
🌐 Translation
🇮🇳 हिंदी:
मैं खुश हूं

↓ Translation ↓

🇬🇧 English:
I am happy
```

**Translate to specific language:**
```
> /translate Hello, how are you? --to hi-IN
```

### From CLI:

```bash
# Auto-detect and translate to English
nexus translate "నేను సంతోషంగా ఉన్నాను"

# Translate to specific language
nexus translate "I am learning AI" --to ta-IN
```

---

## 🎯 Complete Testing Flow

### **Full Multilingual Workflow:**

```bash
# 1. Launch Nexus
nexus

# 2. Set your language
> /lang hi-IN

# 3. Chat in Hindi
> सिस्टम की जानकारी दिखाओ

# 4. Use voice command
> /voice --lang hi-IN --duration 5
[Speak: "CPU usage check karo"]

# 5. Get spoken response
> /speak यह आपका परिणाम है --lang hi-IN

# 6. Translate something
> /translate Docker container क्या है? --to en

# 7. View languages
> /langs

# 8. Back to English
> /lang en
```

---

## 🐛 Troubleshooting

### Voice Input Not Working?

**Check microphone:**
```bash
# Test recording
arecord -d 5 test.wav
aplay test.wav
```

**Install PyAudio:**
```bash
sudo apt-get install portaudio19-dev python3-pyaudio
pip install pyaudio
```

### Voice Output (TTS) Not Playing?

**Audio saved but not playing?**
- File is saved to `/tmp/nexus_speech.wav`
- Play manually: `aplay /tmp/nexus_speech.wav`
- Check speakers: `alsamixer`

### Translation Not Working?

**Mock mode active?**
- Check console output when starting: Should say "🌐 Sarvam.ai Translation Activated"
- If says "Mock Mode", your API key is not set
- Verify: `cat .env | grep SARVAM_API_KEY`

### API Key Issues?

```bash
# Check if key is loaded
echo $SARVAM_API_KEY

# Restart after adding key
# Keys are loaded on startup
```

---

## 📊 Expected Outputs

### When Translation is Active:
```
[dim green]🌐 Sarvam.ai Translation Activated[/dim green]
```

### When in Mock Mode (no API key):
```
[dim yellow]🌐 Translation in Mock Mode (Set SARVAM_API_KEY for real translation)[/dim yellow]
```

### Language Detection:
```
🔍 Detected Language: 🇮🇳 हिंदी
Translated input: <English translation>
```

### Voice Status:
```
🎤 Recording...
⚙️ Processing...
✓ Complete!
```

---

## 🎪 Demo Commands

### Quick Copy-Paste Tests:

**Test 1: Hindi Translation**
```
nexus translate "मुझे Python सीखना है" --to en
```

**Test 2: Voice Command (Hindi)**
```
nexus voice --lang hi-IN --duration 5
# Speak: "system update karo"
```

**Test 3: Text-to-Speech (Hindi)**
```
nexus speak "नमस्ते दोस्तों" --lang hi-IN
```

**Test 4: Hinglish in TUI**
```
nexus
> /lang hi-IN
> Docker install karo aur mysql bhi
```

**Test 5: Code-mixed Detection**
```
nexus
> Main kal Mumbai jaunga aur meeting karunga
```

---

## ✅ Success Indicators

You'll know it's working when you see:

1. **Startup:** `🌐 Sarvam.ai Translation Activated` (green)
2. **Detection:** `🔍 Detected Language: 🇮🇳 हिंदी` when typing Hindi
3. **Translation:** Beautiful panels with native scripts
4. **Voice:** Audio plays automatically after TTS
5. **Recording:** Shows recording progress and transcription

---

## 💡 Pro Tips

1. **Hinglish works best:** Type naturally, mixing English and Hindi
2. **Set language first:** Use `/lang hi-IN` for automatic translation
3. **Voice duration:** 5 seconds is usually enough for a command
4. **Check help:** `/help` shows all commands including translation
5. **Technical terms:** Docker, MySQL, etc. are preserved in translations

---

## 🚀 Ready to Test!

```bash
# Start here:
nexus

# Then try:
> /langs                          # See all languages
> /lang hi-IN                     # Set to Hindi
> Hello, what can you do?         # Chat normally
> /voice --lang hi-IN             # Try voice
> /speak नमस्ते --lang hi-IN       # Try TTS
```

Happy testing! 🎉
