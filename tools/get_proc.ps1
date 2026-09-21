Get-Process | Where-Object { $_.MainWindowTitle -like '*Angel*' -or $_.ProcessName -like '*angel*' } | Format-Table Id, ProcessName, MainWindowTitle, Path

