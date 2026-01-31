from htmlkit import DEFAULT_FETCHER as DEFAULT_FETCHER
from htmlkit import BaseDataFetcher as BaseDataFetcher
from htmlkit import CombinedFetcher as CombinedFetcher
from htmlkit import DataSchemeFetcher as DataSchemeFetcher
from htmlkit import FilesystemFetcher as FilesystemFetcher
from htmlkit import core as _core
from htmlkit import debug_html_to_pic as debug_html_to_pic
from htmlkit import html_to_pic as html_to_pic
from htmlkit import md_to_pic as md_to_pic
from htmlkit import template_to_html as template_to_html
from htmlkit import template_to_pic as template_to_pic
from htmlkit import text_to_pic as text_to_pic

import nonebot
from nonebot.drivers import HTTPClientMixin, Request
from nonebot.internal.driver import HTTPClientSession
from nonebot.log import logger
from nonebot.plugin import PluginMetadata, get_plugin_config
from nonebot_plugin_htmlkit.config import NoneBotFcConfig, set_fc_environ

__plugin_meta__ = PluginMetadata(
    name="nonebot-plugin-htmlkit",
    description="轻量级的 HTML 渲染工具",
    usage="",
    type="library",
    homepage="https://github.com/nonebot/plugin-htmlkit",
    extra={},
)


def init_fontconfig(**kwargs):
    logger.info("NoneBot Initializing fontconfig...")
    with set_fc_environ(get_plugin_config(NoneBotFcConfig)):
        _core._init_fontconfig_internal()  # pyright: ignore[reportPrivateUsage]
    logger.info("NoneBot Fontconfig initialized.")


class NonebotHTTPFetcher(BaseDataFetcher):
    def __init__(self, session: HTTPClientSession):
        self.session: HTTPClientSession = session

    async def get_data(self, url: str) -> bytes | None:
        request = Request("GET", url)
        response = await self.session.request(request)
        if response.status_code == 200:
            if isinstance(response.content, bytes):
                return response.content
            elif isinstance(response.content, str):
                return response.content.encode("utf-8")
        return None


driver = nonebot.get_driver()


@driver.on_startup
async def _():
    init_fontconfig()

    try:
        if isinstance(driver, HTTPClientMixin):
            driver_session = driver.get_session()
            await driver_session.setup()
            DEFAULT_FETCHER.set(
                CombinedFetcher(
                    DataSchemeFetcher(),
                    FilesystemFetcher(),
                    NonebotHTTPFetcher(driver_session),
                )
            )
            logger.info("Got HTTP session.")
    except Exception as e:
        logger.opt(exception=e).error(
            "Error while getting HTTP session and setting up."
        )
