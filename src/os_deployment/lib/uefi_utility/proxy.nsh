@echo -off
mode 80 25

# Flatten Dir
cp -q %1\* . > f1_tmp

echo Running ISDM Command

# Prep exec script
echo %2 > test.nsh

echo Executing: %2
date
time

#Exec command
test.nsh

date
time
echo ISDM Command Run Complete

# Copy logs
cp -q -r *.log logs\. > f1_tmp

# Cleanup
#rm *.*
