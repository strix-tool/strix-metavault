; Strix MetaVault - NSIS setup wizard (Modern UI 2)
; Build with:  makensis windows\StrixMetaVault.nsi
; Requires dist\Strix MetaVault.exe (produced by PyInstaller via build_installer.bat).

Unicode true
!include "MUI2.nsh"

!define APP_NAME    "Strix MetaVault"
!define APP_VERSION "1.0.0"
!define APP_EXE     "Strix MetaVault.exe"
!define APP_ICON    "metavault.ico"
!define APP_PUBLISHER "Strix MetaVault"
!define SRC_DIR     "${__FILEDIR__}\.."
!define UNINST_KEY  "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"

Name "${APP_NAME}"
OutFile "${__FILEDIR__}\Strix-MetaVault-Setup.exe"
InstallDir "$LOCALAPPDATA\${APP_NAME}"
InstallDirRegKey HKCU "Software\${APP_NAME}" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
ShowInstDetails show
ShowUnInstDetails show

VIProductVersion "1.0.0.0"
VIAddVersionKey "ProductName"     "${APP_NAME}"
VIAddVersionKey "FileDescription" "${APP_NAME} Setup"
VIAddVersionKey "FileVersion"     "1.0.0.0"
VIAddVersionKey "ProductVersion"  "1.0.0.0"
VIAddVersionKey "LegalCopyright"  "(c) 2026 ${APP_PUBLISHER}"

!define MUI_ABORTWARNING
!define MUI_ICON   "${SRC_DIR}\metavault.ico"
!define MUI_UNICON "${SRC_DIR}\metavault.ico"
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Launch ${APP_NAME}"

; ----- Installer pages -----
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "${SRC_DIR}\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; ----- Uninstaller pages -----
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; ----- Install -----
Section "${APP_NAME} (required)" SecMain
  SectionIn RO
  SetOutPath "$INSTDIR"
  File "${SRC_DIR}\dist\${APP_EXE}"
  File "${SRC_DIR}\README.md"
  File "/oname=LICENSE.txt" "${SRC_DIR}\LICENSE"
  File "${SRC_DIR}\${APP_ICON}"

  ; optional bundled tools (only if present at build time)
  SetOutPath "$INSTDIR\tools"
  File /nonfatal "${SRC_DIR}\tools\*.exe"
  File /nonfatal "${SRC_DIR}\tools\*.txt"
  SetOutPath "$INSTDIR"

  ; shortcuts
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortCut  "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_ICON}" 0
  CreateShortCut  "$SMPROGRAMS\${APP_NAME}\Uninstall ${APP_NAME}.lnk" "$INSTDIR\Uninstall.exe"
  CreateShortCut  "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_ICON}" 0

  ; registry: install location + Add/Remove Programs entry
  WriteRegStr   HKCU "Software\${APP_NAME}" "InstallDir" "$INSTDIR"
  WriteRegStr   HKCU "${UNINST_KEY}" "DisplayName"     "${APP_NAME}"
  WriteRegStr   HKCU "${UNINST_KEY}" "DisplayVersion"  "${APP_VERSION}"
  WriteRegStr   HKCU "${UNINST_KEY}" "Publisher"       "${APP_PUBLISHER}"
  WriteRegStr   HKCU "${UNINST_KEY}" "DisplayIcon"     "$INSTDIR\${APP_EXE}"
  WriteRegStr   HKCU "${UNINST_KEY}" "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegStr   HKCU "${UNINST_KEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoRepair" 1

  WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

; ----- Uninstall -----
Section "Uninstall"
  Delete "$INSTDIR\${APP_EXE}"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\LICENSE.txt"
  Delete "$INSTDIR\${APP_ICON}"
  Delete "$INSTDIR\tools\*.exe"
  Delete "$INSTDIR\tools\*.txt"
  RMDir  "$INSTDIR\tools"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir  "$INSTDIR"

  Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
  Delete "$SMPROGRAMS\${APP_NAME}\Uninstall ${APP_NAME}.lnk"
  RMDir  "$SMPROGRAMS\${APP_NAME}"
  Delete "$DESKTOP\${APP_NAME}.lnk"

  DeleteRegKey HKCU "${UNINST_KEY}"
  DeleteRegKey HKCU "Software\${APP_NAME}"
SectionEnd
