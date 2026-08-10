import os
import sys

# Add the root directory of the project to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config.settings import settings
from src.core.logger import logger
from src.core.notifications.voice_monkey_notification import VoiceMonkeyNotification

def main():
    logger.info("Starting Alexa notification test...")
    
    api_token = settings.VOICE_MONKEY_API_TOKEN
    monkey_id = settings.VOICE_MONKEY_NEW_VIDEO_FOR_DOWNLOAD_MONKEY_ID
    
    if not api_token or not monkey_id:
        logger.error("Missing Voice Monkey credentials in .env file. Please check VOICE_MONKEY_API_TOKEN and VOICE_MONKEY_NEW_VIDEO_FOR_DOWNLOAD_MONKEY_ID.")
        return
        
    logger.info(f"Using API Token: {'*' * (len(api_token) - 4) + api_token[-4:] if len(api_token) > 4 else '***'}")
    logger.info(f"Using Monkey ID: {monkey_id}")
    
    notification = VoiceMonkeyNotification(
        api_token=api_token,
        monkey_id=monkey_id,
        logger=logger
    )
    
    logger.info("Sending test notification to Alexa via Voice Monkey...")
    
    success = notification.send(message="This is a test notification from Signal Catcher.")
    
    if success:
        logger.info("Notification sent successfully! Check your Alexa device.")
    else:
        logger.error("Failed to send notification. Please check the logs above for details.")

if __name__ == "__main__":
    main()
