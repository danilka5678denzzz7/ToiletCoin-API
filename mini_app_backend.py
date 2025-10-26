import time
import json 
import os   
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# =========================================================
# !!! ТОКЕН БОТА НЕ НУЖЕН ДЛЯ FASTAPI БЭКЕНДА !!!
# =========================================================

# --- КОНФИГУРАЦИЯ ИГРЫ ---
ENERGY_REGEN_RATE = 5      # Сколько энергии восстанавливается в секунду
INITIAL_MAX_ENERGY = 1000  # Начальный лимит энергии
INITIAL_ROLLS_PER_TAP = 1  # Начальное количество рулонов за один клик

# --- КОНФИГУРАЦИЯ БУСТОВ ---
class Boosts:
    # Улучшение: Рулоны за клик (Rolls per Tap)
    DENSITY_COSTS = [100, 500, 2000, 5000, 15000, 50000, 150000, 500000] 
    DENSITY_LEVELS = len(DENSITY_COSTS) + 1 

    # Улучшение: Максимальная энергия (Max Energy)
    COIL_COSTS = [200, 1000, 4000, 12000, 40000, 120000] 
    COIL_LEVELS = len(COIL_COSTS) + 1 
    COIL_ENERGY_BONUS = 500 # На сколько увеличивается max_energy с каждым уровнем

# --- КОНФИГУРАЦИЯ ФАЙЛА ДАННЫХ ---
DATA_FILE = 'users_data.json'

# --- ИМИТАЦИЯ БАЗЫ ДАННЫХ ---
users_data = {}

# -----------------------------------------------------------------
# ФУНКЦИИ СОХРАНЕНИЯ/ЗАГРУЗКИ (Без изменений)
# -----------------------------------------------------------------

def load_user_data():
    """Загружает данные пользователей из JSON файла при старте."""
    global users_data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                loaded_data = json.load(f)
                users_data = {int(k): v for k, v in loaded_data.items()}
                print(f"✅ Загружено {len(users_data)} пользователей из {DATA_FILE}")
        except Exception as e:
            print(f"❌ Ошибка при загрузке данных: {e}")
            users_data = {}
    else:
        print("ℹ️ Файл данных не найден. Начинаем с чистого листа.")
        users_data = {}

def save_user_data():
    """Сохраняет данные пользователей в JSON файл."""
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(users_data, f, indent=4)
    except Exception as e:
        print(f"❌ Ошибка при сохранении данных: {e}") 

# -----------------------------------------------------------------
# ОСНОВНЫЕ ИГРОВЫЕ ФУНКЦИИ (Без изменений)
# -----------------------------------------------------------------

def get_user_data(user_id):
    """Инициализирует данные пользователя, если он новый, или возвращает существующие."""
    if user_id not in users_data:
        users_data[user_id] = {
            'rolls': 0,
            'energy': INITIAL_MAX_ENERGY,
            'max_energy': INITIAL_MAX_ENERGY,
            'rolls_per_tap': INITIAL_ROLLS_PER_TAP,
            'density_level': 1,
            'coil_level': 1,    
            'last_tap_time': time.time()
        }
    return users_data[user_id]

def calculate_current_energy(user_data):
    """Рассчитывает текущую энергию с учетом времени восстановления."""
    now = time.time()
    time_passed = now - user_data['last_tap_time']
    
    restored_energy = int(time_passed * ENERGY_REGEN_RATE)
    new_energy = min(user_data['energy'] + restored_energy, user_data['max_energy'])
    
    if new_energy < user_data['max_energy']:
        user_data['last_tap_time'] += (restored_energy / ENERGY_REGEN_RATE)
    else:
        user_data['last_tap_time'] = now

    user_data['energy'] = new_energy
    return user_data['energy']

# -----------------------------------------------------------------
# МОДЕЛИ PYDANTIC ДЛЯ ВХОДЯЩИХ ДАННЫХ
# -----------------------------------------------------------------

class TapRequest(BaseModel):
    # В будущем тут будет initData для валидации, сейчас просто для примера
    # user_id: int 
    pass

class BuyRequest(BaseModel):
    boost_type: str # 'density' или 'coil'

# -----------------------------------------------------------------
# --- FASTAPI МОДЕЛИ И РОУТЫ ---
from fastapi.middleware.cors import CORSMiddleware # <--- НОВЫЙ ИМПОРТ

app = FastAPI()

# --- КОНФИГУРАЦИЯ CORS (ОБЯЗАТЕЛЬНО ДЛЯ ЛОКАЛЬНОГО ТЕСТИРОВАНИЯ) ---
# Звездочка (*) разрешает запросы с ЛЮБОГО источника (включая ваш локальный файл://)
origins = [
    "*", 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)
# ------------------------------------------------------------------------

class TapRequest(BaseModel):
    pass # <-- Добавьте это
# ... далее идет class TapRequest ...

@app.on_event("startup")
async def startup_event():
    """Загружаем данные при старте сервера."""
    load_user_data()

@app.get("/api/data/{user_id}")
async def get_user_data_api(user_id: int):
    """Возвращает все текущее состояние пользователя."""
    user_data = get_user_data(user_id)
    calculate_current_energy(user_data)
    
    # Возвращаем только необходимые данные
    return {
        "rolls": int(user_data['rolls']), # Убедимся, что это int
        "energy": int(user_data['energy']),
        "max_energy": int(user_data['max_energy']),
        "rolls_per_tap": int(user_data['rolls_per_tap']),
        "density_level": int(user_data['density_level']),
        "coil_level": int(user_data['coil_level']),
    }

@app.post("/api/tap/{user_id}")
async def process_tap_api(user_id: int, request_data: TapRequest):
    """Обрабатывает один клик."""
    user_data = get_user_data(user_id)
    calculate_current_energy(user_data)
    
    if user_data['energy'] >= 1:
        # Успешный тап
        user_data['energy'] -= 1
        user_data['rolls'] += user_data['rolls_per_tap']
        
        if user_data['energy'] > 0:
            user_data['last_tap_time'] = time.time()
            
        save_user_data()
        
        return {
            "success": True, 
            "rolls": int(user_data['rolls']), 
            "energy": int(user_data['energy']),
            "tapped_amount": user_data['rolls_per_tap']
        }
    else:
        raise HTTPException(status_code=400, detail="Not enough energy")


@app.post("/api/buy/{user_id}")
async def buy_boost_api(user_id: int, request: BuyRequest):
    """Обрабатывает покупку любого буста."""
    user_data = get_user_data(user_id)
    boost_type = request.boost_type

    # --- Покупка Плотности Бумаги ---
    if boost_type == 'density':
        current_level = user_data['density_level']

        if current_level > Boosts.DENSITY_LEVELS:
            raise HTTPException(status_code=400, detail="Max level reached for density")

        cost = Boosts.DENSITY_COSTS[current_level - 1]

        if user_data['rolls'] >= cost:
            user_data['rolls'] -= cost
            user_data['density_level'] += 1
            user_data['rolls_per_tap'] += 1
            save_user_data()
            return {"success": True, "new_level": user_data['density_level'], "boost_type": "density"}
        else:
            raise HTTPException(status_code=400, detail=f"Insufficient rolls. Needed: {cost}")

    # --- Покупка Большой Катушки ---
    elif boost_type == 'coil':
        current_level = user_data['coil_level']

        if current_level > Boosts.COIL_LEVELS:
            raise HTTPException(status_code=400, detail="Max level reached for coil")

        cost = Boosts.COIL_COSTS[current_level - 1]
        bonus_energy = Boosts.COIL_ENERGY_BONUS

        if user_data['rolls'] >= cost:
            user_data['rolls'] -= cost
            user_data['coil_level'] += 1
            user_data['max_energy'] += bonus_energy
            user_data['energy'] = user_data['max_energy']
            
            save_user_data()
            return {"success": True, "new_level": user_data['coil_level'], "boost_type": "coil", "new_max_energy": user_data['max_energy']}
        else:
            raise HTTPException(status_code=400, detail=f"Insufficient rolls. Needed: {cost}")
    
    else:
        raise HTTPException(status_code=400, detail="Invalid boost type")


if __name__ == "__main__":
    # Запуск сервера на порту 8000
    # Внимание: для реального Mini App этот сервер должен быть развернут на публичном хостинге с HTTPS!
    uvicorn.run(app, host="0.0.0.0", port=8000)