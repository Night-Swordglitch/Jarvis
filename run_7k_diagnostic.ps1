# Inspect the actual post-scheduler state used by Phase 7K.

Write-Host "`n=== 7K ANALYTICS DIAGNOSTIC ===" -ForegroundColor Cyan

Select-String -Path .\test_phase7_step14.py `
    -Pattern "scheduler_snapshot|evidence_store|analytics_agent|completed_aliases" `
    -Context 2,4 |
    ForEach-Object {
        Write-Host ""
        Write-Host $_.ToString()
    }

Write-Host "`n=== RUNNING 7K WITH DIAGNOSTIC ===" -ForegroundColor Yellow

python .\test_phase7_step14.py

Write-Host "`n=== END 7K DIAGNOSTIC ===" -ForegroundColor Cyan
