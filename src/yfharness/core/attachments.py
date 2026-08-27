"""Validated local attachments with an explicit remote-transfer boundary."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from yfharness.core.exceptions import HarnessError
from yfharness.core.models import AttachmentTransfer, ContentPart, ContentPartType
from yfharness.tools.security import WorkspaceGuard

MAX_IMAGE_BYTES = 10 * 1024 * 1024
_IMAGE_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def prepare_image(
    value: str | Path,
    guard: WorkspaceGuard,
    *,
    send_to_model: bool,
) -> ContentPart:
    path = guard.resolve(value, must_exist=True)
    if not path.is_file():
        raise HarnessError(f"图片附件不是文件: {guard.relative(path)}")
    data = path.read_bytes()
    if len(data) > MAX_IMAGE_BYTES:
        raise HarnessError(f"图片附件超过 {MAX_IMAGE_BYTES // (1024 * 1024)} MiB 限制")
    mime_type = _image_mime(data)
    if mime_type is None:
        raise HarnessError("仅支持 PNG、JPEG、GIF 或 WebP 图片")
    return ContentPart(
        type=ContentPartType.IMAGE,
        path=str(path),
        mime_type=mime_type,
        transfer=(
            AttachmentTransfer.REMOTE_MODEL if send_to_model else AttachmentTransfer.LOCAL_ONLY
        ),
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )


def image_data_url(part: ContentPart) -> str:
    if part.type is not ContentPartType.IMAGE:
        raise HarnessError("附件不是图片")
    if part.transfer is not AttachmentTransfer.REMOTE_MODEL:
        raise HarnessError("附件未授权发送给远程模型")
    if part.path is None or part.mime_type is None or part.sha256 is None:
        raise HarnessError("附件元数据不完整")
    path = Path(part.path)
    data = path.read_bytes()
    if len(data) != part.size_bytes or hashlib.sha256(data).hexdigest() != part.sha256:
        raise HarnessError("图片附件在准备后已发生变化，已拒绝上传")
    if _image_mime(data) != part.mime_type:
        raise HarnessError("图片附件类型与内容不匹配")
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{part.mime_type};base64,{encoded}"


def _image_mime(data: bytes) -> str | None:
    for signature, mime_type in _IMAGE_SIGNATURES:
        if data.startswith(signature):
            return mime_type
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None
