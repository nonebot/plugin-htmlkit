# nonebot-plugin-htmlkit

一个基于 [litehtml](https://github.com/litehtml/litehtml) 的轻量级 HTML 渲染插件。

## 特性

- 基于 [fontconfig](https://www.freedesktop.org/wiki/Software/fontconfig/) 的字体管理, 支持系统字体和自定义字体
- 提供了 HTML，纯文本，markdown，和 Jinja2 模板渲染的快捷函数
- 支持自定义图片和 CSS 的加载策略
- 支持通过 CSS 控制样式
- 支持自适应控制渲染宽度

## 安装

使用 [`nb-cli`](https://cli.nonebot.dev/) 安装：

```bash
nb plugin install nonebot_plugin_htmlkit-plugin-htmlkit
```

或者，使用你选择的 Python 包管理器工具安装 `nonebot-plugin-htmlkit` 即可。

## 使用

### API

```python
from nonebot import require

require("nonebot_plugin_htmlkit")
from nonebot_plugin_htmlkit import (
    text_to_pic,
    md_to_pic,
    template_to_pic,
    html_to_pic,
)
```

> [!CAUTION]
> 注意：请先 `require("nonebot_plugin_htmlkit")` 后再 `import` 插件！！！

### 配置项

`plugin-htmlkit` 的配置项主要为 [fontconfig](https://www.freedesktop.org/wiki/Software/fontconfig/) 的相关配置。

对于 `FC/FONTCONFIG` 开头的配置项，请参考 [fontconfig 文档](https://www.freedesktop.org/software/fontconfig/fontconfig-user.html) 以了解更多。

```python
# ===============================
# Fontconfig 配置
# ===============================

# FONTCONFIG_FILE
# 用于覆盖默认的配置文件路径。
FONTCONFIG_FILE: str

# FONTCONFIG_PATH
# 用于覆盖默认的配置目录。
FONTCONFIG_PATH: str

# FONTCONFIG_SYSROOT
# 用于设置默认的 sysroot 目录。
FONTCONFIG_SYSROOT: str

# FC_DEBUG
# 用于输出详细的调试信息。
# 详细见 fontconfig 文档。
FC_DEBUG: str

# FC_DBG_MATCH_FILTER
# 用于在调试时过滤特定模式。
# 仅当 FC_DEBUG 设置为 MATCH2 时生效。
FC_DBG_MATCH_FILTER: str

# FC_LANG
# 用于指定查询时的默认语言（弱绑定）。
# 如果未设置，则从当前 locale 推导。
FC_LANG: str

# FONTCONFIG_USE_MMAP
# 控制是否使用 mmap(2) 来处理缓存文件（如果可用）。
# 值为布尔类型（yes/no, 1/0）。
# 如果显式设置该变量，将跳过系统检查并强制启用或禁用。
FONTCONFIG_USE_MMAP: str
```

#### 许可证

MIT
