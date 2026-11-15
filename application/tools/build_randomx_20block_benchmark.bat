@echo off
setlocal
set ROOT=%~dp0..\
set SRC=%ROOT%vendor\randomx-1.2.3
set BUILD=%ROOT%build\randomx
call "%ROOT%tools\build_randomx_benchmark.bat"
if errorlevel 1 exit /b %errorlevel%
if not exist "%BUILD%\Release\randomx.lib" (
  echo RandomX static library not found: %BUILD%\Release\randomx.lib
  exit /b 2
)
cl /nologo /O2 /std:c++14 /EHsc /I"%SRC%\src" "%ROOT%tools\randomx_20block_benchmark.cpp" /link /LIBPATH:"%BUILD%\Release" randomx.lib /OUT:"%BUILD%\Release\randomx-20block-benchmark.exe"
if errorlevel 1 exit /b %errorlevel%
echo Built: %BUILD%\Release\randomx-20block-benchmark.exe
