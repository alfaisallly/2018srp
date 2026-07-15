"""
Coarray MUSIC DOA Estimator - desktop GUI.

Enter target angles (degrees), press Run, and the app estimates the directions
of arrival using coarray MUSIC on a coprime array, showing the numeric results
and the MUSIC spectrum plot.

Designer: Eng. Ahmed Majed  /  المهندس أحمد ماجد
"""

import re
import sys
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)

from doa_core import estimate_doa

APP_TITLE = "Coarray MUSIC DOA Estimator"
DESIGNER = "Design: Eng. Ahmed Majed   |   تصميم: المهندس أحمد ماجد"


class DoaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE + "  -  Eng. Ahmed Majed")
        self.geometry("1040x680")
        self.minsize(900, 600)

        # Footer is packed before the expanding body so it always stays visible.
        self._build_header()
        self._build_footer()
        self._build_body()

        # Run once with defaults so the window is not empty on launch.
        self.after(200, self.run_estimation)

    # ---------------- layout ----------------
    def _build_header(self):
        head = tk.Frame(self, bg="#12324f")
        head.pack(side=tk.TOP, fill=tk.X)
        tk.Label(head, text=APP_TITLE, bg="#12324f", fg="white",
                 font=("Helvetica", 18, "bold")).pack(pady=(10, 0))
        tk.Label(head, text="Direction-of-Arrival estimation (coprime array)",
                 bg="#12324f", fg="#cfe3f5",
                 font=("Helvetica", 11)).pack(pady=(0, 10))

    def _build_body(self):
        body = tk.Frame(self)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # ---- left: controls ----
        ctrl = tk.LabelFrame(body, text="Inputs  /  المدخلات", padx=10, pady=10)
        ctrl.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        self.vars = {}
        self._add_entry(ctrl, "angles",
                        "Target angles (deg) - separate by comma or space\n"
                        "زوايا الأهداف (بالدرجات) - افصل بفاصلة أو مسافة",
                        "-50, -20, 5, 25, 60")
        tk.Button(ctrl, text="Clear angles  /  مسح الزوايا",
                  command=lambda: self.vars["angles"].set("")).pack(fill=tk.X,
                                                                    pady=(0, 8))
        self._add_entry(ctrl, "snr", "SNR (dB)", "10")
        self._add_entry(ctrl, "snapshots", "Snapshots  /  عدد اللقطات", "500")
        self._add_entry(ctrl, "M", "Coprime M", "5")
        self._add_entry(ctrl, "N", "Coprime N", "7")

        run = tk.Button(ctrl, text="Run  /  تشغيل", command=self.run_estimation,
                        bg="#1f7a3f", fg="white", font=("Helvetica", 12, "bold"),
                        activebackground="#2c9a52")
        run.pack(fill=tk.X, pady=(12, 8))

        tk.Label(ctrl, text="Results  /  النتائج",
                 font=("Helvetica", 11, "bold")).pack(anchor="w", pady=(6, 2))
        self.results = tk.Text(ctrl, width=34, height=16, wrap="word",
                               font=("Courier New", 10))
        self.results.pack(fill=tk.BOTH, expand=True)

        # ---- right: plot ----
        plot_frame = tk.Frame(body)
        plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10), pady=10)
        self.fig = Figure(figsize=(6.2, 4.8), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        NavigationToolbar2Tk(self.canvas, plot_frame)

    def _build_footer(self):
        foot = tk.Frame(self, bg="#12324f")
        foot.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Label(foot, text=DESIGNER, bg="#12324f", fg="white",
                 font=("Helvetica", 11, "bold")).pack(pady=6)

    def _add_entry(self, parent, key, label, default):
        tk.Label(parent, text=label, justify="left").pack(anchor="w")
        var = tk.StringVar(value=default)
        entry = ttk.Entry(parent, textvariable=var, width=32)
        entry.pack(fill=tk.X, pady=(0, 8))
        # tkinter's default Ctrl+A moves the cursor; make it select-all instead.
        entry.bind("<Control-a>", lambda e: (e.widget.select_range(0, "end"),
                                             e.widget.icursor("end"), "break")[-1])
        entry.bind("<Control-A>", lambda e: (e.widget.select_range(0, "end"),
                                             e.widget.icursor("end"), "break")[-1])
        self.vars[key] = var

    # ---------------- logic ----------------
    def _parse_inputs(self):
        raw = self.vars["angles"].get()
        # Accept commas, semicolons, Arabic commas, or whitespace as separators.
        tokens = [t for t in re.split(r"[\s,;،]+", raw.strip()) if t != ""]
        try:
            angles = [float(t) for t in tokens]
        except ValueError:
            raise ValueError(
                "Could not read the target angles. Enter numbers separated by "
                "commas or spaces, e.g.  -50, -20, 5, 25, 60")
        if not angles:
            raise ValueError("Please enter at least one target angle.")
        if any(abs(a) >= 90 for a in angles):
            raise ValueError("Angles must be strictly between -90 and 90 degrees.")
        snr = float(self.vars["snr"].get())
        snapshots = int(float(self.vars["snapshots"].get()))
        M = int(float(self.vars["M"].get()))
        N = int(float(self.vars["N"].get()))
        return angles, snr, snapshots, M, N

    def run_estimation(self):
        try:
            angles, snr, snapshots, M, N = self._parse_inputs()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Input error", str(exc))
            return

        try:
            res = estimate_doa(angles, snr_db=snr, snapshots=snapshots,
                               M=M, N=N, seed=7)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Computation error", str(exc))
            return

        self._show_results(res)
        self._draw_plot(res)

    def _show_results(self, res):
        true = res["angles_true_deg"]
        est = res["angles_est_deg"]
        errs = np.abs(true - est) if true.shape == est.shape else None

        lines = []
        lines.append("Array: coprime  M=%d, N=%d" % (res["M"], res["N"]))
        lines.append("Physical sensors: %d" % res["sensors"].size)
        lines.append("Coarray ULA length: %d" % res["coarray_len"])
        lines.append("Snapshots: %d   SNR: %g dB" % (res["snapshots"], res["snr_db"]))
        lines.append("")
        lines.append("%-3s %10s %10s %8s" % ("#", "true", "est", "err"))
        lines.append("-" * 34)
        for i in range(len(true)):
            e = est[i] if i < len(est) else float("nan")
            de = errs[i] if errs is not None and i < len(errs) else float("nan")
            lines.append("%-3d %10.2f %10.2f %8.3f" % (i + 1, true[i], e, de))
        if errs is not None:
            lines.append("")
            lines.append("Max error: %.3f deg" % float(np.max(errs)))
            lines.append("RMSE:      %.3f deg" %
                         float(np.sqrt(np.mean(errs ** 2))))
        self.results.delete("1.0", tk.END)
        self.results.insert(tk.END, "\n".join(lines))

    def _draw_plot(self, res):
        self.ax.clear()
        self.ax.plot(res["grid_deg"], res["spectrum_db"], color="#1f5fbf",
                     lw=1.2, label="MUSIC spectrum")
        for a in res["angles_true_deg"]:
            self.ax.axvline(a, color="red", ls="--", lw=1.0)
        self.ax.plot(res["angles_est_deg"],
                     np.zeros_like(res["angles_est_deg"]) + 1.0,
                     "kv", ms=8, label="Estimated DOA")
        self.ax.axvline(res["angles_true_deg"][0], color="red", ls="--", lw=1.0,
                        label="True DOA")
        self.ax.set_xlim(-90, 90)
        self.ax.set_xlabel("Angle (degrees)")
        self.ax.set_ylabel("Normalized MUSIC spectrum (dB)")
        self.ax.set_title("Coarray MUSIC  -  Eng. Ahmed Majed")
        self.ax.grid(True, alpha=0.3)
        self.ax.legend(loc="lower center", fontsize=8)
        self.fig.tight_layout()
        self.canvas.draw()


def main():
    app = DoaApp()
    app.mainloop()


if __name__ == "__main__":
    main()
