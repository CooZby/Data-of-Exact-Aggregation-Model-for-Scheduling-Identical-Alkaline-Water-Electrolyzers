import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import matplotlib.patheffects as path_effects

# ================== 可调整参数（全部集中在这里） ==================
OUTPUT_DIR = "E5_log_res"
CSV_PATH = os.path.join(OUTPUT_DIR, "details.csv")
FIG_DIR = os.path.join(OUTPUT_DIR, "figures")
os.makedirs(FIG_DIR, exist_ok=True)

FIG_SIZE = (10, 3.8)                       # 图片尺寸
FONT_SIZE_LABEL = 12                       # 轴标签字体大小
FONT_SIZE_TICK = 12                        # 刻度字体大小
FONT_SIZE_ANNOTATION = 11                  # 数据标签字体大小

# 颜色（柱状图使用五种颜色，正/负误差用红蓝）
COLORS_BAR = ["#999999", "#4E79A7", "#59A14F", "#F28E2B", "#E15759"]
COLOR_POS = "#D62728"   # 正电价颜色（鲜艳红）
COLOR_NEG = "#1F77B4"   # 负电价颜色（饱和蓝）

# 误差带参数
ALPHA_BAND = 0.8                # 条带透明度
BAND_LINEWIDTH = 0.8            # 条带边缘线宽
BOUNDARY_LINEWIDTH = 1.0        # 上下边界线宽
MEAN_LINEWIDTH = 2              # 均值曲线线宽
MEAN_MARKERSIZE = 5
SHOW_MEAN = True

# ---------- 坐标轴范围控制 ----------
Y_LEFT_MIN = 0.5
Y_LEFT_MAX = 68
Y_MID_MIN = -1.0
Y_MID_MAX = 1.5                 # 正电价轴上限（会自动扩展）
Y_RIGHT_MIN = -12.0
Y_RIGHT_MAX = 10                # 负电价轴上限（会自动扩展）

# ---------- 刻度样式控制 ----------
TICK_LENGTH = 6                 # 刻度线长度（points）
TICK_WIDTH = 1.5                # 刻度线宽度
AX3_SPINE_OFFSET = 60           # 最右轴(spine)偏移量

# 方法名称映射
method_mapping = {
    'Basic': 'S-AWE',
    'AA': 'AA',
    'AA_R': 'VA-1',
    'AA_R_Cold': 'VA-2',
    'TestAgg': 'EA'
}
method_order = ['S-AWE', 'AA', 'VA-1', 'VA-2', 'EA']

# ================== 数据读取与计算 ==================
df = pd.read_csv(CSV_PATH)
df['solve_time'] = pd.to_numeric(df['solve_time'], errors='coerce')
df['rel_error'] = pd.to_numeric(df['rel_error'], errors='coerce')
df = df[df['price_sign'].isin(['positive', 'negative'])]
df['abs_rel_error'] = df['rel_error'].abs()
df['method_display'] = df['method'].map(method_mapping)

# ---- 总体求解时间统计（包含 mean, min, max） ----
overall_time = df.groupby('method_display')['solve_time'].agg(
    mean='mean', min='min', max='max'
).reindex(method_order)

# ---- 按电价分组的求解时间统计 ----
def compute_time_stats(sub_df):
    stats = sub_df.groupby('method_display')['solve_time'].agg(
        mean='mean', min='min', max='max'
    ).reindex(method_order)
    return stats

pos_time_stats = compute_time_stats(df[df['price_sign'] == 'positive'])
neg_time_stats = compute_time_stats(df[df['price_sign'] == 'negative'])

# ---- 按电价分组的相对误差统计（排除 S-AWE） ----
def compute_error_stats(sub_df):
    sub = sub_df[sub_df['method_display'] != 'S-AWE']
    stats = sub.groupby('method_display')['abs_rel_error'].agg(
        mean='mean', min='min', max='max'
    ).reindex(['AA', 'VA-1', 'VA-2', 'EA'])
    return stats

pos_error_stats = compute_error_stats(df[df['price_sign'] == 'positive'])
neg_error_stats = compute_error_stats(df[df['price_sign'] == 'negative'])

# ---- 提取绘图所需变量（用于条带图） ----
x_pos = np.arange(1, 5)  # AA, VA-1, VA-2, EA 的位置索引
pos_means = pos_error_stats['mean'].values
pos_mins  = pos_error_stats['min'].values
pos_maxs  = pos_error_stats['max'].values
neg_means = neg_error_stats['mean'].values
neg_mins  = neg_error_stats['min'].values
neg_maxs  = neg_error_stats['max'].values

# ---- 打印统计信息（按方法展示） ----
print("\n" + "="*80)
print("统计结果汇总（按方法）")
print("="*80)

for method in method_order:
    print(f"\n【{method}】")
    
    # 总体求解时间
    if method in overall_time.index:
        t_mean = overall_time.loc[method, 'mean']
        t_min  = overall_time.loc[method, 'min']
        t_max  = overall_time.loc[method, 'max']
        print(f"  总体求解时间 (s)  : 均值 {t_mean:.4f} | 最小 {t_min:.4f} | 最大 {t_max:.4f}")
    else:
        print("  总体求解时间 (s)  : 无数据")
    
    # 正电价求解时间
    if method in pos_time_stats.index:
        pt_mean = pos_time_stats.loc[method, 'mean']
        pt_min  = pos_time_stats.loc[method, 'min']
        pt_max  = pos_time_stats.loc[method, 'max']
        print(f"  正电价求解时间 (s) : 均值 {pt_mean:.4f} | 最小 {pt_min:.4f} | 最大 {pt_max:.4f}")
    else:
        print("  正电价求解时间 (s) : 无数据")
    
    # 负电价求解时间
    if method in neg_time_stats.index:
        nt_mean = neg_time_stats.loc[method, 'mean']
        nt_min  = neg_time_stats.loc[method, 'min']
        nt_max  = neg_time_stats.loc[method, 'max']
        print(f"  负电价求解时间 (s) : 均值 {nt_mean:.4f} | 最小 {nt_min:.4f} | 最大 {nt_max:.4f}")
    else:
        print("  负电价求解时间 (s) : 无数据")
    
    # 相对误差（仅对非 S-AWE 方法）
    if method != 'S-AWE':
        if method in pos_error_stats.index:
            pe_mean = pos_error_stats.loc[method, 'mean']
            pe_min  = pos_error_stats.loc[method, 'min']
            pe_max  = pos_error_stats.loc[method, 'max']
            print(f"  正电价相对误差 (%) : 均值 {pe_mean:.4f} | 最小 {pe_min:.4f} | 最大 {pe_max:.4f}")
        else:
            print("  正电价相对误差 (%) : 无数据")
        
        if method in neg_error_stats.index:
            ne_mean = neg_error_stats.loc[method, 'mean']
            ne_min  = neg_error_stats.loc[method, 'min']
            ne_max  = neg_error_stats.loc[method, 'max']
            print(f"  负电价相对误差 (%) : 均值 {ne_mean:.4f} | 最小 {ne_min:.4f} | 最大 {ne_max:.4f}")
        else:
            print("  负电价相对误差 (%) : 无数据")
    else:
        print("  相对误差 : 基准方法，无误差数据")

print("\n" + "="*80)
print("统计打印完成")
print("="*80)

# ================== 自动扩展轴范围 ==================
if Y_MID_MAX is not None:
    Y_MID_MAX = max(Y_MID_MAX, np.max(pos_maxs) + 0.2*(np.max(pos_maxs)-np.min(pos_mins)+1e-6))
if Y_RIGHT_MAX is not None:
    Y_RIGHT_MAX = max(Y_RIGHT_MAX, np.max(neg_maxs) + 0.2*(np.max(neg_maxs)-np.min(neg_mins)+1e-6))

# ================== 绘图 ==================
plt.rcParams['font.family'] = 'Times New Roman'
plt.rcParams['font.size'] = 11

fig, ax1 = plt.subplots(figsize=FIG_SIZE)
ax2 = ax1.twinx()
ax3 = ax1.twinx()

# 设置两个右轴的位置偏移（避免重叠）
ax2.spines['right'].set_position(('outward', 10))
ax3.spines['right'].set_position(('outward', AX3_SPINE_OFFSET))

# 统一轴颜色
ax1.yaxis.label.set_color('black')
ax1.tick_params(axis='y', colors='black')
ax1.spines['left'].set_color('black')

ax2.yaxis.label.set_color(COLOR_POS)
ax2.tick_params(axis='y', colors=COLOR_POS)
ax2.spines['right'].set_color(COLOR_POS)

ax3.yaxis.label.set_color(COLOR_NEG)
ax3.tick_params(axis='y', colors=COLOR_NEG)
ax3.spines['right'].set_color(COLOR_NEG)

# 所有轴刻度样式：长度、宽度、方向（朝内）
for ax in [ax1, ax2, ax3]:
    ax.tick_params(direction='in', which='both', length=TICK_LENGTH, width=TICK_WIDTH)
ax1.tick_params(axis='x', direction='in', length=TICK_LENGTH, width=TICK_WIDTH)

fig.subplots_adjust(right=0.85)

ax1.set_ylabel('Average computational time (s)', fontsize=FONT_SIZE_LABEL)
ax2.set_ylabel('Positive-price scenario relative gap (%)', fontsize=FONT_SIZE_LABEL)
ax3.set_ylabel('Negative-price scenario relative gap (%)', fontsize=FONT_SIZE_LABEL)
ax2.yaxis.set_label_coords(1.08, 0.5)
ax3.yaxis.set_label_coords(1.18, 0.5)

# ---- 左轴：柱状图 ----
x_all = np.arange(len(method_order))
width = 0.6

# ★★★ 关键修正：只取 mean 列，避免形状不匹配 ★★★
overall_vals = overall_time['mean'].values

bars = ax1.bar(x_all, overall_vals, width, color=COLORS_BAR,
               edgecolor='black', linewidth=0.8, zorder=3)

# ---- 在柱状图上叠加正/负电价平均求解时间（红色圆点、蓝色方块） ----
pos_time_means = pos_time_stats['mean'].values
neg_time_means = neg_time_stats['mean'].values

# for i, method in enumerate(method_order):
#     # 正电价均值点（红色圆点）
#     if not np.isnan(pos_time_means[i]):
#         ax1.scatter(i, pos_time_means[i], color='red', marker='o', s=40, zorder=7, label='_nolegend_')
#     # 负电价均值点（蓝色方块）
#     if not np.isnan(neg_time_means[i]):
#         ax1.scatter(i, neg_time_means[i], color='blue', marker='s', s=40, zorder=7, label='_nolegend_')

# 设置左轴范围
if Y_LEFT_MIN is not None:
    ax1.set_ylim(bottom=Y_LEFT_MIN)
if Y_LEFT_MAX is not None:
    ax1.set_ylim(top=Y_LEFT_MAX)

ylim = ax1.get_ylim()
offset = 0.02 * (ylim[1] - ylim[0])
for i, v in enumerate(overall_vals):
    ax1.text(i, v + offset, f'{v:.3f} s', ha='center', va='bottom',
             fontsize=FONT_SIZE_ANNOTATION, fontweight='bold', color='black')

ax1.set_xticks(x_all)
ax1.set_xticklabels(method_order, rotation=0, ha='center', fontsize=12, fontweight='bold')
ax1.grid(axis='y', linestyle='--', alpha=0.3, zorder=0)
ax1.set_axisbelow(True)
ax1.set_xlim(-0.6, len(method_order)-0.4)

# ---- 中间轴（正电价误差）条带图 ----
ax2.fill_between(x_pos, pos_mins, pos_maxs, color=COLOR_POS,
                 alpha=0.50, edgecolor=COLOR_POS, linewidth=BAND_LINEWIDTH, zorder=4)
ax2.plot(x_pos, pos_maxs, '-', color=COLOR_POS, linewidth=BOUNDARY_LINEWIDTH, alpha=0.9, zorder=5)
ax2.plot(x_pos, pos_mins, '-', color=COLOR_POS, linewidth=BOUNDARY_LINEWIDTH, alpha=0.9, zorder=5)
ax2.plot(x_pos, pos_means, '-o', color=COLOR_POS, linewidth=MEAN_LINEWIDTH,
         markersize=MEAN_MARKERSIZE, label='Positive mean', zorder=6)

if SHOW_MEAN:
    for xi, mu in zip(x_pos, pos_means):
        label_offset = 0.03 * (Y_MID_MAX - Y_MID_MIN)
        y_pos = mu + label_offset
        txt = ax2.text(xi, y_pos, f'{mu:.3f}%', ha='center', va='bottom',
                       fontsize=FONT_SIZE_ANNOTATION, color=COLOR_POS, fontweight='bold',
                       zorder=10)
        txt.set_path_effects([path_effects.withStroke(linewidth=2, foreground='white')])

ax2.set_ylim(Y_MID_MIN, Y_MID_MAX)

# ---- 最右轴（负电价误差）条带图 ----
ax3.fill_between(x_pos, neg_mins, neg_maxs, color=COLOR_NEG,
                 alpha=0.45, edgecolor=COLOR_NEG, linewidth=BAND_LINEWIDTH, zorder=4)
ax3.plot(x_pos, neg_maxs, '-', color=COLOR_NEG, linewidth=BOUNDARY_LINEWIDTH, alpha=0.9, zorder=5)
ax3.plot(x_pos, neg_mins, '-', color=COLOR_NEG, linewidth=BOUNDARY_LINEWIDTH, alpha=0.9, zorder=5)
ax3.plot(x_pos, neg_means, '-s', color=COLOR_NEG, linewidth=MEAN_LINEWIDTH,
         markersize=MEAN_MARKERSIZE, label='Negative mean', zorder=6)

if SHOW_MEAN:
    for xi, mu in zip(x_pos, neg_means):
        label_offset = 0.03 * (Y_RIGHT_MAX - Y_RIGHT_MIN)
        y_pos = mu - label_offset
        txt = ax3.text(xi, y_pos, f'{mu:.3f}%', ha='center', va='top',
                       fontsize=FONT_SIZE_ANNOTATION, color=COLOR_NEG, fontweight='bold',
                       zorder=10)
        txt.set_path_effects([path_effects.withStroke(linewidth=2, foreground='white')])

ax3.set_ylim(Y_RIGHT_MIN, Y_RIGHT_MAX)

# ---- 图例 ----
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

legend_elements = [
    Line2D([0], [0], color=COLOR_POS, linewidth=2, marker='o', markersize=5, label='Positive price scenario relative gap'),
    Line2D([0], [0], color=COLOR_NEG, linewidth=2, marker='s', markersize=5, label='Negative price scenario relative gap')
]

ax1.legend(handles=legend_elements, loc='upper right', frameon=True,
           edgecolor='black', fancybox=False, fontsize=FONT_SIZE_TICK)

ax1.set_xlabel('')
plt.tight_layout(rect=[0, 0, 0.85, 1])

# 保存
svg_path = os.path.join(FIG_DIR, "SolveTime_Error_TripleY.svg")
pdf_path = os.path.join(FIG_DIR, "SolveTime_Error_TripleY.pdf")
png_path = os.path.join(FIG_DIR, "SolveTime_Error_TripleY.png")
plt.savefig(svg_path, bbox_inches='tight')
plt.savefig(pdf_path, bbox_inches='tight')
plt.savefig(png_path, bbox_inches='tight', dpi=300)
print(f"三Y轴图已保存至: {FIG_DIR}")
plt.show()