import matplotlib.pyplot as plt
import csv
import os

# Đảm bảo thư mục tồn tại
if not os.path.exists('reports'): os.makedirs('reports')

scenarios = []
throughput = []
latency = []

try:
    with open('data/performance_log.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            scenarios.append(row['Scenario'])
            throughput.append(float(row['Throughput(Mbps)']))
            latency.append(float(row['Latency(ms)']))
except FileNotFoundError:
    print("[-] Không tìm thấy file data/performance_log.csv. Vui lòng chạy test trong Mininet trước!")
    exit()

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

# Biểu đồ 1: Băng thông (Càng cao càng tốt)
ax1.bar(scenarios, throughput, color=['#4dff4d', '#ff4d4d'], width=0.5, edgecolor='black')
ax1.set_title('So sánh Băng thông (Throughput)', fontweight='bold', fontsize=13)
ax1.set_ylabel('Megabits per second (Mbps)')
ax1.set_ylim(0, max(throughput) * 1.3 if throughput else 20)
for i, v in enumerate(throughput):
    ax1.text(i, v + (max(throughput)*0.02), f"{v} Mbps", ha='center', fontweight='bold', fontsize=11)

# Biểu đồ 2: Độ trễ (Càng thấp càng tốt)
ax2.bar(scenarios, latency, color=['#4dff4d', '#ff4d4d'], width=0.5, edgecolor='black')
ax2.set_title('So sánh Độ trễ (Latency)', fontweight='bold', fontsize=13)
ax2.set_ylabel('Milliseconds (ms)')
ax2.set_ylim(0, max(latency) * 1.3 if latency else 1.0)
for i, v in enumerate(latency):
    ax2.text(i, v + (max(latency)*0.02), f"{v} ms", ha='center', fontweight='bold', fontsize=11)

plt.suptitle('ĐÁNH GIÁ HIỆU NĂNG MẠNG TRƯỚC VÀ SAU KHI ÁP DỤNG BẢO MẬT', fontsize=15, fontweight='bold', y=1.05)
plt.tight_layout()
plt.savefig('reports/performance_comparison.png', dpi=300, bbox_inches='tight')
print("[+] Đã xuất biểu đồ so sánh tại: reports/performance_comparison.png")
plt.show()