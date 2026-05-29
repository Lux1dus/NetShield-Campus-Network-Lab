import matplotlib.pyplot as plt
import csv
import os
import numpy as np

# Đảm bảo thư mục tồn tại
if not os.path.exists('reports'): os.makedirs('reports')

times = []
total_mbps = []
web1_mbps = []
web2_mbps = []

# Đọc dữ liệu từ file log Round Robin
try:
    with open('data/traffic_log_rr.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            times.append(int(row['Time']))
            total_mbps.append(float(row['TotalMbps']))
            web1_mbps.append(float(row['Web1Mbps']))
            web2_mbps.append(float(row['Web2Mbps']))
except FileNotFoundError:
    print("Không tìm thấy file data/traffic_log_rr.csv. Hãy chạy 'prepare_test_rr' trước!")
    exit()

# Thuật toán làm mượt (Moving Average) để đồ thị đẹp hơn
def moving_average(data, window_size=5):
    return np.convolve(data, np.ones(window_size)/window_size, mode='valid')

window = 5
if len(times) > window:
    w_times = times[window-1:]
    w_web1 = moving_average(web1_mbps, window)
    w_web2 = moving_average(web2_mbps, window)
    w_total = moving_average(total_mbps, window)
else:
    w_times = times
    w_web1 = web1_mbps
    w_web2 = web2_mbps
    w_total = total_mbps

plt.figure(figsize=(10, 6))

# VẼ BIỂU ĐỒ ĐƯỜNG (LINE CHART) THAY VÌ STACKPLOT
# Dùng linewidth=2 để đường vẽ đậm, rõ nét
plt.plot(w_times, w_web1, label='Lưu lượng Web 1', color='#3498db', linewidth=2.5)
plt.plot(w_times, w_web2, label='Lưu lượng Web 2', color='#e67e22', linewidth=2.5)

# Vẽ đường tổng lưu lượng
plt.plot(w_times, w_total, label='Tổng Traffic (r_edge)', color='black', linestyle='--', linewidth=1.5)

# Tô một lớp nền mờ xám dưới đường Tổng để tạo cảm giác "Khung giới hạn băng thông"
plt.fill_between(w_times, w_total, color='gray', alpha=0.08)

plt.title('Cơ chế Cân bằng tải Round Robin (Line Chart)', fontsize=15, fontweight='bold', pad=15)
plt.xlabel('Thời gian (giây)', fontsize=12)
plt.ylabel('Băng thông (Mbps)', fontsize=12)

# Tự động co giãn trục Y
if len(w_total) > 0:
    plt.ylim(0, max(w_total) * 1.15)
else:
    plt.ylim(0, 15)

plt.grid(True, linestyle=':', alpha=0.6)
plt.legend(loc='lower center', bbox_to_anchor=(0.5, -0.18), ncol=3, frameon=False)

plt.tight_layout()
plt.savefig('reports/round_robin_chart.png', dpi=300)
print("Đã xuất biểu đồ Round Robin Line Chart: reports/round_robin_chart.png")
plt.show()