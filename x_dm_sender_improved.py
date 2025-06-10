#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X(Twitter) 自動DM送信システム - 改良版
長期運用対応・凍結リスク軽減・エラーハンドリング強化
"""

import csv
import json
import time
import random
import requests
import logging
from datetime import datetime, timedelta
from typing import Set, Tuple, List, Optional
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, 
    WebDriverException, ElementClickInterceptedException
)

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('x_dm_sender.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class XDMSender:
    def __init__(self, config_file: str = "config.json"):
        """初期化"""
        self.config = self.load_config(config_file)
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.sent_users: Set[str] = set()
        self.blacklist_urls: Set[str] = set()
        self.sent_count = 0
        self.today_date = datetime.now().strftime('%Y-%m-%d')
        
        # ファイル初期化
        self.setup_files()
        
        # 過去データ読み込み
        self.load_sent_history()
        self.load_blacklist()
        
        logger.info("X DM Sender initialized successfully")

    def load_config(self, config_file: str) -> dict:
        """設定ファイル読み込み"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Config file {config_file} not found")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            raise

    def setup_files(self):
        """必要なファイル・ディレクトリの初期化"""
        log_file = Path(self.config['files']['log_file'])
        if not log_file.exists():
            with open(log_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['date', 'username', 'url', 'status', 'error', 'message_sent'])

    def setup_chrome_driver(self):
        """Chrome WebDriver設定"""
        try:
            options = Options()
            options.add_argument(self.config['chrome']['profile_path'])
            options.add_argument(f"--window-size={','.join(map(str, self.config['chrome']['window_size']))}")
            
            # 検出回避のオプション
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # ヘッドレスモード設定
            if self.config['chrome'].get('headless', False):
                options.add_argument("--headless")
            
            service = Service(self.config['chrome']['driver_path'])
            self.driver = webdriver.Chrome(service=service, options=options)
            
            # WebDriver検出を回避
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.wait = WebDriverWait(self.driver, 10)
            logger.info("Chrome driver initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Chrome driver: {e}")
            raise

    def load_sent_history(self):
        """送信履歴読み込み（3ヶ月制限対応）"""
        try:
            reset_date = datetime.now() - timedelta(days=self.config['sending']['sent_history_reset_days'])
            
            with open(self.config['files']['log_file'], 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        send_date = datetime.strptime(row['date'], '%Y-%m-%d %H:%M')
                        if send_date > reset_date and row['status'] == 'Success':
                            self.sent_users.add(row['username'])
                    except (ValueError, KeyError):
                        continue
                        
            logger.info(f"Loaded {len(self.sent_users)} users from recent history")
            
        except FileNotFoundError:
            logger.info("No previous sending history found")

    def load_blacklist(self):
        """Googleスプレッドシートからブラックリスト読み込み"""
        try:
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                self.config['google_sheets']['credentials_file'], scope
            )
            client = gspread.authorize(creds)
            sheet = client.open_by_key(self.config['google_sheets']['spreadsheet_key'])
            worksheet = sheet.get_worksheet(0)
            
            urls = worksheet.col_values(self.config['google_sheets']['blacklist_column'])
            self.blacklist_urls = set(
                url.strip() for url in urls 
                if url and (url.startswith("https://twitter.com") or url.startswith("https://x.com"))
            )
            
            logger.info(f"Loaded {len(self.blacklist_urls)} blacklisted URLs")
            
        except Exception as e:
            logger.warning(f"Failed to load blacklist from Google Sheets: {e}")
            self.blacklist_urls = set()

    def load_message_text(self) -> str:
        """送信メッセージテキスト読み込み"""
        try:
            with open(self.config['files']['message_file'], 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            logger.warning(f"Message file {self.config['files']['message_file']} not found")
            return "こんにちは！"

    def is_allowed_time(self) -> bool:
        """送信許可時間チェック"""
        now = datetime.now().hour
        blocked_hours = self.config['sending']['blocked_hours']
        return now not in blocked_hours

    def wait_between_actions(self, action_count: int = 0):
        """アクション間の待機（人間らしいパターン）"""
        min_wait = self.config['sending']['min_wait_seconds']
        max_wait = self.config['sending']['max_wait_seconds']
        
        # 送信数に応じて待機時間を調整
        base_wait = random.uniform(min_wait, max_wait)
        if action_count > 100:
            base_wait *= 1.5  # 疲労パターン
        elif action_count > 300:
            base_wait *= 2.0
            
        # ランダムな短い休憩を追加
        if random.random() < 0.1:  # 10%の確率で長い休憩
            base_wait += random.uniform(60, 180)
            
        time.sleep(base_wait)

    def safe_click(self, element, max_attempts: int = 3):
        """安全なクリック実行"""
        for attempt in range(max_attempts):
            try:
                self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                time.sleep(0.5)
                element.click()
                return True
            except ElementClickInterceptedException:
                logger.warning(f"Click intercepted, attempt {attempt + 1}")
                time.sleep(1)
            except Exception as e:
                logger.warning(f"Click failed: {e}")
                
        return False

    def extract_usernames_from_page(self) -> Set[Tuple[str, str]]:
        """ページからユーザー名とURLを抽出"""
        usernames = set()
        try:
            # 複数のセレクタパターンを試行
            selectors = [
                '//div[@data-testid="UserCell"]//a[contains(@href, "/")]',
                '//div[contains(@data-testid, "User")]//a[contains(@href, "/")]',
                '//a[contains(@href, "twitter.com/") or contains(@href, "x.com/")]'
            ]
            
            for selector in selectors:
                try:
                    users = self.driver.find_elements(By.XPATH, selector)
                    for user in users:
                        href = user.get_attribute("href")
                        if href and "/status/" not in href and "/search" not in href:
                            # URLの正規化
                            if "twitter.com" in href or "x.com" in href:
                                username_part = href.split("/")[-1].split("?")[0]
                                if username_part and not username_part.startswith("i/"):
                                    username = "@" + username_part
                                    usernames.add((username, href))
                    
                    if usernames:
                        break
                        
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Failed to extract usernames: {e}")
            
        return usernames

    def scroll_and_collect(self, max_scrolls: int = None) -> Set[Tuple[str, str]]:
        """スクロールしてユーザー情報収集"""
        if max_scrolls is None:
            max_scrolls = self.config['search']['max_scroll_per_page']
            
        all_usernames = set()
        last_height = 0
        stable_count = 0
        
        for scroll in range(max_scrolls):
            # 現在のページからユーザー抽出
            current_users = self.extract_usernames_from_page()
            all_usernames.update(current_users)
            
            # スクロール実行
            current_height = self.driver.execute_script("return document.body.scrollHeight")
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # 人間らしい待機
            time.sleep(random.uniform(2, 4))
            
            # 高さの変化をチェック
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == current_height:
                stable_count += 1
                if stable_count >= 2:  # 2回連続で変化なしなら終了
                    break
            else:
                stable_count = 0
                
            last_height = current_height
            
        logger.info(f"Collected {len(all_usernames)} users after {scroll + 1} scrolls")
        return all_usernames

    def search_users_by_keywords(self) -> Set[Tuple[str, str]]:
        """キーワード検索でユーザー収集"""
        all_users = set()
        
        for keyword in self.config['search']['keywords']:
            if len(all_users) >= self.config['search']['max_users_per_keyword'] * len(self.config['search']['keywords']):
                break
                
            try:
                logger.info(f"Searching for keyword: {keyword}")
                search_url = f"https://x.com/search?q={keyword}&src=typed_query&f=user"
                self.driver.get(search_url)
                
                # ページ読み込み待機
                time.sleep(random.uniform(3, 6))
                
                # ユーザー収集
                users = self.scroll_and_collect()
                
                # フィルタリング
                filtered_users = {
                    (username, url) for username, url in users
                    if username not in self.sent_users and url not in self.blacklist_urls
                }
                
                all_users.update(filtered_users)
                logger.info(f"Found {len(filtered_users)} new users for keyword '{keyword}'")
                
                # キーワード間の待機
                self.wait_between_actions()
                
            except Exception as e:
                logger.error(f"Error searching for keyword '{keyword}': {e}")
                continue
                
        return all_users

    def collect_following_users(self, target_users: List[Tuple[str, str]]) -> Set[Tuple[str, str]]:
        """対象ユーザーのフォロイング情報を収集"""
        following_users = set()
        max_targets = min(10, len(target_users))  # 最大10人のフォロイングを取得
        
        for i, (username, _) in enumerate(target_users[:max_targets]):
            try:
                logger.info(f"Collecting following for {username} ({i+1}/{max_targets})")
                
                following_url = f"https://x.com/{username[1:]}/following"
                self.driver.get(following_url)
                
                # ページ読み込み待機
                time.sleep(random.uniform(4, 7))
                
                # フォロイング収集
                users = self.scroll_and_collect(max_scrolls=3)  # フォロイング収集は軽めに
                
                # フィルタリング
                filtered_users = {
                    (username, url) for username, url in users
                    if username not in self.sent_users and url not in self.blacklist_urls
                }
                
                following_users.update(filtered_users)
                logger.info(f"Found {len(filtered_users)} following users for {username}")
                
                # 待機
                self.wait_between_actions()
                
            except Exception as e:
                logger.error(f"Error collecting following for {username}: {e}")
                continue
                
        return following_users

    def send_dm_to_user(self, username: str, url: str, message: str) -> Tuple[bool, str]:
        """個別ユーザーにDM送信"""
        try:
            logger.info(f"Attempting to send DM to {username}")
            
            # プロフィールページに移動
            self.driver.get(url)
            time.sleep(random.uniform(3, 6))
            
            # メッセージボタンを探してクリック
            message_selectors = [
                '//div[@aria-label="メッセージ"]',
                '//div[@data-testid="sendDMFromProfile"]',
                '//a[contains(@href, "/messages/compose")]',
                '//div[contains(text(), "メッセージ")]'
            ]
            
            message_button = None
            for selector in message_selectors:
                try:
                    message_button = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    break
                except TimeoutException:
                    continue
            
            if not message_button:
                return False, "Message button not found"
            
            # ボタンクリック
            if not self.safe_click(message_button):
                return False, "Failed to click message button"
            
            # メッセージ入力欄待機
            time.sleep(random.uniform(2, 4))
            
            # テキストボックス検索
            textbox_selectors = [
                'div[role="textbox"]',
                'div[data-testid="dmComposerTextInput"]',
                'div[contenteditable="true"]'
            ]
            
            textbox = None
            for selector in textbox_selectors:
                try:
                    textbox = self.wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    break
                except TimeoutException:
                    continue
            
            if not textbox:
                return False, "Text input not found"
            
            # メッセージ入力
            textbox.click()
            time.sleep(0.5)
            
            # 人間らしいタイピング
            for char in message:
                textbox.send_keys(char)
                if random.random() < 0.1:  # 10%の確率で短い休憩
                    time.sleep(random.uniform(0.1, 0.3))
            
            # 送信
            time.sleep(random.uniform(1, 2))
            textbox.send_keys(Keys.RETURN)
            
            # 送信確認
            time.sleep(random.uniform(2, 4))
            
            return True, "Success"
            
        except Exception as e:
            logger.error(f"Error sending DM to {username}: {e}")
            return False, str(e)

    def log_sending_result(self, username: str, url: str, status: str, error: str, message: str):
        """送信結果をログに記録"""
        try:
            with open(self.config['files']['log_file'], 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    username,
                    url,
                    status,
                    error,
                    message[:50] + "..." if len(message) > 50 else message
                ])
        except Exception as e:
            logger.error(f"Failed to log result: {e}")

    def send_daily_report(self):
        """日次レポート送信"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            success_count = 0
            fail_count = 0
            failed_users = []
            
            with open(self.config['files']['log_file'], 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['date'].startswith(today):
                        if row['status'] == 'Success':
                            success_count += 1
                        else:
                            fail_count += 1
                            failed_users.append(f"{row['username']} ({row['error'][:30]})")
            
            # レポート作成
            report = f"""
📊 X DM送信 日次レポート ({today})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 送信成功: {success_count}件
❌ 送信失敗: {fail_count}件
📈 成功率: {success_count/(success_count+fail_count)*100:.1f}% ({success_count}/{success_count+fail_count})
"""
            
            if failed_users[:5]:  # 最大5件の失敗例を表示
                report += "\n⚠️ 主な送信失敗:\n" + "\n".join([f"・{user}" for user in failed_users[:5]])
            
            # Slack送信
            self.notify_slack(report.strip())
            logger.info("Daily report sent successfully")
            
        except Exception as e:
            logger.error(f"Failed to send daily report: {e}")
            self.notify_slack(f"❌ 日次レポート生成エラー: {e}")

    def send_monthly_report(self):
        """月次レポート送信（月初に実行）"""
        try:
            now = datetime.now()
            if now.day != self.config['slack']['monthly_report_day']:
                return
                
            # 前月のデータを集計
            last_month = (now.replace(day=1) - timedelta(days=1))
            month_str = last_month.strftime('%Y-%m')
            
            total_sent = 0
            total_replies = 0  # 実装時は返信データも記録する必要あり
            daily_counts = {}
            
            with open(self.config['files']['log_file'], 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['date'].startswith(month_str) and row['status'] == 'Success':
                        total_sent += 1
                        day = row['date'][:10]
                        daily_counts[day] = daily_counts.get(day, 0) + 1
            
            # 月次レポート作成
            avg_daily = total_sent / len(daily_counts) if daily_counts else 0
            
            report = f"""
📅 X DM送信 月次レポート ({last_month.strftime('%Y年%m月')})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 総送信数: {total_sent}件
📈 平均日次送信: {avg_daily:.1f}件
📆 稼働日数: {len(daily_counts)}日
💬 返信数: {total_replies}件 (手動集計要)
🎯 返信率: 手動集計要
"""
            
            self.notify_slack(report.strip())
            logger.info("Monthly report sent successfully")
            
        except Exception as e:
            logger.error(f"Failed to send monthly report: {e}")

    def notify_slack(self, message: str):
        """Slack通知"""
        try:
            response = requests.post(
                self.config['slack']['webhook_url'],
                json={"text": message},
                timeout=10
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Slack notification failed: {e}")

    def run(self):
        """メイン実行"""
        try:
            logger.info("Starting X DM Sender")
            
            # 時間チェック
            if not self.is_allowed_time():
                logger.info("Current time is in blocked hours. Exiting.")
                return
            
            # Chrome起動
            self.setup_chrome_driver()
            
            # メッセージテキスト読み込み
            message_text = self.load_message_text()
            
            # ユーザー収集
            logger.info("Starting user collection...")
            target_users = self.search_users_by_keywords()
            
            # 足りない場合はフォロイング収集
            if len(target_users) < self.config['sending']['max_messages_per_day']:
                logger.info("Not enough users found. Collecting following users...")
                following_users = self.collect_following_users(list(target_users))
                target_users.update(following_users)
            
            # 送信実行
            logger.info(f"Starting DM sending to {min(len(target_users), self.config['sending']['max_messages_per_day'])} users")
            
            for username, url in list(target_users)[:self.config['sending']['max_messages_per_day']]:
                if self.sent_count >= self.config['sending']['max_messages_per_day']:
                    break
                    
                if not self.is_allowed_time():
                    logger.info("Reached blocked hours. Stopping.")
                    break
                
                # DM送信
                success, error = self.send_dm_to_user(username, url, message_text)
                
                # ログ記録
                status = "Success" if success else "Failed"
                self.log_sending_result(username, url, status, error, message_text)
                
                if success:
                    self.sent_count += 1
                    self.sent_users.add(username)
                    logger.info(f"DM sent successfully to {username} ({self.sent_count}/{self.config['sending']['max_messages_per_day']})")
                else:
                    logger.warning(f"Failed to send DM to {username}: {error}")
                
                # 待機
                self.wait_between_actions(self.sent_count)
            
            logger.info(f"DM sending completed. Total sent: {self.sent_count}")
            
        except Exception as e:
            logger.error(f"Critical error in main execution: {e}")
            self.notify_slack(f"🚨 システムエラー: {e}")
            
        finally:
            # リソースクリーンアップ
            if self.driver:
                self.driver.quit()
            
            # レポート送信
            self.send_daily_report()
            self.send_monthly_report()


def main():
    """エントリーポイント"""
    try:
        sender = XDMSender()
        sender.run()
    except Exception as e:
        logger.error(f"Failed to initialize or run DM sender: {e}")


if __name__ == "__main__":
    main() 