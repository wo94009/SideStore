# Chinese Settings Build — v5 verification record

Build: GitHub Actions `Chinese Settings Build` run #2 (2026-10-08), branch `LiveContainerSupport`.

## Verified offline

- ZIP CRC, duplicate entries, NIB structure and reference integrity (66 NIBs)
- Mach-O load commands (15 ARM64 files, no SideStoreZH.dylib references)
- Compiled translation catalog marker present in framework binary
- LiveContainer 334 localized keys preserved

## Counts

- SideStore localization keys: 2213
- LiveContainer Chinese keys: 334
- NIB resources changed: 66 (see verification_v5.json in local sidestore_zh/output/)

## Note

SHA256.txt artifact value disagreed with the actual zip (stale cache in CI `artifacts/`
dir). Workflow fixed: `rm -f SideStoreApp-zh.zip SHA256.txt` before `zip -qry` + `shasum`.

## Not yet verified

- Device install and launch (requires re-signing with iloader)
- Settings sub-page Chinese display on real hardware
