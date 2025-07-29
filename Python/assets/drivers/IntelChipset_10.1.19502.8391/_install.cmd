@ECHO OFF
SETLOCAL ENABLEDELAYEDEXPANSION
SETLOCAL ENABLEEXTENSIONS

GOTO INIT

:RUNTIME 
	%~d0
	CD %~p0
	
	IF EXIST C:\Windows\ConfigSetRoot (
		CALL SetupChipset.exe 
		PAUSE
	) ELSE (
		CALL SetupChipset.exe
		GOTO EXIT_POINT
	)

	GOTO EXIT_POINT

:INIT
   	IF "%PROCESSOR_ARCHITECTURE%" EQU "amd64" (
		>NUL 2>&1 "%SYSTEMROOT%\SysWOW64\cacls.exe" "%SYSTEMROOT%\SysWOW64\config\system"
	) ELSE (
		>NUL 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
	)
	
	IF '%errorlevel%' NEQ '0' (
		GOTO UACPROMT
	) ELSE ( 
		GOTO RUNTIME 
	)

	GOTO EXIT_POINT

:UACPROMT
	ECHO Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
	SET params= %*
	ECHO UAC.ShellExecute "cmd.exe", "/c ""%~s0"" %params:"=""%", "", "runas", 1 >> "%temp%\getadmin.vbs"
	"%temp%\getadmin.vbs"
	DEL "%temp%\getadmin.vbs"
	EXIT /B
	
	GOTO EXIT_POINT

:EXIT_POINT
	GOTO:EOF