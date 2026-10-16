# Instala a IA interna (miau-ia) sem precisar rodar .bat: chamado pelo programa Studios Miau.
# Uso: powershell -ExecutionPolicy Bypass -File instalar-tudo.ps1 -Papel pc1|pc2
# Passos: baixa o código do GitHub -> instala o Python 3.12 (só para este usuário) -> instalar.bat /auto -> (PC 2) libera a rede.
param([string]$Papel = "pc1", [string]$Destino = "$env:LOCALAPPDATA\miau-ia")
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$OutputEncoding = [Text.Encoding]::UTF8
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
function Etapa($n, $t) { Write-Output "##ETAPA $n/5 $t" }

try {
  Etapa 1 "Baixando o miau-ia do GitHub"
  $tmp = Join-Path $env:TEMP ("miau-ia-" + [guid]::NewGuid().ToString("N"))
  New-Item -ItemType Directory -Force -Path $tmp | Out-Null
  $zip = Join-Path $tmp "codigo.zip"
  Invoke-WebRequest -UseBasicParsing "https://codeload.github.com/miausicalproductions-sudo/contas-adm-app/zip/refs/heads/main" -OutFile $zip
  Expand-Archive -Path $zip -DestinationPath $tmp -Force
  $src = Get-ChildItem -Path $tmp -Directory | Where-Object { Test-Path (Join-Path $_.FullName "local-ai") } | Select-Object -First 1
  if (-not $src) { throw "o arquivo baixado não tem a pasta local-ai" }
  New-Item -ItemType Directory -Force -Path $Destino | Out-Null
  robocopy (Join-Path $src.FullName "local-ai") $Destino /E /XD venv dados /XF config.toml /NFL /NDL /NJH /NJS /NP | Out-Null
  Write-Output "Pasta do miau-ia: $Destino"

  Etapa 2 "Conferindo o Python 3.12"
  $py = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
  if (-not (Test-Path $py)) {
    $achou = $null
    try { $achou = (& py -3.12 -c "import sys;print(sys.executable)" 2>$null) } catch { }
    if ($achou -and (Test-Path $achou)) { $py = $achou }
    else {
      Write-Output "Instalando o Python 3.12 (só para este usuário, sem pedir senha)..."
      $exe = Join-Path $tmp "python-3.12.exe"
      Invoke-WebRequest -UseBasicParsing "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe" -OutFile $exe
      $p = Start-Process -FilePath $exe -ArgumentList "/quiet InstallAllUsers=0 PrependPath=0 Include_launcher=0 Include_test=0 Shortcuts=0" -Wait -PassThru
      if (-not (Test-Path $py)) { throw "o Python não instalou (código $($p.ExitCode))" }
    }
  }
  Write-Output "Python: $py"

  Etapa 3 "Instalando as IAs (PyTorch, gerador de figurinhas, recorte, transcrição, leitura). Demora de 10 a 40 min"
  $env:PYEXE = $py
  $args2 = @("/c", "instalar.bat", "/auto")
  if ($Papel -eq "pc2") { $args2 += "/pc2" }
  Push-Location $Destino
  & cmd.exe $args2 2>&1 | ForEach-Object { Write-Output $_ }
  $cod = $LASTEXITCODE
  Pop-Location
  if ($cod -ne 0) { throw "a instalação das IAs parou (código $cod). Veja as linhas acima." }

  Etapa 4 "Ligando o miau-ia junto com o Windows"
  if ($Papel -eq "pc2") {
    Write-Output "Liberando a porta 8765 na rede local (o Windows vai pedir permissão)..."
    try {
      Start-Process -FilePath "netsh" -ArgumentList 'advfirewall firewall add rule name="miau-ia 8765" dir=in action=allow protocol=TCP localport=8765 profile=private' -Verb RunAs -Wait -WindowStyle Hidden
    } catch { Write-Output "Não liberei o firewall agora: rode liberar-rede-pc2.bat como administrador na pasta $Destino." }
  }

  Etapa 5 "Pronto"
  $cfg = Get-Content (Join-Path $Destino "config.toml") -Raw
  $tok = ([regex]::Match($cfg, 'token\s*=\s*"([^"]*)"')).Groups[1].Value
  Write-Output "##TOKEN $tok"
  Write-Output "##PASTA $Destino"
  if ($Papel -eq "pc2") {
    $ips = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' } | ForEach-Object { $_.IPAddress })
    foreach ($i in $ips) { Write-Output "##IP http://$($i):8765" }
  }
  Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
  exit 0
} catch {
  Write-Output "##ERRO $($_.Exception.Message)"
  exit 1
}
