from asyncio import get_running_loop, run_coroutine_threadsafe
import base64
from collections.abc import Callable, Coroutine, Mapping, Sequence
import os
from pathlib import Path
from typing import Any, Literal
from urllib.parse import unquote, urljoin

import aiofiles
import jinja2
import markdown

import nonebot
from nonebot.drivers import HTTPClientMixin, Request
from nonebot.log import logger
from nonebot.plugin import PluginMetadata, get_plugin_config

from . import config, core
from .config import FcConfig

__plugin_meta__ = PluginMetadata(
    name="nonebot-plugin-htmlkit",
    description="轻量级的 HTML 渲染工具",
    usage="",
    type="library",
    homepage="https://github.com/nonebot/plugin-htmlkit",
    extra={},
)

driver = nonebot.get_driver()
session = driver.get_session() if isinstance(driver, HTTPClientMixin) else None


def init_fontconfig(**kwargs: Any):
    logger.info("Initializing fontconfig...")
    with config.set_fc_environ(get_plugin_config(FcConfig)):
        core._init_fontconfig_internal()  # pyright: ignore[reportPrivateUsage]
    logger.info("Fontconfig initialized.")


@driver.on_startup
async def _():
    init_fontconfig()

    if session is not None:
        await session.setup()


ImgFetchFn = Callable[[str], Coroutine[Any, Any, bytes | None]]
CSSFetchFn = Callable[[str], Coroutine[Any, Any, str | None]]


async def none_fetcher(_url: str) -> None:
    return None


async def read_file(path: str) -> str:
    async with aiofiles.open(path, encoding="utf-8") as f:
        return await f.read()


async def read_tpl(path: str) -> str:
    return await read_file(f"{TEMPLATES_PATH}/{path}")


def _crop_str(s: str, max_len: int = 50) -> str:
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


async def data_scheme_img_fetcher(url: str) -> bytes | None:
    if url.startswith("data:"):
        try:
            header, data = url.split(",", 1)
            if "base64" in header:
                return base64.b64decode(data)
            else:
                return unquote(data).encode("utf-8")
        except Exception as e:
            logger.opt(exception=e).warning(
                f"Failed to decode data scheme URL: {_crop_str(url)}"
            )
    return None


async def filesystem_img_fetcher(url: str) -> bytes | None:
    if url.startswith("file://"):
        path = url[7:]
        if os.path.isfile(path):
            try:
                async with aiofiles.open(path, "rb") as f:
                    return await f.read()
            except Exception as e:
                logger.opt(exception=e).warning(
                    f"Failed to read local file {_crop_str(path)}"
                )
    return None


async def network_img_fetcher(url: str) -> bytes | None:
    if session is None:
        logger.critical(
            "Driver does not support HTTP requests. "
            "Please initialize NoneBot with HTTP client drivers like HTTPX or AIOHTTP."
        )
        return None
    try:
        response = await session.request(Request("GET", url))
        if isinstance(response.content, bytes):
            return response.content
        return None
    except Exception as e:
        logger.opt(exception=e).warning(f"Failed to fetch resource from {url}")
    return None


async def combined_img_fetcher(url: str) -> bytes | None:
    content = await data_scheme_img_fetcher(url)
    if content is not None:
        return content
    content = await filesystem_img_fetcher(url)
    if content is not None:
        return content
    return await network_img_fetcher(url)


async def data_scheme_css_fetcher(url: str) -> str | None:
    if url.startswith("data:"):
        try:
            header, data = url.split(",", 1)
            if "base64" in header:
                return base64.b64decode(data).decode("utf-8")
            else:
                return unquote(data)
        except Exception as e:
            logger.opt(exception=e).warning(
                f"Failed to decode data scheme URL: {_crop_str(url)}"
            )
    return None


async def filesystem_css_fetcher(url: str) -> str | None:
    if url.startswith("file://"):
        path = url[7:]
        if os.path.isfile(path):
            try:
                async with aiofiles.open(path, encoding="utf-8") as f:
                    return await f.read()
            except Exception as e:
                logger.opt(exception=e).warning(
                    f"Failed to read local CSS file {_crop_str(path)}"
                )
    return None


async def network_css_fetcher(url: str) -> str | None:
    if session is None:
        logger.critical(
            "Driver does not support HTTP requests. "
            "Please initialize NoneBot with HTTP client drivers like HTTPX or AIOHTTP."
        )
        return None
    try:
        response = await session.request(Request("GET", url))
        if isinstance(response.content, bytes):
            try:
                return response.content.decode("utf-8")
            except Exception as e:
                logger.opt(exception=e).warning(
                    f"Failed to decode CSS from {_crop_str(url)}"
                )
        return None
    except Exception as e:
        logger.opt(exception=e).warning(
            f"Failed to fetch CSS resource from {_crop_str(url)}"
        )
    return None


async def combined_css_fetcher(url: str) -> str | None:
    content = await data_scheme_css_fetcher(url)
    if content is not None:
        return content
    content = await filesystem_css_fetcher(url)
    if content is not None:
        return content
    return await network_css_fetcher(url)


async def html_to_pic(
    html: str,
    *,
    base_url: str = "",
    dpi: float = 96.0,
    max_width: float = 800.0,
    device_height: float = 600.0,
    default_font_size: float = 12.0,
    font_name: str = "sans-serif",
    allow_refit: bool = True,
    image_format: Literal["png", "jpeg"] = "png",
    jpeg_quality: int = 100,
    lang: str = "zh",
    culture: str = "CN",
    img_fetch_fn: ImgFetchFn = combined_img_fetcher,
    css_fetch_fn: CSSFetchFn = combined_css_fetcher,
    native_data_scheme: bool = True,
    urljoin_fn: Callable[[str, str], str] = urljoin,
) -> bytes:
    """
    将 HTML 渲染为图片。

    Args:
        html (str): HTML 内容
        base_url (str, optional): 基础路径
        dpi (float, optional): DPI
        max_width (float, optional): 最大宽度
        device_height (float, optional): 设备高度
        default_font_size (float, optional): 默认字体大小
        font_name (str, optional): 字体名称
        allow_refit (bool, optional): 允许根据内容缩小宽度
        image_format ("png" | "jpeg", optional): 图片格式
        jpeg_quality (int, optional): jpeg图片质量, 1-100
        lang (str, optional): 语言
        culture (str, optional): 文化
        img_fetch_fn (ImgFetchFn, optional): 图片获取函数
        css_fetch_fn (CSSFetchFn, optional): CSS获取函数
        native_data_scheme (bool, optional): 是否使用原生代码解码 base64 data scheme URL
        urljoin_fn (Callable, optional): urljoin函数

    Returns:
        bytes: 渲染后的图片字节
    """
    loop = get_running_loop()
    return await core._render_internal(  # pyright: ignore[reportPrivateUsage]
        html,
        base_url,
        dpi,
        max_width,
        device_height,
        default_font_size,
        font_name,
        allow_refit,
        -1 if image_format == "png" else jpeg_quality,
        lang,
        culture,
        lambda exc_type, exc_value, exc_traceback: nonebot.logger.opt(
            exception=(exc_type, exc_value, exc_traceback)
        ).error("Exception in html_to_pic: "),
        run_coroutine_threadsafe,
        urljoin_fn,
        loop,
        img_fetch_fn,
        css_fetch_fn,
        native_data_scheme,
        False,
    )


async def debug_html_to_pic(
    html: str,
    *,
    base_url: str = "",
    dpi: float = 144.0,
    max_width: float = 800.0,
    device_height: float = 600.0,
    default_font_size: float = 12.0,
    font_name: str = "sans-serif",
    allow_refit: bool = True,
    image_format: Literal["png", "jpeg"] = "png",
    jpeg_quality: int = 100,
    lang: str = "zh",
    culture: str = "CN",
    img_fetch_fn: ImgFetchFn = combined_img_fetcher,
    css_fetch_fn: CSSFetchFn = combined_css_fetcher,
    native_data_scheme: bool = True,
    urljoin_fn: Callable[[str, str], str] = urljoin,
) -> tuple[bytes, str]:
    """
    将 HTML 渲染为图片以及可调试的 HTML 字符串。

    Args:
        html (str): HTML 内容
        base_url (str, optional): 基础路径
        dpi (float, optional): DPI
        max_width (float, optional): 最大宽度
        device_height (float, optional): 设备高度
        default_font_size (float, optional): 默认字体大小
        font_name (str, optional): 字体名称
        allow_refit (bool, optional): 允许根据内容缩小宽度
        image_format ("png" | "jpeg", optional): 图片格式
        jpeg_quality (int, optional): jpeg图片质量, 1-100
        lang (str, optional): 语言
        culture (str, optional): 文化
        img_fetch_fn (ImgFetchFn, optional): 图片获取函数
        css_fetch_fn (CSSFetchFn, optional): CSS获取函数
        native_data_scheme (bool, optional): 是否使用原生代码解码 base64 data scheme URL
        urljoin_fn (Callable, optional): urljoin函数

    Returns:
        tuple[bytes, str]: 渲染后的图片字节和调试用 HTML 字符串
    """
    loop = get_running_loop()
    return await core._render_internal(  # pyright: ignore[reportPrivateUsage]
        html,
        base_url,
        dpi,
        max_width,
        device_height,
        default_font_size,
        font_name,
        allow_refit,
        -1 if image_format == "png" else jpeg_quality,
        lang,
        culture,
        lambda exc_type, exc, tb: nonebot.logger.opt(
            exception=(exc_type, exc, tb)
        ).error("Exception in html_to_pic: "),
        run_coroutine_threadsafe,
        urljoin_fn,
        loop,
        img_fetch_fn,
        css_fetch_fn,
        native_data_scheme,
        True,
    )


TEMPLATES_PATH = str(Path(__file__).parent / "templates")

env = jinja2.Environment(
    extensions=["jinja2.ext.loopcontrols"],
    loader=jinja2.FileSystemLoader(TEMPLATES_PATH),
    enable_async=True,
)


async def text_to_pic(
    text: str,
    css_path: str = "",
    *,
    dpi: float = 96.0,
    max_width: int = 500,
    allow_refit: bool = True,
    image_format: Literal["png", "jpeg"] = "png",
    jpeg_quality: int = 100,
) -> bytes:
    """
    多行文本转图片

    Args:
        text (str): 纯文本, 可多行
        css_path (str, optional): css文件路径
        dpi (float, optional): DPI，默认为 96.0
        max_width (int, optional): 图片最大宽度，默认为 500
        allow_refit (bool, optional): 允许根据内容缩小宽度，默认为 True
        image_format ("png" | "jpeg", optional): 图片格式, 默认为 "png"
        jpeg_quality (int, optional): jpeg图片质量, 1-100, 默认为 100

    Returns:
        bytes: 图片, 可直接发送
    """
    template = env.get_template("text.html")
    return await html_to_pic(
        html=await template.render_async(
            text=text,
            css=await read_file(css_path) if css_path else await read_tpl("text.css"),
        ),
        dpi=dpi,
        max_width=max_width,
        base_url=f"file://{css_path or TEMPLATES_PATH}",
        allow_refit=allow_refit,
        image_format=image_format,
        jpeg_quality=jpeg_quality,
    )


async def md_to_pic(
    md: str = "",
    md_path: str = "",
    css_path: str = "",
    *,
    dpi: float = 96.0,
    max_width: int = 500,
    img_fetch_fn: ImgFetchFn = combined_img_fetcher,
    allow_refit: bool = True,
    image_format: Literal["png", "jpeg"] = "png",
    jpeg_quality: int = 100,
) -> bytes:
    """
    markdown 转 图片

    Args:
        md (str, optional): markdown 格式文本
        md_path (str, optional): markdown 文件路径
        css_path (str,  optional): css文件路径
        dpi (float, optional): DPI，默认为 96.0
        max_width (int, optional): 图片最大宽度，默认为 500
        img_fetch_fn (ImgFetchFn, optional): 图片获取函数，默认为 combined_img_fetcher
        allow_refit (bool, optional): 允许根据内容缩小宽度，默认为 True
        image_format ("png" | "jpeg", optional): 图片格式, 默认为 "png"
        jpeg_quality (int, optional): jpeg图片质量, 1-100, 默认为 100

    Returns:
        bytes: 图片, 可直接发送
    """
    template = env.get_template("markdown.html")
    if not md:
        if md_path:
            md = await read_file(md_path)
        else:
            raise Exception("md or md_path must be provided")
    logger.debug(md)
    md = markdown.markdown(
        md,
        extensions=[
            "pymdownx.tasklist",
            "tables",
            "fenced_code",
            "codehilite",
            "pymdownx.tilde",
        ],
        extension_configs={"mdx_math": {"enable_dollar_delimiter": True}},
    )

    logger.debug(md)
    if "math/tex" in md:
        logger.warning("TeX math is not supported by htmlkit.")

    if css_path:
        css = await read_file(css_path)
    else:
        css = await read_tpl("github-markdown-light.css") + await read_tpl(
            "pygments-default.css",
        )

    return await html_to_pic(
        html=await template.render_async(md=md, css=css),
        dpi=dpi,
        max_width=max_width,
        device_height=10,
        base_url=f"file://{css_path or TEMPLATES_PATH}",
        img_fetch_fn=img_fetch_fn,
        allow_refit=allow_refit,
        image_format=image_format,
        jpeg_quality=jpeg_quality,
    )


async def template_to_html(
    template_path: str | os.PathLike[str] | Sequence[str | os.PathLike[str]],
    template_name: str,
    filters: None | Mapping[str, Any] = None,
    **kwargs,
) -> str:
    """
    使用jinja2模板引擎渲染html

    Args:
        template_path (str | os.PathLike[str] | Sequence[str | os.PathLike[str]]):
            模板环境路径
        template_name (str): 模板名
        filters (Mapping[str, Any] | None): 自定义过滤器
        **kwargs: 模板参数

    Returns:
        str: 渲染后的html字符串
    """
    template_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_path),
        enable_async=True,
    )
    if filters:
        for filter_name, filter_func in filters.items():
            template_env.filters[filter_name] = filter_func
            logger.debug(f"Custom filter loaded: {filter_name}")
    template = template_env.get_template(template_name)
    return await template.render_async(**kwargs)


async def template_to_pic(
    template_path: str | os.PathLike[str] | Sequence[str | os.PathLike[str]],
    template_name: str,
    templates: Mapping[Any, Any],
    filters: None | Mapping[str, Any] = None,
    *,
    dpi: float = 96.0,
    max_width: int = 500,
    device_height: int = 600,
    base_url: str | None = None,
    img_fetch_fn: ImgFetchFn = combined_img_fetcher,
    css_fetch_fn: CSSFetchFn = combined_css_fetcher,
    allow_refit: bool = True,
    image_format: Literal["png", "jpeg"] = "png",
    jpeg_quality: int = 100,
) -> bytes:
    """
    使用jinja2模板引擎通过html生成图片

    Args:
        template_path (str | os.PathLike[str] | Sequence[str | os.PathLike[str]]):
            模板环境路径
        template_name (str): 模板名
        templates (Mapping[Any, Any]): 模板参数
        filters (Mapping[str, Any] | None): 自定义过滤器
        dpi (float, optional): DPI，默认为 96.0
        max_width (int, optional): 图片最大宽度，默认为 500
        device_height (int, optional): 设备高度，默认为 800
        base_url (str | None, optional): 基础路径，默认为 "file://{template.filename}"
        img_fetch_fn (ImgFetchFn, optional): 图片获取函数
        css_fetch_fn (CSSFetchFn, optional): css获取函数
        allow_refit (bool, optional): 允许根据内容缩小宽度
        image_format ("png" | "jpeg", optional): 图片格式, 默认为 "png"
        jpeg_quality (int, optional): jpeg图片质量, 1-100, 默认为 100

    Returns:
        bytes: 图片 可直接发送
    """
    template_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_path),
        enable_async=True,
    )
    if filters:
        for filter_name, filter_func in filters.items():
            template_env.filters[filter_name] = filter_func
            logger.debug(f"Custom filter loaded: {filter_name}")
    template = template_env.get_template(template_name)
    if not base_url:
        if template.filename:
            base_url = f"file://{Path(template.filename).as_posix()}"
        else:
            base_url = "file:///"
            logger.warning("Template has no filename, base_url set to `file:///`")
    return await html_to_pic(
        html=await template.render_async(**templates),
        base_url=base_url,
        dpi=dpi,
        max_width=max_width,
        device_height=device_height,
        img_fetch_fn=img_fetch_fn,
        css_fetch_fn=css_fetch_fn,
        allow_refit=allow_refit,
        image_format=image_format,
        jpeg_quality=jpeg_quality,
    )
