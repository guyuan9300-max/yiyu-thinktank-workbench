# Code Signing Policy

This policy describes how Yiyu Thinktank Workbench release artifacts should be built, signed, and published.

## Goals

- Make every official installer traceable to a public Git commit and tag.
- Keep signing credentials out of the repository and out of application bundles.
- Ensure update metadata is generated from the final signed artifact.
- Avoid publishing unsigned installers as official public downloads.

## Release Baseline

Official releases must start from a clean `main` branch and an annotated Git tag, for example:

```bash
git checkout main
git pull --ff-only
git tag -a v0.3.2 -m "Yiyu Thinktank Workbench v0.3.2"
git push origin v0.3.2
```

The tag is the cross-platform source baseline. macOS, Windows, and future mobile artifacts for the same version should be built from that exact tag.

## macOS Signing

macOS artifacts are signed with the Yiyu Apple Developer ID Application certificate and notarized by Apple.

Required local secrets:

- Apple Developer ID Application certificate in the login keychain.
- App Store Connect API key stored outside the repository.
- Required Apple issuer/key identifiers stored in local environment or secure release configuration.

The signed and notarized `.dmg`, `.zip`, `.blockmap`, and update metadata are the only macOS artifacts that should be published as official update assets.

## Windows Signing

Windows artifacts should be signed before public release. The preferred path is SignPath open-source signing through GitHub Actions.

Expected Windows signing flow:

1. GitHub Actions builds an unsigned NSIS x64 installer from the release tag.
2. The unsigned installer is submitted to SignPath.
3. SignPath returns a signed installer.
4. `npm run release:windows:refresh-metadata` regenerates `latest.yml` and `.blockmap` from the signed installer.
5. The signed installer and refreshed update metadata are uploaded to the official Windows update source.

Unsigned Windows installers may be used only for short internal compatibility checks. They should not be set as the official public Windows download or automatic update target.

## Update Metadata Rule

Signing can change an installer hash. Therefore, update metadata must always be generated from the final artifact:

- macOS: generate/update metadata after signing and notarization.
- Windows: regenerate `latest.yml` and `.blockmap` after Authenticode or SignPath signing.

## Secret Handling

Never commit:

- Apple Developer certificates or API keys.
- Windows PFX/P12 certificates or passwords.
- SignPath API tokens.
- Cloud storage AK/SK credentials.
- Production `.env` files, database dumps, internal logs, or customer data.

Allowed secret storage locations:

- Local keychain or secure password manager.
- GitHub repository secrets.
- SignPath project configuration.
- Server-side environment variables on the official website/auth API host.

## Publishing Channels

- GitHub: public source code, issues, documentation, and Git tags.
- Official website: user-facing download and release center.
- TOS release source: authoritative installer assets and automatic update metadata.
- Directed push: organization-specific assignment records and private variants, resolved by the central website release API.

GitHub Release assets are optional and are not part of the ordinary user download path.
