"""Unit tests for agents.tools.web_search module."""

from unittest.mock import Mock, patch

from shotgun.agents.tools.web_search import openai_web_search_tool


class TestWebSearchTool:
    """Test suite for web_search_tool function."""

    def test_successful_search(self):
        """Test successful web search execution."""
        mock_response = Mock()
        mock_response.output_text = "Search results about Python programming"

        mock_client = Mock()
        mock_client.responses.create.return_value = mock_response

        mock_model_config = Mock()
        mock_model_config.api_key = "test-api-key"

        with (
            patch(
                "shotgun.agents.tools.web_search.openai.get_provider_model"
            ) as mock_get_provider,
            patch("shotgun.agents.tools.web_search.openai.OpenAI") as mock_openai,
            patch("shotgun.agents.tools.web_search.openai.trace") as mock_trace,
        ):
            mock_get_provider.return_value = mock_model_config
            mock_openai.return_value = mock_client
            mock_span = Mock()
            mock_trace.get_current_span.return_value = mock_span

            result = openai_web_search_tool("Python programming tutorial")

            assert result == "Search results about Python programming"
            mock_client.responses.create.assert_called_once()
            mock_span.set_attribute.assert_called()
            mock_openai.assert_called_once_with(api_key="test-api-key")

    def test_empty_search_results(self):
        """Test handling of empty search results."""
        mock_response = Mock()
        mock_response.output_text = None

        mock_client = Mock()
        mock_client.responses.create.return_value = mock_response

        mock_model_config = Mock()
        mock_model_config.api_key = "test-api-key"

        with (
            patch(
                "shotgun.agents.tools.web_search.openai.get_provider_model"
            ) as mock_get_provider,
            patch("shotgun.agents.tools.web_search.openai.OpenAI") as mock_openai,
            patch("shotgun.agents.tools.web_search.openai.trace") as mock_trace,
        ):
            mock_get_provider.return_value = mock_model_config
            mock_openai.return_value = mock_client
            mock_span = Mock()
            mock_trace.get_current_span.return_value = mock_span

            result = openai_web_search_tool("nonexistent topic")

            assert result == "No content returned"
            mock_client.responses.create.assert_called_once()

    def test_blank_search_results(self):
        """Test handling of blank search results."""
        mock_response = Mock()
        mock_response.output_text = ""

        mock_client = Mock()
        mock_client.responses.create.return_value = mock_response

        mock_model_config = Mock()
        mock_model_config.api_key = "test-api-key"

        with (
            patch(
                "shotgun.agents.tools.web_search.openai.get_provider_model"
            ) as mock_get_provider,
            patch("shotgun.agents.tools.web_search.openai.OpenAI") as mock_openai,
            patch("shotgun.agents.tools.web_search.openai.trace") as mock_trace,
        ):
            mock_get_provider.return_value = mock_model_config
            mock_openai.return_value = mock_client
            mock_span = Mock()
            mock_trace.get_current_span.return_value = mock_span

            result = openai_web_search_tool("empty results")

            assert result == "No content returned"

    def test_openai_api_error(self):
        """Test handling of OpenAI API errors."""
        mock_client = Mock()
        mock_client.responses.create.side_effect = Exception("API rate limit exceeded")

        mock_model_config = Mock()
        mock_model_config.api_key = "test-api-key"

        with (
            patch(
                "shotgun.agents.tools.web_search.openai.get_provider_model"
            ) as mock_get_provider,
            patch("shotgun.agents.tools.web_search.openai.OpenAI") as mock_openai,
            patch("shotgun.agents.tools.web_search.openai.trace") as mock_trace,
        ):
            mock_get_provider.return_value = mock_model_config
            mock_openai.return_value = mock_client
            mock_span = Mock()
            mock_trace.get_current_span.return_value = mock_span

            result = openai_web_search_tool("search query")

            assert "Error performing web search" in result
            assert "API rate limit exceeded" in result
            mock_span.set_attribute.assert_called()

    def test_openai_client_creation_error(self):
        """Test handling of OpenAI client creation errors."""
        mock_model_config = Mock()
        mock_model_config.api_key = "test-api-key"

        with (
            patch(
                "shotgun.agents.tools.web_search.openai.get_provider_model"
            ) as mock_get_provider,
            patch("shotgun.agents.tools.web_search.openai.OpenAI") as mock_openai,
            patch("shotgun.agents.tools.web_search.openai.trace") as mock_trace,
        ):
            mock_get_provider.return_value = mock_model_config
            mock_openai.side_effect = Exception("Invalid API key")
            mock_span = Mock()
            mock_trace.get_current_span.return_value = mock_span

            result = openai_web_search_tool("test query")

            assert "Error performing web search" in result
            assert "Invalid API key" in result

    def test_correct_api_parameters(self):
        """Test that correct parameters are passed to OpenAI API with formatted prompt."""
        mock_response = Mock()
        mock_response.output_text = "Results"

        mock_client = Mock()
        mock_client.responses.create.return_value = mock_response

        mock_model_config = Mock()
        mock_model_config.api_key = "test-api-key"

        with (
            patch(
                "shotgun.agents.tools.web_search.openai.get_provider_model"
            ) as mock_get_provider,
            patch("shotgun.agents.tools.web_search.openai.OpenAI") as mock_openai,
            patch("shotgun.agents.tools.web_search.openai.trace") as mock_trace,
        ):
            mock_get_provider.return_value = mock_model_config
            mock_openai.return_value = mock_client
            mock_span = Mock()
            mock_trace.get_current_span.return_value = mock_span

            query = "Python web frameworks"
            openai_web_search_tool(query)

            # Verify the API call parameters
            call_args = mock_client.responses.create.call_args
            assert call_args is not None

            kwargs = call_args.kwargs
            assert kwargs["model"] == "gpt-5-mini"
            assert kwargs["store"] is False

            # Check input structure
            assert "input" in kwargs
            input_data = kwargs["input"]
            assert len(input_data) == 1
            assert input_data[0]["role"] == "user"

            # Verify the formatted prompt contains the query and instructions
            passed_prompt = input_data[0]["content"][0]["text"]
            assert query in passed_prompt
            assert "Please provide current and accurate information" in passed_prompt
            assert "Query: " + query in passed_prompt

            # Check tools configuration
            assert "tools" in kwargs
            tools = kwargs["tools"]
            assert len(tools) == 1
            assert tools[0]["type"] == "web_search"
            assert tools[0]["user_location"]["type"] == "approximate"
            assert tools[0]["search_context_size"] == "high"  # Updated from low

    def test_telemetry(self):
        """Test telemetry integration."""
        mock_response = Mock()
        mock_response.output_text = "Search results"

        mock_client = Mock()
        mock_client.responses.create.return_value = mock_response

        mock_model_config = Mock()
        mock_model_config.api_key = "test-api-key"

        with (
            patch(
                "shotgun.agents.tools.web_search.openai.get_provider_model"
            ) as mock_get_provider,
            patch("shotgun.agents.tools.web_search.openai.OpenAI") as mock_openai,
            patch("shotgun.agents.tools.web_search.openai.trace") as mock_trace,
        ):
            mock_get_provider.return_value = mock_model_config
            mock_openai.return_value = mock_client
            mock_span = Mock()
            mock_trace.get_current_span.return_value = mock_span

            query = "test search"
            result = openai_web_search_tool(query)

            # Verify telemetry span attributes
            expected_calls = [
                ("input.value", f"**Query:** {query}\n"),
                ("output.value", f"**Results:**\n {result}\n"),
            ]

            for attr_name, attr_value in expected_calls:
                mock_span.set_attribute.assert_any_call(attr_name, attr_value)

    def test_error_telemetry(self):
        """Test error telemetry."""
        mock_client = Mock()
        error_message = "Connection timeout"
        mock_client.responses.create.side_effect = Exception(error_message)

        mock_model_config = Mock()
        mock_model_config.api_key = "test-api-key"

        with (
            patch(
                "shotgun.agents.tools.web_search.openai.get_provider_model"
            ) as mock_get_provider,
            patch("shotgun.agents.tools.web_search.openai.OpenAI") as mock_openai,
            patch("shotgun.agents.tools.web_search.openai.trace") as mock_trace,
        ):
            mock_get_provider.return_value = mock_model_config
            mock_openai.return_value = mock_client
            mock_span = Mock()
            mock_trace.get_current_span.return_value = mock_span

            query = "failing search"
            openai_web_search_tool(query)

            # Verify error telemetry
            mock_span.set_attribute.assert_any_call(
                "output.value",
                f"**Error:**\n Error performing web search: {error_message}\n",
            )

    def test_query_variations(self):
        """Test that various query formats are properly embedded in formatted prompts."""
        mock_response = Mock()
        mock_response.output_text = "Generic results"

        mock_client = Mock()
        mock_client.responses.create.return_value = mock_response

        mock_model_config = Mock()
        mock_model_config.api_key = "test-api-key"

        test_queries = [
            "simple query",
            "query with spaces and punctuation!",
            "🚀 emoji query",
            'query with "quotes"',
            "multi\nline\nquery",
            "very long query " * 50,
            "",  # empty query
            "query with special chars: @#$%^&*()",
            "unicode: café résumé naïve",
            "numbers: 123 456.789",
        ]

        with (
            patch(
                "shotgun.agents.tools.web_search.openai.get_provider_model"
            ) as mock_get_provider,
            patch("shotgun.agents.tools.web_search.openai.OpenAI") as mock_openai,
            patch("shotgun.agents.tools.web_search.openai.trace") as mock_trace,
        ):
            mock_get_provider.return_value = mock_model_config
            mock_openai.return_value = mock_client
            mock_span = Mock()
            mock_trace.get_current_span.return_value = mock_span

            for query in test_queries:
                result = openai_web_search_tool(query)
                assert result == "Generic results"

                # Verify the query was embedded correctly in the formatted prompt
                call_args = mock_client.responses.create.call_args
                passed_prompt = call_args.kwargs["input"][0]["content"][0]["text"]

                # Check that query is contained in the formatted prompt
                if query.strip():  # Skip assertion for empty query
                    assert query in passed_prompt
                    assert "Query: " + query in passed_prompt
                assert (
                    "Please provide current and accurate information" in passed_prompt
                )

    def test_long_search_results(self):
        """Test handling of very long search results."""
        long_result = "A" * 10000  # Very long result
        mock_response = Mock()
        mock_response.output_text = long_result

        mock_client = Mock()
        mock_client.responses.create.return_value = mock_response

        mock_model_config = Mock()
        mock_model_config.api_key = "test-api-key"

        with (
            patch(
                "shotgun.agents.tools.web_search.openai.get_provider_model"
            ) as mock_get_provider,
            patch("shotgun.agents.tools.web_search.openai.OpenAI") as mock_openai,
            patch("shotgun.agents.tools.web_search.openai.trace") as mock_trace,
        ):
            mock_get_provider.return_value = mock_model_config
            mock_openai.return_value = mock_client
            mock_span = Mock()
            mock_trace.get_current_span.return_value = mock_span

            result = openai_web_search_tool("test query")

            assert result == long_result
            assert len(result) == 10000


class TestIntegrationScenarios:
    """Integration test scenarios for web search."""

    def test_complete_search_workflow(self):
        """Test complete search workflow with realistic data and formatted prompts."""
        mock_response = Mock()
        mock_response.output_text = """
        Based on my search, here are the current Python web frameworks:

        1. **Django** - Full-featured framework with ORM
        2. **Flask** - Lightweight microframework
        3. **FastAPI** - Modern async framework
        4. **Tornado** - Async framework for real-time apps

        These are the most popular options as of 2024.
        """

        mock_client = Mock()
        mock_client.responses.create.return_value = mock_response

        mock_model_config = Mock()
        mock_model_config.api_key = "test-api-key"

        with (
            patch(
                "shotgun.agents.tools.web_search.openai.get_provider_model"
            ) as mock_get_provider,
            patch("shotgun.agents.tools.web_search.openai.OpenAI") as mock_openai,
            patch("shotgun.agents.tools.web_search.openai.trace") as mock_trace,
        ):
            mock_get_provider.return_value = mock_model_config
            mock_openai.return_value = mock_client
            mock_span = Mock()
            mock_trace.get_current_span.return_value = mock_span

            query = "current Python web frameworks 2024"
            result = openai_web_search_tool(query)

            assert "Django" in result
            assert "Flask" in result
            assert "FastAPI" in result
            assert "2024" in result

            # Verify proper API usage
            mock_client.responses.create.assert_called_once()
            call_kwargs = mock_client.responses.create.call_args.kwargs
            assert call_kwargs["model"] == "gpt-5-mini"

            # Verify the formatted prompt contains the query
            passed_prompt = call_kwargs["input"][0]["content"][0]["text"]
            assert query in passed_prompt
            assert "Please provide current and accurate information" in passed_prompt
            assert "Query: " + query in passed_prompt

    def test_error_recovery_scenarios(self):
        """Test various error recovery scenarios."""
        error_scenarios = [
            (ConnectionError("Network unavailable"), "Network unavailable"),
            (TimeoutError("Request timeout"), "Request timeout"),
            (KeyError("Missing API key"), "Missing API key"),
            (ValueError("Invalid model"), "Invalid model"),
            (RuntimeError("Service unavailable"), "Service unavailable"),
        ]

        mock_model_config = Mock()
        mock_model_config.api_key = "test-api-key"

        for exception, expected_error_text in error_scenarios:
            mock_client = Mock()
            mock_client.responses.create.side_effect = exception

            with (
                patch(
                    "shotgun.agents.tools.web_search.openai.get_provider_model"
                ) as mock_get_provider,
                patch("shotgun.agents.tools.web_search.openai.OpenAI") as mock_openai,
                patch("shotgun.agents.tools.web_search.openai.trace") as mock_trace,
            ):
                mock_get_provider.return_value = mock_model_config
                mock_openai.return_value = mock_client
                mock_span = Mock()
                mock_trace.get_current_span.return_value = mock_span

                result = openai_web_search_tool("test query")

                assert "Error performing web search" in result
                assert expected_error_text in result
