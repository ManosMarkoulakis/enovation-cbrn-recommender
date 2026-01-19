$ErrorActionPreference = "Stop"

Write-Host "Generating reference dataset..."
python -m recsys_wp0.wp0_code.make_reference --in recsys_wp0\eval_data\reference_labels.jsonl --out recsys_wp0\eval_data\reference_labels.jsonl

Write-Host "WP0 eval (all) on reference labels..."
python -m recsys_wp0.wp0_code.eval_runner --split all

Write-Host "WP2 eval (all) on reference labels..."
python -m recsys_wp2.wp2_code.wp2_eval_runner --split all

Write-Host "WP3 eval (all) on reference labels..."
python -m recsys_wp3.wp3_code.wp3_eval_runner --split all
