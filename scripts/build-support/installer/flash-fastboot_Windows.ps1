#Requires -Version 5.1
[CmdletBinding()]
param([Parameter(Position = 0)][string]$PackageDirectory = $PSScriptRoot)

# PixelOS install with explicit data mode; fixed B slot. No serial-number binding.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:LogWriter = $null
$script:FB_OUTPUT = ''
$exitCode = 1
$script:QuietTools = $true
$script:ColorEnabled = $false
$script:ConsoleModeSaved = $false
$script:ConsoleHandle = [IntPtr]::Zero
$script:OriginalConsoleMode = [uint32]0
$originalEncoding = [Console]::OutputEncoding

function Initialize-Color {
    # Enable ANSI using the system console API; no external runtime is required.
    try {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class KanoeConsole {
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern IntPtr GetStdHandle(int id);
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool GetConsoleMode(IntPtr handle, out uint mode);
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool SetConsoleMode(IntPtr handle, uint mode);
}
'@
        $script:ConsoleHandle = [KanoeConsole]::GetStdHandle(-11)
        $mode = [uint32]0
        if ([KanoeConsole]::GetConsoleMode($script:ConsoleHandle, [ref]$mode)) {
            $script:OriginalConsoleMode = $mode
            $script:ConsoleModeSaved = $true
            $script:ColorEnabled = [KanoeConsole]::SetConsoleMode($script:ConsoleHandle, ($mode -bor 4))
        }
        [Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
    } catch {
        Write-Log ("Color initialization: " + $_.Exception.Message) -Quiet
    }
}

function Show-Banner {
    if ($script:ColorEnabled -and [IO.File]::Exists((Join-Path $script:PackageRoot 'assets/kanoe-64.ansi'))) {
        try {
        $art = [IO.File]::ReadAllText((Join-Path $script:PackageRoot 'assets/kanoe-64.ansi'), [Text.Encoding]::UTF8)
        [Console]::Write($art)
        } catch { Write-Host 'KANOE · PixelOS · popsicle' }
    } else {
        Write-Host 'KANOE · PixelOS · popsicle'
        Write-Host '酷安 @Itagaki_Kanoe / Coolapk @Itagaki_Kanoe'
    }
}


function Write-Log([string]$Text, [switch]$Quiet) {
    if ($null -ne $script:LogWriter) { $script:LogWriter.WriteLine($Text) }
    if (-not $Quiet) { Write-Host $Text }
}

function Assert-Condition([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function ConvertTo-NativeArgument([string]$Value) {
    # All arguments are fixed tokens or filesystem paths. Quotes/newlines are invalid here.
    Assert-Condition ($Value -notmatch '["\r\n\x00]') 'Invalid native argument'
    return '"' + [regex]::Replace($Value, '(\\+)$', '$1$1') + '"'
}

function Invoke-Tool([string]$Executable, [string[]]$ToolArguments) {
    Write-Log ((Split-Path -Leaf $Executable) + ' ' + ($ToolArguments -join ' ')) -Quiet:$script:QuietTools
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo.FileName = $Executable
    $process.StartInfo.Arguments = (($ToolArguments | ForEach-Object { ConvertTo-NativeArgument $_ }) -join ' ')
    $process.StartInfo.WorkingDirectory = $script:PackageRoot
    $process.StartInfo.UseShellExecute = $false
    $process.StartInfo.CreateNoWindow = $true
    $process.StartInfo.RedirectStandardOutput = $true
    $process.StartInfo.RedirectStandardError = $true
    $output = New-Object System.Text.StringBuilder
    try {
        Assert-Condition ($process.Start()) 'Could not start tool'
        # Drain both streams concurrently, including text without a terminating newline.
        # This avoids PowerShell 5.1 treating fastboot's normal stderr as a fatal error.
        $streams = @($process.StandardOutput, $process.StandardError)
        $buffers = @((New-Object char[] 1024), (New-Object char[] 1024))
        $pending = @($streams[0].ReadAsync($buffers[0], 0, 1024), $streams[1].ReadAsync($buffers[1], 0, 1024))
        while ($null -ne $pending[0] -or $null -ne $pending[1]) {
            $madeProgress = $false
            for ($i = 0; $i -lt 2; $i++) {
                if ($null -eq $pending[$i] -or -not $pending[$i].IsCompleted) { continue }
                $count = $pending[$i].GetAwaiter().GetResult()
                $madeProgress = $true
                if ($count -eq 0) { $pending[$i] = $null; continue }
                $text = -join $buffers[$i][0..($count - 1)]
                $script:LogWriter.Write($text)
                if (-not $script:QuietTools) { Write-Host -NoNewline $text }
                [void]$output.Append($text)
                $pending[$i] = $streams[$i].ReadAsync($buffers[$i], 0, 1024)
            }
            if (-not $madeProgress) { Start-Sleep -Milliseconds 20 }
        }
        $process.WaitForExit()
        $script:FB_OUTPUT = $output.ToString().Replace("`r", '')
        if ($script:QuietTools -and ($process.ExitCode -ne 0 -or $script:FB_OUTPUT -match '(?im)(^|\s)FAILED([\s:!(]|$)|^fastboot: error:')) {
            Write-Host $script:FB_OUTPUT
        }
        Assert-Condition ($process.ExitCode -eq 0) "Tool failed (exit $($process.ExitCode))"
        Assert-Condition ($script:FB_OUTPUT -notmatch '(?im)(^|\s)FAILED([\s:!(]|$)|^fastboot: error:') 'Tool reported FAILED/error'
    } finally {
        # Never issue another device command from cleanup, including on Ctrl+C.
        $process.Dispose()
    }
}

function Invoke-Fastboot([string[]]$ToolArguments) {
    Invoke-Tool $script:FastbootBin $ToolArguments
}

function Get-FastbootVariable([string]$Name) {
    $wasQuiet = $script:QuietTools
    try {
        $script:QuietTools = $true
        Invoke-Fastboot @('getvar', $Name)
    } finally { $script:QuietTools = $wasQuiet }
    $prefix = $Name + ':'
    $values = @($script:FB_OUTPUT -split "`n" | Where-Object { $_.StartsWith($prefix, [StringComparison]::Ordinal) })
    Assert-Condition ($values.Count -eq 1) "Missing/ambiguous getvar $Name"
    $value = $values[0].Substring($prefix.Length).Trim()
    Assert-Condition ($value.Length -gt 0) "Empty getvar $Name"
    return $value
}

function Get-PartitionCapacity([string]$Name) {
    $value = Get-FastbootVariable "partition-size:$Name"
    Assert-Condition ($value -cmatch '^(0[xX])?[0-9a-fA-F]{1,12}$') "Invalid partition capacity: $Name"
    $capacity = [Convert]::ToInt64(($value -replace '^0[xX]', ''), 16)
    Assert-Condition ($capacity -gt 0) "Empty partition: $Name"
    return $capacity
}

try {
    Assert-Condition ($env:OS -eq 'Windows_NT') 'Use the macOS or Linux entry on this computer'
    $script:PackageRoot = (Resolve-Path -LiteralPath $PackageDirectory).ProviderPath
    $logDirectory = Join-Path $script:PackageRoot 'logs'
    [void][IO.Directory]::CreateDirectory($logDirectory)
    $logPath = Join-Path $logDirectory ("flash-{0}-{1}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'), $PID)
    $script:LogWriter = New-Object IO.StreamWriter($logPath, $false, (New-Object Text.UTF8Encoding($false)))
    $script:LogWriter.AutoFlush = $true
    Write-Log 'PixelOS user + OS4.0.0.23 firmware. Supported base: official A16 OS3.0.318.0.' -Quiet
    Write-Log 'Choose whether to erase or preserve userdata and metadata after preflight. Back up first.' -Quiet
    Write-Log 'Full super replaces both logical slots. Only B is populated; A is not a rollback system.' -Quiet
    Write-Log "Log: $logPath" -Quiet

    Initialize-Color
    Show-Banner
    Write-Log '请将手机进入 Bootloader Fastboot 模式，并使用 USB 连接电脑。'
    if ([Console]::IsInputRedirected) {
        Write-Host -NoNewline '按回车继续：'
        $connection = [Console]::ReadLine()
        if ($null -eq $connection) {
            Write-Log "已取消，未执行任何刷写。日志：$logPath"
            $exitCode = 0
            exit $exitCode
        }
    } else {
        $connection = Read-Host '按回车继续'
    }
    Write-Log '请稍等'

    $firmware = @('abl','xbl','xbl_config','multiimgqti','tme_seq_patch','tme_fw','tme_config','xbl_ac_config',
        'uefi','aop','aop_config','tz','hyp','modem','modemfirmware','bluetooth','dsp','keymaster','spuservice',
        'devcfg','qupfw','uefisecapp','imagefv','shrm','cpucp','idmanager','featenabler','xbl_ramdump',
        'cpucp_dtb','soccp','soccp_debug','soccp_dcd','pdp','pdp_cdb','tz_ac_config','hyp_ac_config',
        'dcp','tz_qti_config','secretkeeper','vm-bootsys','qtvm_dtbo','pvmfw')
    $parts = @($firmware) + @('super','boot','dtbo','vendor_boot','vbmeta','recovery','vbmeta_system','init_boot')
    $images = @($parts | ForEach-Object { if ($_ -eq 'super') { 'images/super-install-b.img' } else { "images/$_.img" } })
    function Verify-Files([string[]]$Names) {
        $sumRows = [IO.File]::ReadAllLines((Join-Path $script:PackageRoot 'metadata/SHA256SUMS'))
        foreach ($name in $Names) {
            $item = Get-Item -LiteralPath (Join-Path $script:PackageRoot $name) -Force
            Assert-Condition (-not $item.PSIsContainer -and $item.Length -gt 0 -and -not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) "Missing/empty/reparse file: $name"
            $hashes = @($sumRows | ForEach-Object {
                if ($_ -cmatch '^([0-9a-f]{64})  ([A-Za-z0-9_./+-]+)$' -and $Matches[2] -ceq $name) { $Matches[1] }
            })
            Assert-Condition ($hashes.Count -eq 1) "Missing/invalid checksum: $name"
            $actualHash = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash
            Assert-Condition ($actualHash -ieq $hashes[0]) "Checksum mismatch: $name"
            Write-Log "Verified: $name" -Quiet
        }
    }
    foreach ($directory in @('images','metadata','tools','tools/Windows')) {
        $item = Get-Item -LiteralPath (Join-Path $script:PackageRoot $directory) -Force
        Assert-Condition ($item.PSIsContainer -and -not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) "Invalid directory: $directory"
    }
    Verify-Files ($images + @('metadata/flash-manifest.tsv','tools/Windows/fastboot.exe','tools/Windows/AdbWinApi.dll','tools/Windows/AdbWinUsbApi.dll'))
    $rows = @([IO.File]::ReadAllLines((Join-Path $script:PackageRoot 'metadata/flash-manifest.tsv')))
    Assert-Condition ($rows.Count -eq 50) 'Incomplete/extra manifest rows'
    $sizes = @()
    for ($i = 0; $i -lt $parts.Count; $i++) {
        $fields = $rows[$i].Split("`t")
        Assert-Condition ($fields.Count -eq 5) "Invalid manifest row $i"
        $part = $parts[$i]
        $target = "${part}_b"
        $source = 'a17-payload'
        if ($i -ge 42) { $source = 'pixelos-target-files' }
        if ($part -eq 'super') { $target = 'super'; $source = 'pixelos-super' }
        Assert-Condition ($fields[0] -ceq $target -and $fields[1] -ceq $images[$i] -and $fields[4] -ceq $source) "Invalid manifest contract $i"
        Assert-Condition ($fields[2] -cmatch '^[1-9][0-9]{0,11}$' -and $fields[3] -cmatch '^[1-9][0-9]{0,11}$') 'Invalid image size'
        $bytes = [long]$fields[2]; $expanded = [long]$fields[3]
        $imagePath = Join-Path $script:PackageRoot $images[$i]
        Assert-Condition ((Get-Item -LiteralPath $imagePath).Length -eq $bytes) "File length mismatch: $imagePath"
        if ($part -eq 'super') {
            Assert-Condition ($expanded -eq 13421772800) 'Wrong super capacity'
            $reader = New-Object IO.BinaryReader([IO.File]::OpenRead($imagePath))
            try {
                Assert-Condition ($reader.ReadUInt32() -eq 0xed26ff3aL) 'Expected verified sparse super'
                $reader.BaseStream.Position = 12
                $blockSize = $reader.ReadUInt32(); $blocks = $reader.ReadUInt32()
                Assert-Condition ($blockSize -eq 4096 -and [long]$blockSize * [long]$blocks -eq $expanded) 'Wrong expanded super size'
            } finally { $reader.Dispose() }
        } else { Assert-Condition ($bytes -eq $expanded) "Expected raw image: $imagePath" }
        $sizes += $expanded
    }

    # Use the verified bundled tools regardless of PATH or FASTBOOT settings.
    $toolDirectory = Join-Path $script:PackageRoot 'tools/Windows'
    $script:FastbootBin = Join-Path $toolDirectory 'fastboot.exe'
    Write-Log "Using bundled Platform Tools: $toolDirectory" -Quiet
    Invoke-Fastboot @('--version')

    Assert-Condition ((Get-FastbootVariable 'product') -ceq 'popsicle') 'Wrong device'
    Assert-Condition ((Get-FastbootVariable 'is-userspace') -ceq 'no') 'Bootloader fastboot required'
    Invoke-Fastboot @('oem','device-info')
    Assert-Condition ($script:FB_OUTPUT -cmatch '(?m)Device unlocked: true$') 'Unlocked Bootloader required'
    Assert-Condition ((Get-FastbootVariable 'slot-count') -ceq '2') 'Two slots required'
    Assert-Condition ((Get-FastbootVariable 'current-slot') -cmatch '^[ab]$') 'Invalid current slot'
    Assert-Condition ((Get-FastbootVariable 'anti') -cmatch '^[01]$') 'Outside supported A16 anti boundary (0 or 1)'
    for ($i = 0; $i -lt $parts.Count; $i++) {
        $target = "$($parts[$i])_b"
        if ($parts[$i] -eq 'super') { $target = 'super' }
        $capacity = Get-PartitionCapacity $target
        Assert-Condition ($capacity -ge $sizes[$i]) "Partition too small: $target"
        if ($target -eq 'super') { Assert-Condition ($capacity -eq 13421772800) 'Unexpected physical super' }
    }
    foreach ($part in @('userdata','metadata')) {
        [void](Get-PartitionCapacity $part)
        $type = Get-FastbootVariable "partition-type:$part"
        Write-Log "$part advertised type: $type; format as f2fs only if erase mode is selected" -Quiet
    }
    Write-Log '请选择数据处理方式：'
    Write-Log '1：清空数据，擦除并格式化 userdata 和 metadata，包括内部存储、应用及加密信息。'
    Write-Log '2：保留数据，跳过上述两个分区的擦除和格式化；仍会重写系统与固件。'
    Write-Log '保留模式未实机验证，不能保证跨 ROM/版本的数据及加密兼容性。请先备份。'
    $dataMode = Read-Host '输入 1 或 2（其他输入或无输入均取消）'
    $confirmation = ''
    if ($dataMode -ceq '1' -or $dataMode -ceq '2') {
        if ($dataMode -ceq '1') {
            Write-Log '已选择：清空数据。手机全部用户数据将被删除。'
        } else {
            Write-Log '已选择：保留数据。脚本不会擦除或格式化 userdata 和 metadata。'
        }
        if ($dataMode -ceq '1') {
            Verify-Files @('tools/Windows/make_f2fs.exe','tools/Windows/make_f2fs_casefold.exe')
        }
        Write-Log '只有输入小写 yes 并按回车才会按所选模式开始刷写；其他输入或无输入均取消。'
        $confirmation = Read-Host '确认按所选模式刷机？输入 yes'
    }
    if ($confirmation -cne 'yes') {
        Write-Log '已取消，未执行任何刷写、擦除、切槽或重启。'
        $exitCode = 0
    } else {
        Write-Log '开始刷写，请勿断开连接。'
        $script:QuietTools = $false
        foreach ($part in $firmware) { Invoke-Fastboot @('flash',"${part}_b","images/$part.img") }
        Invoke-Fastboot @('-S','256M','flash','super','images/super-install-b.img')
        foreach ($part in @('boot','dtbo','vendor_boot','vbmeta','recovery','vbmeta_system')) {
            Invoke-Fastboot @('flash',"${part}_b","images/$part.img")
        }
        if ($dataMode -ceq '1') {
            foreach ($part in @('userdata','metadata')) {
                Invoke-Fastboot @('erase',$part)
                Invoke-Fastboot @('format:f2fs',$part)
            }
        } else {
            Write-Log '保留数据：已跳过 userdata 和 metadata 的擦除、格式化。'
        }
        Invoke-Fastboot @('flash','init_boot_b','images/init_boot.img')
        Invoke-Fastboot @('set_active','b')
        Assert-Condition ((Get-FastbootVariable 'current-slot') -ceq 'b') 'B slot selection did not take effect'
        Invoke-Fastboot @('reboot')
        Show-Banner
        Write-Log "已完成刷写，已发送重启命令。首次启动请耐心等待。日志：$logPath"
        $exitCode = 0
    }
} catch {
    $message = "已停止：$($_.Exception.Message)。不再执行后续操作。"
    if ($null -ne $script:LogWriter) { $message += " 日志：$logPath" }
    Write-Host $message
    if ($null -ne $script:LogWriter) {
        try { $script:LogWriter.WriteLine($message) } catch { Write-Host 'Could not write final log message.' }
    }
} finally {
    if ($script:ColorEnabled) { [Console]::Write(([char]27).ToString() + '[0m') }
    if ($script:ConsoleModeSaved) {
        [void][KanoeConsole]::SetConsoleMode($script:ConsoleHandle, $script:OriginalConsoleMode)
    }
    [Console]::OutputEncoding = $originalEncoding
    if ($null -ne $script:LogWriter) { $script:LogWriter.Dispose() }

}
exit $exitCode
