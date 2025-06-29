# src/codecat/cli_app.py

"""
Defines the command-line interface (CLI) for Codecat using Typer.

This module is the main entry point for all CLI commands and options.
It orchestrates the application's functionality, from configuration
and file scanning to processing and output generation.
"""

import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import nullcontext
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from typing_extensions import Annotated

# --- Application Imports ---
from codecat import __version__
from codecat.config import DEFAULT_CONFIG, load_config
from codecat.constants import DEFAULT_CONFIG_FILENAME
from codecat.file_processor import ProcessedFileData, process_file
from codecat.file_scanner import scan_project
from codecat.markdown_generator import generate_markdown

# --- Initialize Rich Console for output ---
console = Console(stderr=True, highlight=False)

# Initialize the Typer CLI app with custom help and settings.
app = typer.Typer(
    name="codecat",
    help="🐾 [bold]Codecat CLI[/bold] — A powerful tool to aggregate source code and text into a single Markdown file.",
    add_completion=False,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)


def version_callback(value: bool):
    """Prints the application version and exits."""
    if value:
        console.print(f"Codecat CLI Version: [bold cyan]{__version__}[/bold cyan]")
        raise typer.Exit()


# --- Reusable CLI Option Definitions ---
ProjectPath = Annotated[
    Path,
    typer.Argument(
        help="The path to the project directory you want to scan.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
    ),
]

ConfigPath = Annotated[
    Optional[Path],
    typer.Option(
        "--config",
        "-c",
        help=f"Path to a custom config file. If not provided, looks for [cyan]{DEFAULT_CONFIG_FILENAME}[/cyan] in the project path.",
        resolve_path=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
]

IncludePatterns = Annotated[
    Optional[List[str]],
    typer.Option(
        "--include",
        "-i",
        help='Glob pattern for files to include. [bold]Use multiple times for multiple patterns[/bold] (e.g., -i "*.py" -i "*.js").',
    ),
]

ExcludePatterns = Annotated[
    Optional[List[str]],
    typer.Option(
        "--exclude",
        "-e",
        help='Glob pattern to exclude files or directories. [bold]Use multiple times for multiple patterns[/bold] (e.g., -e "dist/*").',
    ),
]


# --- Helper Functions for Rich UI and Output ---
def _create_summary_table(
    processed_results: List[ProcessedFileData], project_path: Path
) -> Table:
    """Creates a Rich Table summarizing the results of a scan."""
    summary = Table(
        title=f"Codecat Scan Summary for '{project_path.name}'",
        show_header=True,
        header_style="bold magenta",
    )
    summary.add_column("Status", style="dim", width=12)
    summary.add_column("Count", justify="right")
    summary.add_column("Details")

    status_counts = Counter(p.status for p in processed_results)

    text_files = status_counts.get("text_content", 0)
    binary_files = status_counts.get("binary_file", 0)
    read_errors = status_counts.get("read_error", 0)
    access_errors = status_counts.get("skipped_access_error", 0)

    summary.add_row(
        "[green]Text Files[/green]", str(text_files), "Successfully read and included."
    )
    summary.add_row(
        "[yellow]Binary Files[/yellow]", str(binary_files), "Detected and skipped."
    )
    summary.add_row(
        "[red]Read Errors[/red]", str(read_errors), "Could not decode content."
    )
    summary.add_row(
        "[red]Access Errors[/red]",
        str(access_errors),
        "OS permission or access issues.",
    )
    summary.add_section()
    summary.add_row(
        "[bold]Total Files Processed[/bold]", str(len(processed_results)), ""
    )

    return summary


def _log_initial_info(
    project_path: Path, is_verbose: bool, effective_config: dict
) -> None:
    """Prints the initial startup panel and configuration if verbose is enabled."""
    console.print(
        Panel(
            f"🐾 [bold]Codecat v{__version__}[/bold] | Processing: [cyan]'{project_path.resolve()}'[/cyan]",
            border_style="blue",
        )
    )
    if is_verbose:
        console.print("[bold]Effective Configuration:[/bold]")
        console.print(JSON(json.dumps(effective_config)))


def _scan_project_files(
    project_path: Path, effective_config: dict, show_ui: bool
) -> List[Path]:
    """Scans the project for files to process, handling UI and errors."""
    scan_status_text = f"Scanning files in [cyan]'{project_path.name}'[/cyan]..."
    scan_context = (
        console.status(scan_status_text, spinner="dots") if show_ui else nullcontext()
    )

    with scan_context as status:
        try:
            # Pass the status object to the scanner so it can update the UI
            files_to_scan = scan_project(
                project_path, effective_config, project_path, status_indicator=status
            )
        except Exception as e:
            console.print(f"\n[bold red]Error during file scanning:[/bold red] {e}")
            if effective_config.get("stop_on_error", False):
                console.print("[bold red]Exiting due to stop_on_error.[/bold red]")
            raise typer.Exit(code=1)

    if not files_to_scan:
        console.print(
            "\n[yellow]No files found to aggregate based on the current configuration.[/yellow]"
        )
        raise typer.Exit()

    if effective_config.get("verbose", False):
        console.print(f"Scan complete. Found {len(files_to_scan)} files to process.")
    elif show_ui:
        console.print(f"✔ Scan complete. Found {len(files_to_scan)} files to process.")
    return files_to_scan


def _process_files_parallel(
    files_to_scan: List[Path],
    project_path: Path,
    effective_config: dict,
    show_ui: bool,
    max_workers: Optional[int],
) -> List[ProcessedFileData]:
    """
    Processes a list of files in parallel, showing progress and handling errors.
    Returns a sorted list of ProcessedFileData objects.
    """
    processed_results: List[ProcessedFileData] = []
    is_verbose = effective_config.get("verbose", False)
    stop_on_error = effective_config.get("stop_on_error", False)

    progress_ui = Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    )
    progress_context = progress_ui if show_ui else nullcontext()

    with progress_context as progress:
        if show_ui:
            assert progress is not None
            task = progress.add_task(
                "[green]Processing files...", total=len(files_to_scan)
            )
        else:
            task = None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(process_file, f, project_path, effective_config): f
                for f in files_to_scan
            }
            for future in as_completed(future_to_file):
                try:
                    result = future.result()
                    processed_results.append(result)
                    if is_verbose:
                        if result.status == "text_content":
                            console.print(f"[green]✔ Read:[/] {result.relative_path}")
                        elif result.status == "binary_file":
                            console.print(
                                f"[yellow]! Skipped (binary):[/] {result.relative_path}"
                            )
                        else:
                            console.print(
                                f"[red]✖ Error ({result.status}):[/] {result.relative_path}"
                            )
                except Exception as e:
                    file_path = future_to_file[future]
                    console.print(
                        f"[bold red]Critical error processing {file_path}: {e}[/bold red]"
                    )
                    if stop_on_error:
                        raise typer.Exit(code=1)

                if show_ui and task:
                    assert progress is not None
                    progress.update(task, advance=1)

    return sorted(processed_results, key=lambda p: p.relative_path)


def _write_markdown_output(
    markdown_content: str, output_file_path: Path, silent: bool, num_files: int
) -> None:
    """Writes the final markdown content to a file and prints a success message."""
    try:
        output_file_path.write_text(markdown_content, encoding="utf-8")
        if not silent:
            console.print(
                f"\n[bold green]✔ Success![/bold green] Aggregated {num_files} files into:"
            )
            console.print(f"[cyan]{output_file_path.resolve()}[/cyan]")
    except IOError as e:
        console.print(
            f"\n[bold red]Error writing to output file '{output_file_path.resolve()}': {e}[/bold red]"
        )
        raise typer.Exit(code=1)


def _orchestrate_scan(
    project_path: Path,
    effective_config: dict,
    show_ui: bool,
    max_workers: Optional[int],
) -> List[ProcessedFileData]:
    """
    Handles the shared logic of scanning and processing files for any command.

    This function consolidates the workflow of scanning a project directory
    based on the effective configuration and then processing the discovered
    files in parallel.

    Returns:
        A list of ProcessedFileData objects containing the results.
    """
    files_to_scan = _scan_project_files(project_path, effective_config, show_ui)
    processed_results = _process_files_parallel(
        files_to_scan, project_path, effective_config, show_ui, max_workers
    )
    return processed_results


# --- Main Application Commands ---


@app.command()
def run(
    project_path: ProjectPath = Path("."),
    config_file_path_override: ConfigPath = None,
    output_file_name: Annotated[
        Optional[str],
        typer.Option(
            "--output-file",
            "-o",
            help="Name for the output Markdown file. [bold]Overrides config setting.[/bold]",
        ),
    ] = None,
    include_patterns_override: IncludePatterns = None,
    exclude_patterns_override: ExcludePatterns = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable detailed, step-by-step log output. Disables the progress bar.",
        ),
    ] = False,
    silent: Annotated[
        bool,
        typer.Option(
            "--silent",
            "-s",
            help="Suppress all informational output. Only critical errors will be shown.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Scan and process files, but [bold]do not write the output file.[/bold] Useful for previews.",
        ),
    ] = False,
    no_header: Annotated[
        bool,
        typer.Option(
            "--no-header",
            help="Do not include the main Codecat title header in the output file.",
        ),
    ] = False,
    max_workers: Annotated[
        Optional[int],
        typer.Option(
            "--max-workers",
            help="Set the max number of parallel threads. Defaults to an optimal number based on your system's cores.",
        ),
    ] = None,
):
    """
    Scans a project, aggregates files, and compiles them into a single Markdown file.
    """
    is_verbose = verbose and not silent
    is_testing = "pytest" in sys.modules
    show_ui = not is_verbose and not silent and not is_testing

    effective_config, _, _ = load_config(
        project_path,
        config_file_path_override,
        output_file_name,
        include_patterns_override,
        exclude_patterns_override,
        no_header,
    )
    effective_config["verbose"] = is_verbose

    if not silent:
        _log_initial_info(project_path, is_verbose, effective_config)

    processed_results = _orchestrate_scan(
        project_path, effective_config, show_ui, max_workers
    )

    if not silent:
        console.print(_create_summary_table(processed_results, project_path))

    if dry_run:
        console.print(
            "\n[bold yellow]--dry-run enabled. No output file will be written.[/bold yellow]"
        )
        raise typer.Exit()

    markdown_content = generate_markdown(
        processed_results, project_path, effective_config
    )
    output_file_path = project_path / effective_config["output_file"]

    _write_markdown_output(
        markdown_content, output_file_path, silent, len(processed_results)
    )


@app.command()
def stats(
    project_path: ProjectPath = Path("."),
    config_file_path_override: ConfigPath = None,
    include_patterns_override: IncludePatterns = None,
    exclude_patterns_override: ExcludePatterns = None,
    max_workers: Annotated[
        Optional[int],
        typer.Option(
            "--max-workers",
            help="Set the max number of parallel threads. Defaults to an optimal number based on your system's cores.",
        ),
    ] = None,
):
    """
    Scans the project and displays file count and line count statistics.
    """
    is_testing = "pytest" in sys.modules
    show_ui = not is_testing

    effective_config, _, _ = load_config(
        project_path,
        config_file_path_override,
        None,
        include_patterns_override,
        exclude_patterns_override,
        no_header_override=True,
    )
    effective_config["verbose"] = False

    console.print(
        Panel(
            f"📊 [bold]Codecat Stats[/bold] | Analyzing: [cyan]'{project_path.resolve()}'[/cyan]",
            border_style="blue",
        )
    )

    processed_results = _orchestrate_scan(
        project_path, effective_config, show_ui, max_workers
    )

    lang_map = effective_config.get("language_hints", {})
    lang_counts = Counter()
    line_counts = Counter()
    total_lines = 0
    text_files = [
        p
        for p in processed_results
        if p.status == "text_content" and p.content is not None
    ]

    for file_data in text_files:
        assert file_data.content is not None
        lang = lang_map.get(file_data.path.suffix.lower(), "text")
        lang_counts[lang] += 1
        num_lines = len(file_data.content.splitlines())
        line_counts[lang] += num_lines
        total_lines += num_lines

    stats_table = Table(
        title="File Type Statistics", show_header=True, header_style="bold cyan"
    )
    stats_table.add_column("Language/Type", style="green")
    stats_table.add_column("Files", justify="right", style="magenta")
    stats_table.add_column("Lines of Code", justify="right", style="yellow")
    stats_table.add_column("% of Lines", justify="right", style="dim")

    for lang, count in lang_counts.most_common():
        lines = line_counts[lang]
        percentage = (lines / total_lines * 100) if total_lines > 0 else 0
        stats_table.add_row(lang, str(count), f"{lines:,}", f"{percentage:.1f}%")

    stats_table.add_section()
    stats_table.add_row(
        "[bold]Total[/bold]",
        f"[bold]{sum(lang_counts.values()):,}[/bold]",
        f"[bold]{total_lines:,}[/bold]",
        "[bold]100.0%[/bold]",
    )

    console.print(stats_table)
    console.print(_create_summary_table(processed_results, project_path))


@app.command(name="generate-config")
def generate_config(
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            "-o",
            help="Directory to generate the config file in. Defaults to the current directory.",
            resolve_path=True,
            file_okay=False,
            dir_okay=True,
            writable=True,
        ),
    ] = Path("."),
    config_filename: Annotated[
        str,
        typer.Option(
            "--config-file-name",
            help=f"Name of the config file. Defaults to [cyan]{DEFAULT_CONFIG_FILENAME}[/cyan].",
        ),
    ] = DEFAULT_CONFIG_FILENAME,
):
    """
    Generates a well-documented, default configuration file.
    """
    if not output_dir.exists():
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            console.print(f"Created directory: [cyan]{output_dir.resolve()}[/cyan]")
        except Exception as e:
            console.print(
                f"[bold red]Error:[/bold red] Could not create directory '{output_dir.resolve()}'. {e}"
            )
            raise typer.Exit(code=1)
    elif not output_dir.is_dir():
        console.print(
            f"[bold red]Error:[/bold red] Output path '{output_dir.resolve()}' exists but is not a directory."
        )
        raise typer.Exit(code=1)

    config_file_path = output_dir / config_filename

    if config_file_path.exists():
        console.print(
            f"[yellow]Config file '{config_file_path.resolve()}' already exists.[/yellow]"
        )
        overwrite = typer.confirm("Do you want to overwrite it?", default=False)
        if not overwrite:
            console.print("Config file generation aborted by user.")
            raise typer.Exit(code=1)

    try:
        with open(config_file_path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        console.print(
            f"Successfully generated config file: [green]{config_file_path.resolve()}[/green]"
        )
    except IOError as e:
        console.print(
            f"[bold red]Error writing config file '{config_file_path.resolve()}': {e}[/bold red]"
        )
        raise typer.Exit(code=1)


@app.callback()
def main_callback(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            "-V",
            callback=version_callback,
            is_eager=True,
            help="Show the application version and exit.",
        ),
    ] = None,
):
    """
    🐾 Codecat CLI: A tool to aggregate source code into a single Markdown file.
    """
    pass
