"""Unit tests for agents.tools.user_interaction module."""

from unittest.mock import Mock, patch

from shotgun.agents.tools.user_interaction import ask_user


class TestAskUser:
    """Test suite for ask_user function."""

    def test_successful_user_input(self):
        """Test successful user input handling."""
        mock_stdin = Mock()
        mock_stdin.readline.return_value = "  yes, please  \n"

        with patch("shotgun.agents.tools.user_interaction.sys.stdin", mock_stdin):
            result = ask_user("Do you want to proceed?")

            assert result == "yes, please"
            mock_stdin.readline.assert_called_once()

    def test_empty_user_input(self):
        """Test handling of empty user input."""
        mock_stdin = Mock()
        mock_stdin.readline.return_value = "\n"

        with patch("shotgun.agents.tools.user_interaction.sys.stdin", mock_stdin):
            result = ask_user("Enter something:")

            assert result == ""
            mock_stdin.readline.assert_called_once()

    def test_whitespace_only_input(self):
        """Test handling of whitespace-only input."""
        mock_stdin = Mock()
        mock_stdin.readline.return_value = "   \t  \n"

        with patch("shotgun.agents.tools.user_interaction.sys.stdin", mock_stdin):
            result = ask_user("Enter text:")

            assert result == ""
            mock_stdin.readline.assert_called_once()

    def test_multiline_input_first_line_only(self):
        """Test that only first line is returned from multiline input."""
        mock_stdin = Mock()
        mock_stdin.readline.return_value = "first line\nsecond line\n"

        with patch("shotgun.agents.tools.user_interaction.sys.stdin", mock_stdin):
            result = ask_user("Enter text:")

            # Only the first line should be returned, stripped
            assert result == "first line\nsecond line"

    def test_eof_error_handling(self):
        """Test handling of EOFError (Ctrl+D on Unix)."""
        mock_stdin = Mock()
        mock_stdin.readline.side_effect = EOFError("End of file")

        with patch("shotgun.agents.tools.user_interaction.sys.stdin", mock_stdin):
            result = ask_user("Enter something:")

            assert result == "User input not available or interrupted"
            mock_stdin.readline.assert_called_once()

    def test_keyboard_interrupt_handling(self):
        """Test handling of KeyboardInterrupt (Ctrl+C)."""
        mock_stdin = Mock()
        mock_stdin.readline.side_effect = KeyboardInterrupt("Interrupted")

        with patch("shotgun.agents.tools.user_interaction.sys.stdin", mock_stdin):
            result = ask_user("Enter something:")

            assert result == "User input not available or interrupted"
            mock_stdin.readline.assert_called_once()

    def test_question_logging(self):
        """Test that the question is logged properly."""
        mock_stdin = Mock()
        mock_stdin.readline.return_value = "response\n"

        with (
            patch("shotgun.agents.tools.user_interaction.sys.stdin", mock_stdin),
            patch("shotgun.agents.tools.user_interaction.logger") as mock_logger,
        ):
            question = "What is your favorite color?"
            result = ask_user(question)

            assert result == "response"
            # Check that question was logged
            mock_logger.info.assert_any_call("\n👉 %s\n", question)
            # Check that thanks message was logged
            mock_logger.info.assert_any_call(" Thanks!\n")
            # Check that debug message was logged
            mock_logger.debug.assert_called_once_with(
                "User response received: %s", "response"
            )

    def test_exception_logging(self):
        """Test that exceptions are logged properly."""
        mock_stdin = Mock()
        mock_stdin.readline.side_effect = EOFError("Test EOF")

        with (
            patch("shotgun.agents.tools.user_interaction.sys.stdin", mock_stdin),
            patch("shotgun.agents.tools.user_interaction.logger") as mock_logger,
        ):
            result = ask_user("Test question")

            assert result == "User input not available or interrupted"
            mock_logger.warning.assert_called_once_with(
                "User input interrupted or unavailable"
            )

    def test_special_characters_in_input(self):
        """Test handling of special characters in user input."""
        special_inputs = [
            "Hello! @#$%^&*()",
            "émojis 🚀 and unicode",
            "line with\ttabs",
            "\"quotes\" and 'apostrophes'",
            "<html>tags</html>",
            "newlines\nand\rcarriage returns",
        ]

        for special_input in special_inputs:
            mock_stdin = Mock()
            mock_stdin.readline.return_value = f"  {special_input}  \n"

            with patch("shotgun.agents.tools.user_interaction.sys.stdin", mock_stdin):
                result = ask_user("Enter special text:")

                assert result == special_input
                mock_stdin.readline.assert_called_once()

    def test_very_long_input(self):
        """Test handling of very long user input."""
        long_input = "A" * 10000  # Very long string
        mock_stdin = Mock()
        mock_stdin.readline.return_value = f"{long_input}\n"

        with patch("shotgun.agents.tools.user_interaction.sys.stdin", mock_stdin):
            result = ask_user("Enter long text:")

            assert result == long_input
            assert len(result) == 10000

    def test_different_question_types(self):
        """Test with different types of questions."""
        questions_and_responses = [
            ("Yes or no?", "yes"),
            ("Enter a number:", "42"),
            ("What's your name?", "Alice"),
            ("🤔 Unicode question?", "Unicode answer! 🎉"),
            ("", "response to empty question"),
            ("Multi\nline\nquestion?", "multiline response"),
        ]

        for question, expected_response in questions_and_responses:
            mock_stdin = Mock()
            mock_stdin.readline.return_value = f"{expected_response}\n"

            with patch("shotgun.agents.tools.user_interaction.sys.stdin", mock_stdin):
                result = ask_user(question)

                assert result == expected_response


class TestIntegrationScenarios:
    """Integration test scenarios for user interaction."""

    def test_realistic_conversation_flow(self):
        """Test a realistic conversation flow with multiple questions."""
        conversation = [
            ("What's your name?", "John Doe"),
            ("What would you like to do?", "create a project"),
            ("Are you sure? (y/n)", "y"),
            ("Any additional comments?", ""),
        ]

        responses = []
        for question, expected_response in conversation:
            mock_stdin = Mock()
            mock_stdin.readline.return_value = f"{expected_response}\n"

            with patch("shotgun.agents.tools.user_interaction.sys.stdin", mock_stdin):
                actual_response = ask_user(question)
                responses.append((question, actual_response, expected_response))

        # Verify all responses match
        for question, actual, expected in responses:
            assert actual == expected, f"Question: {question}"

    def test_error_recovery_scenarios(self):
        """Test error recovery in various scenarios."""
        error_scenarios = [
            (EOFError("stdin closed"), "User input not available or interrupted"),
            (
                KeyboardInterrupt("user cancelled"),
                "User input not available or interrupted",
            ),
        ]

        for exception, expected_response in error_scenarios:
            mock_stdin = Mock()
            mock_stdin.readline.side_effect = exception

            with patch("shotgun.agents.tools.user_interaction.sys.stdin", mock_stdin):
                result = ask_user("This will fail:")

                assert result == expected_response
