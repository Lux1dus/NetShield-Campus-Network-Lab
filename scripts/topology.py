#!/usr/bin/python
# -*- coding: utf-8 -*-

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node, OVSSwitch, Controller, RemoteController
from mininet.log import setLogLevel, info
from mininet.cli import CLI
import mininet.term 
import os
import time
import re
import csv
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

# =====================================================
# ĐỊNH NGHĨA MÀU SẮC TOÀN CỤC
# =====================================================
GREEN = '\033[92m'
RED = '\033[91m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
ENDC = '\033[0m'
BOLD = '\033[1m'

def log_msg(message, level="INFO"):
    prefix = f"[{BLUE}*{ENDC}]"
    if level == "SUCCESS": prefix = f"[{GREEN}v{ENDC}]"
    if level == "ERROR": prefix = f"[{RED}!{ENDC}]"
    if level == "WARN": prefix = f"[{YELLOW}?{ENDC}]"
    print(f"{prefix} {message}")

# =====================================================
# CÁC LỚP HỖ TRỢ (ROUTER & TOPO)
# =====================================================
class LinuxRouter(Node):
    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        self.cmd('sysctl -w net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl -w net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()

class CampusTopo(Topo):
    def build(self):
        r_edge = self.addNode('r_edge', cls=LinuxRouter, ip='203.0.113.1/24', privateDirs=['/var/run/frr'])
        r_core1 = self.addNode('r_core1', cls=LinuxRouter, ip='10.0.0.2/30', privateDirs=['/var/run/frr'])
        r_core2 = self.addNode('r_core2', cls=LinuxRouter, ip='10.0.0.6/30', privateDirs=['/var/run/frr'])

        s_dmz = self.addSwitch('s_dmz', dpid='10', stp=True, failMode='standalone')
        s_dist1 = self.addSwitch('s_dist1', dpid='11', stp=True, failMode='standalone')
        s_dist2 = self.addSwitch('s_dist2', dpid='12', stp=True, failMode='standalone')
        s_acc1 = self.addSwitch('s_acc1', dpid='13', stp=True, failMode='standalone') 
        s_acc2 = self.addSwitch('s_acc2', dpid='14', stp=True, failMode='standalone') 
        s_acc3 = self.addSwitch('s_acc3', dpid='15', stp=True, failMode='standalone')

        h1 = self.addHost('h1', ip='192.168.10.10/24', defaultRoute='via 192.168.10.254')
        h2 = self.addHost('h2', ip='192.168.20.10/24', defaultRoute='via 192.168.20.254')
        h3 = self.addHost('h3', ip='192.168.20.11/24', defaultRoute='via 192.168.20.254')
        h4 = self.addHost('h4', ip='192.168.30.10/24', defaultRoute='via 192.168.30.254')
        
        web1 = self.addHost('web1', ip='172.16.1.10/24', defaultRoute='via 172.16.1.254')
        web2 = self.addHost('web2', ip='172.16.1.20/24', defaultRoute='via 172.16.1.254')
        db1 = self.addHost('db1', ip='172.16.1.30/24', defaultRoute='via 172.16.1.254')
        h_out = self.addHost('h_out', ip='203.0.113.100/24', defaultRoute='via 203.0.113.1')

        self.addLink(r_edge, h_out)
        self.addLink(r_edge, r_core1)
        self.addLink(r_edge, s_dmz)
        
        self.addLink(r_core1, r_core2)
        self.addLink(r_core1, s_dist1)
        self.addLink(r_core1, s_dist2)
        self.addLink(r_core2, s_dist1)
        self.addLink(r_core2, s_dist2)

        self.addLink(s_dist1, s_acc1)
        self.addLink(s_dist1, s_acc2)
        self.addLink(s_dist2, s_acc2)
        self.addLink(s_dist2, s_acc3)

        self.addLink(h1, s_acc1)
        self.addLink(h2, s_acc2)
        self.addLink(h3, s_acc2)
        self.addLink(h4, s_acc3)
        
        self.addLink(web1, s_dmz)
        self.addLink(web2, s_dmz)
        self.addLink(db1, s_dmz)

def startFRR(node, router_id, networks, is_edge=False):
    node_name = node.name
    os.system(f'rm -rf /tmp/{node_name}') 
    os.system(f'mkdir -p /tmp/{node_name}')

    with open(f'/tmp/{node_name}/zebra.conf', 'w') as f:
        f.write(f"hostname {node_name}\nlog file /tmp/{node_name}/zebra.log\n")
        
    with open(f'/tmp/{node_name}/ospfd.conf', 'w') as f:
        f.write(f"hostname {node_name}\nlog file /tmp/{node_name}/ospfd.log\n")
        f.write("router ospf\n")
        f.write(f" ospf router-id {router_id}\n")
        for net in networks:
            f.write(f" network {net} area 0\n")
        if is_edge:
            f.write(" default-information originate always\n")
            
    os.system(f'chown -R frr:frr /tmp/{node_name}')
    os.system(f'chmod 777 /tmp/{node_name}')
    
    node.cmd(f'/usr/lib/frr/zebra -f /tmp/{node_name}/zebra.conf -d -z /tmp/{node_name}/zebra.api -i /tmp/{node_name}/zebra.pid')
    node.cmd(f'/usr/lib/frr/ospfd -f /tmp/{node_name}/ospfd.conf -d -z /tmp/{node_name}/zebra.api -i /tmp/{node_name}/ospfd.pid')

# =====================================================
# GIAO DIỆN CLI TÙY CHỈNH
# =====================================================
class CampusCLI(CLI):
    def log(self, message, level="INFO"):
        log_msg(message, level)

    def do_firewall_on(self, line):
        "Kích hoạt cơ chế bảo mật đa tầng từ file acl.sh"
        net = self.mn
        self.log("Đang nạp luật bảo mật từ file acl.sh...")
        os.system('chmod +x scripts/acl.sh 2>/dev/null || chmod +x acl.sh')
        cmd_path = "scripts/acl.sh" if os.path.exists("scripts/acl.sh") else "./acl.sh"
        
        for role, name in [('edge', 'r_edge'), ('core', 'r_core1'), ('core', 'r_core2')]:
            net.get(name).cmd(f'{cmd_path} {role}')
        
        self.mn.fw_state = 'ON'
        self.log("HỆ THỐNG PHÒNG THỦ ĐÃ SẴN SÀNG!", "SUCCESS")

    def do_firewall_off(self, line):
        "Bãi bỏ toàn bộ ACL và Firewall bằng dropacl.sh"
        net = self.mn
        self.log("Đang bãi bỏ các luật bảo mật...")
        os.system('chmod +x scripts/dropacl.sh 2>/dev/null || chmod +x dropacl.sh')
        cmd_path = "scripts/dropacl.sh" if os.path.exists("scripts/dropacl.sh") else "./dropacl.sh"
        
        for name in ['r_edge', 'r_core1', 'r_core2']:
            net.get(name).cmd(f'{cmd_path}')
            
        self.mn.fw_state = 'OFF'
        self.log("FIREWALL is OFF. Mạng đang mở hoàn toàn!", "WARN")

    # ================= KIỂM THỬ HIỆU NĂNG =================
    def _run_performance_test(self, scenario_name, mode):
        net = self.mn
        web1, h_out = net.get('web1', 'h_out')
        self.log(f"Đang chạy kiểm thử: {BOLD}{scenario_name}{ENDC}")
        
        time.sleep(1) 
        ping_out = h_out.cmd('ping -c 10 -W 1 203.0.113.1')
        lat_match = re.search(r'rtt min/avg/max/mdev = [\d.]+/([\d.]+)', ping_out)
        latency = float(lat_match.group(1)) if lat_match else 0.0
        
        web1.cmd('iperf -s -p 5001 > /dev/null 2>&1 &')
        iperf_out = h_out.cmd('iperf -c 203.0.113.1 -p 5001 -t 10 -f m')
        bw_match = re.search(r'(\d+(\.\d+)?)\s*Mbits/sec', iperf_out)
        throughput = float(bw_match.group(1)) if bw_match else 0.0
        web1.cmd('killall -9 iperf 2>/dev/null')

        if not os.path.exists('data'): os.makedirs('data')
        with open('data/performance_log.csv', mode, newline='') as f:
            writer = csv.writer(f)
            if mode == 'w':
                writer.writerow(['Scenario', 'Throughput(Mbps)', 'Latency(ms)'])
            writer.writerow([scenario_name, throughput, latency])
        self.log(f"Hoàn tất! {throughput} Mbps | {latency} ms", "SUCCESS")

    def do_test_baseline(self, line):
        "Test hiệu năng khi CHƯA có Firewall"
        if getattr(self.mn, 'fw_state', 'OFF') == 'ON':
            self.log("LỖI: Firewall đang BẬT! Vui lòng chạy 'firewall_off' trước khi test baseline.", "ERROR")
            return
        self._run_performance_test('Chưa bật Firewall/ACL', 'w')

    def do_test_protected(self, line):
        "Test hiệu năng khi ĐÃ CÓ Firewall"
        if getattr(self.mn, 'fw_state', 'OFF') == 'OFF':
            self.log("LỖI: Firewall đang TẮT! Vui lòng chạy 'firewall_on' trước khi test protected.", "ERROR")
            return
        self._run_performance_test('Đã bật Firewall/ACL', 'a')

    def do_draw_compare(self, line):
        "Xuất biểu đồ so sánh hiệu năng mạng (Băng thông & Độ trễ)"
        self.log("Đang đọc dữ liệu từ data/performance_log.csv...")
        self.log("Đang xuất biểu đồ so sánh...")
        # Lệnh chạy script vẽ đồ thị độc lập
        os.system('python3 scripts/draw_compare.py 2>/dev/null || python3 draw_compare.py')

    # ================= LOAD BALANCING ROUND ROBIN =================
    
    def do_prepare_test_rr(self, line):
        "Bắt đầu Round Robin Load Balancing (Tăng lên 50 luồng để chia đều hơn)"
        if getattr(self.mn, 'fw_state', 'OFF') == 'OFF':
            self.log("LỖI: Hãy chạy 'firewall_on' trước để mở cổng UDP 8080!", "ERROR")
            return
            
        net = self.mn
        h_out, r_edge = net.get('h_out', 'r_edge')
        
        self.log("Khởi động Monitor trên r_edge (Chế độ Đếm Gói Tin Chi Tiết)...")
        net.terms += mininet.term.makeTerm(r_edge, title='RR Monitor', cmd='python3 scripts/lb_monitor_rr.py')
        
        time.sleep(2)
        self.log("ĐANG BƠM TRAFFIC (10Mbps UDP, 50 Luồng song song để chia đều 50-50)...", "WARN")
        # Tăng -P lên 50 để phân bổ xác suất đều hơn trong Linux NAT
        h_out.cmd('iperf -u -c 203.0.113.1 -p 8080 -b 10M -t 40 -P 50 > /dev/null 2>&1 &')
        self.log("Dữ liệu đang được chia! Hãy dùng 'draw_rr' hoặc 'heatmap_rr' để xem.", "SUCCESS")

    def do_draw_rr(self, line):
        "Vẽ biểu đồ phân bổ tải 50-50 (Stackplot)"
        self.log("Đang xuất biểu đồ Round Robin...")
        os.system('python3 scripts/draw_chart_rr.py')

    def do_heatmap_rr(self, line):
        "Xuất Bản đồ nhiệt kiểm toán toàn diện (Bản siêu gọn)"
        import matplotlib.pyplot as plt
        import numpy as np
        from matplotlib.colors import ListedColormap
        from matplotlib.patches import Patch
        
        net = self.mn
        routers = {'Edge': net.get('r_edge'), 
                   'Core1': net.get('r_core1'), 
                   'Core2': net.get('r_core2')}
        
        self.log("Đang phân tích cấu trúc Tường lửa và Load Balancing...")
        rules, packets, colors_map = [], [], []
        
        for r_name, router in routers.items():
            output = router.cmd('iptables -L FORWARD -v -n -x')
            lines = output.strip().split('\n')[2:] 
            
            seen_8080 = set() # Bộ lọc để vứt bỏ các dòng bị che khuất
            
            for row in lines:
                parts = row.split()
                if len(parts) >= 9:
                    pkts = int(parts[0])
                    target = parts[2]
                    source = parts[7]
                    dest = parts[8]
                    
                    extra_info = " ".join(parts[9:])
                    
                    if 'ESTABLISHED' in extra_info:
                        rule_name = f"[{r_name}] Stateful Firewall (Luồng đã duyệt)"
                        
                    elif 'dpt:5001' in extra_info:
                        rule_name = f"[{r_name}] Mở cổng 5001 (Iperf Test) -> Web 1"
                        
                    elif 'dpt:8080' in extra_info or '8080' in extra_info:
                        srv = "Web 1" if '172.16.1.10' in dest else "Web 2"
                        if srv in seen_8080:
                            continue # Bỏ qua hoàn toàn, không vẽ lên biểu đồ
                        seen_8080.add(srv)
                        rule_name = f"[{r_name}] LB UDP 8080 -> {srv}"
                        
                    elif 'dpt:80' in extra_info:
                        srv = "Web 1" if '172.16.1.10' in dest else "Web 2"
                        rule_name = f"[{r_name}] Mở cổng 80 (HTTP) -> {srv}"
                        
                    else:
                        rule_name = f"[{r_name}] {target}: {source} -> {dest}"
                        
                    rules.append(rule_name)
                    packets.append(pkts)
                    colors_map.append(1 if target == 'ACCEPT' else -1)
        
        if sum(packets) == 0 or not rules:
            self.log("Chưa có traffic đi qua Firewall. Hãy chạy lệnh test trước!", "ERROR")
            return

        fig, ax = plt.subplots(figsize=(14, len(rules)*0.8 + 2))
        heatmap_data = np.array(colors_map).reshape(-1, 1)
        cmap = ListedColormap(['#ff4d4d', '#4dff4d']) 
        
        ax.matshow(heatmap_data, cmap=cmap, aspect='auto')
        ax.set_xticks([])
        ax.set_yticks(range(len(rules)))
        ax.set_yticklabels(rules, fontsize=11, fontweight='bold')
        
        for i in range(len(rules)):
            pkt_count = packets[i]
            weight = 'bold' if pkt_count > 0 else 'normal'
            ax.text(0, i, f"{pkt_count:,} pkts", va='center', ha='center', color='black', fontweight=weight, fontsize=13)
            
        plt.title('Bản Đồ Nhiệt Kiểm Toán: Firewall ACL & Load Balancing', pad=30, fontweight='heavy', fontsize=16)
        
        legend_elements = [Patch(facecolor='#4dff4d', edgecolor='black', label='ACCEPT (Cho phép)'),
                           Patch(facecolor='#ff4d4d', edgecolor='black', label='DROP (Ngăn chặn)')]
        ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1.35, 1.05))

        plt.tight_layout()
        plt.savefig('reports/comprehensive_heatmap.png', dpi=300, bbox_inches='tight')
        self.log("Đã lưu Heatmap siêu gọn vào reports/comprehensive_heatmap.png", "SUCCESS")
        plt.show()

    def do_exit(self, line):
        "Thoát"
        return True

# =====================================================
# KHỞI CHẠY MẠNG
# =====================================================
def runNet():
    topo = CampusTopo()
    net = Mininet(topo=topo, controller=None)
    net.start()
    
    r_edge = net.get('r_edge')
    r_core1 = net.get('r_core1')
    r_core2 = net.get('r_core2')

    r_edge.cmd('ifconfig r_edge-eth1 10.0.0.1 netmask 255.255.255.252')
    r_edge.cmd('ifconfig r_edge-eth0 203.0.113.1 netmask 255.255.255.0')
    r_edge.cmd('ifconfig r_edge-eth2 172.16.1.254 netmask 255.255.255.0')
    r_core1.cmd('ifconfig r_core1-eth0 10.0.0.2 netmask 255.255.255.252')
    r_core1.cmd('ifconfig r_core1-eth1 10.0.0.5 netmask 255.255.255.252')
    r_core1.cmd('ifconfig r_core1-eth2 192.168.10.254 netmask 255.255.255.0')
    r_core1.cmd('ifconfig r_core1-eth3 192.168.20.254 netmask 255.255.255.0')
    r_core2.cmd('ifconfig r_core2-eth0 10.0.0.6 netmask 255.255.255.252')
    r_core2.cmd('ifconfig r_core2-eth1 192.168.30.254 netmask 255.255.255.0')

    startFRR(r_edge, '1.1.1.1', ['10.0.0.0/30', '172.16.1.0/24'], is_edge=True)
    startFRR(r_core1, '2.2.2.2', ['10.0.0.0/30', '10.0.0.4/30', '192.168.10.0/24', '192.168.20.0/24'])
    startFRR(r_core2, '3.3.3.3', ['10.0.0.4/30', '192.168.30.0/24'])

    log_msg("Đang chờ OSPF hội tụ...", "WARN")
    time.sleep(15)

    r_edge.cmd('iptables -t nat -A POSTROUTING -o r_edge-eth0 -s 192.168.0.0/16 -j MASQUERADE')
    r_edge.cmd('iptables -t nat -A PREROUTING -i r_edge-eth0 -p tcp --dport 5001 -j DNAT --to-destination 172.16.1.10:5001')
    r_edge.cmd('iptables -t nat -A PREROUTING -i r_edge-eth0 -p tcp --dport 80 -j DNAT --to-destination 172.16.1.10:80')
    net.get('web1').cmd('python3 -m http.server 80 > /dev/null 2>&1 &')
    net.get('web2').cmd('python3 -m http.server 80 > /dev/null 2>&1 &')

    print(f"\n{BLUE}{BOLD}A. KIỂM THỬ HIỆU NĂNG & ACL (Chương 5):{ENDC}")
    print(f"   Step 1: {YELLOW}test_baseline{ENDC}   -> Đo băng thông khi chưa bật bảo mật")
    print(f"   Step 2: {YELLOW}firewall_on{ENDC}     -> Kích hoạt Firewall & ACL đa lớp")
    print(f"   Step 3: {YELLOW}test_protected{ENDC}  -> Đo lại băng thông để thấy ảnh hưởng")
    print(f"   Step 4: {YELLOW}draw_compare{ENDC}    -> Xem biểu đồ so sánh Băng thông & Độ trễ")
    
    print(f"\n{BLUE}{BOLD}B. KIỂM THỬ CÂN BẰNG TẢI ROUND ROBIN (Yêu cầu mới):{ENDC}")
    print(f"   Step 1: {YELLOW}prepare_test_rr{ENDC} -> Chạy Monitor & Bơm 50 luồng traffic UDP 8080")
    print(f"   Step 2: {YELLOW}draw_rr{ENDC}         -> Xem biểu đồ Mbps phân bổ 50-50 (Stackplot)")
    print(f"   Step 3: {YELLOW}heatmap_rr{ENDC}      -> Xem tổng dung lượng MB tích lũy trên các Server")
    
    print(f"\n{RED}Lưu ý: Luôn chạy 'firewall_on' trước khi test Round Robin để mở cổng 8080.{ENDC}\n")
    
    CampusCLI(net).cmdloop()
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    runNet()
