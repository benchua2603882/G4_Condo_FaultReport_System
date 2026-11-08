"""Tests for the OOP IOManager. Run with: python test_io_manager.py"""

from unittest.mock import patch

from io_manager import (
    ConsoleChannel, IOChannel,
    NameValidator, PhoneValidator, RequiredTextValidator,
)

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

def test_validators_polymorphism():
    """Every validator is used the same way: clean() or ValueError."""
    cases = [
        (NameValidator(), "  Test Resident  ", "Test Resident", "Resident123"),
        (PhoneValidator(), "  +6500123456  ", "+6500123456", "++65"),
        (RequiredTextValidator(), "  leak  ", "leak", "   "),
    ]
    for validator, good_raw, good_clean, bad_raw in cases:
        name = type(validator).__name__
        check(f"{name} accepts and trims", validator.clean(good_raw), good_clean)
        try:
            validator.clean(bad_raw)
            raise AssertionError(f"{name} accepted bad input")
        except ValueError as error:
            check(f"{name} rejects bad input", str(error), validator.error_message)

if __name__ == "__main__":
    test_channel_interface()
    test_validators_polymorphism()
    print("\nAll IOManager tests passed!")