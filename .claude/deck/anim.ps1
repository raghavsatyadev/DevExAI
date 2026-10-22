param([string]$Pptx)
# Adds a fade transition to every slide, and fades in shapes named "buildNN ..."
# step by step (NN ascending). Each step starts after the previous one, so the
# presenter never has to click to reveal content. Prints a readback per slide.
$fade = 10          # msoAnimEffectFade
$withPrev = 2       # msoAnimTriggerWithPrevious
$afterPrev = 3      # msoAnimTriggerAfterPrevious
$fadeSmooth = 3849  # ppEffectFadeSmoothly
$app = New-Object -ComObject PowerPoint.Application
$deck = $app.Presentations.Open($Pptx, $false, $false, $false)
foreach ($s in $deck.Slides) {
  $s.SlideShowTransition.EntryEffect = $fadeSmooth
  $s.SlideShowTransition.Duration = 0.5
  $seq = $s.TimeLine.MainSequence
  for ($i = $seq.Count; $i -ge 1; $i--) { $seq.Item($i).Delete() }
  $tagged = @($s.Shapes | Where-Object { $_.Name -match '^build(\d\d) ' } |
    Sort-Object @{ Expression = { [int]($_.Name.Substring(5, 2)) } }, ZOrderPosition)
  $last = $null
  foreach ($sh in $tagged) {
    $stepNo = $sh.Name.Substring(5, 2)
    $trigger = if ($stepNo -ne $last) { $afterPrev } else { $withPrev }
    $eff = $seq.AddEffect($sh, $fade, 0, $trigger)
    $eff.Timing.Duration = 0.4
    $last = $stepNo
  }
  # Videos start with the slide's last build step; added last so no fade waits for the video to end
  foreach ($m in @($s.Shapes | Where-Object { $_.Type -eq 16 })) {
    $null = $seq.AddEffect($m, 83, 0, $withPrev)  # msoAnimEffectMediaPlay
  }
  $types = ($seq | ForEach-Object { "$($_.EffectType)/$($_.Timing.TriggerType)" } |
    Sort-Object -Unique) -join ","
  Write-Output ("slide {0}: transition={1} effects={2} [{3}]" -f $s.SlideIndex,
    $s.SlideShowTransition.EntryEffect, $seq.Count, $types)
}
$deck.Save()
$deck.Close()
if ($app.Presentations.Count -eq 0) { $app.Quit() }
