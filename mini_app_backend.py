import time
import json 
import os   
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from mangum import Mangum # <-- Только импорт, handler удален

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

# --- ХРАНИЛИЩЕ ДАННЫХ В ПАМЯТИ ---
# ВНИМАНИЕ: На Vercel эти данные будут сбрасываться!
users_data = {}

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
    
    if new_energy < user_data['max_energy']:
        user_data['last_tap_time'] += (restored_energy / ENERGY_REGEN_RATE)
    else:
        user_data['last_tap_time'] = now 

    user_data['energy'] = new_energy
    return user_data['energy']

# --- FASTAPI МОДЕЛИ И РОУТЫ ---

app = FastAPI()

# --- КОНФИГУРАЦИЯ CORS ---
origins = ["*"] 

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

@app.get("/api/data/{user_id}")
async def get_user_data_api(user_id: int):
    user_data = get_user_data(user_id)
    calculate_current_energy(user_data)
    
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
        
        user_data['last_tap_time'] = time.time() 
            
        return {
            "success": True, 
            "rolls": int(user_data['rolls']), 
            "energy": int(user_data['energy']),
            "tapped_amount": user_data['rolls_per_tap']
        }
    else:
        user_data['last_tap_time'] = time.time()
        raise HTTPException(status_code=400, detail="Not enough energy")
