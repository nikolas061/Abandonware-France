# Project Legacy Files

Historical project additions are tracked by:

```sh
python3 tools/lolg_project_legacy_inventory.py -o output/project_legacy_inventory
```

The report keeps old scripts, notes, configs, mod archives, HD asset trees,
runtime overrides, extracted references, and diagnostic previews visible without
copying or moving the large files.

Generated files:

```text
output/project_legacy_inventory/index.html
output/project_legacy_inventory/summary.csv
output/project_legacy_inventory/manifest.csv
```

The default scan window is from `2026-05-01` up to, but not including,
`2026-06-15`, which captures the earlier project work before the current
decoder/reporting batch.
