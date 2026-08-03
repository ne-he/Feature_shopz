# scripts/keep_awake.ps1
# Script to prevent Windows from going to sleep while Antigravity IDE is running.
# Uses Win32 SetThreadExecutionState API to prevent sleep programmatically.

# Define Win32 API for Thread Execution State
$Signature = @'
[DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
public static extern uint SetThreadExecutionState(uint esFlags);
'@

# Add the Win32 API definition to the PowerShell session
if (-not ([System.Management.Automation.PSTypeName]'WinAPI.Win32').Type) {
    Add-Type -MemberDefinition $Signature -Name "Win32" -Namespace "WinAPI"
}

# Execution state flags
$ES_CONTINUOUS = 0x80000000
$ES_SYSTEM_REQUIRED = 0x00000001
$ES_DISPLAY_REQUIRED = 0x00000002

Write-Host "=== Antigravity IDE Keep-Awake Script ===" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop manually." -ForegroundColor Yellow

$sleepPrevented = $false

while ($true) {
    # Search for processes containing "Antigravity"
    $processes = Get-Process | Where-Object { $_.Name -like "*Antigravity*" }
    
    if ($processes) {
        if (-not $sleepPrevented) {
            # Prevent system sleep (ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
            [WinAPI.Win32]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED) | Out-Null
            $sleepPrevented = $true
            Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Detected Antigravity IDE processes. Preventing Windows from entering sleep..." -ForegroundColor Green
        }
        # Keep displaying the running processes count
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Antigravity IDE is active (Count: $($processes.Count)). Sleep prevented." -ForegroundColor DarkGreen
    } else {
        if ($sleepPrevented) {
            # Restore default execution state (ES_CONTINUOUS only)
            [WinAPI.Win32]::SetThreadExecutionState($ES_CONTINUOUS) | Out-Null
            $sleepPrevented = $false
            Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Antigravity IDE is no longer running." -ForegroundColor Yellow
        }
        Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] No active processes found. Restoring default power state and exiting..." -ForegroundColor Red
        break
    }
    
    Start-Sleep -Seconds 60
}
