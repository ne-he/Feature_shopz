# Data Directory

This directory holds raw and processed datasets. **No data files are committed to git**
(see the project root `.gitignore`); only this README and `.gitkeep` placeholders are tracked.

## Layout

| Path | Purpose | Git-tracked? |
|------|---------|--------------|
| `data/raw/` | Original, untouched source data | No (gitignored) |
| `data/processed/` | Cleaned/validated data produced by the ingestion layer | No (gitignored) |

## Obtaining the Dataset

The project uses the **E-Commerce Synthetic Dataset** (Kaggle, synthetic, CC0 Public Domain).

- **File name:** `ecommerce_synthetic_dataset.csv`
- **Size:** ~17 MB, 100,000 rows, 21 columns
- **Expected location:** `data/raw/ecommerce_synthetic_dataset.csv`

### Setup steps

The dataset file currently lives in the **project root**. Move it into place:

```bash
# from the project root
mv ecommerce_synthetic_dataset.csv data/raw/ecommerce_synthetic_dataset.csv
```

On Windows PowerShell:

```powershell
Move-Item ecommerce_synthetic_dataset.csv data\raw\ecommerce_synthetic_dataset.csv
```

If you are setting up the project fresh and do not have the file, download it from
the Kaggle source referenced in `PRD.md § 6` and place it at the path above.

## Notes

- `data/raw/` is the input for the ingestion layer (`src/ingestion/`).
- `data/processed/` is written by `src/ingestion/cleaner.py` after schema validation
  and quirk handling (e.g. clipping `ReviewScore` to `[1.0, 5.0]`).
