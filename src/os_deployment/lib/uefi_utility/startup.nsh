
# FORCE_EFI_BOOT
@echo -on
#  mode 80 25
#  Module Name:  startup.nsh
#  Abstract:  Startup script to initiate deploy

set ABORT False
set SHORT_DELAY 3000000
set MED_DELAY 6000000
set LONG_DELAAY 10000000
cls
for %x run (0 40)
    if exist fs%x:\ipmi.efi then
        fs%x:
        load ipmi.efi
        platform_config.nsh
    endif
endfor

# Send to client that server is boot and startup is activate
if %PLATFORM% == "EGS" then
    env_egs.nsh
endif 

if %PLATFORM% == "BHS" then
    env_bhs.nsh
endif

set ipmiCommand "%IPMI_CMD_PREFIX% %IPMI_SEVERITY_NOTICE% %IPMI_CATEGORY_FLOW% %IPMI_RESERVE% %IPMI_BOOT_OK%"
echo %ipmiCommand%
%IPMITOOL% %ipmiCommand%
for %x run (0 40)
    if exist fs%x:\uefitool_map then
        if exist fs%x:\startup.nsh then
            fs%x:
            set UTILITY_SOURCE_FS fs%x:
            set LOG_FS fs%x:
            echo Found UEFI Utility Package on fs%x: >> log_startup.txt
            goto FOUNDUEFITOOL
         endif
    endif
endfor
echo "Unable to find Utility Packages".  >> log_startup.txt
echo "Please confirm the inband mount for the utility is normally". >> log_startup.txt
echo ""
set ABORT True
# Send to client that utility package not found
%IPMITOOL% %IPMI_CMD_PREFIX% %IPMI_SEVERITY_NOTICE% %IPMI_CATEGORY_FLOW% %IPMI_RESERVE% %IPMI_FOUND_NO_UTILITY_PACKAGE%
goto END


:FOUNDUEFITOOL
%UTILITY_SOURCE_FS%
echo Main Flow Start.... > log_startup.txt
main_flow.nsh
goto END

:END
echo Startup Process End....

if "%ABORT%" == "True" then
   %IPMITOOL% %IPMI_CMD_PREFIX% %IPMI_SEVERITY_NOTICE% %IPMI_CATEGORY_FLOW% %IPMI_RESERVE% %IPMI_FOUND_NO_UTILITY_PACKAGE%
else
   %IPMITOOL% %IPMI_CMD_PREFIX% %IPMI_SEVERITY_NOTICE% %IPMI_CATEGORY_FLOW% %IPMI_RESERVE% %IPMI_PROCESS_COMPLETE%
endif        