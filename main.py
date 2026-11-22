import base64
import json
import os
import random
import re
import sys
import threading
import time
from datetime import datetime, timedelta
from json import dumps

import requests
import tls_client
import websocket
from colorama import Fore

from libs.eazyui import Center, Colorate, Colors  # noqa: F401
from libs.solver import Solver


def get_discord_build_number(fallback: int = 300000) -> int:
    env_build = os.environ.get("DISCORD_BUILD_NUMBER")
    if env_build and env_build.isdigit():
        return int(env_build)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        resp = requests.get("https://discord.com/login", headers=headers, timeout=15)
        html = resp.text

        # Match /assets/<name>.js or assets/<name>.js
        matches = re.findall(r"(?:^|[\"'/])assets/([A-Za-z0-9_.-]+)\.js", html)
        if matches:
            asset_name = f"{matches[-2]}.js" if len(matches) >= 2 else f"{matches[0]}.js"
            asset_url = f"https://discord.com/assets/{asset_name}"
            js_text = requests.get(asset_url, headers=headers, timeout=15).text

            num_match = re.search(r"buildNumber[\"':\s,]+(\d{5,7})", js_text)
            if num_match:
                return int(num_match.group(1))

        Output("ERROR").log(
            f"Build scrape failed (status={resp.status_code}, len={len(html)}); "
            f"using fallback build {fallback}"
        )
    except Exception as exc:
        Output("ERROR").log(f"Build scrape error ({exc}); using fallback build {fallback}")

    return fallback

buildNumb = get_discord_build_number()

with open("input/names.txt", "r", encoding="utf-8") as f:
    names = [line.strip() for line in f.read().splitlines() if line.strip()]

with open("input/proxies.txt", "r", encoding="utf-8") as f:
    proxies = [line.strip() for line in f.read().splitlines() if line.strip()]

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

bios = []
if config.get("bio") and os.path.exists("input/bios.txt"):
    with open("input/bios.txt", "r", encoding="utf-8") as f:
        bios = [line.strip() for line in f.read().splitlines() if line.strip()]

state_lock = threading.Lock()
locked = 0
unlocked = 0
total = 0


def format_elapsed(seconds: int) -> str:
    delta = timedelta(seconds=max(0, seconds))
    parts = []
    if delta.days > 0:
        parts.append(f"{delta.days}d")
    hours = delta.seconds // 3600
    minutes = (delta.seconds // 60) % 60
    secs = delta.seconds % 60
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def updateTitle() -> None:
    gen_started_at = time.time()
    while True:
        try:
            with state_lock:
                cur_total = total
                cur_locked = locked
                cur_unlocked = unlocked

            elapsed_sec = round(time.time() - gen_started_at)
            elapsed_str = format_elapsed(elapsed_sec)
            unlock_rate = round((cur_unlocked / cur_total) * 100, 2) if cur_total > 0 else 0.0
            elapsed_mins = max((time.time() - gen_started_at) / 60.0, 1e-6)
            per_min = round(cur_unlocked / elapsed_mins)
            per_hour = round(per_min * 60)

            title_text = (
                f"[Token Generator] - Unlocked: {cur_unlocked} | Locked: {cur_locked} "
                f"| Unlock Rate: {unlock_rate}% | Speed: {per_min}/min - {per_hour}/hour "
                f"| Time Elapsed: {elapsed_str}"
            )

            if os.name == "nt":
                import ctypes

                ctypes.windll.kernel32.SetConsoleTitleW(title_text)
        except Exception:
            pass
        time.sleep(1)


class Output:
    def __init__(self, level: str) -> None:
        self.level = level
        self.color_map = {
            "INFO": (Fore.LIGHTBLUE_EX, "*"),
            "INFO2": (Fore.LIGHTCYAN_EX, "^"),
            "CAPTCHA": (Fore.LIGHTMAGENTA_EX, "C"),
            "ERROR": (Fore.LIGHTRED_EX, "!"),
            "SUCCESS": (Fore.LIGHTGREEN_EX, "$"),
        }

    def log(self, *args, **kwargs) -> None:
        color, badge = self.color_map.get(self.level, (Fore.LIGHTWHITE_EX, self.level))
        time_now = datetime.now().strftime("%H:%M:%S")
        message = " ".join(str(a) for a in args)
        if kwargs:
            extra = " ".join(f"{k}={v}" for k, v in kwargs.items())
            message = f"{message} {extra}".strip()
        print(f"[{Fore.LIGHTBLACK_EX}{time_now}{Fore.RESET}] ({color}{badge.upper()}{Fore.RESET}) {message}")


class Discord:
    def __init__(self) -> None:
        self.session = tls_client.Session(
            client_identifier="chrome112",
            random_tls_extension_order=True,
        )

        self.session.headers = {
            "authority": "discord.com",
            "accept": "*/*",
            "accept-language": "fr-BE,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "content-type": "application/json",
            "origin": "https://discord.com",
            "referer": "https://discord.com/",
            "sec-ch-ua": '"Chromium";v="112", "Google Chrome";v="112", "Not:A-Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
            ),
            "x-track": (
                "eyJvcyI6IldpbmRvd3MiLCJicm93c2VyIjoiQ2hyb21lIiwiZGV2aWNlIjoiIiw"
                "ic3lzdGVtX2xvY2FsZSI6ImZyLUJFIiwiYnJvd3Nlcl91c2VyX2FnZW50IjoiTW9"
                "6aWxsYS81LjAgKFdpbmRvd3MgTlQgMTAuMDsgV2luNjQ7IHg2NCkgQXBwbGVXZWJ"
                "LaXQvNTM3LjM2IChLSFRNTCwgbGlrZSBHZWNrbykgQ2hyb21lLzExMi4wLjAuMCBT"
                "YWZhcmkvNTM3LjM2IiwiYnJvd3Nlcl92ZXJzaW9uIjoiMTEyLjAuMC4wIiwib3Nfd"
                "mVyc2lvbiI6IjEwIiwicmVmZXJyZXIiOiIiLCJyZWZlcnJpbmdfZG9tYWluIjoiI"
                "iwicmVmZXJyZXJfY3VycmVudCI6IiIsInJlZmVycmluZ19kb21haW5fY3VycmVudC"
                "I6IiIsInJlbGVhc2VfY2hhbm5lbCI6InN0YWJsZSIsImNsaWVudF9idWlsZF9udW1"
                "iZXIiOjk5OTksImNsaWVudF9ldmVudF9zb3VyY2UiOm51bGx9"
            ),
        }

        self.prop = {
            "os": "Windows",
            "browser": "Chrome",
            "device": "",
            "system_locale": "fr-FR",
            "browser_user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
            ),
            "browser_version": "112.0.0",
            "os_version": "10",
            "referrer": "",
            "referring_domain": "",
            "referrer_current": "",
            "referring_domain_current": "",
            "release_channel": "stable",
            "client_build_number": buildNumb,
            "client_event_source": None,
            "design_id": 0,
        }
        self.super = base64.b64encode(
            json.dumps(self.prop, separators=(",", ":")).encode("utf-8")
        ).decode("utf-8")

        if not proxies:
            raise RuntimeError("No proxies found in input/proxies.txt")
        if not names:
            raise RuntimeError("No names found in input/names.txt")

        self.sessId = str(random.randint(500, 10000))
        raw_proxy = random.choice(proxies).replace("sessionid", self.sessId)
        self.proxy = raw_proxy if raw_proxy.startswith("http") else f"http://{raw_proxy}"
        self.session.proxies = {
            "http": self.proxy,
            "https": self.proxy,
        }
        self.fingerprint = ""
        self.token = ""

    def getFingerprint(self) -> str:
        res = self.session.get("https://discord.com/api/v9/experiments")
        self.session.cookies = res.cookies
        data = res.json()
        if "fingerprint" not in data:
            raise RuntimeError(f"Fingerprint missing in response: {data}")
        return data["fingerprint"]

    def createAccount(self, captchaKey: str) -> str:
        payload2 = {
            "consent": True,
            "fingerprint": self.fingerprint,
            "global_name": random.choice(names),
            "gift_code_sku_id": None,
            "invite": config.get("invite"),
            "unique_username_registration": True,
        }
        headers3 = {
            "Accept": "*/*",
            "Accept-Language": "en-GB",
            "Connection": "keep-alive",
            "Content-Length": str(len(dumps(payload2))),
            "Content-Type": "application/json",
            "Origin": "https://discord.com",
            "Referer": "https://discord.com/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-GPC": "1",
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"
            ),
            "X-Fingerprint": self.fingerprint,
            "X-Captcha-Key": captchaKey,
            "X-Track": (
                "eyJvcyI6IldpbmRvd3MiLCJicm93c2VyIjoiQ2hyb21lIiwiZGV2aWNlIjoiIiw"
                "ic3lzdGVtX2xvY2FsZSI6ImVuLVVTIiwiYnJvd3Nlcl91c2VyX2FnZW50IjoiTW9"
                "6aWxsYS81LjAgKFdpbmRvd3MgTlQgMTAuMDsgV2luNjQ7IHg2NCkgQXBwbGVXZWJ"
                "LaXQvNTM3LjM2IChLSFRNTCwgbGlrZSBHZWNrbykgQ2hyb21lLzExNS4wLjAuMCBT"
                "YWZhcmkvNTM3LjM2IiwiYnJvd3Nlcl92ZXJzaW9uIjoiMTE1LjAuMC4wIiwib3Nfd"
                "mVyc2lvbiI6IjEwIiwicmVmZXJyZXIiOiIiLCJyZWZlcnJpbmdfZG9tYWluIjoiI"
                "iwicmVmZXJyZXJfY3VycmVudCI6IiIsInJlZmVycmluZ19kb21haW5fY3VycmVudC"
                "I6IiIsInJlbGVhc2VfY2hhbm5lbCI6InN0YWJsZSIsImNsaWVudF9idWlsZF9udW1"
                "iZXIiOjIyMTIzNSwiY2xpZW50X2V2ZW50X3NvdXJjZSI6bnVsbH0="
            ),
        }
        self.session.headers.update(headers3)
        response = self.session.post(
            "https://discord.com/api/v9/auth/register",
            json=payload2,
        ).json()
        if "token" in response:
            return response["token"]
        if "retry_after" in response:
            raise Exception(f'Rate Limited For {response["retry_after"]}s')
        raise Exception(str(response))

    def isLocked(self) -> bool:
        resp = self.session.get("https://discord.com/api/v9/users/@me/affinities/users")
        return "You need to verify your account in order to perform this action." in resp.text

    def _record_outcome(self, is_unlocked: bool) -> None:
        global total, locked, unlocked
        with state_lock:
            total += 1
            if is_unlocked:
                unlocked += 1
                with open("tokens.txt", "a", encoding="utf-8") as f:
                    f.write(f"{self.token}\n")
            else:
                locked += 1

    def generate(self) -> None:
        self.fingerprint = self.getFingerprint()
        self.session.headers.update({
            "origin": "https://discord.com",
            "x-fingerprint": self.fingerprint,
        })

        started_solving = time.time()
        captcha_key = None
        while captcha_key is None:
            solver = Solver(
                proxy=self.proxy,
                siteKey="4c672d35-0701-42b2-88c3-78380b0db560",
                siteUrl="discord.com",
            )
            captcha_key = solver.solveCaptcha()

        Output("INFO").log(
            f"Solved {captcha_key[:30]} in {round(time.time() - started_solving)}s"
        )

        self.token = self.createAccount(captcha_key)
        masked_token = f"{self.token[:30]}*************************"

        self.session.headers.update({
            "authorization": self.token,
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "referer": "https://discord.com/channels/@me",
            "x-debug-options": "bugReporterEnabled",
            "x-discord-locale": "fr",
            "x-super-properties": self.super,
        })
        self.session.headers.pop("x-track", None)
        self.session.headers.pop("origin", None)

        if self.isLocked():
            self._record_outcome(False)
            Output("ERROR").log(f"Locked [{masked_token}]")
            return

        self.session.proxies = {
            "http": None,
            "https": None,
        }

        ws = websocket.WebSocket()
        ws.connect("wss://gateway.discord.gg/?v=9")
        try:
            ws.send(
                json.dumps({
                    "op": 2,
                    "d": {
                        "token": self.token,
                        "capabilities": 4093,
                        "properties": self.prop,
                        "presence": {
                            "status": "online",
                            "since": 0,
                            "activities": [],
                            "afk": False,
                        },
                        "compress": False,
                        "client_state": {
                            "guild_versions": {},
                            "highest_last_message_id": "0",
                            "read_state_version": 0,
                            "user_guild_settings_version": -1,
                            "user_settings_version": -1,
                            "private_channels_version": "0",
                            "api_code_version": 0,
                        },
                    },
                })
            )
            ws.send(
                json.dumps({
                    "op": 4,
                    "d": {
                        "guild_id": None,
                        "channel_id": None,
                        "self_mute": True,
                        "self_deaf": False,
                        "self_video": False,
                    },
                })
            )

            added = ""

            while True:
                try:
                    json_data = {"date_of_birth": "1991-11-12"}
                    if config.get("avatar") and os.path.isdir("input/image"):
                        image_files = [
                            f
                            for f in os.listdir("input/image")
                            if f.endswith(".jpg") or f.endswith(".png")
                        ]
                        if image_files:
                            img_path = os.path.join("input/image", random.choice(image_files))
                            with open(img_path, "rb") as img_f:
                                encoded_img = base64.b64encode(img_f.read()).decode("utf-8")
                            json_data["avatar"] = f"data:image/png;base64,{encoded_img}"
                            added += "Avatar, "

                    response = self.session.patch(
                        "https://discord.com/api/v9/users/@me",
                        json=json_data,
                    )
                    if response.status_code == 200:
                        added += "BirthDate, "
                    elif response.status_code != 400:
                        self._record_outcome(False)
                        Output("ERROR").log(f"Locked Av [{masked_token}]")
                        return
                    break
                except Exception:
                    pass

            while True:
                try:
                    if config.get("hypesquad"):
                        response = self.session.post(
                            "https://discord.com/api/v9/hypesquad/online",
                            json={"house_id": random.randint(1, 3)},
                        )
                        if response.status_code == 204:
                            added += "Hypesquad, "
                        elif response.status_code != 400:
                            self._record_outcome(False)
                            Output("ERROR").log(f"Locked Hp [{masked_token}]")
                            return
                    break
                except Exception:
                    pass

            if config.get("bio") and bios:
                while True:
                    try:
                        bio = random.choice(bios)
                        response = self.session.patch(
                            "https://discord.com/api/v9/users/%40me/profile",
                            json={"bio": bio},
                        )
                        if response.status_code == 200:
                            added += "Bio, "
                        elif response.status_code != 400:
                            self._record_outcome(False)
                            Output("ERROR").log(f"Locked Bio [{masked_token}]")
                            return
                        break
                    except Exception:
                        pass

            self._record_outcome(True)
            Output("SUCCESS").log(f"Unlocked [{masked_token}]")
            Output("INFO2").log(f"Humanized: {added}")
        finally:
            try:
                ws.close()
            except Exception:
                pass


def generate() -> None:
    while True:
        try:
            discord = Discord()
            discord.generate()
        except Exception as e:
            Output("ERROR").log(str(e))
            time.sleep(1)


def get_thread_count() -> int:
    env_threads = os.environ.get("THREADS")
    if env_threads and env_threads.isdigit():
        return max(1, int(env_threads))
    if sys.stdin and sys.stdin.isatty():
        return max(1, int(input(Center.XCenter("\nThreads <3 "))))
    return 1


if __name__ == "__main__":
    if os.name == "nt":
        os.system("cls")
        os.system("title Token Generator")

    thread_count = get_thread_count()
    for _ in range(thread_count):
        threading.Thread(target=generate, daemon=True).start()

    threading.Thread(target=updateTitle, daemon=True).start()

    while True:
        time.sleep(60)
