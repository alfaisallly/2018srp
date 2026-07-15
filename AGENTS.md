# AGENTS.md

## Cursor Cloud specific instructions

This repo is a collection of **MATLAB** scripts for array signal processing / DOA
estimation (classic MUSIC, forward spatial-smoothing MUSIC, and coarray MUSIC with
coprime/sum-difference arrays). There is **no lint, test, or build tooling** in the
repo — the deliverable is running the `.m` scripts.

### Runtime
MATLAB is proprietary and not available here. Use **GNU Octave** (installed by the
update script) as the drop-in runtime. `freqz` (used in
`codeByChunLinLiu/coarray_MUSIC.m`) lives in the `signal` package, so run
`pkg load signal;` first.

### Running scripts headless (no display)
The VM has no display, so use the gnuplot toolkit and offscreen Qt, then save
figures with `print`. Example:
```
QT_QPA_PLATFORM=offscreen octave -q --eval "\
  graphics_toolkit('gnuplot'); set(0,'defaultfigurevisible','off'); pkg load signal; \
  cd('codeFromNet'); source('clscl_MUSIC.m'); \
  print(gcf,'/tmp/out.png','-dpng','-r100');"
```

### Non-obvious caveats
- The standalone scripts start with `clear all`. If you write an Octave runner that
  passes arguments, read them via `argv()` (a builtin that survives `clear all`)
  *after* `source()`-ing the script — plain variables get wiped.
- `codeFromNet/forward_smooth.m` uses uppercase line-spec colors (`'R-'`, `'B-'`)
  that MATLAB tolerates but Octave rejects, so it errors under Octave unmodified.
- `codeByChunLinLiu/main_coarray_MUSIC_interpolation.m` computes the `x_V` / `R_V`
  (coarray interpolation) path via **CVX** (http://cvxr.com/cvx/), which has no
  supported Octave build. The `x_U` coarray-MUSIC path (ref [1]) runs fine without
  CVX — drive `sample_covariance_to_difference_coarray(S, R_S, 'x_U')` +
  `coarray_MUSIC(...)` directly if you need a CVX-free demonstration.

### Known-good scripts under Octave
- `codeFromNet/clscl_MUSIC.m` (classic MUSIC)
- `myCode/SD_CPA.m` (sum-difference coprime-array spatial-smoothing MUSIC)
- `codeByChunLinLiu` library via the `x_U` path (see caveat above)
