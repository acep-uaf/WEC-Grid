"""
Case file conversion utilities for Marine-Grid.

Provides the ``Converter`` class for translating PSS/E RAW case files
into PyPSA ``Network`` objects via ``grg-pssedata``. Handles buses,
branches, generators, loads, two-winding transformers, and shunt
impedances with per-unit conversion on the system MVA base.

File: src/marinegrid/util/convert.py
"""

# Standard library
from pathlib import Path

# Third-party
import grg_pssedata.io as grgio
import pypsa

class Converter:
    """
    Case file format converter for Marine-Grid.

    Translates power system case files into solver-ready network objects.
    Currently supports PSS/E RAW format (v30-33) via the ``grg-pssedata``
    parser, producing a PyPSA ``Network`` with all standard component
    types.

    Attributes:
        ALLOWED_EXTENSIONS: Set of file suffixes accepted by the
            converter (currently ``{".raw"}``).

    Example:
        >>> conv = Converter()
        >>> network = conv.raw_to_pypsa("IEEE14.raw")
        >>> network.buses
    """

    ALLOWED_EXTENSIONS = {".raw"}

    def __init__(self) -> None:
        """Initialize conversion helper."""
        pass

    # -------------------------------------------------------------------------
    # Conversion Methods
    # -------------------------------------------------------------------------

    def raw_to_pypsa(self, raw_file: str | Path) -> pypsa.Network:
        """
        Convert raw case file to PyPSA Network.

        Args:
            raw_file: Path to the .raw case file.

        Returns:
            Converted PyPSA Network object.

        Raises:
            TypeError: If raw_file is not a str or Path.
            FileNotFoundError: If the file does not exist.
            ValueError: If the file extension is not .raw or is not a file.
        """
        if not isinstance(raw_file, (str, Path)):
            raise TypeError("raw_file must be a str or pathlib.Path pointing to a .raw file")

        raw_file_path = Path(raw_file)

        if raw_file_path.suffix.lower() != ".raw":
            raise ValueError(f"raw_file must have a .raw extension, got: {raw_file_path.name}")

        if not raw_file_path.exists():
            raise FileNotFoundError(f"raw_file not found: {raw_file_path}")

        # Parse RAW using GRG parser (silence GRG's print_err output)
        original_print_err = getattr(grgio, "print_err", None)
        try:
            if original_print_err is not None:
                grgio.print_err = lambda *args, **kwargs: None

            case = grgio.parse_psse_case_file(raw_file_path)
        except (ValueError, TypeError, AttributeError, IOError) as e:
            raise ValueError(
                f"Failed to parse RAW file '{raw_file_path.name}': {e}"
            ) from e
        finally:
            if original_print_err is not None:
                grgio.print_err = original_print_err

        if case is None or not case.buses:
            raise ValueError("Parsed PSS/E case is empty or invalid")

        sbase = float(case.sbase)

        # Create empty PyPSA network (PyPSA infers per-unit from v_nom, r, x, g, b, s_nom)
        network = pypsa.Network()
        network.meta["psse_raw_file"] = raw_file_path
        network.meta["psse_sbase_mva"] = sbase
        network.meta["psse_basfrq_hz"] = getattr(case, "basfrq", None)

        # Define carriers used across components so optimization has valid references
        network.add("Carrier", "AC")
        network.add("Carrier", "wind")
        network.add("Carrier", "wave")

        # Build lookups
        bus_lookup = {bus.i: bus for bus in case.buses}

        # Mapping PSS/E bus types to PyPSA control types
        ide_to_ctrl = {1: "PQ", 2: "PV", 3: "Slack"}

        # --- Add Buses ---
        for bus in case.buses:
            bus_name = str(bus.i)
            network.add(
                "Bus",
                name=bus_name,
                v_nom=bus.basekv,
                v_mag_pu_set=bus.vm,
                v_mag_pu_min=bus.nvlo,
                v_mag_pu_max=bus.nvhi,
                control=ide_to_ctrl.get(bus.ide, "PQ"),
                carrier="AC",
            )
            # Store original PSS/E bus name for reference
            network.buses.at[bus_name, "psse_name"] = bus.name

        # --- Add Lines (Branches) ---
        for idx, br in enumerate(case.branches):
            # Skip out-of-service branches
            if br.st != 1:
                continue

            from_bus = abs(br.i)
            to_bus = abs(br.j)
            bus0_name = str(from_bus)
            bus1_name = str(to_bus)

            # Base voltage and impedance base for from-bus
            v_base_kv = network.buses.at[bus0_name, "v_nom"]
            z_base_ohm = (v_base_kv ** 2)

            # Convert per-unit series impedance to Ohms
            r_ohm = br.r * z_base_ohm
            x_ohm = br.x * z_base_ohm

            # Avoid zero series resistance which can break linearized PF checks
            if r_ohm == 0.0:
                r_ohm = 1e-6

            # Total shunt admittance in per-unit (branch charging + end shunts)
            g_pu = (br.gi + br.gj)
            b_pu = (br.bi + br.bj + br.b)

            # Convert per-unit shunt admittance to Siemens:
            # Y_siemens = Y_pu × Y_base, where Y_base = S_base / V_base²
            # NOTE: Verify shunt values against known power flow results.
            # If PyPSA loading percentages or reactive flows look off,
            # check whether sbase belongs in this conversion for your case.
            denom = v_base_kv ** 2
            g_s = g_pu * sbase / denom if denom != 0 else 0.0
            b_s = b_pu * sbase / denom if denom != 0 else 0.0

            s_nom = br.ratea if br.ratea > 0.0 else sbase

            line_name = f"L{idx}"
            network.add(
                "Line",
                name=line_name,
                bus0=bus0_name,
                bus1=bus1_name,
                r=r_ohm,
                x=x_ohm,
                g=g_s,
                b=b_s,
                s_nom=s_nom,
                s_nom_extendable=False,
                length=br.len,
                carrier="AC",
            )

        # --- Add Generators ---
        for idx, g in enumerate(case.generators):
            if g.stat != 1:
                continue

            gen_bus = g.i
            bus = bus_lookup.get(gen_bus)
            ctrl = ide_to_ctrl.get(bus.ide if bus is not None else 1, "PQ")

            # Nominal power and limits (kept in MW for now)
            p_nom = g.pt if g.pt > 0.0 else max(abs(g.pg), 0.0)
            if p_nom <= 0.0:
                p_nom = sbase
            p_min_pu = g.pb / p_nom if p_nom != 0.0 else 0.0

            # Scale P,Q to per-unit on system base for PyPSA's AC solver
            p_set = g.pg / sbase
            q_set = g.qg / sbase

            carrier = "wind" if getattr(g, "wmod", 0) != 0 else "AC"

            # Simple default operating cost to satisfy optimization objective requirements.
            # TODO: pull actual cost curves when available.
            marginal_cost = getattr(g, "cost", 0.0) or 0.0

            gen_name = f"G{idx}"
            network.add(
                "Generator",
                name=gen_name,
                bus=str(gen_bus),
                control=ctrl,
                p_nom=p_nom,
                p_nom_extendable=False,
                p_min_pu=p_min_pu,
                p_max_pu=1.0,
                p_set=p_set,
                q_set=q_set,
                carrier=carrier,
                efficiency=1.0,
                marginal_cost=float(marginal_cost),
            )

        # --- Add Loads ---
        for idx, load in enumerate(case.loads):
            if load.status != 1:
                continue

            load_name = f"LD{idx}"
            network.add(
                "Load",
                name=load_name,
                bus=str(load.i),
                carrier="AC",
                p_set=load.pl / sbase,
                q_set=load.ql / sbase,
            )

        # --- Add Two-Winding Transformers ---
        for idx, tx in enumerate(case.transformers):
            # Only handle two-winding transformers here
            if getattr(tx, "is_three_winding", lambda: False)():
                continue

            p1 = tx.p1
            p2 = tx.p2
            w1 = tx.w1

            # Skip transformer if fully out of service
            if p1.stat != 1:
                continue

            bus0 = str(p1.i)
            bus1 = str(p1.j)

            # Choose transformer base MVA
            s_tx_base = p2.sbase12 if getattr(p2, "sbase12", 0.0) > 0.0 else sbase
            v_base_kv = network.buses.at[bus0, "v_nom"]
            z_base_tx = (v_base_kv ** 2) / s_tx_base

            # Convert per-unit impedance to Ohms: Z_ohm = Z_pu × Z_base
            # where Z_base = V_base² / S_base (computed as z_base_tx above).
            # NOTE: Verify r/x values against your case. If the transformer uses
            # a winding-specific MVA base different from sbase12, adjust z_base_tx.
            r_ohm = p2.r12 * z_base_tx
            x_ohm = p2.x12 * z_base_tx
            if r_ohm == 0.0:
                r_ohm = 1e-6  # avoid zero-impedance warnings in linearized models

            # Use transformer MVA base as s_nom if available
            s_nom = w1.rata if w1.rata > 0.0 else s_tx_base

            tx_name = f"T{idx}"
            network.add(
                "Transformer",
                name=tx_name,
                bus0=bus0,
                bus1=bus1,
                r=r_ohm,
                x=x_ohm,
                g=0.0,
                b=0.0,
                s_nom=s_nom,
                s_nom_extendable=False,
                num_parallel=1,
                tap_ratio=w1.windv,
                tap_side=0,
                phase_shift=w1.ang,
            )

        # --- Add Shunt Impedances (Fixed and Switched) ---
        # Fixed shunts
        for idx, sh in enumerate(case.fixed_shunts):
            if sh.status != 1:
                continue

            bus_name = str(sh.i)
            v_base_kv = network.buses.at[bus_name, "v_nom"]
            if v_base_kv == 0.0:
                continue

            # gl/bl are MW/MVAr at 1.0 pu voltage on system base.
            # G_pu = gl / sbase, Y_base = sbase / V² → G_siemens = gl / V²
            # NOTE: Verify shunt MW/MVAr injection against your power flow case.
            g_s = sh.gl / (v_base_kv ** 2)
            b_s = sh.bl / (v_base_kv ** 2)

            if abs(g_s) < 1e-9 and abs(b_s) < 1e-9:
                continue

            name = f"FSH{idx}"
            network.add(
                "ShuntImpedance",
                name=name,
                bus=bus_name,
                g=g_s,
                b=b_s,
            )

        # Switched shunts: use only the initial susceptance binit for the static network
        for idx, sh in enumerate(case.switched_shunts):
            if sh.stat != 1:
                continue

            bus_name = str(sh.i)
            v_base_kv = network.buses.at[bus_name, "v_nom"]
            if v_base_kv == 0.0:
                continue

            # binit is MVAr at 1.0 pu voltage on system base.
            # B_siemens = binit / V² (same derivation as fixed shunts)
            # NOTE: Verify switched shunt MVAr against your power flow case.
            b_mvar = sh.binit
            if abs(b_mvar) < 1e-9:
                continue

            b_s = b_mvar / (v_base_kv ** 2)

            name = f"SSH{idx}"
            network.add(
                "ShuntImpedance",
                name=name,
                bus=bus_name,
                g=0.0,
                b=b_s,
            )

        # Fill dependent per-unit quantities
        network.calculate_dependent_values()

        network.name = raw_file_path.stem

        return network
