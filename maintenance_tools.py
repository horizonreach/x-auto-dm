#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X DM送信システム メンテナンスツール
データ分析・トラブルシューティング・システム監視
"""

import csv
import json
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict, Counter

import pandas as pd
import requests

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MaintenanceTools:
    def __init__(self, config_file: str = "config.json"):
        """初期化"""
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.log_file = self.config['files']['log_file']
    
    def analyze_sending_statistics(self, days: int = 7) -> Dict:
        """送信統計分析"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            stats = {
                'total_attempts': 0,
                'successful_sends': 0,
                'failed_sends': 0,
                'success_rate': 0.0,
                'daily_breakdown': defaultdict(lambda: {'success': 0, 'failed': 0}),
                'error_analysis': Counter(),
                'hourly_pattern': defaultdict(int),
                'most_active_days': [],
                'recommendations': []
            }
            
            with open(self.log_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        send_date = datetime.strptime(row['date'], '%Y-%m-%d %H:%M:%S')
                        if send_date >= cutoff_date:
                            stats['total_attempts'] += 1
                            day_key = send_date.strftime('%Y-%m-%d')
                            hour_key = send_date.hour
                            
                            if row['status'] == 'Success':
                                stats['successful_sends'] += 1
                                stats['daily_breakdown'][day_key]['success'] += 1
                            else:
                                stats['failed_sends'] += 1
                                stats['daily_breakdown'][day_key]['failed'] += 1
                                stats['error_analysis'][row['error'][:50]] += 1
                            
                            stats['hourly_pattern'][hour_key] += 1
                            
                    except (ValueError, KeyError) as e:
                        continue
            
            # 成功率計算
            if stats['total_attempts'] > 0:
                stats['success_rate'] = (stats['successful_sends'] / stats['total_attempts']) * 100
            
            # 最も活発な日を特定
            daily_totals = {day: data['success'] + data['failed'] 
                          for day, data in stats['daily_breakdown'].items()}
            stats['most_active_days'] = sorted(daily_totals.items(), 
                                             key=lambda x: x[1], reverse=True)[:3]
            
            # 推奨事項
            if stats['success_rate'] < 70:
                stats['recommendations'].append("⚠️ 成功率が70%を下回っています。セレクタの更新が必要かもしれません")
            
            if stats['error_analysis'].most_common(1):
                top_error = stats['error_analysis'].most_common(1)[0]
                if top_error[1] > stats['total_attempts'] * 0.3:
                    stats['recommendations'].append(f"🔧 主要エラー: {top_error[0]} ({top_error[1]}回)")
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to analyze statistics: {e}")
            return {}
    
    def check_sent_history_health(self) -> Dict:
        """送信履歴の健全性チェック"""
        try:
            reset_days = self.config['sending']['sent_history_reset_days']
            cutoff_date = datetime.now() - timedelta(days=reset_days)
            
            unique_users = set()
            recent_users = set()
            duplicate_sends = []
            
            with open(self.log_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        send_date = datetime.strptime(row['date'], '%Y-%m-%d %H:%M:%S')
                        username = row['username']
                        
                        if username in unique_users:
                            duplicate_sends.append({
                                'username': username,
                                'date': row['date'],
                                'status': row['status']
                            })
                        
                        unique_users.add(username)
                        
                        if send_date >= cutoff_date and row['status'] == 'Success':
                            recent_users.add(username)
                            
                    except (ValueError, KeyError):
                        continue
            
            return {
                'total_unique_users': len(unique_users),
                'recent_successful_users': len(recent_users),
                'duplicate_sends': duplicate_sends[:10],  # 最初の10件
                'reset_effectiveness': len(recent_users) / len(unique_users) * 100 if unique_users else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to check sent history health: {e}")
            return {}
    
    def validate_system_health(self) -> Dict:
        """システム全体の健全性チェック"""
        health_report = {
            'timestamp': datetime.now().isoformat(),
            'status': 'healthy',
            'issues': [],
            'warnings': []
        }
        
        try:
            # 必要ファイルの存在チェック
            required_files = [
                'config.json',
                'credentials.json', 
                'text_sender.txt',
                'x_dm_sender_improved.py'
            ]
            
            missing_files = [f for f in required_files if not Path(f).exists()]
            if missing_files:
                health_report['issues'].append(f"Missing files: {missing_files}")
                health_report['status'] = 'critical'
            
            # ログファイルサイズチェック
            if Path(self.log_file).exists():
                log_size_mb = Path(self.log_file).stat().st_size / (1024 * 1024)
                if log_size_mb > 100:  # 100MB以上
                    health_report['warnings'].append(f"Log file size: {log_size_mb:.1f}MB (consider rotation)")
            
            # 設定ファイル検証
            try:
                with open('config.json', 'r') as f:
                    config = json.load(f)
                    
                if config['slack']['webhook_url'] == "https://hooks.slack.com/services/XXXX/XXXX/XXXX":
                    health_report['warnings'].append("Slack webhook URL not configured")
                    
            except Exception as e:
                health_report['issues'].append(f"Config file validation failed: {e}")
                health_report['status'] = 'critical'
            
            # 最近の送信アクティビティチェック
            recent_activity = self.check_recent_activity()
            if not recent_activity:
                health_report['warnings'].append("No recent sending activity detected")
            
            return health_report
            
        except Exception as e:
            health_report['status'] = 'error'
            health_report['issues'].append(f"Health check failed: {e}")
            return health_report
    
    def check_recent_activity(self, hours: int = 24) -> bool:
        """最近のアクティビティチェック"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            with open(self.log_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        send_date = datetime.strptime(row['date'], '%Y-%m-%d %H:%M:%S')
                        if send_date >= cutoff_time:
                            return True
                    except (ValueError, KeyError):
                        continue
            
            return False
            
        except FileNotFoundError:
            return False
        except Exception:
            return False
    
    def generate_comprehensive_report(self, days: int = 7) -> str:
        """包括的なレポート生成"""
        try:
            stats = self.analyze_sending_statistics(days)
            health = self.validate_system_health()
            history_health = self.check_sent_history_health()
            
            report = f"""
📊 X DM送信システム 包括レポート
生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
分析期間: 過去{days}日間

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 送信統計
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 総送信試行: {stats.get('total_attempts', 0):,}件
• 送信成功: {stats.get('successful_sends', 0):,}件
• 送信失敗: {stats.get('failed_sends', 0):,}件
• 成功率: {stats.get('success_rate', 0):.1f}%

📅 最も活発な日:
"""
            
            for day, count in stats.get('most_active_days', [])[:3]:
                report += f"• {day}: {count}件\n"
            
            report += f"""
⏰ 時間別送信パターン (上位5時間):
"""
            hourly_sorted = sorted(stats.get('hourly_pattern', {}).items(), 
                                 key=lambda x: x[1], reverse=True)
            for hour, count in hourly_sorted[:5]:
                report += f"• {hour:02d}時: {count}件\n"
            
            report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ エラー分析
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            for error, count in stats.get('error_analysis', {}).most_common(5):
                report += f"• {error}: {count}回\n"
            
            report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏥 システム健全性
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• ステータス: {health.get('status', 'unknown').upper()}
• 登録済みユーザー数: {history_health.get('total_unique_users', 0):,}人
• 3ヶ月以内送信済み: {history_health.get('recent_successful_users', 0):,}人
• リセット効果: {history_health.get('reset_effectiveness', 0):.1f}%
"""
            
            if health.get('issues'):
                report += "\n🚨 重要な問題:\n"
                for issue in health['issues']:
                    report += f"• {issue}\n"
            
            if health.get('warnings'):
                report += "\n⚠️ 警告:\n"
                for warning in health['warnings']:
                    report += f"• {warning}\n"
            
            if stats.get('recommendations'):
                report += "\n💡 推奨事項:\n"
                for rec in stats['recommendations']:
                    report += f"• {rec}\n"
            
            return report.strip()
            
        except Exception as e:
            logger.error(f"Failed to generate report: {e}")
            return f"レポート生成エラー: {e}"
    
    def export_data_to_excel(self, days: int = 30, output_file: str = None) -> str:
        """データをExcelにエクスポート"""
        try:
            if output_file is None:
                output_file = f"dm_sender_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # データ読み込み
            data = []
            with open(self.log_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        send_date = datetime.strptime(row['date'], '%Y-%m-%d %H:%M:%S')
                        if send_date >= cutoff_date:
                            data.append(row)
                    except (ValueError, KeyError):
                        continue
            
            # Excel出力
            df = pd.DataFrame(data)
            if not df.empty:
                with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='送信ログ', index=False)
                    
                    # 統計シート
                    stats = self.analyze_sending_statistics(days)
                    stats_data = [
                        ['項目', '値'],
                        ['総送信試行', stats.get('total_attempts', 0)],
                        ['送信成功', stats.get('successful_sends', 0)],
                        ['送信失敗', stats.get('failed_sends', 0)],
                        ['成功率(%)', f"{stats.get('success_rate', 0):.1f}"]
                    ]
                    pd.DataFrame(stats_data[1:], columns=stats_data[0]).to_excel(
                        writer, sheet_name='統計', index=False
                    )
            
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to export to Excel: {e}")
            return None
    
    def send_maintenance_report_to_slack(self, days: int = 7):
        """メンテナンスレポートをSlackに送信"""
        try:
            report = self.generate_comprehensive_report(days)
            
            # 長すぎる場合は要約版を作成
            if len(report) > 3000:
                stats = self.analyze_sending_statistics(days)
                health = self.validate_system_health()
                
                short_report = f"""
🔧 X DMシステム メンテナンスレポート
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 過去{days}日間: 成功{stats.get('successful_sends', 0)}件 / 試行{stats.get('total_attempts', 0)}件 ({stats.get('success_rate', 0):.1f}%)
🏥 システム状態: {health.get('status', 'unknown').upper()}
"""
                if health.get('issues'):
                    short_report += f"🚨 問題: {len(health['issues'])}件\n"
                if health.get('warnings'):
                    short_report += f"⚠️ 警告: {len(health['warnings'])}件\n"
                
                report = short_report.strip()
            
            # Slack送信
            response = requests.post(
                self.config['slack']['webhook_url'],
                json={"text": report},
                timeout=10
            )
            response.raise_for_status()
            
            logger.info("Maintenance report sent to Slack successfully")
            
        except Exception as e:
            logger.error(f"Failed to send maintenance report: {e}")


def main():
    """コマンドライン実行"""
    parser = argparse.ArgumentParser(description='X DM Sender Maintenance Tools')
    parser.add_argument('--analyze', '-a', type=int, default=7, 
                       help='Analyze statistics for specified days (default: 7)')
    parser.add_argument('--health', action='store_true', 
                       help='Perform system health check')
    parser.add_argument('--report', '-r', type=int, 
                       help='Generate comprehensive report for specified days')
    parser.add_argument('--export', '-e', type=int, 
                       help='Export data to Excel for specified days')
    parser.add_argument('--slack', '-s', type=int, 
                       help='Send maintenance report to Slack for specified days')
    
    args = parser.parse_args()
    tools = MaintenanceTools()
    
    if args.health:
        health = tools.validate_system_health()
        print(json.dumps(health, indent=2, ensure_ascii=False))
    
    if args.analyze:
        stats = tools.analyze_sending_statistics(args.analyze)
        print(json.dumps(stats, indent=2, ensure_ascii=False, default=str))
    
    if args.report:
        report = tools.generate_comprehensive_report(args.report)
        print(report)
    
    if args.export:
        output_file = tools.export_data_to_excel(args.export)
        if output_file:
            print(f"Data exported to: {output_file}")
        else:
            print("Export failed")
    
    if args.slack:
        tools.send_maintenance_report_to_slack(args.slack)
        print("Maintenance report sent to Slack")


if __name__ == "__main__":
    main() 