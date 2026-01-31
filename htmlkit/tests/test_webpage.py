from pathlib import Path

import aiofiles
import pytest
from utils import assert_image_equal

from htmlkit import html_to_pic

WEBPAGES = [
    directory.name
    for directory in Path(__file__).parent.joinpath("webpages").iterdir()
    if directory.is_dir()
]


@pytest.mark.asyncio
@pytest.mark.parametrize("image_format", ["png", "jpeg"])
@pytest.mark.parametrize("webpage", WEBPAGES)
@pytest.mark.parametrize("refit", [True, False])
async def test_render_webpage(image_format, regen_ref, output_img_dir, webpage, refit):
    page_path = Path(__file__).parent / "webpages" / webpage / "index.html"
    async with aiofiles.open(page_path, encoding="utf-8") as f:
        html_content = await f.read()
    img_bytes = await html_to_pic(
        html_content,
        base_url=f"file://{page_path.absolute().as_posix()}",
        max_width=1080,
        image_format=image_format,
        allow_refit=refit,
    )
    assert img_bytes.startswith(
        b"\x89PNG\r\n\x1a\n" if image_format == "png" else b"\xff\xd8"
    )

    filename = f"{webpage}{'_no_refit' if not refit else ''}.{image_format}"
    await assert_image_equal(img_bytes, filename, regen_ref, output_img_dir)
