#!/usr/bin/env python3
"""Benchmark script to compare indexing speed with/without gitignore support.

Usage:
    uv run python scripts/benchmark_indexing.py /path/to/repo
    uv run python scripts/benchmark_indexing.py  # defaults to current repo
"""

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

# Add src to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import real_ladybug as kuzu

from shotgun.codebase.core.gitignore import GitignoreManager
from shotgun.codebase.core.ingestor import IGNORE_PATTERNS, Ingestor, SimpleGraphBuilder
from shotgun.codebase.core.language_config import should_ignore_directory
from shotgun.codebase.core.parser_loader import load_parsers


def count_files(repo_path: Path) -> dict:
    """Count files that would be indexed with/without gitignore."""
    gi = GitignoreManager(repo_path)

    stats = {
        "total_files": 0,
        "hardcoded_dirs_skipped": 0,
        "gitignore_dirs_skipped": 0,
        "gitignore_files_skipped": 0,
        "gitignore_patterns": gi.stats["patterns_loaded"],
    }

    for root, dirs, files in os.walk(repo_path, topdown=True):
        root_path = Path(root)
        new_dirs = []

        for d in dirs:
            if should_ignore_directory(d, IGNORE_PATTERNS):
                stats["hardcoded_dirs_skipped"] += 1
            else:
                try:
                    rel = (
                        root_path.relative_to(repo_path) / d
                        if root_path != repo_path
                        else Path(d)
                    )
                    if gi.is_directory_ignored(rel):
                        stats["gitignore_dirs_skipped"] += 1
                    else:
                        new_dirs.append(d)
                except ValueError:
                    new_dirs.append(d)

        dirs[:] = new_dirs

        for f in files:
            stats["total_files"] += 1
            try:
                rel = (root_path / f).relative_to(repo_path)
                if gi.is_ignored(rel):
                    stats["gitignore_files_skipped"] += 1
            except ValueError:
                pass

    return stats


def run_indexing(repo_path: Path, respect_gitignore: bool) -> tuple[float, dict]:
    """Run full indexing and return timing + stats."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "benchmark.kuzu"
        db = kuzu.Database(str(db_path))
        conn = kuzu.Connection(db)

        try:
            ingestor = Ingestor(conn)
            ingestor.create_schema()
            parsers, queries = load_parsers()

            builder = SimpleGraphBuilder(
                ingestor=ingestor,
                repo_path=repo_path,
                parsers=parsers,
                queries=queries,
                respect_gitignore=respect_gitignore,
            )

            start = time.time()
            asyncio.run(builder.run())
            duration = time.time() - start

            return duration, builder._index_stats.copy()
        finally:
            conn.close()
            db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark indexing with/without gitignore support"
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Path to repository to index (default: current directory)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: only count files, don't do full indexing",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full mode: run actual indexing (slower but more accurate)",
    )

    args = parser.parse_args()
    repo_path = Path(args.repo_path).resolve()

    if not repo_path.exists():
        print(f"Error: {repo_path} does not exist")
        sys.exit(1)

    print(f"Benchmarking: {repo_path}")
    print(f"{'=' * 60}")

    # Quick file count (always run)
    print("\nCounting files...")
    stats = count_files(repo_path)

    print("\nFile Statistics:")
    print(f"  Total files (after hardcoded filter): {stats['total_files']}")
    print(f"  Directories skipped (hardcoded):      {stats['hardcoded_dirs_skipped']}")
    print(f"  Directories skipped (gitignore):      {stats['gitignore_dirs_skipped']}")
    print(f"  Files skipped (gitignore):            {stats['gitignore_files_skipped']}")
    print(f"  Gitignore patterns loaded:            {stats['gitignore_patterns']}")

    potential_savings = (
        stats["gitignore_files_skipped"] + stats["gitignore_dirs_skipped"]
    )
    if potential_savings > 0:
        print(f"\n  Potential savings from gitignore: {potential_savings} items")
    else:
        print("\n  Note: No additional items skipped by gitignore")
        print("        (This is normal for clean git clones without build artifacts)")

    # Full indexing benchmark (optional)
    if args.full:
        print(f"\n{'=' * 60}")
        print("Running full indexing benchmark...")
        print("(This may take a while for large repos)")

        print("\n[1/2] Indexing WITHOUT gitignore...")
        t1, s1 = run_indexing(repo_path, respect_gitignore=False)
        print(f"       Time: {t1:.1f}s, Files processed: {s1['files_processed']}")

        print("\n[2/2] Indexing WITH gitignore...")
        t2, s2 = run_indexing(repo_path, respect_gitignore=True)
        print(f"       Time: {t2:.1f}s, Files processed: {s2['files_processed']}")
        print(f"       Files skipped by gitignore: {s2['files_ignored_gitignore']}")
        print(f"       Dirs skipped by gitignore: {s2['dirs_ignored_gitignore']}")

        print(f"\n{'=' * 60}")
        print("RESULTS:")
        print(f"  Without gitignore: {t1:.1f}s")
        print(f"  With gitignore:    {t2:.1f}s")
        if t2 > 0:
            speedup = t1 / t2
            print(f"  Speedup:           {speedup:.2f}x")
    elif not args.quick:
        print("\nTip: Use --full to run actual indexing benchmark")
        print("     Use --quick to only show file counts (default)")


if __name__ == "__main__":
    main()
