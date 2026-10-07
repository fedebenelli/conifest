"""Modelo termodinámico y cálculo de la envolvente de fases.

Formulación de ``script.py``: Peng-Robinson 78 con regla de mezcla QMR
(kij/lij), cálculo de envolvente P-T por el método de especificación
``kind="dew"`` con estado inicial t0=300 K, p0=1 bar.

El último componente del script (C50-C80A, asfaltenos) queda **fuera del
modelo**: no aparece en z, tc/pc/w ni en la matriz kij.
"""

from functools import lru_cache

import numpy as np
from yaeos import QMR, PengRobinson78

# ---------------------------------------------------------------------------
# Propiedades críticas y acentricidad de los 14 componentes
# ---------------------------------------------------------------------------
tc = [
    126.2, 304.2, 190.6, 305.4, 369.8,
    408.1, 425.2, 460.4, 469.6, 507.4,
    691.81, 956.77, 1118.6, 1325.03,
]
pc = [
    33.94, 73.76, 46.0, 48.84, 42.46,
    36.48, 38.0, 33.84, 33.74, 29.69,
    19.46, 13.08, 10.66, 10.28,
]
w = [
    0.04, 0.225, 0.008, 0.098, 0.152,
    0.176, 0.193, 0.227, 0.251, 0.296,
    0.68, 1.208, 0.949, 0.182,
]

names = [
    "N2", "CO2", "C1", "C2", "C3",
    "iC4", "nC4", "iC5", "nC5", "C6",
    "C7-C25", "C26-C49", "C50-64PN", "C65-C80PN",
]

nc = len(tc)
kij = np.zeros((nc, nc))
lij = np.zeros((nc, nc))

kij[0, :] = [
    0.0, -0.032, 0.028, 0.041, 0.076, 0.094, 0.07, 0.087,
    0.088, 0.08, 0.08, 0.08, 0.08, 0.08,
]
kij[1, :] = [
    -0.032, 0.0, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12,
    0.12, 0.12, 0.1, 0.1, 0.1, 0.1,
]
for _i in range(2, 14):
    kij[_i, 1] = 0.12 if _i <= 9 else 0.1
kij[2:10, 0] = [0.028, 0.041, 0.076, 0.094, 0.07, 0.087, 0.088, 0.08]
kij[10:14, 0] = 0.08
kij[10:14, 1] = 0.1

mixrule = QMR(kij=kij, lij=lij)
ar_model = PengRobinson78(tc, pc, w, mixrule=mixrule)

# ---------------------------------------------------------------------------
# Composición por defecto (idéntica a la del script menos C50-C80A)
# ---------------------------------------------------------------------------
z_default_raw = [
    0.0048, 0.00919, 0.43391, 0.1101, 0.06544,
    0.00789, 0.03787, 0.01279, 0.02248, 0.02698,
    0.22738, 0.03747, 0.0023, 0.00054,
]

# Todos los componentes del modelo tienen slider
VISIBLE = list(range(nc))

# Valores por defecto de los 14 sliders
sliders_default = list(z_default_raw)

# ---------------------------------------------------------------------------
# Grupos de sliders
# ---------------------------------------------------------------------------
GROUPS = {
    "Gases": [0, 2, 3, 4, 5, 6],          # N2, C1, C2, C3, iC4, nC4
    "CO2": [1],                            # CO2
    "Intermedios": [7, 8, 9, 10],          # iC5, nC5, C6, C7-C25
    "Pesados": [11, 12, 13],               # C26-C49, C50-64PN, C65-C80PN
}
GROUP_ORDER = list(GROUPS)

GROUP_COLORS = {
    "Gases": "#1f77b4",
    "CO2": "#d62728",
    "Intermedios": "#2ca02c",
    "Pesados": "#9467bd",
}


def normalize(raw):
    """Normaliza las fracciones crudas (14 componentes).

    Reproduce el ``z = z / sum(z)`` del script con ``sum()`` nativo
    sobre ``np.float64`` y división de arrays.
    """
    arr = np.array(list(raw), dtype=float)
    total = sum(arr)
    if total <= 0:
        return None
    return arr / total


def group_shares(raw):
    """Participación (%) de cada grupo en la mezcla total."""
    total = float(sum(raw))
    if total <= 0:
        return {g: 0.0 for g in GROUP_ORDER}
    return {g: 100.0 * sum(raw[i] for i in idx) / total
            for g, idx in GROUPS.items()}


@lru_cache(maxsize=512)
def _envelope_cached(z_key):
    """Envelope cacheado por composición normalizada redondeada."""
    z = np.array(z_key, dtype=float)
    try:
        env = ar_model.phase_envelope_pt(z, kind="dew", t0=300, p0=1)
    except Exception:
        return None
    if env is None or len(env.temperatures) == 0:
        return None
    return {
        "temperatures": np.asarray(env.temperatures, dtype=float),
        "pressures": np.asarray(env.pressures, dtype=float),
        "kinds": np.asarray(env.main_phases_kinds),
        "critical_t": np.asarray(env.critical_temperatures, dtype=float),
        "critical_p": np.asarray(env.critical_pressures, dtype=float),
    }


def compute_envelope(raw):
    """Envolvente P-T para una composición cruda (14 componentes).

    Devuelve ``None`` si la mezcla es inválida (o nula), si es un componente
    puro (no hay envolvente y CO2 puro deja el solver de yaeos en bucle
    infinito) o si el cálculo falla.
    """
    z = normalize(raw)
    if z is None:
        return None
    if np.count_nonzero(z) < 2:
        return None
    z_key = tuple(float(v) for v in z)
    return _envelope_cached(z_key)
