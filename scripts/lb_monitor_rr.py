#!/usr/bin/python3
"""
Round Robin Load Balancing Monitor (Cộng dồn & Bảo toàn luật cũ)
- Sử dụng += để tránh lỗi ghi đè 0 Mbps.
- Sử dụng module random 0.5 để chia tải đều 50-50.
- Không xóa (Flush) các luật mặc định của hệ thống.
"""
import os
import time
import csv
import subprocess

# Đảm bảo thư mục data tồn tại
if not os.path.exists('data'): os.makedirs('data')

# Cấu hình
INTERFACE = "r_edge-eth2"
WEB1_IP = "172.16.1.10"
WEB2_IP = "172.16.1.20"
LOG_FILE = "data/traffic_log_rr.csv"

def get_tx_bytes(iface):
    try:
        with open(f"/sys/class/net/{iface}/statistics/tx_bytes", "r") as f:
            return int(f.read().strip())
    except Exception:
        return 0

def get_iptables_bytes():
    """
    Lấy số byte thực tế (Cộng dồn từ mọi luật khớp IP và cổng 8080)
    """
    bytes_web1 = 0
    bytes_web2 = 0
    try:
        output = subprocess.check_output(['iptables', '-L', 'FORWARD', '-v', '-n', '-x']).decode('utf-8')
        for line in output.split('\n'):
            # Chỉ đếm traffic của cổng 8080 (cổng test)
            if '8080' in line:
                if WEB1_IP in line:
                    parts = line.split()
                    if len(parts) > 1: bytes_web1 += int(parts[1]) # Cộng dồn (Sum)
                elif WEB2_IP in line:
                    parts = line.split()
                    if len(parts) > 1: bytes_web2 += int(parts[1]) # Cộng dồn (Sum)
    except Exception:
        pass
    return bytes_web1, bytes_web2

def setup_round_robin():
    print(f"\n[+] ĐANG CÀI ĐẶT ROUND ROBIN (Bảo toàn cấu hình gốc)...", flush=True)
    
    # 1. Chèn luật NAT Round Robin lên ĐẦU chuỗi (Sử dụng module Random 0.5)
    # -I PREROUTING 1: Chèn vào vị trí số 1 để nó được ưu tiên xử lý trước
    # 50% xác suất ném sang Web 2
    os.system(f'iptables -t nat -I PREROUTING 1 -i r_edge-eth0 -p udp --dport 8080 -m statistic --mode random --probability 0.5 -j DNAT --to-destination {WEB2_IP}:8080')
    # 50% còn lại (không khớp luật trên) ném sang Web 1
    os.system(f'iptables -t nat -I PREROUTING 2 -i r_edge-eth0 -p udp --dport 8080 -j DNAT --to-destination {WEB1_IP}:8080')
    
    # 2. Chèn luật ĐẾM (Counting) vào bảng FORWARD
    os.system(f'iptables -I FORWARD 1 -d {WEB1_IP} -p udp --dport 8080 -j ACCEPT')
    os.system(f'iptables -I FORWARD 1 -d {WEB2_IP} -p udp --dport 8080 -j ACCEPT')
    
    # Xóa sạch cache connection cũ để áp dụng luật mới ngay
    os.system('conntrack -F > /dev/null 2>&1')

def cleanup():
    """ Dọn dẹp chỉ các luật mình đã chèn vào """
    print(f"\n[*] Đang dọn dẹp các luật Load Balancing...", flush=True)
    os.system(f'iptables -t nat -D PREROUTING -i r_edge-eth0 -p udp --dport 8080 -m statistic --mode random --probability 0.5 -j DNAT --to-destination {WEB2_IP}:8080 2>/dev/null')
    os.system(f'iptables -t nat -D PREROUTING -i r_edge-eth0 -p udp --dport 8080 -j DNAT --to-destination {WEB1_IP}:8080 2>/dev/null')
    os.system(f'iptables -D FORWARD -d {WEB1_IP} -p udp --dport 8080 -j ACCEPT 2>/dev/null')
    os.system(f'iptables -D FORWARD -d {WEB2_IP} -p udp --dport 8080 -j ACCEPT 2>/dev/null')

# Khởi tạo file log
with open(LOG_FILE, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Time', 'TotalMbps', 'Web1Mbps', 'Web2Mbps', 'Mode'])

setup_round_robin()

print(f"[*] Đang giám sát Round Robin (UDP 8080)...", flush=True)
old_bytes = get_tx_bytes(INTERFACE)
old_w1, old_w2 = get_iptables_bytes()
start_time = time.time()

try:
    while True:
        time.sleep(1)
        new_bytes = get_tx_bytes(INTERFACE)
        new_w1, new_w2 = get_iptables_bytes()
        
        # Tính Mbps
        total_mbps = (new_bytes - old_bytes) * 8 / 1048576.0
        w1_mbps = (new_w1 - old_w1) * 8 / 1048576.0
        w2_mbps = (new_w2 - old_w2) * 8 / 1048576.0
        
        # Cập nhật
        old_bytes, old_w1, old_w2 = new_bytes, new_w1, new_w2
        elapsed = int(time.time() - start_time)
        
        # In ra màn hình Xterm
        print(f"T: {elapsed}s | Tổng: {total_mbps:.2f} | Web1: {w1_mbps:.2f} | Web2: {w2_mbps:.2f}    ", end='\r', flush=True)
        
        with open(LOG_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([elapsed, round(total_mbps, 2), round(w1_mbps, 2), round(w2_mbps, 2), "RoundRobin"])

except KeyboardInterrupt:
    cleanup()
