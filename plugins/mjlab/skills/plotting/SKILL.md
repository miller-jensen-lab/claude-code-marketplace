---
name: plotting
description: Publication-quality plotting for Miller-Jensen lab work — opinionated defaults for ggplot2 (R) and matplotlib/seaborn (Python), colorblind-safe palettes, figure dimensions for journals, statistical annotations, and the lab plots students actually need (dose-response, time-course, UMAP, heatmap, volcano, SuperPlot). TRIGGER when making any figure (.pdf, .svg, .png), styling axes, picking a palette, faceting, saving for a paper, or working in ggplot2 / matplotlib / seaborn / ComplexHeatmap / patchwork.
related:
  - coding-in-python
  - coding-in-r
  - bio-stats
  - tabular-data
updated: 2026-05-14
---
# Plotting

A figure is the unit of scientific communication. Reviewers see it before they read the methods. Students lose months of work to figures that look fine in RStudio but fall apart at journal width with a colorblind co-author. This skill is the lab's opinionated kit: ggplot2 (R) when the pipeline is R, matplotlib + seaborn (Python) when the pipeline is Python. Same principles either way.

Two non-negotiables:

1. **Show the data.** Replicates as dots, summary as a small overlay. Never a bar plot of means alone (Weissgerber 2015). For replicated cell-biology data with technical sub-samples, use a SuperPlot (Lord et al. 2020).
2. **Save programmatically with explicit dimensions.** Never "export from the Plots pane." A figure that depends on a viewport is not reproducible.

For data wrangling before plotting, see [tabular-data](../tabular-data/SKILL.md). For the tests behind the asterisks, see [bio-stats](../bio-stats/SKILL.md).

## The defaults

A short kit that applies to every figure you make:

- **Format**: PDF or SVG (vector) for paper figures. PNG only for slides and the lab Slack. Raster a figure only when it contains a >1 megapixel image (microscopy, heatmap with 10k cells).
- **Palette**: Okabe-Ito for ≤8 discrete categories; viridis (or its variants `magma`, `plasma`, `cividis`) for continuous; ColorBrewer `RdBu` diverging for signed quantities (log2FC, z-scores).
- **Resolution**: 300 DPI for any raster element; 600 DPI for line art the journal will print B/W.
- **Width**: 89 mm single-column, 183 mm double-column (Nature). 85 mm / 174 mm (Cell). Stick to these; resizing in InDesign blurs your text.
- **Theme**: `theme_classic()` or `theme_bw()` in R; `seaborn.set_theme(style="ticks", context="paper")` in Python. Never ship a journal figure with the gray ggplot default.
- **Type**: sans-serif (Helvetica, Arial, DejaVu Sans). 7-9 pt for axis text, 8-10 pt for labels, matching journal house style.
- **Encoding**: never color alone for n>1 series — pair it with shape (points) or linetype (lines) so the figure survives B/W printing and CVD readers.

## R — ggplot2

### Setup and a lab theme

```r
library(ggplot2)
library(patchwork)   # combine panels
library(ggrepel)     # non-overlapping labels
library(scales)      # log breaks, comma format

# Okabe-Ito, in canonical order
OKABE_ITO <- c("#E69F00", "#56B4E9", "#009E73", "#F0E442",
               "#0072B2", "#D55E00", "#CC79A7", "#000000")

theme_mj <- function(base_size = 8) {
  theme_classic(base_size = base_size, base_family = "Helvetica") +
    theme(
      axis.text   = element_text(color = "black"),
      axis.ticks  = element_line(color = "black"),
      strip.background = element_blank(),
      strip.text  = element_text(face = "bold"),
      legend.key.size = unit(3, "mm"),
      plot.title  = element_text(face = "bold", size = base_size + 1)
    )
}
theme_set(theme_mj())
```

### Palettes by use-case

- **Discrete (≤8 levels)**: `scale_color_manual(values = OKABE_ITO)`. Or install `ggokabeito` and call `scale_color_okabe_ito()`.
- **Continuous, sequential**: `scale_color_viridis_c(option = "viridis")` (use `"magma"` for dark backgrounds, `"cividis"` if you need maximum CVD safety including monochromacy).
- **Diverging (log2FC, z-scores)**: `scale_fill_distiller(palette = "RdBu", limits = c(-x, x))`. Always symmetric around zero — center the scale.
- **Many qualitative categories (>8)**: `MetBrewer::met.brewer("Egypt")` or `paletteer` for a curated, CVD-aware extra. If you have >12 categories, the plot is wrong; facet instead.

Avoid: `rainbow()`, `scale_color_gradientn(colors = rainbow(n))`, `jet`, `Set1` on continuous data.

### Saving — units in mm, dpi explicit

```r
ggsave("results/fig2a_dose_response.pdf",
       plot   = p,
       width  = 89, height = 60, units = "mm",
       device = cairo_pdf)        # cairo embeds fonts cleanly

# PNG companion for slides
ggsave("results/fig2a_dose_response.png",
       plot = p, width = 89, height = 60, units = "mm", dpi = 300)
```

`cairo_pdf` is worth the one-time setup — it embeds fonts so the figure renders identically on the editor's machine. Default `pdf()` uses Type 1 fonts and breaks on uncommon glyphs.

### Faceting vs. combining

- **`facet_wrap`/`facet_grid`** when subplots share axes and you're showing the same plot across a variable. Shared scales, one legend, free `y` only when biologically justified (`scales = "free_y"`).
- **`patchwork`** when subplots are unrelated and form a figure panel.

```r
(p_umap | p_violin) /
  (p_heatmap)       +
  plot_annotation(tag_levels = "a") &
  theme(plot.tag = element_text(face = "bold"))
```

### Statistical annotations — match the test you actually ran

```r
library(ggpubr)
ggboxplot(df, x = "condition", y = "expression", add = "jitter") +
  stat_compare_means(comparisons = list(c("ctrl", "TNF"), c("ctrl", "IL4")),
                     method = "wilcox.test", paired = TRUE)
```

`ggpubr`/`ggsignif` will happily draw stars for whatever default test they pick (often unpaired Wilcoxon). If you ran a mixed model with `lmer` + `emmeans`, draw the brackets manually using `geom_signif(annotations = ...)` with p-values you computed. Asterisks that don't match your stats are a paper-killer in review. See [bio-stats](../bio-stats/SKILL.md).

### Lab plots — concise recipes

**Dose-response.** Fit with `drc::drm` (4-parameter log-logistic is the default for cytokine/inhibitor curves), then plot fit + replicates:

```r
library(drc)
fit <- drm(response ~ dose, data = df, fct = LL.4())
newx <- 10^seq(log10(min(df$dose)), log10(max(df$dose)), length.out = 200)
pred <- predict(fit, newdata = data.frame(dose = newx), interval = "confidence")
ggplot() +
  geom_ribbon(aes(newx, ymin = pred[,"Lower"], ymax = pred[,"Upper"]), alpha = 0.2) +
  geom_line(aes(newx, pred[,"Prediction"])) +
  geom_point(aes(dose, response), data = df) +
  scale_x_log10()
```

**Time-course with replicates.** Show every replicate trace, with a mean overlay:

```r
ggplot(df, aes(time, value, group = donor, color = condition)) +
  geom_line(alpha = 0.3) +
  stat_summary(aes(group = condition), fun = mean, geom = "line", linewidth = 1) +
  scale_color_manual(values = OKABE_ITO)
```

**UMAP (Seurat / SCE).** Strip non-data ink:

```r
DimPlot(obj, reduction = "umap", label = TRUE, repel = TRUE) +
  theme_void() + NoLegend() +
  coord_fixed()
```

**Heatmap.** Use `ComplexHeatmap` for anything with row/column annotations (donor, condition, cell type). `pheatmap` is fine for a 50×10 quick look. `ComplexHeatmap` handles split rows/columns, multiple annotation tracks, and clusters that don't lie.

**Volcano.** Hand-roll — `EnhancedVolcano` looks like every other paper's:

```r
res |>
  mutate(sig = padj < 0.05 & abs(log2FoldChange) > 1) |>
  ggplot(aes(log2FoldChange, -log10(padj), color = sig)) +
  geom_point(size = 0.6, alpha = 0.6) +
  geom_text_repel(aes(label = ifelse(sig, gene, "")), max.overlaps = 20, size = 2.5) +
  scale_color_manual(values = c("grey70", "#D55E00"))
```

**SuperPlot** (Lord et al. 2020). For repeated experiments (donors, biological replicates) each with many technical sub-samples (cells, wells): plot every sub-sample as a small dot colored by replicate, then overlay the per-replicate mean as a large symbol, and run statistics on the replicate-level means — not on the cells. This is the lab-bench equivalent of pseudobulk DE.

```r
ggplot(cells, aes(condition, value)) +
  geom_jitter(aes(color = factor(donor)), width = 0.15, alpha = 0.4, size = 0.6) +
  stat_summary(aes(group = donor, fill = factor(donor)),
               fun = mean, geom = "point", shape = 21, size = 3, color = "black") +
  scale_color_manual(values = OKABE_ITO) +
  scale_fill_manual(values = OKABE_ITO)
```

## Python — matplotlib + seaborn

### Setup and theme

```python
import matplotlib.pyplot as plt
import seaborn as sns
from cycler import cycler

OKABE_ITO = ["#E69F00", "#56B4E9", "#009E73", "#F0E442",
             "#0072B2", "#D55E00", "#CC79A7", "#000000"]

sns.set_theme(style="ticks", context="paper", font_scale=1.0)
plt.rcParams.update({
    "font.family": "Helvetica",     # or "DejaVu Sans" if Helvetica missing
    "pdf.fonttype": 42,             # embed TrueType, not Type 3
    "ps.fonttype": 42,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.prop_cycle": cycler(color=OKABE_ITO),
    "savefig.bbox": "tight",
    "savefig.dpi": 300,
})
```

The `fonttype: 42` line is the one nobody tells you about. Without it, Illustrator can't edit text in your exported PDF.

### Palettes

- Discrete: pass `palette=OKABE_ITO` to any seaborn call, or rely on the default cycler set above.
- Continuous: `cmap="viridis"` (or `"magma"`, `"cividis"`). Never `"jet"`, never `"rainbow"`.
- Diverging: `cmap="RdBu_r"` with `vmin=-x, vmax=x` symmetric.

### Saving

```python
fig.set_size_inches(89 / 25.4, 60 / 25.4)   # mm -> inches
fig.savefig("results/fig2a.pdf")             # vector, fonts embedded
fig.savefig("results/fig2a.png", dpi=300)    # slides
```

Always `set_size_inches` before saving — `bbox_inches="tight"` only trims margins, it doesn't make the figure the size you asked for.

### Combining panels

`patchwork` doesn't exist in Python. Use `plt.subplots` with `gridspec_kw`, or the modern `plt.subplot_mosaic` API:

```python
fig, axd = plt.subplot_mosaic(
    [["a", "a", "b"],
     ["c", "c", "c"]],
    figsize=(183 / 25.4, 120 / 25.4),
    gridspec_kw={"height_ratios": [1, 1.2]},
)
sns.scatterplot(..., ax=axd["a"])
sns.violinplot(..., ax=axd["b"])
sns.heatmap(..., ax=axd["c"])
for label, ax in axd.items():
    ax.set_title(label, loc="left", fontweight="bold")
```

### Statistical annotations

`statannotations` is the current canonical tool — successor to the abandoned `statannot`. Same caveat as `ggpubr`: it will run its own test by default. For mixed-model p-values, pass them via `custom_annotations`.

```python
from statannotations.Annotator import Annotator
pairs = [("ctrl", "TNF"), ("ctrl", "IL4")]
ax = sns.boxplot(data=df, x="condition", y="value")
sns.stripplot(data=df, x="condition", y="value", color="black", size=2, ax=ax)
ann = Annotator(ax, pairs, data=df, x="condition", y="value")
ann.configure(test="Wilcoxon", text_format="star", loc="inside")
ann.apply_and_annotate()
```

### Lab plots — concise recipes

**Dose-response.** `scipy.optimize.curve_fit` on a 4-PL function, or `lmfit` for richer reporting. Plot the fit as a curve on a log-x axis with replicate dots overlaid.

**Time-course.** `sns.lineplot(..., estimator="mean", errorbar=("se", 1))` with `sns.stripplot` for replicates underneath. Pass `units="donor"` to draw per-donor traces.

**UMAP (scanpy).** `sc.pl.umap(adata, color=...)` is fine for QC. For paper finals, get the coordinates out and replot in matplotlib so you control the font, legend, and aspect ratio:

```python
coords = adata.obsm["X_umap"]
df = pd.DataFrame({"x": coords[:,0], "y": coords[:,1], "cluster": adata.obs["leiden"]})
fig, ax = plt.subplots(figsize=(80/25.4, 80/25.4))
sns.scatterplot(df, x="x", y="y", hue="cluster", palette=OKABE_ITO,
                s=2, linewidth=0, ax=ax, legend=False)
ax.set_aspect("equal"); ax.set_axis_off()
```

**Heatmap.** `sns.clustermap` for ≤a few thousand rows. For annotated, split, or large heatmaps, the R `ComplexHeatmap` ecosystem is genuinely better; `PyComplexHeatmap` is the Python port if you must stay in one language.

**Volcano.** Hand-roll with matplotlib + `adjustText` for label collision avoidance:

```python
sig = (res["padj"] < 0.05) & (res["log2FoldChange"].abs() > 1)
ax.scatter(res["log2FoldChange"], -np.log10(res["padj"]),
           c=np.where(sig, "#D55E00", "lightgrey"), s=4, alpha=0.6)
```

**SuperPlot in Python.** Same logic as the R recipe: every cell as a small jittered dot colored by donor, donor means as large outlined markers, statistics on the donor means.

```python
ax = sns.stripplot(data=cells, x="condition", y="value",
                   hue="donor", palette=OKABE_ITO, size=2, alpha=0.4,
                   jitter=0.15, dodge=False, legend=False)
means = cells.groupby(["condition", "donor"], as_index=False)["value"].mean()
sns.stripplot(data=means, x="condition", y="value",
              hue="donor", palette=OKABE_ITO, size=8,
              edgecolor="black", linewidth=0.8, jitter=False, ax=ax, legend=False)
```

## Colorblind safety

~8% of men of European descent have a red-green color vision deficiency. If you only encode by color, ~1 in 12 reviewers can't read your figure.

- Default to Okabe-Ito or viridis. Both are safe for deuteranopia, protanopia, and tritanopia.
- Always add a second channel: shape (`geom_point(aes(shape = ...))`, seaborn `style=`), linetype, or direct text labels.
- Simulate before submitting: `colorBlindness::cvdPlot(p)` in R; the [Coblis](https://www.color-blindness.com/coblis-color-blindness-simulator/) web tool for any image; the macOS accessibility filter.

## Journal-spec dimensions

Verify against the current author guide before final submission; specs drift. As of May 2026:

| Journal       | Single col | 1.5 col   | Double col | Min font  | DPI (color) |
|---------------|-----------:|----------:|-----------:|----------:|------------:|
| Nature family |     89 mm  | 120-136 mm|    183 mm  | 5-7 pt    | 300         |
| Cell family   |     85 mm  | 114 mm    |    174 mm  | 6-8 pt    | 300         |
| eLife         | ≥100 mm    | flexible  | ≥200 mm    | flexible  | 300         |
| PLOS          |    83.5 mm | 132 mm    |    190.5 mm| 8 pt min  | 300         |
| Sci Rep       |     89 mm  | -         |    183 mm  | 8 pt min  | 300         |
| JCB (RUP)     |     85 mm  | -         |    175 mm  | 8 pt      | 300         |

Maximum page height for Nature figures is 170 mm (legend has to fit underneath).

## Common mistakes

- **Bar plot of means without the data.** Always show replicate dots overlaid; for cell-biology with technical sub-samples, use a SuperPlot. The bar can stay; alone, it can't.
- **Default ggplot gray theme on a journal submission.** Switch to `theme_classic()` / `theme_bw()` and remove `panel.grid.minor`.
- **Rainbow/jet on a continuous variable.** Viridis or magma. Rainbow is perceptually non-uniform and unreadable in CVD.
- **PNG at 72 DPI to a journal.** Screen resolution. Save vector (PDF/SVG); PNG only at 300 DPI minimum and only for raster content.
- **Color-only encoding.** Add shape or linetype for every series the reader needs to distinguish.
- **`ggsave()` without `width`/`height`.** The figure dimensions then depend on the RStudio Plots pane size. Always specify `width`, `height`, `units = "mm"`.
- **Exporting from the Plots pane / Jupyter inline.** Reach for `ggsave()` or `fig.savefig()`. The export menu is for screenshots, not for figures.
- **Dual y-axes.** Almost always misleading — the reader has no anchor for the right axis. Use two stacked panels or normalize to the same scale.
- **Asterisks that don't match your test.** `stat_compare_means(method = "wilcox")` runs an unpaired Wilcoxon by default. If your design is paired, or if you ran a mixed model, hand the p-values in. See [bio-stats](../bio-stats/SKILL.md).
- **`pdf.fonttype` left at default in matplotlib.** Type 3 fonts ship as outlines that Illustrator can't edit. Always set `pdf.fonttype = 42`.
- **Saving heatmap row dendrograms without checking the linkage.** `seaborn.clustermap` defaults to Euclidean + average; for log-counts or z-scores you usually want correlation distance + complete or Ward linkage. The dendrogram is a model, not a fact.

## Checklist

- [ ] Vector output (PDF/SVG) at the correct journal width in mm
- [ ] Okabe-Ito / viridis / RdBu — not rainbow, not Set1 on continuous
- [ ] Replicates visible (dots, SuperPlot, or facet) — no bare bars
- [ ] Shape or linetype as a second channel where color matters
- [ ] Fonts embedded (`cairo_pdf` in R, `pdf.fonttype = 42` in Python)
- [ ] Asterisks match the test reported in the methods
- [ ] Figure saved by code, not by clicking Export

## Further reading

- [Weissgerber et al. 2015, *PLoS Biol.* — Beyond Bar and Line Graphs](https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.1002128)
- [Lord, Velle, Mullins & Fritz-Laylin 2020, *J Cell Biol* — SuperPlots](https://rupress.org/jcb/article/219/6/e202001064/151717/SuperPlots-Communicating-reproducibility-and)
- [Wong 2011, *Nat Methods* — Points of view: Color blindness](https://www.nature.com/articles/nmeth.1618) (the Okabe-Ito introduction for biologists)
- [Nature research figure guide](https://research-figure-guide.nature.com/) — building and exporting panels, sizing, type
- [Cell Press figure guidelines](https://www.cell.com/figureguidelines)
- [ggplot2 book (Wickham, 3e)](https://ggplot2-book.org/) — canonical reference
- [`patchwork` documentation](https://patchwork.data-imaginist.com/) — combining ggplots
- [`ComplexHeatmap` reference manual](https://jokergoo.github.io/ComplexHeatmap-reference/book/)
- [seaborn tutorial](https://seaborn.pydata.org/tutorial.html)
- [`statannotations` on GitHub](https://github.com/trevismd/statannotations)
- [Okabe-Ito original Color Universal Design palette](https://jfly.uni-koeln.de/color/) — Okabe & Ito
- [`colorBlindness::cvdPlot`](https://cran.r-project.org/web/packages/colorBlindness/vignettes/colorBlindness.html) — simulate CVD on any ggplot
