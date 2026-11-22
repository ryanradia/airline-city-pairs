# Raw data (not committed)

Put the 12 monthly BTS DB1C Market ZIPs here, July 2025 through June 2026, exactly as downloaded from
https://www.bts.gov/topics/airlines-and-airports/origin-and-destination-survey-data-market

```
DB1C.MARKET.202507.*.zip … DB1C.MARKET.202606.*.zip
```

They total about 18 GB. `results/input_manifest_*.csv` records the filenames and SHA-256 checksums
used for the published results. The script reads them in place and never modifies them.
