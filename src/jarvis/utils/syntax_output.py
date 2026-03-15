"""
syntax_output.py — Rich syntax-highlighted output rendering for Nexus.

Use `print_command_output()` anywhere a shell / LLM command result needs to
be displayed to the user with colour-coded, language-aware highlighting.
"""

from __future__ import annotations

from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax


# ── Language auto-detection ──────────────────────────────────────────────────


def detect_output_language(text: str) -> str:
    """
    Heuristically identify the language/format of command output so Rich
    Syntax can apply the most useful highlighting theme.

    Priority order:
      1. JSON  — starts with { or [
      2. Python traceback — "Traceback (most recent call last)"
      3. YAML  — starts with --- or has key: value patterns
      4. TOML  — contains [section] headers
      5. Bash  — common shell signals (apt, sudo, $, #, →, Error:, …)
      6. text  — fallback (monospace, no highlighting)
    """
    stripped = text.strip()
    if not stripped:
        return "text"

    # JSON
    if stripped.startswith(("{", "[")):
        return "json"

    # Python traceback
    if "Traceback (most recent call last)" in stripped:
        return "python"

    # YAML
    if stripped.startswith("---") or (
        ":\n" in stripped and not stripped.startswith("#!")
    ):
        return "yaml"

    # TOML — [Section] headers
    if stripped.startswith("[") and "]\n" in stripped:
        return "toml"

    # Bash / shell signals
    shell_hints = [
        "$ ",
        "# ",
        "% ",
        "── ",
        "→ ",
        "-->",
        "apt ",
        "sudo ",
        "systemctl ",
        "docker ",
        "git ",
        "pip ",
        "python",
        "Error:",
        "Warning:",
        "Fatal:",
        "fatal:",
        "panic:",
        "Permission denied",
        "No such file",
        "command not found",
        "FAILED",
        "PASSED",
        "OK\n",
        "0 upgraded",
        "Reading package",
        "Connecting to",
        "Fetching ",
        "Cloning into",
        "make[",
        "cmake",
        "gcc",
        "g++",
    ]
    if any(h in stripped for h in shell_hints):
        return "bash"

    return "text"


# ── Core rendering helper ─────────────────────────────────────────────────────


def make_syntax(
    text: str,
    force_lang: Optional[str] = None,
    theme: str = "monokai",
    line_numbers: bool = False,
) -> Syntax:
    """
    Build a Rich Syntax object for *text*.

    Args:
        text:        The raw string to highlight.
        force_lang:  Override auto-detection (e.g. ``"json"``, ``"bash"``).
        theme:       Pygments theme (default: monokai — works on dark terminals).
        line_numbers: Show line numbers. Auto-enabled for structured formats.
    """
    lang = force_lang or detect_output_language(text)

    # Only enable line numbers for structured/code formats where they help navigation.
    # For plain terminal output (text, bash) line numbers are just visual noise.
    if not line_numbers and lang in ("json", "yaml", "toml", "python"):
        line_numbers = text.count("\n") > 8  # only for genuinely long structured blocks

    return Syntax(
        text,
        lang,
        theme=theme,
        word_wrap=True,
        background_color="default",
        line_numbers=line_numbers,
    )


# ── Public API ────────────────────────────────────────────────────────────────


def print_command_output(
    console: Console,
    output: str,
    *,
    step_id: Optional[int] = None,
    action: Optional[str] = None,
    success: bool = True,
    force_lang: Optional[str] = None,
    theme: str = "monokai",
) -> None:
    """
    Print highlighted command output as a bordered panel.

    Example::
        print_command_output(console, result.stdout, step_id=2, action="TERMINAL", success=True)
    """
    if not output or not output.strip():
        return

    text = output.strip()
    syntax = make_syntax(text, force_lang=force_lang, theme=theme)

    if step_id is not None and action is not None:
        colour = "green" if success else "red"
        label = f"[{colour} dim]step {step_id}[/{colour} dim]  [cyan]{action}[/cyan]"
    elif action:
        label = f"[cyan]{action}[/cyan]"
    else:
        label = "[dim]output[/dim]"

    border_style = "green dim" if success else "red"

    console.print(
        Panel(
            syntax,
            title=label,
            title_align="left",
            border_style=border_style,
            padding=(0, 1),
        )
    )


def print_error_output(
    console: Console,
    error: str,
    *,
    step_id: Optional[int] = None,
    action: Optional[str] = None,
    theme: str = "monokai",
) -> None:
    """Print an error output block with red border and bash highlighting."""
    print_command_output(
        console,
        error,
        step_id=step_id,
        action=action,
        success=False,
        force_lang="bash",
        theme=theme,
    )


def print_inline_command(
    console: Console,
    command: str,
    language: str = "bash",
    theme: str = "monokai",
) -> None:
    """
    Render a single command string inline (no panel border) with syntax
    highlighting. Useful for the 'Generated Command:' display.
    """
    syntax = Syntax(
        command.strip(),
        language,
        theme=theme,
        word_wrap=True,
        background_color="default",
    )
    console.print(syntax)


_EXT_LANG_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".html": "html",
    ".css": "css",
    ".xml": "xml",
    ".sql": "sql",
    ".md": "markdown",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".rb": "ruby",
    ".php": "php",
    ".lua": "lua",
    ".conf": "ini",
    ".ini": "ini",
    ".cfg": "ini",
    ".dockerfile": "dockerfile",
    ".tf": "hcl",
}


def print_syntax(
    console: Console,
    content: str,
    filepath: str,
    theme: str = "monokai",
) -> None:
    """
    Print a file's content with syntax highlighting based on its extension.

    Used by the ``nexus read`` CLI command.
    """
    import os

    ext = os.path.splitext(filepath)[1].lower()
    lang = _EXT_LANG_MAP.get(ext, "text")

    syntax = Syntax(
        content.strip(),
        lang,
        theme=theme,
        word_wrap=True,
        background_color="default",
        line_numbers=content.count("\n") > 8,
    )
    console.print(
        Panel(
            syntax,
            title=f"[dim]{filepath}[/dim]",
            title_align="left",
            border_style="cyan dim",
            padding=(0, 1),
        )
    )
