#!/usr/bin/env python3
"""Count tokens in .shotgun/ folder using tiktoken.

Usage:
    python scripts/count_tokens.py [path]

    If no path is provided, defaults to .shotgun/ in current directory.

Can also be imported:
    from scripts.count_tokens import count_tokens_in_directory, count_tokens
"""

import sys
from pathlib import Path
from typing import NamedTuple

import tiktoken


class FileTokenCount(NamedTuple):
    """Token count for a single file."""
    path: Path
    tokens: int
    chars: int


class FolderSummary(NamedTuple):
    """Token count summary for a folder."""
    path: Path
    files: list[FileTokenCount]
    total_tokens: int
    total_chars: int


def get_encoder(model: str = "cl100k_base") -> tiktoken.Encoding:
    """Get tiktoken encoder. cl100k_base is used by Claude/GPT-4."""
    return tiktoken.get_encoding(model)


def count_tokens(text: str, encoder: tiktoken.Encoding | None = None) -> int:
    """Count tokens in a string."""
    if encoder is None:
        encoder = get_encoder()
    return len(encoder.encode(text))


def count_file_tokens(file_path: Path, encoder: tiktoken.Encoding) -> FileTokenCount | None:
    """Count tokens in a single file. Returns None for binary/unreadable files."""
    try:
        content = file_path.read_text(encoding="utf-8")
        tokens = count_tokens(content, encoder)
        return FileTokenCount(path=file_path, tokens=tokens, chars=len(content))
    except (UnicodeDecodeError, PermissionError):
        return None


def count_tokens_in_directory(
    directory: Path,
    extensions: set[str] | None = None,
) -> tuple[list[FolderSummary], int]:
    """
    Count tokens for all files in a directory tree.

    Args:
        directory: Root directory to scan
        extensions: If provided, only count files with these extensions (e.g., {'.md', '.py'})

    Returns:
        Tuple of (list of FolderSummary by subfolder, grand total tokens)
    """
    if extensions is None:
        extensions = {".md", ".py", ".json", ".txt", ".yaml", ".yml", ".j2", ".jinja2"}

    encoder = get_encoder()
    folder_summaries: dict[Path, list[FileTokenCount]] = {}

    for file_path in sorted(directory.rglob("*")):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in extensions:
            continue
        if file_path.name.startswith("."):
            continue

        result = count_file_tokens(file_path, encoder)
        if result is None:
            continue

        # Group by parent folder relative to directory
        rel_path = file_path.relative_to(directory)
        if len(rel_path.parts) > 1:
            folder_key = directory / rel_path.parts[0]
        else:
            folder_key = directory

        if folder_key not in folder_summaries:
            folder_summaries[folder_key] = []
        folder_summaries[folder_key].append(result)

    # Build summaries
    summaries = []
    grand_total = 0

    for folder_path in sorted(folder_summaries.keys()):
        files = folder_summaries[folder_path]
        total_tokens = sum(f.tokens for f in files)
        total_chars = sum(f.chars for f in files)
        grand_total += total_tokens
        summaries.append(FolderSummary(
            path=folder_path,
            files=sorted(files, key=lambda f: f.tokens, reverse=True),
            total_tokens=total_tokens,
            total_chars=total_chars,
        ))

    # Sort by total tokens descending
    summaries.sort(key=lambda s: s.total_tokens, reverse=True)

    return summaries, grand_total


def format_tokens(tokens: int) -> str:
    """Format token count with K suffix for readability."""
    if tokens >= 1000:
        return f"{tokens:,} ({tokens/1000:.1f}K)"
    return f"{tokens:,}"


def print_report(directory: Path, summaries: list[FolderSummary], grand_total: int) -> None:
    """Print a formatted token count report."""
    print(f"\n{'='*60}")
    print(f"Token Count Report: {directory}")
    print(f"{'='*60}\n")

    for summary in summaries:
        folder_name = summary.path.name if summary.path != directory else "(root)"
        print(f"## {folder_name}/")
        print(f"   Total: {format_tokens(summary.total_tokens)} tokens | {summary.total_chars:,} chars")
        print()

        for file_count in summary.files:
            rel_path = file_count.path.relative_to(directory)
            print(f"   {rel_path}")
            print(f"      {format_tokens(file_count.tokens)} tokens | {file_count.chars:,} chars")
        print()

    print(f"{'='*60}")
    print(f"GRAND TOTAL: {format_tokens(grand_total)} tokens")
    print(f"{'='*60}\n")


def main() -> int:
    """CLI entry point."""
    if len(sys.argv) > 1:
        directory = Path(sys.argv[1])
    else:
        directory = Path(".shotgun")

    if not directory.exists():
        print(f"Error: Directory not found: {directory}", file=sys.stderr)
        return 1

    if not directory.is_dir():
        print(f"Error: Not a directory: {directory}", file=sys.stderr)
        return 1

    summaries, grand_total = count_tokens_in_directory(directory)

    if not summaries:
        print(f"No files found in {directory}")
        return 0

    print_report(directory, summaries, grand_total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
