$ErrorActionPreference = 'Stop'
$trialRoot = Split-Path -Parent $PSScriptRoot
$trialPython = Join-Path (Split-Path -Parent $trialRoot) 'SoftwareStatusObserverSkill/.venv/Scripts/python.exe'
$trialListener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$trialListener.Start()
$trialPort = $trialListener.LocalEndpoint.Port
$trialListener.Stop()
$trialDatabase = '.test-data/browser-' + [guid]::NewGuid().ToString('N') + '.sqlite'
$trialServer = '"' + $trialPython + '" -X utf8 -B server.py --demo --port ' + $trialPort + ' --db ' + $trialDatabase
Push-Location $trialRoot
try {
  & $trialPython -X utf8 -B 'C:/Users/Lvi_P/.codex/skills/webapp-testing/scripts/with_server.py' --server $trialServer --port $trialPort --timeout 45 -- node tests/browser.cjs "http://127.0.0.1:$trialPort"
  exit $LASTEXITCODE
} finally { Pop-Location }
