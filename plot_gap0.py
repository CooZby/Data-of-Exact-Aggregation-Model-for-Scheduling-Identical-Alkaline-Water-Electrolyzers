import matplotlib.pyplot as plt
import numpy as np
import os
from matplotlib.lines import Line2D
import matplotlib.patheffects as path_effects

# ================== 配置 ==================
OUTPUT_DIR = "Gap0_E5_24_10s_res"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ================== 数据 ==================
data_raw = [
    ('AA', 'negative', 2090.5141, 1520.5180, 3040.5652),
    ('AA', 'positive', 613.4779, 475.6685, 765.8224),
    ('VA-1', 'negative', 645.0729, 0.0000, 1935.2185),
    ('VA-1', 'positive', 0.0000, 0.0000, 0.0001),
    ('VA-2', 'negative', 4.2601, 0.0002, 7.0650),
    ('VA-2', 'positive', 0.0000, 0.0000, 0.0001),
    ('EA', 'negative', 0.0001, 0.0000, 0.0002),
    ('EA', 'positive', 0.0000, 0.0000, 0.0001)
]

data_dict = {}
for method, sign, mean_val, min_val, max_val in data_raw:
    if method not in data_dict:
        data_dict[method] = {}
    data_dict[method][sign] = {'mean': mean_val, 'min': min_val, 'max': max_val}

methods_all = ['AA', 'VA-1', 'VA-2', 'EA']
colors = {'positive': '#2878B5', 'negative': '#E15759'}

plt.rcParams['font.family'] = 'Times New Roman'

# ============================================================
# 图1：所有方法（三位小数）
# ============================================================
fig1, ax1 = plt.subplots(figsize=(9, 5))
x_pos = np.arange(len(methods_all))
width = 0.35
offset = width / 2 + 0.05

for i, method in enumerate(methods_all):
    # 正电价
    if 'positive' in data_dict[method]:
        pdata = data_dict[method]['positive']
        mean_val, min_val, max_val = pdata['mean'], pdata['min'], pdata['max']
        ax1.fill_between([i - offset, i - offset + 0.15], min_val, max_val,
                         color=colors['positive'], alpha=0.3, edgecolor=colors['positive'], linewidth=1.5)
        ax1.hlines(mean_val, i - offset, i - offset + 0.15, color=colors['positive'], linewidth=2.5)
        ax1.scatter(i - offset + 0.075, mean_val, color=colors['positive'], s=60, zorder=5,
                    marker='o', edgecolor='black')
        # 数据标签偏移：VA-1,VA-2,EA使用固定偏移50，其他使用10%相对偏移
        if method in ['VA-1', 'VA-2', 'EA']:
            y_offset = 50
        else:
            y_offset = 0.1 * (max_val - min_val + 1e-6)
        # 标签样式：无边框，仅浅灰色描边（linewidth=2, foreground='#cccccc'）
        ax1.text(i - offset + 0.075, mean_val + y_offset, f'{mean_val:.3f}',
                 ha='center', va='bottom', fontsize=10, color=colors['positive'], fontweight='bold',)
    # 负电价
    if 'negative' in data_dict[method]:
        ndata = data_dict[method]['negative']
        mean_val, min_val, max_val = ndata['mean'], ndata['min'], ndata['max']
        ax1.fill_between([i + offset - 0.15, i + offset], min_val, max_val,
                         color=colors['negative'], alpha=0.3, edgecolor=colors['negative'], linewidth=1.5)
        ax1.hlines(mean_val, i + offset - 0.15, i + offset, color=colors['negative'], linewidth=2.5)
        ax1.scatter(i + offset - 0.075, mean_val, color=colors['negative'], s=60, zorder=5,
                    marker='s', edgecolor='black')
        if method in ['VA-2', 'EA']:
            y_offset = 50
        else:
            y_offset = 0.05 * (max_val - min_val + 1e-6)
        ax1.text(i + offset - 0.075, mean_val + y_offset, f'{mean_val:.3f}',
                 ha='center', va='bottom', fontsize=10, color=colors['negative'], fontweight='bold')

ax1.set_xticks(x_pos)
ax1.set_xticklabels(methods_all, fontsize=12, fontweight='bold')
ax1.set_ylabel('Absolute Difference ($)', fontsize=12)
ax1.grid(axis='y', linestyle='--', alpha=0.3)
ax1.tick_params(axis='x', direction='in')
ax1.tick_params(axis='y', direction='in')
ax1.set_ylim(-50, 4000)

legend_elements = [
    Line2D([0], [0], color=colors['positive'], linewidth=2, marker='o', markersize=8,
           markerfacecolor=colors['positive'], markeredgecolor='black', label='Positive price scenario'),
    Line2D([0], [0], color=colors['negative'], linewidth=2, marker='s', markersize=8,
           markerfacecolor=colors['negative'], markeredgecolor='black', label='Negative price scenario')
]
ax1.legend(handles=legend_elements, loc='upper left', frameon=True,
           edgecolor='black', fancybox=False, fontsize=10)

plt.tight_layout()
# ===== 图1保存 =====
fig1.savefig(os.path.join(OUTPUT_DIR, 'Fig1_All_Methods.png'), dpi=600, bbox_inches='tight')
fig1.savefig(os.path.join(OUTPUT_DIR, 'Fig1_All_Methods.svg'), bbox_inches='tight')
fig1.savefig(os.path.join(OUTPUT_DIR, 'Fig1_All_Methods.pdf'), bbox_inches='tight')
print(f"图1已保存: SVG/PDF/PNG")
# ============================================================
# 图2：仅 VA-2 和 EA（symlog坐标，标注最大值）
# ============================================================
# ============================================================
# 图2：仅 VA-2 和 EA（symlog坐标，标注最大值）
# ============================================================

# ===== 字体大小集中控制（一键调整） =====
FONT_SIZES = {
    'axis_label': 18,        # 轴标签字体大小（如 ylabel）
    'tick_label': 18,        # 刻度值字体大小（y轴和x轴刻度数字）
    'xtick_label': 18,       # x轴方法名称字体大小
    'max_label': 18,         # Max 标注字体大小
    'legend': 12,            # 图例字体大小
}

fig2, ax2 = plt.subplots(figsize=(8, 5))  # 更扁
methods_small = ['VA-2', 'EA']
x_pos_small = np.arange(len(methods_small))
width_small = 0.35
offset_small = width_small / 2 + 0.05

for i, method in enumerate(methods_small):
    # 正电价
    if 'positive' in data_dict[method]:
        pdata = data_dict[method]['positive']
        mean_val, min_val, max_val = pdata['mean'], pdata['min'], pdata['max']
        if min_val == 0:
            min_val_draw = 1e-8
        else:
            min_val_draw = min_val
        ax2.fill_between([i - offset_small, i - offset_small + 0.15], min_val_draw, max_val,
                         color=colors['positive'], alpha=0.4, edgecolor=colors['positive'], linewidth=1.5)
        ax2.hlines(mean_val, i - offset_small, i - offset_small + 0.15, color=colors['positive'], linewidth=2.5)
        ax2.scatter(i - offset_small + 0.075, mean_val, color=colors['positive'], s=60, zorder=5,
                    marker='o', edgecolor='black')
        # 正电价最大值标注：在上方（加粗辅助线 + 大号字体）
        y_pos = max_val * 1.15  # 向上平移15%，避免与条带重合
        ax2.hlines(max_val, i - offset_small, i - offset_small + 0.15, 
                   color=colors['positive'], linestyle='--', linewidth=2)
        ax2.text(i - offset_small + 0.075, y_pos, f'Max: {max_val:.4f}', 
                 ha='center', va='bottom', fontsize=FONT_SIZES['max_label'], 
                 fontweight='bold', color=colors['positive'])
    
    # 负电价
    if 'negative' in data_dict[method]:
        ndata = data_dict[method]['negative']
        mean_val, min_val, max_val = ndata['mean'], ndata['min'], ndata['max']
        if min_val == 0:
            min_val_draw = 1e-8
        else:
            min_val_draw = min_val
        ax2.fill_between([i + offset_small - 0.15, i + offset_small], min_val_draw, max_val,
                         color=colors['negative'], alpha=0.4, edgecolor=colors['negative'], linewidth=1.5)
        ax2.hlines(mean_val, i + offset_small - 0.15, i + offset_small, color=colors['negative'], linewidth=2.5)
        ax2.scatter(i + offset_small - 0.075, mean_val, color=colors['negative'], s=60, zorder=5,
                    marker='s', edgecolor='black')
        
        # 负电价最大值标注：VA-2标注在右边，EA标注在上方
        if method == 'VA-2':
            # VA-2 负电价标注在右边（条带右端外侧）
            x_pos_label = i + offset_small + 0.05
            y_pos = max_val
            ax2.hlines(max_val, i + offset_small - 0.15, i + offset_small, 
                       color=colors['negative'], linestyle='--', linewidth=2)
            ax2.text(x_pos_label, y_pos, f'Max: {max_val:.4f}', 
                     ha='left', va='center', fontsize=FONT_SIZES['max_label'], 
                     fontweight='bold', color=colors['negative'])
        else:
            # EA 负电价标注在上方（向上平移）
            y_pos = max_val * 2.0  # EA数值很小，需要更大的相对偏移
            ax2.hlines(max_val, i + offset_small - 0.15, i + offset_small, 
                       color=colors['negative'], linestyle='--', linewidth=2)
            ax2.text(i + offset_small - 0.075, y_pos, f'Max: {max_val:.4f}', 
                     ha='center', va='bottom', fontsize=FONT_SIZES['max_label'], 
                     fontweight='bold', color=colors['negative'])

ax2.set_xticks(x_pos_small)
ax2.set_xticklabels(methods_small, fontsize=FONT_SIZES['xtick_label'], fontweight='bold')

# Y轴刻度标签字体大小（通过 tick_params 控制）
ax2.tick_params(axis='y', labelsize=FONT_SIZES['tick_label'])
ax2.tick_params(axis='x', labelsize=FONT_SIZES['tick_label'])

# 轴标签（如果需要 ylabel，取消注释）
# ax2.set_ylabel('Absolute Difference ($)', fontsize=FONT_SIZES['axis_label'])

ax2.grid(axis='y', linestyle='--', alpha=0.3)
ax2.tick_params(axis='x', direction='in')
ax2.tick_params(axis='y', direction='in')
ax2.set_yscale('symlog', linthresh=1e-6, linscale=1)
ax2.set_ylim(1e-8, 50)   # 上限设为50

# # 图例（如果需要，可设置字体大小）
# legend_elements2 = [
#     Line2D([0], [0], color=colors['positive'], linewidth=2, marker='o', markersize=8,
#            markerfacecolor=colors['positive'], markeredgecolor='black', label='Positive price scenario'),
#     Line2D([0], [0], color=colors['negative'], linewidth=2, marker='s', markersize=8,
#            markerfacecolor=colors['negative'], markeredgecolor='black', label='Negative price scenario')
# ]
# ax2.legend(handles=legend_elements2, loc='upper right', frameon=True,
#            edgecolor='black', fancybox=False, fontsize=FONT_SIZES['legend'])
plt.tight_layout()
fig2.savefig(os.path.join(OUTPUT_DIR, 'Fig2_VA2_EA_Zoom.png'), dpi=300, bbox_inches='tight')
fig2.savefig(os.path.join(OUTPUT_DIR, 'Fig2_VA2_EA_Zoom.svg'), bbox_inches='tight')
print(f"图2已保存: {OUTPUT_DIR}/Fig2_VA2_EA_Zoom.png 和 .svg")



# ===== 图2保存 =====
fig2.savefig(os.path.join(OUTPUT_DIR, 'Fig2_VA2_EA_Zoom.png'), dpi=600, bbox_inches='tight')
fig2.savefig(os.path.join(OUTPUT_DIR, 'Fig2_VA2_EA_Zoom.svg'), bbox_inches='tight')
fig2.savefig(os.path.join(OUTPUT_DIR, 'Fig2_VA2_EA_Zoom.pdf'), bbox_inches='tight')
print(f"图2已保存: SVG/PDF/PNG")