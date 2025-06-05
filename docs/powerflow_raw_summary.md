## 1. Case Identification Data  
Defines the case-wide settings before any network elements. 

| Parameter | Type    | Description                                                               | Units |
|-----------|---------|---------------------------------------------------------------------------|-------|
| `IC`      | integer | New case flag (`0` = base case, `1` = add data)                           | —     |
| `SBASE`   | float   | System MVA base                                                           | MVA   |
| `REV`     | integer | PSS®E revision number                                                     | —     |
| `XFRRAT`  | float   | Transformer rating units code (`≤0` = MVA, `>0` = current as MVA)         | —     |
| `NXFRAT`  | float   | Non-transformer branch rating code (`≤0` = MVA, `>0` = current as MVA)     | —     |
| `BASFRQ`  | float   | System base frequency                                                     | Hz    |

<details>
<summary>Example</summary>

```raw
0, 100.00, 33, 0, 0, 60.00       / April 12, 2016 13:35:48; Simulator Version 19; BuildDate 2016_2_6
```
</details>

---

## 2. Bus Data  
Defines each bus in the network.

| Parameter | Type    | Description                                            | Units |
|-----------|---------|--------------------------------------------------------|-------|
| `I`       | integer | Bus number                                             | —     |
| `NAME`    | string  | Alphanumeric bus identifier (up to 12 chars)           | —     |
| `BASKV`   | float   | Bus base voltage                                       | kV    |
| `IDE`     | integer | Bus type (`1`=load, `2`=gen, `3`=swing, `4`=isolated)  | —     |
| `AREA`    | integer | Area number                                            | —     |
| `ZONE`    | integer | Zone number                                            | —     |
| `OWNER`   | integer | Owner number                                           | —     |
| `VM`      | float   | Voltage magnitude                                      | pu    |
| `VA`      | float   | Voltage phase angle                                    | °     |
| `NVHI`    | float   | Normal voltage high limit                              | pu    |
| `NVLO`    | float   | Normal voltage low limit                               | pu    |
| `EVHI`    | float   | Emergency voltage high limit                           | pu    |
| `EVLO`    | float   | Emergency voltage low limit                            | pu    |

<details>
<summary>Example</summary>

```raw
    1,'1           ',138.0000,3,1,1,1,1.00000,   0.0000,1.10000,0.90000,1.10000,0.90000
    2,'2           ',138.0000,2,1,1,1,0.99783,   0.0102,1.10000,0.90000,1.10000,0.90000
    3,'3           ',138.0000,1,1,1,1,0.86395,  10.7472,1.10000,0.90000,1.10000,0.90000
   …  
   24,'24          ',230.0000,1,1,1,1,0.85521,  24.7952,1.10000,0.90000,1.10000,0.90000  
0 / END OF BUS DATA, BEGIN LOAD DATA
```
</details>

---

## 3. Load Data  
Specifies loads at each bus.

| Parameter | Type    | Description                                       | Units          |
|-----------|---------|---------------------------------------------------|----------------|
| `I`       | integer | Bus number                                        | —              |
| `ID`      | string  | Load identifier (1–2 chars)                       | —              |
| `STAT`    | integer | Status (`1`=in-service, `0`=out-of-service)       | —              |
| `AREA`    | integer | Area number                                       | —              |
| `ZONE`    | integer | Zone number                                       | —              |
| `PL`      | float   | Constant-power load active component              | MW             |
| `QL`      | float   | Constant-power load reactive component            | Mvar           |
| `IP`, `IQ`| float   | Const-current load (MW @ 1 pu, Mvar @ 1 pu)       | —              |
| `YP`, `YQ`| float   | Const-admittance load (MW/Mvar @ 1 pu)            | —              |
| `OWNER`   | integer | Owner number                                      | —              |
| `SCALE`   | integer | Scalable flag (`1`=scalable)                      | —              |
| `INTRPT`  | integer | Interruptible flag                                | —              |

<details>
<summary>Example</summary>

```raw
    2,'1 ',1,1,1,  97.000,20.000,0.000,0.000,0.000,0.000,1,1
    3,'1 ',1,1,1,  90.000,19.000,0.000,0.000,0.000,0.000,1,1
    …  
   20,'1 ',1,1,1,  65.000,13.000,0.000,0.000,0.000,0.000,1,1  
0 / END OF LOAD DATA, BEGIN FIXED SHUNT DATA
```
</details>

---

## 4. Fixed Bus Shunt Data  
Models constant shunt devices.

| Parameter | Type    | Description                                   | Units        |
|-----------|---------|-----------------------------------------------|--------------|
| `I`       | integer | Bus number                                    | —            |
| `ID`      | string  | Shunt identifier                              | —            |
| `STAT`    | integer | Status (`1`=in-service)                       | —            |
| `GL`      | float   | Shunt conductance                             | MW @ 1 pu    |
| `BL`      | float   | Shunt susceptance                             | Mvar @ 1 pu  |

<details>
<summary>Example</summary>

```raw
0 / END OF FIXED SHUNT DATA, BEGIN GENERATOR DATA
```
</details>

---

## 5. Generator Data  
Specifies all synchronous machines.
| Parameter | Type    | Description                                          | Units       |
|-----------|---------|------------------------------------------------------|-------------|
| `I`       | integer | Bus number                                           | —           |
| `ID`      | string  | Machine identifier                                   | —           |
| `PG`      | float   | Active power output                                  | MW          |
| `QG`      | float   | Reactive power output                                | Mvar        |
| `QT`, `QB`| float   | Reactive power limits                                | Mvar        |
| `VS`      | float   | Voltage setpoint                                     | pu          |
| `IREG`    | integer | Regulated bus                                        | —           |
| `MBASE`   | float   | Machine MVA base                                     | MVA         |
| `ZR`, `ZX`| float   | Source impedance                                     | pu          |
| `RT`, `XT`| float   | GSU Impedance                                        | pu          |
| `GTAP`    | float   | Transformer turns ratio                              | pu          |
| `STAT`    | integer | Status                                               | —           |
| `RMPCT`   | float   | Mvar contribution share                              | %           |
| `PT`, `PB`| float   | Active power limits                                  | MW          |
| `BASLOD`  | integer | Baseload flag                                        | —           |
| `O1–O4`   | integer | Owner numbers                                        | —           |
| `F1–F4`   | float   | Owner fractions                                      | pu          |

<details>
<summary>Example</summary>

```raw
    1,'1 ',35.849,180.357,9900.0,-9900.0,1.00000,0,100.0,0.00000,1.00000,0.00000,0.00000,1.00000,1,100.0,1000.0,0.0,1,1.0000,0,1.0000,0,1.0000,0,1.0000,0,1.0000
    2,'1 ',67.000,  0.000,   0.0,    0.0,1.00000,0,100.0,0.00000,1.00000,0.00000,0.00000,1.00000,1,100.0,1000.0,0.0,1,1.0000,0,1.0000,0,1.0000,0,1.0000,0,1.0000
    …  
0 / END OF GENERATOR DATA, BEGIN BRANCH DATA
```
</details>

---

## 6. Non-Transformer Branch Data  
Models lines and jumpers.

| Parameter  | Type    | Description                                        | Units            |
|------------|---------|----------------------------------------------------|------------------|
| `I`        | integer | From-bus number                                    | —                |
| `J`        | integer | To-bus number                                      | —                |
| `CKT`      | string  | Circuit identifier                                 | —                |
| `R`, `X`   | float   | Series impedance                                   | pu               |
| `B`        | float   | Total line charging admittance                     | pu               |
| `RATE1–12` | float   | MVA rating levels                                  | MVA              |
| `GI`, `BI` | float   | Shunt admittances at “from” end                    | MW/Mvar @ 1 pu   |
| `GJ`, `BJ` | float   | Shunt admittances at “to” end                      | MW/Mvar @ 1 pu   |
| `STAT`     | integer | Status (`1`=in-service)                            | —                |
| `MET`      | integer | Metered-end flag                                   | —                |
| `LEN`      | float   | Line length                                        | user-defined     |
| `O1–O4`    | integer | Owner numbers                                      | —                |
| `F1–F4`    | float   | Owner fractions                                    | pu               |

<details>
<summary>Example</summary>

```raw
    1,2,'1 ',0.00070,0.00123,0.00065,175.00,0,0,0.00000,0.00000,0.00000,0.00000,1,1,0.0,1,1.0000,0,1.0000,0,1.0000,0,1.0000
    3,1,'1 ',0.05419,0.21114,0.06130,175.00,0,0,0.00000,0.00000,0.00000,0.00000,1,1,0.0,1,1.0000,0,1.0000,0,1.0000,0,1.0000
    …  
0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA
```
</details>

---

## 7. Transformer Data  
Models step-up and network transformers.

| Parameter     | Type    | Description                                               | Units           |
|---------------|---------|-----------------------------------------------------------|-----------------|
| `I`,`J`,`K`   | integer | Winding bus numbers (`K=0` if two-winding only)           | —               |
| `CKT`         | string  | Transformer identifier                                    | —               |
| `CW`,`CZ`,`CM`| integer | I/O codes for tap, impedance & magnetizing units          | —               |
| `MAG1`,`MAG2` | float   | Magnetizing admittance                                    | pu or W/pu/I    |
| `NOMV1–3`     | float   | Nominal winding voltages (if `CW>1`)                      | kV              |
| `R12`,`X12`…  | float   | Leakage impedances                                        | pu or % or Ω    |
| `GTAP`        | float   | Off-nominal turns ratio                                   | pu              |
| `STAT`        | integer | Status                                                    | —               |
| `O1–O4`,`F1–F4`| int/float | Ownership information                                   | — / pu          |
| `VECGRP`      | string  | Vector group code                                         | —               |

<details>
<summary>Example</summary>

```raw
   24, 3,0,'1 ',1,1,1,0.00000,0.00000,2,'        ',1,1,1.0000,0,1.0000,0,1.0000,0,1.0000
     0.00230,0.08390,100.00
   1.00000,230.000,0.000,400.00,0.00,0.00,0,0,1.50000,0.51000,1.50000,0.51000,159,0,0.00000,0.00000
   1.00000,230.000
```
</details>
