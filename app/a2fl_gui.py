# -*- coding: utf-8 -*-
"""Audio2FL - Liquid Glass GUI with i18n (zh / en / ja / ko)"""
from __future__ import annotations

import ctypes
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.i18n import LANG_NAMES, get_i18n

COL = {
    "bg":         "#0B0F1A",
    "card":       "#161C2E",
    "card_hi":    "#1E263C",
    "border":     "#2E3A56",
    "primary":    "#5B8DEF",
    "primary_hi": "#7BA5FF",
    "success":    "#3DD68C",
    "warn":       "#FFB020",
    "error":      "#FF5C5C",
    "text":       "#EEF2FA",
    "muted":      "#9AA3B8",
    "dim":        "#5C657A",
}

FONT_TITLE = ("Microsoft YaHei UI", 22, "bold")
FONT_BOLD  = ("Microsoft YaHei UI", 15, "bold")
FONT_SM    = ("Microsoft YaHei UI", 12)
FONT_MONO  = ("Consolas", 10)


def enable_acrylic(hwnd: int, tint: int = 0xF00B0F1A) -> bool:
    try:
        class AP(ctypes.Structure):
            _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int),
                        ("GradientColor", ctypes.c_uint), ("AnimationId", ctypes.c_int)]
        class WD(ctypes.Structure):
            _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.POINTER(AP)),
                        ("SizeOfData", ctypes.c_size_t)]
        a = AP(); a.AccentState = 4; a.AccentFlags = 2; a.GradientColor = tint
        d = WD(); d.Attribute = 19; d.SizeOfData = ctypes.sizeof(a); d.Data = ctypes.pointer(a)
        return bool(ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(d)))
    except Exception:
        return False


def dark_titlebar(hwnd: int) -> None:
    try:
        v = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(v), ctypes.sizeof(v))
    except Exception:
        pass


def abgr(hexcolor: str, alpha: int = 0xE0) -> int:
    h = hexcolor.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (alpha << 24) | (b << 16) | (g << 8) | r


class Card(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=COL["card"], corner_radius=14,
                         border_width=1, border_color=COL["border"], **kw)


class App(ctk.CTk):
    def __init__(self, audio=None, lang=None):
        ctk.set_appearance_mode("dark")
        super().__init__()

        self.i18n = get_i18n(lang)
        self._busy = False
        self._t0 = 0.0
        self._cancel = False
        self._files: list[str] = []

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w = min(920, sw - 80)
        h = min(700, sh - 90)
        self.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, max(0, (sh - h) // 2 - 20)))
        self.minsize(820, 600)
        self.configure(fg_color=COL["bg"])

        self.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
        dark_titlebar(hwnd)
        enable_acrylic(hwnd, tint=abgr("#0B0F1A", 0xF0))

        self._build()
        self._load_templates()
        self._retranslate()

        if audio:
            self.v_audio.set(audio)

        # 先让窗口真正画出来，再撤掉启动画面，避免出现空白
        self.update_idletasks()
        self.update()
        self.after(120, self._dismiss_splash)

    # ------------------------------------------------------------------
    def _dismiss_splash(self):
        """关闭 PyInstaller --splash 启动画面。

        必须显式调用，否则那层画面会一直停在桌面上。
        """
        try:
            import pyi_splash  # type: ignore
            pyi_splash.close()
        except Exception:
            pass

    def _build(self):
        self.grid_rowconfigure(4, weight=1)
        self.grid_columnconfigure(0, weight=1)
        pad = {"padx": 20}

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", pady=(14, 8), **pad)
        head.grid_columnconfigure(1, weight=1)

        self.lbl_title = ctk.CTkLabel(head, text="Audio2FL", font=FONT_TITLE,
                                      text_color=COL["text"])
        self.lbl_title.grid(row=0, column=0, sticky="w")

        self.lbl_sub = ctk.CTkLabel(head, text="", font=FONT_SM, text_color=COL["muted"])
        self.lbl_sub.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=(6, 0))

        self.opt_lang = ctk.CTkOptionMenu(
            head, values=[LANG_NAMES[c] for c in self.i18n.available],
            width=110, height=30, corner_radius=8, font=FONT_SM,
            fg_color=COL["card_hi"], button_color=COL["border"],
            button_hover_color=COL["primary"], text_color=COL["text"],
            dropdown_fg_color=COL["card"], dropdown_text_color=COL["text"],
            dropdown_hover_color=COL["primary"], command=self._on_lang_change)
        self.opt_lang.grid(row=0, column=2, sticky="e")
        self.opt_lang.set(self.i18n.name())

        # 语言变了，模板显示名也要跟着变
        if hasattr(self, "tpl_menu"):
            self._load_templates()

        c1 = Card(self)
        c1.grid(row=1, column=0, sticky="ew", pady=(0, 10), **pad)
        c1.grid_columnconfigure(1, weight=1)

        self.v_audio = tk.StringVar()
        self.v_out = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Music", "Audio2FL"))
        self.v_tpl = tk.StringVar()

        self._file_rows = []
        self._row_btns = []
        for r, (key, var, cmd) in enumerate([
            ("lbl_audio",    self.v_audio, self._pick_audio),
            ("lbl_outdir",   self.v_out,   self._pick_out),
            ("lbl_template", self.v_tpl,   self._pick_tpl),
        ]):
            lb = ctk.CTkLabel(c1, text="", font=FONT_SM, text_color=COL["muted"],
                              width=76, anchor="w")
            lb.grid(row=r, column=0, padx=(16, 6), pady=7, sticky="w")
            en = ctk.CTkEntry(c1, textvariable=var, height=34, corner_radius=8,
                              fg_color=COL["card_hi"], border_color=COL["border"],
                              text_color=COL["text"], font=FONT_SM)
            en.grid(row=r, column=1, sticky="ew", pady=7)
            bt = ctk.CTkButton(c1, text="", command=cmd, width=62, height=34, corner_radius=8,
                               fg_color=COL["card_hi"], hover_color=COL["border"],
                               text_color=COL["text"], font=FONT_SM,
                               border_width=1, border_color=COL["border"])
            bt.grid(row=r, column=2, padx=(6, 4), pady=7)
            self._file_rows.append((key, lb, bt))
            self._row_btns.append(bt)
            if key == "lbl_template":
                # 模板行额外加一个下拉框
                bt.grid_remove()
                self.tpl_menu = ctk.CTkOptionMenu(
                    c1, values=["—"], width=170, height=34, corner_radius=8, font=FONT_SM,
                    fg_color=COL["card_hi"], button_color=COL["border"],
                    button_hover_color=COL["primary"], text_color=COL["text"],
                    dropdown_fg_color=COL["card"], dropdown_text_color=COL["text"],
                    dropdown_hover_color=COL["primary"], command=self._on_tpl_change)
                self.tpl_menu.grid(row=r, column=2, padx=(6, 4), pady=7)
                bt.grid(row=r, column=3, padx=(0, 16), pady=7)
                self._tpl_map = {}
            if key == "lbl_audio":
                self.btn_folder = ctk.CTkButton(
                    c1, text="", command=self._pick_folder, width=76, height=34,
                    corner_radius=8, fg_color=COL["card_hi"], hover_color=COL["primary"],
                    text_color=COL["text"], font=FONT_SM,
                    border_width=1, border_color=COL["border"])
                self.btn_folder.grid(row=r, column=3, padx=(0, 16), pady=7)
                c1.grid_columnconfigure(2, weight=0)

        c2 = Card(self)
        c2.grid(row=2, column=0, sticky="ew", pady=(0, 10), **pad)
        opt = ctk.CTkFrame(c2, fg_color="transparent")
        opt.pack(fill="x", padx=16, pady=11)

        self.v_flp = tk.BooleanVar(value=True)
        self.v_mid = tk.BooleanVar(value=True)
        self.v_drum = tk.BooleanVar(value=True)
        self.v_bpm = tk.StringVar()

        self._checks = []
        self.v_hq = tk.BooleanVar(value=False)
        for key, var in (("opt_flp", self.v_flp), ("opt_mid", self.v_mid),
                         ("opt_drums", self.v_drum), ("opt_hq", self.v_hq)):
            cb = ctk.CTkCheckBox(opt, text="", variable=var, font=FONT_SM,
                                 text_color=COL["text"], fg_color=COL["primary"],
                                 hover_color=COL["primary_hi"], border_color=COL["border"],
                                 corner_radius=5, checkbox_width=18, checkbox_height=18)
            cb.pack(side="left", padx=(0, 18))
            self._checks.append((key, cb))

        self.lbl_bpm = ctk.CTkLabel(opt, text="BPM", font=FONT_SM, text_color=COL["muted"])
        self.lbl_bpm.pack(side="left", padx=(14, 5))
        ctk.CTkEntry(opt, textvariable=self.v_bpm, width=70, height=30, corner_radius=8,
                     fg_color=COL["card_hi"], border_color=COL["border"],
                     text_color=COL["text"], font=FONT_SM).pack(side="left")
        self.lbl_bpm_hint = ctk.CTkLabel(opt, text="", font=FONT_SM, text_color=COL["dim"])
        self.lbl_bpm_hint.pack(side="left", padx=(6, 0))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=3, column=0, sticky="ew", pady=(0, 8), **pad)
        bar.grid_columnconfigure(0, weight=1)

        btnrow = ctk.CTkFrame(bar, fg_color="transparent")
        btnrow.grid(row=0, column=0, sticky="ew")
        btnrow.grid_columnconfigure(0, weight=1)

        self.btn = ctk.CTkButton(btnrow, text="", command=self._run,
                                 height=46, corner_radius=12, font=FONT_BOLD,
                                 fg_color=COL["primary"], hover_color=COL["primary_hi"],
                                 text_color="#FFFFFF")
        self.btn.grid(row=0, column=0, sticky="ew")

        self.btn_cancel = ctk.CTkButton(btnrow, text="", command=self._do_cancel,
                                        width=96, height=46, corner_radius=12, font=FONT_BOLD,
                                        fg_color=COL["card_hi"], hover_color=COL["error"],
                                        text_color=COL["text"],
                                        border_width=1, border_color=COL["border"],
                                        state="disabled")
        self.btn_cancel.grid(row=0, column=1, padx=(8, 0), sticky="e")

        self.pbar = ctk.CTkProgressBar(bar, height=5, corner_radius=3,
                                       fg_color=COL["card"], progress_color=COL["primary"])
        self.pbar.grid(row=1, column=0, sticky="ew", pady=(8, 3))
        self.pbar.set(0)

        self.lbl = ctk.CTkLabel(bar, text="", font=FONT_SM, text_color=COL["muted"], anchor="w")
        self.lbl.grid(row=2, column=0, sticky="w")

        c3 = Card(self)
        c3.grid(row=4, column=0, sticky="nsew", pady=(0, 10), **pad)
        c3.grid_rowconfigure(0, weight=1)
        c3.grid_columnconfigure(0, weight=1)

        self.log = ctk.CTkTextbox(c3, font=FONT_MONO, fg_color="#070A12",
                                  text_color=COL["text"], corner_radius=10,
                                  border_width=1, border_color=COL["border"], wrap="word")
        self.log.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.log.configure(state="disabled")
        self.log.tag_config("ok", foreground=COL["success"])
        self.log.tag_config("err", foreground=COL["error"])
        self.log.tag_config("info", foreground=COL["muted"])
        self.log.tag_config("hi", foreground=COL["primary_hi"])

        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.grid(row=5, column=0, sticky="ew", pady=(0, 12), **pad)

        self.btn_out = ctk.CTkButton(foot, text="", command=self._open_out,
                                     width=124, height=32, corner_radius=8, font=FONT_SM,
                                     fg_color=COL["card_hi"], hover_color=COL["border"],
                                     text_color=COL["text"], border_width=1, border_color=COL["border"])
        self.btn_out.pack(side="left")
        self.lbl_drag = ctk.CTkLabel(foot, text="", font=FONT_SM, text_color=COL["dim"])
        self.lbl_drag.pack(side="right")

    # ------------------------------------------------------------------
    def _retranslate(self):
        t = self.i18n.t
        self.title(t("app_title"))
        self.lbl_sub.configure(text=t("app_subtitle"))

        for (key, lb, btn) in self._file_rows:
            lb.configure(text=t(key))
            btn.configure(text=t("btn_browse"))

        for key, cb in self._checks:
            cb.configure(text=t(key))

        self.lbl_bpm_hint.configure(text=t("hint_bpm"))
        self.btn.configure(text=t("btn_running") if self._busy else t("btn_start"))
        self.btn_cancel.configure(text=t("btn_cancel"))
        self.btn_out.configure(text=t("btn_open_out"))
        self.lbl_drag.configure(text=t("hint_drag"))
        if hasattr(self, "btn_folder"):
            self.btn_folder.configure(text=t("btn_pick_dir"))

        if not self._busy:
            self.lbl.configure(text=t("status_ready"), text_color=COL["muted"])

        self.opt_lang.set(self.i18n.name())

    def _on_lang_change(self, name: str):
        for code, nm in self.i18n.all_lang_names():
            if nm == name:
                self.i18n.set(code)
                break
        self._retranslate()
        self._append("— " + name + " —", "info")

    # ------------------------------------------------------------------
    def _pick_audio(self):
        t = self.i18n.t
        p = filedialog.askopenfilename(
            title=t("dlg_pick_audio"),
            filetypes=[(t("ft_audio"), "*.mp3 *.wav *.flac *.ogg"), (t("ft_all"), "*.*")])
        if p:
            self.v_audio.set(p)

    def _load_templates(self):
        """填充模板下拉框。"""
        try:
            from app.toflp.pipeline import list_templates
            found = list_templates()
        except Exception:
            found = []
        self._tpl_map = {}
        vals = []
        t = self.i18n.t
        if found:
            for key, path in found:
                # "@default" 是内置模板的占位键，按当前语言显示
                disp = t("tpl_default") if key == "@default" else key
                # 同名时加后缀避免覆盖
                if disp in self._tpl_map:
                    disp = disp + " 2"
                self._tpl_map[disp] = path
                vals.append(disp)
        else:
            vals = [t("tpl_none")]
        self.tpl_menu.configure(values=vals)
        self.tpl_menu.set(vals[0])
        self.v_tpl.set(found[0][1] if found else "")

    def _on_tpl_change(self, name):
        p = self._tpl_map.get(name, "")
        self.v_tpl.set(p)
        if p:
            self._append(self.i18n.t("lbl_template") + ": " + os.path.basename(p), "info")

    def _pick_folder(self):
        """选文件夹 = 批量模式。"""
        d = filedialog.askdirectory(title=self.i18n.t("dlg_pick_outdir"))
        if not d:
            return
        exts = (".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac")
        found = sorted(
            os.path.join(d, f) for f in os.listdir(d)
            if f.lower().endswith(exts) and os.path.isfile(os.path.join(d, f)))
        if not found:
            messagebox.showinfo(self.i18n.t("info"), self.i18n.t("batch_none"))
            return
        self._files = found
        self.v_audio.set(d)
        self._append(self.i18n.t("batch_hint", n=len(found)), "hi")
        for f in found[:12]:
            self._append("  · " + os.path.basename(f), "info")
        if len(found) > 12:
            self._append("  … +%d" % (len(found) - 12), "info")

    def _do_cancel(self):
        self._cancel = True
        self._append(self.i18n.t("status_cancel"), "err")

    def _pick_out(self):
        p = filedialog.askdirectory(title=self.i18n.t("dlg_pick_outdir"))
        if p:
            self.v_out.set(p)

    def _pick_tpl(self):
        p = filedialog.askopenfilename(
            title=self.i18n.t("dlg_pick_tpl"),
            filetypes=[(self.i18n.t("ft_flp"), "*.flp")])
        if p:
            self.v_tpl.set(p)

    def _open_out(self):
        d = self.v_out.get()
        if d and os.path.isdir(d):
            os.startfile(d)
        else:
            messagebox.showinfo(self.i18n.t("info"), self.i18n.t("err_out_missing"))

    def _append(self, text, tag=None):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    # ------------------------------------------------------------------
    def _run(self):
        t = self.i18n.t
        if self._busy:
            return
        audio = self.v_audio.get().strip()
        if not audio or not os.path.exists(audio):
            messagebox.showwarning(t("err_no_audio_t"), t("err_no_audio"))
            return

        out = self.v_out.get().strip() or os.path.join(os.path.dirname(audio), "Audio2FL_out")
        os.makedirs(out, exist_ok=True)

        bpm = self.v_bpm.get().strip()
        if bpm:
            try:
                float(bpm)
            except ValueError:
                messagebox.showwarning(t("err_bpm_t"), t("err_bpm"))
                return

        targets = list(self._files) if self._files else [audio]
        if os.path.isdir(audio) and not self._files:
            exts = (".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac")
            targets = sorted(
                os.path.join(audio, f) for f in os.listdir(audio)
                if f.lower().endswith(exts) and os.path.isfile(os.path.join(audio, f)))
            if not targets:
                messagebox.showwarning(t("err_no_audio_t"), t("batch_none"))
                return

        self._busy = True
        self._cancel = False
        self._t0 = time.time()
        self.btn.configure(state="disabled", text=t("btn_running"))
        self.btn_cancel.configure(state="normal")
        self.pbar.set(0)
        self._append("─" * 56, "info")
        if len(targets) > 1:
            self._append(t("batch_hint", n=len(targets)), "hi")
        else:
            self._append("%s: %s" % (t("lbl_audio"), targets[0]), "hi")
        self._append("%s: %s" % (t("lbl_outdir"), out), "hi")

        threading.Thread(target=self._worker,
                         args=(targets, out, bpm, self.v_hq.get()),
                         daemon=True).start()

    def _worker(self, targets, out, bpm, hq):
        try:
            from app.toflp.pipeline import Options, run

            tpl = self.v_tpl.get().strip()
            if not tpl:
                roots = [os.path.dirname(sys.executable), os.getcwd()]
                if getattr(sys, "_MEIPASS", None):
                    roots.insert(0, sys._MEIPASS)
                for r in roots:
                    cand = os.path.join(r, "template.flp")
                    if os.path.exists(cand):
                        tpl = cand
                        break

            model_name = "htdemucs_ft" if hq else "htdemucs"
            total = len(targets)
            ok = fail = 0
            last_res = None

            for i, audio in enumerate(targets, 1):
                if self._cancel:
                    break
                name = os.path.basename(audio)
                if total > 1:
                    self.after(0, lambda i=i, n=total, nm=name:
                               self._append(self.i18n.t("pr_batch", i=i, n=n, name=nm), "hi"))

                opts = Options(audio=audio, out_dir=out, template=tpl,
                               make_midi=self.v_mid.get(), make_flp=self.v_flp.get(),
                               make_drums=self.v_drum.get(),
                               bpm_override=float(bpm) if bpm else None,
                               model_name=model_name)

                try:
                    res = run(opts,
                              progress=lambda m, f: self.after(0, lambda m=m, f=f: self._prog(m, f)),
                              cancel=lambda: self._cancel)
                    last_res = res
                    ok += 1
                except Exception as exc:
                    fail += 1
                    self.after(0, lambda e=str(exc): self._append("x " + e, "err"))

            self.after(0, lambda: self._done(last_res, total, ok, fail))
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.after(0, lambda: self._err(str(e), tb))

    def _prog(self, msg, frac):
        t = self.i18n.t
        self.pbar.set(max(0.0, min(1.0, frac)))
        el = time.time() - self._t0
        if frac > 0.05:
            eta = el / frac * (1 - frac)
            tail = "  " + t("status_elapsed", n=int(el)) + " / " + t("status_eta", n=int(eta))
        else:
            tail = "  " + t("status_elapsed", n=int(el))
        self.lbl.configure(text="%.1f%%   %s%s" % (frac * 100, msg, tail), text_color=COL["muted"])
        self._append("[%.1f%%] %s" % (frac * 100, msg))

    def _done(self, res, total=1, ok=1, fail=0):
        t = self.i18n.t
        self.pbar.set(1)
        el = time.time() - self._t0
        if self._cancel:
            self.lbl.configure(text=t("status_cancel"), text_color=COL["warn"])
        elif total > 1:
            self.lbl.configure(text=t("batch_done", ok=ok, fail=fail, n=round(el, 1)),
                               text_color=COL["success"] if fail == 0 else COL["warn"])
            self._append(t("batch_done", ok=ok, fail=fail, n=round(el, 1)),
                         "ok" if fail == 0 else "err")
        else:
            self.lbl.configure(text=t("status_done", n=round(el, 1)), text_color=COL["success"])
        for line in (getattr(res, "log", None) or []):
            self._append(line, "ok")
        self._busy = False
        self._files = []
        self.btn.configure(state="normal", text=t("btn_start"))
        self.btn_cancel.configure(state="disabled")

    def _err(self, msg, tb):
        t = self.i18n.t
        self.lbl.configure(text=t("status_error"), text_color=COL["error"])
        self._append("x " + msg, "err")
        for line in tb.splitlines()[-5:]:
            self._append("  " + line, "err")
        self._busy = False
        self.btn.configure(state="normal", text=t("btn_start"))
        self.btn_cancel.configure(state="disabled")
        messagebox.showerror(t("err_fail"), msg)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    audio = None
    lang = None
    for a in argv:
        low = a.lower()
        if low.startswith("--lang="):
            lang = low.split("=", 1)[1]
        elif low.endswith((".mp3", ".wav", ".flac", ".ogg")) and os.path.exists(a):
            audio = a
    App(audio, lang).mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
