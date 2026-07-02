import http.server
import os
import unicodedata
import subprocess
import urllib.parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "radios.csv")
CONF_PATH = os.path.join(BASE_DIR, "bose.conf")
PIPE_PATH = os.path.join(BASE_DIR, "radio_pipe")

def slugify(text):
    text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8')
    return "".join(e for e in text.lower() if e.isalnum())

def load_bose_conf():
    if os.path.exists(CONF_PATH):
        conf = {}
        with open(CONF_PATH, "r") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    conf[k.upper()] = v  # Force uppercase key
        # fallback support for both French (NOM) and English (NAME)
        if "NOM" in conf and "NAME" not in conf:
            conf["NAME"] = conf["NOM"]
        return conf
    return None

def read_csv():
    radios = []
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, mode='r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("name,url") or line.startswith("nom,url"): continue
                parts = line.split(",")
                if len(parts) >= 3:
                    name = parts[0].strip().replace('"', '')
                    url = parts[1].strip().replace('"', '')
                    cat = parts[2].strip().replace('"', '')
                    radios.append({"name": name, "url": url, "cat": cat, "slug": slugify(name)})
    return radios

def write_csv(radios):
    with open(CSV_PATH, mode='w', encoding='utf-8') as f:
        f.write("name,url,category\n")
        for r in radios:
            f.write(f'"{r["name"]}","{r["url"]}","{r["cat"]}"\n')

def list_bluetooth_devices():
    devices = []
    try:
        scan_proc = subprocess.Popen(["bluetoothctl", "scan", "on"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            scan_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            scan_proc.terminate()
            scan_proc.wait()
        
        result = subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True, timeout=3)
        for line in result.stdout.splitlines():
            if line.startswith("Device "):
                parts = line.split(" ", 2)
                if len(parts) >= 3:
                    devices.append({"mac": parts[1], "name": parts[2]})
    except Exception as e:
        print("BT Scan Error:", e)
    return devices

class RadioHandler(http.server.SimpleHTTPRequestHandler):
    def _send_cmd(self, cmd):
        try:
            with open(PIPE_PATH, "w") as f:
                f.write(cmd + "\n")
        except Exception as e:
            print("Pipe Error:", e)

    def do_GET(self):
        url_parsed = urllib.parse.urlparse(self.path)
        path = url_parsed.path.strip("/")
        query = urllib.parse.parse_qs(url_parsed.query)
        
        if path == "select_device" and "mac" in query and "name" in query:
            mac = query["mac"][0]
            name = query["name"][0]
            with open(CONF_PATH, "w") as f:
                f.write(f"MAC={mac}\nNAME={name}\n")
            subprocess.run(["bluetoothctl", "pair", mac], capture_output=True)
            subprocess.run(["bluetoothctl", "trust", mac], capture_output=True)
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return

        radios = read_csv()
        all_slugs = {r["slug"] for r in radios}
        system_commands = ["start", "stop", "vol_up", "vol_down", "vol_mute", "vol_unmute", "sys_poweroff"]
        
        if path in all_slugs or path in system_commands:
            self._send_cmd(path)
            if path in all_slugs or path in ["start", "stop", "vol_up", "vol_down", "vol_mute", "vol_unmute"]:
                self.send_response(204)
                self.end_headers()
                return

        if path == "admin":
            html_admin = "<h2>⚙️ Station Management (CRUD)</h2>"
            radio_edit = {"name": "", "url": "", "cat": "", "slug": ""}
            if "edit" in query:
                for r in radios:
                    if r["slug"] == query["edit"][0]:
                        radio_edit = r
                        break
            
            action_label = "Edit" if radio_edit["slug"] else "Add"
            action_path = f"/admin/edit?slug={radio_edit['slug']}" if radio_edit["slug"] else "/admin/add"
            
            html_admin += f"""
            <div class="form-container">
                <h3>{action_label} a Station</h3>
                <form action="{action_path}" method="POST">
                    <input type="text" name="name" placeholder="Radio Name" value="{radio_edit['name']}" required><br>
                    <input type="url" name="url" placeholder="Stream URL (mp3/aac)" value="{radio_edit['url']}" required><br>
                    <input type="text" name="cat" placeholder="Category" value="{radio_edit['cat']}" required><br>
                    <button type="submit" style="background:#2ECC71; width:100%; margin-top:10px;">💾 Save</button>
                </form>
                { '<a href="/admin" style="display:block; margin-top:10px; color:#666;">Cancel</a>' if radio_edit["slug"] else '' }
            </div>
            <h3>Current Stations</h3>
            <ul class="admin-list">
            """
            for r in radios:
                html_admin += f"""
                <li>
                    <div><b>{r['name']}</b> <small style='color:#777'>({r['cat']})</small><br><span style='font-size:11px; color:#999;'>{r['url']}</span></div>
                    <div class="action-btns">
                        <button onclick="location.href='/admin?edit={r['slug']}'" style="background:#F39C12; padding:5px 10px; font-size:12px;">✏️</button>
                        <form action="/admin/delete?slug={r['slug']}" method="POST" style="display:inline;" onsubmit="return confirm('Delete {r['name']} ?')">
                            <button type="submit" style="background:#E74C3C; padding:5px 10px; font-size:12px;">🗑️</button>
                        </form>
                    </div>
                </li>
                """
            html_admin += "</ul><p><button class='vol-btn' onclick=\"location.href='/'\">Back to Remote</button></p>"
            self._render_page(html_admin)
            return

        conf_bose = load_bose_conf()
        html_content = ""
        
        if not conf_bose or path == "scan":
            html_content += "<h2>🔧 Bluetooth Setup</h2>"
            if not conf_bose:
                html_content += "<p style='color:red;'>⚠️ No speaker configured currently.</p>"
            html_content += "<button class='vol-btn' onclick=\"location.href='/scan'\">🔍 Scan Nearby Devices</button>"
            
            if path == "scan":
                devices = list_bluetooth_devices()
                if devices:
                    html_content += "<h3>Devices Found:</h3><ul style='list-style:none; padding:0; text-align:left; max-width:450px; margin: 10px auto;'>"
                    for d in devices:
                        name_encoded = urllib.parse.quote(d['name'])
                        html_content += f"<li style='padding:10px; background:#fff; margin-bottom:5px; border-radius:5px; display:flex; justify-content:space-between; align-items:center; border:1px solid #ddd;'>"
                        html_content += f"<span><b>{d['name']}</b><br><small style='color:#777'>{d['mac']}</small></span>"
                        html_content += f"<button style='background:#2ECC71; color:white; padding:5px 10px; font-size:12px;' onclick=\"location.href='/select_device?mac={d['mac']}&name={name_encoded}'\">Select</button>"
                        html_content += "</li>"
                    html_content += "</ul>"
                else:
                    html_content += "<p>No devices detected.</p>"
            if conf_bose:
                html_content += f"<p><button class='vol-btn vol-mute' onclick=\"location.href='/'\">Back to Remote</button></p>"
        else:
            categories = {}
            for r in radios:
                if r["cat"] not in categories: categories[r["cat"]] = {}
                categories[r["cat"]][r["slug"]] = r["name"]

            html_content += f"""
            <p style='color:#666; font-size:12px;'>🔊 Connected to: <b>{conf_bose['NAME']}</b> | <a href="/scan" style="color:#3498db;">Change</a> | <a href="/admin" style="color:#f39c12; font-weight:bold;">⚙️ Manage Radios</a></p>
            
            <div class="controls">
                <button class="start" onclick="fetch('/start')">🟢 POWER ON BOSE</button>
                <button class="stop" onclick="fetch('/stop')">🛑 POWER OFF</button>
            </div>

            <div class="volume-bar">
                <button class="vol-btn" onclick="fetch('/vol_down')">🔉 Down</button>
                <button id="mute-toggle-btn" class="vol-btn vol-mute" onclick="toggleMute(this)">🔇 Mute</button>
                <button class="vol-btn" onclick="fetch('/vol_up')">🔊 Up</button>
            </div>
            """

            if categories:
                html_content += '<div class="tabs-bar">\n'
                for idx, cat in enumerate(categories.keys()):
                    active_class = "active" if idx == 0 else ""
                    html_content += f'    <button class="tab-btn {active_class}" onclick="switchTab(\'{slugify(cat)}\', this)">{cat}</button>\n'
                html_content += '</div>\n'

                for idx, (cat, cat_radios) in enumerate(categories.items()):
                    display_style = "display: grid;" if idx == 0 else "display: none;"
                    html_content += f'<div id="cat-{slugify(cat)}" class="grid tab-content" style="{display_style}">\n'
                    for slug, name in cat_radios.items():
                        css_class = "radio-france" if "france" in cat.lower() else "radio-other"
                        html_content += f'    <button class="{css_class}" onclick="fetch(\'/{slug}\')">{name}</button>\n'
                    html_content += "</div>\n"
            else:
                html_content += "<p>No radios configured. Click 'Manage Radios' to add some.</p>"
                
            html_content += """
            <div style="margin-top: 40px; border-top: 1px dashed #ccc; padding-top: 20px;">
                <button class="sys-poweroff" onclick="askPoweroff()">🔴 SHUTDOWN RASPBERRY PI</button>
            </div>
            """

        self._render_page(html_content)

    def do_POST(self):
        url_parsed = urllib.parse.urlparse(self.path)
        path = url_parsed.path.strip("/")
        query = urllib.parse.parse_qs(url_parsed.query)
        
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        fields = urllib.parse.parse_qs(post_data)
        
        radios = read_csv()
        
        if path == "admin/add":
            name = fields.get("name", [""])[0].strip()
            url = fields.get("url", [""])[0].strip()
            cat = fields.get("cat", [""])[0].strip()
            if name and url and cat:
                radios.append({"name": name, "url": url, "cat": cat})
                write_csv(radios)
                
        elif path == "admin/edit" and "slug" in query:
            target_slug = query["slug"][0]
            name = fields.get("name", [""])[0].strip()
            url = fields.get("url", [""])[0].strip()
            cat = fields.get("cat", [""])[0].strip()
            for r in radios:
                if r["slug"] == target_slug:
                    r["name"], r["url"], r["cat"] = name, url, cat
                    break
            write_csv(radios)
            
        elif path == "admin/delete" and "slug" in query:
            target_slug = query["slug"][0]
            radios = [r for r in radios if r["slug"] != target_slug]
            write_csv(radios)

        self.send_response(303)
        self.send_header("Location", "/admin")
        self.end_headers()

    def _render_page(self, body_content):
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Bose Radio Remote</title>
    <style>
        body {{ font-family: sans-serif; text-align: center; background: #f4f4f9; padding: 15px; margin: 0; }}
        h1 {{ color: #333; font-size: 24px; margin-bottom: 5px; }}
        .grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; max-width: 450px; margin: 0 auto; }}
        button {{ padding: 15px 8px; font-size: 14px; font-weight: bold; border: none; border-radius: 8px; color: white; cursor: pointer; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        button:active {{ transform: scale(0.96); }}
        .radio-france {{ background: #E2001A; }}
        .radio-other {{ background: #111111; border: 1px solid #333; }}
        .volume-bar {{ display: grid; grid-template-columns: 1fr 1.2fr 1fr; gap: 10px; max-width: 450px; margin: 15px auto; }}
        .vol-btn {{ background: #34495E; padding: 12px; font-size: 14px; width:100%; box-sizing: border-box; }}
        .vol-mute {{ background: #c0392b; }}
        .vol-unmute {{ background: #27ae60; }}
        .controls {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; max-width: 450px; margin: 10px auto 15px auto; }}
        .start {{ background: #2ECC71; padding: 15px; font-size: 14px; }}
        .stop {{ background: #E74C3C; padding: 15px; font-size: 14px; }}
        .tabs-bar {{ display: flex; gap: 5px; max-width: 450px; margin: 20px auto 10px auto; border-bottom: 2px solid #ddd; padding-bottom: 5px; overflow-x: auto; }}
        .tab-btn {{ background: #bdc3c7; color: #333; font-size: 12px; padding: 8px 12px; border-radius: 6px 6px 0 0; box-shadow: none; flex-shrink: 0; }}
        .tab-btn.active {{ background: #3498db; color: white; font-weight: bold; }}
        .sys-poweroff {{ background: #c0392b; font-size: 12px; padding: 10px; width: 100%; max-width: 450px; opacity: 0.8; }}
        .form-container {{ background: white; padding: 15px; border-radius: 8px; max-width: 450px; margin: 10px auto; text-align: left; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
        .form-container input {{ width: 100%; padding: 10px; margin: 5px 0; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box; }}
        .admin-list {{ list-style: none; padding: 0; max-width: 450px; margin: 15px auto; text-align: left; }}
        .admin-list li {{ background: white; padding: 12px; margin-bottom: 6px; border-radius: 6px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #ddd; }}
        .action-btns {{ display: flex; gap: 5px; }}
    </style>
    <script>
        function switchTab(catSlug, element) {{
            document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById('cat-' + catSlug).style.display = 'grid';
            element.classList.add('active');
        }}
        function askPoweroff() {{
            if (confirm("⚠️ Safely shutdown the Raspberry Pi?")) {{
                document.body.innerHTML = "<h2 style='margin-top:100px; color:#c0392b;'>🛑 Shutting down...</h2>";
                fetch('/sys_poweroff');
            }}
        }}
        function toggleMute(btn) {{
            if (btn.classList.contains('vol-mute')) {{
                fetch('/vol_unmute'); 
                btn.textContent = '🔊 Unmute';
                btn.className = 'vol-btn vol-unmute';
            }} else {{
                fetch('/vol_mute');
                btn.textContent = '🔇 Mute';
                btn.className = 'vol-btn vol-mute';
            }}
        }}
    </script>
</head>
<body>
    <h1>📻 Bose Control Center</h1>
    {body_content}
</body>
</html>"""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

http.server.HTTPServer(("0.0.0.0", 8080), RadioHandler).serve_forever()
