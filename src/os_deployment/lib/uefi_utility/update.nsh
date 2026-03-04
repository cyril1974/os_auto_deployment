@echo -off

load ipmi.efi

echo Running ISDMTool
isdmtool.efi
set compresult %lasterror%
echo ISDMTool Exit code: %code%

mkdir %COMPONENT_FS%\comp_logs
cp -q -r %COMPONENT_FS%\logs\* %COMPONENT_FS%\comp_logs\
cp -q -r %COMPONENT_FS%\*.log  %COMPONENT_FS%\comp_logs\
ls -r %COMPONENT_FS%\comp_logs > %COMPONENT_FS%\comp_logs\index.txt
cp -q -r %COMPONENT_FS%\comp_logs %UTILITY_FS%\logs\
cp -q -r %COMPONENT_FS%\comp_logs %LOG_FS%\logs\
echo 'Update Complete'

stall 12000000

