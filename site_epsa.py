import os
import json
import csv
import io
from datetime import datetime

from flask import Flask, request, redirect, session, Response, send_file
import gspread
from google.oauth2.service_account import Credentials

# ===================== CONFIG =====================
app = Flask(__name__)

# No Render: defina EPSA_SECRET_KEY (qualquer texto grande)
app.secret_key = os.environ.get("EPSA_SECRET_KEY", "troque_essa_chave_no_render")

# No Render: defina EPSA_SHEET_ID (ID da planilha)
SHEET_ID = os.environ.get("EPSA_SHEET_ID", "")

# No Render: defina EPSA_ADMIN_SENHA (sua senha)
ADMIN_SENHA = os.environ.get("EPSA_ADMIN_SENHA", "1234")

# Nome da aba (worksheet) dentro da planilha
WORKSHEET_NAME = os.environ.get("EPSA_WORKSHEET_NAME", "Cadastros")
# ==================================================


# ================= GOOGLE SHEETS ==================
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

google_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
if not google_json:
    raise RuntimeError("Variável GOOGLE_SERVICE_ACCOUNT_JSON não encontrada no ambiente (Render).")

creds = Credentials.from_service_account_info(json.loads(google_json), scopes=scope)
client = gspread.authorize(creds)

if not SHEET_ID:
    raise RuntimeError("Variável EPSA_SHEET_ID não definida no ambiente (Render).")

spreadsheet = client.open_by_key(SHEET_ID)

# Pega ou cria a aba "Cadastros"
try:
    sheet = spreadsheet.worksheet(WORKSHEET_NAME)
except Exception:
    sheet = spreadsheet.add_worksheet(title=WORKSHEET_NAME, rows=2000, cols=10)


def ensure_header():
    # Cabeçalho em A1:D1
    header = ["Data/Hora", "Nome", "Email", "CPF"]
    values = sheet.get("A1:D1")
    current = values[0] if values else []
    if current != header:
        sheet.update(range_name="A1:D1", values=[header])


def only_digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())


def email_ok(email: str) -> bool:
    email = (email or "").strip()
    return ("@" in email) and ("." in email) and (len(email) <= 120)


ensure_header()
# ==================================================


# ===================== HTML BASE =====================
HOME = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>EPSA | Franquia Permute</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{
  --gold:#c9a600; --bg:#0f0f10; --card:#151518; --muted:#bdbdbd; --line:#2a2a2f;
}
*{box-sizing:border-box}
body{margin:0;font-family:Arial,sans-serif;background:var(--bg);color:#fff}
nav{background:#111;padding:14px 16px;position:sticky;top:0;border-bottom:1px solid var(--line);display:flex;gap:18px;align-items:center;justify-content:center}
nav a{color:#fff;text-decoration:none;font-weight:bold;opacity:.9}
nav a:hover{opacity:1}
.wrap{max-width:1100px;margin:0 auto;padding:28px 18px}
header{padding:56px 0 26px;text-align:center}
header img{max-width:280px;width:100%;height:auto}
header h1{font-size:40px;color:var(--gold);margin:18px 0 12px}
header p{font-size:18px;color:var(--muted);max-width:900px;margin:0 auto;line-height:1.5}
section{margin:34px 0}
h2{color:var(--gold);margin:0 0 12px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}
.card{border:1px solid var(--line);background:var(--card);padding:18px;border-radius:10px}
.cta{border:1px solid var(--line);background:#111;padding:22px;border-radius:12px;text-align:center}
.btn{display:inline-block;margin-top:10px;background:var(--gold);color:#000;padding:10px 14px;border-radius:10px;text-decoration:none;font-weight:bold}
footer{border-top:1px solid var(--line);padding:22px;text-align:center;color:#aaa;margin-top:26px}
.small{font-size:13px;color:#aaa}
</style>
</head>
<body>
<nav>
  <a href="/">Início</a>
  <a href="/clientes">Clientes</a>
  <a href="/cadastro">Cadastro</a>
  <a href="/login">Admin</a>
</nav>

<div class="wrap">
<header>
  <img src="/logo.png" alt="EPSA Logo">
  <h1>Transforme produtos e serviços em oportunidades</h1>
  <p>
    A <strong>EPSA</strong> é uma franquia autorizada da <strong>Permute</strong>, especializada em
    permutas corporativas multilaterais, ajudando empresas a reduzir custos e gerar novos negócios.
  </p>
</header>

<section>
  <h2>Quem Somos</h2>
  <div class="card">
    A EPSA atua conectando empresas de diversos segmentos dentro da rede Permute,
    permitindo a troca de produtos e serviços sem impacto direto no caixa,
    utilizando créditos internos (UP$).
  </div>
</section>

<section>
  <h2>Principais Clientes</h2>
  <div class="cards">
    <div class="card"><strong>Cacau Show</strong><br><span class="small">Brindes e ações corporativas</span></div>
    <div class="card"><strong>Kopenhagen</strong><br><span class="small">Produtos premium</span></div>
    <div class="card"><strong>Costão do Santinho</strong><br><span class="small">Hospedagem e eventos</span></div>
  </div>
</section>

<section class="cta" id="contato">
  <h2>Entre em Contato</h2>
  <p class="small">Franquia Permute operada por<br><strong>Sandro Aurélio de Carvalho</strong></p>
  <a class="btn" href="mailto:faleconosco@permute.com.br">Entrar em contato</a>
</section>

<footer>© 2026 EPSA — Franquia Permute</footer>
</div>
</body>
</html>
"""

CLIENTES = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>Clientes | Permute</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--gold:#c9a600;--bg:#0f0f10;--card:#151518;--line:#2a2a2f;--muted:#bdbdbd}
body{margin:0;font-family:Arial,sans-serif;background:var(--bg);color:#fff}
nav{background:#111;padding:14px 16px;position:sticky;top:0;border-bottom:1px solid var(--line);display:flex;gap:18px;align-items:center;justify-content:center}
nav a{color:#fff;text-decoration:none;font-weight:bold;opacity:.9}
nav a:hover{opacity:1}
.wrap{max-width:1100px;margin:0 auto;padding:28px 18px}
h1{color:var(--gold);margin:0 0 14px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px;margin-top:18px}
.card{position:relative;border:1px solid var(--line);background:var(--card);padding:18px;border-radius:10px;text-align:center;font-weight:bold}
.tooltip{
  visibility:hidden;opacity:0;position:absolute;bottom:120%;left:50%;transform:translateX(-50%);
  background:#000;color:#fff;padding:10px;border-radius:8px;width:220px;font-size:13px;
  transition:.2s;border:1px solid #333
}
.card:hover .tooltip{visibility:visible;opacity:1}
.small{color:var(--muted);font-size:13px}
</style>
</head>
<body>
<nav>
  <a href="/">Início</a>
  <a href="/clientes">Clientes</a>
  <a href="/cadastro">Cadastro</a>
  <a href="/login">Admin</a>
</nav>

<div class="wrap">
<h1>Empresas que utilizam a Permute</h1>
<div class="small">Passe o mouse por cima pra ver a descrição 👀</div>

<div class="cards">
  <div class="card">Cacau Show<div class="tooltip">Maior rede de chocolates finos do Brasil.</div></div>
  <div class="card">Kopenhagen<div class="tooltip">Marca tradicional de chocolates premium.</div></div>
  <div class="card">Costão do Santinho<div class="tooltip">Resort referência em turismo e eventos corporativos.</div></div>
  <div class="card">Azul Linhas Aéreas<div class="tooltip">Companhia aérea com ampla malha nacional.</div></div>
  <div class="card">Grupo Bisutti<div class="tooltip">Eventos sociais e corporativos de alto padrão.</div></div>
  <div class="card">Rede Atlântica Hotels<div class="tooltip">Rede hoteleira com atuação nacional.</div></div>
  <div class="card">Hering<div class="tooltip">Marca brasileira de vestuário.</div></div>
  <div class="card">Localiza<div class="tooltip">Aluguel de veículos e mobilidade corporativa.</div></div>
</div>
</div>
</body>
</html>
"""
# ==================================================


# ===================== ROTAS SITE =====================
@app.get("/logo.png")
def logo():
    # no Render, logo.png tem que estar no repo
    return send_file("logo.png", mimetype="image/png")


@app.get("/")
def home():
    return HOME


@app.get("/clientes")
def clientes():
    return CLIENTES
# ==================================================


# ===================== CADASTRO =====================
@app.get("/cadastro")
def cadastro_page():
    return """
<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>Cadastro | EPSA</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--gold:#c9a600;--bg:#0f0f10;--card:#151518;--line:#2a2a2f;--muted:#bdbdbd}
body{margin:0;font-family:Arial,sans-serif;background:var(--bg);color:#fff}
nav{background:#111;padding:14px 16px;position:sticky;top:0;border-bottom:1px solid var(--line);display:flex;gap:18px;align-items:center;justify-content:center}
nav a{color:#fff;text-decoration:none;font-weight:bold;opacity:.9}
nav a:hover{opacity:1}
.wrap{max-width:720px;margin:0 auto;padding:28px 18px}
.card{border:1px solid var(--line);background:var(--card);padding:18px;border-radius:12px}
h1{color:var(--gold);margin:0 0 12px}
label{display:block;margin-top:10px;color:var(--muted);font-size:13px}
input{width:100%;padding:12px;border-radius:10px;border:1px solid #333;background:#101012;color:#fff;margin-top:6px}
button{margin-top:14px;width:100%;padding:12px;border-radius:10px;border:0;background:var(--gold);color:#000;font-weight:bold;cursor:pointer}
#msg{margin-top:12px;font-weight:bold}
.ok{color:#7CFF9B}
.err{color:#ff8b8b}
.small{color:var(--muted);font-size:12px;margin-top:8px}
</style>
</head>
<body>
<nav>
  <a href="/">Início</a>
  <a href="/clientes">Clientes</a>
  <a href="/cadastro">Cadastro</a>
  <a href="/login">Admin</a>
</nav>

<div class="wrap">
  <div class="card">
    <h1>Cadastro</h1>
    <div class="small">Preencha e clique em enviar. Vai aparecer a mensagem aqui mesmo.</div>

    <div id="msg"></div>

    <form id="f">
      <label>Nome</label>
      <input name="nome" required maxlength="80" placeholder="Seu nome">

      <label>Email</label>
      <input name="email" required maxlength="120" placeholder="seuemail@gmail.com">

      <label>CPF</label>
      <input name="cpf" required maxlength="14" placeholder="Só números ou 000.000.000-00">

      <button type="submit">Enviar cadastro</button>
    </form>
  </div>
</div>

<script>
const f = document.getElementById("f");
const msg = document.getElementById("msg");

function setMsg(text, ok){
  msg.className = ok ? "ok" : "err";
  msg.textContent = text;
}

f.addEventListener("submit", async (e) => {
  e.preventDefault();
  setMsg("Enviando...", true);

  const fd = new FormData(f);
  const resp = await fetch("/enviar", { method: "POST", body: fd });
  let data = null;
  try { data = await resp.json(); } catch(e) {}

  if(resp.ok){
    setMsg(data?.message || "Cadastro feito ✅", true);
    f.reset();
  }else{
    setMsg(data?.message || "Deu ruim. Tenta de novo.", false);
  }
});
</script>
</body>
</html>
"""


@app.post("/enviar")
def enviar_cadastro():
    ensure_header()

    nome = (request.form.get("nome") or "").strip()
    email = (request.form.get("email") or "").strip()
    cpf = only_digits(request.form.get("cpf") or "")

    if not nome:
        return {"ok": False, "message": "Nome inválido."}, 400
    if not email_ok(email):
        return {"ok": False, "message": "Email inválido."}, 400
    if len(cpf) != 11:
        return {"ok": False, "message": "CPF inválido (tem que ter 11 dígitos)."}, 400

    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([agora, nome, email, cpf])

    return {"ok": True, "message": "Cadastro feito ✅"}, 200
# ==================================================


# ===================== ADMIN =====================
@app.get("/login")
def login_page():
    # Se já logado, manda pra /dados
    if session.get("admin"):
        return redirect("/dados")

    return """
<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>Admin | EPSA</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--gold:#c9a600;--bg:#0f0f10;--card:#151518;--line:#2a2a2f;--muted:#bdbdbd}
body{margin:0;font-family:Arial,sans-serif;background:var(--bg);color:#fff}
.wrap{max-width:520px;margin:0 auto;padding:28px 18px}
.card{border:1px solid var(--line);background:var(--card);padding:18px;border-radius:12px}
h1{color:var(--gold);margin:0 0 12px}
label{display:block;margin-top:10px;color:var(--muted);font-size:13px}
input{width:100%;padding:12px;border-radius:10px;border:1px solid #333;background:#101012;color:#fff;margin-top:6px}
button{margin-top:14px;width:100%;padding:12px;border-radius:10px;border:0;background:var(--gold);color:#000;font-weight:bold;cursor:pointer}
a{color:#fff}
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <h1>Login do Admin</h1>
    <form method="POST" action="/login">
      <label>Senha</label>
      <input type="password" name="senha" required>
      <button type="submit">Entrar</button>
    </form>
    <p style="margin-top:12px"><a href="/">Voltar</a></p>
  </div>
</div>
</body>
</html>
"""


@app.post("/login")
def login_post():
    senha = request.form.get("senha") or ""
    if senha == ADMIN_SENHA:
        session["admin"] = True
        return redirect("/dados")
    return "Senha errada.", 401


@app.get("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.get("/dados")
def dados_page():
    if not session.get("admin"):
        return redirect("/login")

    ensure_header()
    rows = sheet.get_all_values()

    # Monta tabela simples
    trs = []
    for r in rows:
        tds = "".join(f"<td style='border:1px solid #333;padding:8px'>{c}</td>" for c in r)
        trs.append(f"<tr>{tds}</tr>")
    table_html = "<table style='border-collapse:collapse;width:100%'>" + "".join(trs) + "</table>"

    return f"""
<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>Cadastros | EPSA</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{{--gold:#c9a600;--bg:#0f0f10;--card:#151518;--line:#2a2a2f;--muted:#bdbdbd}}
body{{margin:0;font-family:Arial,sans-serif;background:var(--bg);color:#fff}}
.wrap{{max-width:1100px;margin:0 auto;padding:28px 18px}}
.card{{border:1px solid var(--line);background:var(--card);padding:18px;border-radius:12px}}
h1{{color:var(--gold);margin:0 0 12px}}
.btn{{display:inline-block;background:var(--gold);color:#000;padding:10px 12px;border-radius:10px;text-decoration:none;font-weight:bold;margin-right:8px}}
input{{padding:10px;border-radius:10px;border:1px solid #333;background:#101012;color:#fff}}
button{{padding:10px 12px;border-radius:10px;border:0;background:#ff5a5a;color:#000;font-weight:bold;cursor:pointer}}
.small{{color:var(--muted);font-size:12px}}
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <h1>Cadastros (Admin)</h1>

    <div style="margin-bottom:12px">
      <a class="btn" href="/exportar_csv">Exportar CSV</a>
      <a class="btn" href="/logout">Sair</a>
    </div>

    <div style="margin:14px 0">
      <div class="small">Apagar tudo (precisa confirmar a senha):</div>
      <form method="POST" action="/apagar_tudo" style="margin-top:8px;display:flex;gap:10px;flex-wrap:wrap">
        <input type="password" name="senha_conf" placeholder="Senha admin" required>
        <button type="submit">APAGAR TUDO</button>
      </form>
    </div>

    <div style="overflow:auto;border:1px solid #333;border-radius:10px">
      {table_html}
    </div>
  </div>
</div>
</body>
</html>
"""


@app.get("/exportar_csv")
def exportar_csv():
    if not session.get("admin"):
        return redirect("/login")

    rows = sheet.get_all_values()
    out = io.StringIO()
    w = csv.writer(out)
    for r in rows:
        w.writerow(r)

    csv_bytes = out.getvalue().encode("utf-8-sig")
    return Response(
        csv_bytes,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=cadastros_epsa.csv"}
    )


@app.post("/apagar_tudo")
def apagar_tudo():
    if not session.get("admin"):
        return redirect("/login")

    senha_conf = request.form.get("senha_conf") or ""
    if senha_conf != ADMIN_SENHA:
        return "Senha incorreta.", 401

    # limpa tudo abaixo do cabeçalho
    sheet.batch_clear(["A2:Z"])
    return redirect("/dados")
# ==================================================


# ============ Local (só pra testar no PC) ==========
if __name__ == "__main__":
    # Render usa gunicorn, aqui é só pra você rodar local
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=True)
