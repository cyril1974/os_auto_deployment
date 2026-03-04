@echo -off
mode 80 25

# +
# + ============================================================== +
#  Copyright (c) 2023, Intel Corporation.

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

#  Module Name:  rundeploy.nsh

#  Abstract:  UEFI Script file for initiating deploy.nsh script

cls
fs42:\ipmicmdtool 20 00 08 07 01 03 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
deploy.nsh > output
stall 60000000
fs42:\ipmicmdtool 20 00 08 07 01 04 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
stall 30000000

for %a run (1 10)
    echo run loop %a
    map -r
    for %x run (0 40)
        if exist fs%x:\ then
            if exist fs%x:\vmdrive_map then
                set vmdrive fs%x
                echo Copy output and results to fs%x
                for %y run (0 40)
                    if exist fs%y:\ramdisk_map then
                        copy fs%y:\output fs%x:
                        if exist fs%y:\syscfg.INI then
                            copy fs%y:\syscfg.INI fs%x:
                        endif
                        if exist fs%y:\deploy_result.log then
                            copy fs%y:\deploy_result.log fs%x:
                        endif
                        if exist fs%y:\deploy_details.log then
                            copy fs%y:\deploy_details.log fs%x:
                        endif
                        goto FOUNDIMAGE
                    endif
                endfor
            endif
        endif
    endfor
    stall 20000000
endfor

:NOTFOUND
echo "Unable to find ISMT drive".
echo "Unable to copy the output and results file".
echo ""
goto END
:FOUNDIMAGE
%vmdrive%:\ipmicmdtool 20 00 08 07 01 05 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
echo "Success!!!!"
:END
