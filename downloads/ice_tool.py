#!/usr/bin/env python3
"""
ICE TOOL
--------
Suite da terminale, menu paginato: [n] pagina successiva, [b] pagina precedente.

Dipendenza obbligatoria: pip install requests
Dipendenze opzionali (il tool ti avvisa se mancano, senza crashare):
  pip install phonenumbers   -> per il Phone number lookup
  pip install "qrcode[pil]"  -> per il QR code generator

Per whois/nslookup, se mancano, il tool prova ad installarli da solo con
'sudo apt' (su Linux), chiedendoti la password direttamente tramite sudo.
"""

import os
import re
import sys
import time
import math
import socket
import random
import secrets
import string
import shutil
import getpass
import hashlib
import zipfile
import tarfile
import ssl
import json
import base64
import ipaddress
import urllib.parse
from http import HTTPStatus
import subprocess
import itertools
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
except ImportError:
    print("Manca la libreria 'requests'. Installala con: pip install requests")
    sys.exit(1)

import importlib


def ensure_pip_package(module_name, pip_name=None):
    """Importa il modulo; se manca prova ad installarlo con pip in modo compatibile
    sia con Windows che con Linux (gestisce il caso 'externally-managed-environment'
    di Debian/Ubuntu/Mint aggiungendo --break-system-packages quando serve)."""
    pip_name = pip_name or module_name
    try:
        return importlib.import_module(module_name)
    except ImportError:
        pass

    print(f"{C.YELLOW}Libreria '{pip_name}' non trovata. Provo ad installarla...{C.RESET}")
    base_cmd = [sys.executable, "-m", "pip", "install", pip_name]
    try:
        result = subprocess.run(base_cmd, capture_output=True, text=True, timeout=180)
        combined = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0 and "externally-managed-environment" in combined:
            print(f"{C.GRAY}Ambiente Linux gestito esternamente rilevato, riprovo con --break-system-packages...{C.RESET}")
            result = subprocess.run(base_cmd + ["--break-system-packages"], capture_output=True, text=True, timeout=180)
            combined = (result.stdout or "") + (result.stderr or "")

        if result.returncode == 0:
            importlib.invalidate_caches()
            try:
                mod = importlib.import_module(module_name)
                print(f"{C.GREEN}[+] '{pip_name}' installato correttamente.{C.RESET}\n")
                return mod
            except ImportError:
                print(f"{C.YELLOW}Installato, ma serve riavviare il programma per usarlo.{C.RESET}")
                return None
        else:
            print(f"{C.RED}Installazione fallita:{C.RESET}\n{combined[-500:]}")
            return None
    except Exception as e:
        print(f"{C.RED}Errore durante l'installazione: {e}{C.RESET}")
        return None


# =========================================================
# COLORI / UI DI BASE
# =========================================================
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    GRAY = "\033[90m"
    WHITE = "\033[97m"

    @staticmethod
    def rgb(r, g, b):
        return f"\033[38;2;{r};{g};{b}m"


BLUE = C.rgb(60, 190, 245)

GRADIENT = [C.rgb(10, 20, 90), C.rgb(15, 40, 140), C.rgb(20, 70, 180),
            C.rgb(25, 110, 210), C.rgb(30, 150, 230), C.rgb(60, 190, 245),
            C.rgb(100, 220, 255), C.rgb(150, 235, 255)]

ICE_ART = [
    r" _____ _____ ______   _______ ____   ____  _      ",
    r"|_   _/ ____|  ____| |__   __/ __ \ / __ \| |     ",
    r"  | || |    | |__       | | | |  | | |  | | |     ",
    r"  | || |    |  __|      | | | |  | | |  | | |     ",
    r" _| || |____| |____     | | | |__| | |__| | |____ ",
    r"|_____\_____|______|    |_|  \____/ \____/|______|",
]


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def print_banner():
    clear()
    for i, line in enumerate(ICE_ART):
        color = GRADIENT[i % len(GRADIENT)]
        print(color + C.BOLD + line + C.RESET)
    print(GRADIENT[-1] + C.BOLD + "         < OSINT / NETWORK / SECURITY TOOLKIT >" + C.RESET)
    print(C.GRAY + "-" * 62 + C.RESET)


def section(title):
    print(f"\n{BLUE}{C.BOLD}== {title} =={C.RESET}")


def field(label, value):
    print(f"  {C.GRAY}{label:<20}{C.RESET}{C.WHITE}{value}{C.RESET}")


def pause():
    input(f"\n{C.GRAY}Premi INVIO per tornare al menu...{C.RESET}")


def ask_int(prompt, min_v, max_v):
    while True:
        raw = input(prompt).strip()
        if raw.isdigit() and min_v <= int(raw) <= max_v:
            return int(raw)
        print(f"{C.RED}Inserisci un numero tra {min_v} e {max_v}.{C.RESET}")


def print_two_columns(labels):
    half = (len(labels) + 1) // 2
    left, right = labels[:half], labels[half:]
    for i in range(half):
        l = f"[{i}] {left[i]}"
        r = f"[{i + half}] {right[i]}" if i < len(right) else ""
        print(f"  {BLUE}{l:<44}{C.RESET}{BLUE if r else ''}{r}{C.RESET}")


# =========================================================
# UTILITY DI SISTEMA CONDIVISE
# =========================================================
def run_cmd(cmd_list):
    exe = shutil.which(cmd_list[0])
    if not exe:
        return None, f"comando '{cmd_list[0]}' non trovato sul sistema"
    try:
        result = subprocess.run(cmd_list, capture_output=True, text=True, timeout=15)
        return result.stdout.strip(), None
    except Exception as e:
        return None, str(e)


def ensure_tool_installed(tool_name, apt_package=None):
    if shutil.which(tool_name):
        return True
    if os.name != "posix" or not shutil.which("apt"):
        print(f"{C.YELLOW}'{tool_name}' non trovato e installazione automatica non disponibile su questo sistema.{C.RESET}")
        return False
    pkg = apt_package or tool_name
    print(f"{C.YELLOW}'{tool_name}' non e' installato. Provo a installarlo con: sudo apt install {pkg}{C.RESET}")
    print(f"{C.GRAY}Ti verra' chiesta la password di amministratore da sudo stesso.{C.RESET}\n")
    try:
        subprocess.run(["sudo", "apt", "update"], timeout=120)
        result = subprocess.run(["sudo", "apt", "install", "-y", pkg], timeout=180)
        if result.returncode == 0 and shutil.which(tool_name):
            print(f"{C.GREEN}[+] '{tool_name}' installato correttamente.{C.RESET}\n")
            return True
        print(f"{C.RED}Installazione non riuscita.{C.RESET}\n")
        return False
    except Exception as e:
        print(f"{C.RED}Errore durante l'installazione: {e}{C.RESET}\n")
        return False


# =========================================================
# MINECRAFT NICK CHECKER
# =========================================================
MC_API_URL = "https://api.mojang.com/users/profiles/minecraft/{}"
MC_DELAY = 0.2
MC_OUTPUT_FILE = "mc_available_names.txt"
VALID_CHARS = string.ascii_lowercase + string.digits + "_"


def mc_check_name(session, name):
    try:
        resp = session.get(MC_API_URL.format(name), timeout=8)
    except requests.RequestException:
        return None
    if resp.status_code == 200:
        return False
    elif resp.status_code == 404:
        return True
    return None


def mc_random_name(length):
    return "".join(random.choice(VALID_CHARS) for _ in range(length))


def mc_sequential_generator(length):
    for combo in itertools.product(VALID_CHARS, repeat=length):
        yield "".join(combo)


def minecraft_checker():
    print_banner()
    section("MINECRAFT NICK CHECKER")
    length = ask_int(f"{C.YELLOW}Quanti caratteri deve avere il nickname? (3-16): {C.RESET}", 3, 16)

    print(f"\n{BLUE}Modalita':{C.RESET}")
    print("  [0] Casuale (continua finche' non fermi con CTRL+C)")
    print("  [1] Sequenziale (tutte le combinazioni in ordine — puo' essere ENORME)")
    mode = ask_int(f"{C.YELLOW}Scegli (0/1): {C.RESET}", 0, 1)

    limit = None
    if mode == 0:
        limit_raw = input(f"{C.YELLOW}Quanti nomi vuoi provare? (invio = infinito): {C.RESET}").strip()
        if limit_raw.isdigit():
            limit = int(limit_raw)

    print(f"\n{C.GRAY}I risultati LIBERI verranno salvati in '{MC_OUTPUT_FILE}'{C.RESET}")
    print(f"{C.GRAY}Premi CTRL+C per fermare.{C.RESET}\n")
    time.sleep(0.5)

    session = requests.Session()
    generator = mc_sequential_generator(length) if mode == 1 else None
    tried = found = 0

    try:
        with open(MC_OUTPUT_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n--- Sessione {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (lunghezza={length}) ---\n")
            f.flush()
            while True:
                if limit is not None and tried >= limit:
                    break
                name = next(generator) if mode == 1 else mc_random_name(length)
                result = mc_check_name(session, name)
                if result is None:
                    print(f"{C.GRAY}[!] {name.ljust(length)}  errore/rate-limit, riprovo...{C.RESET}")
                    time.sleep(2.0)
                    continue
                tried += 1
                if result:
                    found += 1
                    print(f"{C.GREEN}[+] {name.ljust(length)}  LIBERO{C.RESET}")
                    f.write(f"{name}\n")
                    f.flush()
                else:
                    print(f"{C.RED}[-] {name.ljust(length)}  occupato{C.RESET}")
                time.sleep(MC_DELAY)
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}Interrotto.{C.RESET}")
    except StopIteration:
        print(f"\n{C.YELLOW}Combinazioni esaurite per questa lunghezza.{C.RESET}")

    print(f"\n{C.BOLD}Riepilogo:{C.RESET} controllati {tried}, trovati {found} liberi.")
    print(f"Salvati in: {BLUE}{os.path.abspath(MC_OUTPUT_FILE)}{C.RESET}")
    pause()


# =========================================================
# USERNAME CHECKER MULTI-SOCIAL
# =========================================================
UA = {"User-Agent": "Mozilla/5.0 (IceTool OSINT)"}


def uc_github(u):
    try:
        return requests.get(f"https://api.github.com/users/{u}", timeout=8).status_code == 200
    except Exception:
        return None


def uc_gitlab(u):
    try:
        r = requests.get(f"https://gitlab.com/api/v4/users?username={u}", timeout=8)
        return r.status_code == 200 and len(r.json()) > 0
    except Exception:
        return None


def uc_reddit(u):
    try:
        return requests.get(f"https://www.reddit.com/user/{u}/about.json", timeout=8, headers=UA).status_code == 200
    except Exception:
        return None


def uc_npm(u):
    try:
        return requests.get(f"https://registry.npmjs.org/-/user/org.couchdb.user:{u}", timeout=8).status_code == 200
    except Exception:
        return None


def uc_instagram(u):
    try:
        r = requests.get(f"https://www.instagram.com/{u}/", timeout=8, headers=UA)
        if r.status_code == 404:
            return False
        return r.status_code == 200 and "Sorry, this page" not in r.text
    except Exception:
        return None


def uc_tiktok(u):
    try:
        r = requests.get(f"https://www.tiktok.com/@{u}", timeout=8, headers=UA)
        if r.status_code == 404:
            return False
        return "Couldn't find this account" not in r.text
    except Exception:
        return None


def uc_steam(u):
    try:
        r = requests.get(f"https://steamcommunity.com/id/{u}", timeout=8, headers=UA)
        return "The specified profile could not be found" not in r.text
    except Exception:
        return None


def uc_twitch(u):
    try:
        return requests.get(f"https://www.twitch.tv/{u}", timeout=8, headers=UA).status_code == 200
    except Exception:
        return None


def uc_pinterest(u):
    try:
        r = requests.get(f"https://www.pinterest.com/{u}/", timeout=8, headers=UA)
        return r.status_code == 200 and "not found" not in r.text.lower()
    except Exception:
        return None


def uc_telegram(u):
    try:
        r = requests.get(f"https://t.me/{u}", timeout=8, headers=UA)
        return "tgme_page_title" in r.text
    except Exception:
        return None


PLATFORMS = {
    "GitHub": uc_github, "GitLab": uc_gitlab, "Reddit": uc_reddit, "NPM": uc_npm,
    "Instagram": uc_instagram, "TikTok": uc_tiktok, "Steam": uc_steam, "Twitch": uc_twitch,
    "Pinterest": uc_pinterest, "Telegram": uc_telegram,
}


def username_checker():
    print_banner()
    section("USERNAME CHECKER MULTI-SOCIAL")
    username = input(f"{C.YELLOW}Username da controllare: {C.RESET}").strip()
    print()
    for name, fn in PLATFORMS.items():
        result = fn(username)
        if result is True:
            print(f"{C.RED}[-] {name:<12} occupato{C.RESET}")
        elif result is False:
            print(f"{C.GREEN}[+] {name:<12} libero/non trovato{C.RESET}")
        else:
            print(f"{C.GRAY}[?] {name:<12} impossibile verificare{C.RESET}")
        time.sleep(0.3)
    print(f"\n{C.GRAY}Nota: alcune piattaforme cambiano pagina spesso e rendono il check meno affidabile.{C.RESET}")
    pause()


# =========================================================
# IP LOOKUP (+ rete locale per "my ip") / VPN / SITE / PORT / SUBDOMAIN / HEADERS / PING
# =========================================================
IP_FIELDS = "status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,mobile,proxy,hosting,query"


def ip_lookup(ip=None):
    url = f"http://ip-api.com/json/{ip or ''}?fields={IP_FIELDS}"
    try:
        resp = requests.get(url, timeout=8)
        data = resp.json()
    except requests.RequestException as e:
        return None, str(e)
    if data.get("status") != "success":
        return None, data.get("message", "errore sconosciuto")
    return data, None


def print_ip_data(data):
    section("RISULTATO IP LOOKUP")
    field("IP:", data.get("query"))
    field("Citta':", data.get("city"))
    field("Regione:", data.get("regionName"))
    field("Stato:", f"{data.get('country')} ({data.get('countryCode')})")
    field("CAP:", data.get("zip"))
    field("Coordinate:", f"{data.get('lat')}, {data.get('lon')}")
    field("Fuso orario:", data.get("timezone"))
    field("ISP:", data.get("isp"))
    field("Organizzazione:", data.get("org"))
    field("AS:", data.get("as"))
    field("Mobile:", "si'" if data.get("mobile") else "no")
    field("Proxy/VPN:", "si'" if data.get("proxy") else "no")
    field("Hosting/DC:", "si'" if data.get("hosting") else "no")


def get_local_network_info():
    """Info di rete disponibili SOLO per il PC su cui gira lo script."""
    info = {}
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        info["local_ip"] = s.getsockname()[0]
        s.close()
    except Exception:
        info["local_ip"] = "non determinabile"

    info["hostname"] = socket.gethostname()
    info["gateway"] = "non determinabile"
    info["ssid"] = "non determinabile (o connesso via cavo)"

    if os.name != "nt":
        out, _ = run_cmd(["ip", "route"])
        if out:
            for line in out.splitlines():
                if line.startswith("default"):
                    parts = line.split()
                    if len(parts) > 2:
                        info["gateway"] = parts[2]
                    break
        ssid_out, _ = run_cmd(["iwgetid", "-r"])
        if not ssid_out:
            nm_out, _ = run_cmd(["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"])
            if nm_out:
                for line in nm_out.splitlines():
                    if line.startswith("yes:"):
                        ssid_out = line.split(":", 1)[1]
                        break
        if ssid_out:
            info["ssid"] = ssid_out
    return info


def print_local_network_info():
    section("RETE LOCALE (solo su questo PC)")
    info = get_local_network_info()
    field("Hostname:", info["hostname"])
    field("IP locale:", info["local_ip"])
    field("Gateway:", info["gateway"])
    field("SSID WiFi:", info["ssid"])


def my_ip_lookup():
    print_banner()
    section("MY IP LOOKUP")
    print(f"{C.GRAY}Recupero informazioni sul tuo IP pubblico...{C.RESET}")
    data, err = ip_lookup(None)
    if err:
        print(f"{C.RED}Errore: {err}{C.RESET}")
    else:
        print_ip_data(data)
        print_local_network_info()
    pause()


def other_ip_lookup():
    print_banner()
    section("OTHER IP LOOKUP")
    ip = input(f"{C.YELLOW}Inserisci l'IP da cercare: {C.RESET}").strip()
    data, err = ip_lookup(ip)
    if err:
        print(f"{C.RED}Errore: {err}{C.RESET}")
    else:
        print_ip_data(data)
        print(f"\n{C.GRAY}Nota: hostname/gateway/SSID non sono ottenibili per un IP che non e' questo PC —{C.RESET}")
        print(f"{C.GRAY}quei dati esistono solo sulla rete locale del dispositivo remoto, non raggiungibili dall'esterno.{C.RESET}")
    pause()


def vpn_detector():
    print_banner()
    section("VPN DETECTOR")
    ip = input(f"{C.YELLOW}Inserisci l'IP da controllare: {C.RESET}").strip()
    data, err = ip_lookup(ip)
    if err:
        print(f"{C.RED}Errore: {err}{C.RESET}")
        pause()
        return
    is_proxy, is_hosting = bool(data.get("proxy")), bool(data.get("hosting"))
    section("RISULTATO")
    field("IP:", data.get("query"))
    field("ISP:", data.get("isp"))
    field("Organizzazione:", data.get("org"))
    if is_proxy:
        print(f"\n  {C.RED}{C.BOLD}[!] Rilevata VPN / Proxy / Tor{C.RESET}")
    elif is_hosting:
        print(f"\n  {C.YELLOW}{C.BOLD}[?] IP di datacenter/hosting (probabile VPN/server){C.RESET}")
    else:
        print(f"\n  {C.GREEN}{C.BOLD}[OK] Nessun indizio di VPN/Proxy{C.RESET}")
    print(f"\n{C.GRAY}Nota: basato su database pubblici, non garantito al 100%.{C.RESET}")
    pause()


def site_lookup():
    print_banner()
    section("SITE LOOKUP")
    domain = input(f"{C.YELLOW}Inserisci il dominio (es. example.com): {C.RESET}").strip()
    domain = domain.replace("https://", "").replace("http://", "").split("/")[0]

    section("DNS")
    ip = None
    try:
        ip = socket.gethostbyname(domain)
        field("IP risolto:", ip)
    except socket.gaierror as e:
        print(f"  {C.RED}Impossibile risolvere il dominio: {e}{C.RESET}")

    section("NSLOOKUP")
    ensure_tool_installed("nslookup", apt_package="dnsutils")
    out, err = run_cmd(["nslookup", domain])
    if err:
        print(f"  {C.GRAY}{err}{C.RESET}")
    else:
        for line in out.splitlines():
            if line.strip():
                print(f"  {C.WHITE}{line.strip()}{C.RESET}")

    section("WHOIS")
    ensure_tool_installed("whois", apt_package="whois")
    out, err = run_cmd(["whois", domain])
    if err:
        print(f"  {C.GRAY}{err}{C.RESET}")
    else:
        keys = ["Domain Name", "Registrar", "Creation Date", "Registry Expiry Date",
                "Updated Date", "Name Server", "Registrant Country", "Registrant Organization"]
        shown = False
        for line in out.splitlines():
            if any(line.strip().lower().startswith(k.lower()) for k in keys) and ":" in line:
                k, v = line.split(":", 1)
                field(k.strip() + ":", v.strip())
                shown = True
        if not shown:
            print(f"  {C.GRAY}(output non standard, prime righe grezze:){C.RESET}")
            for line in out.splitlines()[:15]:
                if line.strip():
                    print(f"  {C.WHITE}{line.strip()}{C.RESET}")

    if ip:
        section("HOSTING / GEOLOCALIZZAZIONE IP")
        data, err = ip_lookup(ip)
        print(f"  {C.RED}Errore: {err}{C.RESET}") if err else print_ip_data(data)
    pause()


COMMON_PORTS = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
    80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS", 445: "SMB",
    465: "SMTPS", 587: "SMTP (submission)", 993: "IMAPS", 995: "POP3S",
    1433: "MSSQL", 1521: "Oracle DB", 3306: "MySQL", 3389: "RDP",
    5432: "PostgreSQL", 5900: "VNC", 6379: "Redis", 8080: "HTTP-alt",
    8443: "HTTPS-alt", 27017: "MongoDB",
}


def scan_port(host, port, timeout=0.8):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return port, s.connect_ex((host, port)) == 0
    except socket.error:
        return port, False


def port_scanner():
    print_banner()
    section("PORT SCANNER")
    print(f"{C.YELLOW}Usa questo strumento SOLO su host di tua proprieta' o per cui hai autorizzazione esplicita.{C.RESET}")
    target = input(f"\n{C.YELLOW}Host/IP da scansionare: {C.RESET}").strip()
    try:
        ip = socket.gethostbyname(target)
    except socket.gaierror as e:
        print(f"{C.RED}Impossibile risolvere l'host: {e}{C.RESET}")
        pause()
        return

    print(f"\n{C.GRAY}Scansiono {len(COMMON_PORTS)} porte comuni su {target} ({ip})...{C.RESET}\n")
    open_ports = []
    with ThreadPoolExecutor(max_workers=40) as executor:
        futures = {executor.submit(scan_port, ip, p): p for p in COMMON_PORTS}
        for fut in as_completed(futures):
            port, is_open = fut.result()
            service = COMMON_PORTS.get(port, "?")
            if is_open:
                open_ports.append(port)
                print(f"{C.GREEN}[+] {port:<6} {service:<20} APERTA{C.RESET}")
            else:
                print(f"{C.RED}[-] {port:<6} {service:<20} chiusa/filtrata{C.RESET}")
    print(f"\n{C.BOLD}Riepilogo:{C.RESET} {len(open_ports)} porte aperte su {len(COMMON_PORTS)}.")
    pause()


def subdomain_finder():
    print_banner()
    section("SUBDOMAIN FINDER")
    domain = input(f"{C.YELLOW}Inserisci il dominio (es. example.com): {C.RESET}").strip()
    domain = domain.replace("https://", "").replace("http://", "").split("/")[0]

    print(f"\n{C.GRAY}Interrogo i log di certificate transparency (crt.sh)...{C.RESET}\n")
    try:
        resp = requests.get(f"https://crt.sh/?q=%25.{domain}&output=json", timeout=20)
        data = resp.json()
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return

    subs = set()
    for entry in data:
        for name in entry.get("name_value", "").split("\n"):
            name = name.strip().lower()
            if name and "*" not in name:
                subs.add(name)

    subs = sorted(subs)
    if not subs:
        print(f"{C.YELLOW}Nessun sottodominio trovato.{C.RESET}")
    else:
        for s in subs:
            print(f"{C.GREEN}[+] {s}{C.RESET}")
        print(f"\n{C.BOLD}Trovati {len(subs)} sottodomini univoci.{C.RESET}")
    pause()


SECURITY_HEADERS = {
    "Strict-Transport-Security": "Forza le connessioni HTTPS",
    "Content-Security-Policy": "Limita le fonti di script/contenuti (anti XSS)",
    "X-Content-Type-Options": "Blocca il MIME-sniffing",
    "X-Frame-Options": "Protegge dal clickjacking",
    "Referrer-Policy": "Controlla i dati referrer inviati",
    "Permissions-Policy": "Limita l'accesso alle API del browser",
}


def http_headers_checker():
    print_banner()
    section("HTTP SECURITY HEADERS CHECKER")
    url = input(f"{C.YELLOW}Inserisci l'URL (es. https://example.com): {C.RESET}").strip()
    if not url.startswith("http"):
        url = "https://" + url
    try:
        resp = requests.get(url, timeout=10, allow_redirects=True)
    except requests.RequestException as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return

    section(f"RISPOSTA: {resp.status_code} {resp.reason}")
    if resp.history:
        field("Redirect:", " -> ".join([r.url for r in resp.history] + [resp.url]))

    section("HEADER DI SICUREZZA")
    present = 0
    for h, desc in SECURITY_HEADERS.items():
        if h in resp.headers:
            present += 1
            print(f"{C.GREEN}[+] {h:<28}{C.RESET} {C.GRAY}{resp.headers[h][:60]}{C.RESET}")
        else:
            print(f"{C.RED}[-] {h:<28}{C.RESET} {C.GRAY}mancante — {desc}{C.RESET}")
    print(f"\n{C.BOLD}Punteggio:{C.RESET} {present}/{len(SECURITY_HEADERS)} header presenti.")

    section("ALTRI HEADER RILEVANTI")
    for h in ["Server", "X-Powered-By"]:
        if h in resp.headers:
            field(h + ":", resp.headers[h])
    pause()


def ping_monitor():
    print_banner()
    section("PING / UPTIME MONITOR")
    host = input(f"{C.YELLOW}Host/IP da testare: {C.RESET}").strip()
    count = ask_int(f"{C.YELLOW}Quanti ping vuoi inviare? (1-20): {C.RESET}", 1, 20)
    cmd = ["ping", "-n", str(count), host] if os.name == "nt" else ["ping", "-c", str(count), host]
    print(f"\n{C.GRAY}Eseguo: {' '.join(cmd)}{C.RESET}\n")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=count * 3 + 10)
        out = result.stdout
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    for line in out.splitlines():
        if line.strip():
            color = C.GREEN if "bytes from" in line or "byte da" in line.lower() else C.WHITE
            print(f"  {color}{line.strip()}{C.RESET}")
    if result.returncode == 0:
        print(f"\n{C.GREEN}{C.BOLD}[+] Host raggiungibile.{C.RESET}")
    else:
        print(f"\n{C.RED}{C.BOLD}[-] Host non raggiungibile o timeout.{C.RESET}")
    pause()


# =========================================================
# SICUREZZA: password breach / generator / file hash comparator
# =========================================================
def password_breach_check(password):
    sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]
    try:
        resp = requests.get(f"https://api.pwnedpasswords.com/range/{prefix}", timeout=8)
    except requests.RequestException as e:
        return None, str(e)
    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code}"
    for line in resp.text.splitlines():
        suf, count = line.split(":")
        if suf == suffix:
            return int(count), None
    return 0, None


def password_breach_checker():
    print_banner()
    section("PASSWORD BREACH CHECKER")
    print(f"{C.GRAY}La password non viene mai inviata in chiaro (k-anonymity: solo 5 char dell'hash SHA1).{C.RESET}\n")
    try:
        pwd = getpass.getpass(f"{C.YELLOW}Password da controllare (non mostrata): {C.RESET}")
    except Exception:
        pwd = input(f"{C.YELLOW}Password da controllare: {C.RESET}")
    if not pwd:
        print(f"{C.RED}Nessuna password inserita.{C.RESET}")
        pause()
        return
    count, err = password_breach_check(pwd)
    if err:
        print(f"{C.RED}Errore: {err}{C.RESET}")
    elif count > 0:
        print(f"\n{C.RED}{C.BOLD}[!] Comparsa in {count:,} violazioni di dati note. Cambiala se la usi ancora.{C.RESET}")
    else:
        print(f"\n{C.GREEN}{C.BOLD}[OK] Nessuna violazione nota trovata.{C.RESET}")
    pause()


def password_generator():
    print_banner()
    section("PASSWORD GENERATOR")
    length = ask_int(f"{C.YELLOW}Lunghezza password (8-64): {C.RESET}", 8, 64)
    use_symbols = input(f"{C.YELLOW}Includere simboli speciali? (s/n): {C.RESET}").strip().lower() == "s"
    pool = string.ascii_letters + string.digits
    if use_symbols:
        pool += "!@#$%^&*()-_=+[]{}?"
    pwd = "".join(secrets.choice(pool) for _ in range(length))
    section("PASSWORD GENERATA")
    print(f"  {C.GREEN}{C.BOLD}{pwd}{C.RESET}")
    print(f"\n{C.GRAY}Generata con il modulo 'secrets' (crittograficamente sicuro).{C.RESET}")
    pause()


def file_hash_comparator():
    print_banner()
    section("FILE HASH COMPARATOR")
    p1 = input(f"{C.YELLOW}Percorso primo file: {C.RESET}").strip()
    p2 = input(f"{C.YELLOW}Percorso secondo file: {C.RESET}").strip()
    if not (os.path.isfile(p1) and os.path.isfile(p2)):
        print(f"{C.RED}Uno o entrambi i file non esistono.{C.RESET}")
        pause()
        return

    def sha256_of(path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    h1, h2 = sha256_of(p1), sha256_of(p2)
    section("RISULTATO")
    field("SHA256 file 1:", h1)
    field("SHA256 file 2:", h2)
    if h1 == h2:
        print(f"\n{C.GREEN}{C.BOLD}[OK] I file sono identici.{C.RESET}")
    else:
        print(f"\n{C.RED}{C.BOLD}[!] I file sono DIVERSI.{C.RESET}")
    pause()


# =========================================================
# EMAIL & TELEFONO
# =========================================================
EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def get_mx_records(domain):
    ensure_tool_installed("nslookup", apt_package="dnsutils")
    out, err = run_cmd(["nslookup", "-type=mx", domain])
    if err or not out:
        return []
    hosts = []
    for line in out.splitlines():
        line = line.strip()
        if "mail exchanger" in line.lower():
            parts = line.split("=")
            if len(parts) > 1:
                hosts.append(parts[-1].strip().rstrip("."))
    return hosts


def email_validator():
    print_banner()
    section("EMAIL VALIDATOR")
    email = input(f"{C.YELLOW}Email da controllare: {C.RESET}").strip()
    if not EMAIL_REGEX.match(email):
        print(f"\n{C.RED}{C.BOLD}[!] Formato email non valido.{C.RESET}")
        pause()
        return
    print(f"\n{C.GREEN}[+] Formato valido.{C.RESET}")
    domain = email.split("@")[1]
    section("RECORD MX (capacita' di ricevere email)")
    mx = get_mx_records(domain)
    if mx:
        for m in mx:
            print(f"{C.GREEN}[+] {m}{C.RESET}")
        print(f"\n{C.GREEN}{C.BOLD}[OK] Il dominio ha server di posta configurati.{C.RESET}")
    else:
        print(f"{C.RED}[-] Nessun record MX trovato — il dominio probabilmente non puo' ricevere email.{C.RESET}")
    pause()


LINE_TYPE_NAMES = {
    0: "Fisso", 1: "Cellulare", 2: "Fisso o cellulare", 3: "VOIP",
    4: "Numero personale", 5: "Numero verde/servizio", 6: "Premium rate",
    7: "Tariffa condivisa", 8: "Cercapersone", 9: "UAN", 10: "Voicemail", 27: "Sconosciuto",
}


def phone_lookup():
    print_banner()
    section("PHONE NUMBER LOOKUP")
    mod = ensure_pip_package("phonenumbers")
    if mod is None:
        print(f"{C.RED}Impossibile procedere senza la libreria 'phonenumbers'.{C.RESET}\n")
        if os.name == "nt":
            print(f"{C.YELLOW}Prova manualmente: pip install phonenumbers{C.RESET}")
        else:
            print(f"{C.YELLOW}Prova manualmente: pip install phonenumbers --break-system-packages{C.RESET}")
            print(f"{C.GRAY}oppure in un virtualenv: python3 -m venv venv && source venv/bin/activate && pip install phonenumbers requests{C.RESET}")
        pause()
        return

    import phonenumbers
    from phonenumbers import geocoder as pn_geocoder, carrier as pn_carrier

    raw = input(f"{C.YELLOW}Numero (con prefisso, es. +39...): {C.RESET}").strip()
    try:
        parsed = phonenumbers.parse(raw, None)
    except phonenumbers.NumberParseException as e:
        print(f"{C.RED}Numero non valido: {e}{C.RESET}")
        pause()
        return
    valid = phonenumbers.is_valid_number(parsed)
    section("RISULTATO")
    field("Valido:", "si'" if valid else "no")
    field("Formato E.164:", phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164))
    field("Paese:", pn_geocoder.description_for_number(parsed, "it") or "sconosciuto")
    field("Operatore:", pn_carrier.name_for_number(parsed, "it") or "sconosciuto/non determinabile")
    field("Tipo linea:", LINE_TYPE_NAMES.get(phonenumbers.number_type(parsed), "sconosciuto"))
    pause()


# =========================================================
# QR CODE GENERATOR (testo / WiFi / vCard)
# =========================================================
def qr_generator():
    print_banner()
    section("QR CODE GENERATOR")
    mod = ensure_pip_package("qrcode", pip_name="qrcode[pil]")
    if mod is None:
        print(f"{C.RED}Impossibile procedere senza la libreria 'qrcode'.{C.RESET}")
        print(f"{C.YELLOW}Prova manualmente: pip install \"qrcode[pil]\"{C.RESET}")
        pause()
        return

    import qrcode

    print("  [0] Testo o link")
    print("  [1] Rete WiFi (connessione automatica scansionando)")
    print("  [2] Contatto (vCard)")
    mode = ask_int(f"{C.YELLOW}Scegli: {C.RESET}", 0, 2)

    if mode == 0:
        data = input(f"{C.YELLOW}Testo o link: {C.RESET}")
    elif mode == 1:
        ssid = input(f"{C.YELLOW}Nome rete (SSID): {C.RESET}")
        pwd = input(f"{C.YELLOW}Password: {C.RESET}")
        sec = input(f"{C.YELLOW}Sicurezza (WPA/WEP/nopass) [WPA]: {C.RESET}").strip() or "WPA"
        data = f"WIFI:T:{sec};S:{ssid};P:{pwd};;"
    else:
        nome = input(f"{C.YELLOW}Nome: {C.RESET}")
        tel = input(f"{C.YELLOW}Telefono: {C.RESET}")
        mail = input(f"{C.YELLOW}Email: {C.RESET}")
        data = f"BEGIN:VCARD\nVERSION:3.0\nFN:{nome}\nTEL:{tel}\nEMAIL:{mail}\nEND:VCARD"

    qr = qrcode.QRCode(border=1)
    qr.add_data(data)
    qr.make()
    print()
    qr.print_ascii(invert=True)

    save = input(f"\n{C.YELLOW}Salvare anche come immagine PNG? (s/n): {C.RESET}").strip().lower()
    if save == "s":
        img = qr.make_image()
        out_path = "qr_code.png"
        img.save(out_path)
        print(f"{C.GREEN}Salvato in: {os.path.abspath(out_path)}{C.RESET}")
    pause()


# =========================================================
# SITE MIRROR (backup di un sito con wget --mirror)
# =========================================================
def site_mirror():
    print_banner()
    section("SITE MIRROR (wget --mirror)")
    print(f"{C.YELLOW}Usa questo strumento SOLO su siti di tua proprieta' o per cui hai autorizzazione esplicita.{C.RESET}")
    print(f"{C.GRAY}E' lo stesso comando che scaricherebbe una pagina altrui per clonarla — su siti non tuoi e' abuso.{C.RESET}\n")

    url = input(f"{C.YELLOW}URL del sito (es. https://iltuosito.com): {C.RESET}").strip()
    if not url:
        print(f"{C.RED}Nessun URL inserito.{C.RESET}")
        pause()
        return
    if not url.startswith("http"):
        url = "https://" + url

    domain = url.replace("https://", "").replace("http://", "").split("/")[0]
    default_folder = domain.replace(":", "_")
    folder = input(f"{C.YELLOW}Nome cartella di destinazione [{default_folder}]: {C.RESET}").strip() or default_folder

    wait = input(f"{C.YELLOW}Secondi di attesa tra le richieste [1]: {C.RESET}").strip() or "1"
    rate = input(f"{C.YELLOW}Limite di velocita' (es. 200k, invio = nessun limite): {C.RESET}").strip()

    if not ensure_tool_installed("wget", apt_package="wget"):
        pause()
        return

    cmd = [
        "wget", "--mirror", "--convert-links", "--adjust-extension",
        "--page-requisites", "--no-parent",
        "--wait", wait,
        "-U", "Mozilla/5.0",
        "-P", folder,
        url,
    ]
    if rate:
        cmd += ["--limit-rate", rate]

    section("COMANDO")
    print(f"  {C.GRAY}{' '.join(cmd)}{C.RESET}")
    print(f"\n{C.GRAY}Avvio il mirror, puo' volerci un po'... (CTRL+C per interrompere){C.RESET}\n")

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, bufsize=1)
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            if "Saving to" in line or "saved [" in line:
                print(f"{C.GREEN}{line}{C.RESET}")
            elif "ERROR" in line.upper() or "failed" in line.lower():
                print(f"{C.RED}{line}{C.RESET}")
            else:
                print(f"{C.GRAY}{line}{C.RESET}")
        proc.wait()
        if proc.returncode == 0:
            print(f"\n{C.GREEN}{C.BOLD}[+] Mirror completato in '{os.path.abspath(folder)}'{C.RESET}")
        else:
            print(f"\n{C.YELLOW}[!] wget ha terminato con codice {proc.returncode} (alcuni file potrebbero mancare, es. pagine bloccate da robots.txt).{C.RESET}")
    except KeyboardInterrupt:
        proc.terminate()
        print(f"\n{C.YELLOW}Interrotto dall'utente.{C.RESET}")
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
    pause()


# =========================================================
# UNIVERSAL EXTRACTOR (exe/msi/jar/zip/mod/plugin ecc.)
# =========================================================
ZIP_LIKE_EXTENSIONS = {".zip", ".jar", ".whl", ".egg", ".apk", ".docx", ".xlsx", ".pptx", ".jmod"}


def ensure_7z():
    if shutil.which("7z") or shutil.which("7za"):
        return shutil.which("7z") or shutil.which("7za")
    if os.name == "nt":
        print(f"{C.YELLOW}7-Zip non trovato. Scaricalo da: https://www.7-zip.org/ e installalo.{C.RESET}")
        print(f"{C.GRAY}Dopo l'installazione potrebbe servire riavviare il terminale (o aggiungere{C.RESET}")
        print(f"{C.GRAY}la cartella di 7-Zip, es. C:\\Program Files\\7-Zip, alla variabile PATH).{C.RESET}")
        return None
    if ensure_tool_installed("7z", apt_package="p7zip-full"):
        return shutil.which("7z")
    return None


def universal_extractor():
    print_banner()
    section("UNIVERSAL EXTRACTOR")
    print(f"{C.GRAY}Estrae il contenuto di .exe, .msi, .jar (mod/plugin Minecraft), .zip, .tar, .whl, .apk ecc.{C.RESET}\n")

    path = input(f"{C.YELLOW}Percorso del file da estrarre: {C.RESET}").strip()
    if not os.path.isfile(path):
        print(f"{C.RED}File non trovato.{C.RESET}")
        pause()
        return

    name = os.path.basename(path)
    stem, ext = os.path.splitext(name)
    ext = ext.lower()
    default_out = stem + "_extracted"
    out_dir = input(f"{C.YELLOW}Cartella di destinazione [{default_out}]: {C.RESET}").strip() or default_out
    os.makedirs(out_dir, exist_ok=True)

    section("ESTRAZIONE")
    try:
        if ext in ZIP_LIKE_EXTENSIONS or zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                z.extractall(out_dir)
            print(f"{C.GREEN}[+] Estratto come archivio ZIP/JAR in '{os.path.abspath(out_dir)}'{C.RESET}")

        elif tarfile.is_tarfile(path):
            with tarfile.open(path) as t:
                t.extractall(out_dir)
            print(f"{C.GREEN}[+] Estratto come archivio TAR in '{os.path.abspath(out_dir)}'{C.RESET}")

        else:
            # .exe / .msi / installer sconosciuti -> tenta con 7-Zip
            seven_zip = ensure_7z()
            if not seven_zip:
                pause()
                return
            print(f"{C.GRAY}Provo l'estrazione con 7-Zip (funziona con molti installer, non tutti)...{C.RESET}\n")
            result = subprocess.run([seven_zip, "x", f"-o{out_dir}", "-y", path],
                                     capture_output=True, text=True, timeout=120)
            for line in result.stdout.splitlines():
                if line.strip():
                    print(f"  {C.GRAY}{line.strip()}{C.RESET}")
            if result.returncode == 0:
                print(f"\n{C.GREEN}[+] Estratto in '{os.path.abspath(out_dir)}'{C.RESET}")
            else:
                print(f"\n{C.RED}[!] 7-Zip non e' riuscito ad aprirlo — non tutti gli installer sono estraibili cosi'.{C.RESET}")
                pause()
                return

        section("CONTENUTO ESTRATTO")
        count = 0
        for root, dirs, files in os.walk(out_dir):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), out_dir)
                print(f"  {C.WHITE}{rel}{C.RESET}")
                count += 1
                if count >= 200:
                    break
            if count >= 200:
                print(f"  {C.GRAY}[...] altri file omessi{C.RESET}")
                break
        print(f"\n{C.BOLD}Totale file estratti:{C.RESET} {count}{'+' if count >= 200 else ''}")

    except Exception as e:
        print(f"{C.RED}Errore durante l'estrazione: {e}{C.RESET}")
    pause()


# =========================================================
# SVILUPPO & PROGRAMMAZIONE
# =========================================================
def http_server_launcher():
    print_banner()
    section("LOCAL HTTP SERVER LAUNCHER")
    folder = input(f"{C.YELLOW}Cartella da servire (invio = corrente): {C.RESET}").strip() or "."
    if not os.path.isdir(folder):
        print(f"{C.RED}Cartella non trovata.{C.RESET}")
        pause()
        return
    port = ask_int(f"{C.YELLOW}Porta (1024-65535): {C.RESET}", 1024, 65535)
    print(f"\n{C.GREEN}Server avviato su http://localhost:{port} (CTRL+C per fermare){C.RESET}\n")
    proc = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--directory", folder])
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        print(f"\n{C.YELLOW}Server fermato.{C.RESET}")
    pause()


def outdated_packages_checker():
    print_banner()
    section("OUTDATED PACKAGES CHECKER")
    path = input(f"{C.YELLOW}Percorso requirements.txt: {C.RESET}").strip()
    if not os.path.isfile(path):
        print(f"{C.RED}File non trovato.{C.RESET}")
        pause()
        return
    with open(path, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    section("RISULTATO")
    for line in lines:
        m = re.match(r"^([A-Za-z0-9_\-.]+)\s*(==|>=|<=|~=)?\s*([A-Za-z0-9_.\-]*)", line)
        if not m:
            continue
        pkg, _, cur_ver = m.group(1), m.group(2), m.group(3)
        try:
            r = requests.get(f"https://pypi.org/pypi/{pkg}/json", timeout=8)
            if r.status_code != 200:
                print(f"{C.GRAY}[?] {pkg:<25} non trovato su PyPI{C.RESET}")
                continue
            latest = r.json()["info"]["version"]
        except Exception:
            print(f"{C.GRAY}[?] {pkg:<25} errore di rete{C.RESET}")
            continue
        if cur_ver and cur_ver != latest:
            print(f"{C.YELLOW}[!] {pkg:<25} attuale={cur_ver} -> ultima={latest}{C.RESET}")
        elif not cur_ver:
            print(f"{C.GRAY}[i] {pkg:<25} versione non fissata (ultima={latest}){C.RESET}")
        else:
            print(f"{C.GREEN}[OK] {pkg:<25} aggiornato ({latest}){C.RESET}")
        time.sleep(0.1)
    pause()


GITIGNORE_TEMPLATES = ["Python", "Node", "Java", "C++", "C", "Go", "Rust",
                        "VisualStudio", "Unity", "Android", "macOS", "Windows", "Linux"]


def gitignore_generator():
    print_banner()
    section(".GITIGNORE GENERATOR")
    print(f"{C.GRAY}Template disponibili: {', '.join(GITIGNORE_TEMPLATES)}{C.RESET}")
    name = input(f"\n{C.YELLOW}Quale template vuoi (es. Python): {C.RESET}").strip()
    try:
        r = requests.get(f"https://raw.githubusercontent.com/github/gitignore/main/{name}.gitignore", timeout=10)
        if r.status_code != 200:
            print(f"{C.RED}Template '{name}' non trovato.{C.RESET}")
            pause()
            return
        content = r.text
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    with open(".gitignore", "w", encoding="utf-8") as f:
        f.write(content)
    section("ANTEPRIMA")
    for line in content.splitlines()[:30]:
        print(f"  {C.WHITE}{line}{C.RESET}")
    print(f"\n{C.GREEN}Salvato in: {os.path.abspath('.gitignore')}{C.RESET}")
    pause()


def env_file_validator():
    print_banner()
    section("ENV FILE VALIDATOR")
    path = input(f"{C.YELLOW}Percorso file .env: {C.RESET}").strip()
    if not os.path.isfile(path):
        print(f"{C.RED}File non trovato.{C.RESET}")
        pause()
        return

    seen, issues = {}, 0
    section("RISULTATO")
    with open(path, encoding="utf-8") as f:
        for i, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                print(f"{C.RED}[!] Riga {i}: manca '=' -> '{line}'{C.RESET}")
                issues += 1
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
                print(f"{C.RED}[!] Riga {i}: nome variabile non valido '{key}'{C.RESET}")
                issues += 1
            if key in seen:
                print(f"{C.YELLOW}[!] Riga {i}: '{key}' duplicata (vista a riga {seen[key]}){C.RESET}")
                issues += 1
            else:
                seen[key] = i
            if not value.strip():
                print(f"{C.YELLOW}[i] Riga {i}: '{key}' ha valore vuoto{C.RESET}")
    print(f"\n{C.GREEN}[OK] Nessun problema rilevato.{C.RESET}" if issues == 0 else f"\n{C.BOLD}Totale problemi:{C.RESET} {issues}")
    pause()


# =========================================================
# OSINT AVANZATO
# =========================================================
TECH_SIGNATURES = {
    "WordPress": ["wp-content", "wp-includes"],
    "Shopify": ["cdn.shopify.com"],
    "React": ["react.production.min.js", "data-reactroot"],
    "Vue.js": ["__vue__", "vue.min.js"],
    "Angular": ["ng-version"],
    "jQuery": ["jquery.min.js", "jquery.js"],
    "Bootstrap": ["bootstrap.min.css"],
    "Google Analytics": ["google-analytics.com", "gtag("],
    "Google Tag Manager": ["googletagmanager.com"],
    "WooCommerce": ["woocommerce"],
    "Drupal": ["Drupal.settings", "/sites/default/files"],
    "Joomla": ["/media/jui/", "Joomla!"],
    "Next.js": ["__NEXT_DATA__"],
}


def tech_stack_detector():
    print_banner()
    section("TECH STACK DETECTOR")
    url = input(f"{C.YELLOW}URL del sito: {C.RESET}").strip()
    if not url.startswith("http"):
        url = "https://" + url
    try:
        resp = requests.get(url, timeout=10, headers=UA)
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return

    section("HEADER SERVER")
    for h in ["Server", "X-Powered-By"]:
        if h in resp.headers:
            field(h + ":", resp.headers[h])
    if "cf-ray" in resp.headers or "cloudflare" in resp.headers.get("Server", "").lower():
        print(f"{C.GREEN}[+] Cloudflare (CDN){C.RESET}")

    section("TECNOLOGIE RILEVATE")
    found = [t for t, patterns in TECH_SIGNATURES.items() if any(p in resp.text for p in patterns)]
    for t in found:
        print(f"{C.GREEN}[+] {t}{C.RESET}")
    if not found:
        print(f"{C.GRAY}Nessuna tecnologia riconosciuta tra quelle note.{C.RESET}")
    pause()


def domain_aggregator():
    print_banner()
    section("COMPANY / DOMAIN AGGREGATOR")
    domain = input(f"{C.YELLOW}Dominio da analizzare: {C.RESET}").strip()
    domain = domain.replace("https://", "").replace("http://", "").split("/")[0]

    section("DNS")
    ip = None
    try:
        ip = socket.gethostbyname(domain)
        field("IP risolto:", ip)
    except socket.gaierror as e:
        print(f"{C.RED}{e}{C.RESET}")

    section("WHOIS (estratto)")
    ensure_tool_installed("whois", apt_package="whois")
    out, _ = run_cmd(["whois", domain])
    if out:
        keys = ["Registrar", "Creation Date", "Registry Expiry Date", "Name Server"]
        for line in out.splitlines():
            if any(line.lower().startswith(k.lower()) for k in keys) and ":" in line:
                k, v = line.split(":", 1)
                field(k.strip() + ":", v.strip())

    if ip:
        section("IP / HOSTING")
        data, err = ip_lookup(ip)
        if data:
            print_ip_data(data)

    section("TECH STACK")
    try:
        resp = requests.get("https://" + domain, timeout=10, headers=UA)
        found = [t for t, p in TECH_SIGNATURES.items() if any(x in resp.text for x in p)]
        for t in found:
            print(f"{C.GREEN}[+] {t}{C.RESET}")
        if not found:
            print(f"{C.GRAY}Nessuna tecnologia nota rilevata.{C.RESET}")
    except Exception as e:
        print(f"{C.GRAY}Impossibile analizzare la homepage: {e}{C.RESET}")
    pause()


def google_dork_generator():
    print_banner()
    section("GOOGLE DORK GENERATOR")
    print(f"{C.GRAY}Genera solo le query — non esegue ricerche o scraping.{C.RESET}\n")
    target = input(f"{C.YELLOW}Dominio o parola chiave target: {C.RESET}").strip()
    dorks = [
        f'site:{target} filetype:pdf',
        f'site:{target} filetype:xls OR filetype:xlsx',
        f'site:{target} filetype:sql',
        f'site:{target} intitle:"index of"',
        f'site:{target} inurl:admin',
        f'site:{target} inurl:login',
        f'site:{target} inurl:wp-content',
        f'site:{target} ext:env',
        f'site:{target} "password" filetype:log',
        f'site:{target} inurl:backup',
    ]
    section("QUERY GENERATE")
    for d in dorks:
        print(f"  {C.GREEN}{d}{C.RESET}")
    pause()


def email_header_analyzer():
    print_banner()
    section("EMAIL HEADER ANALYZER")
    print(f"{C.GRAY}Incolla gli header grezzi dell'email, poi una riga vuota per terminare:{C.RESET}\n")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "":
            break
        lines.append(line)
    text = "\n".join(lines)
    if not text:
        print(f"{C.RED}Nessun header inserito.{C.RESET}")
        pause()
        return

    section("CAMPI PRINCIPALI")
    for fname in ["From", "To", "Subject", "Return-Path", "Date"]:
        m = re.search(rf"^{fname}:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
        if m:
            field(fname + ":", m.group(1).strip())

    section("IP RILEVATI (Received)")
    ips = list(dict.fromkeys(re.findall(r"\[?(\d{1,3}(?:\.\d{1,3}){3})\]?", text)))
    for ip in ips[:10]:
        print(f"  {C.WHITE}{ip}{C.RESET}")

    section("AUTENTICAZIONE (SPF/DKIM/DMARC)")
    m = re.search(r"Authentication-Results:.*", text, re.IGNORECASE)
    if m:
        auth = m.group(0)
        for check in ["spf", "dkim", "dmarc"]:
            cm = re.search(rf"{check}=(\w+)", auth, re.IGNORECASE)
            if cm:
                result = cm.group(1)
                color = C.GREEN if result.lower() == "pass" else C.RED
                print(f"  {color}{check.upper()}: {result}{C.RESET}")
    else:
        print(f"{C.GRAY}Nessun campo Authentication-Results trovato.{C.RESET}")
    pause()


COMMON_DKIM_SELECTORS = ["default", "google", "selector1", "selector2", "k1", "mail", "dkim"]


def spf_dkim_dmarc_checker():
    print_banner()
    section("SPF / DKIM / DMARC CHECKER")
    domain = input(f"{C.YELLOW}Dominio: {C.RESET}").strip()
    ensure_tool_installed("nslookup", apt_package="dnsutils")

    section("SPF")
    out, _ = run_cmd(["nslookup", "-type=txt", domain])
    spf_found = False
    if out:
        for line in out.splitlines():
            if "v=spf1" in line:
                print(f"{C.GREEN}[+] {line.strip()}{C.RESET}")
                spf_found = True
    if not spf_found:
        print(f"{C.RED}[-] Nessun record SPF trovato.{C.RESET}")

    section("DMARC")
    out, _ = run_cmd(["nslookup", "-type=txt", f"_dmarc.{domain}"])
    dmarc_found = False
    if out:
        for line in out.splitlines():
            if "v=dmarc1" in line.lower():
                print(f"{C.GREEN}[+] {line.strip()}{C.RESET}")
                dmarc_found = True
    if not dmarc_found:
        print(f"{C.RED}[-] Nessun record DMARC trovato.{C.RESET}")

    section("DKIM (selettori comuni)")
    found_any = False
    for sel in COMMON_DKIM_SELECTORS:
        out, _ = run_cmd(["nslookup", "-type=txt", f"{sel}._domainkey.{domain}"])
        if out and "v=dkim1" in out.lower():
            print(f"{C.GREEN}[+] Selettore '{sel}' trovato{C.RESET}")
            found_any = True
    if not found_any:
        print(f"{C.GRAY}Nessun selettore comune trovato (potrebbe usarne uno custom).{C.RESET}")
    pause()


def asn_lookup():
    print_banner()
    section("ASN / IP RANGE LOOKUP")
    target = input(f"{C.YELLOW}IP o numero ASN (es. 15169 oppure AS15169): {C.RESET}").strip()
    asn = None
    if target.upper().startswith("AS") and target[2:].isdigit():
        asn = target[2:]
    elif target.isdigit():
        asn = target
    else:
        data, err = ip_lookup(target)
        if err:
            print(f"{C.RED}{err}{C.RESET}")
            pause()
            return
        m = re.match(r"AS(\d+)", data.get("as", ""))
        if m:
            asn = m.group(1)
            field("Organizzazione:", data.get("as"))
        else:
            print(f"{C.RED}Impossibile determinare l'ASN.{C.RESET}")
            pause()
            return

    try:
        r = requests.get(f"https://api.bgpview.io/asn/{asn}/prefixes", timeout=15)
        data = r.json()
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return

    section(f"PREFISSI IP DI AS{asn}")
    prefixes = data.get("data", {}).get("ipv4_prefixes", [])
    for p in prefixes[:40]:
        print(f"  {C.GREEN}{p['prefix']:<20}{C.RESET} {C.GRAY}{p.get('name','')}{C.RESET}")
    print(f"\n{C.BOLD}Totale prefissi IPv4:{C.RESET} {len(prefixes)}")
    pause()


def shodan_wrapper():
    print_banner()
    section("SHODAN WRAPPER")
    key = input(f"{C.YELLOW}La tua API key Shodan: {C.RESET}").strip()
    ip = input(f"{C.YELLOW}IP da controllare: {C.RESET}").strip()
    try:
        r = requests.get(f"https://api.shodan.io/shodan/host/{ip}", params={"key": key}, timeout=15)
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    if r.status_code != 200:
        print(f"{C.RED}Errore Shodan: HTTP {r.status_code}{C.RESET}")
        pause()
        return
    data = r.json()
    section("RISULTATO")
    field("Organizzazione:", data.get("org"))
    field("Sistema operativo:", data.get("os"))
    field("Paese:", data.get("country_name"))
    field("Porte aperte:", ", ".join(str(p) for p in data.get("ports", [])))
    vulns = data.get("vulns")
    if vulns:
        print(f"\n{C.RED}{C.BOLD}[!] Vulnerabilita' note: {', '.join(vulns)}{C.RESET}")
    pause()


def hibp_checker():
    print_banner()
    section("HIBP BREACH CHECKER")
    print(f"{C.GRAY}Richiede una API key HIBP (a pagamento) — controlla una singola email.{C.RESET}")
    print(f"{C.GRAY}Il controllo dell'intero dominio richiede verifica di proprieta' sul loro sito.{C.RESET}\n")
    key = input(f"{C.YELLOW}API key HIBP: {C.RESET}").strip()
    email = input(f"{C.YELLOW}Email da controllare: {C.RESET}").strip()
    try:
        r = requests.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}",
                          headers={"hibp-api-key": key, "User-Agent": "IceTool"},
                          params={"truncateResponse": "false"}, timeout=15)
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    if r.status_code == 404:
        print(f"{C.GREEN}[OK] Nessuna violazione trovata per questa email.{C.RESET}")
    elif r.status_code == 200:
        breaches = r.json()
        section(f"TROVATE {len(breaches)} VIOLAZIONI")
        for b in breaches:
            print(f"{C.RED}[!] {b['Name']} ({b['BreachDate']}) — dati esposti: {', '.join(b.get('DataClasses', []))}{C.RESET}")
    else:
        print(f"{C.RED}Errore HIBP: HTTP {r.status_code}{C.RESET}")
    pause()


# =========================================================
# RETE & SICUREZZA AVANZATA
# =========================================================
def traceroute_tool():
    print_banner()
    section("TRACEROUTE")
    host = input(f"{C.YELLOW}Host/IP di destinazione: {C.RESET}").strip()
    if os.name == "nt":
        cmd = ["tracert", host]
    else:
        ensure_tool_installed("traceroute", apt_package="traceroute")
        cmd = ["traceroute", host]
    print(f"\n{C.GRAY}Eseguo: {' '.join(cmd)} (puo' volerci un po'){C.RESET}\n")
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in proc.stdout:
            if line.strip():
                print(f"  {C.WHITE}{line.strip()}{C.RESET}")
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        print(f"\n{C.YELLOW}Interrotto.{C.RESET}")
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
    pause()


def ssl_cert_checker():
    print_banner()
    section("SSL/TLS CERTIFICATE CHECKER")
    host = input(f"{C.YELLOW}Dominio (senza https://): {C.RESET}").strip().replace("https://", "").replace("http://", "").split("/")[0]
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return

    section("CERTIFICATO")
    subject = dict(x[0] for x in cert.get("subject", []))
    issuer = dict(x[0] for x in cert.get("issuer", []))
    field("Dominio (CN):", subject.get("commonName", "?"))
    field("Emesso da:", issuer.get("commonName", "?"))
    not_after = cert.get("notAfter")
    field("Scade il:", not_after)
    try:
        expire_dt = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
        days_left = (expire_dt - datetime.utcnow()).days
        color = C.GREEN if days_left > 30 else (C.YELLOW if days_left > 0 else C.RED)
        print(f"\n  {color}{C.BOLD}Giorni rimanenti: {days_left}{C.RESET}")
    except Exception:
        pass
    pause()


def ssl_labs_scan():
    print_banner()
    section("SSL LABS SCAN")
    host = input(f"{C.YELLOW}Dominio da analizzare: {C.RESET}").strip().replace("https://", "").replace("http://", "").split("/")[0]
    print(f"\n{C.GRAY}Avvio scansione SSL Labs, puo' richiedere 1-2 minuti...{C.RESET}\n")
    data = {}
    try:
        for _ in range(20):
            r = requests.get("https://api.ssllabs.com/api/v3/analyze", params={"host": host, "all": "done"}, timeout=20)
            data = r.json()
            status = data.get("status")
            print(f"{C.GRAY}Stato: {status}...{C.RESET}")
            if status == "READY":
                break
            time.sleep(10)
        else:
            print(f"{C.YELLOW}Timeout in attesa del risultato.{C.RESET}")
            pause()
            return
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return

    section("RISULTATO")
    for ep in data.get("endpoints", []):
        grade = ep.get("grade", "?")
        color = C.GREEN if grade in ("A+", "A", "A-") else (C.YELLOW if grade.startswith("B") else C.RED)
        print(f"  {color}{C.BOLD}{ep.get('ipAddress')} -> Voto: {grade}{C.RESET}")
    pause()


PUBLIC_RESOLVERS = {"Google": "8.8.8.8", "Cloudflare": "1.1.1.1", "OpenDNS": "208.67.222.222", "Quad9": "9.9.9.9"}


def dns_propagation_checker():
    print_banner()
    section("DNS PROPAGATION CHECKER")
    domain = input(f"{C.YELLOW}Dominio: {C.RESET}").strip()
    ensure_tool_installed("nslookup", apt_package="dnsutils")
    for name, resolver in PUBLIC_RESOLVERS.items():
        out, _ = run_cmd(["nslookup", domain, resolver])
        section(f"{name} ({resolver})")
        found = False
        if out:
            for line in out.splitlines():
                if "Address" in line and resolver not in line:
                    print(f"  {C.GREEN}{line.strip()}{C.RESET}")
                    found = True
        if not found:
            print(f"  {C.RED}Nessuna risposta{C.RESET}")
    pause()


def cve_lookup():
    print_banner()
    section("CVE LOOKUP")
    query = input(f"{C.YELLOW}CVE ID (es. CVE-2021-44228) o parola chiave prodotto: {C.RESET}").strip()
    params = {"cveId": query} if query.upper().startswith("CVE-") else {"keywordSearch": query, "resultsPerPage": 10}
    try:
        r = requests.get("https://services.nvd.nist.gov/rest/json/cves/2.0", params=params, timeout=20)
        data = r.json()
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return

    vulns = data.get("vulnerabilities", [])
    if not vulns:
        print(f"{C.YELLOW}Nessun risultato.{C.RESET}")
        pause()
        return
    for v in vulns[:10]:
        cve = v["cve"]
        cid = cve["id"]
        desc = next((d["value"] for d in cve.get("descriptions", []) if d["lang"] == "en"), "")
        metrics = cve.get("metrics", {})
        score = "?"
        for key in ["cvssMetricV31", "cvssMetricV30", "cvssMetricV2"]:
            if key in metrics:
                score = metrics[key][0]["cvssData"]["baseScore"]
                break
        section(cid)
        field("CVSS score:", str(score))
        print(f"  {C.WHITE}{desc[:250]}{C.RESET}")
    pause()


def arp_scanner():
    print_banner()
    section("ARP SCANNER RETE LOCALE")
    print(f"{C.GRAY}Legge la tabella ARP del sistema (dispositivi gia' visti sulla rete locale).{C.RESET}\n")
    out, err = run_cmd(["arp", "-a"])
    if err:
        print(f"{C.RED}{err}{C.RESET}")
        pause()
        return
    section("DISPOSITIVI TROVATI")
    entries = re.findall(r"(\d{1,3}(?:\.\d{1,3}){3}).{0,20}?([0-9A-Fa-f]{2}[:\-](?:[0-9A-Fa-f]{2}[:\-]){4}[0-9A-Fa-f]{2})", out)
    seen = set()
    for ip, mac in entries:
        mac = mac.replace("-", ":").upper()
        if (ip, mac) in seen:
            continue
        seen.add((ip, mac))
        print(f"  {C.GREEN}{ip:<16}{C.RESET} {C.WHITE}{mac}{C.RESET}")
    if not seen:
        print(f"{C.GRAY}(output grezzo)\n{out[:1000]}{C.RESET}")
    pause()


def mac_vendor_lookup():
    print_banner()
    section("MAC VENDOR LOOKUP")
    mac = input(f"{C.YELLOW}Indirizzo MAC (es. AA:BB:CC:11:22:33): {C.RESET}").strip()
    try:
        r = requests.get(f"https://api.macvendors.com/{mac}", timeout=10)
        if r.status_code == 200:
            field("Vendor:", r.text)
        else:
            print(f"{C.RED}Vendor non trovato per questo MAC.{C.RESET}")
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
    pause()


def banner_grabbing():
    print_banner()
    section("BANNER GRABBING")
    host = input(f"{C.YELLOW}Host/IP: {C.RESET}").strip()
    port = ask_int(f"{C.YELLOW}Porta: {C.RESET}", 1, 65535)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((host, port))
            if port in (80, 8080, 8000):
                s.sendall(f"HEAD / HTTP/1.0\r\nHost: {host}\r\n\r\n".encode())
            banner = s.recv(1024)
        section("BANNER RICEVUTO")
        text = banner.decode("utf-8", errors="replace")
        if text.strip():
            for line in text.splitlines()[:20]:
                print(f"  {C.WHITE}{line}{C.RESET}")
        else:
            print(f"{C.GRAY}Nessun banner ricevuto (il servizio non invia nulla senza una richiesta specifica).{C.RESET}")
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
    pause()


def security_txt_checker():
    print_banner()
    section("SECURITY.TXT CHECKER")
    domain = input(f"{C.YELLOW}Dominio: {C.RESET}").strip().replace("https://", "").replace("http://", "").split("/")[0]
    for path in ["/.well-known/security.txt", "/security.txt"]:
        url = f"https://{domain}{path}"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200 and "ontact" in r.text:
                section(f"TROVATO: {url}")
                for line in r.text.splitlines():
                    if line.strip():
                        print(f"  {C.WHITE}{line.strip()}{C.RESET}")
                pause()
                return
        except Exception:
            continue
    print(f"{C.YELLOW}Nessun security.txt trovato su questo dominio.{C.RESET}")
    pause()


def firewall_status_viewer():
    print_banner()
    section("FIREWALL STATUS VIEWER")
    if os.name == "nt":
        out, err = run_cmd(["netsh", "advfirewall", "show", "allprofiles", "state"])
    else:
        if shutil.which("ufw"):
            print(f"{C.GRAY}Eseguo: sudo ufw status verbose (potrebbe chiedere la password){C.RESET}\n")
            result = subprocess.run(["sudo", "ufw", "status", "verbose"], capture_output=True, text=True)
        else:
            print(f"{C.GRAY}ufw non trovato, provo con iptables (sudo){C.RESET}\n")
            result = subprocess.run(["sudo", "iptables", "-L"], capture_output=True, text=True)
        out, err = result.stdout, None
    if err:
        print(f"{C.RED}{err}{C.RESET}")
    elif out:
        for line in out.splitlines():
            if line.strip():
                print(f"  {C.WHITE}{line.strip()}{C.RESET}")
    else:
        print(f"{C.YELLOW}Nessun output.{C.RESET}")
    pause()


def network_interfaces_info():
    print_banner()
    section("NETWORK INTERFACES INFO")
    if os.name == "nt":
        cmd = ["ipconfig", "/all"]
    else:
        cmd = ["ip", "addr"] if shutil.which("ip") else ["ifconfig"]
    out, err = run_cmd(cmd)
    if err:
        print(f"{C.RED}{err}{C.RESET}")
    else:
        for line in out.splitlines():
            if line.strip():
                print(f"  {C.WHITE}{line.strip()}{C.RESET}")
    pause()


# =========================================================
# OSINT AVANZATO (2)
# =========================================================
def wayback_viewer():
    print_banner()
    section("WAYBACK MACHINE SNAPSHOT VIEWER")
    url = input(f"{C.YELLOW}URL da cercare: {C.RESET}").strip()
    try:
        r = requests.get("http://archive.org/wayback/available", params={"url": url}, timeout=15)
        data = r.json()
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    snap = data.get("archived_snapshots", {}).get("closest")
    if not snap:
        print(f"{C.YELLOW}Nessuno snapshot trovato per questo URL.{C.RESET}")
        pause()
        return
    section("SNAPSHOT PIU' RECENTE")
    field("Data:", snap.get("timestamp"))
    field("URL archiviato:", snap.get("url"))
    field("Disponibile:", "si'" if snap.get("available") else "no")

    try:
        r2 = requests.get("http://web.archive.org/cdx/search/cdx",
                           params={"url": url, "output": "json", "limit": 10}, timeout=15)
        rows = r2.json()
        if len(rows) > 1:
            section("ALTRI SNAPSHOT (fino a 10)")
            for row in rows[1:]:
                print(f"  {C.GREEN}{row[1]}{C.RESET}")
    except Exception:
        pass
    pause()


def domain_reputation_aggregator():
    print_banner()
    section("DOMAIN REPUTATION AGGREGATOR")
    domain = input(f"{C.YELLOW}Dominio: {C.RESET}").strip().replace("https://", "").replace("http://", "").split("/")[0]

    ensure_tool_installed("whois", apt_package="whois")
    out, _ = run_cmd(["whois", domain])
    creation_date = None
    if out:
        m = re.search(r"Creation Date:\s*(\S+)", out, re.IGNORECASE)
        if m:
            creation_date = m.group(1)
            field("Data creazione:", creation_date)
            try:
                created = datetime.fromisoformat(creation_date.replace("Z", "+00:00")).replace(tzinfo=None)
                age_days = (datetime.utcnow() - created).days
                field("Eta' dominio:", f"{age_days} giorni (~{age_days//365} anni)")
                if age_days < 30:
                    print(f"\n{C.RED}{C.BOLD}[!] Dominio registrato da meno di 30 giorni — spesso un segnale da controllare con attenzione.{C.RESET}")
            except Exception:
                pass
    if not creation_date:
        print(f"{C.YELLOW}Data di creazione non trovata nel whois.{C.RESET}")

    try:
        ip = socket.gethostbyname(domain)
        data, err = ip_lookup(ip)
        if data:
            section("HOSTING")
            field("ISP/Org:", data.get("org"))
            field("Paese:", data.get("country"))
            field("Hosting/DC:", "si'" if data.get("hosting") else "no")
    except Exception:
        pass
    pause()


# =========================================================
# RETE & SICUREZZA (spostati qui perche' condivisi da piu' tool) helper aggiuntivi
# =========================================================
def redirect_chain_tracer():
    print_banner()
    section("REDIRECT CHAIN TRACER")
    url = input(f"{C.YELLOW}URL di partenza: {C.RESET}").strip()
    if not url.startswith("http"):
        url = "https://" + url
    try:
        resp = requests.get(url, timeout=15, allow_redirects=True, headers=UA)
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    section("CATENA DI REDIRECT")
    chain = list(resp.history) + [resp]
    for i, r in enumerate(chain):
        arrow = "  " if i == 0 else f"{C.GRAY}  -> {C.RESET}"
        print(f"{arrow}[{r.status_code}] {C.WHITE}{r.url}{C.RESET}")
    print(f"\n{C.BOLD}Destinazione finale:{C.RESET} {resp.url}")
    pause()


def robots_sitemap_viewer():
    print_banner()
    section("ROBOTS.TXT / SITEMAP.XML VIEWER")
    domain = input(f"{C.YELLOW}Dominio: {C.RESET}").strip().replace("https://", "").replace("http://", "").split("/")[0]

    section("ROBOTS.TXT")
    sitemaps = []
    try:
        r = requests.get(f"https://{domain}/robots.txt", timeout=10)
        if r.status_code == 200:
            for line in r.text.splitlines():
                print(f"  {C.WHITE}{line}{C.RESET}")
                if line.lower().startswith("sitemap:"):
                    sitemaps.append(line.split(":", 1)[1].strip())
        else:
            print(f"{C.YELLOW}robots.txt non trovato (HTTP {r.status_code}).{C.RESET}")
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")

    if sitemaps:
        section("SITEMAP TROVATE")
        for sm in sitemaps:
            try:
                r = requests.get(sm, timeout=10)
                urls_count = r.text.count("<loc>")
                print(f"  {C.GREEN}{sm}{C.RESET} {C.GRAY}({urls_count} URL dichiarati){C.RESET}")
            except Exception:
                print(f"  {C.RED}{sm} (non raggiungibile){C.RESET}")
    pause()


def typosquat_generator():
    print_banner()
    section("TYPOSQUATTING DOMAIN GENERATOR")
    domain = input(f"{C.YELLOW}Dominio da proteggere (es. example.com): {C.RESET}").strip()
    if "." not in domain:
        print(f"{C.RED}Formato dominio non valido.{C.RESET}")
        pause()
        return
    name, _, tld = domain.partition(".")
    variants = set()
    for i in range(len(name)):
        variants.add(name[:i] + name[i+1:] + "." + tld)  # omissione
        if i < len(name) - 1:
            variants.add(name[:i] + name[i+1] + name[i] + name[i+2:] + "." + tld)  # swap
    for c in "abcdefghijklmnopqrstuvwxyz0123456789-":
        variants.add(name + c + "." + tld)
    variants.add(name.replace("o", "0") + "." + tld)
    variants.add(name.replace("i", "1") + "." + tld)
    variants.discard(domain)

    section(f"CONTROLLO DI {len(variants)} VARIANTI (puo' volerci un momento)")
    registered = 0
    for v in sorted(variants)[:60]:
        try:
            socket.gethostbyname(v)
            print(f"{C.RED}[!] {v:<35} GIA' REGISTRATO{C.RESET}")
            registered += 1
        except socket.gaierror:
            pass
    print(f"\n{C.BOLD}Varianti gia' registrate trovate:{C.RESET} {registered} (su max 60 controllate)")
    pause()


def s3_bucket_checker():
    print_banner()
    section("PUBLIC S3 BUCKET NAME CHECKER")
    bucket = input(f"{C.YELLOW}Nome bucket da controllare: {C.RESET}").strip()
    url = f"http://{bucket}.s3.amazonaws.com"
    try:
        r = requests.get(url, timeout=10)
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    section("RISULTATO")
    field("URL:", url)
    field("Status:", str(r.status_code))
    if r.status_code == 200:
        print(f"\n{C.RED}{C.BOLD}[!] Il bucket esiste ed e' PUBBLICAMENTE LISTABILE.{C.RESET}")
    elif r.status_code == 403:
        print(f"\n{C.YELLOW}[?] Il bucket esiste ma non e' listabile pubblicamente (privato o permessi limitati).{C.RESET}")
    elif "NoSuchBucket" in r.text:
        print(f"\n{C.GREEN}[OK] Il bucket non esiste.{C.RESET}")
    else:
        print(f"\n{C.GRAY}Risultato ambiguo, controlla manualmente.{C.RESET}")
    pause()


def github_secrets_dork_generator():
    print_banner()
    section("GITHUB SECRETS DORK GENERATOR")
    print(f"{C.GRAY}Genera solo le query — non esegue ricerche automatiche.{C.RESET}\n")
    org = input(f"{C.YELLOW}Nome organizzazione o utente GitHub: {C.RESET}").strip()
    dorks = [
        f'org:{org} "api_key"', f'org:{org} "aws_secret"', f'org:{org} "AWS_ACCESS_KEY_ID"',
        f'org:{org} filename:.env', f'org:{org} "BEGIN RSA PRIVATE KEY"',
        f'org:{org} "password" filename:config', f'org:{org} "secret_key"',
        f'org:{org} extension:yml "token"', f'org:{org} "DATABASE_URL"',
    ]
    section("QUERY GENERATE (usale su github.com/search)")
    for d in dorks:
        print(f"  {C.GREEN}{d}{C.RESET}")
    pause()


def email_format_guesser():
    print_banner()
    section("COMPANY EMAIL FORMAT GUESSER")
    domain = input(f"{C.YELLOW}Dominio aziendale: {C.RESET}").strip()
    nome = input(f"{C.YELLOW}Nome: {C.RESET}").strip().lower()
    cognome = input(f"{C.YELLOW}Cognome: {C.RESET}").strip().lower()
    if not (nome and cognome and domain):
        print(f"{C.RED}Dati mancanti.{C.RESET}")
        pause()
        return
    formats = [
        f"{nome}.{cognome}@{domain}", f"{nome}{cognome}@{domain}",
        f"{nome[0]}{cognome}@{domain}", f"{nome}.{cognome[0]}@{domain}",
        f"{cognome}.{nome}@{domain}", f"{nome}@{domain}", f"{cognome}@{domain}",
        f"{nome[0]}.{cognome}@{domain}",
    ]
    section("FORMATI POSSIBILI")
    for f_ in formats:
        print(f"  {C.WHITE}{f_}{C.RESET}")
    pause()


def abuseipdb_checker():
    print_banner()
    section("ABUSEIPDB CHECKER")
    key = input(f"{C.YELLOW}API key AbuseIPDB (gratuita): {C.RESET}").strip()
    ip = input(f"{C.YELLOW}IP da controllare: {C.RESET}").strip()
    try:
        r = requests.get("https://api.abuseipdb.com/api/v2/check",
                          headers={"Key": key, "Accept": "application/json"},
                          params={"ipAddress": ip, "maxAgeInDays": 90}, timeout=15)
        data = r.json().get("data", {})
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    section("RISULTATO")
    field("Punteggio abuso:", f"{data.get('abuseConfidenceScore','?')}%")
    field("Segnalazioni totali:", str(data.get("totalReports", "?")))
    field("Paese:", data.get("countryCode", "?"))
    field("ISP:", data.get("isp", "?"))
    pause()


def urlscan_wrapper():
    print_banner()
    section("URLSCAN.IO WRAPPER")
    domain = input(f"{C.YELLOW}Dominio da cercare tra le scansioni pubbliche: {C.RESET}").strip()
    try:
        r = requests.get("https://urlscan.io/api/v1/search/", params={"q": f"domain:{domain}"}, timeout=15)
        results = r.json().get("results", [])
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    if not results:
        print(f"{C.YELLOW}Nessuna scansione pubblica trovata per questo dominio.{C.RESET}")
        pause()
        return
    section(f"TROVATE {len(results)} SCANSIONI (mostro le prime 5)")
    for res in results[:5]:
        page = res.get("page", {})
        print(f"  {C.GREEN}{res.get('task',{}).get('time')}{C.RESET} — IP: {page.get('ip','?')} — {res.get('result','')}")
    pause()


# =========================================================
# RETE & SICUREZZA AVANZATA (15)
# =========================================================
def open_redirect_tester():
    print_banner()
    section("OPEN REDIRECT TESTER")
    print(f"{C.YELLOW}Usa solo su siti tuoi/autorizzati.{C.RESET}\n")
    url = input(f"{C.YELLOW}URL completo da testare (con parametro di redirect gia' impostato, es. https://sito.com/redirect?url=https://evil-test.com): {C.RESET}").strip()
    test_host = input(f"{C.YELLOW}Dominio esterno atteso nel redirect (es. evil-test.com): {C.RESET}").strip()
    try:
        r = requests.get(url, timeout=10, allow_redirects=False, headers=UA)
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    section("RISULTATO")
    field("Status:", str(r.status_code))
    loc = r.headers.get("Location", "")
    field("Location:", loc or "(nessuna)")
    if loc and test_host in loc:
        print(f"\n{C.RED}{C.BOLD}[!] Open redirect confermato — reindirizza verso un dominio esterno controllabile.{C.RESET}")
    else:
        print(f"\n{C.GREEN}[OK] Non sembra vulnerabile a questo test.{C.RESET}")
    pause()


DIR_WORDLIST = ["admin", "login", "backup", "config", ".git/HEAD", ".env", "wp-admin",
                "api", "uploads", "test", "dashboard", "phpinfo.php", ".well-known",
                "server-status", "old", "dev", "staging", "database", "db", "logs",
                "robots.txt", "sitemap.xml", "swagger", "graphql", "actuator", "debug"]


def dir_bruteforce():
    print_banner()
    section("DIRECTORY / FILE BRUTE-FORCE SCANNER")
    print(f"{C.YELLOW}Usa SOLO su siti tuoi o per cui hai autorizzazione esplicita.{C.RESET}\n")
    base = input(f"{C.YELLOW}URL base (es. https://sito.com): {C.RESET}").strip().rstrip("/")

    def check(path):
        try:
            r = requests.get(f"{base}/{path}", timeout=6, headers=UA, allow_redirects=False)
            return path, r.status_code
        except Exception:
            return path, None

    section("RISULTATI")
    with ThreadPoolExecutor(max_workers=15) as executor:
        for path, status in executor.map(check, DIR_WORDLIST):
            if status is None:
                continue
            if status in (200, 301, 302, 403):
                color = C.GREEN if status == 200 else C.YELLOW
                print(f"{color}[+] /{path:<20} -> {status}{C.RESET}")
    pause()


def http_methods_tester():
    print_banner()
    section("HTTP METHODS TESTER")
    print(f"{C.RED}Attenzione: PUT/DELETE possono avere effetti reali se il server li accetta senza autenticazione.{C.RESET}")
    print(f"{C.YELLOW}Usa solo su siti tuoi/autorizzati.{C.RESET}\n")
    url = input(f"{C.YELLOW}URL da testare: {C.RESET}").strip()
    for method in ["GET", "HEAD", "OPTIONS", "POST", "PUT", "DELETE", "PATCH", "TRACE"]:
        try:
            r = requests.request(method, url, timeout=8, headers=UA)
            color = C.GREEN if r.status_code < 400 else C.GRAY
            print(f"{color}{method:<8} -> {r.status_code}{C.RESET}")
            if method == "OPTIONS" and "Allow" in r.headers:
                field("  Metodi dichiarati (Allow):", r.headers["Allow"])
        except Exception as e:
            print(f"{C.GRAY}{method:<8} -> errore ({e}){C.RESET}")
    pause()


def cookie_security_analyzer():
    print_banner()
    section("COOKIE SECURITY ANALYZER")
    url = input(f"{C.YELLOW}URL da controllare: {C.RESET}").strip()
    if not url.startswith("http"):
        url = "https://" + url
    try:
        r = requests.get(url, timeout=10, headers=UA)
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    try:
        raw_cookies = r.raw.headers.get_all("Set-Cookie") or []
    except Exception:
        raw_cookies = []
    if not raw_cookies:
        print(f"{C.YELLOW}Nessun cookie impostato da questa risposta.{C.RESET}")
        pause()
        return
    section("COOKIE TROVATI")
    for ck in raw_cookies:
        name = ck.split("=")[0]
        secure = "Secure" in ck
        httponly = "HttpOnly" in ck
        samesite = "SameSite" in ck
        print(f"\n  {C.WHITE}{C.BOLD}{name}{C.RESET}")
        print(f"    {'[+]' if secure else '[-]'} Secure   {'' if secure else C.RED}{'' if secure else '(manca)'}{C.RESET}")
        print(f"    {'[+]' if httponly else '[-]'} HttpOnly {'' if httponly else C.RED}{'' if httponly else '(manca)'}{C.RESET}")
        print(f"    {'[+]' if samesite else '[-]'} SameSite {'' if samesite else C.RED}{'' if samesite else '(manca)'}{C.RESET}")
    pause()


def cors_checker():
    print_banner()
    section("CORS MISCONFIGURATION CHECKER")
    url = input(f"{C.YELLOW}URL/endpoint da testare: {C.RESET}").strip()
    fake_origin = "https://icetool-cors-test.com"
    try:
        r = requests.get(url, headers={**UA, "Origin": fake_origin}, timeout=10)
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    acao = r.headers.get("Access-Control-Allow-Origin", "")
    acac = r.headers.get("Access-Control-Allow-Credentials", "")
    section("RISULTATO")
    field("Access-Control-Allow-Origin:", acao or "(assente)")
    field("Access-Control-Allow-Credentials:", acac or "(assente)")
    if acao == fake_origin or acao == "*":
        risk = f"{C.RED}{C.BOLD}[!] CORS permissivo"
        if acac.lower() == "true" and acao != "*":
            risk += " + credenziali abilitate — rischio ALTO (possibile furto dati autenticati da altri domini)"
        print(f"\n{risk}{C.RESET}")
    else:
        print(f"\n{C.GREEN}[OK] Non riflette origini arbitrarie.{C.RESET}")
    pause()


def sri_checker():
    print_banner()
    section("SRI (SUBRESOURCE INTEGRITY) CHECKER")
    url = input(f"{C.YELLOW}URL della pagina: {C.RESET}").strip()
    if not url.startswith("http"):
        url = "https://" + url
    try:
        html = requests.get(url, timeout=10, headers=UA).text
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    tags = re.findall(r'<(script|link)[^>]+(?:src|href)=["\']https?://[^"\']+["\'][^>]*>', html, re.IGNORECASE)
    external = re.findall(r'<(?:script|link)[^>]+(?:src|href)=["\'](https?://[^"\']+)["\'][^>]*>', html, re.IGNORECASE)
    missing = 0
    section("RISORSE ESTERNE")
    for full_tag_match, url_res in zip(tags, external):
        pass
    for m in re.finditer(r'<(script|link)[^>]*>', html, re.IGNORECASE):
        tag = m.group(0)
        if re.search(r'(src|href)=["\']https?://', tag) and "integrity=" not in tag:
            missing += 1
            src_m = re.search(r'(?:src|href)=["\']([^"\']+)["\']', tag)
            print(f"{C.YELLOW}[!] Senza integrity: {src_m.group(1) if src_m else '?'}{C.RESET}")
    if missing == 0:
        print(f"{C.GREEN}[OK] Tutte le risorse esterne rilevate hanno un attributo integrity (o nessuna risorsa esterna trovata).{C.RESET}")
    else:
        print(f"\n{C.BOLD}Totale senza SRI:{C.RESET} {missing}")
    pause()


def dns_axfr_test():
    print_banner()
    section("DNS ZONE TRANSFER TEST (AXFR)")
    domain = input(f"{C.YELLOW}Dominio: {C.RESET}").strip()
    if os.name == "nt":
        print(f"{C.YELLOW}Il comando 'dig' non e' nativo su Windows. Usa WSL o installa BIND tools.{C.RESET}")
        pause()
        return
    ensure_tool_installed("dig", apt_package="dnsutils")
    out, _ = run_cmd(["nslookup", "-type=ns", domain])
    nameservers = re.findall(r"nameserver\s*=\s*(\S+)", out or "", re.IGNORECASE)
    if not nameservers:
        print(f"{C.RED}Nameserver non trovati.{C.RESET}")
        pause()
        return
    for ns in nameservers:
        ns = ns.rstrip(".")
        section(f"TEST SU {ns}")
        out, _ = run_cmd(["dig", f"@{ns}", domain, "axfr"])
        if out and "Transfer failed" not in out and "connection timed out" not in out.lower() and len(out.splitlines()) > 5:
            print(f"{C.RED}{C.BOLD}[!] Zone transfer riuscito — configurazione DNS insicura!{C.RESET}")
            for line in out.splitlines()[:20]:
                print(f"  {C.WHITE}{line}{C.RESET}")
        else:
            print(f"{C.GREEN}[OK] Zone transfer negato (comportamento corretto).{C.RESET}")
    pause()


WAF_SIGNATURES = {
    "Cloudflare": ["cf-ray", "__cfduid"], "Sucuri": ["x-sucuri-id"],
    "Akamai": ["akamaighost", "x-akamai"], "Incapsula/Imperva": ["x-iinfo", "incap_ses"],
    "AWS WAF/CloudFront": ["x-amz-cf-id"], "F5 BIG-IP ASM": ["x-wa-info"],
}


def waf_detector():
    print_banner()
    section("WAF DETECTOR")
    url = input(f"{C.YELLOW}URL da testare: {C.RESET}").strip()
    if not url.startswith("http"):
        url = "https://" + url
    try:
        normal = requests.get(url, timeout=10, headers=UA)
        probe = requests.get(url, params={"test": "' OR '1'='1"}, timeout=10, headers=UA)
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return

    section("RILEVAMENTO")
    all_headers = " ".join(f"{k}:{v}" for k, v in normal.headers.items()).lower()
    found = []
    for waf, sigs in WAF_SIGNATURES.items():
        if any(s in all_headers for s in sigs):
            found.append(waf)
    for w in found:
        print(f"{C.GREEN}[+] Rilevato: {w}{C.RESET}")
    if not found:
        print(f"{C.GRAY}Nessuna firma WAF nota negli header.{C.RESET}")
    if probe.status_code in (403, 406, 419, 429) and normal.status_code == 200:
        print(f"{C.YELLOW}[?] La richiesta con payload sospetto e' stata bloccata (status {probe.status_code}) — probabile WAF attivo.{C.RESET}")
    pause()


def reverse_dns_lookup():
    print_banner()
    section("REVERSE DNS (rDNS) LOOKUP")
    ip = input(f"{C.YELLOW}IP da controllare: {C.RESET}").strip()
    try:
        host, _, _ = socket.gethostbyaddr(ip)
        field("Hostname (PTR):", host)
    except socket.herror:
        print(f"{C.YELLOW}Nessun record PTR trovato per questo IP.{C.RESET}")
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
    pause()


def tls_version_scanner():
    print_banner()
    section("TLS CIPHER SUITE / VERSION SCANNER")
    host = input(f"{C.YELLOW}Dominio (senza https://): {C.RESET}").strip().replace("https://", "").replace("http://", "").split("/")[0]

    versions = {"TLSv1.0": ssl.TLSVersion.TLSv1, "TLSv1.1": ssl.TLSVersion.TLSv1_1,
                "TLSv1.2": ssl.TLSVersion.TLSv1_2, "TLSv1.3": ssl.TLSVersion.TLSv1_3}
    section("VERSIONI SUPPORTATE")
    for name, ver in versions.items():
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.minimum_version = ver
            ctx.maximum_version = ver
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with socket.create_connection((host, 443), timeout=6) as sock:
                with ctx.wrap_socket(sock, server_hostname=host):
                    print(f"{C.GREEN}[+] {name} supportato{C.RESET}")
        except Exception:
            print(f"{C.RED}[-] {name} non supportato/rifiutato{C.RESET}")

    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cipher = ssock.cipher()
        section("CIFRARIO NEGOZIATO DI DEFAULT")
        field("Cipher:", cipher[0])
        field("Protocollo:", cipher[1])
    except Exception as e:
        print(f"{C.GRAY}Impossibile determinare il cifrario: {e}{C.RESET}")
    pause()


def upnp_discovery():
    print_banner()
    section("UPNP/SSDP DEVICE DISCOVERY")
    print(f"{C.GRAY}Cerco dispositivi UPnP sulla rete locale (5 secondi)...{C.RESET}\n")
    msg = "\r\n".join(["M-SEARCH * HTTP/1.1", "HOST: 239.255.255.250:1900",
                        'MAN: "ssdp:discover"', "MX: 3", "ST: ssdp:all", "", ""]).encode()
    sock_ = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_.settimeout(5)
    devices = {}
    try:
        sock_.sendto(msg, ("239.255.255.250", 1900))
        start = time.time()
        while time.time() - start < 5:
            try:
                data, addr = sock_.recvfrom(4096)
            except socket.timeout:
                break
            text = data.decode(errors="replace")
            loc_m = re.search(r"LOCATION:\s*(\S+)", text, re.IGNORECASE)
            devices[addr[0]] = loc_m.group(1) if loc_m else "?"
    finally:
        sock_.close()

    section("DISPOSITIVI TROVATI")
    if devices:
        for ip, loc in devices.items():
            print(f"  {C.GREEN}{ip:<16}{C.RESET} {C.GRAY}{loc}{C.RESET}")
    else:
        print(f"{C.YELLOW}Nessun dispositivo UPnP ha risposto.{C.RESET}")
    pause()


def port_conflict_checker():
    print_banner()
    section("PORT CONFLICT CHECKER (locale)")
    raw = input(f"{C.YELLOW}Porte da controllare separate da virgola (es. 80,443,3000,8080): {C.RESET}").strip()
    ports = [int(p) for p in raw.split(",") if p.strip().isdigit()]
    section("RISULTATO")
    for p in ports:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", p))
            print(f"{C.GREEN}[+] {p:<6} LIBERA{C.RESET}")
        except OSError:
            print(f"{C.RED}[-] {p:<6} GIA' OCCUPATA{C.RESET}")
        finally:
            s.close()
    pause()


def whois_history():
    print_banner()
    section("WHOIS STORICO (SecurityTrails)")
    key = input(f"{C.YELLOW}API key SecurityTrails: {C.RESET}").strip()
    domain = input(f"{C.YELLOW}Dominio: {C.RESET}").strip()
    try:
        r = requests.get(f"https://api.securitytrails.com/v1/history/{domain}/whois",
                          headers={"APIKEY": key}, timeout=15)
        data = r.json()
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    section("RISULTATO")
    records = data.get("result", {}).get("items", [])
    if not records:
        print(f"{C.YELLOW}Nessun dato storico trovato.{C.RESET}")
    for rec in records[:10]:
        print(f"  {C.GREEN}{rec}{C.RESET}")
    pause()


def http2_http3_checker():
    print_banner()
    section("HTTP/2 & HTTP/3 SUPPORT CHECKER")
    host = input(f"{C.YELLOW}Dominio (senza https://): {C.RESET}").strip().replace("https://", "").replace("http://", "").split("/")[0]

    section("HTTP/2 (via ALPN)")
    try:
        ctx = ssl.create_default_context()
        ctx.set_alpn_protocols(["h2", "http/1.1"])
        with socket.create_connection((host, 443), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                proto = ssock.selected_alpn_protocol()
        print(f"{C.GREEN}[+] Supportato{C.RESET}" if proto == "h2" else f"{C.YELLOW}[-] Non negoziato (probabile solo HTTP/1.1){C.RESET}")
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")

    section("HTTP/3 (indicazione da header Alt-Svc)")
    try:
        r = requests.get(f"https://{host}", timeout=10, headers=UA)
        alt = r.headers.get("Alt-Svc", "")
        if "h3" in alt:
            print(f"{C.GREEN}[+] Il server annuncia HTTP/3: {alt}{C.RESET}")
        else:
            print(f"{C.GRAY}Nessun annuncio h3 nell'header Alt-Svc.{C.RESET}")
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
    pause()


def subnet_calculator():
    print_banner()
    section("SUBNET CALCULATOR")
    cidr = input(f"{C.YELLOW}Rete in formato CIDR (es. 192.168.1.0/24): {C.RESET}").strip()
    try:
        net = ipaddress.ip_network(cidr, strict=False)
    except ValueError as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    section("RISULTATO")
    field("Indirizzo di rete:", str(net.network_address))
    if net.version == 4:
        field("Broadcast:", str(net.broadcast_address))
    field("Netmask:", str(net.netmask))
    field("Numero indirizzi totali:", str(net.num_addresses))
    hosts = list(net.hosts())
    if hosts:
        field("Primo host utilizzabile:", str(hosts[0]))
        field("Ultimo host utilizzabile:", str(hosts[-1]))
        field("Host utilizzabili:", str(len(hosts)))
    pause()


# =========================================================
# SVILUPPO & PROGRAMMAZIONE (12)
# =========================================================
def jwt_decoder():
    print_banner()
    section("JWT DECODER")
    token = input(f"{C.YELLOW}Token JWT: {C.RESET}").strip()
    parts = token.split(".")
    if len(parts) < 2:
        print(f"{C.RED}Non sembra un JWT valido.{C.RESET}")
        pause()
        return

    def decode_part(p):
        padded = p + "=" * (-len(p) % 4)
        try:
            return json.loads(base64.urlsafe_b64decode(padded))
        except Exception:
            return None

    header, payload = decode_part(parts[0]), decode_part(parts[1])
    section("HEADER")
    print(f"  {C.WHITE}{json.dumps(header, indent=2, ensure_ascii=False)}{C.RESET}" if header else f"  {C.RED}Errore nella decodifica{C.RESET}")
    section("PAYLOAD")
    print(f"  {C.WHITE}{json.dumps(payload, indent=2, ensure_ascii=False)}{C.RESET}" if payload else f"  {C.RED}Errore nella decodifica{C.RESET}")
    print(f"\n{C.GRAY}Nota: la firma NON viene verificata, solo decodificata.{C.RESET}")
    pause()


def http_status_lookup():
    print_banner()
    section("HTTP STATUS CODE LOOKUP")
    code = ask_int(f"{C.YELLOW}Codice HTTP (100-599): {C.RESET}", 100, 599)
    try:
        st = HTTPStatus(code)
        field("Nome:", st.phrase)
        field("Descrizione:", st.description)
    except ValueError:
        print(f"{C.YELLOW}Codice non standard/non registrato, ma potrebbe comunque esistere (custom).{C.RESET}")
    pause()


def dockerfile_linter():
    print_banner()
    section("DOCKERFILE LINTER")
    path = input(f"{C.YELLOW}Percorso del Dockerfile: {C.RESET}").strip()
    if not os.path.isfile(path):
        print(f"{C.RED}File non trovato.{C.RESET}")
        pause()
        return
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    issues = []
    for i, l in enumerate(lines, 1):
        s = l.strip()
        if re.match(r"(?i)^FROM\s+\S+:latest", s):
            issues.append((i, "Uso del tag 'latest' — non riproducibile, meglio fissare una versione"))
        if s.upper().startswith("ADD ") and "http" not in s.lower():
            issues.append((i, "Uso di ADD per file locali — meglio COPY"))
        if s.upper().startswith("ENV") and re.search(r"(?i)(PASSWORD|SECRET|API_KEY|TOKEN)\s*=", s):
            issues.append((i, "Possibile segreto hardcoded in ENV"))
    if not any(l.strip().upper().startswith("USER ") for l in lines):
        issues.append((0, "Nessuna istruzione USER — il container girera' come root"))

    section("RISULTATO")
    if not issues:
        print(f"{C.GREEN}[OK] Nessun problema rilevato.{C.RESET}")
    for ln, msg in issues:
        loc = f"riga {ln}" if ln else "generale"
        print(f"{C.YELLOW}[!] {loc}: {msg}{C.RESET}")
    pause()


SECRET_PATTERNS = [
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Generic API Key", re.compile(r"(?i)api[_-]?key['\"]?\s*[:=]\s*['\"][0-9a-zA-Z\-_]{16,}['\"]")),
    ("Slack Token", re.compile(r"xox[baprs]-[0-9a-zA-Z-]{10,}")),
    ("Private Key Header", re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("Generic Password", re.compile(r"(?i)password\s*[:=]\s*['\"].{4,}['\"]")),
    ("Google API Key", re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
]


def git_secrets_scanner():
    print_banner()
    section("GIT REPO SECRETS SCANNER")
    folder = input(f"{C.YELLOW}Percorso cartella/repo (invio = corrente): {C.RESET}").strip() or "."
    if not os.path.isdir(folder):
        print(f"{C.RED}Cartella non trovata.{C.RESET}")
        pause()
        return
    section("SCANSIONE IN CORSO")
    found = 0
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "venv", "__pycache__")]
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "rb") as f:
                    chunk = f.read(2_000_000)
                if b"\x00" in chunk[:8192]:
                    continue
                text = chunk.decode("utf-8", errors="ignore")
            except Exception:
                continue
            for label, pattern in SECRET_PATTERNS:
                for m in pattern.finditer(text):
                    line_no = text[:m.start()].count("\n") + 1
                    print(f"{C.RED}[!] {os.path.relpath(fpath, folder)}:{line_no} -> {label}{C.RESET}")
                    found += 1
    print(f"\n{C.BOLD}Trovati {found} possibili segreti.{C.RESET}" if found else f"\n{C.GREEN}Nessun segreto rilevato.{C.RESET}")
    pause()


def license_checker():
    print_banner()
    section("LICENSE CHECKER DIPENDENZE")
    path = input(f"{C.YELLOW}Percorso requirements.txt o package.json: {C.RESET}").strip()
    if not os.path.isfile(path):
        print(f"{C.RED}File non trovato.{C.RESET}")
        pause()
        return
    section("LICENZE")
    if path.endswith("requirements.txt"):
        with open(path) as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        for line in lines:
            m = re.match(r"^([A-Za-z0-9_\-.]+)", line)
            if not m:
                continue
            pkg = m.group(1)
            try:
                info = requests.get(f"https://pypi.org/pypi/{pkg}/json", timeout=8).json()["info"]
                lic = info.get("license") or "sconosciuta"
                print(f"  {C.WHITE}{pkg:<25}{C.RESET} {C.GRAY}{lic[:50]}{C.RESET}")
            except Exception:
                print(f"  {C.GRAY}{pkg:<25} errore{C.RESET}")
    elif path.endswith("package.json"):
        with open(path) as f:
            data = json.load(f)
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        for pkg in deps:
            try:
                r = requests.get(f"https://registry.npmjs.org/{pkg}/latest", timeout=8)
                lic = r.json().get("license", "sconosciuta")
                print(f"  {C.WHITE}{pkg:<25}{C.RESET} {C.GRAY}{lic}{C.RESET}")
            except Exception:
                print(f"  {C.GRAY}{pkg:<25} errore{C.RESET}")
    else:
        print(f"{C.RED}Formato non supportato.{C.RESET}")
    pause()


def pip_vuln_scanner():
    print_banner()
    section("LOCAL PIP VULNERABILITY SCANNER (OSV.dev)")
    path = input(f"{C.YELLOW}Percorso requirements.txt: {C.RESET}").strip()
    if not os.path.isfile(path):
        print(f"{C.RED}File non trovato.{C.RESET}")
        pause()
        return
    with open(path) as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    section("RISULTATO")
    for line in lines:
        m = re.match(r"^([A-Za-z0-9_\-.]+)\s*==\s*([A-Za-z0-9_.\-]+)", line)
        if not m:
            print(f"{C.GRAY}[?] {line} — versione non fissata, salto{C.RESET}")
            continue
        pkg, ver = m.group(1), m.group(2)
        try:
            r = requests.post("https://api.osv.dev/v1/query",
                               json={"package": {"name": pkg, "ecosystem": "PyPI"}, "version": ver}, timeout=10)
            vulns = r.json().get("vulns", [])
        except Exception as e:
            print(f"{C.GRAY}[?] {pkg} errore: {e}{C.RESET}")
            continue
        if vulns:
            for v in vulns:
                print(f"{C.RED}[!] {pkg}=={ver} -> {v.get('id')}{C.RESET}")
        else:
            print(f"{C.GREEN}[OK] {pkg}=={ver} nessuna vulnerabilita' nota{C.RESET}")
        time.sleep(0.2)
    pause()


def api_tester():
    print_banner()
    section("API TESTER (mini Postman da terminale)")
    method = (input(f"{C.YELLOW}Metodo (GET/POST/PUT/DELETE/PATCH) [GET]: {C.RESET}").strip().upper() or "GET")
    url = input(f"{C.YELLOW}URL: {C.RESET}").strip()
    print(f"{C.GRAY}Header custom (formato Chiave: Valore), riga vuota per finire:{C.RESET}")
    headers = {}
    while True:
        line = input()
        if not line:
            break
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()
    body = None
    if method in ("POST", "PUT", "PATCH"):
        body = input(f"{C.YELLOW}Body (JSON o testo, invio per vuoto): {C.RESET}").strip() or None

    try:
        start = time.time()
        resp = requests.request(method, url, headers=headers, data=body, timeout=15)
        elapsed = (time.time() - start) * 1000
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return

    section("RISPOSTA")
    field("Status:", str(resp.status_code))
    field("Tempo:", f"{elapsed:.0f} ms")
    section("HEADER")
    for k, v in resp.headers.items():
        field(k + ":", v)
    section("BODY (anteprima)")
    print(f"  {C.WHITE}{resp.text[:1000]}{C.RESET}")
    pause()


DOW_NAMES = {"0": "domenica", "1": "lunedi'", "2": "martedi'", "3": "mercoledi'",
             "4": "giovedi'", "5": "venerdi'", "6": "sabato", "7": "domenica"}


def cron_explainer():
    print_banner()
    section("CRON EXPRESSION EXPLAINER")
    expr = input(f"{C.YELLOW}Espressione cron (5 campi, es. 0 5 * * 1): {C.RESET}").strip()
    parts = expr.split()
    if len(parts) != 5:
        print(f"{C.RED}Servono esattamente 5 campi (minuto ora giorno mese giorno-settimana).{C.RESET}")
        pause()
        return
    minute, hour, dom, month, dow = parts
    desc = []
    if minute == "*" and hour == "*":
        desc.append("ogni minuto")
    elif minute.startswith("*/"):
        desc.append(f"ogni {minute[2:]} minuti")
    elif minute.isdigit() and hour.isdigit():
        desc.append(f"alle {hour.zfill(2)}:{minute.zfill(2)}")
    else:
        desc.append(f"minuto={minute} ora={hour}")
    if dom != "*":
        desc.append(f"il giorno {dom} del mese")
    if month != "*":
        desc.append(f"nel mese {month}")
    if dow != "*":
        names = [DOW_NAMES.get(d, d) for d in dow.split(",")]
        desc.append("di " + "/".join(names))
    section("SPIEGAZIONE")
    print(f"  {C.GREEN}Esegue {', '.join(desc)}.{C.RESET}")
    pause()


def markdown_checker():
    print_banner()
    section("MARKDOWN CHECKER")
    path = input(f"{C.YELLOW}Percorso file .md: {C.RESET}").strip()
    if not os.path.isfile(path):
        print(f"{C.RED}File non trovato.{C.RESET}")
        pause()
        return
    text = open(path, encoding="utf-8", errors="replace").read()
    headings = re.findall(r"^(#+)\s+(.+)$", text, re.MULTILINE)
    section("HEADING TROVATI")
    seen, dupes = set(), 0
    for level, title in headings:
        marker = f"{C.RED}[dup]{C.RESET}" if title in seen else ""
        if title in seen:
            dupes += 1
        seen.add(title)
        print(f"  {'  ' * (len(level) - 1)}{C.WHITE}{title}{C.RESET} {marker}")

    links = re.findall(r"\[[^\]]+\]\((https?://[^\)]+)\)", text)
    section(f"LINK TROVATI ({len(links)}, controllo i primi 30)")
    broken = 0
    for link in links[:30]:
        try:
            r = requests.head(link, timeout=6, allow_redirects=True)
            ok = r.status_code < 400
        except Exception:
            ok = False
        if not ok:
            broken += 1
        print(f"  {C.GREEN if ok else C.RED}{link}{C.RESET}")
    print(f"\n{C.BOLD}Heading duplicati:{C.RESET} {dupes}   {C.BOLD}Link rotti:{C.RESET} {broken}/{min(len(links),30)}")
    pause()


SQL_KEYWORDS = ["SELECT", "FROM", "WHERE", "LEFT JOIN", "RIGHT JOIN", "INNER JOIN", "JOIN",
                "GROUP BY", "ORDER BY", "HAVING", "INSERT INTO", "VALUES", "UPDATE", "SET",
                "DELETE FROM", "AND", "OR", "LIMIT", "UNION"]


def sql_formatter():
    print_banner()
    section("SQL QUERY FORMATTER")
    print(f"{C.GRAY}Incolla la query, riga vuota per terminare:{C.RESET}")
    lines = []
    while True:
        try:
            l = input()
        except EOFError:
            break
        if l == "":
            break
        lines.append(l)
    sql = " ".join(lines)
    if not sql:
        print(f"{C.RED}Nessuna query inserita.{C.RESET}")
        pause()
        return
    for kw in sorted(SQL_KEYWORDS, key=len, reverse=True):
        sql = re.sub(rf"(?i)\b{re.escape(kw)}\b", f"\n{kw.upper()}", sql)
    section("RISULTATO FORMATTATO")
    for line in sql.strip().splitlines():
        if line.strip():
            print(f"  {C.WHITE}{line.strip()}{C.RESET}")
    pause()


def changelog_generator():
    print_banner()
    section("CHANGELOG GENERATOR DA GIT LOG")
    folder = input(f"{C.YELLOW}Percorso repo git (invio = corrente): {C.RESET}").strip() or "."
    if not ensure_tool_installed("git", apt_package="git"):
        pause()
        return
    result = subprocess.run(["git", "log", "--pretty=format:%h|%ad|%s", "--date=short", "-n", "60"],
                             cwd=folder, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"{C.RED}{result.stderr.strip()}{C.RESET}")
        pause()
        return
    section("CHANGELOG (ultimi 60 commit)")
    last_date = None
    for line in result.stdout.splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        h, d, msg = parts
        if d != last_date:
            print(f"\n{BLUE}{C.BOLD}## {d}{C.RESET}")
            last_date = d
        print(f"  - {msg} {C.GRAY}({h}){C.RESET}")
    pause()


def webhook_tester():
    print_banner()
    section("WEBHOOK TESTER LOCALE")
    port = ask_int(f"{C.YELLOW}Porta locale su cui ascoltare: {C.RESET}", 1024, 65535)
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def _handle(self):
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(length) if length else b""
            print(f"\n{BLUE}{C.BOLD}>> {self.command} {self.path}{C.RESET}")
            for k, v in self.headers.items():
                print(f"  {C.GRAY}{k}: {v}{C.RESET}")
            if body:
                print(f"  {C.WHITE}Body: {body[:500]}{C.RESET}")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

        do_GET = do_POST = do_PUT = do_DELETE = _handle

        def log_message(self, *args):
            pass

    print(f"\n{C.GREEN}In ascolto su http://localhost:{port} (CTRL+C per fermare){C.RESET}\n")
    server = HTTPServer(("0.0.0.0", port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}Fermato.{C.RESET}")
    pause()


# =========================================================
# CRYPTO (6)
# =========================================================
B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def base58_decode(s):
    num = 0
    for char in s:
        num = num * 58 + B58_ALPHABET.index(char)
    combined = num.to_bytes((num.bit_length() + 7) // 8, "big") if num else b""
    n_leading = len(s) - len(s.lstrip("1"))
    return b"\x00" * n_leading + combined


def validate_base58check(addr):
    try:
        raw = base58_decode(addr)
        if len(raw) < 5:
            return False
        payload, checksum = raw[:-4], raw[-4:]
        h = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
        return h == checksum
    except Exception:
        return False


BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def bech32_polymod(values):
    GEN = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3]
    chk = 1
    for v in values:
        b = chk >> 25
        chk = (chk & 0x1ffffff) << 5 ^ v
        for i in range(5):
            chk ^= GEN[i] if ((b >> i) & 1) else 0
    return chk


def bech32_hrp_expand(hrp):
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def validate_bech32(addr):
    try:
        addr = addr.lower()
        hrp, data_part = addr.rsplit("1", 1)
        data = [BECH32_CHARSET.index(c) for c in data_part]
        return bech32_polymod(bech32_hrp_expand(hrp) + data) == 1
    except Exception:
        return False


CRYPTO_PATTERNS = [
    ("Bitcoin (Legacy P2PKH)", re.compile(r"^1[a-km-zA-HJ-NP-Z1-9]{25,34}$"), "base58"),
    ("Bitcoin (P2SH)", re.compile(r"^3[a-km-zA-HJ-NP-Z1-9]{25,34}$"), "base58"),
    ("Bitcoin (Bech32/SegWit)", re.compile(r"^bc1[a-z0-9]{25,60}$"), "bech32"),
    ("Ethereum / EVM (ETH, BNB, MATIC, ecc.)", re.compile(r"^0x[a-fA-F0-9]{40}$"), "hex"),
    ("Litecoin", re.compile(r"^[LM][a-km-zA-HJ-NP-Z1-9]{25,34}$"), "base58"),
    ("Litecoin (Bech32)", re.compile(r"^ltc1[a-z0-9]{25,60}$"), "bech32"),
    ("Dogecoin", re.compile(r"^D[5-9A-HJ-NP-U][1-9A-HJ-NP-Za-km-z]{32}$"), "base58"),
    ("Ripple (XRP)", re.compile(r"^r[a-zA-Z0-9]{24,34}$"), "none"),
    ("Tron (TRX)", re.compile(r"^T[a-zA-Z0-9]{33}$"), "base58"),
    ("Solana", re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$"), "none"),
    ("Monero", re.compile(r"^4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}$"), "none"),
]


def wallet_address_checker():
    print_banner()
    section("CRYPTO WALLET ADDRESS CHECKER")
    addr = input(f"{C.YELLOW}Indirizzo wallet: {C.RESET}").strip()
    matches = [(name, kind) for name, pattern, kind in CRYPTO_PATTERNS if pattern.match(addr)]
    if not matches:
        print(f"{C.RED}Formato non riconosciuto tra le valute supportate.{C.RESET}")
        pause()
        return
    section("RISULTATO")
    for name, kind in matches:
        print(f"{C.GREEN}[+] Formato compatibile con: {name}{C.RESET}")
        if kind == "base58":
            valid = validate_base58check(addr)
            print(f"    Checksum base58: {C.GREEN+'valido' if valid else C.RED+'NON valido'}{C.RESET}")
        elif kind == "bech32":
            valid = validate_bech32(addr)
            print(f"    Checksum bech32: {C.GREEN+'valido' if valid else C.RED+'NON valido'}{C.RESET}")
        elif kind == "hex":
            print(f"    {C.GRAY}Formato esadecimale corretto (checksum EIP-55 non verificabile senza libreria keccak).{C.RESET}")
    pause()


def blockchain_explorer_wrapper():
    print_banner()
    section("BLOCKCHAIN EXPLORER WRAPPER")
    addr = input(f"{C.YELLOW}Indirizzo BTC o ETH: {C.RESET}").strip()
    if addr.startswith("0x") and len(addr) == 42:
        key = input(f"{C.YELLOW}API key Etherscan (gratuita, invio per saltare): {C.RESET}").strip()
        if not key:
            print(f"{C.YELLOW}Serve una API key Etherscan per controllare indirizzi ETH.{C.RESET}")
            pause()
            return
        try:
            r = requests.get("https://api.etherscan.io/api",
                              params={"module": "account", "action": "balance", "address": addr,
                                      "tag": "latest", "apikey": key}, timeout=10)
            wei = int(r.json().get("result", "0"))
            field("Saldo:", f"{wei/1e18:.6f} ETH")
        except Exception as e:
            print(f"{C.RED}Errore: {e}{C.RESET}")
    else:
        try:
            r = requests.get(f"https://blockchain.info/rawaddr/{addr}", params={"limit": 0}, timeout=15)
            data = r.json()
            field("Saldo:", f"{data.get('final_balance',0)/1e8:.8f} BTC")
            field("N. transazioni:", str(data.get("n_tx", 0)))
        except Exception as e:
            print(f"{C.RED}Errore: {e}{C.RESET}")
    pause()


def gas_fee_estimator():
    print_banner()
    section("GAS FEE ESTIMATOR (Ethereum)")
    key = input(f"{C.YELLOW}API key Etherscan: {C.RESET}").strip()
    try:
        r = requests.get("https://api.etherscan.io/api",
                          params={"module": "gastracker", "action": "gasoracle", "apikey": key}, timeout=10)
        result = r.json().get("result", {})
        field("Safe (gwei):", result.get("SafeGasPrice", "?"))
        field("Standard (gwei):", result.get("ProposeGasPrice", "?"))
        field("Fast (gwei):", result.get("FastGasPrice", "?"))
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
    pause()


def crypto_price_aggregator():
    print_banner()
    section("CRYPTO PRICE AGGREGATOR")
    coins = input(f"{C.YELLOW}ID monete separati da virgola (es. bitcoin,ethereum): {C.RESET}").strip()
    currencies = input(f"{C.YELLOW}Valute separate da virgola [usd,eur]: {C.RESET}").strip() or "usd,eur"
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price",
                          params={"ids": coins, "vs_currencies": currencies}, timeout=10)
        data = r.json()
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    section("PREZZI")
    for coin, prices in data.items():
        for cur, val in prices.items():
            print(f"  {C.GREEN}{coin:<15}{C.RESET} {cur.upper()}: {C.WHITE}{val}{C.RESET}")
    pause()


def smart_contract_verification_checker():
    print_banner()
    section("SMART CONTRACT VERIFICATION CHECKER")
    key = input(f"{C.YELLOW}API key Etherscan: {C.RESET}").strip()
    addr = input(f"{C.YELLOW}Indirizzo contratto: {C.RESET}").strip()
    try:
        r = requests.get("https://api.etherscan.io/api",
                          params={"module": "contract", "action": "getabi", "address": addr, "apikey": key}, timeout=10)
        result = r.json().get("result", "")
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    section("RISULTATO")
    if "not verified" in result.lower():
        print(f"{C.RED}[-] Contratto NON verificato.{C.RESET}")
    else:
        print(f"{C.GREEN}[+] Contratto verificato — ABI disponibile.{C.RESET}")
    pause()


def wallet_flag_checker():
    print_banner()
    section("WALLET FLAG CHECKER")
    addr = input(f"{C.YELLOW}Indirizzo da controllare: {C.RESET}").strip()
    print(f"{C.GRAY}Database community-driven, copertura limitata — esito negativo non e' garanzia.{C.RESET}\n")
    try:
        r = requests.get(f"https://api.cryptoscamdb.org/v1/check/{addr}", timeout=15)
        result = r.json().get("result", {})
        status = result.get("status", "unknown")
        if status == "blocked":
            print(f"{C.RED}{C.BOLD}[!] Segnalato come scam/malevolo nel database.{C.RESET}")
        elif status == "whitelisted":
            print(f"{C.GREEN}[OK] Whitelisted.{C.RESET}")
        else:
            print(f"{C.GRAY}Non presente nel database (nessuna informazione).{C.RESET}")
    except Exception as e:
        print(f"{C.RED}Servizio non raggiungibile: {e}{C.RESET}")
    pause()


# =========================================================
# SISTEMA & DIFESA (10)
# =========================================================
SENSITIVE_DOMAINS = ["google.com", "facebook.com", "microsoft.com", "paypal.com",
                      "apple.com", "amazon.com", "instagram.com"]


def hosts_file_inspector():
    print_banner()
    section("HOSTS FILE INSPECTOR")
    path = r"C:\Windows\System32\drivers\etc\hosts" if os.name == "nt" else "/etc/hosts"
    if not os.path.isfile(path):
        print(f"{C.RED}File hosts non trovato.{C.RESET}")
        pause()
        return
    section(f"CONTENUTO ({path})")
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            print(f"  {C.WHITE}{s}{C.RESET}")
            for dom in SENSITIVE_DOMAINS:
                if dom in s and "127.0.0.1" not in s and "::1" not in s:
                    print(f"    {C.RED}{C.BOLD}[!] Attenzione: '{dom}' reindirizzato manualmente — verifica se e' voluto.{C.RESET}")
    pause()


def scheduled_tasks_viewer():
    print_banner()
    section("SCHEDULED TASKS / CRON VIEWER")
    if os.name == "nt":
        out, err = run_cmd(["schtasks", "/query", "/fo", "LIST"])
    else:
        out, err = run_cmd(["crontab", "-l"])
    if err:
        print(f"{C.GRAY}{err}{C.RESET}")
    elif out:
        for line in out.splitlines()[:100]:
            if line.strip():
                print(f"  {C.WHITE}{line.strip()}{C.RESET}")
    else:
        print(f"{C.GRAY}Nessun task pianificato trovato.{C.RESET}")
    pause()


SUSPICIOUS_PATH_HINTS = ["temp", "tmp", "appdata\\local\\temp", "/tmp/", "downloads"]


def suspicious_processes_scanner():
    print_banner()
    section("PROCESSI IN ESECUZIONE — EURISTICA BASE")
    cmd = ["tasklist", "/v"] if os.name == "nt" else ["ps", "aux"]
    out, err = run_cmd(cmd)
    if err:
        print(f"{C.RED}{err}{C.RESET}")
        pause()
        return
    flagged = 0
    for line in out.splitlines():
        low = line.lower()
        if any(h in low for h in SUSPICIOUS_PATH_HINTS):
            print(f"{C.YELLOW}[?] {line.strip()}{C.RESET}")
            flagged += 1
    print(f"\n{C.BOLD}Processi segnalati:{C.RESET} {flagged}" if flagged else f"\n{C.GREEN}Nessun indizio con questa euristica base.{C.RESET}")
    print(f"{C.GRAY}Nota: euristica semplice, possibili falsi positivi/negativi.{C.RESET}")
    pause()


def usb_device_history():
    print_banner()
    section("USB DEVICE HISTORY")
    if os.name == "nt":
        out, err = run_cmd(["reg", "query", r"HKLM\SYSTEM\CurrentControlSet\Enum\USBSTOR", "/s"])
    else:
        out, err = run_cmd(["dmesg"])
        if out:
            out = "\n".join(l for l in out.splitlines() if "usb" in l.lower())
    if err:
        print(f"{C.RED}{err}{C.RESET}")
    elif out:
        for line in out.splitlines()[:80]:
            if line.strip():
                print(f"  {C.WHITE}{line.strip()}{C.RESET}")
    else:
        print(f"{C.GRAY}Nessun dato trovato (su Linux potrebbe servire sudo per dmesg).{C.RESET}")
    pause()


def file_integrity_monitor():
    print_banner()
    section("FILE INTEGRITY MONITOR")
    folder = input(f"{C.YELLOW}Percorso cartella da monitorare: {C.RESET}").strip()
    if not os.path.isdir(folder):
        print(f"{C.RED}Cartella non trovata.{C.RESET}")
        pause()
        return

    snapshot_path = os.path.join(folder, ".icetool_snapshot.json")
    current = {}
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d != ".git"]
        for fname in files:
            if fname == ".icetool_snapshot.json":
                continue
            fpath = os.path.join(root, fname)
            try:
                h = hashlib.sha256()
                with open(fpath, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        h.update(chunk)
                current[os.path.relpath(fpath, folder)] = h.hexdigest()
            except Exception:
                continue

    if os.path.isfile(snapshot_path):
        with open(snapshot_path) as f:
            old = json.load(f)
        added = set(current) - set(old)
        removed = set(old) - set(current)
        modified = [p for p in current if p in old and current[p] != old[p]]
        section("CONFRONTO CON L'ISTANTANEA PRECEDENTE")
        for p in added:
            print(f"{C.GREEN}[+] Aggiunto: {p}{C.RESET}")
        for p in removed:
            print(f"{C.RED}[-] Rimosso: {p}{C.RESET}")
        for p in modified:
            print(f"{C.YELLOW}[~] Modificato: {p}{C.RESET}")
        if not (added or removed or modified):
            print(f"{C.GREEN}Nessuna modifica rilevata.{C.RESET}")
    else:
        section("BASELINE CREATA")
        print(f"{C.GREEN}Salvata istantanea di {len(current)} file.{C.RESET}")

    with open(snapshot_path, "w") as f:
        json.dump(current, f)
    pause()


CLIPBOARD_PATTERNS = [
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Private Key", re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("Google API Key", re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
]


def clipboard_secret_scanner():
    print_banner()
    section("CLIPBOARD SECRET SCANNER")
    try:
        import tkinter
        root_ = tkinter.Tk()
        root_.withdraw()
        text = root_.clipboard_get()
        root_.destroy()
    except Exception as e:
        print(f"{C.RED}Impossibile leggere la clipboard: {e}{C.RESET}")
        if os.name != "nt":
            print(f"{C.GRAY}Su Linux potrebbe servire: sudo apt install python3-tk{C.RESET}")
        pause()
        return

    section("CONTROLLO")
    found = False
    for label, pattern in CLIPBOARD_PATTERNS:
        if pattern.search(text):
            print(f"{C.RED}[!] Sembra contenere: {label}{C.RESET}")
            found = True
    if not found:
        print(f"{C.GREEN}[OK] Nessun pattern sospetto trovato.{C.RESET}")
    print(f"{C.GRAY}Lunghezza contenuto: {len(text)} caratteri{C.RESET}")
    pause()


def startup_programs_viewer():
    print_banner()
    section("STARTUP PROGRAMS VIEWER")
    if os.name == "nt":
        out, err = run_cmd(["reg", "query", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run"])
        if out:
            for line in out.splitlines():
                if line.strip():
                    print(f"  {C.WHITE}{line.strip()}{C.RESET}")
        elif err:
            print(f"{C.RED}{err}{C.RESET}")
    else:
        autostart_dir = os.path.expanduser("~/.config/autostart")
        if os.path.isdir(autostart_dir):
            for f in os.listdir(autostart_dir):
                print(f"  {C.WHITE}{f}{C.RESET}")
        else:
            print(f"{C.GRAY}Nessuna cartella autostart trovata.{C.RESET}")
    pause()


SENSITIVE_ENV_HINTS = ["key", "secret", "token", "password", "pwd"]


def env_vars_viewer():
    print_banner()
    section("VARIABILI D'AMBIENTE")
    for k, v in sorted(os.environ.items()):
        is_sensitive = any(h in k.lower() for h in SENSITIVE_ENV_HINTS)
        if is_sensitive:
            masked = v[:3] + "..." + v[-3:] if len(v) > 6 else "***"
            print(f"{C.YELLOW}[!] {k}={masked} (mascherato, sembra sensibile){C.RESET}")
        else:
            print(f"  {C.GRAY}{k}={v[:60]}{C.RESET}")
    pause()


LOG_PATTERNS = [
    ("Possibile SQL Injection", re.compile(r"(?i)(union select|or 1=1|' or ')")),
    ("Possibile XSS", re.compile(r"(?i)<script")),
    ("Path traversal", re.compile(r"\.\./\.\./")),
    ("Login falliti", re.compile(r"(?i)failed password|authentication failure")),
]


def log_file_analyzer():
    print_banner()
    section("LOG FILE ANALYZER")
    path = input(f"{C.YELLOW}Percorso file di log: {C.RESET}").strip()
    if not os.path.isfile(path):
        print(f"{C.RED}File non trovato.{C.RESET}")
        pause()
        return
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    section(f"ANALISI ({len(lines)} righe)")
    for label, pattern in LOG_PATTERNS:
        matches = [l for l in lines if pattern.search(l)]
        color = C.RED if matches else C.GREEN
        print(f"{color}{label}: {len(matches)} occorrenze{C.RESET}")
        for m in matches[:3]:
            print(f"    {C.GRAY}{m.strip()[:120]}{C.RESET}")
    pause()


def antivirus_status_checker():
    print_banner()
    section("ANTIVIRUS/DEFENDER STATUS CHECKER")
    if os.name == "nt":
        out, err = run_cmd(["powershell", "-Command",
                             "Get-MpComputerStatus | Select-Object AntivirusEnabled,AntispywareEnabled,RealTimeProtectionEnabled"])
        if out:
            for line in out.splitlines():
                if line.strip():
                    print(f"  {C.WHITE}{line.strip()}{C.RESET}")
        else:
            print(f"{C.GRAY}Impossibile leggere lo stato di Defender.{C.RESET}")
    else:
        if shutil.which("clamscan") or shutil.which("freshclam"):
            print(f"{C.GREEN}[+] ClamAV rilevato sul sistema.{C.RESET}")
            out, _ = run_cmd(["systemctl", "is-active", "clamav-daemon"])
            if out:
                field("Servizio clamav-daemon:", out)
        else:
            print(f"{C.YELLOW}Nessun antivirus comune rilevato (normale su molte distro Linux desktop).{C.RESET}")
    pause()


# =========================================================
# OSINT AVANZATO II (44)
# =========================================================
def github_user_osint():
    print_banner()
    section("GITHUB USER OSINT")
    u = input(f"{C.YELLOW}Username GitHub: {C.RESET}").strip()
    try:
        r = requests.get(f"https://api.github.com/users/{u}", timeout=10)
        if r.status_code != 200:
            print(f"{C.RED}Utente non trovato.{C.RESET}")
            pause()
            return
        d = r.json()
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    section("PROFILO")
    field("Nome:", d.get("name") or "-")
    field("Bio:", d.get("bio") or "-")
    field("Azienda:", d.get("company") or "-")
    field("Posizione:", d.get("location") or "-")
    field("Email pubblica:", d.get("email") or "-")
    field("Blog/sito:", d.get("blog") or "-")
    field("Repo pubblici:", str(d.get("public_repos")))
    field("Follower:", str(d.get("followers")))
    field("Creato il:", d.get("created_at"))
    pause()


def github_org_members():
    print_banner()
    section("GITHUB ORG MEMBERS")
    org = input(f"{C.YELLOW}Nome organizzazione GitHub: {C.RESET}").strip()
    try:
        r = requests.get(f"https://api.github.com/orgs/{org}/members", timeout=10)
        members = r.json()
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    if not isinstance(members, list):
        print(f"{C.YELLOW}Organizzazione non trovata o membri non pubblici.{C.RESET}")
        pause()
        return
    section(f"MEMBRI PUBBLICI ({len(members)})")
    for m in members[:50]:
        print(f"  {C.GREEN}{m.get('login')}{C.RESET}")
    pause()


def npm_package_osint():
    print_banner()
    section("NPM PACKAGE OSINT")
    pkg = input(f"{C.YELLOW}Nome pacchetto npm: {C.RESET}").strip()
    try:
        d = requests.get(f"https://registry.npmjs.org/{pkg}", timeout=10).json()
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    if "error" in d:
        print(f"{C.RED}Pacchetto non trovato.{C.RESET}")
        pause()
        return
    latest = d.get("dist-tags", {}).get("latest")
    info = d.get("versions", {}).get(latest, {})
    section("INFO PACCHETTO")
    field("Ultima versione:", latest)
    field("Autore:", str(info.get("author", "?")))
    field("Homepage:", info.get("homepage", "-"))
    field("Repository:", str(info.get("repository", "-")))
    field("Maintainers:", ", ".join(m.get("name", "?") for m in d.get("maintainers", [])))
    pause()


def pypi_package_osint():
    print_banner()
    section("PYPI PACKAGE OSINT")
    pkg = input(f"{C.YELLOW}Nome pacchetto PyPI: {C.RESET}").strip()
    try:
        d = requests.get(f"https://pypi.org/pypi/{pkg}/json", timeout=10).json()
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    info = d.get("info", {})
    section("INFO PACCHETTO")
    field("Autore:", info.get("author", "-"))
    field("Email autore:", info.get("author_email", "-"))
    field("Homepage:", info.get("home_page") or "-")
    field("Licenza:", info.get("license") or "-")
    field("Numero release:", str(len(d.get("releases", {}))))
    pause()


def whois_privacy_checker():
    print_banner()
    section("WHOIS PRIVACY CHECKER")
    domain = input(f"{C.YELLOW}Dominio: {C.RESET}").strip()
    ensure_tool_installed("whois", apt_package="whois")
    out, _ = run_cmd(["whois", domain])
    if not out:
        print(f"{C.RED}Nessun dato whois disponibile.{C.RESET}")
        pause()
        return
    flags = ["privacy", "redacted", "whoisguard", "protected", "private"]
    if any(f in out.lower() for f in flags):
        print(f"{C.YELLOW}[?] Il whois sembra oscurato da un servizio di privacy.{C.RESET}")
    else:
        print(f"{C.GREEN}[+] Il whois NON sembra oscurato — dati registrante potenzialmente visibili.{C.RESET}")
        for key in ["Registrant Name", "Registrant Organization", "Registrant Email"]:
            m = re.search(rf"{key}:\s*(.+)", out, re.IGNORECASE)
            if m:
                field(key + ":", m.group(1).strip())
    pause()


def website_contact_scraper():
    print_banner()
    section("WEBSITE CONTACT SCRAPER")
    url = input(f"{C.YELLOW}URL del sito: {C.RESET}").strip()
    if not url.startswith("http"):
        url = "https://" + url
    try:
        html = requests.get(url, timeout=10, headers=UA).text
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    emails = sorted(set(re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", html)))
    phones = sorted(set(re.findall(r"\+?\d[\d\s().-]{7,}\d", html)))
    section(f"EMAIL TROVATE ({len(emails)})")
    for e in emails[:20]:
        print(f"  {C.GREEN}{e}{C.RESET}")
    section(f"NUMERI TROVATI ({len(phones)})")
    for p in phones[:20]:
        print(f"  {C.GREEN}{p.strip()}{C.RESET}")
    pause()


def reverse_image_search_links():
    print_banner()
    section("REVERSE IMAGE SEARCH LINK GENERATOR")
    img_url = input(f"{C.YELLOW}URL dell'immagine: {C.RESET}").strip()
    section("LINK DI RICERCA INVERSA")
    print(f"  {C.GREEN}Google Lens:{C.RESET} https://lens.google.com/uploadbyurl?url={img_url}")
    print(f"  {C.GREEN}Yandex:{C.RESET} https://yandex.com/images/search?rpt=imageview&url={img_url}")
    print(f"  {C.GREEN}TinEye:{C.RESET} https://tineye.com/search?url={img_url}")
    pause()


def batch_ip_geolocation():
    print_banner()
    section("BATCH IP GEOLOCATION")
    print(f"{C.GRAY}Incolla una lista di IP (uno per riga), riga vuota per terminare:{C.RESET}")
    ips = []
    while True:
        l = input()
        if not l:
            break
        ips.append(l.strip())
    section("RISULTATI")
    for ip in ips[:30]:
        data, err = ip_lookup(ip)
        if err:
            print(f"{C.RED}{ip} -> errore{C.RESET}")
            continue
        print(f"{C.GREEN}{ip:<16}{C.RESET} {data.get('country')} — {data.get('isp')}")
        time.sleep(0.3)
    pause()


def cidr_reverse_dns_scanner():
    print_banner()
    section("CIDR REVERSE DNS SCANNER")
    print(f"{C.YELLOW}Consigliato solo su range piccoli (/28 o piu' piccoli).{C.RESET}")
    cidr = input(f"{C.YELLOW}CIDR (es. 192.168.1.0/28): {C.RESET}").strip()
    try:
        net = ipaddress.ip_network(cidr, strict=False)
    except ValueError as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    section("RISULTATI (max 256 indirizzi)")
    count = 0
    for ip in net.hosts():
        if count >= 256:
            break
        count += 1
        try:
            host, _, _ = socket.gethostbyaddr(str(ip))
            print(f"{C.GREEN}{str(ip):<16}{C.RESET} -> {host}")
        except socket.herror:
            pass
    pause()


def crtsh_org_search():
    print_banner()
    section("CRT.SH ORGANIZATION SEARCH")
    org = input(f"{C.YELLOW}Nome organizzazione (come compare nei certificati): {C.RESET}").strip()
    try:
        data = requests.get(f"https://crt.sh/?q={urllib.parse.quote(org)}&output=json", timeout=20).json()
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    domains = set()
    for entry in data:
        for n in entry.get("name_value", "").split("\n"):
            domains.add(n.strip().lower())
    section(f"DOMINI TROVATI ({len(domains)})")
    for d in sorted(domains)[:60]:
        print(f"  {C.GREEN}{d}{C.RESET}")
    pause()


def dns_full_dump():
    print_banner()
    section("DNS FULL DUMP")
    domain = input(f"{C.YELLOW}Dominio: {C.RESET}").strip()
    ensure_tool_installed("nslookup", apt_package="dnsutils")
    for rtype in ["A", "AAAA", "MX", "TXT", "NS", "CNAME", "SOA"]:
        out, _ = run_cmd(["nslookup", "-type=" + rtype, domain])
        section(rtype)
        shown = False
        if out:
            for line in out.splitlines():
                if any(k in line for k in ["Address", "mail exchanger", "nameserver", "text =", "canonical name", "origin ="]):
                    print(f"  {C.WHITE}{line.strip()}{C.RESET}")
                    shown = True
        if not shown:
            print(f"  {C.GRAY}(nessun record){C.RESET}")
    pause()


def caa_record_checker():
    print_banner()
    section("CAA RECORD CHECKER")
    domain = input(f"{C.YELLOW}Dominio: {C.RESET}").strip()
    ensure_tool_installed("nslookup", apt_package="dnsutils")
    out, _ = run_cmd(["nslookup", "-type=CAA", domain])
    section("RISULTATO")
    if out and "caa" in out.lower():
        for line in out.splitlines():
            if line.strip():
                print(f"  {C.WHITE}{line.strip()}{C.RESET}")
    else:
        print(f"{C.YELLOW}Nessun record CAA — qualsiasi CA puo' emettere certificati per questo dominio.{C.RESET}")
    pause()


def txt_record_dumper():
    print_banner()
    section("TXT RECORD DUMPER")
    domain = input(f"{C.YELLOW}Dominio: {C.RESET}").strip()
    ensure_tool_installed("nslookup", apt_package="dnsutils")
    out, _ = run_cmd(["nslookup", "-type=txt", domain])
    section("TXT RECORD")
    count = 0
    if out:
        for line in out.splitlines():
            if "text =" in line.lower():
                print(f"  {C.WHITE}{line.strip()}{C.RESET}")
                count += 1
                low = line.lower()
                for svc in ["google-site-verification", "facebook-domain-verification", "atlassian-domain-verification", "stripe-verification"]:
                    if svc in low:
                        print(f"    {C.GRAY}-> verifica di proprieta' per servizio esterno ({svc}){C.RESET}")
    if count == 0:
        print(f"{C.GRAY}Nessun record TXT trovato.{C.RESET}")
    pause()


def company_logo_finder():
    print_banner()
    section("COMPANY LOGO FINDER")
    domain = input(f"{C.YELLOW}Dominio azienda: {C.RESET}").strip()
    url = f"https://logo.clearbit.com/{domain}"
    try:
        r = requests.head(url, timeout=8)
        if r.status_code == 200:
            print(f"{C.GREEN}[+] Logo trovato: {url}{C.RESET}")
        else:
            print(f"{C.YELLOW}Nessun logo trovato per questo dominio.{C.RESET}")
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
    pause()


def virustotal_domain_ip_checker():
    print_banner()
    section("VIRUSTOTAL DOMAIN/IP CHECKER")
    key = input(f"{C.YELLOW}API key VirusTotal: {C.RESET}").strip()
    target = input(f"{C.YELLOW}Dominio o IP: {C.RESET}").strip()
    kind = "ip_addresses" if re.match(r"^\d+\.\d+\.\d+\.\d+$", target) else "domains"
    try:
        r = requests.get(f"https://www.virustotal.com/api/v3/{kind}/{target}", headers={"x-apikey": key}, timeout=15)
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    if r.status_code != 200:
        print(f"{C.RED}Errore VirusTotal: HTTP {r.status_code}{C.RESET}")
        pause()
        return
    stats = r.json()["data"]["attributes"].get("last_analysis_stats", {})
    section("RISULTATO")
    field("Malevolo:", str(stats.get("malicious", 0)))
    field("Sospetto:", str(stats.get("suspicious", 0)))
    field("Pulito:", str(stats.get("harmless", 0)))
    pause()


def company_social_links_finder():
    print_banner()
    section("COMPANY SOCIAL LINKS FINDER")
    domain = input(f"{C.YELLOW}Dominio: {C.RESET}").strip()
    try:
        html = requests.get("https://" + domain, timeout=10, headers=UA).text
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    patterns = {
        "Twitter/X": r"(?:twitter|x)\.com/[A-Za-z0-9_]+",
        "Facebook": r"facebook\.com/[A-Za-z0-9_.]+",
        "LinkedIn": r"linkedin\.com/company/[A-Za-z0-9_-]+",
        "Instagram": r"instagram\.com/[A-Za-z0-9_.]+",
        "YouTube": r"youtube\.com/(?:c/|channel/|@)[A-Za-z0-9_-]+",
    }
    section("PROFILI SOCIAL TROVATI")
    found = False
    for name, pat in patterns.items():
        m = re.search(pat, html)
        if m:
            print(f"{C.GREEN}[+] {name}: https://{m.group(0)}{C.RESET}")
            found = True
    if not found:
        print(f"{C.GRAY}Nessun profilo social trovato nella homepage.{C.RESET}")
    pause()


def office_doc_metadata_extractor():
    print_banner()
    section("OFFICE DOC METADATA EXTRACTOR (docx/xlsx/pptx)")
    path = input(f"{C.YELLOW}Percorso file: {C.RESET}").strip()
    if not os.path.isfile(path) or not zipfile.is_zipfile(path):
        print(f"{C.RED}Non e' un file Office valido.{C.RESET}")
        pause()
        return
    with zipfile.ZipFile(path) as z:
        try:
            core = z.read("docProps/core.xml").decode("utf-8", errors="replace")
        except KeyError:
            print(f"{C.YELLOW}Metadati non trovati in questo file.{C.RESET}")
            pause()
            return
    section("METADATI")
    for tag in ["dc:creator", "cp:lastModifiedBy", "dcterms:created", "dcterms:modified", "dc:title"]:
        m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", core)
        if m:
            field(tag + ":", m.group(1))
    pause()


def pdf_metadata_extractor():
    print_banner()
    section("PDF METADATA EXTRACTOR")
    path = input(f"{C.YELLOW}Percorso file PDF: {C.RESET}").strip()
    if not os.path.isfile(path):
        print(f"{C.RED}File non trovato.{C.RESET}")
        pause()
        return
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("latin-1", errors="ignore")
    section("METADATI (best-effort)")
    found = False
    for key in ["Author", "Title", "Producer", "Creator", "CreationDate", "ModDate"]:
        m = re.search(rf"/{key}\s*\((.*?)\)", text)
        if m:
            field(key + ":", m.group(1))
            found = True
    if not found:
        print(f"{C.GRAY}Nessun metadato leggibile (potrebbe essere compresso/criptato).{C.RESET}")
    pause()


def domain_multi_tld_squat_checker():
    print_banner()
    section("DOMAIN MULTI-TLD SQUAT CHECKER")
    name = input(f"{C.YELLOW}Nome dominio senza TLD (es. example): {C.RESET}").strip()
    tlds = ["com", "net", "org", "io", "co", "info", "biz", "app", "dev", "xyz"]
    section("VERIFICA TLD")
    for tld in tlds:
        d = f"{name}.{tld}"
        try:
            socket.gethostbyname(d)
            print(f"{C.RED}[!] {d:<20} GIA' REGISTRATO{C.RESET}")
        except socket.gaierror:
            print(f"{C.GREEN}[+] {d:<20} libero{C.RESET}")
    pause()


def malware_c2_ip_checker():
    print_banner()
    section("MALWARE C2 IP CHECKER (Feodo Tracker)")
    ip = input(f"{C.YELLOW}IP da controllare: {C.RESET}").strip()
    try:
        data = requests.get("https://feodotracker.abuse.ch/downloads/ipblocklist.json", timeout=20).json()
    except Exception as e:
        print(f"{C.RED}Servizio non raggiungibile: {e}{C.RESET}")
        pause()
        return
    found = any(entry.get("ip_address") == ip for entry in data)
    if found:
        print(f"{C.RED}{C.BOLD}[!] IP presente nella blocklist Feodo Tracker (C2 malware noto).{C.RESET}")
    else:
        print(f"{C.GREEN}[OK] Non presente nella blocklist Feodo Tracker.{C.RESET}")
    pause()


def url_safety_checker():
    print_banner()
    section("URL SAFETY CHECKER (Google Safe Browsing)")
    key = input(f"{C.YELLOW}API key Google Safe Browsing: {C.RESET}").strip()
    url = input(f"{C.YELLOW}URL da controllare: {C.RESET}").strip()
    body = {"client": {"clientId": "icetool", "clientVersion": "1.0"},
            "threatInfo": {"threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],
                            "platformTypes": ["ANY_PLATFORM"], "threatEntryTypes": ["URL"],
                            "threatEntries": [{"url": url}]}}
    try:
        r = requests.post(f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={key}", json=body, timeout=15)
        data = r.json()
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    if data.get("matches"):
        print(f"{C.RED}{C.BOLD}[!] URL segnalato pericoloso: {data['matches'][0].get('threatType')}{C.RESET}")
    else:
        print(f"{C.GREEN}[OK] Nessuna minaccia nota trovata.{C.RESET}")
    pause()


def website_screenshot_fetcher():
    print_banner()
    section("WEBSITE SCREENSHOT FETCHER (via urlscan.io)")
    domain = input(f"{C.YELLOW}Dominio: {C.RESET}").strip()
    try:
        results = requests.get("https://urlscan.io/api/v1/search/", params={"q": f"domain:{domain}"}, timeout=15).json().get("results", [])
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    if not results:
        print(f"{C.YELLOW}Nessuna scansione pubblica trovata.{C.RESET}")
        pause()
        return
    screenshot_url = results[0].get("screenshot")
    if not screenshot_url:
        print(f"{C.YELLOW}Nessuno screenshot disponibile.{C.RESET}")
        pause()
        return
    field("Screenshot URL:", screenshot_url)
    if input(f"\n{C.YELLOW}Salvare come immagine locale? (s/n): {C.RESET}").strip().lower() == "s":
        try:
            img_data = requests.get(screenshot_url, timeout=15).content
            with open("screenshot.png", "wb") as f:
                f.write(img_data)
            print(f"{C.GREEN}Salvato in: {os.path.abspath('screenshot.png')}{C.RESET}")
        except Exception as e:
            print(f"{C.RED}Errore salvataggio: {e}{C.RESET}")
    pause()


def company_domain_finder():
    print_banner()
    section("COMPANY DOMAIN FINDER")
    name = input(f"{C.YELLOW}Nome azienda: {C.RESET}").strip()
    try:
        results = requests.get("https://autocomplete.clearbit.com/v1/companies/suggest", params={"query": name}, timeout=10).json()
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    section("RISULTATI")
    for res in results[:10]:
        print(f"  {C.GREEN}{res.get('name')}{C.RESET} -> {res.get('domain')}")
    pause()


def shodan_search_wrapper():
    print_banner()
    section("SHODAN SEARCH WRAPPER")
    key = input(f"{C.YELLOW}API key Shodan: {C.RESET}").strip()
    query = input(f"{C.YELLOW}Query/dork Shodan: {C.RESET}").strip()
    try:
        data = requests.get("https://api.shodan.io/shodan/host/search", params={"key": key, "query": query}, timeout=20).json()
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    section(f"RISULTATI ({data.get('total',0)} totali, primi 10)")
    for m in data.get("matches", [])[:10]:
        print(f"  {C.GREEN}{m.get('ip_str')}:{m.get('port')}{C.RESET} — {m.get('org','?')}")
    pause()


def threatfox_ioc_checker():
    print_banner()
    section("THREATFOX IOC CHECKER")
    ioc = input(f"{C.YELLOW}IP, dominio o hash: {C.RESET}").strip()
    try:
        data = requests.post("https://threatfox-api.abuse.ch/api/v1/", json={"query": "search_ioc", "search_term": ioc}, timeout=15).json()
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    if data.get("query_status") == "ok":
        section("RISULTATO")
        for item in data.get("data", [])[:5]:
            print(f"{C.RED}[!] {item.get('threat_type')} — malware: {item.get('malware_printable')}{C.RESET}")
    else:
        print(f"{C.GREEN}[OK] Nessuna minaccia nota trovata.{C.RESET}")
    pause()


def dns_over_https_lookup():
    print_banner()
    section("DNS OVER HTTPS LOOKUP (Cloudflare)")
    domain = input(f"{C.YELLOW}Dominio: {C.RESET}").strip()
    try:
        data = requests.get("https://cloudflare-dns.com/dns-query", params={"name": domain, "type": "A"},
                             headers={"accept": "application/dns-json"}, timeout=10).json()
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    section("RISULTATO")
    answers = data.get("Answer", [])
    for ans in answers:
        print(f"  {C.GREEN}{ans.get('data')}{C.RESET}")
    if not answers:
        print(f"{C.YELLOW}Nessuna risposta.{C.RESET}")
    pause()


def hunter_email_finder():
    print_banner()
    section("HUNTER.IO EMAIL FINDER")
    key = input(f"{C.YELLOW}API key Hunter.io: {C.RESET}").strip()
    domain = input(f"{C.YELLOW}Dominio: {C.RESET}").strip()
    try:
        data = requests.get("https://api.hunter.io/v2/domain-search", params={"domain": domain, "api_key": key}, timeout=15).json().get("data", {})
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    emails = data.get("emails", [])
    section(f"EMAIL TROVATE ({len(emails)})")
    for e in emails[:20]:
        print(f"  {C.GREEN}{e.get('value')}{C.RESET} — {e.get('first_name','')} {e.get('last_name','')}")
    pause()


def telegram_channel_info():
    print_banner()
    section("TELEGRAM CHANNEL INFO")
    username = input(f"{C.YELLOW}Username canale (senza @): {C.RESET}").strip()
    try:
        r = requests.get(f"https://t.me/{username}", timeout=10, headers=UA)
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    if "tgme_page_title" not in r.text:
        print(f"{C.RED}Canale non trovato.{C.RESET}")
        pause()
        return
    title_m = re.search(r'tgme_page_title"[^>]*>\s*<span[^>]*>(.*?)</span>', r.text)
    desc_m = re.search(r'tgme_page_description">(.*?)</div>', r.text, re.DOTALL)
    members_m = re.search(r'tgme_page_extra">([\d\s,.]+ (?:members|subscribers|iscritti))', r.text)
    section("RISULTATO")
    if title_m:
        field("Titolo:", title_m.group(1).strip())
    if members_m:
        field("Membri:", members_m.group(1).strip())
    if desc_m:
        field("Descrizione:", re.sub("<[^>]+>", "", desc_m.group(1)).strip()[:150])
    pause()


def discord_invite_info():
    print_banner()
    section("DISCORD INVITE INFO")
    code = input(f"{C.YELLOW}Codice invito (da discord.gg/CODICE): {C.RESET}").strip()
    try:
        data = requests.get(f"https://discord.com/api/v9/invites/{code}", params={"with_counts": "true"}, timeout=10).json()
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    if "guild" not in data:
        print(f"{C.RED}Invito non valido o scaduto.{C.RESET}")
        pause()
        return
    guild = data["guild"]
    section("SERVER")
    field("Nome:", guild.get("name"))
    field("ID:", guild.get("id"))
    field("Membri totali:", str(data.get("approximate_member_count", "?")))
    field("Membri online:", str(data.get("approximate_presence_count", "?")))
    field("Canale invito:", data.get("channel", {}).get("name", "?"))
    pause()


def reddit_user_osint():
    print_banner()
    section("REDDIT USER OSINT")
    username = input(f"{C.YELLOW}Username Reddit: {C.RESET}").strip()
    try:
        data = requests.get(f"https://www.reddit.com/user/{username}/about.json", timeout=10, headers=UA).json().get("data", {})
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    if not data:
        print(f"{C.RED}Utente non trovato.{C.RESET}")
        pause()
        return
    section("PROFILO")
    field("Karma post:", str(data.get("link_karma")))
    field("Karma commenti:", str(data.get("comment_karma")))
    field("Account creato:", datetime.utcfromtimestamp(data.get("created_utc", 0)).strftime("%Y-%m-%d"))
    field("Email verificata:", "si'" if data.get("has_verified_email") else "no")
    pause()


def archive_today_checker():
    print_banner()
    section("ARCHIVE.TODAY CHECKER")
    url = input(f"{C.YELLOW}URL: {C.RESET}").strip()
    print(f"{C.GRAY}Archive.today non ha una API pubblica ufficiale — ecco il link diretto:{C.RESET}\n")
    field("Verifica/archivia qui:", f"https://archive.ph/{url}")
    pause()


def exploit_db_link_generator():
    print_banner()
    section("EXPLOIT-DB / POC LINK GENERATOR")
    query = input(f"{C.YELLOW}CVE ID o nome prodotto: {C.RESET}").strip()
    section("LINK UTILI")
    print(f"  {C.GREEN}Exploit-DB:{C.RESET} https://www.exploit-db.com/search?cve={query}")
    print(f"  {C.GREEN}NVD:{C.RESET} https://nvd.nist.gov/vuln/detail/{query}")
    print(f"  {C.GREEN}GitHub PoC search:{C.RESET} https://github.com/search?q={urllib.parse.quote(query)}+exploit&type=repositories")
    pause()


def company_news_mentions():
    print_banner()
    section("COMPANY NEWS MENTIONS (GNews)")
    key = input(f"{C.YELLOW}API key GNews: {C.RESET}").strip()
    query = input(f"{C.YELLOW}Nome azienda o dominio: {C.RESET}").strip()
    try:
        articles = requests.get("https://gnews.io/api/v4/search", params={"q": query, "apikey": key, "max": 10}, timeout=15).json().get("articles", [])
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    section(f"ARTICOLI TROVATI ({len(articles)})")
    for a in articles:
        print(f"  {C.GREEN}{a.get('title')}{C.RESET} — {a.get('source',{}).get('name')} ({a.get('publishedAt','')[:10]})")
    pause()


def ip_abuse_history_aggregator():
    print_banner()
    section("IP THREAT INTELLIGENCE AGGREGATOR")
    ip = input(f"{C.YELLOW}IP da controllare: {C.RESET}").strip()

    section("ABUSEIPDB (opzionale)")
    key = input(f"{C.YELLOW}API key AbuseIPDB (invio per saltare): {C.RESET}").strip()
    if key:
        try:
            d = requests.get("https://api.abuseipdb.com/api/v2/check", headers={"Key": key, "Accept": "application/json"},
                              params={"ipAddress": ip}, timeout=15).json().get("data", {})
            field("Punteggio abuso:", f"{d.get('abuseConfidenceScore','?')}%")
        except Exception as e:
            print(f"{C.RED}Errore: {e}{C.RESET}")

    section("THREATFOX")
    try:
        data = requests.post("https://threatfox-api.abuse.ch/api/v1/", json={"query": "search_ioc", "search_term": ip}, timeout=15).json()
        if data.get("query_status") == "ok":
            print(f"{C.RED}[!] Presente in ThreatFox come IOC malware.{C.RESET}")
        else:
            print(f"{C.GREEN}[OK] Non presente in ThreatFox.{C.RESET}")
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
    pause()


def domain_threat_aggregator():
    print_banner()
    section("DOMAIN THREAT INTELLIGENCE AGGREGATOR")
    domain = input(f"{C.YELLOW}Dominio: {C.RESET}").strip()

    section("VIRUSTOTAL (opzionale)")
    key = input(f"{C.YELLOW}API key VirusTotal (invio per saltare): {C.RESET}").strip()
    if key:
        try:
            stats = requests.get(f"https://www.virustotal.com/api/v3/domains/{domain}",
                                  headers={"x-apikey": key}, timeout=15).json()["data"]["attributes"].get("last_analysis_stats", {})
            field("Malevolo:", str(stats.get("malicious", 0)))
        except Exception as e:
            print(f"{C.RED}Errore: {e}{C.RESET}")

    section("ETA' DOMINIO (whois)")
    ensure_tool_installed("whois", apt_package="whois")
    out, _ = run_cmd(["whois", domain])
    if out:
        m = re.search(r"Creation Date:\s*(\S+)", out, re.IGNORECASE)
        if m:
            field("Creato il:", m.group(1))
    pause()


def wigle_wifi_lookup():
    print_banner()
    section("WIGLE WIFI LOOKUP")
    api_name = input(f"{C.YELLOW}WiGLE API Name: {C.RESET}").strip()
    api_token = input(f"{C.YELLOW}WiGLE API Token: {C.RESET}").strip()
    ssid = input(f"{C.YELLOW}SSID da cercare: {C.RESET}").strip()
    try:
        data = requests.get("https://api.wigle.net/api/v2/network/search", params={"ssid": ssid},
                             auth=(api_name, api_token), timeout=15).json()
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    results = data.get("results", [])
    section(f"RISULTATI ({len(results)})")
    for res in results[:10]:
        print(f"  {C.GREEN}{res.get('ssid')}{C.RESET} — lat:{res.get('trilat')} lon:{res.get('trilong')} citta':{res.get('city','?')}")
    pause()


def instagram_full_profile_osint():
    print_banner()
    section("INSTAGRAM PROFILE OSINT (esteso)")
    username = input(f"{C.YELLOW}Username: {C.RESET}").strip()
    try:
        r = requests.get(f"https://www.instagram.com/{username}/", timeout=10, headers=UA)
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    if r.status_code == 404 or "Sorry, this page" in r.text:
        print(f"{C.RED}Profilo non trovato.{C.RESET}")
        pause()
        return
    followers_m = re.search(r'"edge_followed_by":\{"count":(\d+)\}', r.text)
    following_m = re.search(r'"edge_follow":\{"count":(\d+)\}', r.text)
    bio_m = re.search(r'"biography":"(.*?)"', r.text)
    section("PROFILO (best-effort, Instagram cambia spesso la struttura pagina)")
    if followers_m:
        field("Follower:", followers_m.group(1))
    if following_m:
        field("Seguiti:", following_m.group(1))
    if bio_m:
        field("Bio:", bio_m.group(1))
    if not (followers_m or bio_m):
        print(f"{C.YELLOW}Dati non estraibili (pagina cambiata o richiede login).{C.RESET}")
    pause()


TAKEOVER_SIGNATURES = {
    "GitHub Pages": "There isn't a GitHub Pages site here", "Heroku": "No such app",
    "AWS S3": "NoSuchBucket", "Shopify": "Sorry, this shop is currently unavailable",
    "Fastly": "Fastly error: unknown domain", "Unbounce": "The requested URL was not found",
}


def subdomain_takeover_checker():
    print_banner()
    section("SUBDOMAIN TAKEOVER CHECKER")
    print(f"{C.YELLOW}Usa solo su domini tuoi/autorizzati.{C.RESET}\n")
    subdomain = input(f"{C.YELLOW}Sottodominio (es. old.example.com): {C.RESET}").strip()
    try:
        text = requests.get(f"http://{subdomain}", timeout=10, headers=UA).text
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    section("RISULTATO")
    found = False
    for service, sig in TAKEOVER_SIGNATURES.items():
        if sig in text:
            print(f"{C.RED}{C.BOLD}[!] Possibile subdomain takeover — punta a {service} non rivendicato!{C.RESET}")
            found = True
    if not found:
        print(f"{C.GREEN}[OK] Nessuna firma di takeover nota trovata.{C.RESET}")
    pause()


def company_glassdoor_link_generator():
    print_banner()
    section("COMPANY REVIEW/PROFILE LINK GENERATOR")
    company = input(f"{C.YELLOW}Nome azienda: {C.RESET}").strip()
    q = urllib.parse.quote(company)
    section("LINK UTILI")
    print(f"  {C.GREEN}Glassdoor:{C.RESET} https://www.glassdoor.com/Search/results.htm?keyword={q}")
    print(f"  {C.GREEN}LinkedIn:{C.RESET} https://www.linkedin.com/search/results/companies/?keywords={q}")
    print(f"  {C.GREEN}Crunchbase:{C.RESET} https://www.crunchbase.com/textsearch?q={q}")
    pause()


def shodan_facet_stats():
    print_banner()
    section("SHODAN FACET STATS")
    key = input(f"{C.YELLOW}API key Shodan: {C.RESET}").strip()
    query = input(f"{C.YELLOW}Query/dork: {C.RESET}").strip()
    try:
        data = requests.get("https://api.shodan.io/shodan/host/search",
                             params={"key": key, "query": query, "facets": "country:5,org:5"}, timeout=20).json()
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    section("TOP PAESI")
    for c in data.get("facets", {}).get("country", []):
        print(f"  {C.GREEN}{c.get('value')}{C.RESET}: {c.get('count')}")
    section("TOP ORGANIZZAZIONI")
    for o in data.get("facets", {}).get("org", []):
        print(f"  {C.GREEN}{o.get('value')}{C.RESET}: {o.get('count')}")
    pause()


def dns_blacklist_checker():
    print_banner()
    section("DNS BLACKLIST (DNSBL) CHECKER")
    ip = input(f"{C.YELLOW}IP da controllare: {C.RESET}").strip()
    parts = ip.split(".")
    if len(parts) != 4:
        print(f"{C.RED}IP non valido.{C.RESET}")
        pause()
        return
    reversed_ip = ".".join(reversed(parts))
    blacklists = ["zen.spamhaus.org", "bl.spamcop.net", "dnsbl.sorbs.net", "b.barracudacentral.org"]
    section("RISULTATO")
    listed = 0
    for bl in blacklists:
        try:
            socket.gethostbyname(f"{reversed_ip}.{bl}")
            print(f"{C.RED}[!] Presente in {bl}{C.RESET}")
            listed += 1
        except socket.gaierror:
            print(f"{C.GREEN}[OK] Non presente in {bl}{C.RESET}")
    if listed == 0:
        print(f"\n{C.GREEN}{C.BOLD}IP pulito su tutte le blacklist controllate.{C.RESET}")
    pause()


def tor_exit_node_checker():
    print_banner()
    section("TOR EXIT NODE CHECKER")
    ip = input(f"{C.YELLOW}IP da controllare: {C.RESET}").strip()
    try:
        exit_nodes = set(requests.get("https://check.torproject.org/torbulkexitlist", timeout=15).text.splitlines())
    except Exception as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    if ip in exit_nodes:
        print(f"{C.RED}{C.BOLD}[!] E' un exit node Tor conosciuto.{C.RESET}")
    else:
        print(f"{C.GREEN}[OK] Non risulta un exit node Tor.{C.RESET}")
    pause()


def pastebin_search_link_generator():
    print_banner()
    section("PASTE SITES SEARCH LINK GENERATOR")
    keyword = input(f"{C.YELLOW}Parola chiave: {C.RESET}").strip()
    section("QUERY GENERATE (via Google, i paste site non hanno ricerca pubblica diretta)")
    print(f'  {C.GREEN}site:pastebin.com "{keyword}"{C.RESET}')
    print(f'  {C.GREEN}site:paste.ee "{keyword}"{C.RESET}')
    print(f'  {C.GREEN}site:ghostbin.com "{keyword}"{C.RESET}')
    pause()


def google_cache_checker():
    print_banner()
    section("GOOGLE CACHE / ARCHIVE CHECKER")
    url = input(f"{C.YELLOW}URL: {C.RESET}").strip()
    section("LINK UTILI (Google non supporta piu' l'operatore cache:)")
    print(f"  {C.GREEN}CachedView:{C.RESET} http://cachedview.nl/")
    print(f"  {C.GREEN}Wayback Machine:{C.RESET} https://web.archive.org/web/*/{url}")
    pause()


# =========================================================
# STRUMENTI DI ANALISI (8)
# =========================================================
def hash_identifier():
    print_banner()
    section("HASH IDENTIFIER")
    h = input(f"{C.YELLOW}Hash da identificare: {C.RESET}").strip()
    guesses = []
    if re.fullmatch(r"[a-fA-F0-9]{32}", h):
        guesses.append("MD5 o NTLM (32 caratteri hex)")
    if re.fullmatch(r"[a-fA-F0-9]{40}", h):
        guesses.append("SHA1 (40 caratteri hex)")
    if re.fullmatch(r"[a-fA-F0-9]{64}", h):
        guesses.append("SHA256 (64 caratteri hex)")
    if re.fullmatch(r"[a-fA-F0-9]{128}", h):
        guesses.append("SHA512 (128 caratteri hex)")
    if re.match(r"^\$2[aby]\$", h):
        guesses.append("bcrypt")
    if re.match(r"^\$1\$", h):
        guesses.append("MD5 crypt (Unix)")
    if re.match(r"^\$6\$", h):
        guesses.append("SHA512 crypt (Unix)")
    section("POSSIBILI ALGORITMI")
    if guesses:
        for g in guesses:
            print(f"  {C.GREEN}{g}{C.RESET}")
    else:
        print(f"{C.YELLOW}Formato non riconosciuto tra quelli comuni.{C.RESET}")
    pause()


def useragent_parser():
    print_banner()
    section("USER-AGENT PARSER")
    ua = input(f"{C.YELLOW}Stringa User-Agent: {C.RESET}").strip()
    os_patterns = {"Windows NT 10": "Windows 10/11", "Windows NT 6.1": "Windows 7",
                   "Mac OS X": "macOS", "Android": "Android", "iPhone": "iOS (iPhone)", "Linux": "Linux"}
    detected_os = next((v for k, v in os_patterns.items() if k in ua), "sconosciuto")
    detected_browser = "sconosciuto"
    if "Edg/" in ua:
        detected_browser = "Microsoft Edge"
    elif "Chrome/" in ua:
        detected_browser = "Google Chrome"
    elif "Firefox/" in ua:
        detected_browser = "Mozilla Firefox"
    elif "Safari/" in ua:
        detected_browser = "Safari"
    section("ANALISI (euristica base)")
    field("Sistema operativo:", detected_os)
    field("Browser:", detected_browser)
    field("Bot/crawler:", "probabile" if re.search(r"(?i)bot|spider|crawl", ua) else "improbabile")
    pause()


def regex_tester():
    print_banner()
    section("REGEX TESTER")
    pattern = input(f"{C.YELLOW}Pattern regex: {C.RESET}")
    text = input(f"{C.YELLOW}Testo su cui testare: {C.RESET}")
    try:
        matches = re.findall(pattern, text)
    except re.error as e:
        print(f"{C.RED}Pattern non valido: {e}{C.RESET}")
        pause()
        return
    section(f"MATCH TROVATI ({len(matches)})")
    for m in matches[:30]:
        print(f"  {C.GREEN}{m}{C.RESET}")
    if not matches:
        print(f"{C.YELLOW}Nessun match.{C.RESET}")
    pause()


def json_formatter_validator():
    print_banner()
    section("JSON FORMATTER / VALIDATOR")
    print(f"{C.GRAY}Incolla il JSON, riga vuota per terminare:{C.RESET}")
    lines = []
    while True:
        l = input()
        if not l:
            break
        lines.append(l)
    raw = "\n".join(lines)
    try:
        parsed = json.loads(raw)
    except Exception as e:
        print(f"{C.RED}JSON non valido: {e}{C.RESET}")
        pause()
        return
    section("JSON FORMATTATO")
    print(f"{C.WHITE}{json.dumps(parsed, indent=2, ensure_ascii=False)}{C.RESET}")
    pause()


def mystery_string_decoder():
    print_banner()
    section("MYSTERY STRING / ENCODED DATA IDENTIFIER")
    print(f"{C.GRAY}Utile per analizzare stringhe trovate durante un'investigazione (log, config, artefatti).{C.RESET}\n")
    s = input(f"{C.YELLOW}Stringa da analizzare: {C.RESET}").strip()
    section("TENTATIVI DI DECODIFICA")
    tried = False
    try:
        padded = s + "=" * (-len(s) % 4)
        dec = base64.b64decode(padded).decode("utf-8", errors="strict")
        print(f"{C.GREEN}Base64:{C.RESET} {dec[:200]}")
        tried = True
    except Exception:
        pass
    dec_url = urllib.parse.unquote(s)
    if dec_url != s:
        print(f"{C.GREEN}URL decode:{C.RESET} {dec_url[:200]}")
        tried = True
    try:
        dec_hex = bytes.fromhex(s).decode("utf-8", errors="strict")
        print(f"{C.GREEN}Hex:{C.RESET} {dec_hex[:200]}")
        tried = True
    except Exception:
        pass
    if not tried:
        print(f"{C.YELLOW}Nessuna decodifica valida trovata tra Base64/URL/Hex.{C.RESET}")
    pause()


def domain_similarity_checker():
    print_banner()
    section("DOMAIN/STRING SIMILARITY CHECKER")
    d1 = input(f"{C.YELLOW}Dominio/stringa 1: {C.RESET}").strip()
    d2 = input(f"{C.YELLOW}Dominio/stringa 2: {C.RESET}").strip()

    def levenshtein(a, b):
        if len(a) < len(b):
            a, b = b, a
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            cur = [i]
            for j, cb in enumerate(b, 1):
                cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
            prev = cur
        return prev[-1]

    dist = levenshtein(d1, d2)
    section("RISULTATO")
    field("Distanza di edit:", str(dist))
    if dist <= 2:
        print(f"\n{C.YELLOW}{C.BOLD}[!] Stringhe molto simili — possibile typosquatting/phishing.{C.RESET}")
    else:
        print(f"\n{C.GREEN}Sufficientemente diverse.{C.RESET}")
    pause()


def cidr_merger():
    print_banner()
    section("CIDR MERGER / AGGREGATOR")
    print(f"{C.GRAY}Incolla IP o CIDR uno per riga, riga vuota per terminare:{C.RESET}")
    entries = []
    while True:
        l = input()
        if not l:
            break
        entries.append(l.strip())
    try:
        nets = [ipaddress.ip_network(e, strict=False) for e in entries]
        merged = list(ipaddress.collapse_addresses(nets))
    except ValueError as e:
        print(f"{C.RED}Errore: {e}{C.RESET}")
        pause()
        return
    section("CIDR AGGREGATI")
    for n in merged:
        print(f"  {C.GREEN}{n}{C.RESET}")
    pause()


def entropy_calculator():
    print_banner()
    section("STRING ENTROPY CALCULATOR")
    s = input(f"{C.YELLOW}Stringa da analizzare: {C.RESET}")
    if not s:
        print(f"{C.RED}Nessuna stringa inserita.{C.RESET}")
        pause()
        return
    freq = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    entropy = -sum((v / len(s)) * math.log2(v / len(s)) for v in freq.values())
    section("RISULTATO")
    field("Entropia (bit/carattere):", f"{entropy:.3f}")
    if entropy > 4.0:
        print(f"\n{C.YELLOW}Alta entropia — probabile stringa casuale/codificata (chiave, hash, secret).{C.RESET}")
    else:
        print(f"\n{C.GREEN}Entropia bassa — probabile testo naturale o pattern ripetitivo.{C.RESET}")
    pause()


# =========================================================
# FILE TOOLS: apri file / esplora cartella / esplora zip / sicurezza file
# =========================================================
def human_size(n):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def file_viewer():
    print_banner()
    section("APRI / LEGGI FILE")
    path = input(f"{C.YELLOW}Percorso del file (anche codice sorgente): {C.RESET}").strip()
    if not os.path.isfile(path):
        print(f"{C.RED}File non trovato.{C.RESET}")
        pause()
        return

    size = os.path.getsize(path)
    field("Percorso:", os.path.abspath(path))
    field("Dimensione:", human_size(size))

    with open(path, "rb") as f:
        chunk = f.read(8192)
    is_text = b"\x00" not in chunk

    section("CONTENUTO")
    if not is_text:
        print(f"{C.YELLOW}Il file sembra binario, non mostro il contenuto grezzo.{C.RESET}")
        print(f"{C.GRAY}Primi byte (hex): {chunk[:32].hex()}{C.RESET}")
    else:
        try:
            text = chunk.decode("utf-8", errors="replace") if size > 8192 else open(path, "r", encoding="utf-8", errors="replace").read()
            lines = text.splitlines()
            max_lines = 300
            for i, line in enumerate(lines[:max_lines], 1):
                print(f"  {C.GRAY}{i:>4}{C.RESET} {C.WHITE}{line}{C.RESET}")
            if len(lines) > max_lines:
                print(f"\n{C.YELLOW}[...] file troncato, mostrate le prime {max_lines} righe su {len(lines)}.{C.RESET}")
        except Exception as e:
            print(f"{C.RED}Errore leggendo il file: {e}{C.RESET}")
    pause()


def dir_browser():
    print_banner()
    section("ESPLORA CARTELLA")
    path = input(f"{C.YELLOW}Percorso cartella (invio = cartella corrente): {C.RESET}").strip() or "."
    if not os.path.isdir(path):
        print(f"{C.RED}Cartella non trovata.{C.RESET}")
        pause()
        return

    try:
        entries = sorted(os.listdir(path))
    except PermissionError:
        print(f"{C.RED}Permesso negato per leggere questa cartella.{C.RESET}")
        pause()
        return

    section(f"CONTENUTO DI {os.path.abspath(path)}")
    dirs = [e for e in entries if os.path.isdir(os.path.join(path, e))]
    files = [e for e in entries if os.path.isfile(os.path.join(path, e))]

    for d in dirs:
        print(f"  {BLUE}[DIR]{C.RESET}  {d}")
    for f in files:
        size = human_size(os.path.getsize(os.path.join(path, f)))
        print(f"  {C.GRAY}[file]{C.RESET} {f:<40} {C.GRAY}{size}{C.RESET}")

    print(f"\n{C.BOLD}Totale:{C.RESET} {len(dirs)} cartelle, {len(files)} file.")
    pause()


def zip_browser():
    print_banner()
    section("ESPLORA FILE ZIP")
    path = input(f"{C.YELLOW}Percorso del file .zip: {C.RESET}").strip()
    if not os.path.isfile(path) or not zipfile.is_zipfile(path):
        print(f"{C.RED}Non e' un file ZIP valido.{C.RESET}")
        pause()
        return

    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        section(f"CONTENUTO ({len(names)} elementi)")
        for n in names:
            info = z.getinfo(n)
            print(f"  {C.WHITE}{n:<50}{C.RESET} {C.GRAY}{human_size(info.file_size)}{C.RESET}")

        target = input(f"\n{C.YELLOW}Vuoi vedere il contenuto di un file? Scrivi il nome esatto (invio per saltare): {C.RESET}").strip()
        if target and target in names:
            try:
                raw = z.read(target)
                if b"\x00" in raw[:8192]:
                    print(f"{C.YELLOW}Il file sembra binario, non mostro il contenuto grezzo.{C.RESET}")
                else:
                    text = raw.decode("utf-8", errors="replace")
                    section(f"CONTENUTO DI {target}")
                    for i, line in enumerate(text.splitlines()[:300], 1):
                        print(f"  {C.GRAY}{i:>4}{C.RESET} {C.WHITE}{line}{C.RESET}")
            except Exception as e:
                print(f"{C.RED}Errore leggendo il file dallo ZIP: {e}{C.RESET}")
        elif target:
            print(f"{C.RED}Nome non trovato nello ZIP.{C.RESET}")
    pause()


DANGEROUS_EXTENSIONS = {".exe", ".scr", ".bat", ".cmd", ".com", ".pif", ".vbs", ".vbe",
                         ".js", ".jse", ".wsf", ".ps1", ".jar", ".msi", ".dll", ".lnk", ".hta"}
COMMON_SAFE_EXTENSIONS = {".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png", ".txt", ".mp3", ".mp4", ".xlsx", ".pptx"}


def file_safety_checker():
    print_banner()
    section("CONTROLLO SICUREZZA FILE")
    print(f"{C.GRAY}Controlla euristiche base (estensione sospetta, file mascherato) e, se fornisci{C.RESET}")
    print(f"{C.GRAY}una API key gratuita di VirusTotal, la reputazione dell'hash nel loro database.{C.RESET}")
    print(f"{C.GRAY}Il file NON viene mai caricato o condiviso: viene solo calcolato l'hash localmente.{C.RESET}\n")

    path = input(f"{C.YELLOW}Percorso del file da controllare: {C.RESET}").strip()
    if not os.path.isfile(path):
        print(f"{C.RED}File non trovato.{C.RESET}")
        pause()
        return

    name = os.path.basename(path)
    parts = name.split(".")
    ext = ("." + parts[-1].lower()) if len(parts) > 1 else ""
    prev_ext = ("." + parts[-2].lower()) if len(parts) > 2 else ""

    with open(path, "rb") as f:
        header = f.read(8)
    is_pe = header[:2] == b"MZ"
    is_elf = header[:4] == b"\x7fELF"

    section("EURISTICHE")
    field("Nome file:", name)
    field("Estensione:", ext or "(nessuna)")

    warnings = 0
    if prev_ext in COMMON_SAFE_EXTENSIONS and ext in DANGEROUS_EXTENSIONS:
        print(f"  {C.RED}{C.BOLD}[!] Doppia estensione sospetta ({prev_ext}{ext}) — trucco tipico per mascherare eseguibili.{C.RESET}")
        warnings += 1
    if is_pe and ext not in {".exe", ".dll", ".scr", ".sys", ".com"}:
        print(f"  {C.RED}{C.BOLD}[!] Il file e' un eseguibile Windows (PE) ma l'estensione non lo fa sembrare tale — sospetto.{C.RESET}")
        warnings += 1
    elif is_pe:
        print(f"  {C.YELLOW}[i] Il file e' un eseguibile Windows (PE).{C.RESET}")
    if is_elf:
        print(f"  {C.YELLOW}[i] Il file e' un eseguibile Linux (ELF).{C.RESET}")
    if ext in DANGEROUS_EXTENSIONS and not (is_pe or is_elf):
        print(f"  {C.YELLOW}[i] Estensione potenzialmente pericolosa ({ext}) — esegui solo se ti fidi della fonte.{C.RESET}")
        warnings += 1
    if warnings == 0:
        print(f"  {C.GREEN}[OK] Nessuna euristica sospetta rilevata.{C.RESET}")

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    sha256 = h.hexdigest()
    section("HASH")
    field("SHA256:", sha256)

    vt_key = input(f"\n{C.YELLOW}API key VirusTotal (invio per saltare): {C.RESET}").strip()
    if vt_key:
        try:
            r = requests.get(f"https://www.virustotal.com/api/v3/files/{sha256}",
                              headers={"x-apikey": vt_key}, timeout=15)
            section("VIRUSTOTAL")
            if r.status_code == 200:
                stats = r.json()["data"]["attributes"]["last_analysis_stats"]
                mal = stats.get("malicious", 0)
                susp = stats.get("suspicious", 0)
                total = sum(stats.values())
                field("Motori totali:", str(total))
                field("Rilevato malevolo da:", str(mal))
                field("Sospetto da:", str(susp))
                if mal > 0:
                    print(f"\n  {C.RED}{C.BOLD}[!] ATTENZIONE: {mal} motori antivirus lo segnalano come malevolo.{C.RESET}")
                else:
                    print(f"\n  {C.GREEN}{C.BOLD}[OK] Nessun motore antivirus lo segnala come malevolo.{C.RESET}")
            elif r.status_code == 404:
                print(f"  {C.YELLOW}Hash non presente nel database VirusTotal — non ancora analizzato,{C.RESET}")
                print(f"  {C.YELLOW}questo NON significa necessariamente che sia sicuro.{C.RESET}")
            else:
                print(f"  {C.RED}Errore VirusTotal: HTTP {r.status_code}{C.RESET}")
        except Exception as e:
            print(f"  {C.RED}Errore contattando VirusTotal: {e}{C.RESET}")
    pause()


# =========================================================
# MENU PAGINATO
# =========================================================
CATEGORIES_ORDERED = [
    ("NOMI & USERNAME", [
        ("Minecraft nick checker", minecraft_checker),
        ("Username checker multi-social", username_checker),
    ]),
    ("RETE & SITI", [
        ("My IP lookup (+ rete locale)", my_ip_lookup),
        ("Other IP lookup", other_ip_lookup),
        ("VPN detector", vpn_detector),
        ("Site lookup (whois/nslookup)", site_lookup),
        ("Port scanner", port_scanner),
        ("Subdomain finder", subdomain_finder),
        ("HTTP security headers checker", http_headers_checker),
        ("Ping / uptime monitor", ping_monitor),
    ]),
    ("SICUREZZA", [
        ("Password breach checker", password_breach_checker),
        ("Password generator", password_generator),
        ("File hash comparator", file_hash_comparator),
        ("Controllo sicurezza file", file_safety_checker),
    ]),
    ("EMAIL & TELEFONO", [
        ("Email validator (formato + MX)", email_validator),
        ("Phone number lookup", phone_lookup),
    ]),
    ("QR & GENERATORI", [
        ("QR code generator (testo/WiFi/vCard)", qr_generator),
        (".gitignore generator", gitignore_generator),
    ]),
    ("FILE & SISTEMA BASE", [
        ("Apri / leggi file (anche codice)", file_viewer),
        ("Esplora cartella", dir_browser),
        ("Esplora file ZIP", zip_browser),
        ("Site mirror (backup sito con wget)", site_mirror),
        ("Universal extractor (exe/jar/zip/mod)", universal_extractor),
        ("Local HTTP server launcher", http_server_launcher),
    ]),
    ("SVILUPPO & PROGRAMMAZIONE", [
        ("Outdated packages checker", outdated_packages_checker),
        ("Env file validator", env_file_validator),
        ("JWT decoder", jwt_decoder),
        ("HTTP status code lookup", http_status_lookup),
        ("Dockerfile linter", dockerfile_linter),
        ("Git repo secrets scanner", git_secrets_scanner),
        ("License checker dipendenze", license_checker),
        ("Local pip vulnerability scanner", pip_vuln_scanner),
        ("API tester (mini Postman)", api_tester),
        ("Cron expression explainer", cron_explainer),
        ("Markdown checker", markdown_checker),
        ("SQL query formatter", sql_formatter),
        ("Changelog generator da git log", changelog_generator),
        ("Webhook tester locale", webhook_tester),
    ]),
    ("OSINT AVANZATO", [
        ("Tech stack detector", tech_stack_detector),
        ("Company/domain aggregator", domain_aggregator),
        ("Google dork generator", google_dork_generator),
        ("Email header analyzer", email_header_analyzer),
        ("Wayback Machine snapshot viewer", wayback_viewer),
        ("Domain reputation aggregator", domain_reputation_aggregator),
        ("Redirect chain tracer", redirect_chain_tracer),
        ("robots.txt / sitemap.xml viewer", robots_sitemap_viewer),
        ("Typosquatting domain generator", typosquat_generator),
        ("Public S3 bucket name checker", s3_bucket_checker),
        ("GitHub secrets dork generator", github_secrets_dork_generator),
        ("Company email format guesser", email_format_guesser),
        ("AbuseIPDB checker", abuseipdb_checker),
        ("urlscan.io wrapper", urlscan_wrapper),
    ]),
    ("RETE & SICUREZZA AVANZATA", [
        ("SPF/DKIM/DMARC checker", spf_dkim_dmarc_checker),
        ("ASN / IP range lookup", asn_lookup),
        ("Shodan wrapper", shodan_wrapper),
        ("HIBP breach checker (email)", hibp_checker),
        ("Traceroute", traceroute_tool),
        ("SSL/TLS certificate checker", ssl_cert_checker),
        ("SSL Labs scan wrapper", ssl_labs_scan),
        ("DNS propagation checker", dns_propagation_checker),
        ("CVE lookup", cve_lookup),
        ("ARP scanner rete locale", arp_scanner),
        ("MAC vendor lookup", mac_vendor_lookup),
        ("Banner grabbing", banner_grabbing),
        ("Security.txt checker", security_txt_checker),
        ("Firewall status viewer", firewall_status_viewer),
        ("Network interfaces info", network_interfaces_info),
        ("Open redirect tester", open_redirect_tester),
        ("Directory/file brute-force scanner", dir_bruteforce),
        ("HTTP methods tester", http_methods_tester),
        ("Cookie security analyzer", cookie_security_analyzer),
        ("CORS misconfiguration checker", cors_checker),
        ("SRI checker", sri_checker),
        ("DNS zone transfer test (AXFR)", dns_axfr_test),
        ("WAF detector", waf_detector),
        ("Reverse DNS (rDNS) lookup", reverse_dns_lookup),
        ("TLS cipher suite / version scanner", tls_version_scanner),
        ("UPnP/SSDP device discovery", upnp_discovery),
        ("Port conflict checker (locale)", port_conflict_checker),
        ("Whois storico (SecurityTrails)", whois_history),
        ("HTTP/2 & HTTP/3 support checker", http2_http3_checker),
        ("Subnet calculator", subnet_calculator),
    ]),
    ("CRYPTO", [
        ("Crypto wallet address checker", wallet_address_checker),
        ("Blockchain explorer wrapper", blockchain_explorer_wrapper),
        ("Gas fee estimator (Ethereum)", gas_fee_estimator),
        ("Crypto price aggregator", crypto_price_aggregator),
        ("Smart contract verification checker", smart_contract_verification_checker),
        ("Wallet flag checker", wallet_flag_checker),
    ]),
    ("SISTEMA & DIFESA", [
        ("Hosts file inspector", hosts_file_inspector),
        ("Scheduled tasks / cron viewer", scheduled_tasks_viewer),
        ("Processi in esecuzione (euristica)", suspicious_processes_scanner),
        ("USB device history", usb_device_history),
        ("File integrity monitor", file_integrity_monitor),
        ("Clipboard secret scanner", clipboard_secret_scanner),
        ("Startup programs viewer", startup_programs_viewer),
        ("Variabili d'ambiente viewer", env_vars_viewer),
        ("Log file analyzer", log_file_analyzer),
        ("Antivirus/Defender status checker", antivirus_status_checker),
    ]),
    ("OSINT AVANZATO II", [
        ("GitHub user OSINT", github_user_osint),
        ("GitHub org members", github_org_members),
        ("NPM package OSINT", npm_package_osint),
        ("PyPI package OSINT", pypi_package_osint),
        ("Whois privacy checker", whois_privacy_checker),
        ("Website contact scraper", website_contact_scraper),
        ("Reverse image search link generator", reverse_image_search_links),
        ("Batch IP geolocation", batch_ip_geolocation),
        ("CIDR reverse DNS scanner", cidr_reverse_dns_scanner),
        ("crt.sh organization search", crtsh_org_search),
        ("DNS full dump (A/MX/TXT/NS/...)", dns_full_dump),
        ("CAA record checker", caa_record_checker),
        ("TXT record dumper", txt_record_dumper),
        ("Company logo finder", company_logo_finder),
        ("VirusTotal domain/IP checker", virustotal_domain_ip_checker),
        ("Company social links finder", company_social_links_finder),
        ("Office doc metadata extractor", office_doc_metadata_extractor),
        ("PDF metadata extractor", pdf_metadata_extractor),
        ("Domain multi-TLD squat checker", domain_multi_tld_squat_checker),
        ("Malware C2 IP checker (Feodo Tracker)", malware_c2_ip_checker),
        ("URL safety checker (Safe Browsing)", url_safety_checker),
        ("Website screenshot fetcher", website_screenshot_fetcher),
        ("Company domain finder", company_domain_finder),
        ("Shodan search wrapper", shodan_search_wrapper),
        ("ThreatFox IOC checker", threatfox_ioc_checker),
        ("DNS over HTTPS lookup", dns_over_https_lookup),
        ("Hunter.io email finder", hunter_email_finder),
        ("Telegram channel info", telegram_channel_info),
        ("Discord invite info", discord_invite_info),
        ("Reddit user OSINT", reddit_user_osint),
        ("Archive.today checker", archive_today_checker),
        ("Exploit-DB / PoC link generator", exploit_db_link_generator),
        ("Company news mentions (GNews)", company_news_mentions),
        ("IP threat intelligence aggregator", ip_abuse_history_aggregator),
        ("Domain threat intelligence aggregator", domain_threat_aggregator),
        ("WiGLE WiFi lookup", wigle_wifi_lookup),
        ("Instagram profile OSINT (esteso)", instagram_full_profile_osint),
        ("Subdomain takeover checker", subdomain_takeover_checker),
        ("Company review/profile link generator", company_glassdoor_link_generator),
        ("Shodan facet stats", shodan_facet_stats),
        ("DNS blacklist (DNSBL) checker", dns_blacklist_checker),
        ("Tor exit node checker", tor_exit_node_checker),
        ("Paste sites search link generator", pastebin_search_link_generator),
        ("Google cache / archive checker", google_cache_checker),
    ]),
    ("STRUMENTI DI ANALISI", [
        ("Hash identifier", hash_identifier),
        ("User-Agent parser", useragent_parser),
        ("Regex tester", regex_tester),
        ("JSON formatter/validator", json_formatter_validator),
        ("Mystery string / encoded data identifier", mystery_string_decoder),
        ("Domain/string similarity checker", domain_similarity_checker),
        ("CIDR merger/aggregator", cidr_merger),
        ("String entropy calculator", entropy_calculator),
    ]),
]

TOOLS = [(cat, label, func) for cat, items in CATEGORIES_ORDERED for label, func in items]

PAGE_SIZE = 10


def main():
    page = 0
    total_pages = math.ceil(len(TOOLS) / PAGE_SIZE)

    while True:
        print_banner()
        section(f"MENU — pagina {page + 1}/{total_pages}  ({len(TOOLS)} strumenti totali)")
        print()
        start = page * PAGE_SIZE
        chunk = TOOLS[start:start + PAGE_SIZE]

        last_cat = None
        for idx, (cat, label, _func) in enumerate(chunk):
            if cat != last_cat:
                print(f"\n{BLUE}{C.BOLD}-- {cat} --{C.RESET}")
                last_cat = cat
            print(f"  {BLUE}[{idx}]{C.RESET} {label}")

        print(f"\n  {C.GRAY}[n] Pagina successiva   [b] Pagina precedente   [q] Esci{C.RESET}")
        choice = input(f"\n{C.YELLOW}Scegli: {C.RESET}").strip().lower()

        if choice == "q":
            print(f"{BLUE}Ciao!{C.RESET}")
            break
        elif choice == "n":
            page = (page + 1) % total_pages
        elif choice == "b":
            page = (page - 1) % total_pages
        elif choice.isdigit() and int(choice) < len(chunk):
            chunk[int(choice)][2]()
        else:
            print(f"{C.RED}Scelta non valida.{C.RESET}")
            time.sleep(1)


if __name__ == "__main__":
    main()
