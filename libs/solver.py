import json
import time
from typing import Any

import httpx

with open("./config.json", "r", encoding="utf-8") as _cfg_file:
    _config_data = json.load(_cfg_file)

keyCap: str | None = _config_data.get("capmonster-key")


def _parse_proxy(proxy: str | None) -> dict[str, str] | None:
    if not proxy:
        return None
    cleaned = proxy.strip()
    if cleaned.startswith("http://"):
        cleaned = cleaned[len("http://") :]
    elif cleaned.startswith("https://"):
        cleaned = cleaned[len("https://") :]

    if "@" not in cleaned or ":" not in cleaned:
        return None

    auth_part, host_part = cleaned.rsplit("@", 1)
    if ":" not in auth_part or ":" not in host_part:
        return None

    login, password = auth_part.split(":", 1)
    host, port = host_part.split(":", 1)
    return {
        "proxyType": "http",
        "proxyAddress": host,
        "proxyPort": port,
        "proxyLogin": login,
        "proxyPassword": password,
    }


def payload(
    service: str = "capmonster.cloud",
    proxy: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    task: dict[str, Any] = {
        "websiteURL": "https://discord.com/",
        "websiteKey": "4c672d35-0701-42b2-88c3-78380b0db560",
    }

    if service == "capsolver.com":
        task["type"] = "HCaptchaTurboTask"
        if proxy is not None:
            task["proxy"] = proxy
        if user_agent is not None:
            task["userAgent"] = user_agent
        result: dict[str, Any] = {
            "clientKey": keyCap,
            "appId": "E68E89B1-C5EB-49FE-A57B-FBE32E34A2B4",
            "task": task,
        }
        return result

    if service == "capmonster.cloud":
        task["type"] = "HCaptchaTask"
        parsed = _parse_proxy(proxy)
        if parsed:
            task.update(parsed)
        return {
            "clientKey": keyCap,
            "task": task,
        }

    raise ValueError(f"Unsupported captcha service: {service}")


class Solver:
    def __init__(self, proxy: str | None, siteKey: str, siteUrl: str) -> None:
        self.debug = False
        self.proxy = proxy
        self.siteKey = siteKey
        self.siteUrl = siteUrl
        self.log(f"Solving Captcha, SiteKey: {self.siteKey} | SiteUrl: {self.siteUrl}")

    def log(self, txt: str) -> None:
        if self.debug:
            print(txt)

    def solveCaptcha(self) -> str | None:
        if not keyCap:
            print("Error: Missing 'capmonster-key' in config.json")
            return None

        page_url = (
            self.siteUrl
            if self.siteUrl.startswith(("http://", "https://"))
            else f"https://{self.siteUrl}/"
        )
        create_url = "https://api.capmonster.cloud/createTask"
        create_data = {
            "clientKey": keyCap,
            "task": {
                "type": "HCaptchaTaskProxyless",
                "websiteURL": page_url,
                "websiteKey": self.siteKey,
            },
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                create_resp = client.post(create_url, json=create_data)
                create_resp.raise_for_status()
                create_json = create_resp.json()

                if create_json.get("errorId") != 0:
                    desc = create_json.get("errorDescription", "Unknown createTask error")
                    print(f"Error: {desc}")
                    return None

                task_id = create_json.get("taskId")
                if not task_id:
                    print(f"Error: Missing taskId in response: {create_json}")
                    return None

                result_url = "https://api.capmonster.cloud/getTaskResult"
                result_data = {
                    "clientKey": keyCap,
                    "taskId": task_id,
                }

                while True:
                    result_resp = client.post(result_url, json=result_data)
                    result_resp.raise_for_status()
                    result_json = result_resp.json()

                    if result_json.get("errorId") != 0:
                        desc = result_json.get("errorDescription", "Unknown getTaskResult error")
                        print(f"Error: {desc}")
                        return None

                    status = result_json.get("status")
                    if status == "processing":
                        time.sleep(3)
                        continue

                    if status == "ready":
                        solution = result_json.get("solution") or {}
                        token = solution.get("gRecaptchaResponse")
                        if not token:
                            print(f"Error: Missing token in solution: {result_json}")
                            return None
                        return str(token)

                    print(f"Error: Unexpected task status '{status}': {result_json}")
                    return None
        except Exception as exc:
            print(f"Error solving captcha: {exc}")
            return None
