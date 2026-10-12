import re
from urllib.parse import urljoin
import bs4
import requests

BASE_URL = "http://hw1.alexbers.com/"
TOKEN = "41730816355b3bf87bd7425dac14fdd5"


def parse_table_kv(table_element):
    data = {}
    rows = table_element.find_all("tr")[1:]
    for row in rows:
        cols = row.find_all("td")
        if len(cols) == 2:
            key = cols[0].text.strip()
            val = cols[1].text.strip()
            data[key] = val
    return data


session = requests.Session()
session.trust_env = False
session.cookies.set("user", TOKEN)
response = session.get(BASE_URL)

step = 1
while True:
    text = response.text
    soup = bs4.BeautifulSoup(text, "html.parser")
    if "поздравляем" in text.lower():
        print("Секрет получен")
        print(text)
        break

    print(f"ШАГ #{step}")
    print("Получен URL:", response.url)
    extra_cookies = {}
    extra_headers = {}
    query_params = {}
    form_data = {}
    files_payload = {}
    tables = soup.find_all("table")

    for table in tables:
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
            rows = table.find_all("tr")[1:]
            for row in rows:
                cols = row.find_all("td")
                if len(cols) == 2:
                    fname = cols[0].get_text(strip=True)
                    content = cols[1].get_text()
                    files_payload[fname] = (
                        fname,
                        content.encode("utf-8"),
                    )

    target_url = None
    match = re.search(
        r"по адресу.*?<code>\s*(/[a-zA-Z0-9_-]+)\s*</code>",
        text
    )
    if match:
        target_url = urljoin(BASE_URL, match.group(1))
    else:
        link = soup.find("a")
        if link and link.get("href"):
            target_url = urljoin(BASE_URL, link["href"])
    if not target_url:
        print("URL не найден")
        print(text)
        break

    is_post = "POST-запрос" in text or "POST" in text or len(files_payload) > 0
    req_cookies = {"user": TOKEN}
    req_cookies.update(extra_cookies)

    if is_post:

        if files_payload:
            print(f"[POST Files] {target_url}")
            response = session.post(
                target_url,
                cookies=req_cookies,
                headers=extra_headers,
                params=query_params,
                files=files_payload,
                timeout=15
            )
        else:
            print(f"[POST Data] {target_url}")
            response = session.post(
                target_url,
                cookies=req_cookies,
                headers=extra_headers,
                params=query_params,
                data=form_data,
                timeout=15
            )

    else:
        print(f"[GET] {target_url}")
        response = session.get(
            target_url,
            cookies=req_cookies,
            headers=extra_headers,
            params=query_params,
            timeout=15,
        )
    step += 1