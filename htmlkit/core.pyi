import asyncio
from collections.abc import Callable, Coroutine
import concurrent.futures
from types import TracebackType
from typing import Any, Literal, TypeAlias, overload
from typing_extensions import Unpack

def _init_fontconfig_internal() -> None: ...

_ExceptionTuple: TypeAlias = tuple[type[BaseException], BaseException, TracebackType]
_ExceptionHandleFn: TypeAlias = Callable[[Unpack[_ExceptionTuple]], None]
_AsyncioRunCoroutineThreadsafeFn: TypeAlias = Callable[
    [Coroutine[Any, Any, Any], asyncio.AbstractEventLoop],
    concurrent.futures.Future[Any],
]
_UrlJoinFn: TypeAlias = Callable[[str, str], str]
_ImageFetchFn: TypeAlias = Callable[[str], Coroutine[Any, Any, None | bytes]]
_CSSFetchFn: TypeAlias = Callable[[str], Coroutine[Any, Any, None | str]]

@overload
def _render_internal(
    html_content: str,
    base_url: str,
    dpi: float,
    width: float,
    height: float,
    default_font_size: float,
    font_name: str,
    allow_refit: bool,
    image_flag: int,
    lang: str,
    culture: str,
    exception_fn: _ExceptionHandleFn,
    asyncio_run_coroutine_threadsafe: _AsyncioRunCoroutineThreadsafeFn,
    urljoin: _UrlJoinFn,
    loop: asyncio.AbstractEventLoop,
    img_fetch_fn: _ImageFetchFn,
    css_fetch_fn: _CSSFetchFn,
    native_data_scheme: bool,
    debug_flag: Literal[False],
    /,
) -> asyncio.Future[bytes]: ...
@overload
def _render_internal(
    html_content: str,
    base_url: str,
    dpi: float,
    width: float,
    height: float,
    default_font_size: float,
    font_name: str,
    allow_refit: bool,
    image_flag: int,
    lang: str,
    culture: str,
    exception_fn: _ExceptionHandleFn,
    asyncio_run_coroutine_threadsafe: _AsyncioRunCoroutineThreadsafeFn,
    urljoin: _UrlJoinFn,
    loop: asyncio.AbstractEventLoop,
    img_fetch_fn: _ImageFetchFn,
    css_fetch_fn: _CSSFetchFn,
    native_data_scheme: bool,
    debug_flag: Literal[True],
    /,
) -> asyncio.Future[tuple[bytes, str]]: ...
def _render_internal(
    html_content: str,
    base_url: str,
    dpi: float,
    width: float,
    height: float,
    default_font_size: float,
    font_name: str,
    allow_refit: bool,
    image_flag: int,
    lang: str,
    culture: str,
    exception_fn: _ExceptionHandleFn,
    asyncio_run_coroutine_threadsafe: _AsyncioRunCoroutineThreadsafeFn,
    urljoin: _UrlJoinFn,
    loop: asyncio.AbstractEventLoop,
    img_fetch_fn: _ImageFetchFn,
    css_fetch_fn: _CSSFetchFn,
    native_data_scheme: bool,
    debug_flag: bool,
    /,
) -> asyncio.Future[bytes | tuple[bytes, str]]: ...
