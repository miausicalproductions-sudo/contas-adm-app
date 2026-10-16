; Página extra do instalador: este PC vai rodar a IA interna (miau-ia)?
; Marcado, o instalador grava instalar-ia.flag na pasta do programa; na 1ª abertura o programa pergunta se é o PC 1 ou o PC 2 e instala tudo sozinho.
!include nsDialogs.nsh
!include LogicLib.nsh
!ifndef BUILD_UNINSTALLER
Var IACheck
Var IAState

!macro customPageAfterChangeDir
  Page custom iaPagina iaSaida
!macroend

Function iaPagina
  nsDialogs::Create 1018
  Pop $0
  ${NSD_CreateLabel} 0 0 100% 36u "IA interna (opcional): figurinhas, recorte de fundo, transcrição de áudio e leitura de vídeos rodando na placa de vídeo deste computador. Precisa de placa NVIDIA e uns 15 GB livres. A instalação acontece sozinha na primeira abertura do programa (10 a 40 min)."
  Pop $0
  ${NSD_CreateCheckbox} 0 44u 100% 14u "Instalar a IA interna neste computador"
  Pop $IACheck
  ${NSD_CreateLabel} 0 64u 100% 24u "Deixe desmarcado no Mac, em notebooks sem placa NVIDIA ou se este computador vai usar as IAs do PC 1 pela rede."
  Pop $0
  nsDialogs::Show
FunctionEnd

Function iaSaida
  ${NSD_GetState} $IACheck $IAState
FunctionEnd
!endif

!macro customInstall
  ${If} $IAState == ${BST_CHECKED}
    FileOpen $1 "$INSTDIR\instalar-ia.flag" w
    FileWrite $1 "1"
    FileClose $1
  ${EndIf}
!macroend
