DATASETS = ("deputies", "votings", "votes", "histories", "topics")


DEPENDENCIES = {"votes": ("votings",), "topics": ("votings",)}


TERMINAL = {"completed", "completed_with_errors", "failed", "cancelled"}


def resolve_datasets(selected: list[str]) -> list[str]:
    if not selected or any(item not in DATASETS for item in selected):
        raise ValueError("Select at least one supported dataset.")
    resolved = set(selected)
    for item in selected:
        resolved.update(DEPENDENCIES.get(item, ()))
    if "histories" in resolved and "votes" not in resolved:
        resolved.add("deputies")
    return [item for item in DATASETS if item in resolved]
