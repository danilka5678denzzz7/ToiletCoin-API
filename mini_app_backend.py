import time
import json 
import os   
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from mangum import Mangum # <--- НОВЫЙ ИМПОРТ ДЛЯ VERCEL

# --- КОНФИГУРАЦИЯ ИГРЫ ---
ENERGY_REGEN_RATE = 5      
INITIAL_MAX_ENERGY = 1000  
INITIAL_ROLLS_PER_TAP = 1  

# --- КОНФИГУРАЦИЯ БУСТОВ ---
class Boosts:
    DENSITY_COSTS = [100, 500, 2000, 5000, 15000, 50000, 150000, 500000] 
    DENSITY_LEVELS = len(DENSITY_COSTS) + 1 
    COIL_COSTS = [200, 1000, 4000, 12000, 40000, 120000] 
    COIL_LEVELS = len(COIL_COSTS) + 1 
    COIL_ENERGY_BONUS = 500 

# --- КОНФИГУРАЦИЯ ФАЙЛА ДАННЫХ ---
DATA_FILE = 'users_data.json'
users_data = {}

# --- ФУНКЦИИ СОХРАНЕНИЯ/ЗАГРУЗКИ ---
def load_user_data():
    global users_data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                loaded_data = json.load(f)
                # Ключи словаря из JSON - строки, переводим в int
                users_data = {int(k): v for k, v in loaded_data.items()} 
        except Exception:
            print(f"INFO: Data file found but is corrupted. Starting fresh.")
            users_data = {}
    else:
        print(f"INFO: Data file not found. Starting fresh.")
        users_data = {}

def save_user_data():
    # На Vercel мы не можем записывать в файл, но оставляем для локального теста
    if not os.environ.get('VERCEL_ENV'):
        try:
            with open(DATA_FILE, 'w') as f:
                json.dump(users_data, f, indent=4)
        except Exception as e:
            print(f"ERROR: Could not save data: {e}")

# --- ИГРОВАЯ ЛОГИКА ---
def get_user_data(user_id):
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
    now = time.time()
    time_passed = now - user_data['last_tap_time']
    restored_energy = int(time_passed * ENERGY_REGEN_RATE)
    new_energy = min(user_data['energy'] + restored_energy, user_data['max_energy'])
    
    # Скорректируйте время последнего тапа, только если энергия восстановилась не полностью
    if new_energy < user_data['max_energy']:
        user_data['last_tap_time'] += (restored_energy / ENERGY_REGEN_RATE)
    else:
        user_data['last_tap_time'] = now # Если энергия полная, время обновления = текущему времени

    user_data['energy'] = new_energy
    return user_data['energy']

# --- FASTAPI МОДЕЛИ И РОУТЫ ---

app = FastAPI()

# --- КОНФИГУРАЦИЯ CORS ---
origins = ["*"] # Разрешаем любой источник

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)
# ------------------------------------------------------------------------

class TapRequest(BaseModel):
    pass 

@app.on_event("startup")
async def startup_event():
    load_user_data()
    print("INFO: Application startup complete.")

@app.get("/api/data/{user_id}")
async def get_user_data_api(user_id: int):
    user_data = get_user_data(user_id)
    calculate_current_energy(user_data)
    save_user_data() # Сохраняем после обновления энергии
    
    return {
        "rolls": int(user_data['rolls']), 
        "energy": int(user_data['energy']),
        "max_energy": int(user_data['max_energy']),
        "rolls_per_tap": int(user_data['rolls_per_tap']),
        "density_level": int(user_data['density_level']),
        "coil_level": int(user_data['coil_level']),
    }

@app.post("/api/tap/{user_id}")
async def process_tap_api(user_id: int, request_data: TapRequest):
    user_data = get_user_data(user_id)
    calculate_current_energy(user_data)
    
    if user_data['energy'] >= 1:
        user_data['energy'] -= 1
        user_data['rolls'] += user_data['rolls_per_tap']
        
        # Обновляем last_tap_time только если энергия не закончилась
        user_data['last_tap_time'] = time.time() 
            
        save_user_data()
        
        return {
            "success": True, 
            "rolls": int(user_data['rolls']), 
            "energy": int(user_data['energy']),
            "tapped_amount": user_data['rolls_per_tap']
        }
    else:
        # Энергия закончилась
        user_data['last_tap_time'] = time.time() # Начинаем отсчет регенерации с этого момента
        save_user_data()
        raise HTTPException(status_code=400, detail="Not enough energy")

# --- ЗАПУСК ДЛЯ VERCEL ---
handler = Mangum(app)

# ЭТОТ БЛОК УДАЛЕН ИЛИ ЗАКОММЕНТИРОВАН ДЛЯ VERCEL:
# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8000)
