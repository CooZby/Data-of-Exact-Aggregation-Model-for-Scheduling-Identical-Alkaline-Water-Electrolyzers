import sys
import os
import pandas as pd
import numpy as np
import math

# 如果还没有添加项目根目录，则添加（但 main_sc.py 已经添加了）
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 现在导入
from DataDef import RNU, Electrolyzer
from func import interpolate_day_load

class DataReader:
    """自调度数据读取器（无火电、无潮流，支持新能源机组）"""

    def __init__(self, data_path: str, duration=24, num_devices=10):
        # 获取当前文件所在目录的上一级目录，然后拼接 inputdata
        # current_dir = os.path.dirname(os.path.abspath(__file__))  # 当前文件所在目录
        # parent_dir = os.path.dirname(current_dir)  # 上一级目录
        # self.data_path = os.path.join(parent_dir, "inputdata", data_path)
        self.data_file = pd.ExcelFile(data_path)

        self.pmax = 100
        # self.H_base = 15000 # 24
        self.H_base = 15000 # 96
        self.Ele_max = num_devices

        # 核心参数（默认值，会从para读取覆盖）
        self.input_duration = 24  # 原始数据每小时点数（如24）
        self.duration = duration  # 目标调度每小时点数
        self.DayMax = 500  # 总数据天数

        # 控制是否启用风电/光伏（从para表单读取）
        self.enable_wind = True
        self.enable_pv = True

        # 完整曲线数据（长度 = duration * DayMax）
        self.load_full = None  # 负荷 (MW)
        self.price_full = None  # 电价 (货币单位/MWh)
        self.hydrogen_demand_full = None  # 氢气需求 (kg/h)

        # 当前使用的曲线切片（用于调度）
        self.load = None
        self.price = None
        self.hydrogen_demand = None

        # 新能源机组列表
        self.rnu_list_full = []  # 完整新能源机组（500天曲线）
        self.rnu_list = []  # 当前使用的新能源机组切片

        # 电解槽列表
        self.electrolyzers = []

        # 解析所有表单
        self._parse_para()
        self._parse_curves()  # 包含负荷、电价、氢气、新能源曲线
        self._parse_electrolyzer()

        # 默认使用所有天
        self.set_schedule_days(list(range(self.DayMax)))

    # ------------------------------------------------------------------
    # 1. 参数解析
    # ------------------------------------------------------------------
    def _parse_para(self):
        try:
            para_df = pd.read_excel(self.data_file, sheet_name="para", index_col=0)
        except Exception as e:
            raise RuntimeError(f"读取参数文件失败: {e}")

        if para_df.shape[1] == 0:
            raise ValueError("sheet 'para' 中没有数据列。")
        data_col = para_df.columns[0]

        def _get(key, cast_type, default=None):
            try:
                if key not in para_df.index:
                    if default is not None:
                        return default
                    raise KeyError(f"参数 '{key}' 未找到。")
                val = para_df.at[key, data_col]
                if pd.isna(val) and default is not None:
                    return default
                return cast_type(val)
            except Exception as e:
                raise type(e)(f"读取参数 '{key}' 失败: {e}")

        # # 读取基本参数（如果有的话）
        # self.input_duration = _get("input_duration", int, default=24)
        # self.duration = _get("duration", int, default=96)
        # self.DayMax = _get("DayMax", int, default=500)
        self.enable_wind = _get("enable_wind", bool, default=True)
        self.enable_pv = _get("enable_pv", bool, default=True)

        # 可选：弃电惩罚（可后续在模型中设定）
        self.wind_penalty = _get("wind_penalty", float, default=0.0)
        self.pv_penalty = _get("pv_penalty", float, default=0.0)

        print(f"参数：原始分辨率 {self.input_duration} 点/天 → 目标 {self.duration} 点/天，"
              f"总数据 {self.DayMax} 天，风电启用={self.enable_wind}，光伏启用={self.enable_pv}")

    # ------------------------------------------------------------------
    # 2. 曲线解析（使用您原有的插值函数）
    # ------------------------------------------------------------------
    def _parse_curves(self):
        """读取 curve 表单，包含 load, wind, pv, price, hydrogen"""
        try:
            df = pd.read_excel(self.data_file, sheet_name="curve")
        except Exception as e:
            raise RuntimeError(f"读取 curve 表单失败: {e}")

        required_cols = ['load', 'price', 'hydrogen']
        if self.enable_wind:
            required_cols.append('wind')
        if self.enable_pv:
            required_cols.append('pv')

        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"curve 表单缺少必要列: {col}")

        # 原始总点数
        total_orig_pts = self.input_duration * self.DayMax
        if len(df) < total_orig_pts:
            raise ValueError(f"curve 表单数据不足：需要 {total_orig_pts} 行，实际 {len(df)} 行")
        df = df.iloc[:total_orig_pts]

        # 提取原始数据（按天分组）
        load_raw = df['load'].values
        price_raw = df['price'].values
        h2_raw = df['hydrogen'].values
        wind_raw = df['wind'].values if self.enable_wind else None
        pv_raw = df['pv'].values if self.enable_pv else None

        # 目标总点数
        total_target_pts = self.duration * self.DayMax

        # 插值函数（对每一天分别调用您的插值函数）
        def daily_interpolate(orig_array):
            """orig_array: 长度 total_orig_pts，返回插值后长度为 total_target_pts 的数组"""
            result = []
            for d in range(self.DayMax):
                start = d * self.input_duration
                end = (d + 1) * self.input_duration
                day_data = orig_array[start:end]
                # 使用原有插值函数
                interp_vals = interpolate_day_load(day_data, self.duration, method="linear")
                result.extend(interp_vals)
            return np.array(result)

        # 执行插值（存储完整曲线）
        self.load_full = daily_interpolate(load_raw)
        self.price_full = daily_interpolate(price_raw)
        self.hydrogen_demand_full = self.H_base * daily_interpolate(h2_raw)

        # 构建完整的新能源机组
        self.rnu_list_full = []

        # 风电
        if self.enable_wind and wind_raw is not None:
            wind_curve_full = daily_interpolate(wind_raw)
            pmax_wind = self.pmax  # 可以根据实际修改，或从曲线最大值获取
            wind_unit = RNU(pmax=pmax_wind, Curve=wind_curve_full.tolist(), Punish=self.wind_penalty)
            self.rnu_list_full.append(wind_unit)

        # 光伏
        if self.enable_pv and pv_raw is not None:
            pv_curve_full = daily_interpolate(pv_raw)
            pmax_pv = self.pmax
            pv_unit = RNU(pmax=pmax_pv, Curve=pv_curve_full.tolist(), Punish=self.pv_penalty)
            self.rnu_list_full.append(pv_unit)

        print(f"曲线加载完成，总调度步数 {total_target_pts}，共 {self.DayMax} 天数据")

    # ------------------------------------------------------------------
    # 新增：灵活选择调度天数
    # ------------------------------------------------------------------
    def set_schedule_days(self, days_list):
        """
        设置要调度的天数列表

        Parameters:
        -----------
        days_list : list
            要调度的天数索引列表（0-based），例如 [0, 1, 2] 表示第1-3天
            或者 [5, 6, 7, 8] 表示第6-9天
            或者 [i for i in range(10, 20)] 表示第11-20天
        """
        if not days_list:
            raise ValueError("days_list 不能为空")

        # 确保天数索引在有效范围内
        valid_days = [d for d in days_list if 0 <= d < self.DayMax]
        if len(valid_days) != len(days_list):
            print(f"警告：部分天数超出范围，已过滤。有效天数：{len(valid_days)}")

        if not valid_days:
            raise ValueError(f"没有有效的天数索引，有效范围：0-{self.DayMax - 1}")

        # 计算需要提取的起始和结束索引
        start_idx = valid_days[0] * self.duration
        end_idx = (valid_days[-1] + 1) * self.duration

        # 提取曲线切片
        self.load = self.load_full[start_idx:end_idx]
        self.price = self.price_full[start_idx:end_idx]
        self.hydrogen_demand = self.hydrogen_demand_full[start_idx:end_idx]

        # 提取新能源曲线切片
        self.rnu_list = []
        for rnu in self.rnu_list_full:
            curve_slice = rnu.Curve[start_idx:end_idx]
            new_rnu = RNU(pmax=rnu.pmax, Curve=curve_slice, Punish=rnu.Punish)
            self.rnu_list.append(new_rnu)

        # 更新调度天数（用于外部访问）
        self.schedule_days = valid_days
        self.current_duration = len(self.load)

        print(f"已设置调度天数：第 {[d + 1 for d in valid_days]} 天")
        print(f"调度步数：{self.current_duration}（{self.current_duration / self.duration} 天）")

    def get_single_day(self, day_idx):
        """
        获取单天的数据

        Parameters:
        -----------
        day_idx : int
            天数索引（0-based）

        Returns:
        --------
        dict : 包含该天所有曲线的字典
        """
        if day_idx < 0 or day_idx >= self.DayMax:
            raise ValueError(f"天数索引超出范围，有效范围：0-{self.DayMax - 1}")

        start = day_idx * self.duration
        end = (day_idx + 1) * self.duration

        day_data = {
            'load': self.load_full[start:end],
            'price': self.price_full[start:end],
            'hydrogen_demand': self.hydrogen_demand_full[start:end],
            'rnu_curves': []
        }

        for rnu in self.rnu_list_full:
            day_data['rnu_curves'].append(rnu.Curve[start:end])

        return day_data

    def get_continuous_days(self, start_day, num_days):
        """
        获取连续多天的数据

        Parameters:
        -----------
        start_day : int
            起始天数索引（0-based）
        num_days : int
            要获取的天数

        Returns:
        --------
        dict : 包含连续多天曲线的字典
        """
        if start_day < 0 or start_day + num_days > self.DayMax:
            raise ValueError(f"天数范围超出，有效起始：0-{self.DayMax - num_days}")

        days_list = list(range(start_day, start_day + num_days))
        self.set_schedule_days(days_list)

        return {
            'load': self.load,
            'price': self.price,
            'hydrogen_demand': self.hydrogen_demand,
            'rnu_list': self.rnu_list,
            'days': days_list
        }

    def get_day_count(self):
        """返回总数据天数"""
        return self.DayMax

    def get_duration_per_day(self):
        """返回每天的点数"""
        return self.duration

    # ------------------------------------------------------------------
    # 3. 电解槽参数解析（保持原样）
    # ------------------------------------------------------------------
    def _parse_electrolyzer(self):
        """解析 electrolyzer 表单，支持中英文列名，自动转换时间参数"""
        try:
            df = pd.read_excel(self.data_file, sheet_name="electrolyzer")
        except Exception:
            self.electrolyzers = []
            return

        step_ratio = self.duration / self.input_duration

        col_aliases = {
            'num': ['设备数量', '数量', 'num'],
            'buses': ['母线编号', '接入母线', 'busno'],
            'P_rated': ['额定功率', '额定容量', 'P_rated'],
            'P_standby': ['待机功率', 'P_standby'],
            'Alpha_max': ['过负荷上限比例', 'Alpha_max'],
            'Alpha_min': ['过负荷下限比例', 'Alpha_min'],
            'Beta_max': ['低负荷上限比例', 'Beta_max'],
            'Beta_min': ['低负荷下限比例', 'Beta_min'],
            'RU': ['爬坡速率', '向上爬坡', 'RampUp', 'RU'],
            'RD': ['爬坡速率', '向下爬坡', 'RampDown', 'RD'],
            'Coef_A': ['产氢系数A', '系数A', 'Coef_A'],
            'Coef_B': ['产氢系数B', '系数B', 'Coef_B'],
            'Fai': ['热启动制氢损失', '启动损失', 'Fai'],
            'H2Prod_max': ['最大产氢率', '产氢上限', 'H2Prod_max'],
            'H2Prod_min': ['最小产氢率', '产氢下限', 'H2Prod_min'],
            'Cost_st_cold': ['冷启动成本', '启动费用', 'Cost_st_cold'],
            'Cost_sd_cold': ['冷关停成本', '关停费用', 'Cost_sd_cold'],
            'Cost_OM': ['运维成本系数', '运维成本', 'Cost_OM'],
            'T_over_max': ['最大过负荷时间', '过负荷最大时长', 'T_over_max'],
            'T_under_max': ['最大低负荷时间', '低负荷最大时长', 'T_under_max'],
            'T_over_min': ['最小过负荷时间', '过负荷最小时长', 'T_over_min'],
            'T_under_min': ['最小停机时间', '停机最小时长', 'T_under_min'],
            'T_idle': ['最小运行时间', '开机最小时长', 'T_idle'],
            'T_standby': ['预热时间', '待机时长', 'T_standby'],
        }

        def get_val(row, key, default=0.0, is_time=False, is_int=False):
            val = None
            if key in df.columns:
                val = row[key]
            elif key in col_aliases:
                for alias in col_aliases[key]:
                    if alias in df.columns:
                        val = row[alias]
                        break
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return default
            res = float(val)
            if is_time:
                # 原始表中为小时，转换为步长，向上取整
                return math.ceil(res * step_ratio)
            if is_int:
                return int(res)
            return res

        self.electrolyzers = []
        for idx, row in df.iterrows():
            if idx >= self.Ele_max:
                break
            ele = Electrolyzer()

            # ID
            id_col = next((c for c in ['序号', 'id', 'idx', 'ElectrolyzerID'] if c in df.columns), None)
            ele.id = int(row[id_col]) if id_col else idx + 1
            ele.num = get_val(row, 'num', default=1, is_int=True)

            # 母线
            bus_col = next((c for c in ['母线编号', 'busno', 'BusID', 'buses'] if c in df.columns), None)
            ele.buses = [int(row[bus_col])] if bus_col and not pd.isna(row[bus_col]) else [0]

            # 功率
            ele.P_rated = get_val(row, 'P_rated', default=0.0)
            ele.P_standby = get_val(row, 'P_standby', default=0.0)

            # 比例系数
            ele.Alpha_max = get_val(row, 'Alpha_max', default=1.5)
            ele.Alpha_min = get_val(row, 'Alpha_min', default=1.2)
            ele.Beta_max = get_val(row, 'Beta_max', default=0.8)
            ele.Beta_min = get_val(row, 'Beta_min', default=0.6)

            # 爬坡率 (单位：MW/步长)
            ru_raw = get_val(row, 'RU', default=None)
            rd_raw = get_val(row, 'RD', default=None)
            step_hours = self.duration / 24.0  # 每个调度步长代表的小时数
            default_ramp = 0.6 * ele.P_rated * step_hours  # MW/步长
            ele.RU = (ru_raw * step_hours) if ru_raw is not None else default_ramp
            ele.RD = (rd_raw * step_hours) if rd_raw is not None else default_ramp

            # 产氢系数
            ele.Coef_A = get_val(row, 'Coef_A', default=0.0)
            ele.Coef_B = get_val(row, 'Coef_B', default=0.0)
            ele.Fai = get_val(row, 'Fai', default=0.0)
            ele.H2Prod_max = get_val(row, 'H2Prod_max', default=ele.P_rated * 0.8)
            ele.H2Prod_min = get_val(row, 'H2Prod_min', default=0.0)

            # 时间参数（转换为步长）
            ele.T_over_max = get_val(row, 'T_over_max', default=0, is_time=True)
            ele.T_under_max = get_val(row, 'T_under_max', default=0, is_time=True)
            ele.T_over_min = get_val(row, 'T_over_min', default=0, is_time=True)
            ele.T_under_min = get_val(row, 'T_under_min', default=0, is_time=True)
            ele.T_idle = get_val(row, 'T_idle', default=0, is_time=True)
            ele.T_standby = get_val(row, 'T_standby', default=0, is_time=True)

            # 成本
            ele.Cost_st_cold = get_val(row, 'Cost_st_cold', default=0.0)
            ele.Cost_sd_cold = get_val(row, 'Cost_sd_cold', default=0.0)
            ele.Cost_OM = get_val(row, 'Cost_OM', default=0.0)

            self.electrolyzers.append(ele)

        print(f"电解槽解析完成，共 {len(self.electrolyzers)} 类设备")