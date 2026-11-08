"""Isolated image conversion process. Only normalized bytes leave the worker."""

import json
import sys
import warnings
from collections.abc import Buffer
from io import BytesIO

FILE_LIMIT = 5 * 1024 * 1024
PIXEL_LIMIT = 12_000_000
MEMORY_LIMIT = 128 * 1024 * 1024


class ImageRejected(Exception):
    pass


class LimitedOutput(BytesIO):
    def write(self, data: Buffer, /) -> int:
        if self.tell() + memoryview(data).nbytes > FILE_LIMIT:
            raise ImageRejected("IMAGE_OUTPUT_TOO_LARGE")
        return super().write(data)


def limit_process() -> None:
    if sys.platform != "win32":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
        resource.setrlimit(resource.RLIMIT_CPU, (5, 5))


def normalize(raw: bytes, expected: str) -> tuple[tuple[int, int], bytes]:
    from PIL import Image, ImageOps, UnidentifiedImageError

    Image.MAX_IMAGE_PIXELS = PIXEL_LIMIT
    allowed = ("JPEG", "PNG", "WEBP")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw), formats=list(allowed)) as image:
                if image.format != expected:
                    raise ImageRejected("IMAGE_MEDIA_TYPE_MISMATCH")
                width, height = image.size
                if not (
                    1 <= width <= 6000 and 1 <= height <= 6000 and width * height <= PIXEL_LIMIT
                ):
                    raise ImageRejected("IMAGE_DIMENSIONS_INVALID")
                if getattr(image, "n_frames", 1) != 1:
                    raise ImageRejected("IMAGE_FRAMES_UNSUPPORTED")
                image.load()
                ImageOps.exif_transpose(image, in_place=True)
                # Drop all decoder metadata. Encode only pixels, with safe channel modes.
                mode = "RGB" if expected == "JPEG" else "RGBA"
                pixels = image.convert(mode)
                pixels.info.clear()
                with LimitedOutput() as output:
                    pixels.save(output, format=expected)
                    return pixels.size, output.getvalue()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ImageRejected("IMAGE_DIMENSIONS_INVALID") from None
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise ImageRejected("IMAGE_DECODE_FAILED") from None
    except MemoryError:
        raise ImageRejected("IMAGE_PROCESSING_LIMIT") from None


def main() -> None:
    limit_process()
    try:
        (width, height), data = normalize(sys.stdin.buffer.read(FILE_LIMIT + 1), sys.argv[1])
        sys.stdout.buffer.write(json.dumps({"width": width, "height": height}).encode() + b"\n")
        sys.stdout.buffer.write(data)
    except ImageRejected as exc:
        sys.stdout.buffer.write(json.dumps({"error": str(exc)}).encode() + b"\n")


if __name__ == "__main__":
    main()
