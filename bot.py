import logging
import mysql.connector
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler

# Configuração do logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Conexão com o banco de dados MySQL
def db_connection():
    return mysql.connector.connect(
        host="localhost",        # Endereço do servidor MySQL
        user="root",             # Seu usuário MySQL
        password="senha",        # Sua senha MySQL
        database="bot_configurations"  # Nome do banco de dados
    )

# Função para verificar se o usuário já tem uma configuração no banco de dados
def get_user_config(user_id):
    conn = db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM user_configs WHERE user_id = %s", (user_id,))
    config = cursor.fetchone()
    conn.close()
    return config

# Função para adicionar ou atualizar a configuração do usuário no banco de dados
def set_user_config(user_id, bot_key, livepix_key):
    conn = db_connection()
    cursor = conn.cursor()
    
    # Verifica se o usuário já tem uma configuração
    cursor.execute("SELECT * FROM user_configs WHERE user_id = %s", (user_id,))
    existing_config = cursor.fetchone()
    
    if existing_config:
        # Atualiza as configurações do usuário
        cursor.execute("""
            UPDATE user_configs
            SET bot_key = %s, livepix_key = %s
            WHERE user_id = %s
        """, (bot_key, livepix_key, user_id))
    else:
        # Insere as configurações do usuário
        cursor.execute("""
            INSERT INTO user_configs (user_id, bot_key, livepix_key)
            VALUES (%s, %s, %s)
        """, (user_id, bot_key, livepix_key))
    
    conn.commit()
    conn.close()

# Função para adicionar ou atualizar os pacotes do usuário no banco de dados
def set_user_package(user_id, package_name, package_value):
    conn = db_connection()
    cursor = conn.cursor()
    
    # Verifica se o pacote já existe
    cursor.execute("""
        SELECT * FROM user_packages WHERE user_id = %s AND package_name = %s
    """, (user_id, package_name))
    existing_package = cursor.fetchone()
    
    if existing_package:
        # Atualiza o pacote
        cursor.execute("""
            UPDATE user_packages
            SET package_value = %s
            WHERE user_id = %s AND package_name = %s
        """, (package_value, user_id, package_name))
    else:
        # Insere o novo pacote
        cursor.execute("""
            INSERT INTO user_packages (user_id, package_name, package_value)
            VALUES (%s, %s, %s)
        """, (user_id, package_name, package_value))
    
    conn.commit()
    conn.close()

# Função para configurar o bot
def configurar(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    update.message.reply_text('Você entrou no modo de configuração do seu bot. Primeiro, defina a chave do bot do Telegram:')
    return BOT_KEY

# Função para definir a chave do bot Telegram
def set_bot_key(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    users_config[user_id]['bot_key'] = update.message.text
    update.message.reply_text(f"Chave do bot configurada como: {update.message.text}. Agora, defina a chave do LivePix:")
    return LIVEPIX_KEY

# Função para definir a chave do LivePix
def set_livepix_key(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    users_config[user_id]['livepix_key'] = update.message.text
    set_user_config(user_id, users_config[user_id]['bot_key'], users_config[user_id]['livepix_key'])
    update.message.reply_text(f"Chave do LivePix configurada como: {update.message.text}. Agora, defina o nome do pacote de assinatura:")
    return PACKAGE_NAME

# Função para definir o nome do pacote
def set_package_name(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    users_config[user_id].setdefault('packages', [])
    users_config[user_id]['current_package'] = {'name': update.message.text}
    update.message.reply_text(f"Pacote '{update.message.text}' configurado. Agora, defina o valor do pacote:")
    return PACKAGE_VALUE

# Função para definir o valor do pacote
def set_package_value(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    value = float(update.message.text)
    users_config[user_id]['current_package']['value'] = value
    set_user_package(user_id, users_config[user_id]['current_package']['name'], value)
    update.message.reply_text(f"Pacote '{users_config[user_id]['current_package']['name']}' configurado com o valor de R${value:.2f}.")
    update.message.reply_text('Pacote configurado com sucesso! Agora você pode adicionar mais pacotes ou sair com /sair.')
    return ConversationHandler.END

# Função principal para configurar e iniciar o bot
def main():
    # Substitua pelo seu token do bot
    TOKEN = 'SEU_TOKEN_AQUI'
    
    updater = Updater(TOKEN, use_context=True)
    
    dp = updater.dispatcher
    
    # Comandos
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("configurar", configurar))
    
    # Configuração do pacote de pagamento
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('configurar', configurar)],
        states={
            BOT_KEY: [MessageHandler(Filters.text & ~Filters.command, set_bot_key)],
            LIVEPIX_KEY: [MessageHandler(Filters.text & ~Filters.command, set_livepix_key)],
            PACKAGE_NAME: [MessageHandler(Filters.text & ~Filters.command, set_package_name)],
            PACKAGE_VALUE: [MessageHandler(Filters.text & ~Filters.command, set_package_value)],
        },
        fallbacks=[CommandHandler('sair', sair)]
    )
    
    dp.add_handler(conv_handler)
    
    # Inicia o bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
