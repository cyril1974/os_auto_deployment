# ipmicmdtool 20 00 08 07 01 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
# Send to client that Start copy utility
IpmiTool.efi %IPMI_CMD_PREFIX% 0x00 0x00 0x00 0x00 0x00 0x07
echo Creating RAM Disk for UEFI UTILITY (fs42)
mkedk2ramdiskx64 -s 128 fs42
echo RAM Disk Creation for UEFI UTILITY (fs42) Complete
echo Copy UEFI TOOL to fs42 Start
# echo "ramdisk_uefi_map" > fs42:\ramdisk_uefi_map
%UTILITY_FS%
cp -r * fs42:\
echo Copy UEFI TOOL to fs42 Complete
# Send to client that Complete copy utility
IpmiTool.efi %IPMI_CMD_PREFIX% 0x00 0x00 0x000x00 0x00 0x09
# ipmicmdtool 20 00 08 07 01 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
set UTILITY_FS fs42: