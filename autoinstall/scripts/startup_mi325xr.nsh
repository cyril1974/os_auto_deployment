
@echo -on
#  mode 80 25
#  Module Name:  startup.nsh
#  Abstract:  Startup script to initiate deploy

cls
for %x run (0 40)
    if exist fs%x:\startup.nsh then
        fs%x:
        # ls
        if exist fs%x:\EFI\BOOT\grub.cfg then
            IpmiTool.efi 0x0A 0x44 0x00 0x00 0x02 0x00 0x00 0x00 0x00 0x21 0x00 0x04 0x12 0x00 0x6F 0xA 0x00 0x00
            cd EFI\BOOT
            bootx64.efi
            goto END
        endif
        echo "Unable to find OS boot file (grub.cfg) on fs%x:"
    endif
endfor

echo "Unable to find startup.nsh on any filesystem"

# Send to client that server is boot and startup is activate
# if %PLATFORM% == "EGS" then
#     env_egs.nsh
# endif 

# if %PLATFORM% == "BHS" then
#     env_bhs.nsh
# endif

# set ipmiCommand "%IPMI_CMD_PREFIX% %IPMI_SEVERITY_NOTICE% %IPMI_CATEGORY_FLOW% %IPMI_RESERVE% %IPMI_BOOT_OK%"
# echo %ipmiCommand%
# %IPMITOOL% %ipmiCommand%
# for %x run (0 40)
#     if exist fs%x:\uefitool_map then
#         if exist fs%x:\startup.nsh then
#             fs%x:
#             set UTILITY_SOURCE_FS fs%x:
#             set LOG_FS fs%x:
#             echo Found UEFI Utility Package on fs%x: >> log_startup.txt
#             goto FOUNDUEFITOOL
#          endif
#     endif
# endfor
# echo "Unable to find Utility Packages".  >> log_startup.txt
# echo "Please confirm the inband mount for the utility is normally". >> log_startup.txt
# echo ""
# set ABORT True
# # Send to client that utility package not found
# %IPMITOOL% %IPMI_CMD_PREFIX% %IPMI_SEVERITY_NOTICE% %IPMI_CATEGORY_FLOW% %IPMI_RESERVE% %IPMI_FOUND_NO_UTILITY_PACKAGE%
# goto END
# 
# 
# :FOUNDUEFITOOL
# %UTILITY_SOURCE_FS%
# echo Main Flow Start.... > log_startup.txt
# main_flow.nsh
# goto END

:END
echo Startup Process End....
      