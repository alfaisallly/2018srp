# Coarray MUSIC DOA Estimator

A desktop application that estimates the **Directions of Arrival (DOA)** of
multiple signal targets using the **coarray MUSIC** algorithm on a coprime
sensor array. You enter the target angles (and optional SNR / snapshots), press
**Run**, and the app shows the estimated angles plus the MUSIC spectrum plot.

This is a self-contained Python port of the repository's MATLAB coarray-MUSIC
code (`codeByChunLinLiu`), the CVX-free `x_U` path.

**Designer: Eng. Ahmed Majed / المهندس أحمد ماجد**

## Run from source (any OS)

```bash
python -m pip install -r requirements.txt
python doa_app.py
```

## Build a standalone Windows 11 executable

On a Windows 11 machine with Python 3.10+ (64-bit) installed, double-click
`build_windows_exe.bat` (or run it in a terminal). It produces:

```
dist\DOA_Estimator.exe
```

`DOA_Estimator.exe` is a single file that runs on Windows 11 without needing
Python installed.

Under the hood the build runs:

```
pyinstaller --onefile --windowed --name DOA_Estimator --collect-all matplotlib doa_app.py
```

## Inputs

| Field | Meaning |
| --- | --- |
| Target angles (deg) | Comma-separated true DOAs, e.g. `-50, -20, 5, 25, 60` (each strictly in -90..90) |
| SNR (dB) | Signal-to-noise ratio of the simulated measurement |
| Snapshots | Number of time samples |
| Coprime M, N | Coprime array design parameters |

## Files

| File | Purpose |
| --- | --- |
| `doa_core.py` | Coarray MUSIC algorithm (NumPy) |
| `doa_app.py` | Tkinter + matplotlib GUI |
| `build_windows_exe.bat` | One-click Windows build script |
| `requirements.txt` | Python dependencies |
