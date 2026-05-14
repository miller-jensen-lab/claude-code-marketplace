---
name: tabular-data
description: Query, transform, and analyze CSV/TSV/Excel/Parquet files for Miller-Jensen lab work — DuckDB SQL on any file as the default, qsv/xlsx2csv/Polars for the few cases where DuckDB isn't ideal. TRIGGER when working with .csv, .tsv, .xlsx, .parquet, .json files; sample sheets, FCS exports, count matrices, gene-list exports.
related:
  - coding-in-python
  - coding-in-r
  - bio-data-hygiene
  - plotting
updated: 2026-05-14
---
# Tabular data

For lab tabular data, **DuckDB first**. SQL syntax, runs on `.csv` / `.tsv` / `.xlsx` / `.parquet` / `.json` without conversion. Same engine via CLI or Python — pick whichever is convenient.

Reach for Polars only when you need a Python function that DuckDB SQL can't express cleanly. Reach for pandas only when an existing analysis already uses it and switching is not worth the diff.

## CLI default — `duckdb`

Install: `brew install duckdb`. Then SQL-anything:

```bash
# preview
duckdb -c "SELECT * FROM 'data/raw/counts.csv' LIMIT 10"

# columns + types
duckdb -c "DESCRIBE SELECT * FROM 'data/raw/counts.csv'"

# filter
duckdb -c "SELECT * FROM 'data/raw/de_results.csv' WHERE padj < 0.05 AND log2FoldChange > 1"

# aggregate by group (e.g., cells per cluster)
duckdb -c "SELECT cluster, COUNT(*) AS n_cells FROM 'data/derived/clusters.parquet' GROUP BY cluster ORDER BY n_cells DESC"

# search text (case-insensitive)
duckdb -c "SELECT * FROM 'genes.tsv' WHERE symbol ILIKE 'IFN%'"

# distinct values
duckdb -c "SELECT DISTINCT sample_id FROM 'sample_sheet.csv'"

# sort
duckdb -c "SELECT gene, log2FoldChange, padj FROM 'de_results.csv' ORDER BY log2FoldChange DESC LIMIT 50"

# join two files on a key
duckdb -c "SELECT s.condition, d.gene, d.log2FoldChange
           FROM 'sample_sheet.csv' s
           JOIN 'de_results.csv' d ON s.sample_id = d.sample_id"

# export to CSV / Parquet
duckdb -c "COPY (SELECT * FROM 'de_results.csv' WHERE padj < 0.05) TO 'results/significant_genes.csv'"
duckdb -c "COPY (SELECT * FROM 'de_results.csv') TO 'data/derived/de_results.parquet'"
```

## Convert once to Parquet, query forever

When a CSV/XLSX is going to be queried more than once, convert it to Parquet first. Tenfold size reduction, hundredfold query speedup, preserves dtypes (no `"NA"` → string accidents).

```bash
duckdb -c "COPY (SELECT * FROM 'huge.csv') TO 'huge.parquet'"
# from now on
duckdb -c "SELECT * FROM 'huge.parquet' WHERE …"
```

For a directory of per-sample CSVs:

```bash
duckdb -c "COPY (SELECT * FROM 'data/raw/*.csv') TO 'data/derived/combined.parquet'"
```

## Cleaning messy data (sample sheets, exported FCS tables, etc.)

```bash
# trim whitespace + normalize case for dedup
duckdb -c "SELECT TRIM(LOWER(sample_id)) AS sample_id FROM 'samples.csv'"

# treat 'NA' / 'N/A' / '' as NULL
duckdb -c "SELECT NULLIF(NULLIF(NULLIF(value, 'NA'), 'N/A'), '') AS value FROM 'data.csv'"

# fallback for missing values
duckdb -c "SELECT COALESCE(condition, 'unknown') AS condition FROM 'samples.csv'"

# split a compound field
duckdb -c "SELECT SPLIT_PART(well, '_', 1) AS plate, SPLIT_PART(well, '_', 2) AS well_id FROM 'samples.csv'"

# strip non-numeric (clean up pasted IDs)
duckdb -c "SELECT REGEXP_REPLACE(barcode, '[^ACGT]', '', 'g') AS barcode FROM 'samples.csv'"

# safe type conversion (bad values → NULL, no error)
duckdb -c "SELECT TRY_CAST(count AS INTEGER) AS count FROM 'data.csv'"

# combine columns
duckdb -c "SELECT donor || '_' || timepoint AS sample FROM 'samples.csv'"
```

## Excel-specific reads

```bash
# specific sheet by name
duckdb -c "SELECT * FROM read_xlsx('lab_book.xlsx', sheet='Plate3')"

# skip header rows / cell range
duckdb -c "SELECT * FROM read_xlsx('readouts.xlsx', range='A5:Z')"

# ignore_errors=true makes bad cells NULL instead of failing
duckdb -c "SELECT * FROM read_xlsx('messy.xlsx', ignore_errors=true)"

# list all sheets
duckdb -c "SELECT * FROM xlsx_sheets('lab_book.xlsx')"
```

Excel is fine for hand-curated sample sheets. It is **not** fine for analysis outputs — Excel silently mangles gene names (`SEPT2` → date, `MARCH1` → date), reorders rows when sorted, and corrupts large numbers. Export to CSV/Parquet before any downstream tool.

## Output formats

```bash
duckdb -box   -c "SELECT * FROM 'data.csv' LIMIT 5"   # pretty ascii table
duckdb -csv   -c "SELECT * FROM 'data.csv'"            # CSV to stdout
duckdb -json  -c "SELECT * FROM 'data.csv'"            # JSON
duckdb -markdown -c "SELECT * FROM 'data.csv' LIMIT 5" # markdown table (paste into a report)
```

## Python — same SQL, plus method chaining

```python
# uv run --with duckdb python3 script.py
import duckdb

# SQL on a file
sig = duckdb.sql("""
    SELECT gene, log2FoldChange, padj
    FROM 'data/derived/de_results.parquet'
    WHERE padj < 0.05 AND ABS(log2FoldChange) > 1
    ORDER BY log2FoldChange DESC
""")
sig.show()

# Relational API — lazy, pythonic
top_genes = (
    duckdb.read_parquet("data/derived/de_results.parquet")
        .filter("padj < 0.05")
        .order("log2FoldChange DESC")
        .limit(50)
)

# Output options
df = top_genes.df()       # pandas DataFrame
pl = top_genes.pl()       # Polars DataFrame
top_genes.write_parquet("results/top_genes.parquet")
```

## Other tools — when DuckDB isn't ideal

| Need | Tool |
|---|---|
| Quick stats / column profile | `qsv stats data.csv`, `qsv frequency data.csv -s column` |
| xlsx → csv only (no querying) | `xlsx2csv data.xlsx > data.csv` |
| Interactive exploration / hand-edit | `visidata data.csv` or `qsv lens` |
| Custom Python row-level function | **Polars** with `map_elements` (see below) |
| Anything `.h5ad` (scanpy native) | `anndata` + `scanpy` directly; DuckDB can't read it |

### Polars — when you need a Python function over rows

```python
# uv run --with 'polars[excel],dateparser' python3 script.py
import polars as pl
import dateparser

df = pl.read_excel("samples.xlsx")

# Parse messy dates ("Jan 5 2024", "1/5/24", "2024-01-05") → ISO
df = df.with_columns(
    pl.col("collection_date")
      .map_elements(lambda s: str(dateparser.parse(s).date()) if s else None,
                    return_dtype=pl.Utf8)
      .str.to_date()
      .alias("collection_date_clean")
)
```

### qsv — fast CSV-specific tools

```bash
qsv stats data.csv           # mean/min/max/quartiles per column
qsv frequency data.csv -s condition   # value counts for one column
qsv dedup data.csv > dedup.csv
qsv sort -s padj data.csv > sorted.csv
qsv search -s gene "^IFN" data.csv    # regex on a column
```

## Anti-patterns (lab edition)

- **`pandas.read_excel` on a >100 MB file.** DuckDB or Polars; pandas is glacial.
- **Genes-as-rows + samples-as-columns in CSV with no header.** Output a proper sample sheet alongside, and always include a header row.
- **`np.nan` written to CSV without `na_rep`.** Becomes the string `"nan"` on read-back. Use `na_rep=""` or write Parquet.
- **Sorting an Excel sheet manually** then committing it as "cleaned data." The sort can desync columns silently — committed sample sheets must come from a script.
- **Loading a 5 GB CSV into memory** to compute one mean. `duckdb -c "SELECT AVG(x) FROM 'file.csv'"` streams it.

## Checklist

- [ ] Raw CSV/XLSX preserved untouched in `data/raw/`
- [ ] Repeated queries → Parquet snapshot in `data/derived/`
- [ ] Sample sheet committed (small, hand-curated); count matrices and other large tables gitignored
- [ ] No Excel-roundtripped gene names (`SEPT2`, `MARCH1`) in the corpus

## Further reading

- [DuckDB docs](https://duckdb.org/docs/)
- [DuckDB `llms.txt`](https://duckdb.org/llms.txt) — for LLM consumption
- [Polars user guide](https://docs.pola.rs/)
- [qsv](https://github.com/jqnatividad/qsv) — `qsv --list`
- [xlsx2csv](https://github.com/dilshod/xlsx2csv)
- [visidata](https://www.visidata.org/) — interactive TUI
- [Gene name errors are widespread (Ziemann et al. 2016)](https://genomebiology.biomedcentral.com/articles/10.1186/s13059-016-1044-7) — the Excel-mangles-gene-names paper
