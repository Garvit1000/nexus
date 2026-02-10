"""
Multilingual UI Components

Provides UI elements for displaying multilingual content
with proper formatting and language indicators.
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from typing import Optional, Dict
from ..modules.translator import TranslationResult


class MultilingualUI:
    """
    UI components for multilingual display in Nexus.
    """
    
    def __init__(self, console: Console):
        self.console = console
        
        # Language display names and styles
        self.lang_styles = {
            "hi-IN": ("🇮🇳 हिंदी", "bright_magenta"),
            "ta-IN": ("🇮🇳 தமிழ்", "bright_cyan"),
            "te-IN": ("🇮🇳 తెలుగు", "bright_blue"),
            "bn-IN": ("🇮🇳 বাংলা", "bright_green"),
            "ml-IN": ("🇮🇳 മലയാളം", "bright_yellow"),
            "kn-IN": ("🇮🇳 ಕನ್ನಡ", "magenta"),
            "gu-IN": ("🇮🇳 ગુજરાતી", "cyan"),
            "mr-IN": ("🇮🇳 मराठी", "blue"),
            "pa-IN": ("🇮🇳 ਪੰਜਾਬੀ", "yellow"),
            "en": ("🇬🇧 English", "bright_white"),
        }
    
    def print_translation(self, result: TranslationResult, show_original: bool = True):
        """
        Display translation result with beautiful formatting.
        
        Args:
            result: TranslationResult object
            show_original: Whether to show original text
        """
        # Get language info
        source_display, source_style = self.lang_styles.get(
            result.source_lang, 
            (result.source_lang, "white")
        )
        target_display, target_style = self.lang_styles.get(
            result.target_lang,
            (result.target_lang, "white")
        )
        
        # Build display content
        content = Text()
        
        if show_original and result.original_text != result.translated_text:
            content.append("Original ", style="dim")
            content.append(source_display, style=source_style)
            content.append(":\n", style="dim")
            content.append(result.original_text, style="italic")
            content.append("\n\n")
            content.append("↓ Translation ↓\n\n", style="dim cyan")
        
        content.append(target_display, style=target_style)
        content.append(":\n", style="dim")
        content.append(result.translated_text, style="bold")
        
        # Add metadata
        if result.is_code_mixed:
            content.append("\n\n", style="dim")
            content.append("⚡ Code-mixed text detected", style="dim yellow italic")
        
        # Display in panel
        panel = Panel(
            content,
            title="[bold cyan]🌐 Translation[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2)
        )
        
        self.console.print(panel)
    
    def print_language_selector(self, languages: Dict[str, str], current: str):
        """
        Display language selection menu.
        
        Args:
            languages: Dict of language codes to names
            current: Current language code
        """
        table = Table(
            title="🌐 Available Languages",
            box=box.ROUNDED,
            border_style="cyan",
            show_header=True,
            header_style="bold cyan"
        )
        
        table.add_column("Code", style="dim", width=8)
        table.add_column("Language", style="bold")
        table.add_column("Status", width=10)
        
        for code, name in sorted(languages.items()):
            # Get display info
            display, style = self.lang_styles.get(code, (name, "white"))
            
            # Status indicator
            if code == current:
                status = Text("✓ Active", style="bold green")
            else:
                status = Text("", style="dim")
            
            table.add_row(code, Text(display, style=style), status)
        
        self.console.print(table)
    
    def print_voice_status(self, status: str, language: Optional[str] = None):
        """
        Display voice command status.
        
        Args:
            status: Status message
            language: Language being used
        """
        # Choose icon based on status
        if "recording" in status.lower():
            icon = "🎤"
            style = "bold red"
        elif "processing" in status.lower():
            icon = "⚙️"
            style = "bold yellow"
        elif "complete" in status.lower() or "success" in status.lower():
            icon = "✓"
            style = "bold green"
        else:
            icon = "🔊"
            style = "bold blue"
        
        # Build message
        text = Text()
        text.append(icon + " ", style=style)
        text.append(status, style=style)
        
        if language:
            lang_display, lang_style = self.lang_styles.get(
                language, 
                (language, "white")
            )
            text.append("\n", style="dim")
            text.append(f"Language: {lang_display}", style=lang_style)
        
        self.console.print(Panel(
            text,
            title="[bold]Voice Command[/bold]",
            border_style=style.replace("bold ", ""),
            box=box.ROUNDED,
            padding=(1, 2)
        ))
    
    def print_multilingual_response(
        self, 
        english_text: str, 
        translated_text: str, 
        target_lang: str,
        show_both: bool = False
    ):
        """
        Display AI response in multiple languages.
        
        Args:
            english_text: Original English response
            translated_text: Translated response
            target_lang: Target language code
            show_both: Show both versions side-by-side
        """
        if show_both and english_text != translated_text:
            # Side-by-side display
            table = Table(
                box=box.ROUNDED,
                border_style="cyan",
                show_header=True,
                header_style="bold cyan",
                expand=True
            )
            
            table.add_column("🇬🇧 English", style="white")
            
            target_display, target_style = self.lang_styles.get(
                target_lang,
                (target_lang, "white")
            )
            table.add_column(target_display, style=target_style)
            
            # Split into lines for better display
            en_lines = english_text.split('\n')
            tr_lines = translated_text.split('\n')
            
            max_lines = max(len(en_lines), len(tr_lines))
            for i in range(max_lines):
                en_line = en_lines[i] if i < len(en_lines) else ""
                tr_line = tr_lines[i] if i < len(tr_lines) else ""
                table.add_row(en_line, tr_line)
            
            self.console.print(table)
        else:
            # Single language display
            target_display, target_style = self.lang_styles.get(
                target_lang,
                (target_lang, "white")
            )
            
            text = Text()
            text.append(target_display, style=target_style)
            text.append(":\n\n", style="dim")
            text.append(translated_text, style="bold white")
            
            self.console.print(Panel(
                text,
                title="[bold cyan]🤖 Nexus Response[/bold cyan]",
                border_style="cyan",
                box=box.ROUNDED,
                padding=(1, 2)
            ))
    
    def print_language_detection(self, detected_lang: str, confidence: Optional[float] = None):
        """
        Display language detection result.
        
        Args:
            detected_lang: Detected language code
            confidence: Detection confidence (0-1)
        """
        lang_display, lang_style = self.lang_styles.get(
            detected_lang,
            (detected_lang, "white")
        )
        
        text = Text()
        text.append("🔍 Detected Language: ", style="dim")
        text.append(lang_display, style=lang_style)
        
        if confidence is not None:
            text.append(f"\nConfidence: {confidence:.1%}", style="dim cyan")
        
        self.console.print(text)
    
    def print_translation_help(self):
        """Display help for translation commands."""
        help_text = """
[bold cyan]Translation Commands:[/bold cyan]

[yellow]/translate <text>[/yellow]
  Auto-detect language and translate to English

[yellow]/translate <text> --to <lang>[/yellow]
  Translate to specific language (e.g., hi-IN, ta-IN)

[yellow]/speak <text> --lang <lang>[/yellow]
  Convert text to speech in specified language

[yellow]/voice --lang <lang>[/yellow]
  Record voice command and process it

[yellow]/lang <code>[/yellow]
  Set your preferred language

[yellow]/langs[/yellow]
  Show all available languages

[bold cyan]Supported Languages:[/bold cyan]
Hindi (hi-IN), Tamil (ta-IN), Telugu (te-IN), Bengali (bn-IN),
Malayalam (ml-IN), Kannada (kn-IN), Gujarati (gu-IN),
Marathi (mr-IN), Punjabi (pa-IN)

[bold cyan]Examples:[/bold cyan]
> /translate मुझे सिस्टम अपडेट करना है
> /speak Hello, I am Nexus --lang hi-IN
> /voice --lang ta-IN
> /lang hi-IN (to set Hindi as default)
        """
        
        self.console.print(Panel(
            help_text.strip(),
            title="[bold]🌐 Multilingual Support[/bold]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2)
        ))
    
    def print_code_mixed_warning(self, text: str):
        """
        Display warning for code-mixed text.
        
        Args:
            text: The code-mixed text
        """
        warning = Text()
        warning.append("⚡ Code-mixed text detected!\n\n", style="bold yellow")
        warning.append("The input appears to mix multiple scripts (e.g., Hinglish).\n", style="dim")
        warning.append("Translation might be less accurate for code-mixed text.", style="dim italic")
        
        self.console.print(Panel(
            warning,
            title="[bold yellow]Note[/bold yellow]",
            border_style="yellow",
            box=box.ROUNDED,
            padding=(1, 2)
        ))
