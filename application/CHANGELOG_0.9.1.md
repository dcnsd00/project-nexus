# NEXUS 0.9.1

- Added official upstream Miner Pack manager for XMRig, SRBMiner-MULTI, T-Rex, lolMiner, GMiner and Rigel using GitHub Releases API.
- Added TeamRedMiner official-page link only; no third-party mirror download.
- Added safe ZIP extraction checks (path traversal, file count, uncompressed size) and expected executable validation.
- Added SHA-256 calculation and upstream digest comparison when provided. Local-only hashes are clearly labelled and are not presented as publisher authentication.
- Added dashboard controls to check versions, download and install packages, and refresh inventory.
- Installed binaries are not automatically executed.
- NEXUS-managed miner paths are included in local binary discovery.
- Added installer tests.
