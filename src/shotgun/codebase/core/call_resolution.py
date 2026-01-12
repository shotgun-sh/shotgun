"""Call resolution utilities for function/method call graph building.

This module provides shared utilities for resolving function calls
and calculating confidence scores for potential callee matches.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping


def calculate_callee_confidence(
    caller_qn: str,
    callee_qn: str,
    module_qn: str,
    object_name: str | None,
    simple_name_lookup: Mapping[str, Collection[str]],
) -> float:
    """Calculate confidence score for a potential callee match.

    Uses multiple heuristics to determine how likely a given callee
    is the correct target of a function call:
    1. Module locality - functions in the same module are most likely
    2. Package locality - functions in the same package hierarchy
    3. Object/class match for method calls
    4. Standard library boost
    5. Name uniqueness boost

    Args:
        caller_qn: Qualified name of the calling function
        callee_qn: Qualified name of the potential callee
        module_qn: Qualified name of the current module
        object_name: Object name for method calls (e.g., 'obj' in obj.method())
        simple_name_lookup: Mapping from simple names to qualified names
            (supports both set[str] and list[str] values)

    Returns:
        Confidence score between 0.0 and 1.0
    """
    score = 0.0

    # 1. Module locality - functions in the same module are most likely
    if callee_qn.startswith(module_qn + "."):
        score += 0.5

        # Even higher if in the same class
        caller_parts = caller_qn.split(".")
        callee_parts = callee_qn.split(".")
        if len(caller_parts) >= 3 and len(callee_parts) >= 3:
            if caller_parts[:-1] == callee_parts[:-1]:  # Same class
                score += 0.2

    # 2. Package locality - functions in the same package hierarchy
    elif "." in module_qn:
        package = module_qn.rsplit(".", 1)[0]
        if callee_qn.startswith(package + "."):
            score += 0.3

    # 3. Object/class match for method calls
    if object_name:
        # Check if callee is a method of a class matching the object name
        callee_parts = callee_qn.split(".")
        if len(callee_parts) >= 2:
            # Simple heuristic: check if class name matches object name
            # (In reality, we'd need type inference for accuracy)
            class_name = callee_parts[-2]
            if class_name.lower() == object_name.lower():
                score += 0.3
            elif object_name == "self" and callee_qn.startswith(
                caller_qn.rsplit(".", 1)[0]
            ):
                # 'self' refers to the same class
                score += 0.4

    # 4. Standard library boost
    # Give a small boost to standard library functions
    if callee_qn.startswith(("builtins.", "typing.", "collections.")):
        score += 0.1

    # 5. Name uniqueness boost
    # If function names are unique enough, boost confidence
    callee_simple_name = callee_qn.split(".")[-1]
    possible_matches = simple_name_lookup.get(callee_simple_name, [])
    possible_count = len(possible_matches)
    if possible_count == 1:
        score += 0.2
    elif possible_count <= 3:
        score += 0.1

    # Normalize to [0, 1]
    return min(score, 1.0)
