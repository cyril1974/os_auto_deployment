# %UTILITY_FS%
# IpmiTool.efi %IPMI_CMD_PREFIX% 0x00 0x00 0x00 0x00 0x00 0x08
# echo Creating RAM Disk for Update Package(fs45)
# mkedk2ramdiskx64 -s 3072 fs45
# echo RAM Disk Creation for Update Package (fs45) Complete

echo Copy Update Package to fs45 Start
%PACKAGE_SOURCE_FS%
cp -r * %PACKAGE_FS%\
echo Copy Update Package to fs45 Complete
%UTILITY_FS%
# Send to client that Complete CUP Package
IpmiTool.efi %IPMI_CMD_PREFIX% 0x00 0x00 0x00 0x00 0x00 0x0A
%PACKAGE_FS%
ls
echo "cup_package_map" > %PACKAGE_FS%\cup_package_map

# Find Utility file system again because it was changed by system
# for %x run (0 40)
#    if exist fs%x:\uefi_utility_map then
#        fs%x:
#        set UTILITY_FS fs%x:
#        echo Re Map Utility File System to %UTILITY_FS%
#    endif
#endfor
set