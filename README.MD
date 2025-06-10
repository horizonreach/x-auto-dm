# X(Twitter) DM自動送信システム

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

VTuber、ライバー、配信者向けのX(Twitter) DM自動送信システムです。安全で効率的な運用を重視し、アカウント凍結リスクを最小限に抑えながら1日最大500件のDM送信を実現します。

## 🌟 主な機能

### ✨ 自動化機能
- **キーワード検索による自動ターゲティング**
- **フォロワー情報収集による送信対象拡大**
- **3ヶ月自動リセット機能付き重複送信防止**
- **時間帯制限（AM3:00-9:00 送信停止）**
- **人間らしい送信パターンの実装**

### 📈 監視・レポート
- **Slack日次レポート自動送信**
- **月次統計レポート**
- **システムヘルスチェック**
- **エラー分析・トラブルシューティング**

### 🛡️ 安全対策
- **Googleスプレッドシート連携ブラックリスト**
- **送信間隔の動的調整**
- **WebDriver検出回避**
- **包括的エラーハンドリング**

## 📋 前提条件

### システム要件
- **Python 3.9以上**
- **Chrome ブラウザ（最新版推奨）**
- **ChromeDriver**
- **Windows 10/11 または macOS 10.14+**

### 必要なアカウント・サービス
- ✅ X(Twitter)アカウント（DM送信可能な状態）
- ✅ Slack Workspace（通知用）
- ✅ Google Cloud Platform アカウント（Sheets API用）
- ✅ Googleスプレッドシート（ブラックリスト管理用）

## 🚀 セットアップガイド

### 1. リポジトリのクローン

```bash
git clone https://github.com/your-username/x-auto-dm.git
cd x-auto-dm
```

### 2. Python仮想環境の作成（推奨）

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 4. ChromeDriverのセットアップ

#### 方法A: 自動ダウンロード（推奨）
```bash
pip install webdriver-manager
```

#### 方法B: 手動ダウンロード
1. [ChromeDriver公式サイト](https://chromedriver.chromium.org/)から対応バージョンをダウンロード
2. `chromedriver.exe`を適当なフォルダに配置
3. `config.json`でパスを指定

### 5. Google Sheets API設定

#### 5.1 Google Cloud Console設定
1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. 新しいプロジェクトを作成
3. 「APIとサービス」→「ライブラリ」→「Google Sheets API」を有効化
4. 「APIとサービス」→「認証情報」→「認証情報を作成」→「サービスアカウント」
5. サービスアカウント作成後、「キー」タブ→「キーを追加」→「JSON」
6. ダウンロードしたJSONファイルを`credentials.json`として保存

#### 5.2 スプレッドシート準備
1. [Googleスプレッドシート](https://sheets.google.com)で新しいシートを作成
2. A列にユーザー名、B列にブラックリストURLを記入
3. サービスアカウントのメールアドレス（JSONファイル内の`client_email`）にシートの編集権限を付与
4. スプレッドシートのURLからIDを取得（`/spreadsheets/d/【ここがID】/edit`）

### 6. Slack Webhook設定

1. Slack Workspace→「設定と管理」→「アプリを管理」
2. 「Incoming Webhooks」をインストール
3. チャンネルを選択してWebhook URLを取得

### 7. 設定ファイルの編集

`config.json`を編集して以下の項目を設定：

```json
{
  "chrome": {
    "driver_path": "C:\\path\\to\\chromedriver.exe",
    "profile_path": "user-data-dir=C:\\Users\\YourName\\AppData\\Local\\Google\\Chrome\\User Data",
    "headless": false,
    "window_size": [1920, 1080]
  },
  "slack": {
    "webhook_url": "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
    "daily_report_time": "23:30",
    "monthly_report_day": 1
  },
  "search": {
    "keywords": ["Vtuber", "配信者", "ライバー", "実況者"],
    "max_scroll_per_page": 5,
    "max_users_per_keyword": 200
  },
  "sending": {
    "max_messages_per_day": 500,
    "blocked_hours": [3, 4, 5, 6, 7, 8, 9],
    "min_wait_seconds": 15,
    "max_wait_seconds": 45,
    "retry_attempts": 3,
    "sent_history_reset_days": 90
  },
  "google_sheets": {
    "credentials_file": "credentials.json",
    "spreadsheet_key": "YOUR_SPREADSHEET_ID_HERE",
    "blacklist_column": 2
  },
  "files": {
    "log_file": "sent_log.csv",
    "message_file": "text_sender.txt"
  }
}
```

### 8. メッセージテンプレート設定

`text_sender.txt`に送信したいメッセージを記載：

```
こんにちは！

○○の企画でご連絡いたします。

【あなたのサービス内容】

ご興味がございましたら、ぜひお返事ください。

よろしくお願いいたします。
```

## 💻 使用方法

### 基本実行

```bash
# 1回だけ実行（テスト用）
python x_dm_sender_improved.py

# スケジューラー起動（本格運用）
python scheduler.py
```

### バックグラウンド実行（長期運用）

```bash
# Windows（PowerShell）
Start-Process python -ArgumentList "scheduler.py" -WindowStyle Hidden

# macOS/Linux
nohup python3 scheduler.py > scheduler.log 2>&1 &
```

### メンテナンスコマンド

```bash
# システム状態確認
python maintenance_tools.py --health

# 過去7日間の統計分析
python maintenance_tools.py --analyze 7

# 詳細レポート生成
python maintenance_tools.py --report 7

# データをExcelにエクスポート
python maintenance_tools.py --export 30

# Slackにメンテナンスレポート送信
python maintenance_tools.py --slack 7
```

## 📊 運用ガイド

### 日常的な確認事項

#### 毎日
- [ ] Slackの日次レポート確認
- [ ] 送信成功率が70%以上かチェック
- [ ] エラー通知の有無確認

#### 週次
- [ ] ログファイルサイズ確認（100MB超過時は要対応）
- [ ] メッセージテンプレート効果測定
- [ ] ブラックリスト更新

#### 月次
- [ ] 月次レポート分析
- [ ] キーワード効果見直し
- [ ] システム設定最適化

### 推奨運用設定

```json
// 控えめスタート（1日50件から開始）
"max_messages_per_day": 50

// 慣れてきたら段階的に増加
"max_messages_per_day": 150  // 1週間後
"max_messages_per_day": 300  // 2週間後
"max_messages_per_day": 500  // 1ヶ月後（最大）
```

## 🔧 トラブルシューティング

### よくある問題と解決方法

#### 1. ChromeDriverエラー
```
selenium.common.exceptions.SessionNotCreatedException
```
**解決方法:**
- ChromeとChromeDriverのバージョンを一致させる
- ChromeDriverを最新版にアップデート

#### 2. 送信成功率が低い（<70%）
**原因と対策:**
- Xの仕様変更 → セレクタを更新
- 送信間隔が短すぎる → 待機時間を増加
- アカウントに制限 → 24時間様子見

#### 3. "Message button not found"エラー頻発
**解決方法:**
```python
# x_dm_sender_improved.pyの355-361行目を確認
message_selectors = [
    '//div[@aria-label="メッセージ"]',
    '//div[@data-testid="sendDMFromProfile"]',
    # 新しいセレクタを追加
]
```

#### 4. Google Sheets API認証エラー
**確認事項:**
- `credentials.json`ファイルの存在
- サービスアカウントにスプレッドシート権限があるか
- `spreadsheet_key`が正しいか

### ログファイルの確認

```bash
# 最新のエラーを確認
tail -f x_dm_sender.log

# 特定の日付のログを確認
grep "2024-06-15" sent_log.csv

# 成功率を確認
python -c "
import csv
with open('sent_log.csv', 'r') as f:
    reader = csv.DictReader(f)
    success = sum(1 for row in reader if row['status'] == 'Success')
    total = sum(1 for row in csv.DictReader(open('sent_log.csv', 'r')))
print(f'成功率: {success/total*100:.1f}% ({success}/{total})')
"
```

## 🚨 緊急時対応

### システム停止

```bash
# プロセス確認
ps aux | grep python

# 強制停止（Windows）
taskkill /f /im python.exe

# 強制停止（macOS/Linux）
pkill -f "python.*scheduler.py"
```

### 緊急設定変更

```bash
# 一時的に送信を完全停止
echo '{"sending": {"max_messages_per_day": 0}}' > emergency_config.json

# システム状態確認
python maintenance_tools.py --health
```

## 📈 パフォーマンス最適化

### 送信数向上のコツ

1. **キーワード最適化**
   ```json
   "keywords": [
     "Vtuber新人",      // 高反応率
     "配信始めました",   // 高反応率  
     "フォロバ100",     // 中反応率
     "ゲーム実況"       // 安定した反応
   ]
   ```

2. **時間帯最適化**
   ```json
   // 高反応時間帯での実行
   "blocked_hours": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]  // 朝活時間避け
   ```

3. **メッセージ最適化**
   - 短文（200文字以内）
   - 具体的な価値提案
   - Call-to-Action明確

## 🔒 セキュリティ・凍結対策

### 実装済み安全対策

✅ **人間らしい操作パターン**
- ランダムな待機時間（15-45秒）
- スクロール速度の変動
- クリック位置の微調整

✅ **検出回避技術**
- WebDriverフラグの無効化
- Automation除外設定
- User-Agent正規化

✅ **リスク分散**
- 複数時間帯での分散実行
- 段階的送信量増加
- 異常検知時の自動停止

### 凍結リスク軽減のベストプラクティス

1. **送信量の段階的増加**
   - 1週目: 50件/日
   - 2週目: 150件/日
   - 3週目: 300件/日
   - 4週目〜: 500件/日

2. **手動操作の併用**
   - 週に2-3回は手動でXにログイン
   - いいね・リツイートも適度に実行
   - プロフィール更新を定期的に実施

3. **送信時間の分散**
   - 1日3回に分けて送信
   - 平日と休日でパターンを変更
   - 長期休暇時は送信量を減少

## 📜 ライセンス

本プロジェクトはMITライセンスの下で公開されています。

## ⚠️ 免責事項

- 本システムは教育・研究目的で開発されています
- X(Twitter)の利用規約を遵守してご利用ください
- アカウント凍結等のリスクは利用者の責任となります
- 法的問題については利用者が責任を負います

## 🤝 サポート・メンテナンス

### コミュニティサポート
- Issue報告: [GitHub Issues](https://github.com/your-username/x-auto-dm/issues)
- 機能要望: [GitHub Discussions](https://github.com/your-username/x-auto-dm/discussions)

### 商用サポート（有料）
- 緊急対応（24時間以内）
- X仕様変更への即日対応
- カスタマイズ・新機能開発
- 運用コンサルティング

詳細は[Issues](https://github.com/your-username/x-auto-dm/issues)でお問い合わせください。

---

**開発**: X DM Automation Team  
**最終更新**: 2024年6月  
**バージョン**: 2.0.0
