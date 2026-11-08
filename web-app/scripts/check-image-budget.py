"""Run inside the Linux API container through stdin to verify its image worker."""

import subprocess
import sys
from io import BytesIO
from time import perf_counter

from PIL import Image

from vibicle_api.errors import ContractError
from vibicle_api.services.images import process_image
from vibicle_api.upload import Upload


def image(size: tuple[int, int]) -> bytes:
    buffer = BytesIO()
    Image.new("1", size).save(buffer, "PNG")
    return buffer.getvalue()


def main() -> None:
    start = perf_counter()
    width, height, output = process_image(Upload("1", "image/png", image((6000, 2000))))
    assert (width, height) == (6000, 2000) and len(output) <= 5 * 1024 * 1024
    elapsed = perf_counter() - start
    cases = (
        (image((6000, 2001)), "IMAGE_DIMENSIONS_INVALID"),
        (image((6001, 20)), "IMAGE_DIMENSIONS_INVALID"),
        (image((120, 100))[:40], "IMAGE_DECODE_FAILED"),
    )
    for raw, code in cases:
        try:
            process_image(Upload("1", "image/png", raw))
        except ContractError as error:
            assert error.error.code == code, error.error.code
        else:
            raise AssertionError("Invalid photo accepted.")
    check = """
import resource
from vibicle_api.image_worker import limit_process
limit_process()
assert resource.getrlimit(resource.RLIMIT_AS) == (128*1024*1024, 128*1024*1024)
assert resource.getrlimit(resource.RLIMIT_CPU) == (5, 5)
try:
    bytearray(256*1024*1024)
except MemoryError:
    print("128 MiB limit rejects a 256 MiB allocation; CPU budget 5 s.")
else:
    raise AssertionError("Worker exceeded memory budget.")
"""
    subprocess.run([sys.executable, "-c", check], check=True, timeout=5)
    print(f"PASS: Linux worker handled 6000x2000 ({elapsed:.3f}s); over-12M and corrupt rejected.")


if __name__ == "__main__":
    main()
