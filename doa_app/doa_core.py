"""
Coarray MUSIC DOA estimation core.

Python port of the coarray MUSIC algorithm from the repository
(codeByChunLinLiu: weight_function.m, sample_covariance_to_difference_coarray.m,
coarray_MUSIC.m). Implements the CVX-free x_U path (ref [1]).

  [1] C.-L. Liu and P. P. Vaidyanathan, "Remarks on the Spatial Smoothing Step
      in Coarray MUSIC," IEEE SPL, vol. 22, no. 9, pp. 1438-1442, Sep. 2015.

Designer: Engineer Ahmed Majed / المهندس أحمد ماجد
"""

import numpy as np


def coprime_sensors(M=5, N=7):
    """Extended coprime array sensor positions (integer, half-wavelength units)."""
    part1 = np.arange(0, N) * M
    part2 = np.arange(1, 2 * M) * N
    S = np.unique(np.concatenate([part1, part2]))
    return S.astype(float)


def weight_U(S):
    """Return U: the central contiguous ULA segment of the difference coarray."""
    S = np.unique(S)
    diff = np.subtract.outer(S, S).ravel()
    D_set = np.unique(diff)
    D_max = int(round(D_set.max()))
    D_full = np.arange(-D_max, D_max + 1)
    holes = np.setdiff1d(D_full, np.round(D_set).astype(int))
    if holes.size == 0:
        return D_set
    N_max = int(np.abs(holes).min()) - 1
    return np.arange(-N_max, N_max + 1).astype(float)


def sample_autocorr_xU(S, R_S):
    """Average the sample covariance over equal lags to get x_U on the ULA coarray."""
    S = np.asarray(S, dtype=float)
    U = weight_U(S)
    lag = np.subtract.outer(S, S)  # lag[i, j] = S[i] - S[j]
    x_U = np.zeros(U.shape[0], dtype=complex)
    for m, u in enumerate(U):
        mask = np.isclose(lag, u)
        x_U[m] = R_S[mask].mean()
    return U, x_U


def _toeplitz(col, row):
    """Toeplitz matrix with first column `col` and first row `row` (row[0] wins)."""
    col = np.asarray(col)
    row = np.asarray(row)
    n = col.shape[0]
    idx = np.subtract.outer(np.arange(n), np.arange(n))  # i - j
    vals = np.concatenate([row[:0:-1], col])             # index offset by (n-1)
    return vals[idx + (n - 1)]


def _music_noise_subspace(x_U, num_sources):
    """Build the spatial-smoothing Toeplitz matrix and return its noise subspace."""
    L = x_U.shape[0]
    if L % 2 == 0:
        raise ValueError("x_U length must be odd (symmetric coarray).")
    mid = L // 2  # 0-based index of the zero lag

    col = x_U[mid:]                 # x_U[mid .. end]
    row = x_U[mid::-1]              # x_U[mid, mid-1, ..., 0]
    R_tilde = _toeplitz(col, row)
    R_tilde = (R_tilde + R_tilde.conj().T) / 2.0

    w, V = np.linalg.eigh(R_tilde)
    order = np.argsort(np.abs(w))[::-1]      # descending by magnitude
    V = V[:, order]
    K = R_tilde.shape[0]
    d = min(num_sources, K - 1)
    Un = V[:, d:]                            # noise subspace
    return Un, K


def coarray_music_spectrum(x_U, num_sources, angles_grid_deg):
    """MUSIC pseudo-spectrum over an angle grid (degrees), normalized to max 1."""
    Un, K = _music_noise_subspace(x_U, num_sources)
    theta_bar = 0.5 * np.sin(np.deg2rad(angles_grid_deg))     # normalized DOA
    idx = np.arange(K).reshape(-1, 1)
    steer = np.exp(2j * np.pi * idx * theta_bar.reshape(1, -1))  # K x G
    proj = Un.conj().T @ steer
    denom = np.sum(np.abs(proj) ** 2, axis=0)
    P = 1.0 / denom
    P = P / P.max()
    return P


def estimate_doa(angles_true_deg, num_sources=None, M=5, N=7,
                 snapshots=500, snr_db=10, seed=None,
                 grid_step=0.05):
    """
    Simulate a coprime-array measurement for the given true angles and estimate
    the DOAs with coarray MUSIC.

    Returns a dict with sensors, spectrum grid/values, and estimated angles.
    """
    rng = np.random.default_rng(seed)
    angles_true_deg = np.asarray(angles_true_deg, dtype=float)
    D = angles_true_deg.size
    if num_sources is None:
        num_sources = D

    S = coprime_sensors(M, N)
    LEN_S = S.shape[0]

    theta_bar = 0.5 * np.sin(np.deg2rad(angles_true_deg))
    V_S = np.exp(2j * np.pi * np.outer(S, theta_bar))         # LEN_S x D

    src = (rng.standard_normal((D, snapshots)) +
           1j * rng.standard_normal((D, snapshots))) / np.sqrt(2)
    noise = (rng.standard_normal((LEN_S, snapshots)) +
             1j * rng.standard_normal((LEN_S, snapshots))) / np.sqrt(2)
    noise_std = 10 ** (-snr_db / 20.0)
    x_S = V_S @ src + noise_std * noise

    R_S = (x_S @ x_S.conj().T) / snapshots
    U, x_U = sample_autocorr_xU(S, R_S)

    grid = np.arange(-90.0, 90.0 + grid_step, grid_step)
    P = coarray_music_spectrum(x_U, num_sources, grid)
    P_db = 10 * np.log10(P)

    est = _find_peaks(grid, P, num_sources)

    return {
        "sensors": S,
        "coarray_len": int(U.shape[0]),
        "grid_deg": grid,
        "spectrum": P,
        "spectrum_db": P_db,
        "angles_true_deg": np.sort(angles_true_deg),
        "angles_est_deg": np.sort(est),
        "snapshots": snapshots,
        "snr_db": snr_db,
        "M": M,
        "N": N,
    }


def _find_peaks(grid, P, k):
    """Return the angles (deg) of the k strongest local maxima of P."""
    is_peak = np.r_[False, (P[1:-1] > P[:-2]) & (P[1:-1] >= P[2:]), False]
    peak_idx = np.where(is_peak)[0]
    if peak_idx.size == 0:
        peak_idx = np.array([int(np.argmax(P))])
    top = peak_idx[np.argsort(P[peak_idx])[::-1][:k]]
    return grid[np.sort(top)]
