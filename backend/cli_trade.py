import requests
import json
import os

API_URL = "http://localhost:8001"

def check_analysis():
    print("\n🔍 Consultando análisis actual...")
    try:
        response = requests.get(f"{API_URL}/analysis")
        if response.status_code == 200:
            data = response.json()
            for asset, details in data.items():
                if details['signal'] != "NEUTRAL":
                    print(f"✅ {asset}: {details['signal']} ({details['confidence']}%) - {details['info']}")
                else:
                    print(f"⚪ {asset}: Sin señal clara.")
            return data
    except Exception as e:
        print(f"❌ Error conectando al backend: {e}")
        return None

def execute_trade():
    print("\n--- EJECUCIÓN DE OPERACIÓN ---")
    asset = input("Activo (ej: EURUSD): ").upper()
    side = input("Tipo (BUY/SELL): ").upper()
    amount = input("Monto a invertir ($): ")
    
    try:
        amount_val = float(amount)
        payload = {
            "symbol": asset,
            "type": side,
            "volume": 0.01,
            "amount": amount_val
        }
        
        print(f"🚀 Enviando orden de {side} para {asset} por ${amount_val}...")
        response = requests.post(f"{API_URL}/trade", json=payload)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "ERROR":
                print(f"🚫 {result['message']}")
            else:
                print(f"\n🔔 OPERACIÓN FINALIZADA")
                print(f"💰 Resultado: {result.get('outcome')}")
                print(f"🏦 Nuevo Saldo: ${result.get('balance'):.2f}")
        else:
            print(f"❌ Error en la API: {response.text}")
            
    except ValueError:
        print("❌ Monto inválido. Debe ser un número.")

if __name__ == "__main__":
    print("Welcome to ANAILIS BOT CLI 🛸")
    while True:
        print("\n1. Ver Señales")
        print("2. Ejecutar Operación")
        print("3. Salir")
        choice = input("Seleccione una opción: ")
        
        if choice == "1":
            check_analysis()
        elif choice == "2":
            execute_trade()
        elif choice == "3":
            break
        else:
            print("Opción inválida.")
