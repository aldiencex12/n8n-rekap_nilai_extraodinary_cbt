import os
import time
import json
import zipfile
import subprocess
import urllib.request
from datetime import datetime, timedelta

def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k not in os.environ:
                        os.environ[k] = v

load_env()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
CBT_URL = os.environ.get("CBT_URL", "").rstrip("/")
CBT_EMAIL = os.environ.get("CBT_EMAIL", "").strip()
CBT_PASSWORD = os.environ.get("CBT_PASSWORD", "").strip()
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/rekap-nilai")
N8N_API_KEY = os.environ.get("N8N_API_KEY", "")
PDF_DIR = os.path.join(BASE_DIR, "rekap_pdf")
EXCLUDED_USERS = set(
    x.strip().lower() for x in os.environ.get("EXCLUDED_USERS", "coba7,coba8,coba9").split(",") if x.strip()
)

def is_excluded_user(no_ujian, nama=""):
    """Mengecek apakah nomor ujian atau nama termasuk dalam daftar akun uji coba yang dikecualikan."""
    nu = (no_ujian or "").strip().lower()
    nm = (nama or "").strip().lower()
    for ex in EXCLUDED_USERS:
        if ex and (nu == ex or nm == ex or nu.startswith(f"{ex}_") or nm.startswith(f"{ex}_")):
            return True
    return False

if not BOT_TOKEN:
    print("❌ PERINGATAN: TELEGRAM_BOT_TOKEN belum diisi di file .env!")
if not CBT_URL:
    print("❌ PERINGATAN: CBT_URL belum diisi di file .env!")
if not CBT_EMAIL:
    print("❌ PERINGATAN: CBT_EMAIL belum diisi di file .env!")
if not CBT_PASSWORD:
    print("❌ PERINGATAN: CBT_PASSWORD belum diisi di file .env!")

def get_cbt_token():
    data = json.dumps({"email": CBT_EMAIL, "password": CBT_PASSWORD}).encode()
    req = urllib.request.Request(f"{CBT_URL}/api/v1/token/generate", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())["data"]["token"]

def get_mapel_target_agama(mapel_name):
    """
    Mendeteksi apakah nama mapel spesifik untuk agama tertentu.
    Returns: 'Islam', 'Protestan', 'Katolik', 'Hindu', 'Budha', atau None jika mapel umum.
    """
    if not mapel_name:
        return None
    m = mapel_name.lower().replace("-", " ").replace("_", " ")
    
    # Deteksi Buddha
    if any(w in m for w in ["budha", "buddha"]):
        return "Budha"
    # Deteksi Hindu
    if "hindu" in m:
        return "Hindu"
    # Deteksi Katolik
    if "katolik" in m:
        return "Katolik"
    # Deteksi Kristen / Protestan
    if any(w in m for w in ["kristen", "protestan", "pak", "pa kristen"]):
        return "Protestan"
    # Deteksi Islam
    if any(w in m for w in ["islam", "pai", "pa islam"]):
        return "Islam"
        
    return None

def is_student_eligible_for_mapel(student_agama, mapel_name):
    """
    Memeriksa apakah siswa berhak/wajib mengikuti mapel tertentu berdasarkan agamanya.
    Jika mapel umum (bukan agama), mengembalikan True.
    """
    target = get_mapel_target_agama(mapel_name)
    if not target:
        return True # Mapel umum (MTK, IPA, B. Indo, dll), semua siswa wajib ikut
    
    s_ag = (student_agama or "").strip().lower()
    if not s_ag:
        # Jika data agama siswa belum tercatat, anggap berhak agar tidak hilang
        return True
        
    if target == "Islam":
        return s_ag == "islam"
    elif target in ["Protestan", "Kristen"]:
        return s_ag in ["protestan", "kristen"]
    elif target == "Katolik":
        return s_ag == "katolik"
    elif target == "Hindu":
        return s_ag == "hindu"
    elif target in ["Budha", "Buddha"]:
        return s_ag in ["budha", "buddha"]
        
    return True

_roster_cache = {
    "data": None,
    "timestamp": 0
}

def get_master_roster(token=None, force_refresh=False):
    """Mengambil daftar siswa per grup/kelas langsung dari API CBT dengan fallback ke file lokal."""
    global _roster_cache
    now = time.time()
    if not force_refresh and _roster_cache["data"] and (now - _roster_cache["timestamp"] < 300):
        return _roster_cache["data"]

    # 1. Coba ambil langsung dari CBT API (Groups & Group-Members)
    try:
        if not token:
            token = get_cbt_token()
            
        # Ambil pemetaan agama siswa langsung dari master data /api/v1/pesertas
        agama_map = {}
        try:
            req_p = urllib.request.Request(f"{CBT_URL}/api/v1/pesertas?perPage=1000", headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req_p, timeout=10) as resp_p:
                peserta_data = json.loads(resp_p.read().decode()).get("data", {}).get("data", [])
                for p_item in peserta_data:
                    nu = p_item.get("no_ujian")
                    ag = p_item.get("agama_name")
                    if nu and ag:
                        agama_map[nu.strip()] = ag.strip()
        except Exception as ep:
            print(f"Warning: Gagal fetch data agama peserta ({ep})")
        
        req_g = urllib.request.Request(f"{CBT_URL}/api/v1/groups", headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req_g, timeout=10) as resp:
            res_g = json.loads(resp.read().decode())
            
        groups = []
        for g_parent in res_g.get("data", []):
            if "child" in g_parent and isinstance(g_parent["child"], list):
                groups.extend(g_parent["child"])
            else:
                groups.append(g_parent)
                
        roster = {}
        for g in groups:
            gid = g.get("id")
            k = g.get("name", "").replace("lt-", "").upper().strip()
            if not gid or not k:
                continue
            req_m = urllib.request.Request(f"{CBT_URL}/api/v1/group-members?perPage=100&group_id={gid}", headers={"Authorization": f"Bearer {token}"})
            try:
                with urllib.request.urlopen(req_m, timeout=10) as resp_m:
                    m_res = json.loads(resp_m.read().decode())
                    items = m_res.get("data", {}).get("data", [])
                    # Urutkan siswa berdasarkan alfabet nama
                    items_sorted = sorted(items, key=lambda x: ((x.get("peserta") or {}).get("name") or "").upper())
                    roster[k] = []
                    idx = 1
                    for it in items_sorted:
                        p = it.get("peserta") or {}
                        nu = p.get("no_ujian", "")
                        nm = p.get("name", "")
                        if is_excluded_user(nu, nm):
                            continue
                        roster[k].append({
                            "no": idx,
                            "no_ujian": nu,
                            "nama": nm,
                            "agama": agama_map.get(nu.strip(), "")
                        })
                        idx += 1
            except Exception as e_m:
                print(f"Warning fetch group {k}: {e_m}")
                
        if roster:
            _roster_cache["data"] = roster
            _roster_cache["timestamp"] = now
            return roster
    except Exception as e:
        print(f"Warning: Gagal fetch roster dari CBT API ({e}), menggunakan fallback Excel lokal.")

    # 2. Fallback ke file Excel lokal jika API CBT gagal
    master_roster = {}
    excel_path = os.path.join(BASE_DIR, "format-group-member-prn-import.xlsx")
    json_path = os.path.join(BASE_DIR, "master_peserta.json")
    if os.path.exists(excel_path) and os.path.exists(json_path):
        try:
            import xml.etree.ElementTree as ET
            with open(json_path) as f:
                master_names = json.load(f)
            with zipfile.ZipFile(excel_path) as z:
                tree = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
                for r in tree.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row")[1:]:
                    cells = {}
                    for c in r.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
                        col = "".join([ch for ch in c.get("r") if ch.isalpha()])
                        is_elem = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}is")
                        v_elem = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                        val = ""
                        if is_elem is not None:
                            val = "".join([t.text for t in is_elem.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t") if t.text])
                        elif v_elem is not None:
                            val = v_elem.text
                        cells[col] = val
                    no_u = cells.get("B")
                    grp = cells.get("C")
                    if no_u and grp:
                        nm_u = master_names.get(no_u, "-")
                        if is_excluded_user(no_u, nm_u):
                            continue
                        if grp not in master_roster:
                            master_roster[grp] = []
                        master_roster[grp].append({
                            "no": int(cells.get("A")) if cells.get("A", "").isdigit() else cells.get("A"),
                            "no_ujian": no_u,
                            "nama": nm_u
                        })
            _roster_cache["data"] = master_roster
            _roster_cache["timestamp"] = now
            return master_roster
        except Exception as ef:
            print(f"Error fallback excel: {ef}")
            
    return _roster_cache.get("data") or {}

def send_message(chat_id, text, reply_markup=None):
    url = f"{API_BASE}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"Error send_message: {e}")
        return None

def edit_message_text(chat_id, message_id, text, reply_markup=None):
    url = f"{API_BASE}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"Error edit_message_text: {e}")
        return None

def answer_callback(callback_query_id, text=None):
    url = f"{API_BASE}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"Error answer_callback: {e}")
        return None

def init_bot_commands():
    try:
        commands = [
            {"command": "rekap", "description": "🔄 Pilih Jadwal & Rekap Nilai CBT"},
            {"command": "start", "description": "🏠 Buka Menu Utama & Tombol Pintasan"},
            {"command": "monitor", "description": "⏳ Pantau Ujian CBT (Live)"},
            {"command": "forcefinish", "description": "⚡ Submit Siswa Belum Selesai"},
            {"command": "susulan", "description": "📋 Cetak Daftar Siswa Susulan"},
            {"command": "pdf", "description": "📄 Unduh PDF Nilai (misal: /pdf 8D)"},
            {"command": "reset", "description": "🧹 Bersihkan File PDF Lama"}
        ]
        req = urllib.request.Request(
            f"{API_BASE}/setMyCommands",
            data=json.dumps({"commands": commands}).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass
    except Exception as e:
        print(f"Error init_bot_commands: {e}")

def get_main_menu():
    return {
        "inline_keyboard": [
            [
                {"text": "🔄 /rekap (Pilih Jadwal Ujian)", "callback_data": "cmd_rekap"}
            ],
            [
                {"text": "📘 Kelas 7", "callback_data": "menu_grade_7"},
                {"text": "📗 Kelas 8", "callback_data": "menu_grade_8"},
                {"text": "📙 Kelas 9", "callback_data": "menu_grade_9"}
            ],
            [
                {"text": "⏳ Monitor Ujian (Live)", "callback_data": "cmd_monitor"},
                {"text": "📋 Daftar Susulan", "callback_data": "cmd_susulan"}
            ],
            [
                {"text": "📦 Unduh Semua (ZIP)", "callback_data": "cmd_pdf_all"},
                {"text": "🧹 Bersihkan Cache PDF", "callback_data": "cmd_reset"}
            ]
        ]
    }

def get_grade_menu(grade):
    classes = [f"{grade}{ch}" for ch in ["A", "B", "C", "D", "E"]]
    row = [{"text": f"📄 {c}", "callback_data": f"pdf_{c}"} for c in classes]
    return {
        "inline_keyboard": [
            row,
            [{"text": "🔙 Kembali ke Menu Utama", "callback_data": "menu_main"}]
        ]
    }

def send_document(chat_id, file_path, caption=""):
    url = f"{API_BASE}/sendDocument"
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    filename = os.path.basename(file_path)
    
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
        f"{chat_id}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="caption"\r\n\r\n'
        f"{caption}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"Error send_document ({filename}): {e}")
        return None

def trigger_n8n(target_date=None):
    url = N8N_WEBHOOK_URL
    if target_date:
        url += f"?date={target_date}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True
    except Exception as e:
        print(f"Error trigger_n8n: {e}")
        return False

def round_score(val):
    """Bulatkan nilai jika bertipe float/desimal atau string dengan koma/titik."""
    if val is None or val == "" or val == "-":
        return val
    try:
        val_str = str(val).replace(",", ".").strip()
        val_float = float(val_str)
        return int(round(val_float))
    except (ValueError, TypeError):
        return val

def generate_pdfs(target_class=None, target_jadwal_id=None, target_date=None):
    """Generates print-ready PDFs with Kop, student table, absent highlight, and signatures directly from CBT API."""
    token = get_cbt_token()
    master_roster = get_master_roster(token, force_refresh=True)

    score_map = {}
    subjects_per_class = {}
    mapels_found = set()

    # 1. Direct fetch from CBT API
    try:
        date_str = target_date or datetime.now().strftime("%Y-%m-%d")
        req_j = urllib.request.Request(f"{CBT_URL}/api/v1/jadwals?start_date={date_str}&end_date={date_str}", headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req_j, timeout=10) as resp:
            all_jadwals = json.loads(resp.read().decode()).get("data", [])

        if target_jadwal_id and target_jadwal_id != "all":
            jadwals_to_process = [j for j in all_jadwals if j.get("id") == target_jadwal_id]
        else:
            jadwals_to_process = all_jadwals

        jurusan_id = "3e41ce1d-af1b-4d2c-80e1-46f6dd261403"
        for j in jadwals_to_process:
            jid = j["id"]
            mapel = j.get("alias") or j.get("nama") or "Ujian"
            mapels_found.add(mapel)
            for grp in j.get("group", []):
                gid = grp.get("id")
                k = grp.get("name", "").replace("lt-", "").upper().strip()
                if target_class and k != target_class.upper().strip():
                    continue

                url = f"{CBT_URL}/api/v1/hasil-ujians?jadwal_id={jid}&group_ids={gid}&jurusan_ids={jurusan_id}"
                req_h = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
                try:
                    with urllib.request.urlopen(req_h, timeout=15) as resp:
                        res = json.loads(resp.read().decode())
                    data_siswa = res.get("data", [])
                    if isinstance(data_siswa, dict):
                        data_siswa = data_siswa.get("data", [])
                    for item in data_siswa:
                        nu = item.get("peserta", {}).get("no_ujian", "")
                        raw_val = item.get("check_point", 0)
                        score_map[(k, mapel, nu)] = round_score(raw_val)
                    if k not in subjects_per_class:
                        subjects_per_class[k] = set()
                    subjects_per_class[k].add(mapel)
                except Exception as he:
                    print(f"Error fetching hasil ujian {mapel} for class {k}: {he}")
    except Exception as e:
        print(f"Error fetching CBT API in generate_pdfs: {e}")

    # Fallback to n8n if CBT direct fetch was empty
    if not score_map:
        API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1ZGVhMGNhOS0xNWEyLTQwYzMtYWQ0OC0yOTBlOTBhNDA3ZmMiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiOTk0OTUzNTAtMjI3Mi00MGI1LTlkMzktMzNlNmE2NjA2MWExIiwiaWF0IjoxNzg4Nzk2ODIzfQ.rutODfAQn3CHiaaig_mN_8uT0m6UxW9rzBs8zYv909w"
        try:
            req = urllib.request.Request("http://localhost:5678/api/v1/executions?limit=5", headers={"X-N8N-API-KEY": API_KEY})
            with urllib.request.urlopen(req, timeout=10) as resp:
                exec_list = json.loads(resp.read().decode())
            exec_id = None
            for item in exec_list.get("data", []):
                if item.get("status") == "success" or item.get("finished"):
                    exec_id = item["id"]
                    break
            if not exec_id and exec_list.get("data"):
                exec_id = exec_list["data"][0]["id"]
            if exec_id:
                req_det = urllib.request.Request(f"http://localhost:5678/api/v1/executions/{exec_id}?includeData=true", headers={"X-N8N-API-KEY": API_KEY})
                with urllib.request.urlopen(req_det, timeout=15) as resp:
                    exec_data = json.loads(resp.read().decode())
                all_results = exec_data["data"]["resultData"]["runData"]["Format Data (+Kelas)"][0]["data"]["main"][0]
                for item in all_results:
                    j = item["json"]
                    k = j["kelas"]
                    m = j["mata_pelajaran"]
                    nu = j["no_ujian"]
                    score_map[(k, m, nu)] = round_score(j.get("nilai", 0))
                    if k not in subjects_per_class:
                        subjects_per_class[k] = set()
                    subjects_per_class[k].add(m)
                    mapels_found.add(m)
        except Exception as e:
            print(f"n8n fallback also failed: {e}")

    os.makedirs(PDF_DIR, exist_ok=True)
    tmp_html_dir = "/tmp/rekap_html"
    os.makedirs(tmp_html_dir, exist_ok=True)

    today_str = datetime.now().strftime("%d-%m-%Y")
    today_full = datetime.now().strftime("%d %B %Y")

    classes_to_process = [target_class] if (target_class and target_class in subjects_per_class) else sorted(subjects_per_class.keys())
    generated_files = []
    classes_with_files = set()

    for k in classes_to_process:
        roster = master_roster.get(k, [])
        roster.sort(key=lambda x: x["no"] if isinstance(x["no"], int) else 999)
        
        for m in sorted(subjects_per_class[k]):
            # Opsi A: Jika mapel agama, hanya tampilkan siswa penganut agama tersebut
            target_agama = get_mapel_target_agama(m)
            if target_agama:
                effective_roster = [
                    s for s in roster 
                    if is_student_eligible_for_mapel(s.get("agama"), m) or (k, m, s["no_ujian"]) in score_map
                ]
            else:
                effective_roster = roster

            if not effective_roster:
                continue

            table_rows = []
            hadir_cnt = 0
            absen_cnt = 0
            
            for idx, s in enumerate(effective_roster):
                key = (k, m, s["no_ujian"])
                if key in score_map:
                    val = round_score(score_map[key])
                    hadir_cnt += 1
                    row_html = f"""
                    <tr>
                        <td class="center">{idx + 1}</td>
                        <td class="center">{s["no_ujian"]}</td>
                        <td>{s["nama"]}</td>
                        <td class="center bold">{val}</td>
                        <td class="center status-hadir">Hadir</td>
                    </tr>"""
                else:
                    absen_cnt += 1
                    row_html = f"""
                    <tr class="row-absen">
                        <td class="center">{idx + 1}</td>
                        <td class="center">{s["no_ujian"]}</td>
                        <td>{s["nama"]}</td>
                        <td class="center bold empty-val">-</td>
                        <td class="center status-absen">Tidak Hadir</td>
                    </tr>"""
                table_rows.append(row_html)
                
            html = f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<style>
    @page {{
        size: A4 portrait;
        margin: 12mm 15mm 15mm 15mm;
    }}
    body {{
        font-family: "Arial", "Helvetica", sans-serif;
        color: #111;
        margin: 0;
        padding: 0;
        font-size: 10pt;
    }}
    .header {{
        text-align: center;
        border-bottom: 2.5px solid #2c3e50;
        padding-bottom: 8px;
        margin-bottom: 12px;
    }}
    .header h1 {{
        margin: 0;
        font-size: 14pt;
        text-transform: uppercase;
        color: #1a252f;
        letter-spacing: 0.5px;
    }}
    .header h2 {{
        margin: 3px 0 0 0;
        font-size: 12pt;
        font-weight: bold;
        color: #2980b9;
    }}
    .meta-box {{
        width: 100%;
        margin-bottom: 12px;
        font-size: 9.5pt;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 4px;
        padding: 6px 10px;
    }}
    .meta-table {{
        width: 100%;
    }}
    .meta-table td {{
        padding: 2px 0;
        vertical-align: top;
    }}
    .data-table {{
        width: 100%;
        border-collapse: collapse;
        margin-top: 4px;
    }}
    .data-table th, .data-table td {{
        border: 1px solid #4a5568;
        padding: 4px 6px;
        font-size: 9pt;
    }}
    .data-table th {{
        background-color: #2d3748;
        color: #ffffff;
        font-weight: bold;
        text-align: center;
    }}
    .data-table tr:nth-child(even) {{
        background-color: #f7fafc;
    }}
    .row-absen {{
        background-color: #fff5f5 !important;
    }}
    .center {{ text-align: center; }}
    .bold {{ font-weight: bold; }}
    .status-hadir {{
        color: #27ae60;
        font-size: 8pt;
        font-weight: bold;
    }}
    .status-absen {{
        color: #e53e3e;
        font-size: 8pt;
        font-weight: bold;
    }}
    .empty-val {{
        color: #e53e3e;
    }}
    .sign-section {{
        margin-top: 25px;
        width: 100%;
        page-break-inside: avoid;
    }}
    .sign-box {{
        float: right;
        width: 220px;
        text-align: center;
        font-size: 9.5pt;
    }}
    .sign-space {{
        height: 55px;
    }}
</style>
</head>
<body>
    <div class="header">
        <h1>DAFTAR HASIL UJIAN ASESMEN CBT</h1>
        <h2>SMP HANG TUAH 5 SIDOARJO</h2>
    </div>

    <div class="meta-box">
        <table class="meta-table">
            <tr>
                <td style="width: 16%;"><b>Mata Pelajaran</b></td>
                <td style="width: 2%;">:</td>
                <td style="width: 48%; font-weight: bold; color: #2b6cb0;">{m}</td>
                <td style="width: 14%;"><b>Tanggal</b></td>
                <td style="width: 2%;">:</td>
                <td style="width: 18%;">{today_str}</td>
            </tr>
            <tr>
                <td><b>Kelas</b></td>
                <td>:</td>
                <td style="font-weight: bold;">{k}</td>
                <td><b>Peserta</b></td>
                <td>:</td>
                <td>Hadir: <b>{hadir_cnt}</b> | Absen: <b>{absen_cnt}</b></td>
            </tr>
        </table>
    </div>

    <table class="data-table">
        <thead>
            <tr>
                <th style="width: 6%;">No</th>
                <th style="width: 18%;">No. Ujian</th>
                <th style="width: 52%;">Nama Lengkap Peserta</th>
                <th style="width: 12%;">Nilai</th>
                <th style="width: 12%;">Status</th>
            </tr>
        </thead>
        <tbody>
            {"".join(table_rows)}
        </tbody>
    </table>

    <div class="sign-section">
        <div class="sign-box">
            Sidoarjo, {today_full}<br>
            Guru Pengampu / Proktor,
            <div class="sign-space"></div>
            <b>( _________________________ )</b><br>
            <span style="font-size: 8pt; color: #718096;">NIP. -</span>
        </div>
    </div>
</body>
</html>"""
            
            safe_m = m.replace(" ", "_").replace("/", "_").replace(":", "_")
            html_path = f"{tmp_html_dir}/rekap_{k}_{safe_m}.html"
            pdf_filename = f"Nilai_{k}_{safe_m}.pdf"
            pdf_path = f"{PDF_DIR}/{pdf_filename}"
            
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)
                
            subprocess.run(["google-chrome", "--headless", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer", f"--print-to-pdf={pdf_path}", html_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            generated_files.append(pdf_filename)
            classes_with_files.add(k)

    return {
        "success": bool(generated_files),
        "classes": sorted(list(classes_with_files)) if classes_with_files else classes_to_process,
        "files": generated_files,
        "mapels": list(mapels_found)
    }

import threading
ACTIVE_CHATS = set()

def handle_pdf(chat_id, target_class=None, force_refresh=False, target_date=None):
    if chat_id in ACTIVE_CHATS:
        send_message(chat_id, "⏳ <i>Permintaan sebelumnya sedang diproses, mohon tunggu sebentar...</i>")
        return
    ACTIVE_CHATS.add(chat_id)

    try:
        if target_class:
            target_class = target_class.upper().strip()

        all_files = sorted([f for f in os.listdir(PDF_DIR) if f.endswith(".pdf")])
        if target_class:
            matched = [f for f in all_files if f"_{target_class}_" in f or f"_{target_class}." in f or f"_{target_class}(" in f]
        else:
            matched = all_files

        # If force refresh or files not found yet, generate fresh ones
        if force_refresh or not matched:
            send_message(chat_id, "⏳ <b>Sedang memperbarui data nilai dari CBT dan membuat PDF siap print...</b>")
            generate_pdfs(target_class=target_class, target_date=target_date)
            all_files = sorted([f for f in os.listdir(PDF_DIR) if f.endswith(".pdf")])
            if target_class:
                matched = [f for f in all_files if f"_{target_class}_" in f or f"_{target_class}." in f or f"_{target_class}(" in f]
            else:
                matched = all_files

        if not matched:
            send_message(chat_id, f"❌ Tidak ditemukan file PDF untuk kelas <b>{target_class or 'Semua'}</b>.\nContoh: <code>/pdf 8D</code>, <code>/pdf 7A</code>, atau <code>/pdf all</code>.")
            return

        # If sending all classes and there are more than 4 files, bundle into ZIP
        if not target_class and len(matched) > 4:
            send_message(chat_id, f"📦 <b>Membundel {len(matched)} file PDF Rekap Nilai ke dalam file ZIP...</b>\n<i>Mohon tunggu sebentar...</i>")
            zip_filename = f"Rekap_Nilai_CBT_{datetime.now().strftime('%Y-%m-%d')}.zip"
            zip_path = os.path.join(BASE_DIR, zip_filename)
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for fname in matched:
                    zf.write(os.path.join(PDF_DIR, fname), arcname=fname)

            send_document(chat_id, zip_path, caption=f"📦 <b>Semua Rekap Nilai CBT ({len(matched)} PDF)</b>\nFormat: Dokumen resmi siap cetak.")
            send_message(
                chat_id,
                f"✅ <b>Berhasil! {len(matched)} file PDF telah dikirimkan via ZIP.</b>\n"
                f"Untuk mengunduh kelas tertentu, ketik langsung kodenya (misal: <code>8D</code>).",
                reply_markup=get_main_menu()
            )
            return
            
        send_message(
            chat_id, 
            f"📄 <b>Mengirimkan {len(matched)} file PDF Rekap Nilai siap print...</b>\n"
            f"<i>Mohon tunggu sebentar...</i>"
        )
        
        for idx, fname in enumerate(matched, 1):
            fpath = os.path.join(PDF_DIR, fname)
            title = fname.replace(".pdf", "").replace("Nilai_", "").replace("_", " ")
            caption = f"📄 [{idx}/{len(matched)}] {title}"
            send_document(chat_id, fpath, caption=caption)
            time.sleep(0.4) # Cegah flood limit Telegram
            
        send_message(
            chat_id, 
            f"✅ <b>Berhasil! Sebanyak {len(matched)} file PDF siap print telah dikirimkan.</b>\n\n"
            "<i>Dokumen sudah berformat resmi A4, rapi, dan siap cetak langsung.</i>"
        )
    finally:
        ACTIVE_CHATS.discard(chat_id)

def handle_pilih_jadwal(chat_id, target_date=None):
    """Mengambil daftar jadwal ujian aktif dari CBT dan menampilkan tombol pilihan jadwal ke proktor."""
    try:
        token = get_cbt_token()
        date_str = target_date or datetime.now().strftime("%Y-%m-%d")
        try:
            today_display = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d %B %Y")
        except Exception:
            today_display = date_str

        req_j = urllib.request.Request(f"{CBT_URL}/api/v1/jadwals?start_date={date_str}&end_date={date_str}", headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req_j, timeout=10) as resp:
            jadwals = json.loads(resp.read().decode()).get("data", [])

        if not jadwals:
            send_message(
                chat_id, 
                f"ℹ️ <b>Tidak ditemukan jadwal ujian CBT untuk tanggal {today_display}.</b>\n\n"
                f"Ketik <code>/rekap YYYY-MM-DD</code> (contoh: <code>/rekap 2026-09-07</code>) untuk memilih tanggal lain.",
                reply_markup=get_main_menu()
            )
            return

        keyboard = []
        for j in jadwals:
            alias = j.get("alias") or j.get("nama") or "Ujian"
            jid = j["id"]
            grps = [g.get("name", "").replace("lt-", "") for g in j.get("group", [])]
            grp_str = f" ({', '.join(grps[:3])}{'..' if len(grps) > 3 else ''})" if grps else ""
            keyboard.append([{"text": f"📝 {alias}{grp_str}", "callback_data": f"r_jid_{jid}"}])

        keyboard.append([{"text": "⚡ Tarik & Rekap Semua Jadwal Hari Ini", "callback_data": f"r_all_{date_str}"}])
        keyboard.append([{"text": "🔙 Kembali ke Menu", "callback_data": "menu_main"}])

        send_message(
            chat_id,
            f"📅 <b>PILIH JADWAL UJIAN CBT ({today_display})</b>\n\n"
            f"Ditemukan <b>{len(jadwals)} jadwal ujian</b>. Silakan sentuh tombol mata pelajaran yang ingin direkap dan dicetak nilainya:",
            reply_markup={"inline_keyboard": keyboard}
        )
    except Exception as e:
        print(f"Error handle_pilih_jadwal: {e}")
        send_message(chat_id, f"❌ Gagal mengambil daftar jadwal CBT: {e}")

def handle_process_jadwal(chat_id, jid, date_str=None):
    """Memproses penarikan nilai untuk jadwal yang dipilih dan menghasilkan PDF per kelas."""
    if chat_id in ACTIVE_CHATS:
        send_message(chat_id, "⏳ <i>Sedang memproses permintaan lain, mohon tunggu sebentar...</i>")
        return
    ACTIVE_CHATS.add(chat_id)
    try:
        send_message(chat_id, "⏳ <b>Sedang menarik nilai dari server CBT & menyusun dokumen PDF...</b>\n<i>Proses membutuhkan waktu 3-5 detik.</i>")
        res = generate_pdfs(target_jadwal_id=jid, target_date=date_str)
        if not res or not res.get("success"):
            send_message(chat_id, f"❌ Gagal membuat rekap nilai: {res.get('message', 'Tidak ada data nilai') if res else 'Terjadi kesalahan'}")
            return
        
        classes = res.get("classes", [])
        mapels = res.get("mapels", [])
        mapel_str = ", ".join(mapels) if mapels else "Ujian"
        
        # Susun tombol unduh untuk tiap kelas yang terproses
        class_buttons = []
        row = []
        for c in classes:
            row.append({"text": f"📄 Unduh {c}", "callback_data": f"pdf_{c}"})
            if len(row) == 3:
                class_buttons.append(row)
                row = []
        if row:
            class_buttons.append(row)
            
        class_buttons.append([{"text": "📦 Unduh Semua (ZIP)", "callback_data": "cmd_pdf_all"}])
        class_buttons.append([{"text": "🔙 Menu Utama", "callback_data": "menu_main"}])
        
        send_message(
            chat_id,
            f"✅ <b>Rekap Nilai Berhasil Dibuat!</b>\n\n"
            f"📖 <b>Mata Pelajaran:</b> {mapel_str}\n"
            f"👥 <b>Kelas Terproses:</b> {', '.join(classes)}\n"
            f"📁 <b>Total File PDF:</b> {len(res.get('files', []))} dokumen resmi\n\n"
            f"Silakan sentuh tombol kelas di bawah untuk langsung mengunduh PDF resminya:",
            reply_markup={"inline_keyboard": class_buttons}
        )
    finally:
        ACTIVE_CHATS.discard(chat_id)

def handle_susulan(chat_id, target_date=None):
    send_message(chat_id, "⏳ <b>Sedang memeriksa dan mengumpulkan data siswa susulan...</b>")

    token = get_cbt_token()
    master_roster = get_master_roster(token)

    score_map = {}
    subjects_per_class = {}
    
    # 1. Direct fetch from CBT API
    try:
        today_iso = target_date or datetime.now().strftime("%Y-%m-%d")
        try:
            today_display = datetime.strptime(today_iso, "%Y-%m-%d").strftime("%d %B %Y")
        except Exception:
            today_display = today_iso

        req_j = urllib.request.Request(f"{CBT_URL}/api/v1/jadwals?start_date={today_iso}&end_date={today_iso}", headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req_j, timeout=10) as resp:
            jadwals = json.loads(resp.read().decode()).get("data", [])

        if not jadwals:
            send_message(
                chat_id, 
                f"ℹ️ <b>Tidak ditemukan jadwal ujian CBT untuk tanggal {today_display}.</b>\n\n"
                f"Ketik <code>/susulan YYYY-MM-DD</code> (contoh: <code>/susulan 2026-09-10</code>) untuk memeriksa susulan tanggal lain.",
                reply_markup=get_main_menu()
            )
            return

        jurusan_id = "3e41ce1d-af1b-4d2c-80e1-46f6dd261403"
        for j in jadwals:
            jid = j["id"]
            mapel = j.get("alias") or j.get("nama") or "Ujian"
            for grp in j.get("group", []):
                gid = grp.get("id")
                k = grp.get("name", "").replace("lt-", "").upper().strip()
                url = f"{CBT_URL}/api/v1/hasil-ujians?jadwal_id={jid}&group_ids={gid}&jurusan_ids={jurusan_id}"
                req_h = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
                try:
                    with urllib.request.urlopen(req_h, timeout=15) as resp:
                        res = json.loads(resp.read().decode())
                    items = res.get("data", [])
                    if isinstance(items, dict):
                        items = items.get("data", [])
                    for it in items:
                        nu = it.get("peserta", {}).get("no_ujian", "")
                        score_map[(k, mapel, nu)] = it.get("check_point", 0)
                    if k not in subjects_per_class:
                        subjects_per_class[k] = set()
                    subjects_per_class[k].add(mapel)
                except Exception as e:
                    pass
    except Exception as e:
        print(f"Error fetching CBT in handle_susulan: {e}")
        send_message(chat_id, f"❌ Gagal mengambil data jadwal CBT: {e}")
        return

    susulan_list = []
    for k in sorted(subjects_per_class.keys()):
        roster = master_roster.get(k, [])
        for m in sorted(subjects_per_class[k]):
            for s in roster:
                # Lewati siswa yang agamanya tidak sesuai mapel ujian ini
                if not is_student_eligible_for_mapel(s.get("agama"), m):
                    continue
                if (k, m, s["no_ujian"]) not in score_map:
                    susulan_list.append({
                        "kelas": k,
                        "mapel": m,
                        "no_ujian": s["no_ujian"],
                        "nama": s["nama"]
                    })

    if not susulan_list:
        send_message(chat_id, "🎉 <b>Alhamdulillah! Tidak ada siswa yang perlu susulan.</b>\nSemua siswa terdaftar telah terekam nilainya di CBT.")
        return

    # Kirim ringkasan teks
    text_lines = [
        "📋 <b>DAFTAR PESERTA UJIAN SUSULAN (BELUM UJIAN)</b>",
        "🏫 <i>SMP Hang Tuah 5 Sidoarjo</i>",
        f"🗓️ Tanggal: {today_display}",
        "━━━━━━━━━━━━━━━━━━━━"
    ]
    
    grouped = {}
    for item in susulan_list:
        key = f"{item['kelas']} - {item['mapel']}"
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(item)

    for km, items in grouped.items():
        text_lines.append(f"📌 <b>{km}</b> ({len(items)} siswa):")
        for i, it in enumerate(items, 1):
            text_lines.append(f"   {i}. <code>{it['no_ujian']}</code> - {it['nama']}")
        text_lines.append("")

    text_lines.append("━━━━━━━━━━━━━━━━━━━━")
    text_lines.append(f"📊 <b>Total Siswa Belum Ujian:</b> {len(susulan_list)} data ujian")
    
    send_message(chat_id, "\n".join(text_lines))

    # Generate print-ready PDF for susulan
    try:
        today_str = datetime.strptime(today_iso, "%Y-%m-%d").strftime("%d-%m-%Y")
    except Exception:
        today_str = today_iso
    today_full = today_display
    
    rows_html = []
    for idx, it in enumerate(susulan_list, 1):
        rows_html.append(f"""
        <tr>
            <td style="text-align: center;">{idx}</td>
            <td style="text-align: center; font-weight: bold;">{it['kelas']}</td>
            <td>{it['mapel']}</td>
            <td style="text-align: center;">{it['no_ujian']}</td>
            <td>{it['nama']}</td>
            <td style="text-align: center; color: #888;">..........</td>
        </tr>
        """)

    html_susulan = f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<style>
    @page {{ size: A4 portrait; margin: 12mm 15mm 15mm 15mm; }}
    body {{ font-family: "Arial", sans-serif; font-size: 10pt; color: #111; }}
    .header {{ text-align: center; border-bottom: 2.5px solid #c0392b; padding-bottom: 8px; margin-bottom: 12px; }}
    .header h1 {{ margin: 0; font-size: 14pt; color: #c0392b; text-transform: uppercase; }}
    .header h2 {{ margin: 3px 0 0; font-size: 12pt; color: #2c3e50; }}
    .meta-box {{ background: #fff5f5; border: 1px solid #feb2b2; padding: 6px 10px; margin-bottom: 12px; border-radius: 4px; font-size: 9.5pt; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 5px; }}
    th, td {{ border: 1px solid #4a5568; padding: 5px 6px; font-size: 9pt; }}
    th {{ background: #2d3748; color: #fff; text-align: center; }}
    tr:nth-child(even) {{ background: #f7fafc; }}
    .sign {{ margin-top: 30px; width: 100%; page-break-inside: avoid; }}
    .sign-box {{ float: right; width: 220px; text-align: center; font-size: 9.5pt; }}
</style>
</head>
<body>
    <div class="header">
        <h1>DAFTAR PESERTA UJIAN SUSULAN ASESMEN CBT</h1>
        <h2>SMP HANG TUAH 5 SIDOARJO</h2>
    </div>
    <div class="meta-box">
        <b>Tanggal Cetak:</b> {today_str} &nbsp;|&nbsp; 
        <b>Total Data Susulan:</b> {len(susulan_list)} Peserta
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 5%;">No</th>
                <th style="width: 10%;">Kelas</th>
                <th style="width: 25%;">Mata Pelajaran</th>
                <th style="width: 15%;">No. Ujian</th>
                <th style="width: 30%;">Nama Lengkap</th>
                <th style="width: 15%;">Tanda Tangan</th>
            </tr>
        </thead>
        <tbody>
            {"".join(rows_html)}
        </tbody>
    </table>
    <div class="sign">
        <div class="sign-box">
            Sidoarjo, {today_full}<br>
            Koordinator Ujian Susulan,
            <div style="height: 55px;"></div>
            <b>( _________________________ )</b><br>
            <span style="font-size: 8pt; color: #718096;">NIP. -</span>
        </div>
    </div>
</body>
</html>"""

    pdf_susulan_path = f"{PDF_DIR}/Daftar_Peserta_Ujian_Susulan.pdf"
    html_susulan_path = "/tmp/rekap_html/rekap_susulan.html"
    with open(html_susulan_path, "w", encoding="utf-8") as f:
        f.write(html_susulan)
        
    subprocess.run(["google-chrome", "--headless", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer", f"--print-to-pdf={pdf_susulan_path}", html_susulan_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    send_document(chat_id, pdf_susulan_path, caption=f"📄 [Format Cetak Resmi] Daftar Siswa Ujian Susulan ({len(susulan_list)} Data)")

def handle_monitor(chat_id):
    send_message(chat_id, "⏳ <b>Menghubungi CBT untuk memantau status ujian peserta secara live...</b>")
    
    try:
        token = get_cbt_token()

        today_iso = datetime.now().strftime("%Y-%m-%d")
        yesterday_iso = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        today_full = datetime.now().strftime("%d %B %Y")
        
        req_j = urllib.request.Request(f"{CBT_URL}/api/v1/jadwals", headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req_j, timeout=10) as resp:
            all_jadwals = json.loads(resp.read().decode()).get("data", [])

        jadwals = [j for j in all_jadwals if j.get("status") == 1 or j.get("tanggal") in [today_iso, yesterday_iso]]
        if not jadwals and all_jadwals:
            jadwals = all_jadwals[:5]

        if not jadwals:
            send_message(chat_id, f"ℹ️ <b>Tidak ada jadwal ujian aktif untuk hari ini ({today_full}).</b>")
            return

        total_selesai = 0
        total_sedang = 0
        total_persiapan = 0
        sedang_list = []
        persiapan_list = []

        master_roster = get_master_roster(token)
        master_names = {s["no_ujian"]: s["nama"] for r in master_roster.values() for s in r}

        for j in jadwals:
            jid = j["id"]
            alias = j.get("alias") or j.get("nama") or "Ujian"
            
            url = f"{CBT_URL}/api/v1/siswa-ujians?page=1&perPage=250&jadwal_id={jid}"
            req_u = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            try:
                with urllib.request.urlopen(req_u, timeout=10) as resp:
                    res = json.loads(resp.read().decode())
                items = res.get("data", {}).get("data", [])
                for it in items:
                    st = it.get("status_ujian")
                    p = it.get("peserta", {})
                    nu = p.get("no_ujian", "")
                    nm = p.get("name") or master_names.get(nu, "-")
                    
                    if is_excluded_user(nu, nm):
                        continue
                    
                    if st == 3:
                        total_selesai += 1
                    elif st == 1:
                        total_sedang += 1
                        sisa_m = (it.get("sisa_waktu") or 0) // 60
                        sedang_list.append({
                            "no_ujian": nu,
                            "nama": nm,
                            "mapel": alias,
                            "sisa": sisa_m
                        })
                    elif st == 0:
                        total_persiapan += 1
                        persiapan_list.append({
                            "no_ujian": nu,
                            "nama": nm,
                            "mapel": alias
                        })
            except Exception as e:
                print(f"Error monitor jadwal {alias}: {e}")

        msg_lines = [
            "📊 <b>MONITORING STATUS UJIAN PESERTA (LIVE)</b>",
            "🏫 <i>SMP Hang Tuah 5 Sidoarjo</i>",
            f"🗓️ {today_full} | {datetime.now().strftime('%H:%M:%S')} WIB",
            "━━━━━━━━━━━━━━━━━━━━",
            f"🟢 <b>Sudah Selesai:</b> {total_selesai} peserta (Nilai siap rekap)",
            f"🟡 <b>Sedang Mengerjakan:</b> {total_sedang} peserta (Belum submit)",
            f"🔵 <b>Persiapan / Login:</b> {total_persiapan} peserta",
            "━━━━━━━━━━━━━━━━━━━━"
        ]

        monitor_markup = get_main_menu()
        if sedang_list:
            msg_lines.append("\n⚠️ <b>Siswa Masih Mengerjakan (Belum Submit):</b>")
            for idx, s in enumerate(sedang_list[:15], 1):
                msg_lines.append(f"{idx}. <code>{s['no_ujian']}</code> - <b>{s['nama']}</b>\n   └ Mapel: {s['mapel']} (Sisa: {s['sisa']} mnt)")
            if len(sedang_list) > 15:
                msg_lines.append(f"   <i>... dan {len(sedang_list) - 15} siswa lainnya.</i>")
            msg_lines.append("\n💡 <i>Klik tombol '⚡ Force Finish Semua' di bawah ini jika waktu ujian sudah habis dan ingin men-submit otomatis seluruh siswa.</i>")
            
            monitor_markup = {
                "inline_keyboard": [
                    [{"text": "⚡ Force Finish Semua (Submit Otomatis)", "callback_data": "cmd_forcefinish_all"}],
                    *get_main_menu()["inline_keyboard"]
                ]
            }
        else:
            msg_lines.append("\n✅ <b>Tidak ada siswa yang tertahan sedang mengerjakan saat ini.</b>")
            if total_selesai > 0:
                msg_lines.append(f"<i>Seluruh {total_selesai} peserta pada sesi ini telah menyelesaikan ujian dan nilainya lengkap.</i>")

        if persiapan_list:
            msg_lines.append("\n🔵 <b>Siswa dalam Status Persiapan:</b>")
            for idx, s in enumerate(persiapan_list[:10], 1):
                msg_lines.append(f"{idx}. <code>{s['no_ujian']}</code> - {s['nama']} ({s['mapel']})")
            if len(persiapan_list) > 10:
                msg_lines.append(f"   <i>... dan {len(persiapan_list) - 10} siswa lainnya.</i>")

        send_message(chat_id, "\n".join(msg_lines), reply_markup=monitor_markup)
    except Exception as e:
        print(f"Error handle_monitor: {e}")
        send_message(chat_id, f"❌ Terjadi kesalahan saat memeriksa monitor ujian: {e}")

def handle_force_finish(chat_id, target=None):
    send_message(chat_id, "⏳ <b>Menghubungi CBT untuk memproses Force Finish ujian siswa...</b>")
    
    try:
        token = get_cbt_token()

        today_iso = datetime.now().strftime("%Y-%m-%d")
        yesterday_iso = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Ambil daftar seluruh jadwal
        req_j = urllib.request.Request(f"{CBT_URL}/api/v1/jadwals", headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req_j, timeout=10) as resp:
            all_jadwals = json.loads(resp.read().decode()).get("data", [])

        # Filter jadwal aktif (status == 1) atau tanggal hari ini / kemarin
        jadwals = [j for j in all_jadwals if j.get("status") == 1 or j.get("tanggal") in [today_iso, yesterday_iso]]
        if not jadwals and all_jadwals:
            jadwals = all_jadwals[:5]

        if not jadwals:
            send_message(chat_id, "ℹ️ Tidak ditemukan jadwal ujian yang aktif.")
            return

        master_roster = get_master_roster(token)
        master_names = {s["no_ujian"]: s["nama"] for r in master_roster.values() for s in r}

        to_finish = []
        for j in jadwals:
            jid = j["id"]
            alias = j.get("alias") or j.get("nama") or "Ujian"
            url = f"{CBT_URL}/api/v1/siswa-ujians?page=1&perPage=250&jadwal_id={jid}"
            req_u = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            try:
                with urllib.request.urlopen(req_u, timeout=10) as resp:
                    res = json.loads(resp.read().decode())
                items = res.get("data", {}).get("data", [])
                for it in items:
                    # Siswa yang berstatus sedang mengerjakan (1)
                    if it.get("status_ujian") == 1:
                        p = it.get("peserta", {})
                        nu = p.get("no_ujian", "")
                        nm = p.get("name") or master_names.get(nu, "-")
                        
                        if target and target.lower() not in ["all", "semua"]:
                            tgt = target.lower()
                            if tgt not in nu.lower() and tgt not in nm.lower():
                                continue
                        else:
                            if is_excluded_user(nu, nm):
                                continue
                                
                        to_finish.append({
                            "id": it.get("id"),
                            "no_ujian": nu,
                            "nama": nm,
                            "mapel": alias
                        })
            except Exception as e:
                print(f"Error checking jadwal {alias}: {e}")

        if not to_finish:
            if target and target.lower() not in ["all", "semua"]:
                send_message(chat_id, f"ℹ️ Tidak ditemukan siswa dengan nomor/nama <b>{target}</b> yang berstatus sedang mengerjakan ujian.")
            else:
                send_message(
                    chat_id, 
                    "✅ <b>Semua siswa sudah berstatus SELESAI!</b>\n"
                    "Tidak ada siswa yang berstatus 'Sedang Mengerjakan' (tertahan belum submit) pada sesi ujian saat ini.\n\n"
                    "💡 Semua nilai ujian sudah tersimpan di CBT dan siap direkap. Ketik <code>/rekap</code> untuk mengunduh rekap PDF.",
                    reply_markup=get_main_menu()
                )
            return

        # Eksekusi Force Finish dalam batch array ID: {"id": [uuid1, uuid2, ...]}
        batch_size = 50
        success_count = 0
        failed_count = 0
        finished_items = []

        for i in range(0, len(to_finish), batch_size):
            batch = to_finish[i:i+batch_size]
            batch_ids = [s["id"] for s in batch]
            finish_payload = json.dumps({"id": batch_ids}).encode()
            f_req = urllib.request.Request(
                f"{CBT_URL}/api/v1/siswa-ujians-finish",
                data=finish_payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            )
            try:
                with urllib.request.urlopen(f_req, timeout=15) as f_resp:
                    if f_resp.status in [200, 201]:
                        success_count += len(batch)
                        for s in batch:
                            finished_items.append(f"• <code>{s['no_ujian']}</code> - <b>{s['nama']}</b> ({s['mapel']})")
                    else:
                        failed_count += len(batch)
            except Exception as fe:
                print(f"Error finishing batch: {fe}")
                failed_count += len(batch)

        result_lines = [
            "⚡ <b>HASIL FORCE FINISH UJIAN SISWA</b>",
            "━━━━━━━━━━━━━━━━━━━━",
            f"✅ <b>Berhasil Diselesaikan:</b> {success_count} siswa",
        ]
        if failed_count > 0:
            result_lines.append(f"❌ <b>Gagal:</b> {failed_count} siswa")
        
        result_lines.append("━━━━━━━━━━━━━━━━━━━━")
        if finished_items:
            result_lines.append("<b>Daftar Siswa yang Berhasil Disubmit:</b>")
            result_lines.extend(finished_items[:25])
            if len(finished_items) > 25:
                result_lines.append(f"<i>... dan {len(finished_items) - 25} siswa lainnya.</i>")

        result_lines.append("\n🎉 <i>Nilai siswa di atas sekarang telah otomatis dihitung oleh CBT dan siap ditarik ke rekap nilai!</i>")
        result_lines.append("Ketik <code>/rekap</code> atau sentuh tombol di bawah untuk langsung memperbarui file PDF.")

        send_message(chat_id, "\n".join(result_lines), reply_markup=get_main_menu())
    except Exception as e:
        print(f"Error handle_force_finish: {e}")
        send_message(chat_id, f"❌ Terjadi kesalahan saat memproses Force Finish: {e}")

def handle_git_update(chat_id):
    send_message(chat_id, "🔄 <b>Sedang memeriksa dan mengunduh pembaruan kode dari GitHub...</b>")
    try:
        res = subprocess.run(["git", "pull", "origin", "main"], capture_output=True, text=True, cwd=BASE_DIR, timeout=30)
        output = (res.stdout + "\n" + res.stderr).strip()
        if "Already up to date" in output or "Sudah mutakhir" in output:
            send_message(chat_id, f"✅ <b>Bot sudah menggunakan versi terbaru!</b>\n<pre>{output}</pre>")
        else:
            send_message(chat_id, f"🚀 <b>Kode berhasil diperbarui dari GitHub!</b>\n<pre>{output[:1500]}</pre>\n\n<i>Merestart layanan bot...</i>")
            if os.geteuid() == 0:
                subprocess.run(["systemctl", "restart", "telegram-rekap-bot.service"])
            else:
                subprocess.run(["systemctl", "--user", "restart", "telegram-rekap-bot.service"])
    except Exception as e:
        send_message(chat_id, f"❌ Gagal melakukan update kode: {e}")

def start_bot():
    print("🤖 Telegram Rekap Bot aktif dan mendengarkan pesan...")
    init_bot_commands()
    offset = 0
    while True:
        try:
            url = f"{API_BASE}/getUpdates?offset={offset}&timeout=20"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                
            for update in data.get("result", []):
                offset = update["update_id"] + 1

                # 1. Handle Callback Query (Klik Tombol Pintasan)
                cb = update.get("callback_query")
                if cb:
                    cb_id = cb["id"]
                    cb_data = cb.get("data", "")
                    cb_chat = cb.get("message", {}).get("chat", {})
                    cb_chat_id = cb_chat.get("id")
                    cb_msg_id = cb.get("message", {}).get("message_id")
                    answer_callback(cb_id)

                    if cb_data == "menu_main":
                        edit_message_text(
                            cb_chat_id, cb_msg_id, 
                            "📌 <b>Pilih Menu Rekap Nilai CBT:</b>\nSilakan sentuh tombol di bawah ini:", 
                            reply_markup=get_main_menu()
                        )
                    elif cb_data.startswith("menu_grade_"):
                        gr = cb_data.split("_")[-1]
                        edit_message_text(
                            cb_chat_id, cb_msg_id, 
                            f"📂 <b>Pilih Kelas {gr}:</b>\nSentuh kelas untuk langsung mengunduh PDF:", 
                            reply_markup=get_grade_menu(gr)
                        )
                    elif cb_data.startswith("pdf_"):
                        cls_name = cb_data.split("_")[1]
                        threading.Thread(target=handle_pdf, args=(cb_chat_id, cls_name, False, None), daemon=True).start()
                    elif cb_data == "cmd_monitor":
                        threading.Thread(target=handle_monitor, args=(cb_chat_id,), daemon=True).start()
                    elif cb_data == "cmd_forcefinish_all":
                        threading.Thread(target=handle_force_finish, args=(cb_chat_id, "all"), daemon=True).start()
                    elif cb_data == "cmd_susulan":
                        threading.Thread(target=handle_susulan, args=(cb_chat_id,), daemon=True).start()
                    elif cb_data == "cmd_rekap":
                        threading.Thread(target=handle_pilih_jadwal, args=(cb_chat_id, None), daemon=True).start()
                    elif cb_data.startswith("r_jid_"):
                        jid = cb_data.replace("r_jid_", "")
                        threading.Thread(target=handle_process_jadwal, args=(cb_chat_id, jid, None), daemon=True).start()
                    elif cb_data.startswith("r_all_"):
                        dt = cb_data.replace("r_all_", "")
                        threading.Thread(target=handle_process_jadwal, args=(cb_chat_id, "all", dt), daemon=True).start()
                    elif cb_data == "cmd_pdf_all":
                        threading.Thread(target=handle_pdf, args=(cb_chat_id, None, False, None), daemon=True).start()
                    elif cb_data == "cmd_reset":
                        cnt = 0
                        for f in os.listdir(PDF_DIR):
                            if f.endswith(".pdf"):
                                try:
                                    os.remove(os.path.join(PDF_DIR, f))
                                    cnt += 1
                                except Exception:
                                    pass
                        send_message(cb_chat_id, f"🧹 <b>Folder PDF Berhasil Dibersihkan!</b>\n{cnt} file PDF lama telah dihapus.")
                    continue

                # 2. Handle Text Message
                msg = update.get("message", {})
                text = msg.get("text", "").strip()
                chat = msg.get("chat", {})
                chat_id = chat.get("id")
                first_name = chat.get("first_name", "Pengguna")
                
                if not text or not chat_id:
                    continue
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Pesan dari {first_name} ({chat_id}): {text}")
                
                parts = text.split()
                cmd = parts[0].lower()
                arg = parts[1] if len(parts) > 1 else None
                lower_text = text.lower().strip()
                
                if cmd in ["/start", "/help", "/menu"] or lower_text in ["start", "help", "menu"]:
                    send_message(
                        chat_id,
                        f"Halo <b>{first_name}</b>! 👋\n\n"
                        "Selamat datang di <b>Bot Rekap Nilai CBT SMP Hang Tuah 5 Sidoarjo</b>.\n\n"
                        "Silakan gunakan tombol menu di bawah ini untuk akses cepat, atau ketik langsung kode kelas yang diinginkan:",
                        reply_markup=get_main_menu()
                    )
                elif lower_text.startswith("/forcefinish") or lower_text.startswith("forcefinish") or lower_text.startswith("force finish") or cmd in ["/selesai", "selesai"]:
                    target = "all"
                    words = lower_text.replace("force finish", "forcefinish").split()
                    if len(words) > 1 and words[1] not in ["all", "semua"]:
                        target = words[1]
                    threading.Thread(target=handle_force_finish, args=(chat_id, target), daemon=True).start()
                elif cmd in ["/monitor", "/pantau", "/status"] or lower_text in ["monitor", "pantau", "status"]:
                    threading.Thread(target=handle_monitor, args=(chat_id,), daemon=True).start()
                elif cmd in ["/susulan", "/absen"] or lower_text in ["susulan", "absen"]:
                    tgt_date = arg if (arg and "-" in arg and len(arg) == 10) else None
                    threading.Thread(target=handle_susulan, args=(chat_id, tgt_date), daemon=True).start()
                elif cmd in ["/reset", "/clean", "/hapus"] or lower_text in ["reset", "clean", "hapus"]:
                    cnt = 0
                    for f in os.listdir(PDF_DIR):
                        if f.endswith(".pdf"):
                            try:
                                os.remove(os.path.join(PDF_DIR, f))
                                cnt += 1
                            except Exception:
                                pass
                    send_message(
                        chat_id,
                        f"🧹 <b>Folder PDF berhasil dibersihkan!</b>\n"
                        f"Sebanyak {cnt} file PDF lama telah dihapus.\n\n"
                        f"Ketik <code>/rekap</code> atau <code>/pdf [KELAS]</code> kapan saja untuk otomatis menarik data ujian baru dari CBT."
                    )
                elif cmd in ["/pdf"]:
                    tgt = None if (arg and arg.lower() == "all") else arg
                    threading.Thread(target=handle_pdf, args=(chat_id, tgt, False, None), daemon=True).start()
                elif cmd in ["/update", "/gitpull"] or lower_text in ["update bot", "git pull", "gitpull"]:
                    threading.Thread(target=handle_git_update, args=(chat_id,), daemon=True).start()
                elif cmd in ["/rekap", "/refresh"] or lower_text in ["rekap", "refresh"]:
                    tgt_date = None
                    if arg:
                        if "-" in arg and len(arg) == 10:
                            tgt_date = arg
                            threading.Thread(target=handle_pilih_jadwal, args=(chat_id, tgt_date), daemon=True).start()
                        else:
                            threading.Thread(target=handle_pdf, args=(chat_id, arg, True, None), daemon=True).start()
                    else:
                        threading.Thread(target=handle_pilih_jadwal, args=(chat_id, None), daemon=True).start()
                else:
                    possible_class = cmd.replace("/", "").upper()
                    if possible_class in ["7A", "7B", "7C", "7D", "7E", "8A", "8B", "8C", "8D", "8E", "9A", "9B", "9C", "9D", "9E"]:
                        threading.Thread(target=handle_pdf, args=(chat_id, possible_class, False, None), daemon=True).start()
                    else:
                        send_message(
                            chat_id,
                            f"Ketik <code>/start</code> untuk membuka menu tombol pintasan, atau ketik <code>/pdf 8D</code> untuk unduh nilai.",
                            reply_markup=get_main_menu()
                        )
        except Exception as e:
            print(f"Bot loop exception: {e}")
            time.sleep(2)

if __name__ == "__main__":
    start_bot()
