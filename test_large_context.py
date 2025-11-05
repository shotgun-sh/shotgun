#!/usr/bin/env python3
"""Test script to verify error behavior with extremely large context.

This is NOT a unit test - it's exploratory code to verify what errors
each token counting method raises with oversized context.

Run with: uv run python test_large_context.py
"""

import asyncio


def generate_large_text(target_tokens: int = 1_000_000) -> str:
    """Generate text that should exceed any model's context limit.

    Args:
        target_tokens: Approximate number of tokens to generate

    Returns:
        Very large text string
    """
    # Average ~4 characters per token, so multiply by 4
    base_text = "This is a test sentence with various words to simulate real content. " * 100
    repetitions = (target_tokens * 4) // len(base_text)
    return base_text * repetitions


async def test_tiktoken():
    """Test tiktoken (OpenAI) with extremely large context."""
    print("\n" + "=" * 80)
    print("TESTING TIKTOKEN (OpenAI)")
    print("=" * 80)

    try:
        import tiktoken

        # Generate text that should be ~1M tokens (way over any model's limit)
        large_text = generate_large_text(1_000_000)
        print(f"Generated text length: {len(large_text):,} characters")
        print(f"Estimated tokens: ~{len(large_text) // 4:,}")

        # Try to count tokens
        encoding = tiktoken.get_encoding("o200k_base")
        print("\nAttempting to count tokens...")

        token_count = len(encoding.encode(large_text))
        print(f"✅ SUCCESS! Counted {token_count:,} tokens")
        print("   Note: tiktoken does NOT raise an error for large context")

    except Exception as e:
        print(f"❌ EXCEPTION: {type(e).__name__}")
        print(f"   Message: {str(e)}")
        print(f"   Type hierarchy: {[c.__name__ for c in type(e).__mro__]}")
    except BaseException as e:
        print(f"❌ BASE EXCEPTION (not caught by except Exception): {type(e).__name__}")
        print(f"   Message: {str(e)}")
        print(f"   Type hierarchy: {[c.__name__ for c in type(e).__mro__]}")


async def test_sentencepiece():
    """Test SentencePiece (Gemini) with extremely large context."""
    print("\n" + "=" * 80)
    print("TESTING SENTENCEPIECE (Gemini)")
    print("=" * 80)

    try:
        # Generate large text
        large_text = generate_large_text(1_000_000)
        print(f"Generated text length: {len(large_text):,} characters")
        print(f"Estimated tokens: ~{len(large_text) // 4:,}")

        # Use the SentencePieceTokenCounter class directly
        from shotgun.agents.history.token_counting.sentencepiece_counter import (
            SentencePieceTokenCounter,
        )

        print("\nInitializing SentencePiece counter...")
        counter = SentencePieceTokenCounter("gemini-2.0-flash-exp")

        print("Attempting to count tokens...")
        token_count = await counter.count_tokens(large_text)

        print(f"✅ SUCCESS! Counted {token_count:,} tokens")
        print("   Note: SentencePiece does NOT raise an error for large context")

    except Exception as e:
        print(f"❌ EXCEPTION: {type(e).__name__}")
        print(f"   Message: {str(e)}")
        print(f"   Type hierarchy: {[c.__name__ for c in type(e).__mro__]}")


async def test_anthropic_api():
    """Test Anthropic API with extremely large context."""
    print("\n" + "=" * 80)
    print("TESTING ANTHROPIC API (Claude)")
    print("=" * 80)

    try:
        import os

        from anthropic import AsyncAnthropic

        # Check if we have an API key
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("⚠️  SKIPPED: No Anthropic API key configured")
            print("   Set ANTHROPIC_API_KEY environment variable to test")
            print("\n📝 Based on documentation:")
            print("   - Anthropic API enforces a 32 MB request size limit")
            print("   - This would raise APIStatusError with status_code=413")
            print("   - But it does NOT validate token count limits")
            print("   - Token limits are checked when creating messages, not counting")
            return

        client = AsyncAnthropic(api_key=api_key)

        # Test 1: Large text under 32MB (should succeed)
        print("\n[Test 1: Large text under 32 MB limit]")
        large_text = generate_large_text(1_000_000)
        print(f"Generated text length: {len(large_text):,} characters (~{len(large_text) / (1024*1024):.1f} MB)")
        print(f"Estimated tokens: ~{len(large_text) // 4:,}")

        print("Attempting to count tokens via Anthropic API...")
        result = await client.messages.count_tokens(
            messages=[{"role": "user", "content": large_text}],
            model="claude-sonnet-4-20250514",
        )

        print(f"✅ SUCCESS! API returned {result.input_tokens:,} tokens")
        print("   Note: Anthropic API counts tokens, doesn't validate token limits")

        # Test 2: Try to hit the 32 MB limit (should fail with 413)
        print("\n[Test 2: Text over 32 MB limit]")
        # Generate ~35 MB of text
        huge_text = "x" * (35 * 1024 * 1024)
        print(f"Generated text length: {len(huge_text):,} characters (~{len(huge_text) / (1024*1024):.1f} MB)")

        print("Attempting to count tokens for 35 MB text...")
        result = await client.messages.count_tokens(
            messages=[{"role": "user", "content": huge_text}],
            model="claude-sonnet-4-20250514",
        )
        print(f"✅ SUCCESS! API returned {result.input_tokens:,} tokens")
        print("   Note: Either 32 MB limit is per-request, not per-message content")

    except Exception as e:
        print(f"❌ EXCEPTION: {type(e).__name__}")
        print(f"   Message: {str(e)}")
        print(f"   Type hierarchy: {[c.__name__ for c in type(e).__mro__]}")

        # Check if it's an APIStatusError to get the status code
        if hasattr(e, 'status_code'):
            print(f"   HTTP Status Code: {e.status_code}")
            if e.status_code == 413:
                print("   ✅ This is the expected 413 'request_too_large' error!")
        if hasattr(e, 'response'):
            print(f"   Response body: {getattr(e.response, 'text', 'N/A')}")


async def test_all():
    """Run all tests."""
    print("\n" + "#" * 80)
    print("# TESTING TOKEN COUNTING WITH EXTREMELY LARGE CONTEXT")
    print("#" * 80)
    print("\nThis script tests what happens when we try to count tokens")
    print("for text that FAR EXCEEDS any model's context limit.")
    print("\nExpected result: Token counting should SUCCEED (no errors)")
    print("because counting ≠ validation. Validation happens separately.")

    await test_tiktoken()
    await test_sentencepiece()
    await test_anthropic_api()

    print("\n" + "#" * 80)
    print("# SUMMARY")
    print("#" * 80)
    print("\nKey findings:")
    print("1. Token counting libraries/APIs do NOT enforce context limits")
    print("2. They just count tokens - validation is separate")
    print("3. Errors come from file I/O, network issues, or API problems")
    print("4. Context size validation must be done by comparing count to max_input_tokens")
    print("\n")


if __name__ == "__main__":
    asyncio.run(test_all())
