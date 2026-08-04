' Wrapper que roda o launcher.ps1 de forma TOTALMENTE oculta.
'
' O atalho do jogo aponta para ca (via wscript). Sem isto, chamar o PowerShell
' direto pelo atalho pisca uma janela preta de terminal por um instante -- foi o
' "prompt" que aparecia. O WScript.Shell.Run com o modo 0 nao mostra janela
' nenhuma; a interface (barra de progresso, so quando ha atualizacao) e' criada
' pelo proprio launcher.ps1 via Windows Forms.

Set fso = CreateObject("Scripting.FileSystemObject")
Set sh  = CreateObject("WScript.Shell")

pasta = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = pasta

comando = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ _
        & pasta & "\launcher.ps1"""

' 0 = janela oculta ; False = nao espera terminar
sh.Run comando, 0, False
