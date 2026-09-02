"""Validated local attachments with an explicit remote-transfer boundary."""

from __future__ import annotations

import base64
import hashlib
import mimetypes
from pathlib import Path

from yfharness.core.exceptions import HarnessError
from yfharness.core.models import AttachmentTransfer, ContentPart, ContentPartType
from yfharness.tools.security import WorkspaceGuard

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_FILE_BYTES = 200_000
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


def prepare_file(value: str | Path, guard: WorkspaceGuard) -> ContentPart:
    """Validate a local UTF-8 file for bounded context inclusion."""

    path = guard.resolve(value, must_exist=True)
    if not path.is_file():
        raise HarnessError(f"文件附件不是文件: {guard.relative(path)}")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise HarnessError(f"文件附件超过 {MAX_FILE_BYTES // 1000} KB 限制")
    data = path.read_bytes()
    _validate_file_data(data)
    mime_type = mimetypes.guess_type(path.name)[0] or "text/plain"
    return ContentPart(
        type=ContentPartType.FILE,
        path=str(path),
        mime_type=mime_type,
        transfer=AttachmentTransfer.LOCAL_ONLY,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )


def file_context(part: ContentPart, guard: WorkspaceGuard) -> tuple[str, str]:
    """Return the exact verified path and text that may enter model context."""

    if part.type is not ContentPartType.FILE:
        raise HarnessError("附件不是普通文件")
    if part.transfer is not AttachmentTransfer.LOCAL_ONLY:
        raise HarnessError("普通文件只能作为本地上下文")
    if part.path is None or part.sha256 is None or part.size_bytes is None:
        raise HarnessError("文件附件元数据不完整")
    path = guard.resolve(part.path, must_exist=True)
    if not path.is_file():
        raise HarnessError("文件附件已不存在")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise HarnessError(f"文件附件超过 {MAX_FILE_BYTES // 1000} KB 限制")
    data = path.read_bytes()
    _validate_file_data(data)
    if len(data) != part.size_bytes or hashlib.sha256(data).hexdigest() != part.sha256:
        raise HarnessError("文件附件在准备后已发生变化，已拒绝读取")
    return guard.relative(path), data.decode("utf-8")


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


def _validate_file_data(data: bytes) -> None:
    if len(data) > MAX_FILE_BYTES:
        raise HarnessError(f"文件附件超过 {MAX_FILE_BYTES // 1000} KB 限制")
    if b"\x00" in data[:8192]:
        raise HarnessError("暂不支持二进制文件，请选择 UTF-8 文本文件")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HarnessError("暂不支持非 UTF-8 文件") from exc


def _image_mime(data: bytes) -> str | None:
    for signature, mime_type in _IMAGE_SIGNATURES:
        if data.startswith(signature):
            return mime_type
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None
