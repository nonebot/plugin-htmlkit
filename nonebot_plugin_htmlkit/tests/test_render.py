from htmlkit import html_to_pic, md_to_pic
import pytest
from utils import assert_image_equal

HTML_SOURCES = {
    "basic": "<html><body><h1>Hello, World!</h1><p>This is a test.</p></body></html>",
    "image": '<html><body><h1>Hello, World!</h1><img src="https://www.python.org/static/community_logos/python-logo.png"></body></html>',
    "css": """<html>
    <head><style>
    body { background-color: red; }
    h1 { color: cyan; text-align: center; }
    </style></head>
    <body><h1>Hello, World!</h1></body>
    </html>""",
    "text-variant": """<html><body>
    <p><i>Italic text</i></p>
    <p><b>Bold text</b></p>
    <p><u>Underline text</u></p>
    <p><b><i><u>Combined text</u></i></b></p>
    <p><code>Monospace text</code></p>
    <p><s>Strikethrough text</s></p>
    </body></html>""",
}

REFIT = [True, False]

FORMATS = ["png", "jpeg"]


@pytest.mark.asyncio
@pytest.mark.parametrize(("html_id", "html_src"), HTML_SOURCES.items())
@pytest.mark.parametrize("image_format", FORMATS)
@pytest.mark.parametrize("refit", REFIT)
async def test_render_and_verify(
    html_id, html_src, image_format, regen_ref, output_img_dir, refit
):
    img_bytes = await html_to_pic(
        html_src, image_format=image_format, allow_refit=refit
    )
    assert img_bytes.startswith(
        b"\x89PNG\r\n\x1a\n" if image_format == "png" else b"\xff\xd8"
    )

    filename = f"{html_id}{'_no_refit' if not refit else ''}.{image_format}"
    await assert_image_equal(img_bytes, filename, regen_ref, output_img_dir)


MARKDOWN_SOURCE = """
# Hello, World!
This is a **markdown** test with an image:
![Python Logo](https://www.python.org/static/community_logos/python-logo.png)
and some more text **surrounding** it.

And here is a link to [Python's website](https://www.python.org).

![Python Logo](https://www.python.org/static/community_logos/python-logo.png)

The image is on a new paragraph.

## Blockquote

> This is a blockquote.

## List

- Item 1
- Item 2
- Item 3

## Table

| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |

## Code Block

```python
def hello():
    print("Hello, World!")
```

```cpp
#include <iostream>

int main() {
    std::cout << "Hello, World!" << std::endl;
    return 0;
}
```

## Text Decoration

This text is *italic*, this is **bold**, this is ***bold italic***,
this is <u>underlined</u>, this is ~~strikethrough~~, and this is `monospace`.
"""


@pytest.mark.asyncio
@pytest.mark.parametrize("image_format", FORMATS)
@pytest.mark.parametrize("refit", REFIT)
async def test_markdown_render_and_verify(
    regen_ref,
    output_img_dir,
    image_format,
    refit,
):
    img_bytes = await md_to_pic(
        MARKDOWN_SOURCE, image_format=image_format, allow_refit=refit
    )
    assert img_bytes.startswith(
        b"\x89PNG\r\n\x1a\n" if image_format == "png" else b"\xff\xd8"
    )

    filename = f"markdown{'_no_refit' if not refit else ''}.{image_format}"
    await assert_image_equal(img_bytes, filename, regen_ref, output_img_dir)
