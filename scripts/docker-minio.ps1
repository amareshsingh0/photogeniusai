# MinIO for local S3-compatible storage. Windows PowerShell.
# Usage: .\scripts\docker-minio.ps1
# API: 9000, Console: 9001. Credentials: minioadmin / minioadmin

$name = "minio"
docker ps -a -q -f "name=^${name}$" | ForEach-Object { docker rm -f $_ 2>$null }
docker run -d --name $name `
  -p 9000:9000 -p 9001:9001 `
  -e MINIO_ROOT_USER=minioadmin `
  -e MINIO_ROOT_PASSWORD=minioadmin `
  minio/minio server /data --console-address ":9001"
Write-Host "MinIO: http://localhost:9001 (console) | S3 endpoint: localhost:9000"
