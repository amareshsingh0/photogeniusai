[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding  = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING     = 'utf-8'

Write-Host '=== Log Streams ==='
$streams = (aws logs describe-log-streams `
  --log-group-name '/aws/sagemaker/Endpoints/photogenius-orchestrator' `
  --region us-east-1 `
  --order-by LastEventTime `
  --descending `
  --max-items 2 | ConvertFrom-Json).logStreams
$streams | ForEach-Object { Write-Host $_.logStreamName $_.lastEventTime }

Write-Host ''
Write-Host '=== STARTUP LOGS (first 60 events, most recent stream) ==='
$latestStream = $streams[0].logStreamName
Write-Host "Stream: $latestStream"
Write-Host ''

$events = (aws logs get-log-events `
  --log-group-name '/aws/sagemaker/Endpoints/photogenius-orchestrator' `
  --log-stream-name $latestStream `
  --region us-east-1 `
  --start-from-head `
  --limit 60 | ConvertFrom-Json).events
$events | ForEach-Object { Write-Host $_.message }

Write-Host ''
Write-Host '=== RECENT LOGS (last 60 events, most recent stream) ==='
$events2 = (aws logs get-log-events `
  --log-group-name '/aws/sagemaker/Endpoints/photogenius-orchestrator' `
  --log-stream-name $latestStream `
  --region us-east-1 `
  --limit 60 | ConvertFrom-Json).events
$events2 | ForEach-Object { Write-Host $_.message }
