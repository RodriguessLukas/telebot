import telebot
import time
import json
import requests
from threading import Thread

# Armazena configurações dos usuários
CONFIGURACOES = {}
PACOTES = {}
usuarios_pagamento = {}

# Carregar configurações salvas
try:
    with open("configuracoes.json", "r") as file:
        CONFIGURACOES = json.load(file)
except FileNotFoundError:
    pass

bot = telebot.TeleBot("SEU_TOKEN_DO_BOT")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, "Bem-vindo! Configure seu bot com /configurar_bot antes de usá-lo.")

@bot.message_handler(commands=['configurar_bot'])
def configurar_bot(message):
    bot.send_message(message.chat.id, "Envie suas configurações no formato: token_bot, url_livepix, id_grupo, id_admin")
    bot.register_next_step_handler(message, salvar_configuracao)

def salvar_configuracao(message):
    try:
        token_bot, url_livepix, id_grupo, id_admin = message.text.split(',')
        CONFIGURACOES[message.chat.id] = {
            "token": token_bot.strip(),
            "livepix": url_livepix.strip(),
            "grupo": id_grupo.strip(),
            "admin": id_admin.strip()
        }
        with open("configuracoes.json", "w") as file:
            json.dump(CONFIGURACOES, file)
        bot.send_message(message.chat.id, "Configuração salva com sucesso! Agora configure seus pacotes com /configurar_pacotes.")
    except:
        bot.send_message(message.chat.id, "Formato inválido. Tente novamente.")

@bot.message_handler(commands=['configurar_pacotes'])
def configurar_pacotes(message):
    if message.chat.id not in CONFIGURACOES:
        bot.send_message(message.chat.id, "Configure seu bot primeiro com /configurar_bot.")
        return
    if str(message.chat.id) != CONFIGURACOES[message.chat.id]["admin"]:
        bot.send_message(message.chat.id, "Apenas o administrador pode configurar os pacotes.")
        return
    bot.send_message(message.chat.id, "Envie os pacotes no formato: nome,preço,dias (um por linha).")
    bot.register_next_step_handler(message, salvar_pacotes)

def salvar_pacotes(message):
    global PACOTES
    linhas = message.text.split('\n')
    novos_pacotes = {}
    for linha in linhas:
        try:
            nome, preco, dias = linha.split(',')
            novos_pacotes[nome.strip()] = {"preco": float(preco.strip()), "dias": int(dias.strip())}
        except:
            bot.send_message(message.chat.id, f"Erro ao processar linha: {linha}")
            return
    PACOTES[message.chat.id] = novos_pacotes
    bot.send_message(message.chat.id, "Pacotes configurados com sucesso!")

@bot.message_handler(commands=['planos'])
def listar_planos(message):
    if message.chat.id not in PACOTES:
        bot.send_message(message.chat.id, "Nenhum plano disponível. Aguarde o administrador configurar.")
        return
    msg = "Planos disponíveis:\n"
    for plano, detalhes in PACOTES[message.chat.id].items():
        msg += f"{plano}: R$ {detalhes['preco']} por {detalhes['dias']} dias\n"
    msg += "Digite /comprar <plano> para adquirir."
    bot.send_message(message.chat.id, msg)

@bot.message_handler(commands=['comprar'])
def comprar_plano(message):
    try:
        _, plano = message.text.split()
        if message.chat.id not in PACOTES or plano not in PACOTES[message.chat.id]:
            bot.send_message(message.chat.id, "Plano inválido. Use /planos para ver os disponíveis.")
            return
        
        preco = PACOTES[message.chat.id][plano]['preco']
        user_id = message.chat.id
        
        # Criar pagamento via LivePix
        livepix_url = CONFIGURACOES[user_id]["livepix"]
        response = requests.post(livepix_url, json={"valor": preco, "user_id": user_id})
        pagamento = response.json()
        
        if 'qrcode' in pagamento:
            usuarios_pagamento[user_id] = {'plano': plano, 'expira_em': time.time() + 900}  # Expira em 15 min
            bot.send_photo(user_id, pagamento['qrcode'], caption=f"Escaneie o QR Code para pagar R$ {preco}.")
        else:
            bot.send_message(user_id, "Erro ao gerar o pagamento. Tente novamente.")
    except:
        bot.send_message(message.chat.id, "Uso correto: /comprar <plano>")

def verificar_pagamentos():
    while True:
        for user_id, info in list(usuarios_pagamento.items()):
            if time.time() > info['expira_em']:
                del usuarios_pagamento[user_id]
                continue
            
            livepix_url = CONFIGURACOES[user_id]["livepix"]
            response = requests.get(f"{livepix_url}/status/{user_id}")
            status = response.json()
            
            if status.get('pago'):
                dias = PACOTES[user_id][info['plano']]['dias']
                expira_em = time.time() + (dias * 86400)
                
                bot.send_message(user_id, "Pagamento confirmado! Você foi adicionado ao grupo.")
                bot.add_chat_members(CONFIGURACOES[user_id]["grupo"], user_id)
                
                with open("usuarios.json", "r+") as file:
                    usuarios = json.load(file)
                    usuarios[str(user_id)] = expira_em
                    file.seek(0)
                    json.dump(usuarios, file)
                    file.truncate()
                
                del usuarios_pagamento[user_id]
        time.sleep(10)

def remover_expirados():
    while True:
        with open("usuarios.json", "r+") as file:
            usuarios = json.load(file)
            agora = time.time()
            for user_id, expira_em in list(usuarios.items()):
                if agora > expira_em:
                    bot.kick_chat_member(CONFIGURACOES[user_id]["grupo"], int(user_id))
                    bot.send_message(int(user_id), "Seu acesso ao grupo expirou. Renove seu plano com /planos.")
                    del usuarios[user_id]
            file.seek(0)
            json.dump(usuarios, file)
            file.truncate()
        time.sleep(3600)

Thread(target=verificar_pagamentos, daemon=True).start()
Thread(target=remover_expirados, daemon=True).start()

bot.polling(none_stop=True)
