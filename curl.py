#!/usr/bin/env python3

import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlencode, urljoin

import bs4

BASE_URL = "http://hw1.alexbers.com/"
TOKEN = "41730816355b3bf87bd7425dac14fdd5"


def parse_table_kv(table_element):
    data = {}
    rows = table_element.find_all("tr")[1:]
    for row in rows:
        cols = row.find_all("td")
        if len(cols) == 2:
            key = cols[0].text.strip()
            value = cols[1].text.strip()
            data[key] = value
    return data


def curl_request(url, method="GET", cookies=None, headers=None, params=None,
                 data=None, files=None):
    cookies = cookies or {}
    headers = headers or {}
    params = params or {}
    data = data or {}
    files = files or {}

    if params:
        separator = "&" if "?" in url else "?"
        url += separator + urlencode(params)

    cookie_header = "; ".join(f"{key}={value}" for key, value in cookies.items())
    command = ["curl", "-sS", "-L"]
    if cookie_header:
        command.extend(["-H", f"Cookie: {cookie_header}"])
    for key, value in headers.items():
        command.extend(["-H", f"{key}: {value}"])

    with tempfile.TemporaryDirectory() as temp_dir:
        if method == "POST" and files:
            for index, (name, content) in enumerate(files.values()):
                file_path = Path(temp_dir) / f"upload_{index}"
                file_path.write_bytes(content)
                command.extend(["-F", f"{name}=@{file_path};filename={name}"])
        elif method == "POST" and data:
            for key, value in data.items():
                command.extend(["--data-urlencode", f"{key}={value}"])
        elif method == "POST":
            command.extend(["--data", ""])

        response_file = Path(temp_dir) / "response.html"
        command.extend(["-o", str(response_file), "-w", "%{url_effective}", url])

        result = subprocess.run(command, capture_output=True)
        if result.returncode:
            error = result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"curl завершился с ошибкой: {error}")

        return (
            response_file.read_text(encoding="utf-8"),
            result.stdout.decode("utf-8", errors="replace"),
        )


def main():
    step = 1
    response_text, response_url = curl_request(BASE_URL, cookies={"user": TOKEN})

    while True:
        soup = bs4.BeautifulSoup(response_text, "html.parser")
        if "поздравляем" in response_text.lower():
            print("Секрет получен")
            print(response_text)
            break

        print(f"ШАГ #{step}")
        print("Получен URL:", response_url)
        extra_cookies = {}
        extra_headers = {}
        query_params = {}
        form_data = {}
        files_payload = {}

        for table in soup.find_all("table"):
            prev_text = ""
            for element in table.previous_elements:
                if isinstance(element, bs4.element.NavigableString):
                    previous_text = element.strip()
                    if previous_text:
                        prev_text = previous_text.lower()
                        break

            if "cookie" in prev_text:
                extra_cookies.update(parse_table_kv(table))
            elif "заголовки" in prev_text:
                extra_headers.update(parse_table_kv(table))
            elif "параметры запроса" in prev_text:
                query_params.update(parse_table_kv(table))
            elif "данные формы" in prev_text:
                form_data.update(parse_table_kv(table))
            elif "указанным содержимым" in prev_text:
                for row in table.find_all("tr")[1:]:
                    cols = row.find_all("td")
                    if len(cols) == 2:
                        name = cols[0].get_text(strip=True)
                        content = cols[1].get_text()
                        files_payload[name] = (name, content.encode("utf-8"))

        match = re.search(
            r"по адресу.*?<code>\s*(/[a-zA-Z0-9_-]+)\s*</code>", response_text
        )
        if match:
            target_url = urljoin(BASE_URL, match.group(1))
        else:
            link = soup.find("a")
            target_url = urljoin(BASE_URL, link["href"]) if link and link.get("href") else None

        if not target_url:
            print("URL не найден")
            print(response_text)
            break

        request_cookies = {"user": TOKEN, **extra_cookies}
        is_post = "POST-запрос" in response_text or "POST" in response_text or bool(files_payload)

        if is_post:
            if files_payload:
                print(f"[POST Files] {target_url}")
                request_data = {"files": files_payload}
            else:
                print(f"[POST Data] {target_url}")
                request_data = {"data": form_data}
        else:
            print(f"[GET] {target_url}")
            request_data = {}

        response_text, response_url = curl_request(
            target_url, "POST" if is_post else "GET", request_cookies,
            extra_headers, query_params, **request_data
        )

        step += 1


if __name__ == "__main__":
    main()
