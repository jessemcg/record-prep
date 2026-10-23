"""Explicit completion receipt for in-place text processing.

Raw text is an extraction output, not proof that normalization ran. The receipt
is published only after all pages and the layout rebind succeed. It is portable
with the bundle and deliberately independent of model/settings freshness.
"""
import os
from pathlib import Path
import tempfile


RECEIPT = "artifacts/text_processing.complete"


def invalidate(root: Path) -> None:
    (root / RECEIPT).unlink(missing_ok=True)


def publish(root: Path) -> None:
    target = root / RECEIPT
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                                     prefix=".text-processing-", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write("Process text files completed successfully.\n")
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
