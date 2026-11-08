import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from python_multipart import MultipartParser
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import parse_options_header

from vibicle_api.errors import reject
from vibicle_api.vehicle_schemas import revision_number

if TYPE_CHECKING:
    from python_multipart.multipart import MultipartCallbacks

FILE_LIMIT = 5 * 1024 * 1024
BODY_LIMIT = 6 * 1024 * 1024
MEDIA_FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}


@dataclass(frozen=True)
class Upload:
    expected: str
    media_type: str
    content: bytes


def boundary_for(content_type: str | None) -> bytes:
    media, options = parse_options_header(content_type or "")
    boundary = options.get(b"boundary", b"")
    if media != b"multipart/form-data":
        reject(415, "UNSUPPORTED_MEDIA_TYPE", "請使用 multipart/form-data。")
    if not re.fullmatch(rb"[a-zA-Z0-9'()+_,./:=? -]{1,70}", boundary) or boundary.endswith(b" "):
        reject(400, "MALFORMED_REQUEST", "Multipart Boundary 不正確。")
    return boundary


def parse_upload(body: bytes, boundary: bytes) -> Upload:
    fields: dict[bytes, bytes] = {}
    headers: dict[bytes, bytes] = {}
    name_buffer = bytearray()
    value_buffer = bytearray()
    content = bytearray()
    header_size = 0
    part_name = b""
    media_type = ""
    complete = False

    def part_begin() -> None:
        nonlocal header_size
        headers.clear()
        content.clear()
        header_size = 0

    def append_header(buffer: bytearray, data: bytes, start: int, end: int) -> None:
        nonlocal header_size
        header_size += end - start
        if header_size > 8192:
            reject(413, "PAYLOAD_TOO_LARGE", "上傳 Part Header 過大。")
        buffer.extend(data[start:end])

    def header_end() -> None:
        nonlocal header_size
        header_size += 4
        if header_size > 8192:
            reject(413, "PAYLOAD_TOO_LARGE", "上傳 Part Header 過大。")
        name = bytes(name_buffer).lower()
        if name in headers:
            reject(400, "DUPLICATE_FIELD", "上傳 Part Header 重複。")
        headers[name] = bytes(value_buffer)
        name_buffer.clear()
        value_buffer.clear()

    def headers_finished() -> None:
        nonlocal part_name, media_type
        kind, options = parse_options_header(headers.get(b"content-disposition"))
        part_name = options.get(b"name", b"")
        if part_name in fields:
            reject(400, "DUPLICATE_FIELD", "上傳欄位重複。")
        if kind != b"form-data" or part_name not in {b"file", b"expected_row_version"}:
            reject(422, "VALIDATION_FAILED", "上傳欄位不正確。")
        if part_name == b"file":
            if b"filename" not in options:
                reject(422, "VALIDATION_FAILED", "請提供一個照片檔案。")
            media, _ = parse_options_header(headers.get(b"content-type"))
            media_type = media.decode("ascii", errors="replace")
            if media_type not in MEDIA_FORMATS:
                reject(415, "IMAGE_MEDIA_TYPE_UNSUPPORTED", "請上傳 JPEG、PNG 或 WebP。")
        elif b"filename" in options:
            reject(422, "VALIDATION_FAILED", "版本必須是文字欄位。")

    def part_data(data: bytes, start: int, end: int) -> None:
        size = len(content) + end - start
        if part_name == b"file" and size > FILE_LIMIT:
            reject(413, "PAYLOAD_TOO_LARGE", "照片不可超過 5 MiB。")
        if part_name != b"file" and size > 19:
            reject(422, "VALIDATION_FAILED", "版本格式不正確。")
        content.extend(data[start:end])

    def part_end() -> None:
        fields[part_name] = bytes(content)

    def finish() -> None:
        nonlocal complete
        complete = True

    callbacks: MultipartCallbacks = {
        "on_part_begin": part_begin,
        "on_header_field": lambda data, start, end: append_header(name_buffer, data, start, end),
        "on_header_value": lambda data, start, end: append_header(value_buffer, data, start, end),
        "on_header_end": header_end,
        "on_headers_finished": headers_finished,
        "on_part_data": part_data,
        "on_part_end": part_end,
        "on_end": finish,
    }
    try:
        parser = MultipartParser(boundary, callbacks)
        parser.write(body)
        parser.finalize()
    except MultipartParseError:
        reject(400, "MALFORMED_REQUEST", "上傳格式不正確。")
    if not complete:
        reject(400, "MALFORMED_REQUEST", "上傳內容不完整。")
    if fields.keys() != {b"file", b"expected_row_version"} or not fields[b"file"]:
        reject(422, "VALIDATION_FAILED", "必須提供照片與資料版本。")
    try:
        expected = fields[b"expected_row_version"].decode("ascii")
        revision_number(expected)
    except ValueError:
        reject(422, "VALIDATION_FAILED", "版本格式不正確。")
    return Upload(expected=expected, media_type=media_type, content=fields[b"file"])
