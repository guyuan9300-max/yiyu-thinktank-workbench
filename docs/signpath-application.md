# SignPath Application Notes

These notes are intended for the release maintainer when applying for SignPath open-source signing.

## Project Information

- Project name: Yiyu Thinktank Workbench
- Repository URL: <https://github.com/guyuan9300-max/yiyu-thinktank-workbench>
- License: GNU Affero General Public License v3.0 only
- Build system: GitHub Actions
- Artifact: Windows NSIS x64 installer, for example `yiyu-workbench-0.3.2-x64-setup.exe`
- Intended signer: SignPath Foundation is acceptable for the open-source Windows build.

## Suggested Application Description

Yiyu Thinktank Workbench is an open-source Electron desktop application for public-interest organization collaboration, local knowledge workflows, and research operations. The Windows installer is built from the public GitHub repository using GitHub Actions. We are requesting open-source code signing to reduce Windows SmartScreen and unsigned installer warnings, and to make public release artifacts traceable to the public source repository and Git tag.

## Repository Readiness Checklist

- The repository is public.
- `LICENSE` is present and uses an OSI-approved license.
- `README.md` explains the project purpose, build commands, and release model.
- `docs/code-signing-policy.md` explains how builds are signed and published.
- No production secrets, certificates, logs, database dumps, or customer data are committed.
- Windows build workflow exists under `.github/workflows/`.

## After Approval

Create SignPath project settings for:

- Project slug: `yiyu-thinktank-workbench`
- Artifact configuration: Windows NSIS installer
- Signing policy: release signing from GitHub Actions trusted build

Then add the required SignPath values as GitHub Secrets or repository variables. Do not write them into source files.

After the signed installer is returned, run:

```powershell
npm run release:windows:refresh-metadata -- --exe "dist\\yiyu-workbench-0.3.2-x64-setup.exe"
```

This regenerates update metadata from the signed installer.

## Temporary Unsigned Builds

If approval is not ready in time, an unsigned Windows installer can be uploaded to the website only as a clearly marked internal testing package. It should not be published as the official public Windows update feed.
