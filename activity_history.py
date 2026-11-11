from copy import deepcopy
from datetime import datetime


class ActivityHistory:
    """Build history from saved values; drafts cannot replace previous entries."""

    def changes_between(self, original, updated):
        """Return old/new values for changed contact, fault and analysis fields."""
        fields = ("name", "phone_number", "description", "image_path")
        changes = {}
        for index, field in enumerate(fields, 1):
            if original[index] != updated[index]:
                changes[field] = {"old": original[index], "new": updated[index]}
        for field in sorted(set(original[6]) | set(updated[6])):
            if field != "history" and original[6].get(field) != updated[6].get(field):
                changes[field] = {"old": original[6].get(field), "new": updated[6].get(field)}
        return deepcopy(changes)

print("hello")