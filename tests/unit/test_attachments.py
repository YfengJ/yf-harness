from __future__ import annotations

from pathlib import Path

import pytest

from yfharness.core.attachments import image_data_url, prepare_image
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
