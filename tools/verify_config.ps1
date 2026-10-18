$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$exe = "D:\Steam\steamapps\common\RefRain - prism memories -\config.exe"
$asm = [System.Reflection.Assembly]::ReflectionOnlyLoadFrom($exe)
foreach ($name in @("RefRainConfig.FrmMain.resources", "RefRainConfig.FrmMain.en.resources", "Config.Properties.Resources.resources", "Config.Properties.Resources.en.resources")) {
  Write-Output "=== $name"
  $s = $asm.GetManifestResourceStream($name)
  if ($s -eq $null) { Write-Output "  STREAM NULL"; continue }
  $rr = New-Object System.Resources.ResourceReader($s)
  $en = $rr.GetEnumerator()
  while ($en.MoveNext()) {
    $k = $en.Key
    $v = $en.Value
    if ($v -is [string] -and $v -ne "") {
      Write-Output ("  " + $k + " = " + $v)
    }
  }
  $rr.Close()
}
