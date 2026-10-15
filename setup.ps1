param([switch]$Worker, [string]$Session)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$root = $PSScriptRoot
$runtime = Join-Path $root 'runtime'
[IO.Directory]::CreateDirectory($runtime) | Out-Null

function Write-State([int]$Step, [string]$Message, [string]$Result = 'working') {
    $state = @{step=$Step; message=$Message; result=$Result} | ConvertTo-Json -Compress
    $temp = Join-Path $runtime ("setup-$Session.tmp")
    $dest = Join-Path $runtime ("setup-$Session.json")
    [IO.File]::WriteAllText($temp, $state, [Text.Encoding]::UTF8)
    Move-Item -LiteralPath $temp -Destination $dest -Force
}

function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "İşlem tamamlanamadı (kod: $LASTEXITCODE). Ayrıntılar kurulum günlüğünde." }
}

function Test-Python([string]$Program) {
    if (-not (Test-Path -LiteralPath $Program -PathType Leaf)) { return $false }
    & $Program -c 'import sys;sys.exit(0 if sys.version_info[:2]==(3,13) and sys.maxsize>2**32 else 1)' 2>$null
    return $LASTEXITCODE -eq 0
}

function Find-Python {
    $candidates = @((Join-Path $root '.venv\Scripts\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\TiniPython313\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'))
    foreach ($key in @('HKCU:\Software\Python\PythonCore\3.13\InstallPath',
                       'HKLM:\Software\Python\PythonCore\3.13\InstallPath')) {
        if (Test-Path $key) {
            $folder = (Get-Item $key).GetValue('')
            if ($folder) { $candidates += Join-Path $folder 'python.exe' }
        }
    }
    foreach ($candidate in $candidates) {
        if (Test-Python $candidate) { return $candidate }
    }
    return $null
}

if ($Worker) {
    try {
        Set-Location -LiteralPath $root
        Write-State 0 'Bilgisayar kontrol ediliyor…'
        if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
            throw 'Bu sürüm Windows x64 ve NVIDIA ekran kartı gerektiriyor.'
        }
        $gpus = Get-CimInstance Win32_VideoController
        if (-not ($gpus | Where-Object { $_.Name -match 'NVIDIA' })) {
            throw 'NVIDIA ekran kartı bulunamadı. Bu sürüm NVIDIA ekran kartı gerektiriyor.'
        }
        Write-State 1 'Python hazırlanıyor…'
        $python = Find-Python
        if (-not $python) {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            $installer = Join-Path $runtime 'python-3.13.13-amd64.exe'
            Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.13.13/python-3.13.13-amd64.exe' -OutFile $installer
            $signature = Get-AuthenticodeSignature -LiteralPath $installer
            if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Python Software Foundation(?:,|$)') {
                throw 'Python yükleyicisinin dijital imzası doğrulanamadı. Kurulum durduruldu.'
            }
            $target = Join-Path $env:LOCALAPPDATA 'Programs\TiniPython313'
            $process = Start-Process -FilePath $installer -WindowStyle Hidden -Wait -PassThru -ArgumentList @(
                '/quiet', 'InstallAllUsers=0', 'Include_launcher=0', 'Include_test=0',
                'Include_doc=0', 'Include_tcltk=0', 'PrependPath=0', ('TargetDir="' + $target + '"'))
            if ($process.ExitCode -notin @(0,3010)) { throw "Python kurulamadı (kod: $($process.ExitCode))." }
            $python = Join-Path $target 'python.exe'
            if (-not (Test-Python $python)) { throw 'Python başlatılamadı. Kurulum günlüğüne bak.' }
        }
        $venv = Join-Path $root '.venv\Scripts\python.exe'
        if (-not (Test-Python $venv)) {
            if (Test-Path -LiteralPath (Join-Path $root '.venv')) {
                throw 'Bu klasörde uyumsuz bir Python ortamı var. Paketi yeni bir klasöre çıkarıp Kur dosyasını aç.'
            }
            Invoke-Checked $python @('-m','venv',(Join-Path $root '.venv'))
        }
        Write-State 2 'Uygulama paketleri hazırlanıyor. İlk kurulum birkaç dakika sürebilir…'
        & $venv (Join-Path $root 'setup_helper.py') packages
        if ($LASTEXITCODE -ne 0) {
            Invoke-Checked $venv @('-m','pip','install','--disable-pip-version-check','-r',(Join-Path $root 'requirements.txt'))
        }
        Write-State 3 'Ekran kartı bağlantısı kontrol ediliyor…'
        Invoke-Checked $venv @((Join-Path $root 'setup_helper.py'),'gpu')
        Write-State 4 'Konuşma modeli hazırlanıyor. İlk indirme yaklaşık 1,6 GB…'
        Invoke-Checked $venv @((Join-Path $root 'setup_helper.py'),'model')
        Write-State 5 'Tını simgeleri oluşturuluyor…'
        . (Join-Path $root 'setup_shortcuts.ps1')
        New-TiniShortcuts -Root $root -Folders @(
            [Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))
        Write-State 6 'Hazır! Tını masaüstüne eklendi.' 'done'
        exit 0
    } catch {
        $_ | Out-String | Write-Output
        Write-State 0 $_.Exception.Message 'error'
        exit 1
    }
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()
$mutex = New-Object Threading.Mutex($false, 'Local\TiniSetup')
if (-not $mutex.WaitOne(0)) {
    [Windows.Forms.MessageBox]::Show('Kurulum zaten açık.', 'Tını') | Out-Null
    $mutex.Dispose()
    exit
}
try {
    $Session = [Guid]::NewGuid().ToString('N')
    $form = New-Object Windows.Forms.Form
    $form.Text = 'Tını kurulumu'
    $form.ClientSize = New-Object Drawing.Size(500,265)
    $form.StartPosition = 'CenterScreen'
    $form.FormBorderStyle = 'FixedDialog'
    $form.MaximizeBox = $false
    $form.Font = New-Object Drawing.Font('Segoe UI',10)
    $heading = New-Object Windows.Forms.Label
    $heading.Text = 'Tını hazırlanıyor'
    $heading.Font = New-Object Drawing.Font('Segoe UI',18)
    $heading.SetBounds(24,20,450,40)
    $label = New-Object Windows.Forms.Label
    $label.Text = 'Birkaç dakika sürebilir. Komut yazmana gerek yok.'
    $label.SetBounds(26,76,448,58)
    $bar = New-Object Windows.Forms.ProgressBar
    $bar.SetBounds(26,145,448,12)
    $bar.Style = 'Marquee'
    $bar.Maximum = 6
    $log = New-Object Windows.Forms.LinkLabel
    $log.Text = 'Kurulum günlüğü'
    $log.SetBounds(26,207,220,26)
    $stdout = Join-Path $runtime "setup-$Session.log"
    $stderr = Join-Path $runtime "setup-$Session-errors.log"
    $log.Add_Click({
        $details = Join-Path $runtime "setup-$Session-details.log"
        $content = @()
        foreach ($file in @($stdout,$stderr)) {
            if (Test-Path -LiteralPath $file) { $content += Get-Content -LiteralPath $file -Raw }
        }
        $content | Set-Content -LiteralPath $details -Encoding UTF8
        Start-Process notepad.exe -ArgumentList ('"' + $details + '"')
    })
    $button = New-Object Windows.Forms.Button
    $button.Text = 'Tını aç'
    $button.Enabled = $false
    $button.SetBounds(337,198,137,36)
    $button.Add_Click({
        if ($script:setupSuccess) {
            Start-Process -FilePath (Join-Path $root '.venv\Scripts\pythonw.exe') -WorkingDirectory $root -WindowStyle Hidden -ArgumentList ('"' + (Join-Path $root 'launcher.pyw') + '"')
        }
        $form.Close()
    })
    $form.Controls.AddRange(@($heading,$label,$bar,$log,$button))
    $script:setupSuccess = $false
    $script:setupFinished = $false
    $script:setupProcess = $null
    $timer = New-Object Windows.Forms.Timer
    $timer.Interval = 300
    $timer.Add_Tick({
        $stateFile = Join-Path $runtime "setup-$Session.json"
        if (Test-Path -LiteralPath $stateFile) {
            try { $state = Get-Content -LiteralPath $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json } catch { return }
            $label.Text = $state.message
            if ($state.result -eq 'done' -or $state.result -eq 'error') {
                $script:setupFinished = $true
                $script:setupSuccess = $state.result -eq 'done'
                $heading.Text = if ($script:setupSuccess) { 'Tını hazır' } else { 'Kurulum tamamlanamadı' }
                $bar.Style = 'Continuous'
                $bar.Value = if ($script:setupSuccess) { 6 } else { 0 }
                $button.Text = if ($script:setupSuccess) { 'Tını aç' } else { 'Kapat' }
                $button.Enabled = $true
                $timer.Stop()
            }
        }
        if (-not $script:setupFinished -and $script:setupProcess -and $script:setupProcess.HasExited) {
            $script:setupFinished = $true
            $heading.Text = 'Kurulum tamamlanamadı'
            $label.Text = 'Kurulum beklenmedik şekilde durdu. Kurulum günlüğüne bakıp tekrar dene.'
            $button.Text = 'Kapat'
            $button.Enabled = $true
            $timer.Stop()
        }
    })
    $form.Add_Shown({
        try {
            $script:setupProcess = Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -WindowStyle Hidden -PassThru -WorkingDirectory $root -RedirectStandardOutput $stdout -RedirectStandardError $stderr -ArgumentList @(
                '-NoProfile','-ExecutionPolicy','Bypass','-File',('"' + (Join-Path $root 'setup.ps1') + '"'),'-Worker','-Session',$Session)
            $timer.Start()
        } catch {
            $script:setupFinished = $true
            $heading.Text = 'Kurulum başlatılamadı'
            $label.Text = $_.Exception.Message
            $button.Text = 'Kapat'
            $button.Enabled = $true
        }
    })
    $form.Add_FormClosing({ param($sender,$event)
        if (-not $script:setupFinished) {
            $event.Cancel = $true
            $label.Text = 'Kurulum sürüyor; tamamlandığında bu pencereyi kapatabilirsin.'
        }
    })
    [void]$form.ShowDialog()
    $timer.Dispose()
    $form.Dispose()
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
