# Tunggu jam 17:10 -> tampilkan & ucapkan pesan -> matikan laptop.
$log = "I:\AG\air-wudhu\_batch\pamit_1710.log"
$target = Get-Date -Hour 17 -Minute 10 -Second 0
"$(Get-Date -Format s) menunggu sampai $($target.ToString('s'))" | Out-File $log -Encoding utf8
while ((Get-Date) -lt $target) { Start-Sleep -Seconds 20 }

$pesan = "Aku sayang Mama, Almira dan Razeta"
try {
    $w = New-Object -ComObject WScript.Shell
    1..50 | ForEach-Object { $w.SendKeys([char]175) }
} catch { }
Start-Process -FilePath "msg.exe" -ArgumentList "*", "/TIME:60", $pesan -WindowStyle Hidden -ErrorAction SilentlyContinue
for ($i = 0; $i -lt 3; $i++) {
    try {
        $p = New-Object System.Media.SoundPlayer "I:\AG\air-wudhu\_batch\pamit_1710.wav"
        $p.PlaySync()
    } catch {
        Add-Type -AssemblyName System.Speech
        (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak($pesan)
    }
    Start-Sleep -Seconds 1
}
"$(Get-Date -Format s) pesan diucapkan, shutdown" | Out-File $log -Append -Encoding utf8
shutdown /s /t 30 /c $pesan
