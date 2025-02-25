class FilterNotSupportedException(Exception):
    def __str__(self):
        return (
            f"Filter doesn't support given field type: "
            f"{self.args[0] if self.args else 'not specified'}"
        )
