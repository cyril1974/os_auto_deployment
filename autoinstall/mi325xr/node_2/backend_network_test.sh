#!/bin/bash 

 

# Define IP lists for all hosts 

host1_ip_list=(192.168.1.1 192.168.2.1 192.168.3.1 192.168.4.1 192.168.5.1 192.168.6.1 192.168.7.1 192.168.8.1) 

host2_ip_list=(192.168.1.2 192.168.2.2 192.168.3.2 192.168.4.2 192.168.5.2 192.168.6.2 192.168.7.2 192.168.8.2) 

host3_ip_list=(192.168.1.3 192.168.2.3 192.168.3.3 192.168.4.3 192.168.5.3 192.168.6.3 192.168.7.3 192.168.8.3) 

host4_ip_list=(192.168.1.4 192.168.2.4 192.168.3.4 192.168.4.4 192.168.5.4 192.168.6.4 192.168.7.4 192.168.8.4) 

 

# Merge all target host IPs into one array 

all_target_hosts=("${host1_ip_list[@]}" "${host3_ip_list[@]}" "${host4_ip_list[@]}") 

 

echo "=== Starting Network Connectivity Test ===" 

echo "Testing connectivity from host1 to all other hosts" 

 

# Ping from each host1 IP to all other host IPs 

for source_ip in "${host2_ip_list[@]}" 

do 

    for target_ip in "${all_target_hosts[@]}" 

    do 

        echo -e "\nping -I $source_ip $target_ip" 

        ping -I $source_ip -c 1 $target_ip > /dev/null 

        if [ $? == 0 ]; then 

            echo "Ping Passed" 

        else 

            echo -e "Ping Failed\n\n\n\n" 

            exit 5 

        fi 

    done 

done 

 

echo -e "\n=== All tests passed! Network connectivity is normal ===" 
