set FOUND_CUP False
for %y run (0 40)
    if exist fs%y:\cup.manifest then
        set PACKAGE_SOURCE_FS fs%y:
        set PACKAGE_MOUNT_FS fs%y:
        echo Found Deploy Packages on fs%y:
        set FOUND_CUP True
        goto END_FINDCUP
    endif
endfor
goto END_FINDCUP

:END_FINDCUP
if "%FOUND_CUP%" == "False" then
  echo "Unable to find Update Packages".  
  echo "Please mount the drive with the update package".
  echo ""
  # Send to client that update package not found
  IpmiTool.efi %IPMI_CMD_PREFIX% 0x03 0x00 0x00 0x00 0x00 0x04
endif  
