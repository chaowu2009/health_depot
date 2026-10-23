# Vendored front-end files

All JavaScript and CSS is stored in this repository and served by the app. Nothing loads from
a CDN or external font service at runtime (required for offline demos and government networks).

| Library | Version | File | Source |
|---|---|---|---|
| htmx | 2.0.11 | `src/static/vendor/htmx.min.js` | npm `htmx.org` |
| Alpine.js | 3.17.4 | `src/static/vendor/alpine.min.js` | npm `alpinejs` (`dist/cdn.min.js`) |
| Chart.js | 4.5.1 | `src/static/vendor/chart.umd.min.js` | npm `chart.js` |
| SortableJS | 1.15.7 | `src/static/vendor/Sortable.min.js` | npm `sortablejs` |
| Tailwind CSS | 4.3.3 | build-time only (`package.json`); output `src/static/css/app.css` | npm `@tailwindcss/cli` |

Fonts: system font stack only (no downloaded fonts).

Source-map comments (`//# sourceMappingURL=...`) are removed from vendored files because the map files are not shipped. Checksums (after that change): `src/static/vendor/SHA256SUMS`. Verify with `sha256sum -c SHA256SUMS` from that folder.
To upgrade a library: download the new file, update this table and the checksum, and test.
