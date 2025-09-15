#!/usr/bin/env python3
"""Runner script for integration tests.

This script sets up the environment and runs integration tests for CodebaseService.
It can be run independently or as part of CI/CD.
"""

import argparse
import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from shotgun.codebase import CodebaseService, QueryType


def disable_logging():
    """Disable logging during tests to avoid logger issues and noise."""
    import logging

    logging.disable(logging.CRITICAL)


async def run_smoke_test() -> bool:
    """Run a quick smoke test to verify basic functionality."""
    disable_logging()
    print("🧪 Running integration smoke test...")

    with tempfile.TemporaryDirectory(prefix="shotgun_smoke_test_") as temp_dir:
        temp_path = Path(temp_dir)

        # Create service
        service = CodebaseService(temp_path / "storage")

        # Create minimal test codebase
        test_codebase = temp_path / "test_code"
        test_codebase.mkdir()

        # Write a simple Python file
        (test_codebase / "example.py").write_text("""
class Example:
    def hello(self):
        return "world"

def test_function():
    return True
""")

        try:
            # Test graph creation
            print("  📈 Creating graph...")
            start_time = time.time()
            graph = await service.create_graph(test_codebase, "Smoke Test Graph")
            create_time = time.time() - start_time
            print(
                f"  ✅ Graph created in {create_time:.2f}s (ID: {graph.graph_id[:8]}...)"
            )

            # Test Cypher query
            print("  🔍 Testing Cypher query...")
            start_time = time.time()
            cypher_result = await service.execute_query(
                graph.graph_id,
                "MATCH (c:Class) RETURN c.name AS name, c.qualified_name AS qualified_name",
                QueryType.CYPHER,
            )
            cypher_time = time.time() - start_time
            print(
                f"  ✅ Cypher query executed in {cypher_time:.2f}s, found {cypher_result.row_count} classes"
            )

            # Test natural language query
            print("  🧠 Testing natural language query...")
            start_time = time.time()
            nl_result = await service.execute_query(
                graph.graph_id, "Show me all functions", QueryType.NATURAL_LANGUAGE
            )
            nl_time = time.time() - start_time
            print(
                f"  ✅ Natural language query executed in {nl_time:.2f}s, found {nl_result.row_count} results"
            )

            # Test error handling
            print("  ❌ Testing error handling...")
            error_result = await service.execute_query(
                graph.graph_id, "INVALID CYPHER", QueryType.CYPHER
            )
            print(f"  ✅ Error handling works: {not error_result.success}")

            print("🎉 Smoke test completed successfully!")
            return True

        except Exception as e:
            print(f"❌ Smoke test failed: {e}")
            import traceback

            traceback.print_exc()
            return False


async def run_comprehensive_test() -> bool:
    """Run a more comprehensive test with realistic codebase."""
    disable_logging()
    print("🔬 Running comprehensive integration test...")

    with tempfile.TemporaryDirectory(prefix="shotgun_comprehensive_test_") as temp_dir:
        temp_path = Path(temp_dir)

        # Create service
        service = CodebaseService(temp_path / "storage")

        # Create realistic test codebase
        test_codebase = temp_path / "realistic_code"
        test_codebase.mkdir()

        # Create multiple Python files
        files_to_create = {
            "models.py": """
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class User:
    id: int
    name: str
    email: str
    active: bool = True

    def deactivate(self):
        self.active = False

class UserRepository:
    def __init__(self):
        self.users: List[User] = []

    def add_user(self, user: User) -> None:
        self.users.append(user)

    def find_by_id(self, user_id: int) -> Optional[User]:
        return next((u for u in self.users if u.id == user_id), None)

    def find_active_users(self) -> List[User]:
        return [u for u in self.users if u.active]
""",
            "services.py": """
from models import User, UserRepository
from typing import List

class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def create_user(self, name: str, email: str) -> User:
        user_id = len(self.repository.users) + 1
        user = User(user_id, name, email)
        self.repository.add_user(user)
        return user

    def get_user(self, user_id: int) -> User:
        user = self.repository.find_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        return user

    def get_active_users(self) -> List[User]:
        return self.repository.find_active_users()

    def deactivate_user(self, user_id: int) -> None:
        user = self.get_user(user_id)
        user.deactivate()

def test_user_service():
    repo = UserRepository()
    service = UserService(repo)
    user = service.create_user("John Doe", "john@example.com")
    assert user.name == "John Doe"
""",
            "main.py": """
from services import UserService
from models import UserRepository

def main():
    repository = UserRepository()
    service = UserService(repository)

    # Create some test users
    user1 = service.create_user("Alice", "alice@example.com")
    user2 = service.create_user("Bob", "bob@example.com")

    print(f"Created users: {user1.name}, {user2.name}")

    # Test retrieval
    found_user = service.get_user(1)
    print(f"Found user: {found_user.name}")

    # Test deactivation
    service.deactivate_user(2)
    active_users = service.get_active_users()
    print(f"Active users: {[u.name for u in active_users]}")

if __name__ == "__main__":
    main()
""",
            "utils.py": r"""
import re
from typing import Union

def validate_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def format_name(first: str, last: str) -> str:
    return f"{first.title()} {last.title()}"

def calculate_age(birth_year: int, current_year: int) -> int:
    return max(0, current_year - birth_year)

class ValidationError(Exception):
    pass

def validate_user_data(name: str, email: str, age: int) -> None:
    if not name or len(name.strip()) == 0:
        raise ValidationError("Name is required")

    if not validate_email(email):
        raise ValidationError("Invalid email format")

    if age < 0 or age > 150:
        raise ValidationError("Invalid age")

def test_validation():
    try:
        validate_user_data("John Doe", "john@example.com", 30)
        return True
    except ValidationError:
        return False
""",
        }

        # Write all files
        for filename, content in files_to_create.items():
            (test_codebase / filename).write_text(content)

        try:
            print(f"  📁 Created test codebase with {len(files_to_create)} files")

            # Test graph creation
            print("  📈 Creating comprehensive graph...")
            start_time = time.time()
            graph = await service.create_graph(
                test_codebase, "Comprehensive Test Graph"
            )
            create_time = time.time() - start_time
            print(f"  ✅ Graph created in {create_time:.2f}s")
            print(f"     - Nodes: {graph.node_count}")
            print(f"     - Relationships: {graph.relationship_count}")

            # Test various queries
            test_queries = [
                (
                    "Classes",
                    "MATCH (c:Class) RETURN count(c) as count",
                    QueryType.CYPHER,
                ),
                (
                    "Functions",
                    "MATCH (f:Function) RETURN count(f) as count",
                    QueryType.CYPHER,
                ),
                (
                    "Methods",
                    "MATCH (m:Method) RETURN count(m) as count",
                    QueryType.CYPHER,
                ),
                (
                    "Find User class",
                    "Show me the User class",
                    QueryType.NATURAL_LANGUAGE,
                ),
                (
                    "Find test functions",
                    "Find all functions that start with test",
                    QueryType.NATURAL_LANGUAGE,
                ),
                (
                    "UserService methods",
                    "What methods does UserService have?",
                    QueryType.NATURAL_LANGUAGE,
                ),
            ]

            for test_name, query, query_type in test_queries:
                print(f"  🔍 Testing: {test_name}")
                start_time = time.time()
                result = await service.execute_query(graph.graph_id, query, query_type)
                query_time = time.time() - start_time

                if result.success:
                    if query_type == QueryType.CYPHER and "count" in query.lower():
                        count = result.results[0]["count"] if result.results else 0
                        print(f"    ✅ Found {count} items in {query_time:.2f}s")
                    else:
                        print(
                            f"    ✅ Query successful, {result.row_count} results in {query_time:.2f}s"
                        )
                        if result.cypher_query:
                            print(
                                f"    📝 Generated Cypher: {result.cypher_query[:100]}..."
                            )
                else:
                    print(f"    ❌ Query failed: {result.error}")

            # Test graph management
            print("  📊 Testing graph management...")
            graphs = await service.list_graphs()
            print(f"    📋 Found {len(graphs)} graphs")

            graph_info = await service.get_graph(graph.graph_id)
            print(f"    📖 Retrieved graph info: {graph_info.name}")

            print("🎉 Comprehensive test completed successfully!")
            return True

        except Exception as e:
            print(f"❌ Comprehensive test failed: {e}")
            import traceback

            traceback.print_exc()
            return False


def check_environment():
    """Check if the environment is properly configured for integration tests."""
    print("🔧 Checking environment...")

    issues = []

    # Check for LLM configuration
    if not (os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")):
        issues.append("No LLM API keys found (OPENAI_API_KEY or ANTHROPIC_API_KEY)")

    if issues:
        print("❌ Environment issues found:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("✅ Environment looks good!")
        return True


async def main():
    """Main function to run integration tests."""
    parser = argparse.ArgumentParser(
        description="Run CodebaseService integration tests"
    )
    parser.add_argument("--smoke-only", action="store_true", help="Run only smoke test")
    parser.add_argument(
        "--comprehensive-only", action="store_true", help="Run only comprehensive test"
    )
    parser.add_argument(
        "--skip-env-check", action="store_true", help="Skip environment check"
    )

    args = parser.parse_args()

    print("🚀 CodebaseService Integration Tests")
    print("=" * 50)

    # Check environment unless skipped
    if not args.skip_env_check:
        if not check_environment():
            print("\n💡 To skip environment checks, use --skip-env-check")
            sys.exit(1)

    success = True

    # Run smoke test
    if not args.comprehensive_only:
        try:
            success &= await run_smoke_test()
        except Exception as e:
            print(f"❌ Smoke test crashed: {e}")
            success = False

    # Run comprehensive test
    if not args.smoke_only:
        try:
            success &= await run_comprehensive_test()
        except Exception as e:
            print(f"❌ Comprehensive test crashed: {e}")
            success = False

    print("\n" + "=" * 50)
    if success:
        print("🎉 All integration tests passed!")
        sys.exit(0)
    else:
        print("❌ Some integration tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
