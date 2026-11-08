"""Tests for the OOP IOManager. Run with: python test_io_manager.py"""

from unittest.mock import patch

from io_manager import ConsoleChannel, IOChannel


def check(label, actual, expected):
    assert actual == expected, f"{label}: expected {expected!r}, got {actual!r}"
    print("PASS:", label)


def test_channel_interface():
    try:
        IOChannel()
        raise AssertionError("IOChannel should be abstract")
    except TypeError:
        print("PASS: IOChannel is now abstract hence cannot be created directly")

    channel = ConsoleChannel()
    with patch("builtins.input", return_value="hello") as fake_input:
        check("ConsoleChannel.read returns typed text", channel.read("Q: "), "hello")
        fake_input.assert_called_once_with("Q: ")
    with patch("builtins.print") as fake_print:
        channel.write("hi")
        fake_print.assert_called_once_with("hi")


if __name__ == "__main__":
    test_channel_interface()
    print("\nAll IOManager tests passed!")