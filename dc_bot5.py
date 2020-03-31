#!/usr/bin/env python
import time
from bot import Bot
from dotenv import load_dotenv
load_dotenv()

def main():
    dc_bot = Bot(["probe"])
    while True:
        dc_bot.since = dc_bot.check_mentions()
        dc_bot.write_since_id()
        time.sleep(15)

if __name__ == "__main__":
    main()
