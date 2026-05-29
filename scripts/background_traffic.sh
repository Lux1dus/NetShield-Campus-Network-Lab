#!/bin/bash
# Tạo lưu lượng nền 3Mbps duy trì trong 120 giây
echo "[+] Đang tạo lưu lượng nền (3 Mbps)..."
iperf -u -c 203.0.113.1 -p 8080 -b 3M -t 120 > /dev/null 2>&1 &