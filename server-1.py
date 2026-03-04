from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import mercadopago
import os
import uuid
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Access Token vem da variável de ambiente no Railway (mais seguro)
MP_TOKEN = os.environ.get("MP_ACCESS_TOKEN", "APP_USR-6862352104699240-030417-cbef20208cf56985bc41db5c2b0e0f82-2577776355")
MP_PUBLIC_KEY = os.environ.get("MP_PUBLIC_KEY", "APP_USR-8009f5b7-c130-422a-950c-ac9d6a48c64f")
sdk = mercadopago.SDK(MP_TOKEN)

# ── SERVE O SITE ──
@app.route("/")
def index():
    return render_template("index.html", mp_public_key=MP_PUBLIC_KEY)

# ── CRIAR PAGAMENTO PIX ──
@app.route("/api/pix", methods=["POST"])
def criar_pix():
    data = request.json
    valor = float(data.get("valor", 0))
    nome  = data.get("nome", "Cliente")
    email = data.get("email", "cliente@email.com")
    servico = data.get("servico", "Serviço CodeGyn Studio")

    if valor <= 0:
        return jsonify({"erro": "Valor inválido"}), 400

    payment_data = {
        "transaction_amount": valor,
        "description": servico,
        "payment_method_id": "pix",
        "payer": {
            "email": email,
            "first_name": nome.split()[0],
            "last_name": nome.split()[-1] if len(nome.split()) > 1 else ".",
        }
    }

    result = sdk.payment().create(payment_data)
    payment = result["response"]

    if result["status"] == 201:
        return jsonify({
            "id": payment["id"],
            "status": payment["status"],
            "qr_code": payment["point_of_interaction"]["transaction_data"]["qr_code"],
            "qr_code_base64": payment["point_of_interaction"]["transaction_data"]["qr_code_base64"],
            "valor": valor
        })
    else:
        return jsonify({"erro": payment.get("message", "Erro ao gerar Pix")}), 400

# ── CRIAR PAGAMENTO CARTÃO ──
@app.route("/api/cartao", methods=["POST"])
def criar_cartao():
    data = request.json
    valor      = float(data.get("valor", 0))
    email      = data.get("email", "cliente@email.com")
    nome       = data.get("nome", "Cliente")
    token      = data.get("token")          # token gerado pelo MP no frontend
    parcelas   = int(data.get("parcelas", 1))
    servico    = data.get("servico", "Serviço CodeGyn Studio")
    id_metodo  = data.get("payment_method_id", "")

    if not token:
        return jsonify({"erro": "Token do cartão não informado"}), 400

    payment_data = {
        "transaction_amount": valor,
        "token": token,
        "description": servico,
        "installments": parcelas,
        "payment_method_id": id_metodo,
        "payer": {
            "email": email,
            "first_name": nome.split()[0],
            "last_name": nome.split()[-1] if len(nome.split()) > 1 else ".",
        }
    }

    result = sdk.payment().create(payment_data)
    payment = result["response"]

    if result["status"] == 201:
        return jsonify({
            "id": payment["id"],
            "status": payment["status"],
            "status_detail": payment["status_detail"],
            "valor": valor
        })
    else:
        return jsonify({"erro": payment.get("message", "Erro no cartão")}), 400

# ── CRIAR BOLETO ──
@app.route("/api/boleto", methods=["POST"])
def criar_boleto():
    data  = request.json
    valor = float(data.get("valor", 0))
    email = data.get("email", "cliente@email.com")
    nome  = data.get("nome", "Cliente")
    cpf   = data.get("cpf", "")
    servico = data.get("servico", "Serviço CodeGyn Studio")

    payment_data = {
        "transaction_amount": valor,
        "description": servico,
        "payment_method_id": "bolbradesco",
        "payer": {
            "email": email,
            "first_name": nome.split()[0],
            "last_name": nome.split()[-1] if len(nome.split()) > 1 else ".",
            "identification": {
                "type": "CPF",
                "number": cpf.replace(".", "").replace("-", "")
            }
        }
    }

    result = sdk.payment().create(payment_data)
    payment = result["response"]

    if result["status"] == 201:
        return jsonify({
            "id": payment["id"],
            "status": payment["status"],
            "boleto_url": payment.get("transaction_details", {}).get("external_resource_url", ""),
            "barcode": payment.get("barcode", {}).get("content", ""),
            "valor": valor,
            "vencimento": payment.get("date_of_expiration", "")
        })
    else:
        return jsonify({"erro": payment.get("message", "Erro ao gerar boleto")}), 400

# ── VERIFICAR STATUS DO PAGAMENTO ──
@app.route("/api/status/<payment_id>", methods=["GET"])
def checar_status(payment_id):
    result = sdk.payment().get(payment_id)
    payment = result["response"]
    return jsonify({
        "id": payment.get("id"),
        "status": payment.get("status"),
        "status_detail": payment.get("status_detail"),
        "valor": payment.get("transaction_amount")
    })

# ── WEBHOOK DO MERCADO PAGO ──
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json or {}
    if data.get("type") == "payment":
        payment_id = data["data"]["id"]
        result = sdk.payment().get(payment_id)
        payment = result["response"]
        status = payment.get("status")
        valor  = payment.get("transaction_amount")
        email  = payment.get("payer", {}).get("email", "")
        print(f"[WEBHOOK] Pagamento {payment_id} | Status: {status} | Valor: R${valor} | Email: {email}")
        # Aqui você pode salvar em banco, enviar email, etc.
    return jsonify({"ok": True}), 200

# ── ENVIAR ORÇAMENTO VIA WHATSAPP (gera link) ──
@app.route("/api/orcamento", methods=["POST"])
def receber_orcamento():
    data    = request.json
    nome    = data.get("nome", "")
    email   = data.get("email", "")
    tel     = data.get("tel", "")
    tipo    = data.get("tipo", "")
    desc    = data.get("desc", "")
    valor   = data.get("valor", "")

    msg = (
        f"Novo orçamento recebido!\n\n"
        f"Nome: {nome}\n"
        f"Email: {email}\n"
        f"Telefone: {tel}\n"
        f"Serviço: {tipo}\n"
        f"Valor estimado: R${valor}\n\n"
        f"Descrição: {desc}"
    )
    print(f"[ORÇAMENTO] {msg}")

    from urllib.parse import quote
    whatsapp_link = f"https://wa.me/5562992894867?text={quote(msg)}"

    return jsonify({
        "ok": True,
        "whatsapp_link": whatsapp_link,
        "protocolo": f"CGN-{int(datetime.now().timestamp())}"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
