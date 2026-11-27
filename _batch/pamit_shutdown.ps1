# Tunggu proses posting FB (PID) selesai -> ucapkan pesan -> matikan laptop.
param([int]$WaitPid = 25216)
$log = "I:\AG\air-wudhu\_batch\pamit_shutdown.log"
"$(Get-Date -Format s) menunggu PID $WaitPid" | Out-File $log -Encoding utf8
try { Wait-Process -Id $WaitPid -ErrorAction Stop } catch { }
"$(Get-Date -Format s) PID $WaitPid selesai" | Out-File $log -Append -Encoding utf8

$pesan = "AKU SAYANG RAZETA JONONG, TERIMA KASIH"
# pastikan suara terdengar: buka mute & naikkan volume
try {
    $w = New-Object -ComObject WScript.Shell
    1..50 | ForEach-Object { $w.SendKeys([char]175) }
} catch { }
Start-Process -FilePath "msg.exe" -ArgumentList "*", "/TIME:60", $pesan -WindowStyle Hidden -ErrorAction SilentlyContinue
for ($i = 0; $i -lt 2; $i++) {
    try {
        $p = New-Object System.Media.SoundPlayer "I:\AG\air-wudhu\_batch\pamit.wav"
        $p.PlaySync()
    } catch {
        Add-Type -AssemblyName System.Speech
        (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak($pesan)
    }
    Start-Sleep -Seconds 1
}
"$(Get-Date -Format s) pesan diucapkan, shutdown" | Out-File $log -Append -Encoding utf8
shutdown /s /t 30 /c $pesan
