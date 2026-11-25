@echo off
setlocal
set ROOT=%~dp0..\
set SRC=%ROOT%vendor\randomx-1.2.3
set BUILD=%ROOT%build\randomx
cmake -S "%SRC%" -B "%BUILD%" -A x64 -DCMAKE_BUILD_TYPE=Release
if errorlevel 1 exit /b %errorlevel%
cmake --build "%BUILD%" --config Release --parallel
if errorlevel 1 exit /b %errorlevel%
echo Built: %BUILD%\Release\randomx-benchmark.exe
