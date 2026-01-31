from pathlib import Path

from nonebug import NONEBOT_INIT_KWARGS
import pytest
from pytest_asyncio import is_async_test

import nonebot

ASSETS_DIR = Path(__file__).parent / "assets"


def pytest_configure(config: pytest.Config):
    config.stash[NONEBOT_INIT_KWARGS] = {
        "driver": "~httpx",
        "fontconfig_path": ASSETS_DIR.as_posix(),
        "fontconfig_file": "fonts.conf",
    }


@pytest.fixture(scope="session", autouse=True)
async def after_nonebot_init(after_nonebot_init: None):
    nonebot.load_plugin("nonebot_plugin_htmlkit")


def pytest_addoption(parser):
    parser.addoption(
        "--regen-ref",
        action="store_true",
        default=False,
        help="Regenerate reference images instead of verifying against them",
    )
    parser.addoption(
        "--output-img-dir",
        type=str,
        default="",
        help="Directory to save output images",
    )


@pytest.fixture(scope="session")
def regen_ref(request):
    return request.config.getoption("--regen-ref")


@pytest.fixture(scope="session")
def output_img_dir(request):
    return request.config.getoption("--output-img-dir")


def pytest_collection_modifyitems(items: list[pytest.Item]):
    pytest_asyncio_tests = (item for item in items if is_async_test(item))
    session_scope_marker = pytest.mark.asyncio(loop_scope="session")
    for async_test in pytest_asyncio_tests:
        async_test.add_marker(session_scope_marker, append=False)
