from pathlib import Path

import aiofiles
import pytest
from utils import assert_image_equal

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
    from nonebot_plugin_htmlkit import html_to_pic

    page_path = Path(__file__).parent / "webpages" / webpage / "index.html"
    async with aiofiles.open(page_path, encoding="utf-8") as f:
        html_content = await f.read()
    img_bytes_fut = html_to_pic(
        html_content,
        base_url=f"file://{page_path.absolute().as_posix()}",
        max_width=1080,
        image_format=image_format,
        allow_refit=refit,
    )
    img_bytes = await img_bytes_fut
    assert img_bytes.startswith(
        b"\x89PNG\r\n\x1a\n" if image_format == "png" else b"\xff\xd8"
    )
    filename = f"{webpage}{'_no_refit' if not refit else ''}.{image_format}"
    await assert_image_equal(img_bytes, filename, regen_ref, output_img_dir)
