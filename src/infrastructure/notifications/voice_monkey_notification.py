import requests
from src.domain.interfaces.notification import INotification
from src.domain.interfaces.logger import ILogger

class VoiceMonkeyNotification(INotification):
    """
    Notification implementation using Voice Monkey.
    """
    def __init__(self, api_token: str, monkey_id: str, logger: ILogger):
        self.api_token = api_token
        self.monkey_id = monkey_id
        self.logger = logger
        self.base_url = "https://api-v3.voicemonkey.io/trigger"

    def send(self, message: str = None, **kwargs) -> bool:
        if not self.api_token or not self.monkey_id:
            self.logger.warning("Voice Monkey credentials not provided. Skipping notification.")
            return False

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "device": self.monkey_id
        }

        try:
            response = requests.post(self.base_url, json=payload, headers=headers)
            
            if response.status_code == 200:
                self.logger.info("VoiceMonkeyNotification sent successfully!")
                return True
            else:
                self.logger.error(f"VoiceMonkeyNotification failed. Code: {response.status_code}. Error: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"VoiceMonkeyNotification connection error: {e}")
            return False
