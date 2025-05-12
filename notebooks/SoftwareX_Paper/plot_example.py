import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import matplotlib.patches as mpatches



#TODO: use same font as paper 
#TODO: check the jounral for figure type, maybe EPS ?
 

def analyze_power_difference(p1, p2):
    p1 = np.array(p1)
    p2 = np.array(p2)
    diff = p1 - p2
    rmse = np.sqrt(np.mean(diff**2))

    # Handle constant series gracefully
    if np.std(p1) == 0 or np.std(p2) == 0:
        corr = np.nan  # or set to 0 or "undefined"
    else:
        corr = np.corrcoef(p1, p2)[0, 1]

    return rmse, corr

def plot_bus_power_comparison(
    psse_obj, pypsa_obj,
    psse_p_col, pypsa_p_col,
    bus_id, outfile_name,
    psse_label="PSS®E", pypsa_label="PyPSA",
    annotation_loc=None, legend_loc='upper right',
    figsize=(8, 6), dpi=300
):
    """
    Plots active power comparison for a given bus from PSS®E and PyPSA results,
    and shows RMSE and Correlation on the plot.

    Parameters:
    - psse_obj, pypsa_obj: Snapshot-enabled wrapper objects
    - psse_p_col, pypsa_p_col: column names for power in each DataFrame
    - bus_id: the bus number to extract
    - outfile_name: path to save SVG
    - annotation_loc: legend placement string: 'upper left', etc.
    - legend_loc: location for legend
    - figsize: figure size (tuple)
    - dpi: figure resolution
    """
    # --- PSSE side ---
    psse_values = []
    psse_times = []
    for snap in psse_obj.snapshot_history:
        df = snap.buses
        match = df[df["BUS_ID"] == bus_id]
        if not match.empty and psse_p_col.upper() in match.columns:
            psse_values.append(match[psse_p_col.upper()].values[0])
            psse_times.append(snap.time)

    psse_series = pd.Series(psse_values, index=pd.to_datetime(psse_times))

    # --- PyPSA side ---
    bus_id_str = str(bus_id)
    pypsa_series = pypsa_obj.buses_t[pypsa_p_col].loc[:, bus_id_str]

    # --- Align indices ---
    if len(psse_series) != len(pypsa_series):
        print(f"⚠️ Length mismatch: PSSE ({len(psse_series)}) vs PyPSA ({len(pypsa_series)}). Truncating to min.")
    min_len = min(len(psse_series), len(pypsa_series))

    psse_series = psse_series.iloc[:min_len]
    pypsa_series = pypsa_series.iloc[:min_len]
    time_hr = (psse_series.index - psse_series.index[0]).total_seconds() / 3600

    # --- Analysis ---
    try:
        rmse, corr = analyze_power_difference(psse_series.values, pypsa_series.values)
        annotation = f"RMSE = {rmse:.3f} MW\nCorr  = {corr:.3f}"
        print(f"[Bus {bus_id}] {annotation.replace(chr(10), ', ')}")
    except Exception as e:
        annotation = "Analysis Failed"
        print(f"[Bus {bus_id}] Analysis failed: {e}")

    # --- Annotation placement ---
    ha, va = 'left', 'top'
    if annotation_loc is None:
        median_val = np.median(psse_series.values)
        if median_val < 20:
            annotation_coords = (0.98, 0.02)
            ha, va = 'right', 'bottom'
        else:
            annotation_coords = (0.02, 0.98)
            ha, va = 'left', 'top'
    else:
        loc_map = {
            'upper left': ((0.02, 0.98), 'left', 'top'),
            'upper right': ((0.98, 0.98), 'right', 'top'),
            'lower left': ((0.02, 0.02), 'left', 'bottom'),
            'lower right': ((0.98, 0.02), 'right', 'bottom')
        }
        annotation_coords, ha, va = loc_map.get(annotation_loc, ((0.02, 0.98), 'left', 'top'))

    # --- Plot config ---
    plt.rcParams.update({
        "font.size": 11.5,
        "axes.titlesize": 12,
        "axes.labelsize": 11.5,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "axes.grid": True,
        "grid.alpha": 0.4,
        "grid.color": "#999999",
        "grid.linestyle": "--",
        "xtick.direction": "in",
        "ytick.direction": "in"
    })

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    ax.plot(time_hr, psse_series.values, label=f'{psse_label} - Bus {bus_id}',
            color='#1f77b4', marker='o', markersize=3.0, linestyle=':', linewidth=1)
    ax.plot(time_hr, pypsa_series.values, label=f'{pypsa_label} - Bus {bus_id}',
            color='#d62728', marker='s', markersize=3.0, linestyle=':', linewidth=1)

    ax.set_xlabel("Time [hr]")
    ax.set_ylabel("Active Power $P$ [MW]")

    ax.xaxis.set_major_locator(plt.MaxNLocator(8))
    ax.yaxis.set_major_locator(plt.MaxNLocator(8))
    ax.minorticks_on()
    ax.grid(which='minor', linestyle=':', linewidth=0.4, alpha=0.5)
    ax.legend(loc=legend_loc, frameon=True)

    ax.text(
        annotation_coords[0], annotation_coords[1], annotation,
        transform=ax.transAxes,
        verticalalignment=va,
        horizontalalignment=ha,
        fontsize=10,
        bbox=dict(facecolor='white', edgecolor='gray', boxstyle='round,pad=0.3')
    )

    plt.tight_layout()
    plt.savefig("./figs/" + outfile_name, format="svg")
    plt.show()
    plt.close()


def plot_voltage_angle_spread(
    psse_obj, pypsa_obj,
    swing_bus, target_bus,
    outfile_name="voltage_angle_spread.svg",
    annotation_loc=None, legend_loc='upper right',
    figsize=(6.6, 5.0), dpi=300
):
    """
    Compare voltage angle difference (Δθ) from swing bus to target bus
    for PSS®E and PyPSA over time.
    """

    # --- PSS®E ---
    psse_spread = []
    psse_times = []
    for snap in psse_obj.snapshot_history:
        df = snap.buses
        df = df.set_index("BUS_ID")
        if swing_bus in df.index and target_bus in df.index:
            angle_swing = df.loc[swing_bus, "ANGLE_RAD"] * 180 / np.pi
            angle_target = df.loc[target_bus, "ANGLE_RAD"] * 180 / np.pi
            psse_spread.append(abs(angle_target - angle_swing))
            psse_times.append(snap.time)

    psse_series = pd.Series(psse_spread, index=pd.to_datetime(psse_times))

    # --- PyPSA ---
    bus_s = str(swing_bus)
    bus_t = str(target_bus)
    pypsa_series = (
        pypsa_obj.buses_t.v_ang[bus_t] - pypsa_obj.buses_t.v_ang[bus_s]
    ) * 180 / np.pi

    # --- Align ---
    min_len = min(len(psse_series), len(pypsa_series))
    psse_series = psse_series.iloc[:min_len]
    pypsa_series = pypsa_series.iloc[:min_len]
    time_hr = (psse_series.index - psse_series.index[0]).total_seconds() / 3600

    # --- Analysis ---
    try:
        rmse, corr = analyze_power_difference(psse_series.values, pypsa_series.values)
        annotation = f"RMSE = {rmse:.3f}°\nCorr  = {corr:.3f}"
        print(f"[Δθ Bus {swing_bus}-{target_bus}] {annotation.replace(chr(10), ', ')}")
    except Exception as e:
        annotation = "Analysis Failed"
        print(f"[Δθ Bus {swing_bus}-{target_bus}] Analysis failed: {e}")

    # --- Determine annotation placement ---
    ha, va = 'left', 'top'
    if annotation_loc is None:
        median_val = np.median(psse_series.values)
        if median_val < 10:
            annotation_coords = (0.98, 0.02)
            ha, va = 'right', 'bottom'
        else:
            annotation_coords = (0.02, 0.98)
            ha, va = 'left', 'top'
    else:
        loc_map = {
            'upper left': ((0.02, 0.98), 'left', 'top'),
            'upper right': ((0.98, 0.98), 'right', 'top'),
            'lower left': ((0.02, 0.02), 'left', 'bottom'),
            'lower right': ((0.98, 0.02), 'right', 'bottom')
        }
        annotation_coords, ha, va = loc_map.get(annotation_loc, ((0.02, 0.98), 'left', 'top'))

    # --- Plot config ---
    plt.rcParams.update({
        "font.size": 11.5,
        "axes.titlesize": 12,
        "axes.labelsize": 11.5,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "axes.grid": True,
        "grid.alpha": 0.4,
        "grid.color": "#999999",
        "grid.linestyle": "--",
        "xtick.direction": "in",
        "ytick.direction": "in"
    })

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.plot(time_hr, psse_series.values, label=f"PSS®E Δθ ({swing_bus}-{target_bus})",
            color='#1f77b4', marker='o', markersize=3.0, linestyle=':', linewidth=1.2)
    ax.plot(time_hr, pypsa_series.values, label=f"PyPSA Δθ ({swing_bus}-{target_bus})",
            color='#d62728', marker='s', markersize=3.0, linestyle=':', linewidth=1.2)

    ax.set_xlabel("Time [hr]")
    ax.set_ylabel("Δθ [deg]")
    ax.legend(loc=legend_loc, frameon=False)
    ax.xaxis.set_major_locator(plt.MaxNLocator(8))
    ax.yaxis.set_major_locator(plt.MaxNLocator(8))
    ax.minorticks_on()
    ax.grid(which='minor', linestyle=':', linewidth=0.4, alpha=0.5)
    ax.legend(loc=legend_loc, frameon=True)

    ax.text(
        annotation_coords[0], annotation_coords[1], annotation,
        transform=ax.transAxes,
        verticalalignment=va,
        horizontalalignment=ha,
        fontsize=10,
        bbox=dict(facecolor='white', edgecolor='gray', boxstyle='round,pad=0.3')
    )

    plt.tight_layout()
    plt.savefig("./figs/" + outfile_name, format="svg")
    plt.show()
    plt.close()


import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches

def plot_mismatch(
    psse_obj, psse_obj1,
    bus_num,
    outfile_name="mismatch_boxplot.svg",
    annotation_loc=None, legend_loc='upper right',
    figsize=(6.6, 5.0), dpi=300
):
    """
    Plot side-by-side boxplots of the 'MISMATCH' time series at a single bus
    for two PSS®E runs (e.g. no-WEC vs. with-WEC), manually marking outliers.
    """
    # --- 1) Extract PSSE MISMATCH values for this bus ---
    def _extract(psse_wrapper):
        vals = []
        for snap in psse_wrapper.snapshot_history:
            df = snap.buses
            if 'BUS_ID' in df.columns and bus_num in df['BUS_ID'].values:
                vals.append(df.loc[df['BUS_ID'] == bus_num, 'MISMATCH'].item())
        return np.array(vals)

    data_no  = _extract(psse_obj1)
    data_yes = _extract(psse_obj)
    data     = [data_no, data_yes]
    labels   = [f"MISMATCH (No WEC)", f"MISMATCH (With WEC)"]
    colors   = ["#AED6F1", "#0B3D91"]  # light blue, dark blue

    # --- 2) Draw the boxplot WITHOUT built‐in fliers ---
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    bp = ax.boxplot(
        data,
        labels=labels,
        notch=True,
        patch_artist=True,
        showfliers=False,      # turn off built‐in fliers
        boxprops=dict(linewidth=1, zorder=2),
        whiskerprops=dict(linewidth=1, zorder=2),
        capprops=dict(linewidth=1, zorder=2),
        medianprops=dict(linewidth=0, zorder=3),
    )

    # --- 3) Color the boxes & add diamond medians ---
    for patch, col in zip(bp['boxes'], colors):
        patch.set_facecolor(col)
        patch.set_edgecolor('black')

    for i, arr in enumerate(data, start=1):
        median = np.median(arr)
        ax.scatter(
            i, median,
            marker='D', s=40,
            facecolor='white', edgecolor='black',
            zorder=4
        )

    # --- 4) Manually compute & plot outliers ---
    for i, arr in enumerate(data, start=1):
        if arr.size == 0:
            continue
        q1, q3 = np.percentile(arr, [25, 75])
        iqr    = q3 - q1
        lower, upper = q1 - 1.5*iqr, q3 + 1.5*iqr

        outliers = arr[(arr < lower) | (arr > upper)]
        if outliers.size > 0:
            # you can jitter the x‐position a little if you like:
            xs = np.full_like(outliers, i, dtype=float)
            ax.scatter(
                xs, outliers,
                marker='o', s=50,
                facecolors='none',
                edgecolors='black',
                linewidths=1.2,
                zorder=5
            )

    # --- 5) Axes styling ---
    ax.ticklabel_format(axis="y", style="scientific", scilimits=(0,0))
    ax.grid(axis="y", linestyle="--", linewidth=0.5, alpha=0.7)
    ax.set_ylabel("MISMATCH (MW)", fontsize=10)
    ax.set_title(f"Distribution of MISMATCH at Bus {bus_num}", fontsize=12)

    # --- 6) Legend ---
    handles = [mpatches.Patch(facecolor=c, edgecolor='black') for c in colors]
    ax.legend(handles, labels, loc=legend_loc)

    plt.tight_layout()
    plt.savefig(outfile_name, format="svg")
    plt.show()
    plt.close()