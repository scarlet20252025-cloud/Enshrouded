param(
  [int]$ProcId,
  [string]$Script,
  [string]$LogPath
)
$frida = "C:\Users\63526\AppData\Roaming\Python\Python314\Scripts\frida.exe"
& $frida -p $ProcId -l $Script --runtime=v8 *> $LogPath
"FRIDA EXIT CODE: $LASTEXITCODE"
