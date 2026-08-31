import requests

from src.core.interfaces.notifications.notification import INotification
from src.core.logger.interfaces import ILogger


class VoiceMonkeyNotification(INotification):
    """
    Notification implementation using Voice Monkey.
    """
    def __init__(
        self, api_token: str | None, monkey_id: str | None, logger: ILogger
    ):
        # Both are optional on purpose: when either is missing, `send` logs a warning
        # and returns False instead of raising, so the notification is a soft
        # dependency of the capture pipeline.
        self.api_token = api_token
        self.monkey_id = monkey_id
        self.logger = logger
        self.base_url = "https://api-v3.voicemonkey.io/announce"

    def send(self, message: str | None = None, **kwargs) -> bool:
        self.logger.debug(
            f"Preparing to send VoiceMonkey notification for device/monkey_id: '{self.monkey_id}'",
            context={"monkey_id": self.monkey_id, "has_api_token": bool(self.api_token)}
        )

        if not self.api_token or not self.monkey_id:
            self.logger.warning(
                "Voice Monkey credentials not provided (api_token or monkey_id is missing). Skipping notification.",
                context={"has_api_token": bool(self.api_token), "has_monkey_id": bool(self.monkey_id)}
            )
            return False

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "token": self.api_token,
            "device": self.monkey_id,
            "voice": "Ricardo",
            "language": "pt-BR"
        }
        if message:
            payload["text"] = message
        payload.update(kwargs)

        try:
            self.logger.info(
                f"Sending VoiceMonkey notification request to device: '{self.monkey_id}'...",
                context={"url": self.base_url, "device": self.monkey_id, "payload": payload}
            )
            response = requests.post(self.base_url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                self.logger.info(
                    "VoiceMonkeyNotification sent successfully!",
                    context={"status_code": response.status_code, "response": response.text, "monkey_id": self.monkey_id}
                )
                return True
            else:
                self.logger.error(
                    f"VoiceMonkeyNotification failed. Code: {response.status_code}. Error: {response.text}",
                    context={"status_code": response.status_code, "error": response.text, "monkey_id": self.monkey_id}
                )
                return False
                
        except Exception as e:
            self.logger.error(
                f"VoiceMonkeyNotification connection error: {e}",
                context={"error": str(e), "monkey_id": self.monkey_id}
            )
            return False
