# ipmicmdtool 20 00 08 07 01 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
# Send to client that Start copy CUP Package
%UTILITY_FS%
IpmiTool.efi %IPMI_CMD_PREFIX% 0x00 0x00 0x00 0x00 0x00 0x08
echo Creating RAM Disk for Update Package(fs45)
mkedk2ramdiskx64 -s 4096 fs45
echo RAM Disk Creation for Update Package (fs45) Complete
echo Update Package to fs45 Start
# echo "ramdisk_package_map" > fs45:\ramdisk_package_map
%PACKAGE_FS%
cp -r * fs45:\
echo Copy Update Package to fs45 Complete
%UTILITY_FS%
# Send to client that Complete CUP Package
IpmiTool.efi %IPMI_CMD_PREFIX% 0x00 0x00 0x00 0x00 0x00 0x0A
# ipmicmdtool 20 00 08 07 01 02 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
%PACKAGE_FS%
ls