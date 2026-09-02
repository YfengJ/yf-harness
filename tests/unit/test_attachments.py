from __future__ import annotations

from pathlib import Path

import pytest

from yfharness.core.attachments import (
    MAX_FILE_BYTES,
    file_context,
    image_data_url,
    prepare_file,
    prepare_image,
)
from yfharness.core.exceptions import HarnessError
from yfharness.core.models import AttachmentTransfer, ContentPartType
from yfharness.tools.security import WorkspaceGuard

_PNG = b"\x89PNG\r\n\x1a\n" + b"test-payload"


def test_prepare_image_records_verified_metadata_and_transfer(tmp_path: Path) -> None:
    path = tmp_path / "sample.png"
    path.write_bytes(_PNG)

    part = prepare_image(path, WorkspaceGuard(tmp_path), send_to_model=True)

    assert part.type is ContentPartType.IMAGE
    assert part.transfer is AttachmentTransfer.REMOTE_MODEL
    assert part.mime_type == "image/png"
    assert part.size_bytes == len(_PNG)
    assert image_data_url(part).startswith("data:image/png;base64,")


def test_image_upload_rechecks_hash_and_workspace_boundary(tmp_path: Path) -> None:
    path = tmp_path / "sample.png"
    path.write_bytes(_PNG)
    part = prepare_image(path, WorkspaceGuard(tmp_path), send_to_model=True)
    path.write_bytes(_PNG + b"changed")

    with pytest.raises(HarnessError, match="已发生变化"):
        image_data_url(part)

    outside = tmp_path.parent / "outside-image.png"
    outside.write_bytes(_PNG)
    try:
        with pytest.raises(HarnessError):
            prepare_image(outside, WorkspaceGuard(tmp_path), send_to_model=False)
    finally:
        outside.unlink()


def test_prepare_image_rejects_extension_spoofing(tmp_path: Path) -> None:
    path = tmp_path / "fake.png"
    path.write_text("not an image", encoding="utf-8")

    with pytest.raises(HarnessError, match="仅支持"):
        prepare_image(path, WorkspaceGuard(tmp_path), send_to_model=True)


def test_prepare_file_records_local_context_metadata(tmp_path: Path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("真实项目说明", encoding="utf-8")

    part = prepare_file(path, WorkspaceGuard(tmp_path))

    assert part.type is ContentPartType.FILE
    assert part.transfer is AttachmentTransfer.LOCAL_ONLY
    assert part.mime_type == "text/markdown"
    assert file_context(part, WorkspaceGuard(tmp_path)) == ("notes.md", "真实项目说明")


def test_file_context_rejects_binary_oversized_changed_and_external_files(
    tmp_path: Path,
) -> None:
    binary = tmp_path / "archive.bin"
    binary.write_bytes(b"binary\x00payload")
    with pytest.raises(HarnessError, match="二进制"):
        prepare_file(binary, WorkspaceGuard(tmp_path))

    non_utf8 = tmp_path / "legacy.txt"
    non_utf8.write_bytes(b"\xff\xfe")
    with pytest.raises(HarnessError, match="非 UTF-8"):
        prepare_file(non_utf8, WorkspaceGuard(tmp_path))

    oversized = tmp_path / "large.txt"
    oversized.write_bytes(b"a" * (MAX_FILE_BYTES + 1))
    with pytest.raises(HarnessError, match="超过"):
        prepare_file(oversized, WorkspaceGuard(tmp_path))

    changed = tmp_path / "changed.txt"
    changed.write_text("before", encoding="utf-8")
    part = prepare_file(changed, WorkspaceGuard(tmp_path))
    changed.write_text("after", encoding="utf-8")
    with pytest.raises(HarnessError, match="已发生变化"):
        file_context(part, WorkspaceGuard(tmp_path))

    outside = tmp_path.parent / "outside-file.txt"
    outside.write_text("outside", encoding="utf-8")
    try:
        with pytest.raises(HarnessError):
            prepare_file(outside, WorkspaceGuard(tmp_path))
    finally:
        outside.unlink()
