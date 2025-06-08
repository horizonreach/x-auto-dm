import csv
import time
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service

# === 設定 ===
CHROMEDRIVER_PATH = "C:\\Users\\simay\\python\\chromedriver.exe"
CHROME_PROFILE_PATH = "user-data-dir=C:\\Users\\simay\\AppData\\Local\\Google\\Chrome\\User Data"
SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/XXXX/XXXX/XXXX"  # 変更してください
KEYWORDS = ["Vtuber", "Twitch", "ライバー"]
MAX_MESSAGES_PER_DAY = 500
MESSAGE_TEXT = """送信文
"""

# === Slack通知関数 ===
def notify_slack(message):
    try:
        requests.post(SLACK_WEBHOOK_URL, json={"text": message})
    except Exception as e:
        print("Slack通知に失敗:", e)

# === Chrome起動 ===
options = webdriver.ChromeOptions()
options.add_argument(CHROME_PROFILE_PATH)
service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=options)

# === 送信済アカウント読み込み ===
sent_users_file = "sent_log.csv"
sent_users = set()
try:
    with open(sent_users_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sent_users.add(row["username"])
except FileNotFoundError:
    pass

# === ログファイル準備 ===
log_file = open(sent_users_file, "a", newline="", encoding="utf-8")
fieldnames = ["date", "username", "url", "status", "error"]
writer = csv.DictWriter(log_file, fieldnames=fieldnames)
if log_file.tell() == 0:
    writer.writeheader()

sent_count = 0
usernames_to_send = set()

def extract_usernames_from_page():
    users = driver.find_elements(By.XPATH, '//div[@data-testid="UserCell"]//a[contains(@href, "/")]')
    usernames = set()
    for user in users:
        href = user.get_attribute("href")
        if href and "/status/" not in href:
            username = "@" + href.split("/")[-1]
            usernames.add((username, href))
    return usernames

def scroll_and_collect(max_scrolls=5):
    all_usernames = set()
    last_height = driver.execute_script("return document.body.scrollHeight")
    for _ in range(max_scrolls):
        all_usernames.update(extract_usernames_from_page())
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
    return all_usernames

try:
    # === 1次取得: キーワード検索 ===
    for keyword in KEYWORDS:
        if sent_count >= MAX_MESSAGES_PER_DAY:
            break
        search_url = f"https://twitter.com/search?q={keyword}&src=typed_query&f=user"
        driver.get(search_url)
        time.sleep(5)
        results = scroll_and_collect()
        for username, url in results:
            if username not in sent_users:
                usernames_to_send.add((username, url))

    # === 2次取得: フォロー一覧から拡張 ===
    if sent_count + len(usernames_to_send) < MAX_MESSAGES_PER_DAY:
        candidates = list(usernames_to_send)
        for username, _ in candidates:
            if sent_count + len(usernames_to_send) >= MAX_MESSAGES_PER_DAY:
                break
            follow_url = f"https://twitter.com/{username[1:]}/following"
            driver.get(follow_url)
            time.sleep(5)
            followings = scroll_and_collect()
            for f_username, f_url in followings:
                if f