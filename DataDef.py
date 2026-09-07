"""
@Author:            ZHANG Biyuan
@Date:              2025/5/26
@Brief:             调度元件参数定义
"""
from typing import List, Dict, Optional, Literal
from dataclasses import dataclass, field
from enum import Enum

@dataclass
class Thermal:
    """火电机组类"""
    # 机组运行参数
    pmax: float = 0.0
    pmin: float = 0.0
    RU: float = 0.0
    RD: float = 0.0
    SD: float = pmin
    SU: float = pmin
    UT: int = 0
    DT: int = 0
    cost_u: float = 0.0
    cost_d: float = 0.0
    u_max: int = 0
    d_max: int = 0
    ramp_fix_u: List[float] = field(default_factory=list)
    ramp_fix_d: List[float] = field(default_factory=list)

    # 成本函数参数
    bid_p: List[float] = field(default_factory=list)
    bid_pri: List[float] = field(default_factory=list)

    # 系统参数
    indices: List[int] = field(default_factory=list)
    buses: List[int] = field(default_factory=list)
    num: int = 1

    # 另一种成本形式
    a: float = 0.0
    b: float = 0.0
    c: float = 0.0


@dataclass
class Electrolyzer:
    """电解槽参数定义类 (Electrolyzer Parameter Definition)"""

    # ------------------------------------------------------------------
    # 1. 状态转换相关参数 (Parameters Related to State Transitions)
    # ------------------------------------------------------------------

    # T_OverMax: 最大连续过负荷运行时间 (Maximum Continuous Overload Duration) [h]
    T_over_max: int = 1

    # T_UnderMax: 最大连续低负荷运行时间 (Maximum Continuous Underload Duration) [h]
    T_under_max: int = 1

    # T_OverMin: 最小过负荷持续时间 (Minimum Overload Duration) [h]
    T_over_min: int = 1

    # T_UnMin: 最小低负荷或停机持续时间 (Minimum Underload/Shutdown Duration) [h]
    T_under_min: int = 1

    # T_Idle: 最小空闲/运行持续时间 (Minimum Idle/Up Time) [h]
    T_idle: int = 1

    # T_Standby:  standby状态持续时间或预热时间 (Standby Duration/Warm-up Time) [h]
    T_standby: int = 1

    # ------------------------------------------------------------------
    # 2. 制氢与功率相关参数 (Parameters Related to Hydrogen Production & Power)
    # ------------------------------------------------------------------

    # P_Rated: 额定输入电功率 (Rated Input Power) [MW]
    P_rated: float = 0.0

    # P_standby: 待机功率 (Standby Power) [MW]
    P_standby: float = 0.0

    # Alpha_Max/Min: 过负荷最大/最小比例
    Alpha_max: float = 1.5
    Alpha_min: float = 1.0

    # Beta_Max/Min: 低负荷最大/最小比例
    Beta_max: float = 0.6
    Beta_min: float = 0.2

    # R_Up/Down: 向上/向下爬坡速率 (Ramp Up/Down Rate) [MW/h]
    RU: float = 0.6 * P_rated
    RD: float = 0.6 * P_rated

    # Coef_A/B: 产氢量曲线系数 (Quadratic Coefficients for H2 Production)
    Coef_A: float = 0.0
    Coef_B: float = 0.0
    Fai: float = 0.0 #  热启动时刻的制氢损失

    # ------------------------------------------------------------------
    # 3. 衍生约束与经济参数 (Derived Constraints & Economic Parameters)
    # ------------------------------------------------------------------

    # H2_Prod_Max/Min: 最大/最小产氢率 (Max/Min Hydrogen Production Rate) [kg/h]
    H2Prod_max: float = 0.0
    H2Prod_min: float = 0.0

    # 冷启动/关停成本 [$]
    Cost_st_cold: float = 0.0
    Cost_sd_cold: float = 0.0

    # Cost_OM: 运维成本系数 (Operation & Maintenance Cost Coefficient) [$/MWh]
    Cost_OM: float = 0.0

    # ------------------------------------------------------------------
    # 4. 系统标识与拓扑参数 (System Identification & Topology)
    # ------------------------------------------------------------------

    # Indices: 设备索引列表 (Device Indices)
    indices: List[int] = field(default_factory=list)

    # Buses: 接入母线编号列表 (Connected Bus IDs)
    buses: List[int] = field(default_factory=list)

    # Num: 设备数量 (Number of Units)
    num: int = 1

    # ID: 场站编号
    id: int = 0


@dataclass
class RNU:
    """新能源机组类型 （Renewable Units）"""
    pmax: float = 0.0
    Curve: List[float] = field(default_factory=list)
    Punish: float = 0.0


@dataclass
class SolverParams:
    """求解器参数配置"""
    MIPGap: float = 1e-4
    TimeLimit: int = 10800
    Methods: int = 2