#!/usr/bin/env python
# benchmark_wecgrid.py
import argparse, json, os, sys, time, threading, psutil, gc, platform, importlib, datetime, subprocess
from pathlib import Path

# ---------- Monitoring ----------
class ProcMonitor:
    def __init__(self, interval=0.2):
        self.interval = interval
        self._proc = psutil.Process()
        self._stop = threading.Event()
        self._peak_rss = 0
        self._cpu_samples = []

    def _children(self):
        try:
            return self._proc.children(recursive=True)
        except psutil.Error:
            return []

    def _prime(self, procs):
        for p in procs:
            try:
                p.cpu_percent(None)
            except psutil.Error:
                pass

    def _loop(self):
        procs = [self._proc] + self._children()
        self._prime(procs)
        while not self._stop.is_set():
            total_cpu = 0.0
            total_rss = 0
            procs = [self._proc] + self._children()
            for p in procs:
                try:
                    total_cpu += p.cpu_percent(None)
                    total_rss += p.memory_info().rss
                except psutil.Error:
                    pass
            self._cpu_samples.append(total_cpu)
            if total_rss > self._peak_rss:
                self._peak_rss = total_rss
            time.sleep(self.interval)

    def __enter__(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._stop.set()
        self._thread.join()

    @property
    def peak_rss_gb(self):
        return self._peak_rss / (1024**3)

    @property
    def avg_cpu_pct(self):
        return (sum(self._cpu_samples) / len(self._cpu_samples)) if self._cpu_samples else 0.0

    @property
    def p95_cpu_pct(self):
        if not self._cpu_samples:
            return 0.0
        s = sorted(self._cpu_samples)
        idx = max(0, int(0.95 * len(s)) - 1)
        return s[idx]


def benchmark_run(run_fn, interval=0.2):
    with ProcMonitor(interval=interval) as mon:
        t0 = time.perf_counter()
        run_fn()
        wall = time.perf_counter() - t0
    return {
        "wall_time_s": wall,
        "peak_rss_gb": mon.peak_rss_gb,
        "avg_cpu_pct": mon.avg_cpu_pct,
        "p95_cpu_pct": mon.p95_cpu_pct,
    }

# ---------- Backend-aware counting ----------
def get_bus_gen_counts(engine, active_backend: str):
    """
    Count buses/generators from the ACTIVE backend only.
    - 'psse': engine.psse.bus / engine.psse.gen
    - 'pypsa': engine.pypsa.bus / engine.pypsa.gen
    Returns (0,0) if unavailable.
    """
    active = (active_backend or "").lower()
    buses = gens = 0

    if active == "psse":
        psse = getattr(engine, "psse", None)
        if psse is not None:
            try:
                buses = len(getattr(psse, "bus"))
            except Exception:
                buses = 0
            try:
                gens = len(getattr(psse, "gen"))
            except Exception:
                gens = 0
            return buses, gens

    if active == "pypsa":
        pypsa = getattr(engine, "pypsa", None)
        if pypsa is not None:
            try:
                buses = len(getattr(pypsa, "bus"))
            except Exception:
                buses = 0
            try:
                gens = len(getattr(pypsa, "gen"))
            except Exception:
                gens = 0
            return buses, gens

    return 0, 0

# ---------- Parse WEC farms ----------
def parse_wec_args(arg_list, file_path):
    farms = []
    for s in (arg_list or []):
        farms.append(json.loads(s))
    if file_path:
        with open(file_path, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            farms.extend(data)
        else:
            raise ValueError("--wec-file must contain a JSON list of farm objects")
    return farms

# ---------- System metadata ----------
def _mod_ver(name):
    try:
        m = importlib.import_module(name)
        return getattr(m, "__version__", None)
    except Exception:
        return None

def _git_sha():
    try:
        sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
        return sha
    except Exception:
        return None

def get_system_meta(args, buses_eff, gens_eff, wec_farms, buses_base, gens_base):
    cpu = psutil.cpu_freq()
    vm = psutil.virtual_memory()
    total_wec_devices = sum(int(f.get("size", 0)) for f in wec_farms) if wec_farms else 0
    return {
        "timestamp": datetime.datetime.now().isoformat(),
        "case": args.case,
        "backends": args.backend,
        "runs": args.runs,
        "warmup_steps": args.warmup_steps,
        "sampler_interval_s": args.interval,
        "isolate": bool(args.isolate),
        "buses_base": buses_base,
        "generators_base": gens_base,
        "buses_effective": buses_eff,
        "generators_effective": gens_eff,
        "wec_enabled": bool(wec_farms),
        "total_wec_farms": len(wec_farms) if wec_farms else 0,
        "total_wec_devices": total_wec_devices,
        "wec_farms": wec_farms or [],
        "env": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "os": platform.system(),
            "processor": platform.uname().processor,
            "logical_cpus": psutil.cpu_count(logical=True),
            "physical_cores": psutil.cpu_count(logical=False),
            "cpu_freq_mhz": cpu.current if cpu else None,
            "ram_total_gb": round(vm.total / (1024**3), 2),
            "MKL_NUM_THREADS": os.environ.get("MKL_NUM_THREADS"),
            "OPENBLAS_NUM_THREADS": os.environ.get("OPENBLAS_NUM_THREADS"),
            "NUMEXPR_NUM_THREADS": os.environ.get("NUMEXPR_NUM_THREADS"),
        },
        "versions": {
            "numpy": _mod_ver("numpy"),
            "pandas": _mod_ver("pandas"),
            "psutil": _mod_ver("psutil"),
            "pypsa": _mod_ver("pypsa"),
            "wecgrid": _mod_ver("wecgrid"),
            "wecgrid_git": _git_sha(),
        },
    }

# ---------- One simulation (apply WECs if provided) ----------
def run_single(case_path, backends, active_backend, wec_farms=None,
               warmup_steps=None, sampler_interval=0.2):
    import wecgrid

    # Warm-up (optional, unmeasured)
    if warmup_steps and warmup_steps > 0:
        warm = wecgrid.Engine()
        warm.case(case_path); warm.load(backends)
        try:
            warm.simulate(num_steps=warmup_steps)
        except TypeError:
            # if simulate doesn't accept num_steps
            warm.simulate()
        finally:
            del warm; gc.collect()

    # Timed run
    eng = wecgrid.Engine()
    eng.case(case_path); eng.load(backends)

    # Apply WECs (if any) before simulate
    if wec_farms:
        for farm in wec_farms:
            eng.apply_wec(**farm)
        # If your engine requires finalization for counts to reflect, do it here:
        # e.g., eng.prepare(), eng.commit(), etc.

    def _runner():
        eng.simulate()  # ensure plotting/logging disabled inside if supported

    try:
        metrics = benchmark_run(_runner, interval=sampler_interval)
        buses_eff, gens_eff = get_bus_gen_counts(eng, active_backend)
        total_wec_devices = sum(int(f.get("size", 0)) for f in (wec_farms or []))
        metrics.update({
            "buses": buses_eff,
            "generators": gens_eff,
            "time_per_bus_s": (metrics["wall_time_s"] / buses_eff) if buses_eff else None,
            "time_per_gen_s": (metrics["wall_time_s"] / gens_eff) if gens_eff else None,
            "time_per_wec_device_s": (metrics["wall_time_s"] / total_wec_devices) if total_wec_devices else None,
        })
    finally:
        del eng; gc.collect()
    return metrics

# ---------- CLI / Orchestration ----------
def main():
    ap = argparse.ArgumentParser(description="Benchmark WEC-Grid performance (backend-aware, WEC-aware).")
    ap.add_argument("--case", required=True, help="Path to grid case (e.g., RAW)")
    ap.add_argument("--backend", action="append", required=True,
                    help="Repeatable: --backend psse  (first entry = active backend)")
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--warmup-steps", type=int, default=10)
    ap.add_argument("--interval", type=float, default=0.2, help="Sampler interval for CPU/RSS")
    ap.add_argument("--outfile", type=str, default="./perf/benchmark.json",
                    help="Output file (.json recommended; .csv for per-run)")
    ap.add_argument("--isolate", action="store_true", help="Run each trial in a fresh Python process")
    # WEC inputs
    ap.add_argument("--wec", action="append",
                    help="JSON string for one farm (repeatable). "
                         "Ex: --wec '{\"farm_name\":\"RM3-FARM\",\"size\":1,\"wec_sim_id\":1,\"connecting_bus\":5}'")
    ap.add_argument("--wec-file", type=str, help="Path to JSON file with an array of farm dicts")
    args = ap.parse_args()

    # Pin numeric libs to 1 thread for consistency
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

    wec_farms = parse_wec_args(args.wec, args.wec_file)
    active = args.backend[0]  # "psse" or "pypsa"

    # ---- Base counts (no WEC) from a warm engine ----
    import wecgrid
    warm = wecgrid.Engine()
    warm.case(args.case); warm.load(args.backend)
    try:
        if args.warmup_steps:
            try:
                warm.simulate(num_steps=args.warmup_steps)
            except TypeError:
                warm.simulate()
    finally:
        buses_base, gens_base = get_bus_gen_counts(warm, active)
        del warm; gc.collect()

    # ---- Effective counts (with WEC), for meta display ----
    buses_eff_meta, gens_eff_meta = buses_base, gens_base
    if wec_farms:
        tmp = wecgrid.Engine()
        tmp.case(args.case); tmp.load(args.backend)
        for farm in wec_farms:
            tmp.apply_wec(**farm)
        # If your engine needs a finalize step for objects to appear, call it here.
        buses_eff_meta, gens_eff_meta = get_bus_gen_counts(tmp, active)
        del tmp; gc.collect()

    print(f"Case: {args.case}")
    print(f"Backends: {args.backend} (active: {active})")
    print(f"Runs: {args.runs}  (warm-up steps: {args.warmup_steps})")
    if wec_farms:
        print(f"WEC farms: {len(wec_farms)} (enabled)")
        print(json.dumps(wec_farms, indent=2))
        print(f"Counts (base -> effective): buses {buses_base} -> {buses_eff_meta}, "
              f"gens {gens_base} -> {gens_eff_meta}")
    else:
        print("WEC farms: none")

    results = []

    if args.isolate:
        # Fresh interpreter per run
        py = sys.executable
        for i in range(args.runs):
            print(f"[run {i+1}/{args.runs}] (isolated)")
            code = (
                "import json; "
                "from benchmark_wecgrid import run_single; "
                f"m=run_single(r'{args.case}', {args.backend}, active_backend='{active}', "
                f"wec_farms={json.dumps(wec_farms)}, warmup_steps=0, sampler_interval={args.interval}); "
                "print(json.dumps(m))"
            )
            proc = subprocess.run([py, "-c", code], capture_output=True, text=True)
            if proc.returncode != 0:
                print(proc.stderr, file=sys.stderr)
                sys.exit(proc.returncode)
            m = json.loads(proc.stdout.strip())
            m["run"] = i + 1
            results.append(m)
    else:
        # In-process runs
        for i in range(args.runs):
            print(f"[run {i+1}/{args.runs}]")
            m = run_single(args.case, args.backend, active_backend=active,
                           wec_farms=wec_farms, warmup_steps=0, sampler_interval=args.interval)
            m["run"] = i + 1
            results.append(m)

    # ---------- Summaries ----------
    def _clean(xs): return [x for x in xs if x is not None]
    def mean(xs): xs=_clean(xs); return sum(xs)/len(xs) if xs else None
    def stdp(xs):
        xs=_clean(xs)
        if not xs: return None
        m=mean(xs)
        return (sum((x-m)**2 for x in xs)/len(xs))**0.5
    def p95(xs):
        xs=_clean(xs)
        if not xs: return None
        s=sorted(xs)
        return s[max(0, int(0.95*len(s))-1)]

    wall = [r["wall_time_s"] for r in results]
    rss  = [r["peak_rss_gb"] for r in results]
    cpu  = [r["avg_cpu_pct"] for r in results]
    cpu95= [r["p95_cpu_pct"] for r in results]
    tpb  = [r.get("time_per_bus_s") for r in results]
    tpg  = [r.get("time_per_gen_s") for r in results]
    tpw  = [r.get("time_per_wec_device_s") for r in results]
    # counts recorded per-run are effective; meta also contains base/effective

    meta = get_system_meta(args, buses_eff_meta, gens_eff_meta, wec_farms, buses_base, gens_base)
    summary = {
        "runs": len(results),
        "buses_base": buses_base,
        "generators_base": gens_base,
        "buses_effective": buses_eff_meta,
        "generators_effective": gens_eff_meta,
        "wec_enabled": bool(wec_farms),
        "total_wec_farms": meta["total_wec_farms"],
        "total_wec_devices": meta["total_wec_devices"],
        "wall_time_s_mean": mean(wall), "wall_time_s_std": stdp(wall), "wall_time_s_p95": p95(wall),
        "peak_rss_gb_mean": mean(rss),  "peak_rss_gb_std": stdp(rss),  "peak_rss_gb_p95": p95(rss),
        "avg_cpu_pct_mean": mean(cpu),  "avg_cpu_pct_std": stdp(cpu),  "avg_cpu_pct_p95": p95(cpu),
        "time_per_bus_s_mean": mean(tpb), "time_per_bus_s_std": stdp(tpb),
        "time_per_gen_s_mean": mean(tpg), "time_per_gen_s_std": stdp(tpg),
        "time_per_wec_device_s_mean": mean(tpw), "time_per_wec_device_s_std": stdp(tpw),
    }

    # ---------- Output ----------
    out = Path(args.outfile)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() == ".csv":
        import csv
        with out.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=[
                "run","buses","generators",
                "wall_time_s","time_per_bus_s","time_per_gen_s","time_per_wec_device_s",
                "peak_rss_gb","avg_cpu_pct","p95_cpu_pct"
            ])
            w.writeheader()
            for r in results:
                w.writerow(r)
        with (out.with_suffix(".meta.json")).open("w") as f:
            json.dump({"meta": meta, "summary": summary}, f, indent=2)
        print(f"Saved CSV to {out.resolve()}")
        print(f"Saved meta+summary JSON to {out.with_suffix('.meta.json').resolve()}")
    else:
        payload = {"meta": meta, "summary": summary, "runs": results}
        with out.open("w") as f:
            json.dump(payload, f, indent=2)
        print(f"Saved JSON (meta+summary+runs) to {out.resolve()}")

    print("\nSummary:")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())