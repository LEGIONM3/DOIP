# DOIP Synthetic Physics Simulation Specification

## 1. Physical Dynamics Models

### 1.1 Kinematics & Spatial Motion
The platform models terrestrial and aerial units over spherical earth approximations:
$$\Delta \text{lat} = \frac{v_{\text{eff}} \cdot \Delta t \cdot \cos(\theta)}{R_{\text{Earth}}}$$
$$\Delta \text{lon} = \frac{v_{\text{eff}} \cdot \Delta t \cdot \sin(\theta)}{R_{\text{Earth}} \cdot \cos(\text{lat})}$$
where $v_{\text{eff}}$ is effective forward ground speed adjusted for headwind drag:
$$v_{\text{eff}} = \max\left(0, v - v_{\text{wind}} \cdot \cos(\theta_{\text{wind}} - \theta) \cdot 0.05 \cdot C_d\right)$$

Acceleration is constrained by maximum power and terrain friction coefficient $\mu$:
$$a_{\text{max}} = \frac{2.5}{\mu} \quad [\text{m/s}^2]$$
Turn rate is limited by vehicle chassis envelope:
$$|\omega| \le \omega_{\text{max}} \quad [\text{deg/s}]$$

### 1.2 Energy Consumption Dynamics
Fuel and battery depletion rate per second $B_{\text{rate}}$ is given by:
$$B_{\text{rate}} = \left(B_0 + k_v \cdot v_{\text{eff}} \cdot \mu \cdot \left(1 + 0.3 \cdot \frac{m_{\text{payload}}}{1000}\right)\right) \cdot \Delta t$$
- $B_0$: Base idle burn rate (%/sec)
- $k_v$: Dynamic speed burn coefficient
- $\mu$: Terrain friction multiplier (1.0 = asphalt, 1.8 = deep sand/mud)
- $m_{\text{payload}}$: Carried equipment mass (kg)

### 1.3 RF Communications Path Loss & Electronic Jamming
RF received power $P_{rx}$ at relay distance $d$ follows the log-distance path loss formulation with terrain and electronic warfare jamming attenuation:
$$\text{PL}(d) = 20 \log_{10}(d) + 32.4 \quad [\text{dB}]$$
$$P_{rx} = -30.0 - 0.5 \cdot \text{PL}(d) - 25.0 \cdot \gamma_{\text{occlusion}} - 40.0 \cdot J_{\text{jamming}} - 10.0 \cdot \frac{R_{\text{precip}}}{50.0} \quad [\text{dBm}]$$

Packet delivery ratio and latency degrade non-linearly:
- $P_{rx} > -70 \text{ dBm}$: $0\%$ packet loss, $15\text{ ms}$ latency.
- $-90 < P_{rx} \le -70 \text{ dBm}$: Packet loss $5\% - 30\%$, latency $30 - 90\text{ ms}$.
- $-110 < P_{rx} \le -90 \text{ dBm}$: Packet loss $35\% - 85\%$, latency $120 - 320\text{ ms}$.
- $P_{rx} \le -110 \text{ dBm}$: $100\%$ loss (LOST comms state), latency $2500\text{ ms}$.

### 1.4 Mechanical Logistics & Wear
Mechanical wear accumulation rate:
$$\Delta W = \left(\frac{d_{\text{traveled}}}{1000}\right) \cdot 0.05 \cdot \mu \quad [\%]$$
When $W \ge 75\%$ or fuel $\le 10\%$, `maintenance_required = True`.
