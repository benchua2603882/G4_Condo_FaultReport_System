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

    def record(self, report, action, actor, changes, previous=None):
            """Return a copy with one timestamped event, preserve saved history."""
            history = previous[6].get("history", []) if previous is not None else []
            if not isinstance(history, list) or any(not isinstance(entry, dict) for entry in history):
                raise ValueError("The stored complaint history is invalid.")
            result = deepcopy(report)
            result[6]["history"] = deepcopy(history) + [{
                "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
                "action": action,
                "actor": actor,
                "changes": deepcopy(changes),
            }]
            return result

print("hello")