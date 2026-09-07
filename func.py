"""
@Author:            ZHANG Biyuan
@Date:              2025/5/26
@Brief:             函数
"""

"""分段线性化报价"""
def seg_k_h_process(bid_p, bid_pri):
    h = bid_pri[0]
    k = []
    for i in range(len(bid_p)):
        k.append((i + 1) / 2 * (bid_pri[i + 1] - bid_pri[i]) / bid_p[i])
    # k = [int(k[1]) for _ in range(len(k))]

    return k, h

"""求解器参数设置"""
def _para_setting(model, solver):
    if solver == "copt":
        import coptpy as cp
        # model.setParam(cp.COPT.Param.Logging, 0)
        # model.setParam(cp.COPT.Param.HeurLevel, 3)
        # model.setParam(cp.COPT.Param.RelGap, 0.001)
        # model.setParam(cp.COPT.Param.RelGap, 1)
        model.setParam(cp.COPT.Param.TimeLimit, 10800)
        model.setParam(cp.COPT.Param.Threads, 8)
    elif solver == "gurobi":
        import gurobipy as grb
        # model.setParam(grb.GRB.Param.OutputFlag, 0)
        # model.setParam(grb.GRB.Param.MIPGap, 0.001)
        # model.setParam(grb.GRB.Param.MIPGap, 1e-12)
        model.setParam(grb.GRB.Param.TimeLimit, 3600)
        # model.setParam(grb.GRB.Param.TimeLimit, 3600 * 5)
        # model.setParam(grb.GRB.Param.Heuristics, 3)
        model.setParam(grb.GRB.Param.Threads, 8)
    elif solver == "optv":
        import optvpy as op
        model.Set(op.OPTVIntParam.PRESOLVE_LEVEL, 2)
        model.Set(op.OPTVIntParam.THREADS, 8)
        model.Set(op.OPTVDblParam.TIME_LIMIT, 10800)
        model.Set(op.OPTVDblParam.GAP, 0.01)

"""计算分段成本"""
def calculate_segment_cost(power, bid_p, bid_pri):
    cost = 0

    # 如果出力为0，则没有运行成本
    if power == 0:
        return 0

    # 找到当前出力所在的区间
    current_segment = 0
    for i in range(len(bid_p) - 1):
        if bid_p[i] <= power <= bid_p[i + 1]:
            current_segment = i
            break

    # 计算前面完整区间的成本
    for i in range(current_segment):
        segment_power = bid_p[i + 1] - bid_p[i]
        cost += segment_power * bid_pri[i]

    # 计算当前区间的成本
    remaining_power = power - bid_p[current_segment]
    cost += remaining_power * bid_pri[current_segment]

    return cost


import os
import csv

"""统计信息"""
def export_compres_to_csv(compres_dict, csv_dir="CompRes", csv_name="result.csv"):
    """
    将 CompRes 字典写入 CSV（追加模式）
    - 若文件不存在：写表头 + 数据
    - 若文件已存在：只写数据

    参数：
        compres_dict: CompRes 是一个 dict
        csv_dir: 文件夹名称
        csv_name: 文件名
    """

    if not isinstance(compres_dict, dict):
        raise ValueError("compres_dict 必须是一个字典！")

    # 创建目录
    os.makedirs(csv_dir, exist_ok=True)

    csv_path = os.path.join(csv_dir, csv_name)

    headers = list(compres_dict.keys())
    row_data = [compres_dict[h] for h in headers]

    need_header = not os.path.exists(csv_path)

    with open(csv_path, "a", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)

        if need_header:
            writer.writerow(headers)

        writer.writerow(row_data)

    print(f"[CompRes 写入] {csv_path}")



"""模型求解统计"""
def _collect_solver_stats(model, cost, solving_time, solver, model_name):
    """
    收集模型求解统计信息
    - 如果 cost < 0 或 None，则认为模型无可行解，直接返回基础信息
    - 否则根据求解器类型提取详细属性
    """
    stats = {
        "CaseName": model_name,
        "ObjVal": cost,
        "BestBound": None,
        "MIPGap(%)": None,
        "SolvingTime": solving_time,
        "Node": None,
        "RootRelaxVal": None,
        "NumVars": None,
        "NumBinVars": None,
        "NumConstrs": None,
        "NumNZs": None,
        "SolverStatus": None,
        "SpeedupRatio": None,
        "RelativeGap(%)": None
    }

    # ---------------- 无可行解，直接返回 ----------------
    if cost is None or cost < 0:
        stats["SolverStatus"] = "Failed"
        return stats

    m = model

    # ---------------- COPT ----------------
    if solver.lower() == "copt":
        import coptpy as cp

        # 求解器状态
        try:
            stats["SolverStatus"] = m.getAttr("status")
        except:
            stats["SolverStatus"] = None

        # 目标值（保持原方式）
        try:
            stats["ObjVal"] = m.getObjective().value
        except:
            stats["ObjVal"] = None

        # helper：安全读取属性
        def safe(attr):
            try:
                return m.getAttr(attr)
            except:
                return None

        stats["NumBinVars"] = safe("Bins") + safe("Ints")
        stats["Node"] = safe("NodeCnt")
        stats["BestBound"] = safe("BestBnd")
        stats["NumVars"] = safe("Cols")
        stats["NumConstrs"] = safe("Rows")
        stats["NumNZs"] = safe("NumNZs")
        bg = safe("BestGap")
        stats["MIPGap(%)"] = bg * 100 if bg is not None else None

        return stats

    # ---------------- Gurobi ----------------
    elif solver.lower() == "gurobi":
        # 求解器状态
        try:
            stats["SolverStatus"] = m.Status
        except:
            stats["SolverStatus"] = None

        # 安全获取属性
        def _safe_grb_attr_attr(name):
            try:
                return getattr(m, name)
            except:
                return None

        def _safe_grb_getAttr(name):
            try:
                return m.getAttr(name)
            except:
                return None

        # 目标值
        stats["ObjVal"] = _safe_grb_attr_attr("ObjVal") or _safe_grb_getAttr("ObjVal")

        # 最优界
        stats["BestBound"] = _safe_grb_attr_attr("ObjBound") or _safe_grb_getAttr("ObjBound")

        # MIP gap
        bg = _safe_grb_attr_attr("MIPGap") or _safe_grb_getAttr("MIPGap")
        stats["MIPGap(%)"] = bg * 100 if bg is not None else None

        # 节点数
        stats["Node"] = _safe_grb_attr_attr("NodeCount") or _safe_grb_getAttr("NodeCount")

        # root relaxation
        stats["RootRelaxVal"] = _safe_grb_attr_attr("ObjBoundC") or _safe_grb_getAttr("ObjBoundC")

        # model size
        stats["NumVars"] = _safe_grb_attr_attr("NumVars") or _safe_grb_getAttr("NumVars")
        stats["NumBinVars"] = (_safe_grb_attr_attr("NumBinVars") or
                               _safe_grb_getAttr("NumBinVars") or
                               _safe_grb_attr_attr("NumIntVars"))
        stats["NumConstrs"] = _safe_grb_attr_attr("NumConstrs") or _safe_grb_getAttr("NumConstrs")

        return stats

    else:
        # unsupported solver，直接返回基础 stats
        return stats



"""插值函数"""
import numpy as np
from scipy.interpolate import CubicSpline, interp1d
def interpolate_day_load(data, target_len, method="linear"):
    """
    将原始一天的负荷 data 插值为 target_len 长度的数据

    Parameters
    ----------
    data : list or np.ndarray
        原始负荷序列
    target_len : int
        插值后的目标长度
    method : str
        插值方式 ("cubic" 或 "linear")

    Returns
    -------
    np.ndarray
        插值后的负荷曲线
    """

    data = np.array(data, dtype=float)
    n = len(data)

    # 原始时间轴：1 ~ n
    x_original = np.linspace(1, n, n)

    # 目标时间轴：1 ~ n 均匀插值 target_len 个点
    x_new = np.linspace(1, n, target_len)


    # 创建插值对象
    if method == "cubic" and n >= 3:  # cubic 至少需要3点
        interp_func = CubicSpline(x_original, data)
    else:
        interp_func = interp1d(x_original, data, kind="linear")

    return interp_func(x_new)


"""负荷曲线 绘制"""
import matplotlib.pyplot as plt
def plot_all_load_curves(loadc_dict, title="Daily Load Curves"):
    """
    画出 loadc_dict 中所有天的负荷曲线
    loadc_dict: 形如 {"day_1": [...], "day_2": [...], ...}
    """
    plt.figure(figsize=(10, 5))

    for day, curve in loadc_dict.items():
        plt.plot(curve, label=day)

    plt.xlabel("Time Interval")
    plt.ylabel("Load")
    plt.title(title)
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


"""二次函数"""
def quad_cost(p, a, b, c):
    """二次成本函数 f(p) = a p² + b p + c"""
    return a * p * p + b * p + c


"""功率分段"""
def split_power_segments(pmin, pmax, seg):
    """
    将 (pmax - pmin) 分成 seg 段，保证最后一段补偿误差。
    返回长度 seg 的数组（每段大小）
    """
    total = pmax - pmin
    avg = total / seg

    # 前 seg - 1 段四舍五入三位小数
    res = [round(avg, 3) for _ in range(seg - 1)]
    last = total - sum(res)
    res.append(last)
    return res

"""启停曲线生成"""
def generate_ramp_fix(length, pmin):
    """
    根据长度生成 fix_u 和 fix_d
    fix_u 单调递增: [d, 2d, ..., pmin]
    fix_d 单调递减: reverse
    """
    d = pmin / length
    fix_u = [round(d * (i + 1), 3) for i in range(length - 1)] + [round(pmin, 3)]
    fix_d = list(reversed(fix_u))
    return fix_u, fix_d


"""状态区间生成"""
"""启动、停机区间生成"""
def operation_interval_thermal(UT, DT, duration):
    """
    生成火电机组在机组组合模型中的运行/关停区间集合

    Args:
        UT (int): 最小开机时间（时段数）
        DT (int): 最小关机时间（时段数）
        duration (int): 调度总时段数

    Returns:
        set_on (list[tuple[int,int]]): 机组可开机区间 (a, b)，a为开始时段，b为结束时段（含）
        set_off (list[tuple[int,int]]): 机组可关机区间 (a, b)
        set_on_t (list[tuple[int,int,int]]): 机组在(a, b)区间内第t时段处于开机的三元组
    """
    # 可开及可关区间
    set_on = []
    set_off = []
    for a in range(duration):
        for b in range(a + UT, duration + 1):
            set_on.append((a, b))
        for b in range(a + DT, duration + 1):
            set_off.append((a, b))
    # 特殊处理开始阶段
    # for b in range(1, UT):
    #     set_on.append((0, b))
    for b in range(1, DT):
        set_off.append((0, b))
    # 末尾处理
    for a in range(duration - UT + 1, duration):
        set_on.append((a, duration))
    for a in range(duration - DT + 1, duration):
        set_off.append((a, duration))

    # 可开及可关含内部区间
    set_on_t = []
    for a in range(duration):
        for b in range(a + DT, duration + 1):
            for t in range(a, b):
                set_on_t.append((a, b, t))
    # 特殊处理开始阶段
    for b in range(1, UT):
        for t in range(0, b):
            set_on_t.append((0, b, t))
    # 末尾处理
    for a in range(duration - DT + 1, duration):
        for t in range(a, duration):
            set_on_t.append((a, duration, t))

    set_on = [tuple(x) for x in set_on]
    set_off = [tuple(x) for x in set_off]
    set_on_t = [tuple(x) for x in set_on_t]

    return set_on, set_off, set_on_t


"""文件清理"""
def clear_mps_files():
    import os
    from pathlib import Path
    """删除指定目录下的所有 .mps 文件"""
    MODEL_DIRS = [
        Path("../ModelFile/BasicModel"),
        Path("../ModelFile/CheckModel"),
        Path("ModelFile/TightModel")
    ]
    for dir_path in MODEL_DIRS:
        if dir_path.exists():
            for mps_file in dir_path.glob("*.mps"):
                try:
                    mps_file.unlink()  # 删除文件
                    print(f"已删除: {mps_file}")
                except Exception as e:
                    print(f"删除失败: {mps_file}, 错误: {e}")
    # SOL_DIRS = [
    #     Path("Solutions/BasicModel"),
    #     Path("Solutions/CheckModel"),
    #     Path("Solutions/TightModel")
    # ]
    # for dir_path in SOL_DIRS:
    #     if dir_path.exists():
    #         for sol_file in dir_path.glob("*.sol"):
    #             try:
    #                 sol_file.unlink()  # 删除文件
    #                 print(f"已删除: {sol_file}")
    #             except Exception as e:
    #                 print(f"删除失败: {sol_file}, 错误: {e}")

"""条件断面挡位区间解析"""
def _parse_rule_data(rules, M_flow=1e6):
    """
    解析给定时间步的规则数据，提取控制区间和限额。

    参数:
        rules: 规则列表 (ctsl.rules)
        rule_vars_dict: 规则变量字典 {(r_idx, t): var}
        time_step: 当前时间步 t
        M_flow: 默认的大M值 (用于缺失限额时的填充)

    返回:
        current_rule_vars: 当前时间步的规则变量列表
        ctl_intervals: 控制条件区间列表 [(min, max), ...]
        lim_min_vals: 最小限额列表
        lim_max_vals: 最大限额列表
    """
    ctl_intervals = []
    lim_min_vals = []
    lim_max_vals = []

    for r_idx, rule in enumerate(rules):
        # 解析控制区间 (min, max)
        if not rule.conditions:
            raise ValueError(f"Rule {r_idx} has no conditions.")

        cond = rule.conditions[0]
        if not isinstance(cond.value, tuple) or len(cond.value) != 2:
            raise ValueError(f"Rule {r_idx} value must be a tuple (min, max), got {cond.value}")

        ctl_intervals.append(cond.value)

        # 获取限额 (处理缺失值)
        lim_min = getattr(rule, 'limit_min', None)
        lim_max = getattr(rule, 'limit_max', None)

        # 如果为 None，则使用大M填充
        lim_min_vals.append(lim_min if lim_min is not None else -M_flow)
        lim_max_vals.append(lim_max if lim_max is not None else M_flow)

    return ctl_intervals, lim_min_vals, lim_max_vals