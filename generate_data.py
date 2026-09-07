import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from scipy.ndimage import gaussian_filter1d

# 设置随机种子
np.random.seed(42)

# ==================== 参数配置 ====================
DAYS = 1000
HOURS_PER_DAY = 24
TOTAL_HOURS = DAYS * HOURS_PER_DAY
LATITUDE = 40.0

# ==================== 时间轴 ====================
start_date = datetime(2020, 1, 1)
timestamps = [start_date + timedelta(hours=i) for i in range(TOTAL_HOURS)]

def day_of_year_float(dt):
    return (dt - start_date).total_seconds() / (24 * 3600)

# ==================== 1. 风电曲线 ====================
hour_of_year = np.array([(dt - start_date).total_seconds() / 3600.0 for dt in timestamps])
day_of_year = hour_of_year / 24.0
# 季节因子：冬高夏低
season_factor = 0.5 + 0.3 * np.cos(2 * np.pi * (day_of_year - 15) / 365)
# 日变化：夜间稍高
hour_of_day = np.array([dt.hour for dt in timestamps])
diurnal_factor = 0.05 * np.cos(2 * np.pi * (hour_of_day - 4) / 24)
base_wind = np.clip(season_factor + diurnal_factor, 0.1, 0.85)

# AR(1)天气扰动
rho = 0.95
white_noise = np.random.normal(0, 0.08, TOTAL_HOURS)
ar_noise = np.zeros(TOTAL_HOURS)
ar_noise[0] = white_noise[0]
for t in range(1, TOTAL_HOURS):
    ar_noise[t] = rho * ar_noise[t-1] + white_noise[t]
wind_cf = base_wind + 0.2 * ar_noise
wind_cf = np.clip(wind_cf, 0.05, 0.95)

# 极端事件（每年5~8次持续2~5天）
event_weeks = np.random.choice(range(DAYS//7), size=int(DAYS//7*0.15), replace=False)
for week in event_weeks:
    start_idx = week * 7 * 24
    duration = np.random.randint(2, 5) * 24
    end_idx = min(start_idx + duration, TOTAL_HOURS)
    if np.random.rand() > 0.6:
        wind_cf[start_idx:end_idx] *= np.random.uniform(0.4, 0.7)
    else:
        wind_cf[start_idx:end_idx] *= np.random.uniform(1.2, 1.4)
wind_cf = np.clip(wind_cf, 0.05, 0.98)
# 平滑（去除高频毛刺）
wind_cf = gaussian_filter1d(wind_cf, sigma=1.5)

# ==================== 2. 光伏曲线 ====================
def solar_elevation_angle(dt, lat):
    day_year = dt.timetuple().tm_yday
    declination = -23.45 * np.cos(2 * np.pi * (day_year + 10) / 365) * np.pi / 180.0
    hour_angle = (dt.hour - 12) * 15 * np.pi / 180.0
    lat_rad = lat * np.pi / 180.0
    sin_elev = np.sin(lat_rad)*np.sin(declination) + np.cos(lat_rad)*np.cos(declination)*np.cos(hour_angle)
    return np.arcsin(np.clip(sin_elev, -1, 1))

def clear_sky_irradiance(dt, lat):
    elev = solar_elevation_angle(dt, lat)
    if elev <= 0:
        return 0.0
    return np.sin(elev) ** 1.2

clear_sky = np.array([clear_sky_irradiance(dt, LATITUDE) for dt in timestamps])

# 云量：每天基础值+日内随机游走
daily_cloud_base = np.random.beta(2, 5, DAYS)
daily_cloud_base = 0.3 + 0.5 * daily_cloud_base
cloud_factor = np.repeat(daily_cloud_base, HOURS_PER_DAY)
for d in range(DAYS):
    idx = slice(d*HOURS_PER_DAY, (d+1)*HOURS_PER_DAY)
    intra = np.cumsum(np.random.normal(0, 0.05, HOURS_PER_DAY)) * 0.1
    cloud_factor[idx] = np.clip(cloud_factor[idx] + intra, 0.2, 0.95)
cloud_attenuation = 1 - 0.8 * (cloud_factor - 0.3) / 0.7
cloud_attenuation = np.clip(cloud_attenuation, 0.2, 1.0)
pv_cf = clear_sky * cloud_attenuation
pv_cf = np.clip(pv_cf, 0.0, 0.95)
pv_cf += np.random.normal(0, 0.005, TOTAL_HOURS)
pv_cf = np.clip(pv_cf, 0.0, 0.98)
pv_cf = gaussian_filter1d(pv_cf, sigma=1.0)

# ==================== 3. 电价曲线（含负电价，拉大峰谷差） ====================
# 基础负荷形状：早晚高峰明显，夜间低谷极低
load_profile = np.zeros(HOURS_PER_DAY)
for h in range(24):
    if 7 <= h <= 9:  # 早高峰
        load_profile[h] = 0.85 + 0.15 * (h - 7) / 2  # 0.85-1.0
    elif 10 <= h <= 11:  # 上午持续
        load_profile[h] = 0.95
    elif 12 <= h <= 14:  # 中午略降
        load_profile[h] = 0.80 + 0.05 * np.sin(np.pi * (h - 13) / 2)
    elif 15 <= h <= 16:  # 下午回升
        load_profile[h] = 0.85 + 0.05 * (h - 15)
    elif 17 <= h <= 19:  # 晚高峰
        load_profile[h] = 0.90 + 0.10 * (h - 17) / 2  # 0.9-1.0
    elif 20 <= h <= 21:  # 晚间下降
        load_profile[h] = 0.70 - (h - 20) * 0.15
    elif h >= 22 or h <= 5:  # 夜间低谷
        if h <= 5:
            load_profile[h] = 0.15 + 0.05 * h / 5  # 0:00=0.15, 5:00=0.20
        else:
            load_profile[h] = 0.20 - (h - 22) * 0.05  # 22:00=0.20, 23:00=0.15
    else:  # 其他时段
        load_profile[h] = 0.60

load_profile = np.clip(load_profile, 0.12, 1.0)

# 工作日和周末差异（周末负荷更低）
day_of_week = np.array([dt.weekday() for dt in timestamps])
# 周末负荷降低20-30%
weekend_factor = np.where(day_of_week >= 5, 0.75, 1.0)
# 周五下午负荷也略低
friday_evening_factor = np.where((day_of_week == 4) & (hour_of_day >= 16), 0.9, 1.0)
load_hourly = np.tile(load_profile, DAYS) * weekend_factor * friday_evening_factor

# 可再生能源渗透影响（出力高时电价降低）
renewable_output = (wind_cf + pv_cf) / 2.0
renewable_effect = 0.5 * renewable_output  # 最大影响0.5（原0.4）

# 季节电价趋势：夏季高（空调），冬季也高（供暖），春秋低
season_price_factor = 1 + 0.15 * np.sin(2 * np.pi * (day_of_year - 30) / 365)  # 1月、7月高

# 价格噪声（低频，保持平滑）
price_noise = np.random.normal(0, 0.06, TOTAL_HOURS)
price_noise = gaussian_filter1d(price_noise, sigma=6)

# 基础电价（扩大范围）
base_price = 40 + 50 * load_hourly  # 原50+30*load，范围40-90 → 扩大至40-90

# 最终电价
price = base_price * (1 - renewable_effect) * season_price_factor + 8 * price_noise

# 负电价注入：选取约8%的天数（增加负电价频率）
neg_price_days = np.random.choice(DAYS, size=int(DAYS * 0.5), replace=False)
for d in neg_price_days:
    # 随机选择连续4-10小时
    start_h = np.random.choice([0, 1, 2, 3, 12, 13, 14, 15])
    duration = np.random.randint(4, 11)
    for h in range(duration):
        t_idx = d * 24 + (start_h + h) % 24
        if 0 <= t_idx < TOTAL_HOURS:
            # 负电价范围 -25 到 -5（更负）
            price[t_idx] = -np.random.uniform(5, 25)

# 正电价尖峰注入（约3%的天数，下午时段）
peak_price_days = np.random.choice(DAYS, size=int(DAYS * 0.03), replace=False)
for d in peak_price_days:
    start_h = np.random.choice([16, 17, 18, 19])
    duration = np.random.randint(2, 5)
    for h in range(duration):
        t_idx = d * 24 + (start_h + h) % 24
        if 0 <= t_idx < TOTAL_HOURS:
            # 尖峰电价 150-300
            price[t_idx] = np.random.uniform(150, 300)

# 整体平滑（保持过渡自然）
price = gaussian_filter1d(price, sigma=1.5)
price = np.clip(price, -25, 300)

# 确保电价曲线在高峰时段足够高，低谷时段足够低
# 对每天进行微调，确保峰谷差
for d in range(DAYS):
    start_idx = d * 24
    day_prices = price[start_idx:start_idx + 24]
    day_max = day_prices.max()
    day_min = day_prices.min()

    # 如果峰谷差小于80，放大峰谷差
    if day_max - day_min < 80:
        # 放大系数1.2-1.5
        scale = np.random.uniform(1.2, 1.5)
        mean_price = day_prices.mean()
        # 以均值为中心放大
        price[start_idx:start_idx + 24] = mean_price + (day_prices - mean_price) * scale
        # 确保负电价不会变得太负
        price[start_idx:start_idx + 24] = np.clip(price[start_idx:start_idx + 24], -25, 300)

print(f"电价统计:")
print(f"  正电价尖峰天数占比: {len(peak_price_days) / DAYS * 100:.1f}%")

# ==================== 4. 氢气需求曲线（标幺值0~1，拉大峰谷差，包含零需求时段） ====================
# 日形状：白天高，夜间低，凌晨可能出现零需求
h2_profile = np.zeros(24)
for h in range(24):
    if 0 <= h <= 3:  # 凌晨0-3点：可能为零需求
        # 随机决定是否为零（约60%的天数有零需求时段）
        # 这里先设置基础值，后面再加随机性
        h2_profile[h] = 0.0
    elif h == 4:  # 凌晨4点：开始复苏
        h2_profile[h] = 0.05 + 0.03 * np.random.rand()
    elif 5 <= h <= 6:  # 清晨5-6点：缓慢上升
        h2_profile[h] = 0.1 + (h - 5) * 0.15
    elif 7 <= h <= 9:  # 早上7-9点：快速上升至高峰
        h2_profile[h] = 0.3 + (h - 7) * 0.25
    elif 10 <= h <= 15:  # 白天10-15点：持续高峰
        h2_profile[h] = 0.95 + 0.05 * np.sin(np.pi * (h - 12.5) / 5)
    elif 16 <= h <= 18:  # 下午16-18点：晚高峰
        h2_profile[h] = 0.9 - (h - 16) * 0.2
    elif 19 <= h <= 21:  # 晚上19-21点：持续下降
        h2_profile[h] = 0.4 - (h - 19) * 0.15
    elif 22 <= h <= 23:  # 深夜22-23点：降至零附近
        h2_profile[h] = 0.1 - (h - 22) * 0.05  # 22:00=0.1, 23:00=0.05

# 确保非负
h2_profile = np.clip(h2_profile, 0.0, 1.0)

# 扩展至每天
h2_demand_pu = np.tile(h2_profile, DAYS)

# 为每天添加随机性：某些天的凌晨时段可能不为零，某些天的凌晨时段更长
for d in range(DAYS):
    start_idx = d * 24
    # 随机决定今天凌晨是否有零需求时段（70%概率有零需求）
    has_zero_hours = np.random.random() < 0.7

    if has_zero_hours:
        # 随机决定零需求时段的长度（1-4小时）
        zero_duration = np.random.randint(1, 5)
        # 随机决定零需求开始的小时（0-2点）
        zero_start = np.random.randint(0, 3)
        for h in range(zero_duration):
            if zero_start + h < 4:  # 只在凌晨0-4点范围内
                h2_demand_pu[start_idx + zero_start + h] = 0.0
    else:
        # 没有零需求时段，但凌晨时段仍然很低
        for h in range(4):
            h2_demand_pu[start_idx + h] = max(0.05, h2_demand_pu[start_idx + h] * 0.5)

# 周末降低25%
day_of_week = np.array([dt.weekday() for dt in timestamps])
weekend_factor_h2 = np.where(day_of_week >= 5, 0.75, 1.0)
h2_demand_pu *= weekend_factor_h2

# 季节变化（夏季+15%，冬季-15%）
season_demand = 1 + 0.15 * np.sin(2 * np.pi * (day_of_year - 150) / 365)
h2_demand_pu *= season_demand

# 随机波动（平滑，保持连续）
random_demand = np.random.lognormal(0, 0.12, TOTAL_HOURS)
random_demand = gaussian_filter1d(random_demand, sigma=4)
random_demand = random_demand / np.mean(random_demand)
h2_demand_pu *= random_demand

# 将非常小的值（<0.01）设置为0，模拟真实零需求
h2_demand_pu[h2_demand_pu < 0.01] = 0.0

# 归一化到0~1
if h2_demand_pu.max() > h2_demand_pu.min():
    h2_demand_pu = (h2_demand_pu - h2_demand_pu.min()) / (h2_demand_pu.max() - h2_demand_pu.min())
h2_demand_pu = np.clip(h2_demand_pu, 0.0, 1.0) **2

# 确保零需求时段严格为0（归一化后可能不再是0，重新强制）
for d in range(DAYS):
    start_idx = d * 24
    # 如果某个时段原本是0，但归一化后变成了很小的正数，重新设为0
    for h in range(24):
        if h2_profile[h] == 0.0 and h2_demand_pu[start_idx + h] < 0.05:
            h2_demand_pu[start_idx + h] = 0.0


# ==================== 5. 电解槽参数（基于您提供的6个，扩展至20个，保留原始精度） ====================
# 原始数据（根据您提供的文本逐行录入，共23列，列名如下）
orig_data = [
    [1, 5, 5, 0.25, 3600, 3600, 112.6, 0, 198.67, 17.85, 84.27, 2, 3, 2, 2, 4, 3, 20, 2252, 0, 19.867, 1.785, 10],
    [2, 24, 7, 0.35, 5040, 5040, 121.4, 0, 208.53, 21.87, 123.5, 2, 4, 2, 2, 4, 3, 20, 2428, 0, 20.853, 2.187, 14],
    [3, 38, 6, 0.3, 4320, 4320, 117.6, 0, 202.17, 12.93, 102.2, 2, 3, 2, 2, 4, 3, 20, 2352, 0, 20.217, 1.293, 12],
    [4, 61, 5, 0.25, 3600, 3600, 113.2, 0, 198.21, 17.21, 84.02, 2, 3, 2, 2, 4, 3, 20, 2264, 0, 19.821, 1.721, 10],
    [5, 91, 6, 0.3, 4320, 4320, 118.1, 0, 201.85, 12.25, 101.9, 2, 3, 2, 2, 4, 3, 20, 2362, 0, 20.185, 1.225, 12],
    [6, 116, 7, 0.35, 5040, 5040, 121.5, 0, 208.12, 22.32, 123.3, 2, 4, 2, 2, 4, 3, 20, 2430, 0, 20.812, 2.232, 14],
]
columns = ['id', 'busno', 'unknown1', 'P_standby', 'RU', 'RD', 'Cost_st_cold', 'Cost_sd_cold',
           'unknown2', 'Fai', 'T_standby', 'T_idle', 'T_under_max', 'T_over_max', 'T_under_min',
           'T_over_min', 'num', 'unknown3', 'Coef_A', 'Coef_B', 'Param1', 'Param2', 'P_rated']
df_orig = pd.DataFrame(orig_data, columns=columns)

# 生成14个新电解槽（参数基于原始列的范围随机生成，整数保留整数，浮点数保留3位小数）
num_new = 14
new_rows = []
for _ in range(num_new):
    row = []
    for col in columns:
        if col == 'id':
            continue
        col_min = df_orig[col].min()
        col_max = df_orig[col].max()
        if col in ['id', 'busno', 'unknown1', 'RU', 'RD', 'Cost_st_cold', 'Cost_sd_cold', 'unknown2',
                   'T_under_max', 'T_over_max', 'T_under_min', 'T_over_min', 'num', 'unknown3', 'Coef_A', 'Coef_B', 'P_rated']:
            # 整数类型
            val = np.random.randint(col_min, col_max+1)
        else:
            # 浮点数，保留3位小数
            val = round(np.random.uniform(col_min, col_max), 3)
        row.append(val)
    new_rows.append(row)
new_df = pd.DataFrame(new_rows, columns=[c for c in columns if c != 'id'])
new_df.insert(0, 'id', range(7, 7+num_new))
all_elec_df = pd.concat([df_orig, new_df], ignore_index=True)

# ==================== 6. 保存数据 ====================
main_df = pd.DataFrame({
    'timestamp': timestamps,
    'wind_cf': np.round(wind_cf, 4),
    'pv_cf': np.round(pv_cf, 4),
    'price_MWh': np.round(price, 2),
    'hydrogen_demand_pu': np.round(h2_demand_pu, 4)
})
main_df.to_csv('renewable_price_hydrogen.csv', index=False)

all_elec_df.to_csv('electrolyzers.csv', index=False)

print("数据生成完成！")
print(f"总天数: {DAYS}, 总小时数: {TOTAL_HOURS}")
print("输出文件:")
print("  - renewable_price_hydrogen.csv : 风电/光伏容量因子、电价($/MWh，含负价)、氢气需求标幺值(0~1)")
print("  - electrolyzers.csv : 20个电解槽完整参数（整数保留整，小数保留3位）")
print(f"负电价天数占比: {len(neg_price_days)/DAYS*100:.1f}%")
print("\n前5行预览:")
print(main_df.head())