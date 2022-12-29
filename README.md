# Telegram Streamer Alert Bot
A simple bot that can check twitch streamers and notify when they go online

## Requirements
This bot uses python-telegram-bot, twitchAPI and sqlalchemy to work, all with async support. Install the dependencies by running
```bash
pip install -r requirements.txt
```
### Authentication
You also need to provide the respective tokens for each platform in a file tokens.py. If you don't have them, you can get the telegram token by creating a bot in [Botfather](https://t.me/BotFather) and the twitch tokens in the [Twitch developers console](https://dev.twitch.tv/console) page by creating an application. The following code shows how it should be added to the file (the token values were examples from each documentation, they aren't real values)
```py
TELEGRAM_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
TWITCH_CLIENT_SECRET = "41vpdji4e9gif29md0ouet6fktd2"
TWITCH_CLIENT_ID = "hof5gwx0su6owfnys0yan9c87zr6t"
```

## Running the bot
Running the bot is as simple as
```bash
python bot.py
```
