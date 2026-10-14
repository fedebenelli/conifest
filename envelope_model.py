"""Modelo termodinámico y cálculo de la envolvente de fases.

Formulación de ``script.py``: Peng-Robinson 78 con regla de mezcla QMR
(kij/lij), cálculo de envolvente P-T por el método de especificación
``kind="dew"`` con estado inicial t0=300 K, p0=1 bar.

Incluye variantes pre-instanciadas del modelo para manejar casos donde
uno o más grupos están ausentes (sin Gases, sin Intermedios, sin Pesados,
o combinaciones de estos).
"""

from functools import lru_cache

import numpy as np
from yaeos import QMR, PengRobinson78

# ---------------------------------------------------------------------------
# Propiedades críticas y acentricidad de los 14 componentes
# ---------------------------------------------------------------------------
tc_full = [
    126.2, 304.2, 190.6, 305.4, 369.8,
    408.1, 425.2, 460.4, 469.6, 507.4,
    691.81, 956.77, 1118.6, 1325.03,
]
pc_full = [
    33.94, 73.76, 46.0, 48.84, 42.46,
    36.48, 38.0, 33.84, 33.74, 29.69,
    19.46, 13.08, 10.66, 10.28,
]
w_full = [
    0.04, 0.225, 0.008, 0.098, 0.152,
    0.176, 0.193, 0.227, 0.251, 0.296,
    0.68, 1.208, 0.949, 0.182,
]

names = [
    "N2", "CO2", "C1", "C2", "C3",
    "iC4", "nC4", "iC5", "nC5", "C6",
    "C7-C25", "C26-C49", "C50-64PN", "C65-C80PN",
]

nc_full = len(tc_full)
kij_full = np.zeros((nc_full, nc_full))
lij_full = np.zeros((nc_full, nc_full))

kij_full[0, :] = [
    0.0, -0.032, 0.028, 0.041, 0.076, 0.094, 0.07, 0.087,
    0.088, 0.08, 0.08, 0.08, 0.08, 0.08,
]
kij_full[1, :] = [
    -0.032, 0.0, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12,
    0.12, 0.12, 0.1, 0.1, 0.1, 0.1,
]
for _i in range(2, 14):
    kij_full[_i, 1] = 0.12 if _i <= 9 else 0.1
kij_full[2:10, 0] = [0.028, 0.041, 0.076, 0.094, 0.07, 0.087, 0.088, 0.08]
kij_full[10:14, 0] = 0.08
kij_full[10:14, 1] = 0.1

# ---------------------------------------------------------------------------
# Composición por defecto
# ---------------------------------------------------------------------------
z_default_raw = [
    0.0048, 0.00919, 0.43391, 0.1101, 0.06544,
    0.00789, 0.03787, 0.01279, 0.02248, 0.02698,
    0.22738, 0.03747, 0.0023, 0.00054,
]

# Variables de compatibilidad con app.py
sliders_default = list(z_default_raw)
VISIBLE = list(range(nc_full))
# ---------------------------------------------------------------------------
# Definición de grupos (Gases incluye CO2)
# ---------------------------------------------------------------------------
GROUPS = {
    "Gases": [0, 1, 2, 3, 4, 5, 6],
    "Intermedios": [7, 8, 9, 10],
    "Pesados": [11, 12, 13],
}
GROUPS_INV = {i: g for g, idxs in GROUPS.items() for i in idxs}
ALL_GROUPS = ["Gases", "Intermedios", "Pesados"]


# ---------------------------------------------------------------------------
# Variantes pre-instanciadas del modelo
# ---------------------------------------------------------------------------
class ModelVariant:
    """Modelo con un subconjunto específico de componentes."""

    def __init__(self, component_indices):
        self.indices = sorted(component_indices)
        self.nc = len(self.indices)
        self.tc = [tc_full[i] for i in self.indices]
        self.pc = [pc_full[i] for i in self.indices]
        self.w = [w_full[i] for i in self.indices]
        self.kij = kij_full[np.ix_(self.indices, self.indices)]
        self.lij = lij_full[np.ix_(self.indices, self.indices)]
        self.mixrule = QMR(kij=self.kij, lij=self.lij)
        self.model = PengRobinson78(self.tc, self.pc, self.w, mixrule=self.mixrule)
        # Mapeo de índice original → índice local
        self.orig_to_local = {orig: local for local, orig in enumerate(self.indices)}

    def extract_z(self, z_full):
        """Extrae y normaliza z para este subconjunto."""
        if z_full is None:
            return None
        z_sub = np.array([z_full[i] for i in self.indices], dtype=float)
        total = z_sub.sum()
        if total <= 0:
            return None
        return z_sub / total

    def compute_envelope(self, z_full):
        """Calcula la envolvente con este sub-modelo."""
        z_sub = self.extract_z(z_full)
        if z_sub is None or np.count_nonzero(z_sub) < 2:
            return None
        try:
            env = self.model.phase_envelope_pt(z_sub, kind="dew", t0=300, p0=1)
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


# Crear variantes para todas las combinaciones posibles (2^3 - 1 = 7)
VARIANTS = {}
for mask in range(1, 8):
    active_groups = tuple(g for i, g in enumerate(ALL_GROUPS) if mask & (1 << i))
    component_indices = []
    for g in active_groups:
        component_indices.extend(GROUPS[g])
    VARIANTS[active_groups] = ModelVariant(component_indices)


def get_active_variant(z):
    """Selecciona la variante correcta según qué grupos están presentes."""
    active = []
    for g in ALL_GROUPS:
        indices = GROUPS[g]
        if any(z[i] > 1e-12 for i in indices):
            active.append(g)
    key = tuple(active)
    return VARIANTS.get(key)


def normalize(raw):
    """Normaliza las fracciones crudas."""
    arr = np.array(list(raw), dtype=float)
    total = sum(arr)
    if total <= 0:
        return None
    return arr / total


def group_shares(raw):
    """Participación (%) de cada grupo en la mezcla total."""
    total = float(sum(raw))
    if total <= 0:
        return {g: 0.0 for g in ALL_GROUPS}
    return {g: 100.0 * sum(raw[i] for i in idx) / total
            for g, idx in GROUPS.items()}


@lru_cache(maxsize=512)
def _envelope_cached(z_key):
    """Envelope cacheado por composición normalizada."""
    z = np.array(z_key, dtype=float)
    if np.count_nonzero(z) < 2:
        return None

    variant = get_active_variant(z)
    if variant is None:
        return None

    return variant.compute_envelope(z)


def compute_envelope(raw):
    """Envolvente P-T usando la variante correcta según grupos activos."""
    z = normalize(raw)
    if z is None:
        return None
    if np.count_nonzero(z) < 2:
        return None

    z_key = tuple(float(v) for v in z)
    return _envelope_cached(z_key)
