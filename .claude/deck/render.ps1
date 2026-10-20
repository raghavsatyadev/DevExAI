param([string]$Pptx, [string]$OutDir)
New-Item -ItemType Directory -Force $OutDir | Out-Null
Get-ChildItem $OutDir -Filter *.png | Remove-Item -Force
$app = New-Object -ComObject PowerPoint.Application
$deck = $app.Presentations.Open($Pptx, $true, $false, $false)
foreach ($s in $deck.Slides) {
  $s.Export((Join-Path $OutDir ("s{0:D2}.png" -f $s.SlideIndex)), "PNG", 1600, 900)
}
$deck.Close()
if ($app.Presentations.Count -eq 0) { $app.Quit() }
Write-Output "rendered $($deck.Slides.Count)"
