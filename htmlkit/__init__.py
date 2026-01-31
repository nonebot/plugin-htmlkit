from __future__ import annotations

from asyncio import get_running_loop, run_coroutine_threadsafe
import base64
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import suppress
from contextvars import ContextVar
import os
from pathlib import Path
from typing import Any, Literal, Protocol
from urllib.parse import unquote, urljoin

import aiofiles
import jinja2
from loguru import logger
import markdown

from . import config, core
from .config import FcConfig

with suppress(ImportError):
    import httpx
with suppress(ImportError):
    import aiohttp

_FONTCONFIG_INITIALIZED = False


def init_fontconfig(fc_config: FcConfig | None = None) -> None:
    global _FONTCONFIG_INITIALIZED
    logger.info("Initializing fontconfig...")
    with config.set_fc_environ(fc_config or FcConfig()):
        core._init_fontconfig_internal()  # pyright: ignore[reportPrivateUsage]
    _FONTCONFIG_INITIALIZED = True
    logger.info("Fontconfig initialized.")


async def read_file(path: str) -> str:
    async with aiofiles.open(path, encoding="utf-8") as f:
        return await f.read()


async def read_tpl(path: str) -> str:
    return await read_file(f"{TEMPLATES_PATH}/{path}")


def _crop_str(s: str, max_len: int = 50) -> str:
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


class Fetcher(Protocol):
    async def fetch_image(self, url: str) -> bytes | None:
        raise NotImplementedError()

    async def fetch_css(self, url: str) -> str | None:
        raise NotImplementedError()


class NoneFetcher(Fetcher):
    async def fetch_image(self, url: str) -> bytes | None:
        return None

    async def fetch_css(self, url: str) -> bytes | None:
        return None


class BaseDataFetcher(Fetcher):
    async def get_data(self, url: str) -> bytes | None:
        raise NotImplementedError()

    async def fetch_image(self, url: str) -> bytes | None:
        try:
            data = await self.get_data(url)
            return data
        except Exception as e:
            logger.opt(exception=e).warning(
                f"Failed to fetch image from URL: {_crop_str(url)}"
            )
        return None

    async def fetch_css(self, url: str) -> str | None:
        try:
            data = await self.get_data(url)
            if data is not None:
                return data.decode("utf-8")
        except Exception as e:
            logger.opt(exception=e).warning(
                f"Failed to fetch CSS from URL: {_crop_str(url)}"
            )
        return None


class DataSchemeFetcher(BaseDataFetcher):
    async def get_data(self, url: str) -> bytes | None:
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


class FilesystemFetcher(BaseDataFetcher):
    async def get_data(self, url: str) -> bytes | None:
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


class HttpxNetworkFetcher(BaseDataFetcher):
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client

    async def get_data(self, url: str) -> bytes | None:
        if self.client is None:
            self.client = httpx.AsyncClient()
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.opt(exception=e).warning(f"Failed to fetch resource from {url}")
        return None


class AiohttpNetworkFetcher(BaseDataFetcher):
    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        self.session = session

    async def get_data(self, url: str) -> bytes | None:
        if self.session is None:
            self.session = aiohttp.ClientSession()
        try:
            async with self.session.get(url) as response:
                response.raise_for_status()
                return await response.read()
        except Exception as e:
            logger.opt(exception=e).warning(f"Failed to fetch resource from {url}")
        return None


class PopularNetworkFetcher(BaseDataFetcher):
    def __init__(self) -> None:
        import importlib.util

        self.fetcher = None
        if importlib.util.find_spec("httpx"):
            self.fetcher = HttpxNetworkFetcher()
            return
        elif importlib.util.find_spec("aiohttp"):
            self.fetcher = AiohttpNetworkFetcher()
            return

    async def get_data(self, url: str) -> bytes | None:
        if self.fetcher is not None:
            return await self.fetcher.get_data(url)
        return None


class CombinedFetcher(Fetcher):
    def __init__(self, *fetchers: Fetcher | Iterable[Fetcher]) -> None:
        self.fetchers: list[Fetcher] = []
        for fetcher in fetchers:
            if isinstance(fetcher, Iterable):
                self.fetchers.extend(fetcher)
            else:
                self.fetchers.append(fetcher)

    async def fetch_image(self, url: str) -> bytes | None:
        for fetcher in self.fetchers:
            try:
                data = await fetcher.fetch_image(url)
                if data is not None:
                    return data
            except Exception as e:
                logger.opt(exception=e).warning(
                    f"Fetcher {fetcher} failed for URL: {_crop_str(url)}"
                )

        return None

    async def fetch_css(self, url: str) -> str | None:
        for fetcher in self.fetchers:
            try:
                data = await fetcher.fetch_css(url)
                if data is not None:
                    return data
            except Exception as e:
                logger.opt(exception=e).warning(
                    f"Fetcher {fetcher} failed for URL: {_crop_str(url)}"
                )
        return None


DEFAULT_FETCHER: ContextVar[Fetcher] = ContextVar(
    "DEFAULT_FETCHER",
    default=CombinedFetcher(
        DataSchemeFetcher(),
        FilesystemFetcher(),
        PopularNetworkFetcher(),
    ),
)


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
    fetcher: Fetcher | None = None,
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
        fetcher (Fetcher, optional): 资源获取器
        native_data_scheme (bool, optional): 是否使用原生代码解码 base64 data scheme URL
        urljoin_fn (Callable, optional): urljoin函数

    Returns:
        bytes: 渲染后的图片字节
    """
    if not _FONTCONFIG_INITIALIZED:
        init_fontconfig()

    loop = get_running_loop()
    fetcher = fetcher or DEFAULT_FETCHER.get()

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
        lambda exc_type, exc_value, exc_traceback: logger.opt(
            exception=(exc_type, exc_value, exc_traceback)
        ).error("Exception in html_to_pic: "),
        run_coroutine_threadsafe,
        urljoin_fn,
        loop,
        fetcher.fetch_image,
        fetcher.fetch_css,
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
    fetcher: Fetcher | None = None,
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
        fetcher (Fetcher): 资源获取器
        native_data_scheme (bool, optional): 是否使用原生代码解码 base64 data scheme URL
        urljoin_fn (Callable, optional): urljoin函数

    Returns:
        tuple[bytes, str]: 渲染后的图片字节和调试用 HTML 字符串
    """
    if not _FONTCONFIG_INITIALIZED:
        init_fontconfig()

    loop = get_running_loop()
    fetcher = fetcher or DEFAULT_FETCHER.get()

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
        lambda exc_type, exc, tb: logger.opt(exception=(exc_type, exc, tb)).error(
            "Exception in html_to_pic: "
        ),
        run_coroutine_threadsafe,
        urljoin_fn,
        loop,
        fetcher.fetch_image,
        fetcher.fetch_css,
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
    fetcher: Fetcher | None = None,
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
        fetcher (Fetcher, optional): 资源获取器
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
        fetcher=fetcher,
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
    allow_refit: bool = True,
    fetcher: Fetcher | None = None,
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
        allow_refit (bool, optional): 允许根据内容缩小宽度，默认为 True
        fetcher (Fetcher, optional): 资源获取器
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
        allow_refit=allow_refit,
        fetcher=fetcher,
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
    fetcher: Fetcher | None = None,
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
        fetcher (Fetcher, optional): 资源获取器
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
        fetcher=fetcher,
        allow_refit=allow_refit,
        image_format=image_format,
        jpeg_quality=jpeg_quality,
    )


__all__ = (
    "DEFAULT_FETCHER",
    "AiohttpNetworkFetcher",
    "BaseDataFetcher",
    "CombinedFetcher",
    "DataSchemeFetcher",
    "FcConfig",
    "Fetcher",
    "FilesystemFetcher",
    "HttpxNetworkFetcher",
    "NoneFetcher",
    "PopularNetworkFetcher",
    "debug_html_to_pic",
    "html_to_pic",
    "init_fontconfig",
    "md_to_pic",
    "template_to_html",
    "template_to_pic",
    "text_to_pic",
)
