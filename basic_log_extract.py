import re
import csv
import os
from collections import defaultdict
import sys

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
all_days_seen = set()       # 记录所有出现过的天数（包括不可行的）
infeasible_days = set()     # 记录不可行的天数

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

        # 1. 检测新的一天
        day_match = re.search(r'开始计算第(\d+)天', line)
        if day_match:
            # 处理上一天的数据
            if method_data_list and not current_day_infeasible:
                all_records.extend(method_data_list)
            elif method_data_list and current_day_infeasible:
                print(f"第 {current_day} 天不可行，已跳过该天所有记录。")
                # 记录不可行天数
                if current_day is not None:
                    infeasible_days.add(current_day)
            
            current_day = int(day_match.group(1))
            all_days_seen.add(current_day)  # 记录该天出现
            method_idx = -1
            method_data_list = []
            in_summary = False
            current_day_infeasible = False
            continue

        # 2. 检测模型规模
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
                'rel_error': None,
                'price_sign': None
            }
            day_idx = current_day - 1
            if price_signs and day_idx in price_signs:
                rec['price_sign'] = price_signs[day_idx]
            method_data_list.append(rec)
            continue

        # 3. 变量类型
        var_match = re.search(r'Variable types: (\d+) continuous, (\d+) integer', line)
        if var_match and method_data_list:
            rec = method_data_list[-1]
            rec['continuous'] = int(var_match.group(1))
            rec['integer'] = int(var_match.group(2))
            continue

        # 4. 根节点松弛
        root_match = re.search(
            r'Root relaxation: objective ([\d\.e\+-]+), (\d+) iterations, ([\d\.]+) seconds', line
        )
        if root_match and method_data_list:
            rec = method_data_list[-1]
            rec['root_obj'] = float(root_match.group(1))
            rec['root_time'] = float(root_match.group(3))
            continue

        # 5. 检测不可行
        if re.search(r'Model is infeasible', line, re.IGNORECASE) or '模型不可行' in line:
            current_day_infeasible = True
            continue

        # 6. 求解完成时间
        solve_match = re.search(r'求解完成（状态=2），求解用时：([\d\.]+) 秒', line)
        if solve_match and method_data_list:
            rec = method_data_list[-1]
            rec['solve_time'] = float(solve_match.group(1))
            continue

        # 7. 最优目标值（需确保不是 '-'）
        best_match = re.search(r'Best objective ([\d\.e\+-]+)', line)
        if best_match and method_data_list:
            try:
                val = float(best_match.group(1))
                rec = method_data_list[-1]
                rec['best_obj'] = val
            except ValueError:
                # 如果无法转换（如 '-'），忽略，保持 None
                pass
            continue

        # 8. 汇总表格开始
        if '模型类型' in line and '目标值' in line and '求解时间' in line:
            in_summary = True
            continue

        # 9. 汇总表格数据行
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

        # 10. 汇总结束
        if '--------------------------------------------------------------------------------' in line and in_summary:
            in_summary = False
            if method_data_list and not current_day_infeasible:
                all_records.extend(method_data_list)
            elif method_data_list and current_day_infeasible:
                print(f"第 {current_day} 天不可行，已跳过该天所有记录。")
                if current_day is not None:
                    infeasible_days.add(current_day)
            method_data_list = []

# 处理最后的残留数据
if method_data_list and not current_day_infeasible:
    all_records.extend(method_data_list)
elif method_data_list and current_day_infeasible:
    print(f"第 {current_day} 天不可行，已跳过该天所有记录。")
    if current_day is not None:
        infeasible_days.add(current_day)

# ================== 统计并打印可行性信息 ==================
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

# ================== 计算加速比和相对误差（相对于 Basic） ==================
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
            rec['rel_error'] = (method_obj - basic_obj) / basic_obj * 100

# ================== 写入详细数据 CSV ==================
detail_csv = os.path.join(OUTPUT_DIR, 'details.csv')
fieldnames = [
    'day', 'method', 'price_sign', 'rows', 'cols', 'nonzeros',
    'continuous', 'integer', 'root_obj', 'root_time',
    'solve_time', 'best_obj', 'speedup', 'rel_error'
]

with open(detail_csv, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for rec in all_records:
        row = rec.copy()
        for k in ['speedup', 'rel_error']:
            if row.get(k) is not None:
                if k == 'speedup':
                    row[k] = f"{row[k]:.3f}"
                else:
                    row[k] = f"{row[k]:.4f}"
        writer.writerow(row)

print(f"详细数据已保存至: {detail_csv}，共 {len(all_records)} 条记录")

# ================== 计算总平均 ==================
def compute_averages(records):
    avg_dict = {}
    for method in METHOD_NAMES:
        recs = [r for r in records if r['method'] == method]
        if not recs:
            continue
        avg = {'method': method, 'count': len(recs)}
        numeric_fields = ['rows', 'cols', 'nonzeros', 'continuous', 'integer',
                          'root_obj', 'root_time', 'solve_time', 'best_obj',
                          'speedup', 'rel_error']
        for field in numeric_fields:
            values = [r[field] for r in recs if r[field] is not None]
            avg[field] = sum(values) / len(values) if values else None
        avg_dict[method] = avg
    return avg_dict

avg_all = compute_averages(all_records)

avg_csv = os.path.join(OUTPUT_DIR, 'averages.csv')
with open(avg_csv, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=['method', 'count', 'rows', 'cols', 'nonzeros',
                                           'continuous', 'integer', 'root_obj', 'root_time',
                                           'solve_time', 'best_obj', 'speedup', 'rel_error'])
    writer.writeheader()
    for method in METHOD_NAMES:
        if method in avg_all:
            row = avg_all[method].copy()
            for k in ['speedup', 'rel_error']:
                if row.get(k) is not None:
                    if k == 'speedup':
                        row[k] = f"{row[k]:.3f}"
                    else:
                        row[k] = f"{row[k]:.4f}"
            writer.writerow(row)

print(f"总平均值已保存至: {avg_csv}")

# ================== 按电价符号分别统计 ==================
if price_signs:
    sign_groups = {'positive': [], 'negative': []}
    for rec in all_records:
        sign = rec.get('price_sign')
        if sign in sign_groups:
            sign_groups[sign].append(rec)

    sign_avg_rows = []
    for sign, recs in sign_groups.items():
        if not recs:
            continue
        avg_dict = compute_averages(recs)
        for method, avg in avg_dict.items():
            row = avg.copy()
            row['sign'] = sign
            row['count'] = len([r for r in recs if r['method'] == method])
            sign_avg_rows.append(row)

    sign_csv = os.path.join(OUTPUT_DIR, 'price_sign_averages.csv')
    with open(sign_csv, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=['sign', 'method', 'count', 'rows', 'cols',
                                               'nonzeros', 'continuous', 'integer',
                                               'root_obj', 'root_time', 'solve_time',
                                               'best_obj', 'speedup', 'rel_error'])
        writer.writeheader()
        for row in sign_avg_rows:
            for k in ['speedup', 'rel_error']:
                if row.get(k) is not None:
                    if k == 'speedup':
                        row[k] = f"{row[k]:.3f}"
                    else:
                        row[k] = f"{row[k]:.4f}"
            writer.writerow(row)

    print(f"正负电价场景平均已保存至: {sign_csv}")
    positive_days = sum(1 for s in price_signs.values() if s == 'positive')
    negative_days = sum(1 for s in price_signs.values() if s == 'negative')
    print(f"电价符号统计：正电价天数 = {positive_days}，负电价天数 = {negative_days}")
else:
    print("未读取电价信息，跳过正负电价统计。")