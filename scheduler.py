#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X DM送信システム スケジューラー
定期実行・メンテナンス・監視機能
"""

import schedule
import time
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DMSenderScheduler:
    def __init__(self):
        self.script_path = "x_dm_sender_improved.py"
        
    def run_dm_sender(self):
        """DM送信スクリプト実行"""
        try:
            logger.info("Starting scheduled DM sender execution")
            
            # Pythonスクリプト実行
            result = subprocess.run(
                [sys.executable, self.script_path],
                capture_output=True,
                text=True,
                timeout=3600  # 1時間タイムアウト
            )
            
            if result.returncode == 0:
                logger.info("DM sender completed successfully")
            else:
                logger.error(f"DM sender failed with return code {result.returncode}")
                logger.error(f"Error output: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            logger.error("DM sender execution timed out")
        except Exception as e:
            logger.error(f"Failed to run DM sender: {e}")
    
    def cleanup_old_logs(self, days: int = 30):
        """古いログファイルのクリーンアップ"""
        try:
            import os
            from datetime import timedelta
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            for log_file in Path('.').glob('*.log'):
                if log_file.stat().st_mtime < cutoff_date.timestamp():
                    log_file.unlink()
                    logger.info(f"Deleted old log file: {log_file}")
                    
        except Exception as e:
            logger.error(f"Failed to cleanup logs: {e}")
    
    def health_check(self):
        """システムヘルスチェック"""
        try:
            # 必要ファイルの存在確認
            required_files = [
                'config.json',
                'credentials.json',
                'text_sender.txt',
                self.script_path
            ]
            
            missing_files = []
            for file in required_files:
                if not Path(file).exists():
                    missing_files.append(file)
            
            if missing_files:
                logger.warning(f"Missing required files: {missing_files}")
            else:
                logger.info("Health check passed - all required files present")
                
        except Exception as e:
            logger.error(f"Health check failed: {e}")
    
    def start_scheduler(self):
        """スケジューラー開始"""
        logger.info("Starting DM Sender Scheduler")
        
        # 平日の定期実行スケジュール（複数回に分散）
        schedule.every().monday.at("10:30").do(self.run_dm_sender)
        schedule.every().monday.at("15:00").do(self.run_dm_sender)
        schedule.every().monday.at("19:30").do(self.run_dm_sender)
        
        schedule.every().tuesday.at("11:00").do(self.run_dm_sender)
        schedule.every().tuesday.at("16:30").do(self.run_dm_sender)
        schedule.every().tuesday.at("20:00").do(self.run_dm_sender)
        
        schedule.every().wednesday.at("10:00").do(self.run_dm_sender)
        schedule.every().wednesday.at("14:30").do(self.run_dm_sender)
        schedule.every().wednesday.at("18:00").do(self.run_dm_sender)
        
        schedule.every().thursday.at("11:30").do(self.run_dm_sender)
        schedule.every().thursday.at("15:30").do(self.run_dm_sender)
        schedule.every().thursday.at("19:00").do(self.run_dm_sender)
        
        schedule.every().friday.at("10:00").do(self.run_dm_sender)
        schedule.every().friday.at("16:00").do(self.run_dm_sender)
        schedule.every().friday.at("18:30").do(self.run_dm_sender)
        
        # 土日は軽めの実行
        schedule.every().saturday.at("14:00").do(self.run_dm_sender)
        schedule.every().sunday.at("15:00").do(self.run_dm_sender)
        
        # メンテナンス系タスク
        schedule.every().day.at("02:00").do(self.health_check)
        schedule.every().week.at("02:30").do(lambda: self.cleanup_old_logs(30))
        
        logger.info("Scheduler configured. Starting execution loop...")
        
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # 1分間隔でチェック
            except KeyboardInterrupt:
                logger.info("Scheduler stopped by user")
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(300)  # エラー時は5分待機


def main():
    """エントリーポイント"""
    scheduler = DMSenderScheduler()
    scheduler.start_scheduler()


if __name__ == "__main__":
    main() 