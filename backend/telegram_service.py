import os
import httpx
from dotenv import load_dotenv

load_dotenv()

class TelegramService:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.api_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

    async def send_execution_alert(self, symbol, type, price, strategy, confidence, elite_score):
        if not self.token or not self.chat_id:
            return

        message = (
            f"🚀 **OPERACIÓN EJECUTADA (IA)** 🚀\n\n"
            f"💎 **Activo:** {symbol}\n"
            f"💹 **Tipo:** {type}\n"
            f"📍 **Precio:** {price}\n"
            f"🧠 **Estrategia:** {strategy}\n"
            f"🔥 **Confianza:** {confidence}%\n"
            f"🏆 **Elite Score:** {elite_score}\n"
            f"⚙️ **Estado:** Gestionando por IA..."
        )

        await self._send_request(message)

    async def send_outcome_report(self, symbol, outcome, profit, strategy, next_amount):
        if not self.token or not self.chat_id:
            return

        icon = "✅" if outcome == "WIN" else "❌"
        status_text = "GANANCIA RECOGIDA" if outcome == "WIN" else "PÉRDIDA / PROTECCIÓN"
        correction_msg = ""
        
        if outcome == "LOSS":
            correction_msg = "\n\n🧠 **Corrección IA:** El cerebro ha detectado la falla y ha ajustado los pesos de la estrategia para evitar redundancia en este activo."

        message = (
            f"{icon} **REPORTE DE RESULTADO** {icon}\n\n"
            f"💎 **Activo:** {symbol}\n"
            f"📊 **Resultado:** {outcome} ({status_text})\n"
            f"💰 **Profit:** ${profit:+.2f}\n"
            f"🧠 **Estrategia:** {strategy}\n"
            f"📈 **Próxima Inversión:** ${next_amount:.2f}{correction_msg}"
        )

        await self._send_request(message)

    async def _send_request(self, message):
        async with httpx.AsyncClient() as client:
            try:
                await client.post(self.api_url, json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "Markdown"
                })
            except Exception as e:
                print(f"Error sending Telegram message: {e}")
