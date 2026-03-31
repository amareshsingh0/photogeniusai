# Train the 3 essential LoRAs (skin_realism_v2, cinematic_lighting_v3, color_harmony_v1).
# Requires: GPU, datasets, torch, diffusers, peft. Optional: boto3 for -UploadS3.
#
# Usage:
#   .\scripts\train_essential_loras.ps1              # Train all 3
#   .\scripts\train_essential_loras.ps1 -UploadS3    # Train all 3 and upload to s3://photogenius-models/loras/

param([switch]$UploadS3)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TrainDir = Resolve-Path (Join-Path $ScriptDir "..")
$Output = if ($env:OUTPUT) { $env:OUTPUT } else { Join-Path (Join-Path $TrainDir "..") "models\loras" }

Set-Location $TrainDir

$uploadArg = if ($UploadS3) { "--upload-s3" } else { "" }

Write-Host "Training skin_realism_v2 (500 portraits, ultra realistic skin texture)..."
python training/train_style_loras.py --style skin_realism_v2 `
  --dataset prithivMLmods/Realistic-Face-Portrait-1024px `
  --epochs 1000 `
  --output "$Output\skin_realism_v2.safetensors" `
  $uploadArg

Write-Host "Training cinematic_lighting_v3 (300 movie stills, cinematic lighting)..."
python training/train_style_loras.py --style cinematic_lighting_v3 `
  --dataset ChristophSchuhmann/improved_aesthetics_parquet `
  --epochs 1000 `
  --output $Output `
  $uploadArg

Write-Host "Training color_harmony_v1 (400 color-theory images, harmonious palette)..."
python training/train_style_loras.py --style color_harmony_v1 `
  --dataset laion/laion-art `
  --epochs 1000 `
  --output $Output `
  $uploadArg

Write-Host "Done. LoRAs in $Output (and S3 if -UploadS3 was used)."
