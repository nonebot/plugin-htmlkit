from pathlib import Path

import pytest
from utils import assert_image_equal

from htmlkit import template_to_pic


@pytest.mark.asyncio
@pytest.mark.parametrize("image_format", ["png", "jpeg"])
async def test_render_templates_1(image_format, regen_ref, output_img_dir):
    template_path = Path(__file__).parent / "templates" / "test_1"

    image_bytes = await template_to_pic(
        template_path=template_path,
        template_name="index.html",
        templates={
            "title": "Test Template",
            "header": "Welcome to the Test Template",
            "content": "This is a simple test of the template rendering.",
        },
        filters={
            "uppercase": str.upper,
            "repeat": lambda s, n: " ".join(s for _ in range(n)),
        },
        image_format=image_format,
    )

    assert image_bytes.startswith(
        b"\x89PNG\r\n\x1a\n" if image_format == "png" else b"\xff\xd8"
    )

    filename = f"template_1.{image_format}"
    await assert_image_equal(image_bytes, filename, regen_ref, output_img_dir)
