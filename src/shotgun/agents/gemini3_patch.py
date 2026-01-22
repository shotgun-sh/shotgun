"""Monkey-patch for pydantic-ai Gemini 3 tool call bug.

Issue: When Gemini 3 returns a tool call via the Responses API, LiteLLM returns
a ResponseOutputMessage with content that has `text: null`. Pydantic-ai creates
a TextPart with content=None, which later crashes when agent code tries to
concatenate it.

Bug location in pydantic-ai 1.44.0:
- pydantic_ai/models/openai.py line 1323:
  `items.append(TextPart(content.text, id=item.id, ...))`
  This doesn't check if content.text is None.

This patch fixes the issue by monkey-patching the _process_response method
to skip TextParts when content.text is None.

Apply this patch early in application startup before any agents are created.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

_patch_applied = False


def apply_gemini3_patch() -> bool:
    """Apply the monkey-patch for Gemini 3 tool call content=None bug.

    This patches OpenAIResponsesModel._process_response to skip creating
    TextParts when the response content text is None.

    Returns:
        True if patch was applied, False if already applied or failed.
    """
    global _patch_applied

    if _patch_applied:
        logger.debug("Gemini 3 patch already applied")
        return False

    try:
        from pydantic_ai.models.openai import OpenAIResponsesModel

        # Store the original method
        original_process_response = OpenAIResponsesModel._process_response

        def patched_process_response(
            self: Any, response: Any, model_request_parameters: Any
        ) -> Any:
            """Patched _process_response that filters out TextParts with None content."""
            # Call the original method
            model_response = original_process_response(
                self, response, model_request_parameters
            )

            # Filter out any TextParts with None content
            from pydantic_ai.messages import TextPart

            filtered_parts = [
                part
                for part in model_response.parts
                if not (isinstance(part, TextPart) and part.content is None)
            ]

            # Only update if we actually filtered something
            if len(filtered_parts) != len(model_response.parts):
                logger.debug(
                    f"Gemini 3 patch: Filtered {len(model_response.parts) - len(filtered_parts)} "
                    "TextPart(s) with None content"
                )
                # Create a new ModelResponse with filtered parts
                from dataclasses import replace

                model_response = replace(model_response, parts=filtered_parts)

            return model_response

        # Apply the patch
        OpenAIResponsesModel._process_response = patched_process_response  # type: ignore[method-assign]
        logger.info("Applied Gemini 3 patch to OpenAIResponsesModel._process_response")
        _patch_applied = True
        return True

    except Exception as e:
        logger.error(f"Failed to apply Gemini 3 patch: {e}")
        return False
