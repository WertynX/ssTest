from flask import Flask, request, Response
import requests
import hashlib
import time

app = Flask(__name__)

# Секретный ключ для подписи (должен совпадать с клиентом)
SECRET_KEY = "YOUR_SECRET_KEY_HERE_CHANGE_THIS"

# Версия сервера
SERVER_VERSION = "v1.1.0"  # Измените при обновлении скрипта

# Словарь ключей: None = разрешено, иначе = причина запрета
VALID_KEYS = {
    "Fg6LpVmZ3rQd9Ntw": None,
    "Hr3NyTxW8sKl5Bqe": None,
    "Jm7WzYpLcDn20Vxs": None,
    "Kq5TvBnX1mAr8Ljo": None,
    "Ld2MzKwReVb63Qpt": None,
    "Sc9VnXaLoRy45Wem": None,
    "Tn4LpZwTkHs98Mdr": None,
    "Um6KoByLdFx72Nve": None,
    "Vp7XtNqMaLv01Krj": None,
    "Wd8RbKlTwYz36Fop": None
}

# Telegram config
TELEGRAM_BOT_TOKEN = "7367795974:AAGOLmN8ztMzTNjPpj-yPEasu524EdQGWfw"
TELEGRAM_USER_ID = "5212844017"

# Содержимое script.lua для обновления
def get_script_content():
    """Возвращает содержимое скрипта для обновления"""
    return '''-- Новый скрипт Pilot (upg.) v1.1.0
print("Это обновленная версия скрипта!")

-- Здесь будет ваш основной код
function main()
    print("Скрипт успешно обновлен до версии " .. SERVER_VERSION)
    -- Добавьте ваш код здесь
end

main()'''

def get_client_ip(request):
    """Получаем все возможные IP-адреса клиента"""
    ip_addresses = []
    
    # Проверяем заголовки в порядке приоритета
    if request.headers.get('X-Forwarded-For'):
        ip_addresses.append(request.headers.get('X-Forwarded-For').split(',')[0].strip())
    if request.headers.get('X-Real-IP'):
        ip_addresses.append(request.headers.get('X-Real-IP'))
    if request.headers.get('X-Client-IP'):
        ip_addresses.append(request.headers.get('X-Client-IP'))
    
    if request.remote_addr:
        ip_addresses.append(request.remote_addr)
    
    ip_addresses = list(dict.fromkeys([ip for ip in ip_addresses if ip]))
    
    return ip_addresses

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_USER_ID,
        "text": text
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print("Ошибка при отправке в Telegram:", e)

def verify_signature(hwid, timestamp, nonce, client_signature):
    """Проверка подписи от клиента"""
    data = f"{hwid}|{timestamp}|{nonce}|{SECRET_KEY}"
    expected_signature = hashlib.md5(data.encode()).hexdigest()
    return client_signature == expected_signature

def create_response_signature(response_data):
    """Создание подписи для ответа"""
    data = f"{response_data}|{SECRET_KEY}"
    return hashlib.md5(data.encode()).hexdigest()

@app.route('/', methods=['POST'])
def check_key():
    try:
        data = request.data.decode('utf-8')
        parts = data.split(" | ")
        
        if len(parts) < 6:
            return "Неверный формат данных", 400
        
        key = parts[0].strip()
        hwid = parts[1].strip()
        timestamp_str = parts[2].strip()
        nonce = parts[3].strip()
        client_signature = parts[4].strip()
        client_version = parts[5].strip() if len(parts) > 5 else "v1.0.0"
        
        # Получаем IP-адреса клиента
        client_ips = get_client_ip(request)
        ips_text = ", ".join(client_ips) if client_ips else "Не удалось определить"
        
        # Проверка timestamp
        try:
            timestamp = int(timestamp_str)
            current_time = int(time.time())
            
            if abs(current_time - timestamp) > 600:  # 10 минут
                message = f"⚠️ Срок действия запроса истек\nIP: {ips_text}\nKEY: {key}\nHWID: {hwid}\nВерсия: {client_version}"
                send_telegram_message(message)
                return "Срок действия запроса истек", 403
        except ValueError:
            return "Неверный формат времени", 400
        
        # Проверка подписи
        if not verify_signature(hwid, timestamp_str, nonce, client_signature):
            message = f"⚠️ Попытка подделки подписи!\nIP: {ips_text}\nKEY: {key}\nHWID: {hwid}\nВерсия: {client_version}"
            send_telegram_message(message)
            return "Неверная подпись", 403
        
        # Проверка версии клиента
        version_mismatch = client_version != SERVER_VERSION
        
        # Проверка ключа
        if key in VALID_KEYS:
            reason = VALID_KEYS[key]
            if reason is None:
                if version_mismatch:
                    # Отправляем обновление скрипта
                    response_text = get_script_content()
                    code = 210  # Специальный код для обновления
                else:
                    response_text = "HTTP/1.1 200 OK"
                    code = 200
            else:
                response_text = f"Причина: {reason}"
                code = 403
        else:
            reason = "Ключ не найден"
            response_text = f"Причина: {reason}"
            code = 403
        
        # Формируем сообщение для Telegram
        message = f"🔐 Проверка ключа (RakBot):\nIP: {ips_text}\nKEY: {key}\nHWID: {hwid}\nВерсия клиента: {client_version}\nОтвет: {code}"
        if version_mismatch and code == 210:
            message += f"\n⚠️ Отправлено обновление с {client_version} до {SERVER_VERSION}"
        if reason and code == 403:
            message += f"\nПричина: {reason}"
        send_telegram_message(message)
        
        # Создаем подпись для ответа
        response_signature = create_response_signature(response_text)
        
        # Возвращаем ответ с подписью и версией сервера
        response = Response(
            response_text.encode("cp1251"),
            status=code,
            content_type='text/plain; charset=windows-1251'
        )
        response.headers['x-response-signature'] = response_signature
        response.headers['x-server-version'] = SERVER_VERSION
        
        return response
        
    except Exception as e:
        client_ips = get_client_ip(request)
        ips_text = ", ".join(client_ips) if client_ips else "Не удалось определить"
        send_telegram_message(f"⚠️ Ошибка при обработке запроса:\nIP: {ips_text}\nError: {str(e)}")
        return f"HTTP/1.1 400 BAD REQUEST\n\nError: {str(e)}", 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
