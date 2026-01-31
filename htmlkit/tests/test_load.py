import pytest

from htmlkit import html_to_pic


@pytest.mark.asyncio
async def test_render_basic_png():
    img_bytes = await html_to_pic(
        "<html><body><h1>Hello, World!</h1><p>This is a test.</p></body></html>"
    )
    assert img_bytes.startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.asyncio
async def test_render_basic_jpeg():
    img_bytes = await html_to_pic(
        "<html><body><h1>Hello, World!</h1><p>This is a test.</p></body></html>",
        image_format="jpeg",
        jpeg_quality=90,
    )
    assert img_bytes.startswith(b"\xff\xd8")


@pytest.mark.asyncio
async def test_render_fetch_image_png():
    img_bytes = await html_to_pic(
        '<html><body><h1>Hello, World!</h1><img src="https://www.python.org/static/community_logos/python-logo.png"></body></html>'
    )
    assert img_bytes.startswith(b"\x89PNG\r\n\x1a\n")
