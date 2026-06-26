# Yiyu Thinktank Workbench

Yiyu Thinktank Workbench is an open-source desktop workbench for public-interest operations, research workflows, and organization collaboration. The app is built with Electron, React, TypeScript, and a local Python backend.

The project is currently in early public testing. macOS is the primary maintained platform, and Windows packaging is being added through a reproducible GitHub Actions release path.

## License

This project is licensed under the GNU Affero General Public License v3.0 only. See [LICENSE](LICENSE).

## Repository

- Source repository: <https://github.com/guyuan9300-max/yiyu-thinktank-workbench>
- Official website and downloads: <https://www.yiyu.love/>
- Public update assets are distributed from the official Yiyu release source, not from GitHub Release assets.

## Architecture

- `src/`: Electron main process, preload bridge, shared code, and React renderer.
- `backend/`: Local Python service for file processing, knowledge workflows, and local AI integration.
- `cloud_backend/`: Shared organization collaboration service used by the workbench.
- `scripts/`: Build, packaging, release, update-feed, and verification helpers.

The desktop package embeds a platform-specific runtime seed in `dist/packaged-runtime` before Electron Builder creates the installer.

## Development

Requirements:

- Node.js 22 or later
- npm
- Python 3.11
- uv
- macOS arm64 for macOS release builds, or Windows x64 for Windows release builds

Install dependencies:

```bash
npm ci
```

Run the local desktop app:

```bash
npm run dev
```

Build validation:

```bash
npm run build:main -- --pretty false
npm run build:renderer
npm run build:backend-check
```

## Collaboration

If you want to claim or contribute to a public co-building task, please read [《协作开发指引》](docs/%E3%80%8A%E5%8D%8F%E4%BD%9C%E5%BC%80%E5%8F%91%E6%8C%87%E5%BC%95%E3%80%8B.md) first.

## macOS Release Build

macOS release builds must be signed with a Developer ID Application certificate and notarized with Apple before they are published.

```bash
npm run release:mac
```

After verification, the release maintainer uploads the signed assets to the official release source and publishes them through the website release center.

## Windows Release Build

Windows release builds are produced from the same Git tag as macOS. The target installer is an NSIS x64 installer.

Build locally on Windows:

```powershell
npm ci
npm run build:packaged-runtime
npm run release:windows
```

Unsigned Windows installers are acceptable only for short internal tests. Official website downloads and automatic updates should use signed installers.

The preferred Windows signing path is SignPath for open-source builds. See:

- [Code signing policy](docs/code-signing-policy.md)
- [SignPath application notes](docs/signpath-application.md)

After SignPath signs the installer, regenerate Windows update metadata because signing changes the installer hash:

```powershell
npm run release:windows:refresh-metadata -- --exe "dist\\yiyu-workbench-0.3.1-x64-setup.exe"
```

Then upload the signed installer, refreshed blockmap, and refreshed `latest.yml` to the official Windows update prefix.

## Release Model

The intended release model is:

1. Merge all source changes into `main`.
2. Create one annotated Git tag for the release, for example `v0.3.2`.
3. Build platform installers from that exact tag.
4. Sign and notarize/sign each platform artifact.
5. Upload signed assets to the official release source.
6. Publish the corresponding platform package from the website release center.

GitHub is the source and tag baseline. Ordinary user installers are distributed from the official website and update source.

## Security Notes

Do not commit production secrets, signing certificates, private keys, database dumps, `.env` files, internal logs, or customer data.

The repository intentionally ignores common certificate and secret file extensions. Release credentials should live only in local secure storage, GitHub Secrets, SignPath configuration, or the server-side deployment environment.
