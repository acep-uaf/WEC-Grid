### LINES

| **PyPSA Attribute**     | **PyPSA Units** | **PSS®E Field**         | **PSS®E Units**       | **Convert**                                                               | **Notes**                                                                 |
|-------------------------|------------------|---------------------------|------------------------|---------------------------------------------------------------------------|---------------------------------------------------------------------------|
| `name`                  | —                | `idx`                     | int                    | `f"L{idx}"`                                                               | Simple sequential name, unique per line                                   |
| `bus0`                  | —                | `i`                       | int                    | `str(br.i)`                                                               | PyPSA bus names must match those in the network                          |
| `bus1`                  | —                | `j`                       | int                    | `str(br.j)`                                                               | Same as above; `abs(j)` no longer used                                   |
| `type`                  | —                | —                         | —                      | `""`                                                                      | Empty to use explicit r/x/b                                               |
| `r`                     | Ω                | `r`                       | p.u.                   | `r * (V_base_kV ** 2) / S_base_MVA`                                      | Uses base voltage from bus `i`                                            |
| `x`                     | Ω                | `x`                       | p.u.                   | `x * (V_base_kV ** 2) / S_base_MVA`                                      | Same as above                                                             |
| `g`                     | S                | `gi + gj`                 | p.u.                   | `(gi + gj) * S_base_MVA / (V_base_kV ** 2)`                              | Sum of both ends                                                         |
| `b`                     | S                | `bi + bj`                 | p.u.                   | `(bi + bj) * S_base_MVA / (V_base_kV ** 2)`                              | Sum of both ends                                                         |
| `s_nom`                 | MVA              | `ratea`                   | MVA                    | `br.ratea`                                                                | Direct assignment                                                         |
| `s_nom_extendable`      | —                | —                         | —                      | `False`                                                                   | Static line capacity                                                      |
| `length`                | km               | `len`                     | (not used)             | `0.0`                                                                     | IEEE 30 doesn’t define lengths                                            |
| `carrier`               | string           | —                         | —                      | `"AC"`                                                                    | Static assignment                                                         |
| `v_ang_min`             | degrees          | —                         | —                      | `-inf`                                                                    | Not enforced by PyPSA (placeholder)                                      |
| `v_ang_max`             | degrees          | —                         | —                      | `inf`                                                                     | Not enforced by PyPSA (placeholder)                                      |

---

### ⚙️ Assumptions

- `V_base_kV = self.network.buses.at[str(br.i), "v_nom"]`
- `S_base_MVA = self.parser.sbase`

**Conversions:**

- Impedance (p.u. → Ω):  
  $begin:math:display$
  Z_{[\\Omega]} = Z_{[pu]} \\cdot \\frac{V^2}{S}
  $end:math:display$

- Admittance (p.u. → S):  
  $begin:math:display$
  Y_{[S]} = Y_{[pu]} \\cdot \\frac{S}{V^2}
  $end:math:display$


### GENERATORS
| **PyPSA Attribute**     | **PyPSA Unit** | **PSS®E Field** | **PSS®E Unit** | **Convert / Notes**                                                                 |
|-------------------------|----------------|------------------|----------------|--------------------------------------------------------------------------------------|
| `name`                  | —              | `index` or `id`  | int / string   | Use `f"G{idx}"` or `id` for custom naming                                           |
| `bus`                   | —              | `i`              | int            | Use `str(g.i)` to match PyPSA bus label                                             |
| `control`               | —              | `ide`, `ireg`    | int            | Map IDE type to "PQ", "PV", or "Slack" manually                                     |
| `p_nom`                 | MW             | `mbase` or `pt`  | MVA / MW       | Use `pt` (upper active limit) as a conservative nominal capacity                    |
| `p_nom_mod`             | MW             | —                | —              | Not directly in PSS®E — can copy `p_nom` or omit                                    |
| `p_nom_extendable`      | bool           | —                | —              | `False` by default; set `True` if doing planning                                    |
| `p_nom_min`             | MW             | `pb`             | MW             | Direct copy                                                                         |
| `p_nom_max`             | MW             | `pt`             | MW             | Direct copy                                                                         |
| `p_min_pu`              | p.u.           | `pb / pt`        | MW             | `p_min_pu = pb / pt` if both are present                                            |
| `p_max_pu`              | p.u.           | —                | —              | `1.0` by default; redundant with `p_nom_max`                                        |
| `p_set`                 | MW             | `pg`             | MW             | Initial active power setpoint                                                       |
| `q_set`                 | MVAr           | `qg`             | MVAr           | Initial reactive power setpoint                                                     |
| `sign`                  | —              | —                | —              | `+1` for gen, `-1` for load — default in PyPSA                                      |
| `carrier`               | —              | `wmod`, `wpf`    | int / float    | Can infer `"wind"` if `wmod != 0`; `"other"` otherwise                              |
| `active`                | bool           | `stat`           | 0 / 1          | `True` if `stat == 1`                                                               |
| `efficiency`            | p.u.           | —                | —              | `1.0` by default; rarely in PSS®E unless extended modeling                          |


### LOADS
| **PyPSA Attribute** | **PyPSA Unit** | **PSS®E Field** | **PSS®E Unit** | **Convert / Notes**                                                                 |
|---------------------|----------------|------------------|----------------|--------------------------------------------------------------------------------------|
| `name`              | —              | `index` or `id`  | int / string   | Use `f"L{idx}"` for uniqueness, or `id` if meaningful                               |
| `bus`               | —              | `i`              | int            | `str(load.i)` to match PyPSA bus ID                                                 |
| `carrier`           | —              | —                | —              | `"AC"` by default                                                                   |
| `p_set`             | MW             | `pl`             | MW             | Active power demand                                                                 |
| `q_set`             | MVAr           | `ql`             | MVAr           | Reactive power demand                                                               |
| `sign`              | —              | —                | —              | PyPSA treats loads with sign = -1 (default), no action needed                       |
| `active`            | bool (optional)| `status`         | 0/1            | Skip if `status != 1`                                                               |

### SHUNTS

| **PyPSA Attribute** | **PyPSA Unit** | **PSS®E Field** | **PSS®E Unit** | **Convert / Notes**                                                             |
|---------------------|----------------|------------------|----------------|----------------------------------------------------------------------------------|
| `name`              | —              | `index` or `id`  | int / string   | Use `f"Shunt_{idx}"` or `id` for clarity                                        |
| `bus`               | —              | `i`              | int            | `str(sh.i)` to match PyPSA bus ID                                               |
| `g`                 | Siemens        | `gl`             | MW @ 1.0 pu    | $begin:math:text$ g = \\frac{gl}{V^2} $end:math:text$, using $begin:math:text$ V = \\text{bus.v_nom} $end:math:text$                       |
| `b`                 | Siemens        | `bl`             | MVAr @ 1.0 pu  | $begin:math:text$ b = \\frac{bl}{V^2} $end:math:text$, using $begin:math:text$ V = \\text{bus.v_nom} $end:math:text$                       |
| `sign`              | —              | —                | —              | Default is `-1` in PyPSA; no action needed                                      |
| `active`            | bool           | `status`         | 0/1            | Include only if `status == 1`                                                   |


### TRANSFORMERS

| **PyPSA Attribute**     | **PyPSA Unit** | **PSS®E Field**             | **PSS®E Unit**        | **Convert / Notes**                                                                 |
|-------------------------|----------------|------------------------------|------------------------|--------------------------------------------------------------------------------------|
| `name`                  | —              | `p1.name` or `index`         | string / int           | Use `f"T{index}"` or full `p1.name.strip()`                                         |
| `bus0`                  | —              | `p1.i`                       | int                    | Primary bus → `str(p1.i)`                                                           |
| `bus1`                  | —              | `p1.j`                       | int                    | Secondary bus → `str(p1.j)`                                                         |
| `type`                  | —              | —                            | —                      | Use `""` to use explicit impedance parameters                                        |
| `model`                 | —              | —                            | —                      | Use `"t"` for PyPSA default                                                         |
| `x`                     | p.u.           | `p2.x12`                     | p.u. on `sbase12`      | Normalize: `x = x12 * (sbase12 / s_nom)`                                            |
| `r`                     | p.u.           | `p2.r12`                     | p.u. on `sbase12`      | Normalize: `r = r12 * (sbase12 / s_nom)`                                            |
| `g`                     | p.u.           | `p1.mag1`                    | MW on system base      | Optional: `g = mag1 / s_nom`                                                        |
| `b`                     | p.u.           | `p1.mag2`                    | MVAr on system base    | Optional: `b = mag2 / s_nom`                                                        |
| `s_nom`                 | MVA            | `w1.rata` or `p2.sbase12`    | MVA                    | Use rating or base; prefer `w1.rata`                                                |
| `s_nom_extendable`      | bool           | —                            | —                      | `False` unless planning                                                             |
| `num_parallel`          | —              | —                            | —                      | `1` unless modeling multiple identical transformers                                 |
| `tap_ratio`             | —              | `w1.windv`                   | p.u.                   | Use `windv` from primary winding                                                    |
| `tap_side`              | —              | —                            | —                      | Default to `0` → tap changer on high-voltage side                                   |
| `tap_position`          | —              | —                            | —                      | Leave unset unless modeling tap schedules                                           |
| `phase_shift`           | degrees        | `w1.ang`                     | degrees                | Use `w1.ang` for voltage phase shift                                                |
| `active`                | bool           | `p1.stat`                    | 0/1/2/3/4              | `True` if `p1.stat == 1` (fully in service)                                         |
| `v_ang_min`             | degrees        | —                            | —                      | Leave as default; not enforced                                                      |
| `v_ang_max`             | degrees        | —                            | —                      | Leave as default; not enforced                                                      |