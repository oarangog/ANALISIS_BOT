import os
import httpx
from dotenv import load_dotenv

load_dotenv()

class TelegramService:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.api_url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        self.parse_mode = "HTML"

    async def send_execution_alert(self, symbol, type, price, strategy, confidence, elite_score):
        if not self.token or not self.chat_id:
            return

        message = (
            f"🚀 <b>OPERACIÓN EJECUTADA (IA)</b> 🚀\n\n"
            f"💎 <b>Activo:</b> {symbol}\n"
            f"💹 <b>Tipo:</b> {type}\n"
            f"📍 <b>Precio:</b> {price}\n"
            f"🧠 <b>Estrategia:</b> {strategy}\n"
            f"🔥 <b>Confianza:</b> {confidence}%\n"
            f"🏆 <b>Elite Score:</b> {elite_score}\n"
            f"⚙️ <b>Estado:</b> Gestionando por IA..."
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
            f"{icon} <b>REPORTE DE RESULTADO</b> {icon}\n\n"
            f"💎 <b>Activo:</b> {symbol}\n"
            f"📊 <b>Resultado:</b> {outcome} ({status_text})\n"
            f"💰 <b>Profit:</b> ${profit:+.2f}\n"
            f"🧠 <b>Estrategia:</b> {strategy}\n"
            f"📈 <b>Próxima Inversión:</b> ${next_amount:.2f}{correction_msg}"
        )

        await self._send_request(message)

    async def send_heartbeat(self, balance, scan_count, is_open):
        if not self.token or not self.chat_id:
            return

        status_emoji = "🟢" if is_open else "🟡"
        market_status = "ABIERTO (SESSIÓN ACTIVA)" if is_open else "CERRADO (ESCANEANDO FOREX)"
        
        message = (
            f"📡 <b>CORTE DE CONTROL (IA)</b> 🦾\n\n"
            f"✅ <b>Bot Operativo:</b> Online y Escaneando\n"
            f"💰 <b>Saldo Actual:</b> ${balance:.2f} USD\n"
            f"📊 <b>Activos Monitoreados:</b> {scan_count}\n"
            f"{status_emoji} <b>Mercado:</b> {market_status}\n\n"
            f"💎 <i>El bot sigue operando en segundo plano bajo el umbral del 90%.</i>"
        )

        await self._send_request(message)

    async def _send_request(self, message):
        async with httpx.AsyncClient() as client:
            try:
                await client.post(self.api_url, json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": self.parse_mode
                })
            except Exception as e:
                print(f"Error sending Telegram message: {e}")
