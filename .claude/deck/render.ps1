param([string]$Pptx, [string]$OutDir)
# PowerPoint resolves relative paths against its own folder, so pass it absolute ones.
$Pptx = (Resolve-Path $Pptx).Path
New-Item -ItemType Directory -Force $OutDir | Out-Null
$OutDir = (Resolve-Path $OutDir).Path
Get-ChildItem $OutDir -Filter *.png | Remove-Item -Force
$app = New-Object -ComObject PowerPoint.Application
$deck = $app.Presentations.Open($Pptx, $true, $false, $false)
$count = $deck.Slides.Count
foreach ($s in $deck.Slides) {
  $s.Export((Join-Path $OutDir ("s{0:D2}.png" -f $s.SlideIndex)), "PNG", 1600, 900)
}
$deck.Close()
if ($app.Presentations.Count -eq 0) { $app.Quit() }
Write-Output "rendered $count"
