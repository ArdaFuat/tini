param([string]$OutputPath='runtime/perf-resources.json', [int]$Seconds=8)
$ErrorActionPreference='Stop'
$sesProcesses=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'pythonw.exe' -and $_.CommandLine -like '*app.py*' })
if (-not $sesProcesses.Count) { throw 'Ses is not running' }
$sesBefore=@{}
foreach ($sesItem in $sesProcesses) { $sesProc=Get-Process -Id $sesItem.ProcessId; $sesBefore[$sesProc.Id]=$sesProc.CPU }
$sesClock=[Diagnostics.Stopwatch]::StartNew()
Start-Sleep -Seconds $Seconds
$sesCpu=0; $sesRam=0; $sesPrivate=0; $sesThreads=0; $sesHandles=0
foreach ($sesId in $sesBefore.Keys) {
 $sesProc=Get-Process -Id $sesId
 $sesCpu+=$sesProc.CPU-$sesBefore[$sesId]
 $sesRam+=$sesProc.WorkingSet64; $sesPrivate+=$sesProc.PrivateMemorySize64
 $sesThreads+=$sesProc.Threads.Count; $sesHandles+=$sesProc.HandleCount
}
$sesElapsed=$sesClock.Elapsed.TotalSeconds
$sesGpu=$null
try {
 $sesGpuSum=0
 $sesSamples=(Get-Counter '\GPU Process Memory(*)\Dedicated Usage').CounterSamples
 foreach ($sesId in $sesBefore.Keys) { $sesGpuSum+=($sesSamples | Where-Object InstanceName -like "pid_${sesId}_*" | Measure-Object CookedValue -Sum).Sum }
 $sesGpu=[math]::Round($sesGpuSum/1MB,1)
} catch { }
$sesResult=[ordered]@{
 cpu_core_ms_per_second=[math]::Round($sesCpu*1000/$sesElapsed,2)
 cpu_percent_machine=[math]::Round(100*$sesCpu/$sesElapsed/[Environment]::ProcessorCount,3)
 working_set_mb=[math]::Round($sesRam/1MB,1)
 private_memory_mb=[math]::Round($sesPrivate/1MB,1)
 gpu_dedicated_mb=$sesGpu
 threads=$sesThreads; handles=$sesHandles; sample_seconds=[math]::Round($sesElapsed,2)
}
$sesJson=$sesResult | ConvertTo-Json
Set-Content -LiteralPath $OutputPath -Value $sesJson -Encoding utf8
Write-Output $sesJson
