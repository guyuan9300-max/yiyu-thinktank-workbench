# 开源软件归属（NOTICE 模板）

> 此文件是模板。**真实的 NOTICE 应由 `docs/legal/scripts/collect-licenses.mjs` 自动生成**，输出到 `docs/legal/generated/NOTICE.txt`。
>
> 每次发版前重新生成，并把生成的 NOTICE.txt 复制到 App 资源目录（`Contents/Resources/legal/NOTICE.txt`），由"关于面板 → 开源许可"入口展示。

---

## 标准化开头（建议保留）

```
=================================================================
  益语智库自用平台 V2.0
  开源软件归属与许可声明
  Open Source Software Notice and Attribution
=================================================================

本软件使用了以下开源软件。我们对这些项目的作者表示感谢。
This software incorporates the following open source software.
We are grateful to the authors of these projects.

如对本声明或开源软件有任何疑问，请联系：legal@yiyu.example.com
For questions about this notice or open source software,
please contact: legal@yiyu.example.com

==================================================================
```

## 主体内容（自动生成）

由 collect-licenses.mjs 脚本根据 npm + pip 依赖自动生成。

格式示例：

```
* electron@28.0.0
  License: MIT
  Source:  https://github.com/electron/electron

* react@18.2.0
  License: MIT
  Source:  https://github.com/facebook/react

* fastapi@0.109.0
  License: MIT
  Source:  https://github.com/tiangolo/fastapi

* sqlalchemy@2.0.25
  License: MIT
  Source:  https://www.sqlalchemy.org/
```

## 必须人工补充的部分

下面这些非 npm/pip 的依赖必须人工维护：

```
* Python Build Standalone (python-build-standalone)
  License: PSF-2.0 / MIT (composite)
  Source:  https://github.com/astral-sh/python-build-standalone
  Notes:   包含 CPython 解释器及其标准库

* CPython
  License: PSF-2.0
  Source:  https://www.python.org/
  Notes:   Python 解释器

* SQLite
  License: Public Domain
  Source:  https://www.sqlite.org/
  Notes:   嵌入式数据库

* Chromium (via Electron)
  License: BSD-3-Clause + multiple
  Source:  https://www.chromium.org/
  Notes:   渲染引擎。详细子组件许可见 Chromium 项目 LICENSES 目录
```

## 字体声明（若用到非系统字体）

```
* 思源黑体 / Source Han Sans
  License: SIL Open Font License 1.1
  Source:  https://github.com/adobe-fonts/source-han-sans
  Copyright: Adobe Systems Incorporated

* 苹方-简 (PingFang SC) [系统字体]
  Copyright Apple Inc., 通过 macOS 系统获取
  Notes: 系统字体，无需额外声明
```

## 图标声明（若用到第三方图标库）

```
* Lucide Icons
  License: ISC License
  Source:  https://lucide.dev/
  Copyright: 2022 Lucide Contributors
```

## 完整 License 文本

App Store 与法务要求保留完整 license 文本。`generated/NOTICE.txt` 中包含每个依赖的完整 license 文本（不只是 SPDX 标识）。

如使用 license-checker，可以通过 `--customPath` 选项把完整 license 文本拼进 NOTICE.txt：

```bash
license-checker --production --customPath docs/legal/scripts/license-format.json \
                --json > all-licenses.json
```

`license-format.json` 内容：

```json
{
  "name": "",
  "version": "",
  "licenses": "",
  "licenseText": "noLicenseText"
}
```

---

## 维护规范

| 时机 | 操作 |
| --- | --- |
| 每次合并新依赖 | 跑一次 collect-licenses.mjs，提交更新的 NOTICE.txt |
| 每次发版前 | 跑一次完整扫描 + 检查 license-warnings.txt |
| 重大版本（年度） | 律师复核 NOTICE.txt 完整性 |

---

## 历史版本

| 版本 | 日期 | 主要变化 |
| --- | --- | --- |
| v1.0 | 2026-XX-XX | 初版 |
