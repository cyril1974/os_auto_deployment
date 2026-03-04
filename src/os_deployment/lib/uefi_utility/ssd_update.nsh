@echo -off
mode 80 25

# +
# + ============================================================== +
#  Copyright (c) 2022, Intel Corporation.

#  This source code and any documentation accompanying it ("Material") is furnished
#  under license and may only be used or copied in accordance with the terms of that
#  license.  No license, express or implied, by estoppel or otherwise, to any
#  intellectual property rights is granted to you by disclosure or delivery of these
#  Materials.  The Materials are subject to change without notice and should not be
#  construed as a commitment by Intel Corporation to market, license, sell or support
#  any product or technology.  Unless otherwise provided for in the license under which
#  this Material is provided, the Material is provided AS IS, with no warranties of
#  any kind, express or implied, including without limitation the implied warranties
#  of fitness, merchantability, or non-infringement.  Except as expressly permitted by
#  the license for the Material, neither Intel Corporation nor its suppliers assumes
#  any responsibility for any errors or inaccuracies that may appear herein.  Except
#  as expressly permitted by the license for the Material, no part of the Material
#  may be reproduced, stored in a retrieval system, transmitted in any form, or
#  distributed by any means without the express written consent of Intel Corporation.

#  Module Name:  ssd_update.nsh

#  Abstract:  UEFI Script file for invoking SSD firmware update

# for %x run (0 40)
#    if exist fs%x:\SSD\initrd then
#        fs%x:
#        echo Found SSD Deploy Packages on fs%x:
#        goto FOUNDIMAGE
#    endif
# endfor
#
#
# goto END

# :FOUNDIMAGE

# mkedk2ramdiskx64 -s 128 fs42

# cp -q -r fs%x:\SSD\* fs42:\

for %d in *
    if exist "%d\initrd" then
        cp -q -r  %d\* %SSD_FS%\
        set
        %SSD_FS%
        cd EFI\BOOT
        bootx64.efi
    endif
endfor        


# for %d in (*)
#    if exist "%d\initrd" then
#        cp -q -r  %d\* %SSD_FS%\       
#    endif
#endfor

# set
# %SSD_FS%
# cd EFI\BOOT
# bootx64.efi

:END
