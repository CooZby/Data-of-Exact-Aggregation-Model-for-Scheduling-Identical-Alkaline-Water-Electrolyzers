import re
import csv
import os
from collections import defaultdict
import sys
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patheffects as path_effects

# ================== 用户可配置参数 ==================
LOG_FILE = "logs/Gap0_E5_24_10s.log"                # 日志文件路径
OUTPUT_DIR = "Gap0_E5_24_10s_res"               # 输出文件夹
EXCEL_FILE = "inputdata/System1_m.xlsx"    # 电价 Excel 文件（如不存在则跳过）
# 若从文件名无法解析设备数和时长，可手动指定：
DEVICES = None      # 例如 5，None 表示自动从文件名解析
DURATION = None     # 例如 24，None 表示自动从文件名解析
# ==================================================

METHOD_NAMES = ['Basic', 'AA', 'TestAgg', 'AA_R', 'AA_R_Cold']

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ================== 从文件名解析设备数和时长 ==================
def parse_devices_duration_from_filename(filename):
    basename = os.path.basename(filename)
    match = re.search(r'E(\d+)_(\d+)', basename)
    if match:
        devices = int(match.group(1))
        duration = int(match.group(2))
        return devices, duration
    return None, None

if DEVICES is None or DURATION is None:
    auto_devices, auto_duration = parse_devices_duration_from_filename(LOG_FILE)
    if DEVICES is None:
        DEVICES = auto_devices
    if DURATION is None:
        DURATION = auto_duration

if DEVICES is None or DURATION is None:
    print("警告：无法从文件名解析设备数和时长，请手动设置 DEVICES 和 DURATION 变量。")
    print("将使用默认值：DEVICES=5, DURATION=24")
    DEVICES = DEVICES or 5
    DURATION = DURATION or 24

print(f"识别到设备数: {DEVICES}, 时长: {DURATION}")

# ================== 读取电价并判断正负 ==================
def get_price_signs(excel_path, devices, duration):
    sign_map = {}
    if not os.path.exists(excel_path):
        print(f"警告：电价文件不存在 ({excel_path})，将跳过电价符号标记。")
        return sign_map

    try:
        import DataRead
        data = DataRead.DataReader(excel_path, duration, devices)
        if hasattr(data, 'price_full'):
            full_price = data.price_full
        else:
            total_days = data.DayMax
            data.set_schedule_days(list(range(total_days)))
            full_price = data.price
        total_points = len(full_price)
        num_days = total_points // duration
        for day_idx in range(num_days):
            start = day_idx * duration
            end = start + duration
            day_prices = full_price[start:end]
            if any(p < 0 for p in day_prices):
                sign_map[day_idx] = 'negative'
            else:
                sign_map[day_idx] = 'positive'
        print(f"成功使用 DataRead 读取电价，共 {num_days} 天，负电价天数: {sum(1 for v in sign_map.values() if v=='negative')}")
        return sign_map
    except ImportError:
        print("未找到 DataRead 模块，尝试使用 pandas 读取 Excel...")
        try:
            import pandas as pd
            df = pd.read_excel(excel_path, header=0)
            price_col = None
            for col in df.columns:
                if 'price' in col.lower() or '电价' in col:
                    price_col = col
                    break
            if price_col is None:
                print("无法识别价格列，请确保 Excel 中包含 'price' 或 '电价' 列名。")
                return {}
            price_series = df[price_col].values.flatten()
            total_points = len(price_series)
            num_days = total_points // duration
            for day_idx in range(num_days):
                start = day_idx * duration
                end = start + duration
                day_prices = price_series[start:end]
                if any(p < 0 for p in day_prices):
                    sign_map[day_idx] = 'negative'
                else:
                    sign_map[day_idx] = 'positive'
            print(f"使用 pandas 读取成功，负电价天数: {sum(1 for v in sign_map.values() if v=='negative')}")
            return sign_map
        except Exception as e:
            print(f"使用 pandas 读取 Excel 失败: {e}")
            return {}
    except Exception as e:
        print(f"读取电价数据出错: {e}")
        return {}

price_signs = get_price_signs(EXCEL_FILE, DEVICES, DURATION)

# ================== 解析日志 ==================
all_records = []
all_days_seen = set()
infeasible_days = set()

current_day = None
method_idx = -1
method_data_list = []
in_summary = False
current_day_infeasible = False

with open(LOG_FILE, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue

        day_match = re.search(r'开始计算第(\d+)天', line)
        if day_match:
            if method_data_list and not current_day_infeasible:
                all_records.extend(method_data_list)
            elif method_data_list and current_day_infeasible:
                print(f"第 {current_day} 天不可行，已跳过该天所有记录。")
                if current_day is not None:
                    infeasible_days.add(current_day)
            
            current_day = int(day_match.group(1))
            all_days_seen.add(current_day)
            method_idx = -1
            method_data_list = []
            in_summary = False
            current_day_infeasible = False
            continue

        model_match = re.search(
            r'Optimize a model with (\d+) rows, (\d+) columns and (\d+) nonzeros', line
        )
        if model_match and current_day is not None:
            method_idx += 1
            rec = {
                'day': current_day,
                'method': METHOD_NAMES[method_idx] if method_idx < len(METHOD_NAMES) else 'Unknown',
                'rows': int(model_match.group(1)),
                'cols': int(model_match.group(2)),
                'nonzeros': int(model_match.group(3)),
                'continuous': None,
                'integer': None,
                'root_obj': None,
                'root_time': None,
                'solve_time': None,
                'best_obj': None,
                'speedup': None,
                'abs_error': None,      # ===== 修改点：用 abs_error 代替 rel_error =====
                'price_sign': None
            }
            day_idx = current_day - 1
            if price_signs and day_idx in price_signs:
                rec['price_sign'] = price_signs[day_idx]
            method_data_list.append(rec)
            continue

        var_match = re.search(r'Variable types: (\d+) continuous, (\d+) integer', line)
        if var_match and method_data_list:
            rec = method_data_list[-1]
            rec['continuous'] = int(var_match.group(1))
            rec['integer'] = int(var_match.group(2))
            continue

        root_match = re.search(
            r'Root relaxation: objective ([\d\.e\+-]+), (\d+) iterations, ([\d\.]+) seconds', line
        )
        if root_match and method_data_list:
            rec = method_data_list[-1]
            rec['root_obj'] = float(root_match.group(1))
            rec['root_time'] = float(root_match.group(3))
            continue

        if re.search(r'Model is infeasible', line, re.IGNORECASE) or '模型不可行' in line:
            current_day_infeasible = True
            continue

        solve_match = re.search(r'求解完成（状态=2），求解用时：([\d\.]+) 秒', line)
        if solve_match and method_data_list:
            rec = method_data_list[-1]
            rec['solve_time'] = float(solve_match.group(1))
            continue

        best_match = re.search(r'Best objective ([\d\.e\+-]+)', line)
        if best_match and method_data_list:
            try:
                val = float(best_match.group(1))
                rec = method_data_list[-1]
                rec['best_obj'] = val
            except ValueError:
                pass
            continue

        if '模型类型' in line and '目标值' in line and '求解时间' in line:
            in_summary = True
            continue

        if in_summary and method_data_list:
            parts = line.split()
            if len(parts) >= 3:
                potential_method = parts[0]
                if potential_method in METHOD_NAMES:
                    try:
                        obj_val = float(parts[1])
                        time_val = float(parts[2])
                        if obj_val == -1.0:
                            current_day_infeasible = True
                        for rec in method_data_list:
                            if rec['method'] == potential_method:
                                rec['best_obj'] = obj_val
                                rec['solve_time'] = time_val
                                break
                    except ValueError:
                        pass

        if '--------------------------------------------------------------------------------' in line and in_summary:
            in_summary = False
            if method_data_list and not current_day_infeasible:
                all_records.extend(method_data_list)
            elif method_data_list and current_day_infeasible:
                print(f"第 {current_day} 天不可行，已跳过该天所有记录。")
                if current_day is not None:
                    infeasible_days.add(current_day)
            method_data_list = []

if method_data_list and not current_day_infeasible:
    all_records.extend(method_data_list)
elif method_data_list and current_day_infeasible:
    print(f"第 {current_day} 天不可行，已跳过该天所有记录。")
    if current_day is not None:
        infeasible_days.add(current_day)

# ================== 统计可行性 ==================
total_days = len(all_days_seen)
feasible_days = total_days - len(infeasible_days)
if total_days > 0:
    feasible_pct = (feasible_days / total_days) * 100
    infeasible_pct = (len(infeasible_days) / total_days) * 100
else:
    feasible_pct = infeasible_pct = 0.0

print("\n" + "=" * 60)
print("📊 求解可行性统计")
print("=" * 60)
print(f"总天数: {total_days}")
print(f"可行天数: {feasible_days} ({feasible_pct:.2f}%)")
print(f"不可行天数: {len(infeasible_days)} ({infeasible_pct:.2f}%)")
if infeasible_days:
    print(f"不可行天数列表: {sorted(infeasible_days)}")
print("=" * 60 + "\n")

# ================== 计算加速比和绝对误差（相对于 Basic） ==================
days_dict = defaultdict(list)
for rec in all_records:
    days_dict[rec['day']].append(rec)

for day, recs in days_dict.items():
    basic_rec = None
    for rec in recs:
        if rec['method'] == 'Basic':
            basic_rec = rec
            break
    if basic_rec is None:
        continue
    basic_time = basic_rec.get('solve_time')
    basic_obj = basic_rec.get('best_obj')
    if basic_time is None or basic_time == 0 or basic_obj is None or basic_obj == 0:
        continue
    for rec in recs:
        if rec['method'] == 'Basic':
            continue
        method_time = rec.get('solve_time')
        method_obj = rec.get('best_obj')
        if method_time is not None and method_time > 0:
            rec['speedup'] = basic_time / method_time
        if method_obj is not None:
            # ===== 修改点：计算绝对误差（单位：$） =====
            rec['abs_error'] = abs(method_obj - basic_obj)   # 绝对值，单位$

# ================== 写入详细数据 CSV ==================
detail_csv = os.path.join(OUTPUT_DIR, 'details.csv')
fieldnames = [
    'day', 'method', 'price_sign', 'rows', 'cols', 'nonzeros',
    'continuous', 'integer', 'root_obj', 'root_time',
    'solve_time', 'best_obj', 'speedup', 'abs_error'   # ===== 修改点：替换 rel_error 为 abs_error =====
]

with open(detail_csv, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for rec in all_records:
        row = rec.copy()
        # 格式化数值
        if row.get('speedup') is not None:
            row['speedup'] = f"{row['speedup']:.3f}"
        if row.get('abs_error') is not None:
            row['abs_error'] = f"{row['abs_error']:.4f}"
        # 其他字段保留原样
        writer.writerow(row)

print(f"详细数据已保存至: {detail_csv}，共 {len(all_records)} 条记录")

# ================== 打印提取的数据（绝对误差统计） ==================
print("\n📊 绝对误差统计（单位：$）")
print("=" * 70)
print(f"{'Method':<12} {'Price Sign':<12} {'Mean Abs Error':<20} {'Min Abs Error':<20} {'Max Abs Error':<20}")
print("-" * 70)

# 按方法和电价场景分组统计
grouped = defaultdict(list)
for rec in all_records:
    if rec['method'] != 'Basic' and rec['abs_error'] is not None:
        key = (rec['method'], rec['price_sign'])
        grouped[key].append(rec['abs_error'])

for (method, sign), errors in sorted(grouped.items()):
    mean_err = np.mean(errors)
    min_err = np.min(errors)
    max_err = np.max(errors)
    sign_display = sign if sign else 'Unknown'
    print(f"{method:<12} {sign_display:<12} {mean_err:<20.4f} {min_err:<20.4f} {max_err:<20.4f}")
print("=" * 70 + "\n")

# ================== 绘制绝对误差条带图（正/负电价场景） ==================
# 准备绘图数据
plot_data = defaultdict(lambda: {'positive': {'means': [], 'mins': [], 'maxs': []},
                                 'negative': {'means': [], 'mins': [], 'maxs': []}})

for (method, sign), errors in grouped.items():
    if sign in ['positive', 'negative']:
        plot_data[method][sign]['means'].append(np.mean(errors))
        plot_data[method][sign]['mins'].append(np.min(errors))
        plot_data[method][sign]['maxs'].append(np.max(errors))

# 方法顺序（排除 Basic）
method_order = ['AA', 'TestAgg', 'AA_R', 'AA_R_Cold']
x_pos = np.arange(len(method_order))

# 颜色配置（正/负电价不同色调）
colors = {
    'positive': '#2878B5',   # 蓝色
    'negative': '#E15759'    # 红色
}

plt.rcParams['font.family'] = 'Times New Roman'
plt.rcParams['font.size'] = 12

fig, ax = plt.subplots(figsize=(8, 5))

# 绘制正电价条带（蓝色）和负电价条带（红色）
for i, method in enumerate(method_order):
    # 正电价
    if 'positive' in plot_data[method]:
        pdata = plot_data[method]['positive']
        mean_val = pdata['means'][0]
        min_val = pdata['mins'][0]
        max_val = pdata['maxs'][0]
        # 条带（半透明填充）
        ax.fill_between([i-0.3, i+0.3], min_val, max_val, color=colors['positive'], alpha=0.3, edgecolor=colors['positive'], linewidth=1)
        # 均值线（实线+标记）
        ax.plot([i-0.3, i+0.3], [mean_val, mean_val], color=colors['positive'], linewidth=2, label='_nolegend_')
        ax.scatter(i, mean_val, color=colors['positive'], s=50, zorder=5, marker='o')
        # 标注均值
        ax.text(i, mean_val + 0.02*(max_val-min_val), f'{mean_val:.2f}', ha='center', va='bottom', fontsize=9, color=colors['positive'])
    # 负电价
    if 'negative' in plot_data[method]:
        ndata = plot_data[method]['negative']
        mean_val = ndata['means'][0]
        min_val = ndata['mins'][0]
        max_val = ndata['maxs'][0]
        # 条带（半透明填充）
        ax.fill_between([i-0.1, i+0.1], min_val, max_val, color=colors['negative'], alpha=0.3, edgecolor=colors['negative'], linewidth=1)
        # 均值线（虚线+方块标记）
        ax.plot([i-0.1, i+0.1], [mean_val, mean_val], color=colors['negative'], linewidth=2, linestyle='--', label='_nolegend_')
        ax.scatter(i, mean_val, color=colors['negative'], s=50, zorder=5, marker='s')
        ax.text(i, mean_val - 0.02*(max_val-min_val), f'{mean_val:.2f}', ha='center', va='top', fontsize=9, color=colors['negative'])

# 图例
from matplotlib.lines import Line2D
legend_elements = [
    Line2D([0], [0], color=colors['positive'], linewidth=2, marker='o', markersize=8, label='Positive price'),
    Line2D([0], [0], color=colors['negative'], linewidth=2, linestyle='--', marker='s', markersize=8, label='Negative price')
]
ax.legend(handles=legend_elements, loc='upper left', frameon=True, edgecolor='black', fancybox=False, fontsize=10)

ax.set_xticks(x_pos)
ax.set_xticklabels(method_order, fontsize=12)
ax.set_ylabel('Absolute Error ($)', fontsize=12)
ax.grid(axis='y', linestyle='--', alpha=0.3)
ax.tick_params(axis='x', direction='in')
ax.tick_params(axis='y', direction='in')

plt.tight_layout()
plot_path = os.path.join(OUTPUT_DIR, 'abs_error_band.png')
plt.savefig(plot_path, dpi=300, bbox_inches='tight')
plt.savefig(os.path.join(OUTPUT_DIR, 'abs_error_band.pdf'), bbox_inches='tight')
print(f"绝对误差条带图已保存至: {plot_path}")
plt.show()

print("\n✅ 数据处理完成！")