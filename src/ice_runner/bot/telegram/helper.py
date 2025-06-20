#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2023 Dmitry Ponomarev.
# Author: Dmitry Ponomarev <ponomarevda96@gmail.com>
"""
Auxialliary helper functions
"""

import argparse
import sys
import requests

def send_media_group(telegram_bot_token: str, telegram_chat_id: str, files: list, caption: str) -> None:
    """
    Send a single message to a given Telegram Chat with a given API token
    containing multiple files with a capture to the last one.
    """
    assert isinstance(telegram_bot_token, str)
    assert isinstance(telegram_chat_id, str)
    assert isinstance(files, list)
    assert isinstance(caption, str)

    if len(files) == 0:
        return {"ok": False, "error": "Nothing to send"} # Nothing to send

    media_json_array = [None] * len(files)

    for idx in range(0, len(files) - 1):
        media_json_array[idx] = {"type": "document", "media": f"attach://file{idx + 1}"}

    media_json_array[len(files) - 1] = {"type": "document", "media": f"attach://file{len(files)}", "caption": caption}

    media_payload = {
        'chat_id': telegram_chat_id,
        'media': str(media_json_array).replace("'", '"')
    }

    files_payload = {}
    for idx in range(len(files)):
        files_payload[f"file{idx + 1}"] = open(files[idx], 'rb')

    url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMediaGroup"
    response = requests.post(url, data=media_payload, files=files_payload)

    for file in files_payload.values():
        file.close()

    return response.json()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('bot_token', type=str)
    parser.add_argument('chat_id', type=str)
    parser.add_argument('files', nargs='+')
    parser.add_argument('caption', type=str)

    args = parser.parse_args()
    res = send_media_group(args.bot_token, args.chat_id, args.files, args.caption)

    if res['ok']:
        print(0)
    else:
        print(1)
