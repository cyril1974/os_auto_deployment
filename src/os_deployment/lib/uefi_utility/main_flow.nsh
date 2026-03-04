#  Module Name:  main_flow.nsh
#  Abstract:  Main Flow Control script to deploy mcup
%UTILITY_SOURCE_FS%
find_cup_fs.nsh >> logs\log_find_cup.txt
if "%FOUND_CUP%" == "True" then
    goto FOUNDIMAGE
else
set ABORT True
    goto END_MAIN   
endif


:FOUNDIMAGE

echo "Create RAM DISK for ALL"

if exist "%UTILITY_SOURCE_FS%\Do_SSD_Update" then
    echo Creating RAM Disk for SSD Update(fs49)
    %UTILITY_SOURCE_FS%
    mkedk2ramdiskx64 -s  128 fs49
    fs49:
    echo "This is SSD Drive" > map_ssd_drive
    echo RAM Disk Creation for SSD Update (fs49) Complete
    map -r
endif    


echo Creating RAM Disk for UEFI UTILITY (fs42)
%UTILITY_SOURCE_FS%
mkedk2ramdiskx64 -s 128 fs42
fs42:
echo "This is Utility Drive" > map_utility_drive
echo RAM Disk Creation for UEFI UTILITY (fs42) Complete
map -r

if not exist "%UTILITY_SOURCE_FS%\Do_SSD_Update" then
    echo Creating RAM Disk for Component Package Update(fs41)
    %UTILITY_SOURCE_FS%
    mkedk2ramdiskx64 -s 1024 fs41
    fs41:
    echo "This is Component Drive" > map_component_drive
    echo RAM Disk Creation for Update Package (fs41) Complete
    map -r

    echo Creating RAM Disk for Update Package(fs45)
    %UTILITY_SOURCE_FS%
    mkedk2ramdiskx64 -s 3092 fs45
    fs45:
    echo "This is Package Drive" > map_package_drive
    echo RAM Disk Creation for Update Package (fs45) Complete
    map -r
endif    

for %x run (0 40)
    if exist fs%x:\map_utility_drive then
        set UTILITY_FS fs%x:
    endif

    if exist fs%x:\map_package_drive then
        set PACKAGE_FS fs%x:
    endif

    if exist fs%x:\map_component_drive then
        set COMPONENT_FS fs%x:
    endif

    if exist fs%x:\map_ssd_drive then
        set SSD_FS fs%x:
    endif
endfor

set
if not exist "%UTILITY_SOURCE_FS%\Do_SSD_Update" then
    %LOG_FS%
    echo "Create Utility FS Start"
    create_utility_filesystem.nsh >> logs\log_create_utility.txt
    echo "Create Utility FS End"

    %LOG_FS%
    echo "Create CUP FS Start"
    create_cup_package_filesystem.nsh >> logs\log_create_cup.txt
    echo "Create CUP FS End"
endif

### Start Firmware Update Here ###
echo Firmware Update Start....
set path %path%;%UTILITY_FS%\
%UTILITY_FS%
# Send to client that Firmware Update Start
%IPMITOOL% %IPMI_CMD_PREFIX% %IPMI_SEVERITY_NOTICE% %IPMI_CATEGORY_FLOW% %IPMI_RESERVE% %IPMI_START_UPDATE_FIRMWARE%
stall %SHORT_DELAY%
if exist "%UTILITY_SOURCE_FS%\Do_SSD_Update" then
    goto SSD
endif

:BOARD
if exist "%UTILITY_FS%\SUP_updated" then
    %IPMITOOL% %IPMI_CMD_PREFIX% %IPMI_SEVERITY_WARNING% %IPMI_CATEGORY_SUP% %IPMI_RESERVE% %IPMI_BOARD_FIRMWARE_UPDATE_REBOOT%
    goto COMPONENT
endif

if exist "%UTILITY_FS_SOURCE%\SUP_updated" then
    %IPMITOOL% %IPMI_CMD_PREFIX% %IPMI_SEVERITY_WARNING% %IPMI_CATEGORY_SUP% %IPMI_RESERVE% %IPMI_BOARD_FIRMWARE_UPDATE_REBOOT%
    goto COMPONENT
endif

if exist "%PACKAGE_MOUNT_FS%\SUP" then
    # Send to client that Start Update Board Firmware
    %IPMITOOL% %IPMI_CMD_PREFIX% %IPMI_SEVERITY_NOTICE% %IPMI_CATEGORY_FLOW% %IPMI_RESERVE% %IPMI_FIND_BOARD_FIRMWARE%
    stall %MED_DELAY%
    %PACKAGE_MOUNT_FS%
    cd \SUP
    if exist "startup.nsh" then
        echo "SUP update is executed" > %UTILITY_FS%\SUP_updated
        startup.nsh > %LOG_FS%\logs\SUP_update.log
    else
        goto COMPONENT
    endif 

    if %lasterror% == 0 then
        echo "SUP update Success..."
        %IPMITOOL% %IPMI_CMD_PREFIX% %IPMI_SEVERITY_OK% %IPMI_CATEGORY_SUP% %IPMI_RESERVE% %IPMI_BOARD_FIRMWARE_UPDATE_SUCCESS%
    else
        echo "SUP update Fail..."
        %IPMITOOL% %IPMI_CMD_PREFIX% %IPMI_SEVERITY_CRITICAL% %IPMI_CATEGORY_SUP% %IPMI_RESERVE% %IPMI_BOARD_FIRMWARE_UPDATE_FAIL%
    endif 
    goto COMPONENT    
else
    # Send to client that Pass Board Firmware
    %IPMITOOL% %IPMI_CMD_PREFIX% %IPMI_SEVERITY_NOTICE% %IPMI_CATEGORY_FLOW% %IPMI_RESERVE% %IPMI_FIND_NO_BOARD_FIRMWARE%
    goto COMPONENT    
endif    

:COMPONENT
if exist "%UTILITY_FS%\Component_updated" then
    %IPMITOOL% %IPMI_CMD_PREFIX% %IPMI_SEVERITY_WARNING% %IPMI_CATEGORY_COMPONENT% %IPMI_RESERVE% %IPMI_COMPONENT_FIRMWARE_UPDATE_REBOOT%
    goto SSD
endif

if exist "%PACKAGE_FS%\UEFI" then
    # Send to client that Start Update Board Firmware
    %IPMITOOL% %IPMI_CMD_PREFIX% %IPMI_SEVERITY_NOTICE% %IPMI_CATEGORY_FLOW% %IPMI_RESERVE% %IPMI_FIND_COMPONENT_FIRMWARE%
    stall %MED_DELAY%
    cp -q %UTILITY_FS%\ISDMTool.efi %PACKAGE_FS%\UEFI\
    cp -q %UTILITY_FS%\update.nsh %PACKAGE_FS%\UEFI\
    %PACKAGE_FS%
    cd \UEFI
    cp -r * %COMPONENT_FS%\
    %COMPONENT_FS%
    if exist "isdm.manifest" then
        update.nsh > %LOG_FS%\logs\UEFI_update.log
    else
        %IPMITOOL% %IPMI_CMD_PREFIX% %IPMI_SEVERITY_NOTICE% %IPMI_CATEGORY_FLOW% %IPMI_RESERVE% %IPMI_FIND_NO_COMPONENT_FIRMWARE%
        goto SSD
    endif        
    if %compresult% == 0 then
        echo "UEFI update Success..."
        %IPMITOOL% %IPMI_CMD_PREFIX% %IPMI_SEVERITY_OK% %IPMI_CATEGORY_COMPONENT% %IPMI_RESERVE% %IPMI_COMPONENT_FIRMWARE_UPDATE_SUCCESS%
    else
        echo "UEFI update Fail..."
        %IPMITOOL% %IPMI_CMD_PREFIX% %IPMI_SEVERITY_CRITICAL% %IPMI_CATEGORY_COMPONENT% %IPMI_RESERVE% %IPMI_COMPONENT_FIRMWARE_UPDATE_FAIL%
    endif
    echo "Component update is executed" > %UTILITY_FS%\Component_updated
    echo "Component update is executed" > %LOGO_FS%\Component_updated
    goto SSD  
else
    # Send to client that Pass Board Firmware
    %IPMITOOL% %IPMI_CMD_PREFIX% %IPMI_SEVERITY_NOTICE% %IPMI_CATEGORY_FLOW% %IPMI_RESERVE% %IPMI_FIND_NO_COMPONENT_FIRMWARE%
    goto SSD
endif      

:SSD
if exist "%PACKAGE_SOURCE_FS%\SSD" then
    # Send to client that Start Update Board Firmware
    if exist "%UTILITY_SOURCE_FS%\Do_SSD_Update" then
        rm  %UTILITY_SOURCE_FS%\Do_SSD_Update
        %IPMITOOL% %IPMI_CMD_PREFIX% %IPMI_SEVERITY_NOTICE% %IPMI_CATEGORY_FLOW% %IPMI_RESERVE% %IPMI_FIND_SSD_FIRMWARE%
        stall %MED_DELAY%
        cp -q %UTILITY_FS%\ssd_update.nsh %PACKAGE_FS%\SSD\
        %IPMITOOL% %IPMI_CMD_PREFIX% %IPMI_SEVERITY_OK% %IPMI_CATEGORY_SSD% %IPMI_RESERVE% %IPMI_COPY_SSD_FIRMWARE_UPDATE_BOOT_IMAGE%
        %PACKAGE_SOURCE_FS%
        cd \SSD
        %IPMITOOL% %IPMI_CMD_PREFIX% %IPMI_SEVERITY_OK% %IPMI_CATEGORY_SSD% %IPMI_RESERVE% %IPMI_TRY_TO_BOOT_SYSTEM%
        ssd_update.nsh
        goto LOGS  
    else
        echo "Do SSH Update after reboot" > %UTILITY_SOURCE_FS%\Do_SSD_Update
        reset -w "Reboot to Update SSD Firmware"
    endif    
else
    # Send to client that Pass Board Firmware
    %IPMITOOL% %IPMI_CMD_PREFIX% %IPMI_SEVERITY_NOTICE% %IPMI_CATEGORY_FLOW% %IPMI_RESERVE% %IPMI_FIND_NO_SSD_FIRMWARE%
    goto LOGS
endif      

:LOGS
%IPMITOOL% %IPMI_CMD_PREFIX% %IPMI_SEVERITY_NOTICE% %IPMI_CATEGORY_FLOW% %IPMI_RESERVE% %IPMI_LOG_COLLECTING_START%
stall %MED_DELAY%
cp -r %UTILITY_FS%\logs\* %LOG_FS%\logs\
goto END_MAIN   

:END_MAIN
echo "Main Process End"





