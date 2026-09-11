$dest = "output/final_deliverables"
New-Item -ItemType Directory -Force -Path $dest | Out-Null

$files = @(
    "data/nifty100.db", "output/load_audit.csv", "output/validation_failures.csv",
    "output/capital_allocation.csv", "output/screener_output.xlsx", "config/screener_config.yaml",
    "output/peer_comparison.xlsx", "output/valuation_summary.xlsx", "output/cashflow_intelligence.xlsx",
    "output/pros_cons_generated.csv", "output/analysis_parsed.csv", "output/cluster_labels.csv",
    "output/cluster_profiles.csv", "output/outlier_report.csv", "output/portfolio_stats.csv",
    "output/pattern_distribution_latest.csv", "output/pattern_changes.csv", "output/skipped_tearsheets.csv",
    "reports/pytest_report.html", "reports/elbow_plot.png", "reports/correlation_heatmap.png",
    "docs/analyst_guide.pdf", "docs/acceptance_checklist.pdf", "docs/sprint5_retro.md", "docs/openapi.json"
)

foreach ($f in $files) {
    if (Test-Path $f) { Copy-Item $f $dest -Force; Write-Host "  Copied $f" }
    else { Write-Host "  MISSING $f" -ForegroundColor Yellow }
}

$dirs = @("reports/tearsheets", "reports/sector", "reports/portfolio", "reports/radar_charts")
foreach ($d in $dirs) {
    if (Test-Path $d) { Copy-Item $d $dest -Recurse -Force; Write-Host "  Copied $d/" }
    else { Write-Host "  MISSING $d/" -ForegroundColor Yellow }
}

Write-Host "
Archive complete."
$count = (Get-ChildItem $dest -Recurse -File).Count
Write-Host "Total files: $count"
