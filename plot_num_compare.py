import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import matplotlib.patheffects as path_effects

# ================== 配置 ==================
E10_PATH = "E10_log_res/details.csv"   # 请修改为实际路径
E15_PATH = "E15_log_res/details.csv"   # 请修改为实际路径
OUTPUT_DIR = "num_comparison_figures"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 方法名称映射
method_mapping = {
    'Basic': 'S-AWE',
    'AA': 'AA',
    'AA_R': 'VA-1',
    'AA_R_Cold': 'VA-2',
    'TestAgg': 'EA'
}
method_order = ['S-AWE', 'AA', 'VA-1', 'VA-2', 'EA']

# ============================================================================
# ===== 颜色配置（可调节） =====
# ============================================================================
# 柱状图：深色（E10）和浅色（E15）——同一方法同一色系
COLORS_DARK = ["#999999", "#4E79A7", "#59A14F", "#F28E2B", "#E15759"]
COLORS_LIGHT = ["#CCCCCC", "#8FB3D9", "#A8D08D", "#FAC090", "#F5A0A0"]

# 中间轴（E10）和右轴（E15）的主色
E10_COLOR = "#4E79A7"   # 蓝色系
E15_COLOR = "#E15759"   # 红色系

# E10 条带图颜色
E10_BAND_COLOR = "#8FB3D9"   # 浅蓝填充
E10_BAND_EDGE = E10_COLOR    # 深蓝边缘

# E15 条带图颜色
E15_BAND_COLOR = "#F5A0A0"   # 浅红填充
E15_BAND_EDGE = E15_COLOR    # 深红边缘

plt.rcParams['font.family'] = 'Times New Roman'
plt.rcParams['font.size'] = 12

# ================== 数据读取与处理 ==================
def load_and_process(csv_path):
    df = pd.read_csv(csv_path)
    df['solve_time'] = pd.to_numeric(df['solve_time'], errors='coerce')
    df['rel_error'] = pd.to_numeric(df['rel_error'], errors='coerce')
    df = df[df['price_sign'].isin(['positive', 'negative'])]
    df['abs_rel_error'] = df['rel_error'].abs()
    df['method_display'] = df['method'].map(method_mapping)
    return df

df10 = load_and_process(E10_PATH)
df15 = load_and_process(E15_PATH)

# ---- 总体平均求解时间 ----
overall_time10 = df10.groupby('method_display')['solve_time'].mean().reindex(method_order)
overall_time15 = df15.groupby('method_display')['solve_time'].mean().reindex(method_order)

# ---- 相对误差统计（合并所有场景，不分正负电价） ----
def compute_error_stats_all(df):
    sub = df[df['method_display'] != 'S-AWE']
    stats = sub.groupby('method_display')['abs_rel_error'].agg(
        mean='mean', min='min', max='max'
    ).reindex(['AA', 'VA-1', 'VA-2', 'EA'])
    return stats

stats10 = compute_error_stats_all(df10)
stats15 = compute_error_stats_all(df15)

# ---- 提取绘图数据 ----
x_pos = np.arange(1, 5)   # AA, VA-1, VA-2, EA 的位置

# E10
means10 = stats10['mean'].values
mins10  = stats10['min'].values
maxs10  = stats10['max'].values

# E15
means15 = stats15['mean'].values
mins15  = stats15['min'].values
maxs15  = stats15['max'].values

# ============================================================================
# ===== 📊 打印所有数据 =====
# ============================================================================
print("\n" + "=" * 90)
print("📊 数据统计总览")
print("=" * 90)

# ---- 1. 总体求解时间 ----
print("\n【1. 总体平均求解时间 (s)】")
print("-" * 60)
print(f"{'Method':<12} {'E10 (10 devices)':<20} {'E15 (15 devices)':<20}")
print("-" * 60)
for method in method_order:
    v10 = overall_time10[method] if method in overall_time10.index else None
    v15 = overall_time15[method] if method in overall_time15.index else None
    v10_str = f"{v10:.4f}" if v10 is not None else "N/A"
    v15_str = f"{v15:.4f}" if v15 is not None else "N/A"
    print(f"{method:<12} {v10_str:<20} {v15_str:<20}")
print("-" * 60)

# ---- 2. E10 相对误差统计 ----
print("\n【2. E10 (10 devices) 相对误差统计 (%)】")
print("-" * 70)
print(f"{'Method':<12} {'Mean':<15} {'Min':<15} {'Max':<15}")
print("-" * 70)
for method in ['AA', 'VA-1', 'VA-2', 'EA']:
    if method in stats10.index:
        mean_val = stats10.loc[method, 'mean']
        min_val  = stats10.loc[method, 'min']
        max_val  = stats10.loc[method, 'max']
        print(f"{method:<12} {mean_val:<15.6f} {min_val:<15.6f} {max_val:<15.6f}")
    else:
        print(f"{method:<12} {'N/A':<15} {'N/A':<15} {'N/A':<15}")
print("-" * 70)

# ---- 3. E15 相对误差统计 ----
print("\n【3. E15 (15 devices) 相对误差统计 (%)】")
print("-" * 70)
print(f"{'Method':<12} {'Mean':<15} {'Min':<15} {'Max':<15}")
print("-" * 70)
for method in ['AA', 'VA-1', 'VA-2', 'EA']:
    if method in stats15.index:
        mean_val = stats15.loc[method, 'mean']
        min_val  = stats15.loc[method, 'min']
        max_val  = stats15.loc[method, 'max']
        print(f"{method:<12} {mean_val:<15.6f} {min_val:<15.6f} {max_val:<15.6f}")
    else:
        print(f"{method:<12} {'N/A':<15} {'N/A':<15} {'N/A':<15}")
print("-" * 70)

# ---- 4. 正负电价场景详细数据 ----
print("\n【4. 正/负电价场景详细数据】")
print("-" * 90)

# 按方法分组统计
def print_price_stats(df, device_label):
    sub = df[df['method_display'] != 'S-AWE']
    result = sub.groupby(['method_display', 'price_sign'])['abs_rel_error'].agg(
        mean='mean', min='min', max='max'
    ).reset_index()
    print(f"\n   {device_label}:")
    print(f"   {'Method':<12} {'Scenario':<12} {'Mean':<15} {'Min':<15} {'Max':<15}")
    print(f"   {'-'*70}")
    for method in ['AA', 'VA-1', 'VA-2', 'EA']:
        for sign in ['positive', 'negative']:
            row = result[(result['method_display'] == method) & (result['price_sign'] == sign)]
            if not row.empty:
                mean_val = row['mean'].values[0]
                min_val = row['min'].values[0]
                max_val = row['max'].values[0]
                sign_label = 'Positive' if sign == 'positive' else 'Negative'
                print(f"   {method:<12} {sign_label:<12} {mean_val:<15.6f} {min_val:<15.6f} {max_val:<15.6f}")
    print(f"   {'-'*70}")

print_price_stats(df10, "E10 (10 devices)")
print_price_stats(df15, "E15 (15 devices)")

print("\n" + "=" * 90)
print("✅ 数据打印完成")
print("=" * 90 + "\n")

# ============================================================================
# ===== 坐标轴范围调节（可调节） =====
# ============================================================================
Y_LEFT_MIN = 0
Y_LEFT_MAX = 180

# 中间轴（E10 相对误差，单位：%）
Y_MID_MIN = -150.0
Y_MID_MAX = 250.0

# 右轴（E15 相对误差，单位：%）
Y_RIGHT_MIN = -280.0
Y_RIGHT_MAX = 300.0

# ---- 自动计算范围（如果设为 None 则自动） ----
if Y_MID_MAX is None:
    Y_MID_MAX = np.max(maxs10) + 0.5
if Y_MID_MIN is None:
    Y_MID_MIN = np.min(mins10) - 0.5
if Y_RIGHT_MAX is None:
    Y_RIGHT_MAX = np.max(maxs15) + 0.5
if Y_RIGHT_MIN is None:
    Y_RIGHT_MIN = np.min(mins15) - 0.5

# ============================================================================
# ===== 柱状图参数调节（可调节） =====
# ============================================================================
BAR_WIDTH = 0.28
BAR_OFFSET = 0.17
BAR_HATCH_E10 = '///'
BAR_HATCH_E15 = '\\\\'

# ============================================================================
# ===== 数据标签位置调节（可调节） =====
# ============================================================================
LABEL_OFFSET_RATIO = 0.01
BAR_LABEL_OFFSET = 0.2
PATH_EFFECTS_LINEWIDTH = 2

# ============================================================================
# ===== 条带图参数调节（可调节） =====
# ============================================================================
BAND_ALPHA = 0.4
BAND_LINEWIDTH = 1.5
MEAN_LINEWIDTH = 2

# ================== 绘图 ==================
fig, ax1 = plt.subplots(figsize=(9, 4))

ax2 = ax1.twinx()   # E10
ax3 = ax1.twinx()   # E15

ax2.spines['right'].set_position(('outward', 10))
ax3.spines['right'].set_position(('outward', 80))

# 轴脊颜色
ax1.spines['left'].set_color('black')
ax2.spines['right'].set_color(E10_COLOR)
ax3.spines['right'].set_color(E15_COLOR)

# 轴标签和刻度颜色
ax1.yaxis.label.set_color('black')
ax2.yaxis.label.set_color(E10_COLOR)
ax3.yaxis.label.set_color(E15_COLOR)
ax1.tick_params(axis='y', colors='black')
ax2.tick_params(axis='y', colors=E10_COLOR)
ax3.tick_params(axis='y', colors=E15_COLOR)

# ---- 左轴：柱状图 ----
x_all = np.arange(len(method_order))
offset = BAR_OFFSET

bars1 = ax1.bar(x_all - offset, overall_time10.values, BAR_WIDTH,
                color=COLORS_DARK, edgecolor='black', linewidth=0.8,
                hatch=BAR_HATCH_E10, label='E10', zorder=3)
bars2 = ax1.bar(x_all + offset, overall_time15.values, BAR_WIDTH,
                color=COLORS_LIGHT, edgecolor='black', linewidth=0.8,
                hatch=BAR_HATCH_E15, label='E15', zorder=3)

for i, (v10, v15) in enumerate(zip(overall_time10.values, overall_time15.values)):
    ax1.text(i - offset, v10 + BAR_LABEL_OFFSET, f'{v10:.3f} s',
             ha='center', va='bottom', fontsize=10)
    ax1.text(i + offset, v15 + BAR_LABEL_OFFSET, f'{v15:.3f} s',
             ha='center', va='bottom', fontsize=10)

ax1.set_ylim(bottom=Y_LEFT_MIN, top=Y_LEFT_MAX)
ax1.set_ylabel('Average computational time (s)', fontsize=12)
ax1.set_xticks(x_all)
ax1.set_xticklabels(method_order, rotation=0, ha='center', fontsize=12, fontweight='bold')
ax1.grid(axis='y', linestyle='--', alpha=0.3, zorder=0)
ax1.set_axisbelow(True)
ax1.set_xlim(-0.6, len(method_order)-0.4)
ax1.tick_params(axis='y', direction='in')

# ---- 中间轴（E10 相对误差条带图，仅一条带） ----
ax2.fill_between(x_pos, mins10, maxs10, color=E10_BAND_COLOR,
                 alpha=BAND_ALPHA, edgecolor=E10_BAND_EDGE, linewidth=BAND_LINEWIDTH)
ax2.plot(x_pos, means10, '-o', color=E10_COLOR, linewidth=MEAN_LINEWIDTH,
         markersize=6, zorder=5, label='E10')

# E10 均值标签
for xi, mu in zip(x_pos, means10):
    txt = ax2.text(xi, mu + LABEL_OFFSET_RATIO*(Y_MID_MAX-Y_MID_MIN), f'{mu:.3f}%',
                   ha='center', va='bottom', fontsize=10, color=E10_COLOR, fontweight='bold')
    txt.set_path_effects([path_effects.withStroke(linewidth=PATH_EFFECTS_LINEWIDTH, foreground='white')])

ax2.set_ylabel('Relative gap (%) for 10 device types', fontsize=12, color=E10_COLOR)
ax2.set_ylim(Y_MID_MIN, Y_MID_MAX)
ax2.tick_params(axis='y', direction='in')

# ---- 右轴（E15 相对误差条带图，仅一条带） ----
ax3.fill_between(x_pos, mins15, maxs15, color=E15_BAND_COLOR,
                 alpha=BAND_ALPHA, edgecolor=E15_BAND_EDGE, linewidth=BAND_LINEWIDTH)
ax3.plot(x_pos, means15, '-s', color=E15_COLOR, linewidth=MEAN_LINEWIDTH,
         markersize=6, zorder=5, label='E15')

for xi, mu in zip(x_pos, means15):
    txt = ax3.text(xi, mu + LABEL_OFFSET_RATIO*(Y_RIGHT_MAX-Y_RIGHT_MIN), f'{mu:.3f}%',
                   ha='center', va='bottom', fontsize=10, color=E15_COLOR, fontweight='bold')
    txt.set_path_effects([path_effects.withStroke(linewidth=PATH_EFFECTS_LINEWIDTH, foreground='white')])

ax3.set_ylabel('Relative gap (%) for 15 device types', fontsize=12, color=E15_COLOR)
ax3.set_ylim(Y_RIGHT_MIN, Y_RIGHT_MAX)
ax3.tick_params(axis='y', direction='in')

# ---- 图例 ----
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

legend_elements = [
    Patch(facecolor='none', edgecolor='black', hatch=BAR_HATCH_E10, label='10 device types (Time)'),
    Patch(facecolor='none', edgecolor='black', hatch=BAR_HATCH_E15, label='15 device types (Time)'),
    Line2D([0], [0], color=E10_COLOR, linewidth=2, marker='o', markersize=5, label='10 device types (Relative gap)'),
    Line2D([0], [0], color=E15_COLOR, linewidth=2, marker='s', markersize=5, label='15 device types (Relative gap)')
]

ax1.legend(handles=legend_elements, loc='upper right', frameon=True,
           edgecolor='black', fancybox=False, fontsize=11, ncol=2)

ax1.set_xlabel('')
plt.tight_layout()

# 保存
plt.savefig(os.path.join(OUTPUT_DIR, "E10_E15_Comparison.png"), dpi=300, bbox_inches='tight')
plt.savefig(os.path.join(OUTPUT_DIR, "E10_E15_Comparison.pdf"), bbox_inches='tight')
plt.savefig(os.path.join(OUTPUT_DIR, "E10_E15_Comparison.svg"), bbox_inches='tight')
print("对比图已保存至:", OUTPUT_DIR)
plt.show()