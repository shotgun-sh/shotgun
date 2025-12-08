"""Integration tests for LadybugDB (real_ladybug) compatibility.

These tests verify that the migration from Kuzu to LadybugDB works correctly
by testing all database operations used in the codebase.

Note: These tests don't use @pytest.mark.integration because they don't require
LLM configuration - they're pure database tests.
"""

from pathlib import Path

import real_ladybug as kuzu


def test_database_creation(tmp_path: Path):
    """Test creating a LadybugDB database."""
    db_path = tmp_path / "test.db"
    db = kuzu.Database(str(db_path))
    assert db is not None
    db.close()


def test_connection_creation(tmp_path: Path):
    """Test creating a connection to a LadybugDB database."""
    db_path = tmp_path / "test.db"
    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)
    assert conn is not None
    conn.close()
    db.close()


def test_schema_creation(tmp_path: Path):
    """Test creating node and relationship tables matching our schema."""
    db_path = tmp_path / "test.db"
    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)

    # Create node tables matching our actual schema
    conn.execute(
        "CREATE NODE TABLE Project("
        "name STRING PRIMARY KEY, "
        "repo_path STRING, "
        "graph_id STRING, "
        "created_at INT64, "
        "updated_at INT64"
        ")"
    )
    conn.execute(
        "CREATE NODE TABLE File(path STRING PRIMARY KEY, name STRING, extension STRING)"
    )
    conn.execute(
        "CREATE NODE TABLE Module("
        "qualified_name STRING PRIMARY KEY, "
        "name STRING, "
        "path STRING"
        ")"
    )
    conn.execute(
        "CREATE NODE TABLE Function("
        "qualified_name STRING PRIMARY KEY, "
        "name STRING, "
        "docstring STRING"
        ")"
    )

    # Create relationship tables
    conn.execute("CREATE REL TABLE CONTAINS_FILE(FROM Project TO File)")
    conn.execute("CREATE REL TABLE DEFINES_FUNC(FROM Module TO Function)")

    conn.close()
    db.close()


def test_node_insertion_with_merge(tmp_path: Path):
    """Test inserting nodes using MERGE (upsert behavior)."""
    db_path = tmp_path / "test.db"
    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)

    # Create table
    conn.execute(
        "CREATE NODE TABLE TestNode(id STRING PRIMARY KEY, name STRING, value INT64)"
    )

    # Insert using MERGE (our actual pattern)
    conn.execute(
        "MERGE (n:TestNode {id: $id}) SET n.name = $name, n.value = $value",
        {"id": "test1", "name": "Test Node 1", "value": 42},
    )

    # Verify insertion
    result = conn.execute("MATCH (n:TestNode) RETURN n.id, n.name, n.value")
    rows = list(result)
    assert len(rows) == 1
    assert rows[0][0] == "test1"
    assert rows[0][1] == "Test Node 1"
    assert rows[0][2] == 42

    # Test upsert behavior - same ID should update
    conn.execute(
        "MERGE (n:TestNode {id: $id}) SET n.name = $name, n.value = $value",
        {"id": "test1", "name": "Updated Name", "value": 100},
    )

    result = conn.execute("MATCH (n:TestNode) RETURN n.id, n.name, n.value")
    rows = list(result)
    assert len(rows) == 1
    assert rows[0][1] == "Updated Name"
    assert rows[0][2] == 100

    conn.close()
    db.close()


def test_relationship_creation(tmp_path: Path):
    """Test creating relationships between nodes."""
    db_path = tmp_path / "test.db"
    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)

    # Create tables
    conn.execute("CREATE NODE TABLE Author(name STRING PRIMARY KEY)")
    conn.execute("CREATE NODE TABLE Book(title STRING PRIMARY KEY)")
    conn.execute("CREATE REL TABLE WROTE(FROM Author TO Book)")

    # Insert nodes
    conn.execute("CREATE (a:Author {name: $name})", {"name": "Alice"})
    conn.execute("CREATE (b:Book {title: $title})", {"title": "Wonderland"})

    # Create relationship (our actual pattern)
    conn.execute(
        "MATCH (a:Author {name: $author}), (b:Book {title: $book}) "
        "MERGE (a)-[:WROTE]->(b)",
        {"author": "Alice", "book": "Wonderland"},
    )

    # Verify relationship
    result = conn.execute("MATCH (a:Author)-[:WROTE]->(b:Book) RETURN a.name, b.title")
    rows = list(result)
    assert len(rows) == 1
    assert rows[0][0] == "Alice"
    assert rows[0][1] == "Wonderland"

    conn.close()
    db.close()


def test_query_with_count(tmp_path: Path):
    """Test queries with COUNT aggregation."""
    db_path = tmp_path / "test.db"
    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)

    conn.execute("CREATE NODE TABLE Item(id STRING PRIMARY KEY, type STRING)")

    # Insert multiple items
    for i in range(5):
        conn.execute(
            "CREATE (n:Item {id: $id, type: $type})",
            {"id": f"item{i}", "type": "A" if i % 2 == 0 else "B"},
        )

    # Count all
    result = conn.execute("MATCH (n:Item) RETURN COUNT(n) as count")
    rows = list(result)
    assert rows[0][0] == 5

    # Count by type
    result = conn.execute(
        "MATCH (n:Item) WHERE n.type = $type RETURN COUNT(n) as count",
        {"type": "A"},
    )
    rows = list(result)
    assert rows[0][0] == 3

    conn.close()
    db.close()


def test_detach_delete(tmp_path: Path):
    """Test DETACH DELETE for node removal with relationships."""
    db_path = tmp_path / "test.db"
    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)

    # Create tables
    conn.execute("CREATE NODE TABLE Parent(name STRING PRIMARY KEY)")
    conn.execute("CREATE NODE TABLE Child(name STRING PRIMARY KEY)")
    conn.execute("CREATE REL TABLE HAS_CHILD(FROM Parent TO Child)")

    # Insert nodes and relationships
    conn.execute("CREATE (p:Parent {name: 'Parent1'})")
    conn.execute("CREATE (c:Child {name: 'Child1'})")
    conn.execute(
        "MATCH (p:Parent {name: 'Parent1'}), (c:Child {name: 'Child1'}) "
        "CREATE (p)-[:HAS_CHILD]->(c)"
    )

    # Verify relationship exists
    result = conn.execute("MATCH (p:Parent)-[:HAS_CHILD]->(c:Child) RETURN COUNT(*)")
    assert list(result)[0][0] == 1

    # DETACH DELETE the child (removes node and all connected relationships)
    conn.execute("MATCH (c:Child {name: 'Child1'}) DETACH DELETE c")

    # Verify child is gone
    result = conn.execute("MATCH (c:Child) RETURN COUNT(*)")
    assert list(result)[0][0] == 0

    # Verify relationship is gone
    result = conn.execute("MATCH (p:Parent)-[:HAS_CHILD]->(c:Child) RETURN COUNT(*)")
    assert list(result)[0][0] == 0

    conn.close()
    db.close()


def test_multiple_connections(tmp_path: Path):
    """Test that multiple connections to the same database work."""
    db_path = tmp_path / "test.db"
    db = kuzu.Database(str(db_path))

    # Create multiple connections
    conn1 = kuzu.Connection(db)
    conn2 = kuzu.Connection(db)

    # Create table with first connection
    conn1.execute("CREATE NODE TABLE SharedTable(id STRING PRIMARY KEY)")
    conn1.execute("CREATE (n:SharedTable {id: 'from_conn1'})")

    # Query with second connection
    result = conn2.execute("MATCH (n:SharedTable) RETURN n.id")
    rows = list(result)
    assert len(rows) == 1
    assert rows[0][0] == "from_conn1"

    conn1.close()
    conn2.close()
    db.close()


def test_result_iteration(tmp_path: Path):
    """Test iterating over query results (our actual pattern)."""
    db_path = tmp_path / "test.db"
    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)

    conn.execute("CREATE NODE TABLE Data(id INT64 PRIMARY KEY, value STRING)")

    for i in range(10):
        conn.execute(
            "CREATE (n:Data {id: $id, value: $value})",
            {"id": i, "value": f"value_{i}"},
        )

    result = conn.execute("MATCH (n:Data) RETURN n.id, n.value ORDER BY n.id")

    # Iterate like we do in manager.py
    collected = []
    for row in result:
        collected.append({"id": row[0], "value": row[1]})

    assert len(collected) == 10
    assert collected[0] == {"id": 0, "value": "value_0"}
    assert collected[9] == {"id": 9, "value": "value_9"}

    conn.close()
    db.close()
