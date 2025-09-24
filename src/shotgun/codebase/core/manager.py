"""Kuzu graph database manager for code knowledge graphs."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, ClassVar

import anyio
import kuzu
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from shotgun.codebase.models import (
    CodebaseGraph,
    FileChange,
    GraphStatus,
    OperationStats,
)
from shotgun.logging_config import get_logger

logger = get_logger(__name__)


class CodebaseAlreadyIndexedError(Exception):
    """Raised when a codebase is already indexed."""

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        super().__init__(f"Codebase already indexed: {repo_path}")


class CodebaseFileHandler(FileSystemEventHandler):
    """Handles file system events for code graph updates."""

    def __init__(
        self,
        graph_id: str,
        callback: Callable[[str, list[FileChange]], Awaitable[None]] | None,
        loop: asyncio.AbstractEventLoop,
        ignore_patterns: set[str] | None = None,
    ):
        self.graph_id = graph_id
        self.callback = callback
        self.loop = loop
        self.pending_changes: list[FileChange] = []
        self._lock = anyio.Lock()
        # Import default ignore patterns from ingestor
        from shotgun.codebase.core.ingestor import IGNORE_PATTERNS

        self.ignore_patterns = ignore_patterns or IGNORE_PATTERNS

    def on_any_event(self, event: FileSystemEvent) -> None:
        """Handle any file system event."""
        if event.is_directory:
            return

        # Filter out temporary files
        src_path_str = (
            event.src_path.decode("utf-8")
            if isinstance(event.src_path, bytes)
            else event.src_path
        )
        path = Path(src_path_str)
        filename = path.name

        # Check if any parent directory should be ignored
        for parent in path.parents:
            if parent.name in self.ignore_patterns:
                logger.debug(
                    f"Ignoring file in ignored directory: {parent.name} - path: {src_path_str}"
                )
                return

        # Skip various temporary files
        if any(
            [
                filename.startswith("."),  # Hidden files
                filename.endswith(".swp"),  # Vim swap files
                filename.endswith(".tmp"),  # Generic temp files
                filename.endswith("~"),  # Backup files
                "#" in filename,  # Emacs temp files
                filename.startswith("__pycache__"),  # Python cache
                path.suffix in [".pyc", ".pyo"],  # Python compiled files
                # Numeric temp files (like test_watcher_fix.py.tmp.27477.1755109972829)
                any(part.isdigit() and len(part) > 4 for part in filename.split(".")),
            ]
        ):
            logger.debug(
                f"Ignoring temporary file: {filename} - event_type: {event.event_type}"
            )
            return

        # For move events, also check destination path
        dest_path_str = None
        if hasattr(event, "dest_path") and event.dest_path:
            dest_path_str = (
                event.dest_path.decode("utf-8")
                if isinstance(event.dest_path, bytes)
                else event.dest_path
            )
            dest_path = Path(dest_path_str)
            for parent in dest_path.parents:
                if parent.name in self.ignore_patterns:
                    logger.debug(
                        f"Ignoring move to ignored directory: {parent.name} - dest_path: {dest_path_str}"
                    )
                    return

        # Map event types
        event_type_map = {
            "created": "created",
            "modified": "modified",
            "deleted": "deleted",
            "moved": "moved",
        }

        mapped_type = event_type_map.get(event.event_type, event.event_type)

        # Log the event with type
        logger.info(
            f"File watcher detected {mapped_type} event - graph_id: {self.graph_id}, path: {src_path_str}, event_type: {mapped_type}"
        )

        change = FileChange(
            event_type=mapped_type,
            src_path=src_path_str,
            dest_path=dest_path_str,
            is_directory=event.is_directory,
        )

        # Queue change for batch processing
        # Use asyncio.run_coroutine_threadsafe to schedule async work from watchdog thread
        future = asyncio.run_coroutine_threadsafe(self._queue_change(change), self.loop)
        # Handle any errors
        try:
            future.result(timeout=1.0)  # Wait briefly to ensure it's scheduled
        except Exception as e:
            logger.error(
                f"Failed to queue file change: {e} - graph_id: {self.graph_id}, path: {change.src_path}"
            )

    async def _queue_change(self, change: FileChange) -> None:
        """Queue a change for processing."""
        async with self._lock:
            self.pending_changes.append(change)

        # Trigger callback
        if self.callback:
            await self.callback(self.graph_id, [change])


class CodebaseGraphManager:
    """Manages Kuzu code knowledge graphs with class-level connection pooling."""

    # Class-level storage to ensure single connection per graph
    _connections: ClassVar[dict[str, kuzu.Connection]] = {}
    _databases: ClassVar[dict[str, kuzu.Database]] = {}
    _watchers: ClassVar[dict[str, Any]] = {}
    _handlers: ClassVar[dict[str, CodebaseFileHandler]] = {}
    _lock: ClassVar[anyio.Lock | None] = None

    # Operation tracking for async operations
    _operations: ClassVar[dict[str, asyncio.Task[Any]]] = {}
    _operation_stats: ClassVar[dict[str, OperationStats]] = {}

    def __init__(self, storage_dir: Path):
        """Initialize graph manager.

        Args:
            storage_dir: Directory to store graph databases
        """
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    async def _get_lock(cls) -> anyio.Lock:
        """Get or create the class-level lock."""
        if cls._lock is None:
            cls._lock = anyio.Lock()
        return cls._lock

    @classmethod
    def _generate_graph_id(cls, repo_path: str) -> str:
        """Generate deterministic graph ID from repository path."""
        normalized = str(Path(repo_path).resolve())
        return hashlib.sha256(normalized.encode()).hexdigest()[:12]

    async def _update_graph_status(
        self, graph_id: str, status: GraphStatus, operation_id: str | None = None
    ) -> None:
        """Update the status of a graph in the database."""
        try:
            # First check if the Project node exists
            results = await self._execute_query(
                graph_id,
                "MATCH (p:Project {graph_id: $graph_id}) RETURN p",
                {"graph_id": graph_id},
            )

            if not results:
                # Project node doesn't exist yet, skip update
                logger.warning(
                    f"Project node not found for graph {graph_id}, skipping status update"
                )
                return

            await self._execute_query(
                graph_id,
                """
                MATCH (p:Project {graph_id: $graph_id})
                SET p.status = $status, p.current_operation_id = $operation_id
                """,
                {
                    "graph_id": graph_id,
                    "status": status.value,
                    "operation_id": operation_id,
                },
            )
        except Exception as e:
            logger.error(
                f"Failed to update graph status: {e} - graph_id: {graph_id}, status: {status}"
            )

    async def _store_operation_stats(
        self, graph_id: str, stats: OperationStats
    ) -> None:
        """Store operation statistics in the database."""
        try:
            await self._execute_query(
                graph_id,
                """
                MATCH (p:Project {graph_id: $graph_id})
                SET p.last_operation = $stats
                """,
                {"graph_id": graph_id, "stats": stats.model_dump_json()},
            )
            # Also store in memory for quick access
            self._operation_stats[graph_id] = stats
        except Exception as e:
            logger.error(f"Failed to store operation stats: {e} - graph_id: {graph_id}")

    async def _initialize_graph_metadata(
        self,
        graph_id: str,
        repo_path: str,
        name: str,
        languages: list[str] | None,
        exclude_patterns: list[str] | None,
    ) -> None:
        """Initialize the graph database and create initial metadata.

        This creates the database and Project node immediately so that
        status can be tracked during the build process.
        """
        graph_path = self.storage_dir / f"{graph_id}.kuzu"

        # Create database and connection
        lock = await self._get_lock()
        async with lock:
            db = kuzu.Database(str(graph_path))
            conn = kuzu.Connection(db)
            self._databases[graph_id] = db
            self._connections[graph_id] = conn

        # Create the schema
        from shotgun.codebase.core import Ingestor

        def _create_schema() -> None:
            ingestor = Ingestor(conn)
            ingestor.create_schema()

        await anyio.to_thread.run_sync(_create_schema)

        # Create initial Project node with BUILDING status
        await self._execute_query(
            graph_id,
            """
            CREATE (p:Project {
                name: $name,
                repo_path: $repo_path,
                graph_id: $graph_id,
                created_at: $created_at,
                updated_at: $updated_at,
                schema_version: $schema_version,
                build_options: $build_options,
                status: $status,
                current_operation_id: $current_operation_id,
                last_operation: $last_operation,
                node_count: 0,
                relationship_count: 0,
                stats_updated_at: $stats_updated_at
            })
            """,
            {
                "name": name,
                "repo_path": repo_path,
                "graph_id": graph_id,
                "created_at": int(time.time()),
                "updated_at": int(time.time()),
                "schema_version": "1.0.0",
                "build_options": json.dumps(
                    {"languages": languages, "exclude_patterns": exclude_patterns}
                ),
                "status": GraphStatus.BUILDING.value,
                "current_operation_id": None,
                "last_operation": None,
                "stats_updated_at": int(time.time()),
            },
        )

        # Ensure the Project node is committed
        logger.info(f"Created initial Project node for graph {graph_id}")

    async def build_graph(
        self,
        repo_path: str,
        name: str | None = None,
        languages: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> CodebaseGraph:
        """Build a new code knowledge graph.

        Args:
            repo_path: Path to repository
            name: Optional human-readable name
            languages: Languages to parse (default: all supported)
            exclude_patterns: Patterns to exclude

        Returns:
            Created graph metadata
        """
        repo_path = str(Path(repo_path).resolve())
        graph_id = self._generate_graph_id(repo_path)

        # Use repository name as default name
        if not name:
            name = Path(repo_path).name

        # Determine graph path
        graph_path = self.storage_dir / f"{graph_id}.kuzu"

        # Check if graph already exists
        if graph_path.exists():
            raise CodebaseAlreadyIndexedError(repo_path)

        # Import the builder from local core module
        from shotgun.codebase.core import CodebaseIngestor

        # Build the graph
        logger.info(
            f"Building code graph - graph_id: {graph_id}, repo_path: {repo_path}"
        )

        # Create database and connection
        lock = await self._get_lock()
        async with lock:
            if graph_id in self._databases:
                # Close existing connections
                if graph_id in self._connections:
                    self._connections[graph_id].close()
                    del self._connections[graph_id]
                self._databases[graph_id].close()
                del self._databases[graph_id]

        # Build using the local ingestor
        ingestor = CodebaseIngestor(
            db_path=str(graph_path),
            project_name=name,
            exclude_patterns=exclude_patterns or [],
        )

        # Run build in thread pool
        await anyio.to_thread.run_sync(ingestor.build_graph_from_directory, repo_path)

        # Get statistics
        lock = await self._get_lock()
        async with lock:
            db = kuzu.Database(str(graph_path))
            conn = kuzu.Connection(db)
            self._databases[graph_id] = db
            self._connections[graph_id] = conn

        # Create Project node with metadata BEFORE printing statistics
        await self._execute_query(
            graph_id,
            """
            CREATE (p:Project {
                name: $name,
                repo_path: $repo_path,
                graph_id: $graph_id,
                created_at: $created_at,
                updated_at: $updated_at,
                schema_version: $schema_version,
                build_options: $build_options
            })
            """,
            {
                "name": name,
                "repo_path": repo_path,
                "graph_id": graph_id,
                "created_at": int(time.time()),
                "updated_at": int(time.time()),
                "schema_version": "1.0.0",
                "build_options": json.dumps(
                    {"languages": languages, "exclude_patterns": exclude_patterns}
                ),
            },
        )

        # Now print detailed statistics (will include Project: 1)
        await self._print_graph_statistics(graph_id)

        # Get language statistics
        lang_stats = await self._execute_query(
            graph_id,
            """
            MATCH (f:File)
            WHERE f.extension IS NOT NULL
            RETURN f.extension as extension, COUNT(f) as count
            """,
        )

        language_stats = {}
        if lang_stats:
            for row in lang_stats:
                ext = row.get("extension", "").lower()
                if ext:
                    # Map extensions to languages
                    lang_map = {
                        ".py": "Python",
                        ".js": "JavaScript",
                        ".ts": "TypeScript",
                        ".go": "Go",
                        ".rs": "Rust",
                        ".java": "Java",
                        ".cpp": "C++",
                        ".c": "C",
                        ".cs": "C#",
                        ".rb": "Ruby",
                    }
                    lang = lang_map.get(ext, ext)
                    language_stats[lang] = row.get("count", 0)

        # Get counts dynamically
        node_count = await self._execute_query(
            graph_id, "MATCH (n) RETURN COUNT(n) as count"
        )
        relationship_count = await self._execute_query(
            graph_id, "MATCH ()-[r]->() RETURN COUNT(r) as count"
        )

        graph = CodebaseGraph(
            graph_id=graph_id,
            repo_path=repo_path,
            graph_path=str(graph_path),
            name=name,
            created_at=time.time(),
            updated_at=time.time(),
            build_options={
                "languages": languages,
                "exclude_patterns": exclude_patterns,
            },
            node_count=node_count[0]["count"] if node_count else 0,
            relationship_count=relationship_count[0]["count"]
            if relationship_count
            else 0,
            language_stats=language_stats,
            is_watching=False,
            status=GraphStatus.READY,
            last_operation=None,
            current_operation_id=None,
        )

        # Update status to READY
        await self._update_graph_status(graph_id, GraphStatus.READY)

        return graph

    async def update_graph(
        self, graph_id: str, changes: list[FileChange] | None = None
    ) -> dict[str, Any]:
        """Update graph based on file changes.

        Args:
            graph_id: Graph to update
            changes: List of file changes (if None, will auto-detect)

        Returns:
            Update statistics
        """
        # If no changes provided, use incremental update
        if changes is None:
            return await self.update_graph_incremental(graph_id)

        start_time = time.time()

        # Get graph metadata
        graph = await self.get_graph(graph_id)
        if not graph:
            raise ValueError(f"Graph {graph_id} not found")

        # Import is already done at the top of the method

        # Process changes
        stats = {
            "nodes_added": 0,
            "nodes_removed": 0,
            "relationships_added": 0,
            "relationships_removed": 0,
        }

        lock = await self._get_lock()
        async with lock:
            if graph_id not in self._connections:
                db = kuzu.Database(graph.graph_path)
                conn = kuzu.Connection(db)
                self._databases[graph_id] = db
                self._connections[graph_id] = conn

        # Group changes by type
        for change in changes:
            if change.event_type == "deleted":
                # Remove nodes for deleted files
                await self._execute_query(
                    graph_id,
                    "MATCH (n) WHERE n.path = $path DELETE n",
                    {"path": change.src_path},
                )
                stats["nodes_removed"] += 1
            elif change.event_type in ["created", "modified"]:
                # Re-parse and update the file
                # This is simplified - the actual implementation would use the ingestor
                logger.info(f"Updating file in graph - path: {change.src_path}")

        update_time = (time.time() - start_time) * 1000

        # Update metadata
        await self._execute_query(
            graph_id,
            """
            MATCH (p:Project {graph_id: $graph_id})
            SET p.updated_at = $updated_at
            """,
            {"graph_id": graph_id, "updated_at": int(time.time())},
        )

        return {"update_time_ms": update_time, **stats}

    async def update_graph_incremental(self, graph_id: str) -> dict[str, Any]:
        """Update graph by automatically detecting changes.

        Args:
            graph_id: Graph to update

        Returns:
            Update statistics
        """
        start_time = time.time()

        # Get graph metadata
        graph = await self.get_graph(graph_id)
        if not graph:
            raise ValueError(f"Graph {graph_id} not found")

        # Validate that the repository path still exists
        repo_path = Path(graph.repo_path)
        if not repo_path.exists():
            logger.error(f"Repository path no longer exists: {graph.repo_path}")
            raise ValueError(f"Repository path no longer exists: {graph.repo_path}")
        if not repo_path.is_dir():
            logger.error(f"Repository path is not a directory: {graph.repo_path}")
            raise ValueError(f"Repository path is not a directory: {graph.repo_path}")

        # Parse build options
        build_options = graph.build_options if graph.build_options else {}

        languages = build_options.get("languages")
        exclude_patterns = build_options.get("exclude_patterns")

        lock = await self._get_lock()
        async with lock:
            if graph_id not in self._connections:
                db = kuzu.Database(graph.graph_path)
                self._connections[graph_id] = kuzu.Connection(db)

            conn = self._connections[graph_id]

            # Create change detector
            from shotgun.codebase.core.change_detector import ChangeDetector, ChangeType

            detector = ChangeDetector(conn, Path(graph.repo_path))

            # Load parsers first to know what languages we can actually process
            from shotgun.codebase.core.parser_loader import load_parsers

            parsers, queries = load_parsers()
            available_languages = list(parsers.keys())

            # If no languages were specified in build options, use all available parsers
            # Otherwise, filter to intersection of requested and available languages
            if languages is None or languages == []:
                effective_languages = available_languages
            else:
                effective_languages = [
                    lang for lang in languages if lang in available_languages
                ]

            if not effective_languages:
                logger.warning(
                    f"No parsers available for requested languages - requested: {languages}, available: {available_languages}"
                )
                return {
                    "update_time_ms": (time.time() - start_time) * 1000,
                    "nodes_added": 0,
                    "nodes_removed": 0,
                    "nodes_modified": 0,
                    "relationships_added": 0,
                    "relationships_removed": 0,
                    "files_added": 0,
                    "files_modified": 0,
                    "files_deleted": 0,
                    "files_skipped": 0,
                }

            # Log what languages we're using for update
            logger.info(f"Updating graph with languages: {effective_languages}")

            # Detect changes only for languages we can process
            changes = detector.detect_changes(effective_languages, exclude_patterns)

            # Also detect ALL changes to report on skipped files
            if languages is None or (
                languages and len(languages) > len(effective_languages)
            ):
                all_changes = detector.detect_changes(None, exclude_patterns)
                skipped_count = len(all_changes) - len(changes)
                if skipped_count > 0:
                    logger.info(
                        f"Skipping {skipped_count} files due to missing parsers - available_parsers: {available_languages}, requested_languages: {languages}"
                    )
                    # Log some examples of skipped files
                    skipped_files = set(all_changes.keys()) - set(changes.keys())
                    examples = list(skipped_files)[:5]
                    if examples:
                        logger.info(f"Examples of skipped files: {examples}")
            else:
                skipped_count = 0

            if not changes:
                logger.info(f"No changes detected for graph {graph_id}")
                return {
                    "update_time_ms": (time.time() - start_time) * 1000,
                    "nodes_added": 0,
                    "nodes_removed": 0,
                    "nodes_modified": 0,
                    "relationships_added": 0,
                    "relationships_removed": 0,
                    "files_added": 0,
                    "files_modified": 0,
                    "files_deleted": 0,
                    "files_skipped": skipped_count,
                }

            logger.info(f"Processing {len(changes)} file changes for graph {graph_id}")

            # Initialize stats
            stats = {
                "nodes_added": 0,
                "nodes_removed": 0,
                "nodes_modified": 0,
                "relationships_added": 0,
                "relationships_removed": 0,
                "files_added": 0,
                "files_modified": 0,
                "files_deleted": 0,
                "files_skipped": 0,
            }

            # Initialize ingestor and builder
            from shotgun.codebase.core.ingestor import Ingestor, SimpleGraphBuilder

            ingestor = Ingestor(conn)

            builder = SimpleGraphBuilder(
                ingestor, Path(graph.repo_path), parsers, queries, exclude_patterns
            )

            # Process changes by type
            deletions = []
            modifications = []
            additions = []

            for filepath, change_type in changes.items():
                if change_type == ChangeType.DELETED:
                    deletions.append(filepath)
                    stats["files_deleted"] += 1
                elif change_type == ChangeType.MODIFIED:
                    modifications.append(filepath)
                    stats["files_modified"] += 1
                elif change_type == ChangeType.ADDED:
                    additions.append(filepath)
                    stats["files_added"] += 1

            # Process deletions first
            for filepath in deletions:
                logger.debug(f"Processing deletion: {filepath}")
                deletion_stats = ingestor.delete_file_nodes(filepath)
                stats["nodes_removed"] += sum(deletion_stats.values())

            # Process modifications (as delete + add)
            for filepath in modifications:
                logger.debug(f"Processing modification: {filepath}")
                # Delete old nodes
                deletion_stats = ingestor.delete_file_nodes(filepath)
                stats["nodes_removed"] += sum(deletion_stats.values())

                # Re-process the file
                full_path = Path(graph.repo_path) / filepath
                if full_path.exists():
                    # Determine language from file extension
                    from shotgun.codebase.core.language_config import (
                        get_language_config,
                    )

                    lang_config = get_language_config(full_path.suffix)
                    if lang_config and lang_config.name in parsers:
                        builder._process_single_file(full_path, lang_config.name)
                        stats["nodes_modified"] += 1  # Approximate

            # Process additions
            for filepath in additions:
                logger.debug(f"Processing addition: {filepath}")
                full_path = Path(graph.repo_path) / filepath
                if full_path.exists():
                    # Determine language from file extension
                    from shotgun.codebase.core.language_config import (
                        get_language_config,
                    )

                    lang_config = get_language_config(full_path.suffix)
                    if lang_config and lang_config.name in parsers:
                        builder._process_single_file(full_path, lang_config.name)
                        stats["nodes_added"] += 1  # Approximate

            # Flush all pending operations
            ingestor.flush_all()

            # Update graph metadata
            current_time = int(time.time())
            conn.execute(
                """
                MATCH (p:Project {name: $name})
                SET p.updated_at = $time
                """,
                {"name": graph.name, "time": current_time},
            )

        stats["update_time_ms"] = int((time.time() - start_time) * 1000)
        stats["files_skipped"] = skipped_count
        logger.info(f"Incremental update complete for graph {graph_id}: {stats}")
        return stats

    async def _update_graph_impl(
        self, graph_id: str, changes: list[FileChange] | None = None
    ) -> dict[str, Any]:
        """Internal implementation of graph update (runs in background)."""
        operation_id = str(uuid.uuid4())
        start_time = time.time()

        # Create operation stats
        operation_stats = OperationStats(
            operation_type="update",
            started_at=start_time,
            completed_at=None,
            success=False,
            error=None,
            stats={},
        )

        try:
            # Update status to UPDATING
            await self._update_graph_status(
                graph_id, GraphStatus.UPDATING, operation_id
            )

            # Do the actual update work
            if changes is None:
                stats = await self.update_graph_incremental(graph_id)
            else:
                stats = await self.update_graph(graph_id, changes)

            # Update operation stats
            operation_stats.completed_at = time.time()
            operation_stats.success = True
            operation_stats.stats = stats

            # Update status to READY
            await self._update_graph_status(graph_id, GraphStatus.READY, None)

            # Store operation stats
            await self._store_operation_stats(graph_id, operation_stats)

            return stats

        except Exception as e:
            # Update operation stats with error
            operation_stats.completed_at = time.time()
            operation_stats.success = False
            operation_stats.error = str(e)
            operation_stats.stats["update_time_ms"] = (time.time() - start_time) * 1000

            # Update status to ERROR
            await self._update_graph_status(graph_id, GraphStatus.ERROR, None)

            # Store operation stats
            await self._store_operation_stats(graph_id, operation_stats)

            logger.error(f"Update failed for graph {graph_id}: {e}")
            raise
        finally:
            # Clean up operation tracking
            if graph_id in self._operations:
                del self._operations[graph_id]

    async def get_operation_status(self, graph_id: str) -> dict[str, Any]:
        """Get the current operation status for a graph.

        Args:
            graph_id: Graph ID to check

        Returns:
            Dictionary with status information

        Raises:
            ValueError: If graph not found
        """
        graph = await self.get_graph(graph_id)
        if not graph:
            raise ValueError(f"Graph {graph_id} not found")

        # Build response
        response: dict[str, Any] = {
            "graph_id": graph_id,
            "status": graph.status.value,
            "current_operation_id": graph.current_operation_id,
        }

        # Add last operation details if available
        if graph.last_operation:
            response["last_operation"] = {
                "operation_type": graph.last_operation.operation_type,
                "started_at": graph.last_operation.started_at,
                "completed_at": graph.last_operation.completed_at,
                "success": graph.last_operation.success,
                "error": graph.last_operation.error,
                "stats": graph.last_operation.stats,
            }

        # Check if there's an active operation
        if graph_id in self._operations:
            task = self._operations[graph_id]
            if not task.done():
                response["operation_in_progress"] = True
            else:
                # Operation finished but not cleaned up yet
                response["operation_in_progress"] = False
                # Try to get the result or exception
                try:
                    task.result()
                except Exception as e:
                    response["operation_error"] = str(e)
        else:
            response["operation_in_progress"] = False

        return response

    async def update_graph_async(
        self, graph_id: str, changes: list[FileChange] | None = None
    ) -> str:
        """Start updating a graph asynchronously.

        Returns:
            Operation ID
        """
        # Check if graph exists
        graph = await self.get_graph(graph_id)
        if not graph:
            raise ValueError(f"Graph {graph_id} not found")

        # Check if already updating
        if graph_id in self._operations:
            raise ValueError(f"Graph {graph_id} is already being updated.")

        # Start the update operation in background
        task = asyncio.create_task(self._update_graph_impl(graph_id, changes))
        self._operations[graph_id] = task

        return graph_id

    async def start_watcher(
        self,
        graph_id: str,
        callback: Callable[[str, list[FileChange]], Awaitable[None]] | None = None,
        patterns: list[str] | None = None,
        ignore_patterns: list[str] | None = None,
    ) -> None:
        """Start watching repository for changes.

        Args:
            graph_id: Graph to watch
            callback: Async callback for changes
            patterns: File patterns to watch
            ignore_patterns: Patterns to ignore
        """
        graph = await self.get_graph(graph_id)
        if not graph:
            raise ValueError(f"Graph {graph_id} not found")

        lock = await self._get_lock()
        async with lock:
            if graph_id in self._watchers:
                logger.warning(f"Watcher already running - graph_id: {graph_id}")
                return

            # Get current event loop for thread-safe async calls
            loop = asyncio.get_running_loop()

            # Combine default ignore patterns with any custom ones
            from shotgun.codebase.core.ingestor import IGNORE_PATTERNS

            combined_ignore = IGNORE_PATTERNS.copy()
            if ignore_patterns:
                combined_ignore.update(ignore_patterns)

            # Create handler with loop reference and ignore patterns
            handler = CodebaseFileHandler(graph_id, callback, loop, combined_ignore)
            self._handlers[graph_id] = handler

            # Create and start observer
            observer = Observer()
            observer.schedule(handler, graph.repo_path, recursive=True)
            observer.start()

            self._watchers[graph_id] = observer

        logger.info(
            f"Started file watcher - graph_id: {graph_id}, repo_path: {graph.repo_path}"
        )

    async def stop_watcher(self, graph_id: str) -> int:
        """Stop watching repository.

        Args:
            graph_id: Graph to stop watching

        Returns:
            Number of changes processed
        """
        lock = await self._get_lock()
        async with lock:
            if graph_id not in self._watchers:
                logger.warning(f"No watcher running - graph_id: {graph_id}")
                return 0

            observer = self._watchers[graph_id]
            observer.stop()
            observer.join(timeout=5)

            # Get change count
            handler = self._handlers.get(graph_id)
            change_count = len(handler.pending_changes) if handler else 0

            # Clean up
            del self._watchers[graph_id]
            if graph_id in self._handlers:
                del self._handlers[graph_id]

        logger.info(
            f"Stopped file watcher - graph_id: {graph_id}, changes_processed: {change_count}"
        )
        return change_count

    async def execute_query(
        self, graph_id: str, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute Cypher query on graph.

        Args:
            graph_id: Graph to query
            query: Cypher query
            parameters: Query parameters

        Returns:
            Query results
        """
        return await self._execute_query(graph_id, query, parameters)

    async def _execute_query(
        self, graph_id: str, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Internal query execution with connection management."""
        lock = await self._get_lock()
        async with lock:
            if graph_id not in self._connections:
                # Open connection if needed
                graph_path = self.storage_dir / f"{graph_id}.kuzu"
                if not graph_path.exists():
                    raise ValueError(f"Graph {graph_id} not found")

                db = kuzu.Database(str(graph_path))
                conn = kuzu.Connection(db)
                self._databases[graph_id] = db
                self._connections[graph_id] = conn

            conn = self._connections[graph_id]

        # Execute query in thread pool
        def _run_query() -> list[dict[str, Any]]:
            if parameters:
                result = conn.execute(query, parameters)
            else:
                result = conn.execute(query)

            # Collect results
            rows = []
            columns = (
                result.get_column_names() if hasattr(result, "get_column_names") else []
            )

            if hasattr(result, "has_next") and not isinstance(result, list):
                while result.has_next():
                    row = result.get_next()
                    row_dict = {}
                    for i, col in enumerate(columns):
                        if isinstance(row, tuple | list) and i < len(row):
                            row_dict[col] = row[i]
                        elif hasattr(row, col):
                            row_dict[col] = getattr(row, col)
                    rows.append(row_dict)
            elif isinstance(result, list):
                # Convert list of QueryResult objects to list of dicts
                for query_result in result:
                    row_dict = {}
                    for col in columns:
                        if hasattr(query_result, col):
                            row_dict[col] = getattr(query_result, col)
                    rows.append(row_dict)

            return rows

        return await anyio.to_thread.run_sync(_run_query)

    async def get_graph(self, graph_id: str) -> CodebaseGraph | None:
        """Get graph metadata.

        Args:
            graph_id: Graph ID

        Returns:
            Graph metadata or None if not found
        """
        graph_path = self.storage_dir / f"{graph_id}.kuzu"
        if not graph_path.exists():
            return None

        # Query metadata from Project node
        try:
            results = await self._execute_query(
                graph_id,
                "MATCH (p:Project {graph_id: $graph_id}) RETURN p",
                {"graph_id": graph_id},
            )

            if not results:
                return None

            project = results[0]["p"]

            # Check if watcher is active
            is_watching = graph_id in self._watchers

            # Get language statistics
            lang_stats = await self._execute_query(
                graph_id,
                """
                MATCH (f:File)
                WHERE f.extension IS NOT NULL
                RETURN f.extension as extension, COUNT(f) as count
                """,
            )

            language_stats = {}
            if lang_stats:
                for row in lang_stats:
                    ext = row.get("extension", "").lower()
                    if ext:
                        # Map extensions to languages
                        lang_map = {
                            ".py": "Python",
                            ".js": "JavaScript",
                            ".ts": "TypeScript",
                            ".go": "Go",
                            ".rs": "Rust",
                            ".java": "Java",
                            ".cpp": "C++",
                            ".c": "C",
                            ".cs": "C#",
                            ".rb": "Ruby",
                        }
                        lang = lang_map.get(ext, ext)
                        language_stats[lang] = row.get("count", 0)

            # Get counts dynamically
            node_count = await self._execute_query(
                graph_id, "MATCH (n) RETURN COUNT(n) as count"
            )
            relationship_count = await self._execute_query(
                graph_id, "MATCH ()-[r]->() RETURN COUNT(r) as count"
            )

            # Get detailed statistics
            node_stats, relationship_stats = await self._get_graph_statistics(graph_id)

            # Parse status
            status_str = project.get("status", GraphStatus.READY.value)
            try:
                status = GraphStatus(status_str)
            except ValueError:
                status = GraphStatus.READY

            # Parse last operation
            last_operation = None
            last_op_str = project.get("last_operation")
            if last_op_str:
                try:
                    last_op_data = json.loads(last_op_str)
                    last_operation = OperationStats(**last_op_data)
                except Exception as e:
                    logger.debug(f"Failed to parse last operation stats: {e}")
                    last_operation = None

            return CodebaseGraph(
                graph_id=graph_id,
                repo_path=project.get("repo_path", ""),
                graph_path=str(graph_path),
                name=project.get("name", ""),
                created_at=float(project.get("created_at", 0)),
                updated_at=float(project.get("updated_at", 0)),
                schema_version=project.get("schema_version", "1.0.0"),
                build_options=json.loads(project.get("build_options", "{}")),
                node_count=node_count[0]["count"] if node_count else 0,
                relationship_count=relationship_count[0]["count"]
                if relationship_count
                else 0,
                node_stats=node_stats,
                relationship_stats=relationship_stats,
                language_stats=language_stats,
                is_watching=is_watching,
                status=status,
                last_operation=last_operation,
                current_operation_id=project.get("current_operation_id"),
            )
        except Exception as e:
            logger.error(
                f"Failed to get graph metadata - graph_id: {graph_id}, error: {str(e)}"
            )
            return None

    async def list_graphs(self) -> list[CodebaseGraph]:
        """List all available graphs.

        Returns:
            List of graph metadata
        """
        graphs = []

        # Find all .kuzu files
        for path in self.storage_dir.glob("*.kuzu"):
            if path.is_file():
                graph_id = path.stem
                graph = await self.get_graph(graph_id)
                if graph:
                    graphs.append(graph)

        return sorted(graphs, key=lambda g: g.updated_at, reverse=True)

    async def delete_graph(self, graph_id: str) -> None:
        """Delete a graph.

        Args:
            graph_id: Graph to delete
        """
        # Stop watcher if running
        if graph_id in self._watchers:
            await self.stop_watcher(graph_id)

        # Close connections
        lock = await self._get_lock()
        async with lock:
            if graph_id in self._connections:
                self._connections[graph_id].close()
                del self._connections[graph_id]
            if graph_id in self._databases:
                self._databases[graph_id].close()
                del self._databases[graph_id]

        # Delete files
        graph_path = self.storage_dir / f"{graph_id}.kuzu"
        if graph_path.exists():
            # Delete the database file
            await anyio.to_thread.run_sync(graph_path.unlink)

        # Also delete the WAL file if it exists
        wal_path = self.storage_dir / f"{graph_id}.kuzu.wal"
        if wal_path.exists():
            await anyio.to_thread.run_sync(wal_path.unlink)

        logger.info(f"Deleted graph - graph_id: {graph_id}")

    async def _get_graph_statistics(
        self, graph_id: str
    ) -> tuple[dict[str, int], dict[str, int]]:
        """Get detailed statistics about the graph.

        Returns:
            Tuple of (node_stats, relationship_stats)
        """
        node_stats = {}

        # Count each node type
        node_types = [
            "Project",
            "Package",
            "Module",
            "Class",
            "Function",
            "Method",
            "File",
            "Folder",
            "FileMetadata",
            "DeletionLog",
        ]

        for node_type in node_types:
            try:
                result = await self._execute_query(
                    graph_id, f"MATCH (n:{node_type}) RETURN COUNT(n) as count"
                )
                count = result[0]["count"] if result else 0
                if count > 0:
                    node_stats[node_type] = count
            except Exception as e:
                logger.debug(f"Failed to count {node_type} nodes: {e}")

        # Count relationships - need to handle multiple tables for each type
        rel_counts = {}

        # CONTAINS relationships
        for prefix in [
            "CONTAINS_PACKAGE",
            "CONTAINS_FOLDER",
            "CONTAINS_FILE",
            "CONTAINS_MODULE",
        ]:
            count = 0
            for suffix in ["", "_PKG", "_FOLDER"]:
                table = f"{prefix}{suffix}"
                try:
                    result = await self._execute_query(
                        graph_id, f"MATCH ()-[r:{table}]->() RETURN COUNT(r) as count"
                    )
                    if result:
                        count += result[0]["count"]
                except Exception as e:
                    logger.debug(f"Failed to count {table} relationships: {e}")
            if count > 0:
                rel_counts[prefix] = count

        # Other relationships
        for rel_type in [
            "DEFINES",
            "DEFINES_FUNC",
            "DEFINES_METHOD",
            "INHERITS",
            "OVERRIDES",
            "DEPENDS_ON_EXTERNAL",
            "IMPORTS",
        ]:
            try:
                result = await self._execute_query(
                    graph_id, f"MATCH ()-[r:{rel_type}]->() RETURN COUNT(r) as count"
                )
                if result and result[0]["count"] > 0:
                    rel_counts[rel_type] = result[0]["count"]
            except Exception as e:
                logger.debug(f"Failed to count {rel_type} relationships: {e}")

        # CALLS relationships (multiple tables)
        calls_count = 0
        for table in ["CALLS", "CALLS_FM", "CALLS_MF", "CALLS_MM"]:
            try:
                result = await self._execute_query(
                    graph_id, f"MATCH ()-[r:{table}]->() RETURN COUNT(r) as count"
                )
                if result:
                    calls_count += result[0]["count"]
            except Exception as e:
                logger.debug(f"Failed to count {table} relationships: {e}")
        if calls_count > 0:
            rel_counts["CALLS (total)"] = calls_count

        # TRACKS relationships
        tracks_count = 0
        for entity in ["Module", "Class", "Function", "Method"]:
            try:
                result = await self._execute_query(
                    graph_id,
                    f"MATCH ()-[r:TRACKS_{entity}]->() RETURN COUNT(r) as count",
                )
                if result:
                    tracks_count += result[0]["count"]
            except Exception as e:
                logger.debug(f"Failed to count TRACKS_{entity} relationships: {e}")
        if tracks_count > 0:
            rel_counts["TRACKS (total)"] = tracks_count

        return node_stats, rel_counts

    async def _print_graph_statistics(self, graph_id: str) -> None:
        """Print detailed statistics about the graph."""
        logger.info("\n=== Graph Statistics ===")

        node_stats, rel_stats = await self._get_graph_statistics(graph_id)

        # Print node stats
        for node_type in [
            "Project",
            "Package",
            "Module",
            "Class",
            "Function",
            "Method",
            "File",
            "Folder",
            "FileMetadata",
            "DeletionLog",
        ]:
            count = node_stats.get(node_type, 0)
            logger.info(f"{node_type}: {count}")

        logger.info("\nRelationship counts:")
        for rel_type, count in sorted(rel_stats.items()):
            logger.info(f"{rel_type}: {count}")

    async def _build_graph_impl(
        self,
        graph_id: str,
        repo_path: str,
        name: str,
        languages: list[str] | None,
        exclude_patterns: list[str] | None,
    ) -> CodebaseGraph:
        """Internal implementation of graph building (runs in background)."""
        operation_id = str(uuid.uuid4())
        start_time = time.time()

        # Create operation stats
        operation_stats = OperationStats(
            operation_type="build",
            started_at=start_time,
            completed_at=None,
            success=False,
            error=None,
            stats={},
        )

        try:
            # Update status to BUILDING
            await self._update_graph_status(
                graph_id, GraphStatus.BUILDING, operation_id
            )

            # Do the actual build work
            graph = await self._do_build_graph(
                graph_id, repo_path, name, languages, exclude_patterns
            )

            # Update operation stats
            operation_stats.completed_at = time.time()
            operation_stats.success = True
            operation_stats.stats = {
                "node_count": graph.node_count,
                "relationship_count": graph.relationship_count,
                "language_stats": graph.language_stats,
                "build_time_ms": (time.time() - start_time) * 1000,
            }

            # Update status to READY
            await self._update_graph_status(graph_id, GraphStatus.READY, None)

            # Store operation stats
            await self._store_operation_stats(graph_id, operation_stats)

            return graph

        except Exception as e:
            # Update operation stats with error
            operation_stats.completed_at = time.time()
            operation_stats.success = False
            operation_stats.error = str(e)
            operation_stats.stats["build_time_ms"] = (time.time() - start_time) * 1000

            # Update status to ERROR
            await self._update_graph_status(graph_id, GraphStatus.ERROR, None)

            # Store operation stats
            await self._store_operation_stats(graph_id, operation_stats)

            logger.error(f"Build failed for graph {graph_id}: {e}")
            raise
        finally:
            # Clean up operation tracking
            if graph_id in self._operations:
                del self._operations[graph_id]

    async def _do_build_graph(
        self,
        graph_id: str,
        repo_path: str,
        name: str,
        languages: list[str] | None,
        exclude_patterns: list[str] | None,
    ) -> CodebaseGraph:
        """Execute the actual graph building logic (extracted from original build_graph)."""
        # The database and Project node already exist from _initialize_graph_metadata

        # Get existing connection
        lock = await self._get_lock()
        async with lock:
            if graph_id not in self._connections:
                raise RuntimeError(f"Connection not found for graph {graph_id}")
            conn = self._connections[graph_id]

        # Import the builder from local core module

        # Build the graph
        logger.info(
            f"Building code graph - graph_id: {graph_id}, repo_path: {repo_path}"
        )

        # Build the graph using our existing connection
        def _build_graph() -> None:
            from shotgun.codebase.core import Ingestor, SimpleGraphBuilder
            from shotgun.codebase.core.parser_loader import load_parsers

            # Load parsers for requested languages
            parsers, queries = load_parsers()

            # Log available parsers before filtering
            logger.info(f"Available parsers: {list(parsers.keys())}")

            # Filter parsers to requested languages if specified
            if languages:
                parsers = {
                    lang: parser
                    for lang, parser in parsers.items()
                    if lang in languages
                }
                queries = {
                    lang: query for lang, query in queries.items() if lang in languages
                }
                logger.info(
                    f"Filtered parsers to requested languages {languages}: {list(parsers.keys())}"
                )
            else:
                logger.info(f"Using all available parsers: {list(parsers.keys())}")

            # Create ingestor with existing connection
            ingestor = Ingestor(conn)

            # Create builder
            builder = SimpleGraphBuilder(
                ingestor=ingestor,
                repo_path=Path(repo_path),
                parsers=parsers,
                queries=queries,
                exclude_patterns=exclude_patterns,
            )

            # Build the graph
            builder.run()

        # Run build in thread pool
        await anyio.to_thread.run_sync(_build_graph)

        # Now print detailed statistics (will include Project: 1)
        await self._print_graph_statistics(graph_id)

        # Get the updated graph metadata
        graph = await self.get_graph(graph_id)
        if not graph:
            raise RuntimeError(f"Failed to retrieve graph {graph_id} after build")

        return graph

    async def build_graph_async(
        self,
        repo_path: str,
        name: str | None = None,
        languages: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> str:
        """Start building a new code knowledge graph asynchronously.

        Returns:
            Graph ID of the graph being built
        """
        repo_path = str(Path(repo_path).resolve())
        graph_id = self._generate_graph_id(repo_path)

        # Use repository name as default name
        if not name:
            name = Path(repo_path).name

        # Check if graph already exists
        graph_path = self.storage_dir / f"{graph_id}.kuzu"
        if graph_path.exists():
            raise ValueError(
                f"Graph already exists for {repo_path}. Use update_graph() to modify it."
            )

        # Check if already building
        if graph_id in self._operations:
            raise ValueError(f"Graph {graph_id} is already being built.")

        # Create the database and initial Project node immediately
        # This allows status tracking during the build
        await self._initialize_graph_metadata(
            graph_id=graph_id,
            repo_path=repo_path,
            name=name,
            languages=languages,
            exclude_patterns=exclude_patterns,
        )

        # Start the build operation in background
        task = asyncio.create_task(
            self._build_graph_impl(
                graph_id, repo_path, name, languages, exclude_patterns
            )
        )
        self._operations[graph_id] = task

        return graph_id
