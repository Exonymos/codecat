#!/usr/bin/env python3

# src/codecat/__main__.py

"""
Main entry point for the Codecat CLI application.

This script is invoked by the console script defined in setup configuration,
and also serves as the entry for PyInstaller-built executables.
"""

import os
import sys

# Import the Typer app instance from the CLI module.
from codecat.cli_app import app


def main():
    """
    Starts the Typer CLI app, or shows a helpful message if run incorrectly.

    If the script is launched in a non-interactive terminal without any commands,
    it's assumed to be a double-click. A user-friendly message is shown, and
    the window is paused to prevent it from closing immediately.
    """
    # This check is the most reliable way to detect a double-click on a frozen executable.
    # It runs before Typer, preventing Typer's default error message from appearing.
    if len(sys.argv) == 1 and getattr(sys, "frozen", False) and os.name == "nt":
        from rich.console import Console
        from rich.panel import Panel

        console = Console(stderr=True, highlight=False)
        console.print(
            Panel(
                "[bold red]Error: Missing command.[/bold red]\n\n"
                "Codecat is a command-line tool and must be run from a terminal.\n"
                "Do not double-click the executable.\n\n"
                "Example Usage:\n"
                "  [cyan]codecat --help[/cyan]\n\n"
                "For more information, visit the GitHub README:\n"
                "  [cyan link=https://github.com/your-repo/codecat?tab=readme-ov-file#-codecat]https://github.com/your-repo/codecat[/cyan]\n",
                title="Usage Error",
                border_style="red",
                padding=(1, 2),
            )
        )
        # Use os.system("pause") which is reliable on Windows for this scenario.
        # It waits for any key press.
        os.system("pause")
        sys.exit(1)

    # If it's a valid terminal session or has arguments, run the main Typer app.
    app()


if __name__ == "__main__":
    # Only run main() if this script is executed directly.
    main()
