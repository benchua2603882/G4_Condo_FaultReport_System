"""Tests for the OOP IOManager. Run with: python test_io_manager.py"""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from io_manager import (
    ConsoleChannel, IOChannel, ImagePathCollector, NameValidator,
    PhoneValidator, RequiredTextValidator, ValidatedPrompter,
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

class FakeChannel(IOChannel):
    """Plays back scripted answers and records everything shown to the user."""

    def __init__(self, answers=()):
        self._answers = list(answers)
        self.output = []

    def read(self, prompt=""):
        self.output.append(prompt)
        return self._answers.pop(0)

    def read_secret(self, prompt=""):
        self.output.append(prompt)
        return self._answers.pop(0)

    def write(self, message=""):
        self.output.append(str(message))


def test_prompter_retries():
    channel = FakeChannel([" ", "Resident123", "  Test Resident  "])
    prompter = ValidatedPrompter(channel)
    check("name retried then trimmed", prompter.ask("Name? ", NameValidator()), "Test Resident")
    check("two error messages shown",
          channel.output.count(NameValidator().error_message), 2)

    prompter = ValidatedPrompter(FakeChannel(["", "abc", "++65", "１２３", "  +6500123456  "]))
    check("phone retried, plus and zeros kept",
          prompter.ask("Phone? ", PhoneValidator()), "+6500123456")


def test_image_path_collector():
    with TemporaryDirectory() as folder:
        (Path(folder) / "leak.png").write_bytes(b"x")
        (Path(folder) / "note.txt").write_text("x")

        answers = ["maybe", "y", "", "missing.png", "note.txt", "leak.png"]
        collector = ImagePathCollector(FakeChannel(answers), project_folder=Path(folder))
        expected = str((Path(folder) / "leak.png").resolve())
        check("retries bad answers and returns absolute path", collector.collect(), expected)

        collector = ImagePathCollector(FakeChannel(["N"]), project_folder=Path(folder))
        check("N returns no_image", collector.collect(), "no_image")

if __name__ == "__main__":
    test_channel_interface()
    test_validators_polymorphism()
    test_prompter_retries()
    test_image_path_collector()
    print("\nAll IOManager tests passed!")