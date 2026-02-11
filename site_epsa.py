import os
import math
import time
import csv
import io
from datetime import datetime

from flask import Flask, request, redirect, url_for, session, send_file, Response
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# ===================== CONFIG =====================
app.secret_key = os.environ.get("EPSA_SECRET_KEY", "CHAVE_GRANDE_ALEATORIA_TROCA_ISSO_123456789")

SHEET_ID = os.environ.get("EPSA_SHEET_ID", "14DrTADTPQ2xZWETMuwEShPbzuMsbV4TDHyCDFE1CY9c")
ADMIN_SENHA = os.environ.get("EPSA_ADMIN_SENHA", "487808")  # TROCA PRA SUA SENHA

PER_PAGE = 25

# Anti-spam: X cadastros por janela (por IP)
RATE_LIMIT_MAX = 3
RATE_LIMIT_WINDOW_SEC = 60
# ==================================================

# ================= GOOGLE SHEETS ==================
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_file("credenciais.json", scopes=scope)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(SHEET_ID)
sheet = spreadsheet.sheet1
# ==================================================


def so_numeros(txt: str) -> str:
    return "".join(ch for ch in (txt or "") if ch.isdigit())


def email_ok(email: str) -> bool:
    email = (email or "").strip()
    return ("@" in email) and ("." in email) and (len(email) <= 120)


def mascara_cpf(cpf: str) -> str:
    cpf = so_numeros(cpf)
    if len(cpf) != 11:
        return "***"
    return "***.***.***-" + cpf[-2:]


def ensure_header():
    try:
        values = sheet.get("A1:D1")
        row = values[0] if values else []
        expected = ["Data/Hora", "Nome", "Email", "CPF"]
        if row != expected:
            if not row or all((c == "" for c in row)):
                sheet.update(range_name="A1:D1", values=[expected])
            else:
                sheet.insert_row(expected, 1)
    except Exception:
        pass


def get_ip() -> str:
    # Se um dia tiver proxy, da pra usar X-Forwarded-For, mas por agora é isso
    return request.remote_addr or "unknown"


# ===================== SEGURANÇA ADMIN (tentativas) =====================
# Guarda tentativas por IP na sessão (simples e suficiente pro local/pequeno)
LOCK_AFTER = 5
LOCK_SECONDS = 300  # 5 minutos


def is_locked(ip: str) -> bool:
    lock_until = session.get(f"lock_until:{ip}", 0)
    return time.time() < lock_until


def register_failed_login(ip: str):
    key = f"fails:{ip}"
    fails = int(session.get(key, 0)) + 1
    session[key] = fails
    if fails >= LOCK_AFTER:
        session[f"lock_until:{ip}"] = time.time() + LOCK_SECONDS


def clear_failed_login(ip: str):
    session.pop(f"fails:{ip}", None)
    session.pop(f"lock_until:{ip}", None)
# =======================================================================


# ===================== ANTI-SPAM (cadastro por IP) =====================
# Guarda timestamps na sessão (pra projeto pequeno/local tá ótimo)
def rate_limit_ok(ip: str) -> bool:
    now = time.time()
    key = f"rl:{ip}"
    arr = session.get(key, [])
    # limpa registros velhos
    arr = [t for t in arr if now - t < RATE_LIMIT_WINDOW_SEC]
    if len(arr) >= RATE_LIMIT_MAX:
        session[key] = arr
        return False
    arr.append(now)
    session[key] = arr
    return True
# =======================================================================


# ===================== PÁGINAS =====================

HOME = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>EPSA | Franquia Permute</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body{margin:0;font-family:Arial,sans-serif;background:#fff;color:#000}
header{padding:80px 20px;text-align:center}
header img{max-width:420px}
header h1{font-size:42px;color:#c9a600;margin:20px 0}
header p{font-size:20px;color:#333;max-width:900px;margin:auto}
nav{background:#f2f2f2;padding:15px;text-align:center;position:sticky;top:0;z-index:10}
nav a{color:#000;margin:0 18px;text-decoration:none;font-weight:bold}
section{max-width:1200px;margin:80px auto;padding:0 20px}
h2{color:#c9a600}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:25px}
.cardx{border:1px solid #ddd;padding:30px;border-radius:10px}
.cta{background:#f7f7f7;padding:70px 20px;text-align:center}
footer{background:#f2f2f2;text-align:center;padding:30px}
</style>
</head>

<body>

<header>
<img src="/logo.png">
<h1>Transforme produtos e serviços em oportunidades</h1>
<p>
A <strong>EPSA</strong> é uma franquia autorizada da <strong>Permute</strong>, especializada em
permutas corporativas multilaterais, ajudando empresas a reduzir custos
e gerar novos negócios.
</p>

<div class="d-flex justify-content-center gap-2 mt-4 flex-wrap">
  <a class="btn btn-dark px-4 py-2" href="/cadastro">Quero me cadastrar</a>
  <a class="btn btn-outline-dark px-4 py-2" href="/login">Área admin</a>
</div>
</header>

<nav>
<a href="/">Início</a>
<a href="/clientes">Clientes</a>
<a href="#contato">Contato</a>
<a href="/cadastro">Cadastro</a>
</nav>

<section>
<h2>Quem Somos</h2>
<p>
A EPSA atua conectando empresas de diversos segmentos dentro da rede Permute,
permitindo a troca de produtos e serviços sem impacto direto no caixa,
utilizando créditos internos (UP$).
</p>
</section>

<section>
<h2>Principais Clientes</h2>
<div class="cards">
<div class="cardx"><strong>Cacau Show</strong><br>Brindes e ações corporativas</div>
<div class="cardx"><strong>Kopenhagen</strong><br>Produtos premium</div>
<div class="cardx"><strong>Costão do Santinho</strong><br>Hospedagem e eventos</div>
</div>
</section>

<section id="contato" class="cta">
<h2>Entre em Contato</h2>
<p>
Franquia Permute operada por<br>
<strong>Sandro Aurélio de Carvalho</strong>
</p>
<a href="mailto:faleconosco@permute.com.br">Entrar em contato</a>
</section>

<footer>
© 2026 EPSA — Franquia Permute
</footer>

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
body{margin:0;font-family:Arial,sans-serif;background:#fff;color:#000}
nav{background:#f2f2f2;padding:15px;text-align:center;position:sticky;top:0}
nav a{color:#000;margin:0 18px;text-decoration:none;font-weight:bold}
section{max-width:1200px;margin:60px auto;padding:0 20px}
h1{color:#c9a600}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:20px;margin-top:40px}
.card{
    position:relative;
    border:1px solid #ddd;
    padding:20px;
    border-radius:10px;
    text-align:center;
    font-weight:bold;
}
.tooltip{
    visibility:hidden;
    opacity:0;
    position:absolute;
    bottom:120%;
    left:50%;
    transform:translateX(-50%);
    background:#000;
    color:#fff;
    padding:10px;
    border-radius:8px;
    width:220px;
    font-size:14px;
    transition:0.2s;
}
.card:hover .tooltip{
    visibility:visible;
    opacity:1;
}
</style>
</head>

<body>

<nav>
<a href="/">Início</a>
<a href="/clientes">Clientes</a>
<a href="/cadastro">Cadastro</a>
</nav>

<section>
<h1>Empresas que utilizam a Permute</h1>

<div class="cards">
<div class="card">Cacau Show
<div class="tooltip">Maior rede de chocolates finos do Brasil.</div>
</div>

<div class="card">Kopenhagen
<div class="tooltip">Marca tradicional de chocolates premium.</div>
</div>

<div class="card">Costão do Santinho
<div class="tooltip">Resort referência em turismo e eventos corporativos.</div>
</div>

<div class="card">Azul Linhas Aéreas
<div class="tooltip">Companhia aérea com ampla malha nacional.</div>
</div>

<div class="card">Grupo Bisutti
<div class="tooltip">Eventos sociais e corporativos de alto padrão.</div>
</div>

<div class="card">Rede Atlântica Hotels
<div class="tooltip">Rede hoteleira com atuação nacional.</div>
</div>

<div class="card">Hering
<div class="tooltip">Marca brasileira de vestuário.</div>
</div>

<div class="card">Localiza
<div class="tooltip">Aluguel de veículos e mobilidade corporativa.</div>
</div>
</div>
</section>

</body>
</html>
"""

CADASTRO = """
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <title>Cadastro | EPSA</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body { background: #f6f7f9; }
    .wrap { max-width: 720px; margin: 0 auto; }
    .brand { color: #c9a600; font-weight: 800; letter-spacing: .3px; }
    .card { border: 0; }
    .hint { font-size: .92rem; color: #6c757d; }
    .req { color: #c0392b; }
  </style>
</head>
<body>
  <div class="container py-5 wrap">
    <div class="mb-4 text-center">
      <div class="brand h3 m-0">EPSA</div>
      <div class="text-secondary">Franquia Permute • Cadastro de interesse</div>
    </div>

    <div class="card shadow-sm rounded-4">
      <div class="card-body p-4 p-md-5">
        <h2 class="h4 mb-1">Quero me cadastrar</h2>
        <p class="text-secondary mb-4">
          Preencha os dados abaixo e a gente entra em contato.
        </p>

        <div id="msgArea" class="d-none alert" role="alert"></div>

        <form method="POST" action="/enviar" id="cadForm">
          <div class="row g-3">
            <div class="col-12">
              <label class="form-label">Nome completo <span class="req">*</span></label>
              <input class="form-control form-control-lg" name="nome" id="nome"
                     placeholder="Ex: Arthur Silva" required maxlength="80" autocomplete="name">
              <div class="hint mt-1">Digite seu nome como você usa no dia a dia.</div>
            </div>

            <div class="col-12 col-md-7">
              <label class="form-label">Email <span class="req">*</span></label>
              <input class="form-control form-control-lg" name="email" id="email" type="email"
                     placeholder="ex: voce@email.com" required maxlength="120" autocomplete="email">
            </div>

            <div class="col-12 col-md-5">
              <label class="form-label">CPF <span class="req">*</span></label>
              <input class="form-control form-control-lg" name="cpf" id="cpf"
                     placeholder="000.000.000-00" required inputmode="numeric" autocomplete="off">
              <div class="hint mt-1">Pode digitar com pontos/traço ou só números.</div>
            </div>

            <div class="col-12">
              <div class="alert alert-light border mt-2 mb-0">
                <strong>Privacidade:</strong> seus dados serão usados apenas para contato e registro interno.
              </div>
            </div>

            <div class="col-12 d-grid mt-3">
              <button class="btn btn-dark btn-lg" id="btnSend" type="submit">
                Enviar cadastro
              </button>
              <a class="btn btn-link mt-2" href="/">Voltar pro site</a>
            </div>
          </div>
        </form>
      </div>
    </div>

    <div class="text-center text-secondary mt-4 small">
      © 2026 EPSA — Franquia Permute
    </div>
  </div>

  <script>
    const cpfInput = document.getElementById("cpf");
    const form = document.getElementById("cadForm");
    const btn = document.getElementById("btnSend");
    const msgArea = document.getElementById("msgArea");

    function onlyDigits(s){ return (s || "").replace(/\\D/g, ""); }

    function showMsg(type, text){
      msgArea.classList.remove("d-none", "alert-success", "alert-danger", "alert-warning");
      msgArea.classList.add("alert-" + type);
      msgArea.textContent = text;
      msgArea.scrollIntoView({behavior:"smooth", block:"center"});
    }

    cpfInput.addEventListener("input", () => {
      let v = onlyDigits(cpfInput.value).slice(0, 11);
      let out = v;
      if (v.length > 3) out = v.slice(0,3) + "." + v.slice(3);
      if (v.length > 6) out = out.slice(0,7) + "." + out.slice(7);
      if (v.length > 9) out = out.slice(0,11) + "-" + out.slice(11);
      cpfInput.value = out;
    });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();

      const cpfDigits = onlyDigits(cpfInput.value);
      if (cpfDigits.length !== 11) {
        showMsg("danger", "CPF inválido: precisa ter 11 números.");
        cpfInput.focus();
        return;
      }

      btn.disabled = true;
      btn.textContent = "Enviando...";

      try {
        const formData = new FormData(form);
        const resp = await fetch("/enviar", { method: "POST", body: formData });
        const data = await resp.json();

        if (!resp.ok) {
          showMsg("danger", data.message || "Deu ruim. Tenta de novo.");
        } else {
          showMsg("success", data.message || "Cadastro feito ✅");
          form.reset();
        }
      } catch (err) {
        showMsg("danger", "Erro de conexão. Tenta de novo.");
      } finally {
        btn.disabled = false;
        btn.textContent = "Enviar cadastro";
      }
    });
  </script>
</body>
</html>
"""

LOGIN = """
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <title>Admin | EPSA</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
  <div class="container py-5" style="max-width: 420px;">
    <div class="card shadow-sm rounded-4">
      <div class="card-body p-4">
        <h3 class="mb-3">Área Admin</h3>
        <form method="POST" action="/login">
          <div class="mb-2">
            <label class="form-label">Senha</label>
            <input class="form-control" name="senha" type="password" required>
          </div>

          <div class="text-secondary small mb-3">
            Se errar muitas vezes, o acesso bloqueia por alguns minutos.
          </div>

          <button class="btn btn-dark w-100 py-2">Entrar</button>
        </form>
        <div class="mt-3">
          <a href="/">Voltar</a>
        </div>
      </div>
    </div>
  </div>
</body>
</html>
"""

# ===================== ROTAS =====================

@app.get("/logo.png")
def logo():
    return send_file("logo.png", mimetype="image/png")


@app.get("/")
def home():
    return HOME


@app.get("/clientes")
def clientes():
    return CLIENTES


@app.get("/cadastro")
def cadastro():
    return CADASTRO


# ✅ cadastro via fetch (JSON) + anti-spam por IP
@app.post("/enviar")
def enviar():
    ensure_header()

    ip = get_ip()
    if not rate_limit_ok(ip):
        return {"ok": False, "message": "Muitos envios em pouco tempo. Aguarda 1 minutinho e tenta de novo."}, 429

    nome = (request.form.get("nome") or "").strip()
    email = (request.form.get("email") or "").strip()
    cpf = so_numeros(request.form.get("cpf"))

    if not nome:
        return {"ok": False, "message": "Nome inválido."}, 400
    if not email_ok(email):
        return {"ok": False, "message": "Email inválido."}, 400
    if len(cpf) != 11:
        return {"ok": False, "message": "CPF inválido (precisa ter 11 números)."}, 400

    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([agora, nome, email, cpf])

    return {"ok": True, "message": "Cadastro feito ✅"}, 200


@app.get("/login")
def login():
    return LOGIN


# ✅ login com bloqueio após tentativas
@app.post("/login")
def login_post():
    ip = get_ip()

    if is_locked(ip):
        return "Acesso bloqueado por algumas tentativas. Espera uns minutos e tenta de novo.", 429

    senha = request.form.get("senha") or ""
    if senha == ADMIN_SENHA:
        session["admin"] = True
        clear_failed_login(ip)
        return redirect(url_for("dados"))

    register_failed_login(ip)
    return "Senha errada.", 401


@app.get("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("home"))


# ✅ exportar CSV (admin)
@app.get("/exportar_csv")
def exportar_csv():
    if not session.get("admin"):
        return redirect(url_for("login"))

    ensure_header()
    rows = sheet.get_all_values()

    output = io.StringIO()
    writer = csv.writer(output)
    for r in rows:
        writer.writerow(r)

    csv_bytes = output.getvalue().encode("utf-8-sig")
    return Response(
        csv_bytes,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=cadastros_epsa.csv"}
    )


# ✅ apagar tudo (pede senha de confirmação)
@app.post("/apagar_tudo")
def apagar_tudo():
    if not session.get("admin"):
        return redirect(url_for("login"))

    senha_conf = request.form.get("senha_conf") or ""
    if senha_conf != ADMIN_SENHA:
        return redirect(url_for("dados", err="Senha de confirmação incorreta."))

    ensure_header()
    sheet.batch_clear(["A2:D"])  # apaga tudo abaixo do cabeçalho
    return redirect(url_for("dados", ok="Todos os registros foram apagados."))


@app.get("/dados")
def dados():
    if not session.get("admin"):
        return redirect(url_for("login"))

    ensure_header()

    q = (request.args.get("q") or "").strip().lower()
    page = int(request.args.get("page") or "1")
    page = max(page, 1)

    ok_msg = (request.args.get("ok") or "").strip()
    err_msg = (request.args.get("err") or "").strip()

    rows = sheet.get_all_values()  # ✅ sem limite total

    header = rows[0] if rows else ["Data/Hora", "Nome", "Email", "CPF"]
    data_rows = rows[1:] if len(rows) > 1 else []

    if q:
        data_rows = [r for r in data_rows if q in (" ".join(r)).lower()]

    total = len(data_rows)
    total_pages = max(1, math.ceil(total / PER_PAGE))

    if page > total_pages:
        page = total_pages

    start = (page - 1) * PER_PAGE
    end = start + PER_PAGE
    page_rows = data_rows[start:end]

    trs = ""
    for r in page_rows:
        r = (r + ["", "", "", ""])[:4]
        data_hora, nome, email, cpf = r
        trs += f"<tr><td>{data_hora}</td><td>{nome}</td><td>{email}</td><td>{mascara_cpf(cpf)}</td></tr>"

    prev_link = ""
    next_link = ""
    if page > 1:
        prev_link = f'<a class="btn btn-outline-secondary btn-sm" href="/dados?q={q}&page={page-1}">← Anterior</a>'
    if page < total_pages:
        next_link = f'<a class="btn btn-outline-secondary btn-sm" href="/dados?q={q}&page={page+1}">Próxima →</a>'

    alert_html = ""
    if ok_msg:
        alert_html += f'<div class="alert alert-success">{ok_msg}</div>'
    if err_msg:
        alert_html += f'<div class="alert alert-danger">{err_msg}</div>'

    return f"""
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <title>Cadastros | EPSA</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
  <div class="container py-5">
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h3 class="m-0">Cadastros</h3>

      <div class="d-flex gap-2 align-items-center flex-wrap">
        <a class="btn btn-outline-dark" href="/">Início</a>
        <a class="btn btn-outline-primary" href="/exportar_csv">Baixar CSV</a>
        <a class="btn btn-outline-danger" href="/logout">Sair</a>
      </div>
    </div>

    {alert_html}

    <div class="card shadow-sm rounded-4 mb-3">
      <div class="card-body">
        <div class="d-flex gap-2 flex-wrap">
          <form class="d-flex gap-2 flex-grow-1" method="GET" action="/dados" style="min-width:260px;">
            <input class="form-control" name="q" placeholder="Buscar..." value="{q}">
            <button class="btn btn-dark">Buscar</button>
          </form>

          <form method="POST" action="/apagar_tudo" class="d-flex gap-2 align-items-center"
                onsubmit="return confirm('Tem certeza que quer apagar TODOS os registros? Isso não dá pra desfazer.');">
            <input class="form-control" name="senha_conf" type="password" placeholder="Senha pra confirmar" required style="max-width:220px;">
            <button class="btn btn-danger" type="submit">Apagar tudo</button>
          </form>
        </div>
        <div class="text-secondary small mt-2">
          Dica: “Apagar tudo” só funciona com a senha certa.
        </div>
      </div>
    </div>

    <div class="card shadow-sm rounded-4">
      <div class="card-body p-0">
        <div class="table-responsive">
          <table class="table table-hover m-0">
            <thead class="table-light">
              <tr>
                <th>{header[0]}</th><th>{header[1]}</th><th>{header[2]}</th><th>{header[3]} (mascarado)</th>
              </tr>
            </thead>
            <tbody>
              {trs if trs else '<tr><td colspan="4" class="p-4">Nada encontrado.</td></tr>'}
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="d-flex justify-content-between align-items-center mt-3">
      <div>{prev_link}</div>
      <div class="text-secondary">Página {page} de {total_pages} — {total} registros</div>
      <div>{next_link}</div>
    </div>
  </div>
</body>
</html>
"""


if __name__ == "__main__":
    ensure_header()
    print("🚀 Rodando em http://127.0.0.1:8000")
    app.run(host="127.0.0.1", port=8000, debug=True)
