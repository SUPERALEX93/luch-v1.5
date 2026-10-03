import subprocess
import sys
import threading
import re
from datetime import datetime, timedelta
from colorama import Fore, Back, Style
from ddgs import DDGS
from ultralytics import YOLO

# --- Связь с основным процессом и вебом ---
tts_callback = None  # Сюда main.py передаст функцию генерации голоса ИИ
web_alerts = []      # Очередь уведомлений для веб-интерфейса

def web_search(request):
    with DDGS() as ddgs:
        return list(ddgs.text(request, max_results=10))

def terminal(command):
    if not command or not command.strip():
        return ""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return "ОШИБКА: команда превысила лимит времени 60 секунд."
    except Exception as e:
        return f"ОШИБКА: {e}"
    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if result.returncode != 0:
        combined = (out + "\n" + err).strip()
        return combined or f"ОШИБКА: команда завершилась с кодом {result.returncode}"
    return out or ""

def exit():
    print(Fore.GREEN + "EXIT" + Style.RESET_ALL)
    sys.exit(0)

def lock_pc():
    subprocess.run(["hyprlock"])
    return "BLOCK PC SUCCESSFULLY"

def print_text(text):
    subprocess.run(['wtype', text])
    return "TEXT PRINTED SUCCESSFULLY"

# ---- ТАЙМЕР ----
def timer_alert(description):
    print(Fore.RED + f"\n[АЛАРМ!] Сработал таймер: {description}" + Style.RESET_ALL)

    try:
        subprocess.run(["notify-send", "-u", "critical", "-t", "10000", "LUCH AI ⏰", description])
    except Exception:
        pass
    
    # 2. Генерируем голос ИИ и воспроизводим на ПК локально
    audio_path = "/tmp/timer_alert.wav"
    if tts_callback:
        tts_callback(description, audio_path)
        
    # 3. Передаем сигнал для веб-интерфейса
    web_alerts.append({"description": description})

def set_timer(timer_type, time_val, description):
    now = datetime.now()
    delay_seconds = 0
    
    if timer_type == "absolute":
        try:
            target_time = datetime.strptime(time_val, "%H:%M").time()
            target_dt = datetime.combine(now.date(), target_time)
            if target_dt < now:
                target_dt += timedelta(days=1)
            delay_seconds = (target_dt - now).total_seconds()
        except ValueError:
            return "ERROR: invalid absolute time format."
    elif timer_type == "relative":
        match = re.match(r'^\+?(\d+)([smh])$', time_val.strip().lower())
        if match:
            val = int(match.group(1))
            unit = match.group(2)
            if unit == 's': delay_seconds = val
            elif unit == 'm': delay_seconds = val * 60
            elif unit == 'h': delay_seconds = val * 3600
        else:
            return "ERROR: invalid relative time format."
    else:
        return "ERROR: invalid timer_type."

    t = threading.Timer(delay_seconds, timer_alert, args=[description])
    t.start()
    
    return f"TIMER SET SUCCESSFULLY FOR {time_val}"

commands_ai = {
    "terminal": {"func": terminal, "icon": "🖥️"},
    "web_search": {"func": web_search, "icon": "🌐"},
    "lock_pc": {"func": lock_pc, "icon": "🔒"},
    "print_text": {"func": print_text, "icon": "✍️"},
    "set_timer": {"func": set_timer, "icon": "⏰"},
}

commands_ai_and_args = """
    1. terminal - выполнить команду в терминале.
    Пример: {"command": "terminal", "args": {"command": "ls"}}. 
    
    2. web_search - использовать веб поиск по запросу.
    Пример: {"command": "web_search", "args": {"request": "что такое ии"}}. 
    
    3. lock_pc - заблокировать пк.
    Пример: {"command": "lock_pc", "args": {}}. 
    
    4. print_text - сэмитировать печать текста с клавиатуры.
    Пример: {"command": "print_text", "args": {"text":"тут текст"}}. 
    
    5. set_timer - установить таймер. Обязательно укажи описание!
    Пример 1: {"command": "set_timer", "args": {"timer_type": "relative", "time_val": "10m", "description": "Пора выключать плиту"}}. Доступны 's', 'm', 'h'.
    Пример 2: {"command": "set_timer", "args": {"timer_type": "absolute", "time_val": "18:30", "description": "Начинается важный созвон"}}. Указывается в формате HH:MM.
"""