import os
import httpx
from dotenv import load_dotenv

load_dotenv()

class TelegramService:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.api_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

    async def send_signal(self, asset, signal_data):
        if not self.token or not self.chat_id:
            return

        message = (
            f"🎯 **ALERTA DE ALTA PRECISIÓN** 🎯\n\n"
            f"💎 **Activo:** {asset}\n"
            f"💹 **Operación:** {signal_data['signal']}\n"
            f"🔥 **Confianza:** {signal_data['confidence']}%\n"
            f"⏱️ **Temporalidad:** {signal_data['timeframe']}\n"
            f"🔔 **Entrada YA:** {signal_data['entry_time']}\n"
            f"⌛ **Cierre/Expiración:** {signal_data['expiry_time']}\n"
            f"📍 **Precio Ref:** {signal_data.get('entry', 'Actual')}\n"
            f"🛑 **Stop Loss:** {signal_data['sl']}\n"
            f"✅ **Take Profit:** {signal_data['tp']}\n"
            f"🌍 **Zona Horaria:** {signal_data.get('timezone', 'UTC-5')}\n"
            f"🔍 **Base:** {signal_data.get('info', 'Confluencia Técnica')}\n\n"
            f"⚠️ *Nota: Inicie la operación solo si la vela confirma la entrada.*"
        )

        async with httpx.AsyncClient() as client:
            try:
                await client.post(self.api_url, json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "Markdown"
                })
            except Exception as e:
                print(f"Error sending Telegram message: {e}")
