#!/bin/bash
ROLE=$1

if [ "$ROLE" == "edge" ]; then
    # Extended ACL trên Edge Router
    iptables -F FORWARD
    iptables -P FORWARD DROP
    iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT
    
    # Cho phép luồng Web (TCP 80)
    iptables -A FORWARD -i r_edge-eth0 -p tcp -d 172.16.1.10 --dport 80 -j ACCEPT
    iptables -A FORWARD -i r_edge-eth0 -p tcp -d 172.16.1.20 --dport 80 -j ACCEPT
    
    # Mở luồng Iperf Test Hiệu năng (TCP 5001)
    iptables -A FORWARD -i r_edge-eth0 -p tcp -d 172.16.1.10 --dport 5001 -j ACCEPT
    
    # Mở luồng Iperf Test Load Balancing (UDP 8080)
    iptables -A FORWARD -i r_edge-eth0 -p udp -d 172.16.1.10 --dport 8080 -j ACCEPT
    iptables -A FORWARD -i r_edge-eth0 -p udp -d 172.16.1.20 --dport 8080 -j ACCEPT
    
    # Cho phép mạng nội bộ ra Internet
    iptables -A FORWARD -s 192.168.0.0/16 -o r_edge-eth0 -j ACCEPT

elif [ "$ROLE" == "core" ]; then
    # Standard ACL trên Core Router
    iptables -F FORWARD
    iptables -A FORWARD -s 192.168.30.0/24 -d 192.168.10.0/24 -j DROP
fi
