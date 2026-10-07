"""Input validation tests"""

import sys
from unittest.mock import patch

import io_manager


def test_input_validation():
    """Check that contact validation rejects bad input and preserves accepted text."""

    with patch("builtins.input", side_effect=[" ", "Resident123", "Test Resident"]), patch("builtins.print"):
        assert io_manager.collect_name() == "Test Resident"
    with patch("builtins.input", side_effect=["", "+", "++65", "１２３", "abc", "+6500123456"]), patch("builtins.print"):
        assert io_manager.collect_phone_number() == "+6500123456"


if __name__ == "__main__":
    test_input_validation()
    sys.stdout.write("PASS: test_input_validation\n")
