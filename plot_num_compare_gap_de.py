import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
from matplotlib.lines import Line2D

# ================== 配置 ==================
E10_PATH = "E10_log_res/details.csv"
E15_PATH = "E15_log_res/details.csv"
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
# ===== 科研配色（4种场景，鲜明且协调） =====
# ============================================================================
COLORS = {
    'E10_Pos': '#2878B5',   # 亮蓝
    'E10_Neg': '#9AC9DB',   # 浅蓝灰
    'E15_Pos': '#E15759',   # 亮红
    'E15_Neg': '#F7B6A8'    # 浅红
}

plt.rcParams['font.family'] = 'Times New Roman'
plt.rcParams['font.size'] = 11

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

def compute_price_error_stats(df):
    sub = df[df['method_display'] != 'S-AWE']
    stats = sub.groupby(['method_display', 'price_sign'])['abs_rel_error'].mean().reset_index()
    return stats

stats10 = compute_price_error_stats(df10)
stats15 = compute_price_error_stats(df15)

def pivot_stats(stats, device_label):
    pos_data = stats[stats['price_sign'] == 'positive'][['method_display', 'abs_rel_error']]
    neg_data = stats[stats['price_sign'] == 'negative'][['method_display', 'abs_rel_error']]
    pos_data = pos_data.rename(columns={'abs_rel_error': f'{device_label}_pos_mean'})
    neg_data = neg_data.rename(columns={'abs_rel_error': f'{device_label}_neg_mean'})
    merged = pd.merge(pos_data, neg_data, on='method_display', how='outer')
    return merged

pivot10 = pivot_stats(stats10, 'E10')
pivot15 = pivot_stats(stats15, 'E15')

final_df = pd.merge(pivot10, pivot15, on='method_display', how='outer')
final_df = final_df.set_index('method_display').reindex(['AA', 'VA-1', 'VA-2', 'EA']).reset_index()
final_df = final_df.fillna(0)

# ============================================================================
# ===== 可调参数 =====
# ============================================================================
# 1. Y轴范围控制（左轴）
Y_AXIS_MIN = -0   # Y轴最小值（建议设为负数，给标签留空间）
Y_AXIS_MAX = 7    # Y轴最大值（根据数据调整）

# 2. 数据标签偏移比例
LABEL_OFFSET_RATIO = 0.01   # 相对于数据范围的百分比

# ============================================================================
# ===== 绘图 =====
# ============================================================================
x = np.arange(len(final_df['method_display']))
width = 0.18
gap = 0.03
offsets = [-1.5*width - 1.5*gap, -0.5*width - 0.5*gap, 0.5*width + 0.5*gap, 1.5*width + 1.5*gap]
methods = final_df['method_display'].values

e10_pos = final_df['E10_pos_mean'].values
e10_neg = final_df['E10_neg_mean'].values
e15_pos = final_df['E15_pos_mean'].values
e15_neg = final_df['E15_neg_mean'].values

# 数据范围（用于标签偏移）
all_vals = np.concatenate([e10_pos, e10_neg, e15_pos, e15_neg])
data_range = max(all_vals) - min(all_vals) + 1e-6
y_offset = LABEL_OFFSET_RATIO * data_range

fig, ax = plt.subplots(figsize=(9, 4))

# ===== 绘制4组柱子 =====
bars1 = ax.bar(x + offsets[0], e10_pos, width, 
               color=COLORS['E10_Pos'], edgecolor='black', linewidth=0.6,
               label='10 dev. Positive', zorder=2)
bars2 = ax.bar(x + offsets[1], e10_neg, width,
               color=COLORS['E10_Neg'], edgecolor='black', linewidth=0.6,
               label='10 dev. Negative', zorder=2)
bars3 = ax.bar(x + offsets[2], e15_pos, width,
               color=COLORS['E15_Pos'], edgecolor='black', linewidth=0.6,
               label='15 dev. Positive', zorder=2)
bars4 = ax.bar(x + offsets[3], e15_neg, width,
               color=COLORS['E15_Neg'], edgecolor='black', linewidth=0.6,
               label='15 dev. Negative', zorder=2)

# ===== 柱顶标注均值 =====
# positive 和 negative 分别用不同的偏移量
for i in range(len(methods)):
    # ---- 10设备 ----
    # 正电价（保持在柱子顶部上方，偏移 y_offset）
    ax.text(x[i] + offsets[0], e10_pos[i] + y_offset,
            f'{e10_pos[i]:.3f}%', ha='center', va='bottom', 
            fontsize=11, color='black', rotation=0)
    # 负电价（往上标注，偏移量更大）
    if i == 3:  # EA方法：数值极小，需要更大偏移量
        ax.text(x[i] + offsets[1], e10_neg[i] + y_offset * 6,
                f'{e10_neg[i]:.3f}%', ha='center', va='bottom',
                fontsize=11, color='black', rotation=0)
    else:
        ax.text(x[i] + offsets[1], e10_neg[i] + y_offset,
                f'{e10_neg[i]:.3f}%', ha='center', va='bottom',
                fontsize=11, color='black', rotation=0)

    # ---- 15设备 ----
    if i == 3:  # EA方法：数值极小，需要更大偏移量
        # 正电价（位置稍高一点）
        ax.text(x[i] + offsets[2], e15_pos[i] + y_offset,
                f'{e15_pos[i]:.3f}%', ha='center', va='bottom',
                fontsize=11, color='black', rotation=0)
        # 负电价（再往上标注，与正电价明显错开）
        ax.text(x[i] + offsets[3], e15_neg[i] + y_offset * 6,
                f'{e15_neg[i]:.3f}%', ha='center', va='bottom',
                fontsize=11, color='black', rotation=0)
    else:  # 其他方法
        # 正电价（保持在柱子顶部上方）
        ax.text(x[i] + offsets[2], e15_pos[i] + y_offset,
                f'{e15_pos[i]:.3f}%', ha='center', va='bottom',
                fontsize=11, color='black', rotation=0)
        # 负电价（往上标注，偏移量比 positive 大）
        ax.text(x[i] + offsets[3], e15_neg[i] + y_offset,
                f'{e15_neg[i]:.3f}%', ha='center', va='bottom',
                fontsize=11, color='black', rotation=0)

# ---- 坐标轴设置 ----
ax.set_ylabel('Relative gap (%)', fontsize=12)
ax.set_xticks(x)
ax.set_xticklabels(methods, fontsize=12, fontweight='bold')
ax.tick_params(axis='x', pad=8)
ax.grid(axis='y', linestyle='--', alpha=0.3, zorder=0)
ax.set_axisbelow(True)
ax.tick_params(axis='y', direction='in')
ax.tick_params(axis='x', direction='in')

# ===== 控制Y轴范围（可调） =====
ax.set_ylim(Y_AXIS_MIN, Y_AXIS_MAX)

# ---- 图例 ----
legend_elements = [
    Line2D([0], [0], color='#2878B5', linewidth=0, marker='s', markersize=8,
           markerfacecolor='#2878B5', markeredgecolor='black',
           label='10 device types, positive price scenarios'),
    Line2D([0], [0], color='#9AC9DB', linewidth=0, marker='s', markersize=8,
           markerfacecolor='#9AC9DB', markeredgecolor='black',
           label='10 device types, negative price scenarios'),
    Line2D([0], [0], color='#E15759', linewidth=0, marker='s', markersize=8,
           markerfacecolor='#E15759', markeredgecolor='black',
           label='15 device types, positive price scenarios'),
    Line2D([0], [0], color='#F7B6A8', linewidth=0, marker='s', markersize=8,
           markerfacecolor='#F7B6A8', markeredgecolor='black',
           label='15 device types, negative price scenarios')
]

ax.legend(handles=legend_elements, loc='upper right', frameon=True,
          edgecolor='black', fancybox=False, fontsize=12,
          ncol=1)

plt.tight_layout()

# 保存
plt.savefig(os.path.join(OUTPUT_DIR, "Figure2_Price_Error_Bar.png"), dpi=300, bbox_inches='tight')
plt.savefig(os.path.join(OUTPUT_DIR, "Figure2_Price_Error_Bar.pdf"), bbox_inches='tight')
plt.savefig(os.path.join(OUTPUT_DIR, "Figure2_Price_Error_Bar.svg"), bbox_inches='tight')
print("图2已保存至:", OUTPUT_DIR)
plt.show()