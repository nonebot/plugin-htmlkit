from io import BytesIO
from pathlib import Path

import aiofiles
import numpy as np
from PIL import Image
import pytest


def load_image_bytes(img_bytes):
    return np.array(Image.open(BytesIO(img_bytes)).convert("RGB"), dtype=np.float32)


def mse(img1, img2):
    return np.mean((img1 - img2) ** 2)


REF_PATH = Path(__file__).parent / "ref_images"
REF_PATH.mkdir(exist_ok=True, parents=True)


async def assert_image_equal(img_bytes, filename, regen_ref, output_img_dir):
    img = load_image_bytes(img_bytes)
    ref_path = REF_PATH / filename
    if regen_ref:
        async with aiofiles.open(ref_path, "wb") as f:
            await f.write(img_bytes)
        pytest.skip("Reference image regenerated, skipping verification")

    if output_img_dir:
        out_path = Path(output_img_dir)
        out_path.mkdir(exist_ok=True, parents=True)
        async with aiofiles.open(out_path / filename, "wb") as f:
            await f.write(img_bytes)

    assert ref_path.exists(), (
        f"Reference image {ref_path} does not exist. "
        "Run tests with --regen-ref to generate it."
    )
    async with aiofiles.open(ref_path, "rb") as f:
        ref_img_bytes = await f.read()
    ref_img = load_image_bytes(ref_img_bytes)

    assert (
        img.shape == ref_img.shape
    ), f"Image shape mismatch: {img.shape} vs {ref_img.shape}"
    error = mse(img, ref_img)
    assert error < 1.0, f"Image MSE too high: {error}"
