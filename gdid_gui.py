"""
GDID F!K - Windows Global Device ID Toolkit (GUI)
===================================================

Reads the persistent Windows "Global Device ID" (GDID) and offers
manipulation/disable options for a controlled test environment.
Liest die persistente Windows "Global Device ID" (GDID) aus und bietet
Manipulations-/Deaktivierungsoptionen fuer eine kontrollierte Testumgebung.

IMPORTANT / WICHTIG - only use on your own test systems / VMs:
  - Changing or deleting the LID can break Microsoft Account sign-in,
    Windows activation and Microsoft Store apps.
  - Disabling wlidsvc prevents (re-)creation and transmission of the
    GDID, but also disables everything that service provides (MSA
    sign-in, some Store features).
  - Every change is backed up automatically (JSON file in the tool
    folder) before it is applied, so it can be undone.

Known locations (as of July 2026):
  HKCU\\SOFTWARE\\Microsoft\\IdentityCRL\\ExtendedProperties  -> LID
  HKLM\\SOFTWARE\\Microsoft\\IdentityStore                    -> DeviceId, LID
  HKLM\\SOFTWARE\\Microsoft\\IdentityCRL\\NegativeCache        -> Token scopes
  Service: wlidsvc (Microsoft Account Sign-in Assistant)
"""

import ctypes
import json
import os
import re
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

try:
    import winreg
except ImportError:
    winreg = None

APP_TITLE = "GDID F!K - Global Device ID Toolkit"
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")

HKCU_PATH = r"SOFTWARE\Microsoft\IdentityCRL\ExtendedProperties"
HKLM_IDENTITYSTORE = r"SOFTWARE\Microsoft\IdentityStore"
HKLM_NEGATIVECACHE = r"SOFTWARE\Microsoft\IdentityCRL\NegativeCache"
SERVICE_NAME = "wlidsvc"


# --------------------------------------------------------------------------
# Translations / Uebersetzungen
# --------------------------------------------------------------------------

STRINGS = {
    "app_title":            {"de": "GDID F!K - Global Device ID Toolkit", "en": "GDID F!K - Global Device ID Toolkit"},
    "lang_button":          {"de": "English", "en": "Deutsch"},
    "admin_yes":            {"de": "Administrator: JA", "en": "Administrator: YES"},
    "admin_no":             {"de": "Administrator: NEIN (eingeschraenkt)", "en": "Administrator: NO (restricted)"},
    "restart_admin":        {"de": "Als Administrator neu starten", "en": "Restart as administrator"},

    "frame_values":         {"de": "Aktuelle Werte", "en": "Current values"},
    "frame_actions":        {"de": "Aktionen (Testumgebung)", "en": "Actions (test environment)"},
    "frame_log":            {"de": "Protokoll", "en": "Log"},

    "row_lid":               {"de": "LID (HKCU, Hex):", "en": "LID (HKCU, hex):"},
    "row_gdid":              {"de": "GDID (abgeleitet, Dezimal):", "en": "GDID (derived, decimal):"},
    "row_hklm_deviceid":     {"de": "DeviceId (HKLM\\IdentityStore):", "en": "DeviceId (HKLM\\IdentityStore):"},
    "row_hklm_lid":          {"de": "LID (HKLM\\IdentityStore):", "en": "LID (HKLM\\IdentityStore):"},
    "row_service_state":     {"de": "Dienst wlidsvc - Status:", "en": "Service wlidsvc - status:"},
    "row_service_start":     {"de": "Dienst wlidsvc - Starttyp:", "en": "Service wlidsvc - start type:"},

    "btn_refresh":           {"de": "Aktualisieren", "en": "Refresh"},
    "btn_backup":            {"de": "1) Backup aller Werte erstellen", "en": "1) Create backup of all values"},
    "btn_randomize":         {"de": "2) LID zufaellig neu setzen (Manipulation)", "en": "2) Randomize LID (manipulation)"},
    "btn_delete":            {"de": "3) LID loeschen", "en": "3) Delete LID"},
    "btn_restore":           {"de": "4) Aus Backup wiederherstellen", "en": "4) Restore from backup"},
    "btn_disable_service":   {"de": "5) wlidsvc deaktivieren + stoppen", "en": "5) Disable + stop wlidsvc"},
    "btn_enable_service":    {"de": "6) wlidsvc wieder aktivieren (manuell)", "en": "6) Re-enable wlidsvc (manual)"},
    "btn_open_regedit":      {"de": "7) Registry-Ort in regedit oeffnen", "en": "7) Open location in regedit"},
    "btn_export_log":        {"de": "8) Log exportieren", "en": "8) Export log"},

    "warning_text": {
        "de": ("Hinweis: Punkte 2, 3, 5 veraendern Systemzustand. Vor jeder Aenderung wird automatisch\n"
               "ein Backup erstellt. Deaktivieren von wlidsvc kann Anmeldung mit Microsoft-Konto, Store\n"
               "und Aktivierung beeintraechtigen. Nur auf eigenen Test-/VM-Systemen verwenden."),
        "en": ("Note: Items 2, 3, 5 change system state. A backup is created automatically before\n"
               "every change. Disabling wlidsvc can break Microsoft Account sign-in, the Store and\n"
               "activation. Only use on your own test/VM systems.")
    },

    "not_found":             {"de": "(nicht gefunden)", "en": "(not found)"},
    "not_derivable":         {"de": "(nicht ableitbar)", "en": "(not derivable)"},
    "unknown":                {"de": "UNBEKANNT", "en": "UNKNOWN"},
    "unknown_missing":       {"de": "UNBEKANNT / NICHT VORHANDEN", "en": "UNKNOWN / NOT PRESENT"},

    "log_values_refreshed":  {"de": "Werte aktualisiert.", "en": "Values refreshed."},
    "log_backup_saved":      {"de": "Backup gespeichert: {path}", "en": "Backup saved: {path}"},
    "msg_backup_saved":      {"de": "Backup gespeichert unter:\n{path}", "en": "Backup saved to:\n{path}"},

    "confirm_randomize": {
        "de": ("Die LID wird durch einen zufaelligen Wert ersetzt (nur HKCU, aktueller Benutzer).\n"
               "Ein Backup wird vorher automatisch erstellt.\n\nFortfahren?"),
        "en": ("The LID will be replaced with a random value (HKCU only, current user).\n"
               "A backup is created automatically beforehand.\n\nContinue?")
    },
    "log_lid_set":            {"de": "LID (HKCU) neu gesetzt: {hex} -> GDID g{dec}", "en": "LID (HKCU) set: {hex} -> GDID g{dec}"},
    "msg_lid_set": {
        "de": "Neue LID gesetzt. Ein Neustart/Neuanmeldung kann noetig sein,\ndamit alle Dienste den neuen Wert uebernehmen.",
        "en": "New LID set. A restart/re-sign-in may be required for\nall services to pick up the new value."
    },
    "err_write":              {"de": "Fehler beim Schreiben: {err}", "en": "Error while writing: {err}"},
    "log_err_set_lid":        {"de": "FEHLER beim Setzen der LID: {err}", "en": "ERROR while setting LID: {err}"},

    "confirm_delete": {
        "de": "Die LID (HKCU) wird geloescht. Ein Backup wird vorher erstellt.\n\nFortfahren?",
        "en": "The LID (HKCU) will be deleted. A backup is created beforehand.\n\nContinue?"
    },
    "log_lid_deleted":        {"de": "LID (HKCU) geloescht.", "en": "LID (HKCU) deleted."},
    "log_lid_already_gone":   {"de": "LID war bereits nicht vorhanden.", "en": "LID was already absent."},
    "err_delete":              {"de": "Fehler beim Loeschen: {err}", "en": "Error while deleting: {err}"},
    "log_err_delete_lid":     {"de": "FEHLER beim Loeschen der LID: {err}", "en": "ERROR while deleting LID: {err}"},

    "dlg_choose_backup":      {"de": "Backup auswaehlen", "en": "Choose backup"},
    "filetype_backup":        {"de": "GDID Backup JSON", "en": "GDID backup JSON"},
    "err_backup_read":        {"de": "Backup konnte nicht gelesen werden: {err}", "en": "Backup could not be read: {err}"},
    "confirm_restore":        {"de": "Werte aus\n{name}\nwiederherstellen?", "en": "Restore values from\n{name}?"},
    "log_restored":           {"de": "Werte aus Backup wiederhergestellt: {path}", "en": "Values restored from backup: {path}"},
    "msg_restore_done":       {"de": "Wiederherstellung abgeschlossen.", "en": "Restore completed."},
    "err_restore":            {"de": "Fehler bei Wiederherstellung: {err}", "en": "Error during restore: {err}"},
    "log_err_restore":        {"de": "FEHLER bei Wiederherstellung: {err}", "en": "ERROR during restore: {err}"},

    "need_admin": {
        "de": "Dafuer werden Administratorrechte benoetigt.\nBitte zuerst 'Als Administrator neu starten' klicken.",
        "en": "Administrator rights are required for this.\nPlease click 'Restart as administrator' first."
    },
    "confirm_disable_service": {
        "de": ("Der Dienst 'wlidsvc' (Microsoft Account Sign-in Assistant) wird gestoppt und\n"
               "auf 'Deaktiviert' gesetzt. Dadurch kann keine neue GDID mehr erzeugt/uebermittelt\n"
               "werden - aber die Anmeldung mit einem Microsoft-Konto funktioniert dann nicht mehr.\n\n"
               "Ein Backup wird vorher erstellt. Fortfahren?"),
        "en": ("The 'wlidsvc' service (Microsoft Account Sign-in Assistant) will be stopped and\n"
               "set to 'Disabled'. This prevents any new GDID from being generated/transmitted -\n"
               "but Microsoft Account sign-in will stop working.\n\n"
               "A backup is created beforehand. Continue?")
    },
    "log_sc_config":          {"de": "sc config disabled -> rc={rc}: {out}", "en": "sc config disabled -> rc={rc}: {out}"},
    "log_sc_stop":            {"de": "sc stop -> rc={rc}: {out}", "en": "sc stop -> rc={rc}: {out}"},
    "msg_commands_executed":  {"de": "Befehle ausgefuehrt. Status siehe Protokoll / Aktualisieren-Button.", "en": "Commands executed. See log / Refresh button for status."},

    "log_sc_config_demand":   {"de": "sc config demand -> rc={rc}: {out}", "en": "sc config demand -> rc={rc}: {out}"},
    "log_sc_start":           {"de": "sc start -> rc={rc}: {out}", "en": "sc start -> rc={rc}: {out}"},
    "msg_service_enabled":    {"de": "Dienst wieder auf manuellen Start gesetzt und gestartet (falls moeglich).", "en": "Service set back to manual start and started (if possible)."},

    "log_regedit_opened":     {"de": "regedit geoeffnet (letzte Position gesetzt).", "en": "regedit opened (jump location set)."},
    "err_regedit":            {"de": "regedit konnte nicht geoeffnet werden: {err}", "en": "regedit could not be opened: {err}"},

    "dlg_save_log":           {"de": "Protokoll speichern", "en": "Save log"},
    "filetype_text":          {"de": "Textdatei", "en": "Text file"},
    "msg_log_saved":          {"de": "Protokoll gespeichert unter:\n{path}", "en": "Log saved to:\n{path}"},
}

LANGUAGES = ["de", "en"]


def t(key, lang, **kwargs):
    entry = STRINGS.get(key, {})
    text = entry.get(lang, entry.get("de", key))
    if kwargs:
        text = text.format(**kwargs)
    return text


# --------------------------------------------------------------------------
# Hilfsfunktionen / helpers (Registry / Dienst / Rechte)
# --------------------------------------------------------------------------

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def relaunch_as_admin():
    params = " ".join(f'"{a}"' for a in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, f'"{os.path.abspath(__file__)}" {params}', None, 1
    )


def read_value(hive, subkey, name):
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return value
    except FileNotFoundError:
        return None
    except OSError:
        return None


def write_value(hive, subkey, name, value, value_type=None):
    if winreg is None:
        raise RuntimeError("winreg not available (not Windows?)")
    if value_type is None:
        value_type = winreg.REG_SZ
    with winreg.CreateKeyEx(hive, subkey, 0, winreg.KEY_WRITE) as key:
        winreg.SetValueEx(key, name, 0, value_type, value)


def delete_value(hive, subkey, name):
    if winreg is None:
        raise RuntimeError("winreg not available (not Windows?)")
    try:
        with winreg.OpenKey(hive, subkey, 0, winreg.KEY_WRITE) as key:
            winreg.DeleteValue(key, name)
        return True
    except FileNotFoundError:
        return False


def hex_lid_to_gdid(lid_hex: str):
    if not lid_hex or not re.match(r"^[0-9A-Fa-f]{16}$", lid_hex):
        return None
    return "g" + str(int(lid_hex, 16))


def random_lid_hex() -> str:
    return os.urandom(8).hex().upper()


def run_sc_command(args):
    """Runs an sc.exe command and returns (returncode, output)."""
    try:
        result = subprocess.run(
            ["sc.exe"] + args,
            capture_output=True, text=True, timeout=15,
            encoding="cp850", errors="replace"
        )
        return result.returncode, (result.stdout + result.stderr).strip()
    except Exception as e:
        return -1, str(e)


def get_service_state(lang="de"):
    rc, out = run_sc_command(["query", SERVICE_NAME])
    if rc != 0:
        return t("unknown_missing", lang)
    m = re.search(r"STATE\s*:\s*\d+\s+(\w+)", out)
    return m.group(1) if m else t("unknown", lang)


def get_service_start_type(lang="de"):
    rc, out = run_sc_command(["qc", SERVICE_NAME])
    if rc != 0:
        return t("unknown", lang)
    m = re.search(r"START_TYPE\s*:\s*\d+\s+(\w+)", out)
    return m.group(1) if m else t("unknown", lang)


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------

class GdidApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.lang = "en"
        self.title(APP_TITLE)
        self.geometry("880x660")
        self.minsize(760, 580)

        os.makedirs(BACKUP_DIR, exist_ok=True)

        self._build_style()
        self._build_layout()
        self.refresh_all()

    # ---- UI Aufbau / UI setup ------------------------------------------

    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("Header.TLabel", font=("Segoe UI", 13, "bold"))
        style.configure("Value.TLabel", font=("Consolas", 11))
        style.configure("Warn.TLabel", foreground="#b30000")
        style.configure("Ok.TLabel", foreground="#0a7d0a")

    def _build_layout(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        self.header_label = ttk.Label(top, text=APP_TITLE, style="Header.TLabel")
        self.header_label.pack(side="left")

        self.lang_button = ttk.Button(top, text="", command=self.toggle_language)
        self.lang_button.pack(side="right", padx=8)

        self.admin_label = ttk.Label(top, text="")
        self.admin_label.pack(side="right", padx=8)

        self.admin_btn = None
        if not is_admin():
            self.admin_btn = ttk.Button(top, text="", command=relaunch_as_admin)
            self.admin_btn.pack(side="right", padx=8)

        # --- Anzeige-Bereich / values frame ---
        self.info_frame = ttk.LabelFrame(self, text="", padding=10)
        self.info_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.vars = {
            "lid": tk.StringVar(value="-"),
            "gdid": tk.StringVar(value="-"),
            "hklm_deviceid": tk.StringVar(value="-"),
            "hklm_lid": tk.StringVar(value="-"),
            "service_state": tk.StringVar(value="-"),
            "service_start": tk.StringVar(value="-"),
        }

        self.row_keys = [
            "row_lid", "row_gdid", "row_hklm_deviceid",
            "row_hklm_lid", "row_service_state", "row_service_start",
        ]
        row_value_keys = ["lid", "gdid", "hklm_deviceid", "hklm_lid", "service_state", "service_start"]

        self.row_labels = []
        for i, (label_key, value_key) in enumerate(zip(self.row_keys, row_value_keys)):
            lbl = ttk.Label(self.info_frame, text="")
            lbl.grid(row=i, column=0, sticky="w", pady=2)
            self.row_labels.append(lbl)
            ttk.Label(self.info_frame, textvariable=self.vars[value_key], style="Value.TLabel").grid(
                row=i, column=1, sticky="w", padx=10, pady=2)

        self.refresh_btn = ttk.Button(self.info_frame, text="", command=self.refresh_all)
        self.refresh_btn.grid(row=0, column=2, rowspan=2, padx=10)

        # --- Aktionen / actions ---
        self.actions_frame = ttk.LabelFrame(self, text="", padding=10)
        self.actions_frame.pack(fill="x", padx=10, pady=(0, 10))

        btn_opts = {"width": 38}
        grid_opts = {"padx": 5, "pady": 5}

        self.action_buttons = {}
        specs = [
            ("btn_backup", self.action_backup, 0, 0),
            ("btn_randomize", self.action_randomize, 0, 1),
            ("btn_delete", self.action_delete_lid, 1, 0),
            ("btn_restore", self.action_restore, 1, 1),
            ("btn_disable_service", self.action_disable_service, 2, 0),
            ("btn_enable_service", self.action_enable_service, 2, 1),
            ("btn_open_regedit", self.action_open_regedit, 3, 0),
            ("btn_export_log", self.action_export_log, 3, 1),
        ]
        for key, cmd, row, col in specs:
            btn = ttk.Button(self.actions_frame, text="", command=cmd, **btn_opts)
            btn.grid(row=row, column=col, **grid_opts)
            self.action_buttons[key] = btn

        self.warn_label = ttk.Label(self, text="", style="Warn.TLabel", justify="left")
        self.warn_label.pack(fill="x", padx=14)

        # --- Log ---
        self.log_frame = ttk.LabelFrame(self, text="", padding=6)
        self.log_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.log_text = tk.Text(self.log_frame, height=10, font=("Consolas", 9), state="disabled")
        self.log_text.pack(fill="both", expand=True, side="left")
        scroll = ttk.Scrollbar(self.log_frame, command=self.log_text.yview)
        scroll.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scroll.set)

        self._apply_language()

    # ---- Sprache / language ---------------------------------------------

    def toggle_language(self):
        idx = LANGUAGES.index(self.lang)
        self.lang = LANGUAGES[(idx + 1) % len(LANGUAGES)]
        self._apply_language()
        self.refresh_all()

    def _apply_language(self):
        lang = self.lang
        self.header_label.configure(text=t("app_title", lang))
        self.lang_button.configure(text=t("lang_button", lang))
        if self.admin_btn is not None:
            self.admin_btn.configure(text=t("restart_admin", lang))

        self.info_frame.configure(text=t("frame_values", lang))
        for lbl, key in zip(self.row_labels, self.row_keys):
            lbl.configure(text=t(key, lang))
        self.refresh_btn.configure(text=t("btn_refresh", lang))

        self.actions_frame.configure(text=t("frame_actions", lang))
        for key, btn in self.action_buttons.items():
            btn.configure(text=t(key, lang))

        self.warn_label.configure(text=t("warning_text", lang))
        self.log_frame.configure(text=t("frame_log", lang))

        self.admin_label.configure(
            text=(t("admin_yes", lang) if is_admin() else t("admin_no", lang)),
            style="Ok.TLabel" if is_admin() else "Warn.TLabel"
        )

    # ---- Logging -------------------------------------------------------

    def log(self, message: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{ts}] {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # ---- Datenaktualisierung / data refresh -----------------------------

    def refresh_all(self):
        lang = self.lang
        self.admin_label.configure(
            text=(t("admin_yes", lang) if is_admin() else t("admin_no", lang)),
            style="Ok.TLabel" if is_admin() else "Warn.TLabel"
        )

        lid = read_value(winreg.HKEY_CURRENT_USER, HKCU_PATH, "LID") if winreg else None
        self.vars["lid"].set(lid or t("not_found", lang))
        gdid = hex_lid_to_gdid(lid) if lid else None
        self.vars["gdid"].set(gdid or t("not_derivable", lang))

        hklm_deviceid = read_value(winreg.HKEY_LOCAL_MACHINE, HKLM_IDENTITYSTORE, "DeviceId") if winreg else None
        hklm_lid = read_value(winreg.HKEY_LOCAL_MACHINE, HKLM_IDENTITYSTORE, "LID") if winreg else None
        self.vars["hklm_deviceid"].set(hklm_deviceid or t("not_found", lang))
        self.vars["hklm_lid"].set(hklm_lid or t("not_found", lang))

        self.vars["service_state"].set(get_service_state(lang))
        self.vars["service_start"].set(get_service_start_type(lang))

        self.log(t("log_values_refreshed", lang))

    # ---- Aktionen / actions ----------------------------------------------

    def _current_snapshot(self):
        return {
            "timestamp": datetime.now().isoformat(),
            "HKCU_LID": read_value(winreg.HKEY_CURRENT_USER, HKCU_PATH, "LID"),
            "HKLM_DeviceId": read_value(winreg.HKEY_LOCAL_MACHINE, HKLM_IDENTITYSTORE, "DeviceId"),
            "HKLM_LID": read_value(winreg.HKEY_LOCAL_MACHINE, HKLM_IDENTITYSTORE, "LID"),
            "service_start_type": get_service_start_type(self.lang),
        }

    def action_backup(self, silent=False):
        lang = self.lang
        snap = self._current_snapshot()
        fname = f"gdid_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path = os.path.join(BACKUP_DIR, fname)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snap, f, indent=2, ensure_ascii=False)
        self.log(t("log_backup_saved", lang, path=path))
        if not silent:
            messagebox.showinfo(APP_TITLE, t("msg_backup_saved", lang, path=path))
        return path

    def action_randomize(self):
        lang = self.lang
        if not messagebox.askyesno(APP_TITLE, t("confirm_randomize", lang)):
            return
        self.action_backup(silent=True)
        new_hex = random_lid_hex()
        try:
            write_value(winreg.HKEY_CURRENT_USER, HKCU_PATH, "LID", new_hex, winreg.REG_SZ)
            self.log(t("log_lid_set", lang, hex=new_hex, dec=int(new_hex, 16)))
            messagebox.showinfo(APP_TITLE, t("msg_lid_set", lang))
        except Exception as e:
            messagebox.showerror(APP_TITLE, t("err_write", lang, err=e))
            self.log(t("log_err_set_lid", lang, err=e))
        self.refresh_all()

    def action_delete_lid(self):
        lang = self.lang
        if not messagebox.askyesno(APP_TITLE, t("confirm_delete", lang)):
            return
        self.action_backup(silent=True)
        try:
            removed = delete_value(winreg.HKEY_CURRENT_USER, HKCU_PATH, "LID")
            self.log(t("log_lid_deleted", lang) if removed else t("log_lid_already_gone", lang))
        except Exception as e:
            messagebox.showerror(APP_TITLE, t("err_delete", lang, err=e))
            self.log(t("log_err_delete_lid", lang, err=e))
        self.refresh_all()

    def action_restore(self):
        lang = self.lang
        path = filedialog.askopenfilename(
            title=t("dlg_choose_backup", lang), initialdir=BACKUP_DIR,
            filetypes=[(t("filetype_backup", lang), "*.json")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                snap = json.load(f)
        except Exception as e:
            messagebox.showerror(APP_TITLE, t("err_backup_read", lang, err=e))
            return

        if not messagebox.askyesno(APP_TITLE, t("confirm_restore", lang, name=os.path.basename(path))):
            return

        try:
            if snap.get("HKCU_LID"):
                write_value(winreg.HKEY_CURRENT_USER, HKCU_PATH, "LID", snap["HKCU_LID"], winreg.REG_SZ)
            if snap.get("HKLM_DeviceId") and is_admin():
                write_value(winreg.HKEY_LOCAL_MACHINE, HKLM_IDENTITYSTORE, "DeviceId", snap["HKLM_DeviceId"], winreg.REG_SZ)
            if snap.get("HKLM_LID") and is_admin():
                write_value(winreg.HKEY_LOCAL_MACHINE, HKLM_IDENTITYSTORE, "LID", snap["HKLM_LID"], winreg.REG_SZ)
            self.log(t("log_restored", lang, path=path))
            messagebox.showinfo(APP_TITLE, t("msg_restore_done", lang))
        except Exception as e:
            messagebox.showerror(APP_TITLE, t("err_restore", lang, err=e))
            self.log(t("log_err_restore", lang, err=e))
        self.refresh_all()

    def action_disable_service(self):
        lang = self.lang
        if not is_admin():
            messagebox.showwarning(APP_TITLE, t("need_admin", lang))
            return
        if not messagebox.askyesno(APP_TITLE, t("confirm_disable_service", lang)):
            return
        self.action_backup(silent=True)
        rc1, out1 = run_sc_command(["config", SERVICE_NAME, "start=", "disabled"])
        rc2, out2 = run_sc_command(["stop", SERVICE_NAME])
        self.log(t("log_sc_config", lang, rc=rc1, out=out1))
        self.log(t("log_sc_stop", lang, rc=rc2, out=out2))
        messagebox.showinfo(APP_TITLE, t("msg_commands_executed", lang))
        self.refresh_all()

    def action_enable_service(self):
        lang = self.lang
        if not is_admin():
            messagebox.showwarning(APP_TITLE, t("need_admin", lang))
            return
        rc1, out1 = run_sc_command(["config", SERVICE_NAME, "start=", "demand"])
        rc2, out2 = run_sc_command(["start", SERVICE_NAME])
        self.log(t("log_sc_config_demand", lang, rc=rc1, out=out1))
        self.log(t("log_sc_start", lang, rc=rc2, out=out2))
        messagebox.showinfo(APP_TITLE, t("msg_service_enabled", lang))
        self.refresh_all()

    def action_open_regedit(self):
        lang = self.lang
        try:
            subprocess.Popen([
                "reg.exe", "add",
                r"HKCU\Software\Microsoft\Windows\CurrentVersion\Applets\Regedit",
                "/v", "LastKey", "/d",
                rf"HKEY_CURRENT_USER\{HKCU_PATH}", "/f"
            ], shell=False)
            subprocess.Popen(["regedit.exe"])
            self.log(t("log_regedit_opened", lang))
        except Exception as e:
            messagebox.showerror(APP_TITLE, t("err_regedit", lang, err=e))

    def action_export_log(self):
        lang = self.lang
        path = filedialog.asksaveasfilename(
            title=t("dlg_save_log", lang), initialdir=BACKUP_DIR,
            defaultextension=".txt", filetypes=[(t("filetype_text", lang), "*.txt")]
        )
        if not path:
            return
        content = self.log_text.get("1.0", "end")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        messagebox.showinfo(APP_TITLE, t("msg_log_saved", lang, path=path))


def main():
    if os.name != "nt":
        print("This tool only works on Windows. / Dieses Tool funktioniert nur unter Windows.")
        sys.exit(1)
    app = GdidApp()
    app.mainloop()


if __name__ == "__main__":
    main()
