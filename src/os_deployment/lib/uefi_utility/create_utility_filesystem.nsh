# ipmicmdtool 20 00 08 07 01 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
# Send to client that Start copy CUP Package
%UTILITY_SOURCE_FS%
# IpmiTool.efi %IPMI_CMD_PREFIX% 0x00 0x00 0x00 0x00 0x00 0x07
# echo Creating RAM Disk for UEFI UTILITY (fs42)
# mkedk2ramdiskx64 -s 128 fs42
# echo RAM Disk Creation for UEFI UTILITY (fs42) Complete
# IpmiTool.efi %IPMI_CMD_PREFIX% 0x00 0x00 0x00 0x00 0x00 0x09

%UTILITY_SOURCE_FS%
echo Copy UEFI TOOL to %UTILITY_FS% Start
cp -r * %UTILITY_FS%\
echo Copy UEFI TOOL to %UTILITY_FS% Complete
# Send to client that Complete copy utility
IpmiTool.efi %IPMI_CMD_PREFIX% 0x00 0x00 0x000x00 0x00 0x09
echo "uefi_utility_map" > %UTILITY_FS%\uefi_utility_map




