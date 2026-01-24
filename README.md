# LCSC Linker for KiCad

KiCadの回路図ファイル（.kicad_sch）に対して、LCSCの部品番号とURLを自動的にリンクするツールです。

**個人利用・教育目的向け**のツールです。商用利用は推奨しません。

## 機能

- KiCad 9.0の回路図ファイル（.kicad_sch）を解析
- 部品のValue（値）とFootprint（パッケージ）からLCSC/JLCPCB部品を検索
- 対話的に候補から選択
- LCSCフィールドとURLフィールドを自動記入
- **GUIアプリケーション**と**CLIツール**の両方に対応

## 動作環境

- Python 3.10以上
- macOS / Linux / Windows

## インストール

```bash
git clone https://github.com/yourname/lcsc-linker.git
cd lcsc-linker

# venv作成（必須）
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係インストール
pip install -r requirements.txt
```

## 使い方

### GUIアプリケーション（推奨）

```bash
source venv/bin/activate
python lcsc_linker_gui.py
```

#### GUI操作方法

1. **Browse...** または **File > Open** で .kicad_sch ファイルを選択
2. 部品一覧が表示される
3. 処理方法を選択:
   - **Process All Components** - 全部品を順次処理
   - **Process Empty Only** - LCSC未設定の部品のみ処理
   - 部品をダブルクリック - 個別に処理
4. 部品ダイアログで:
   - 検索結果から選択
   - カスタム検索クエリで再検索
   - 手動でLCSC IDを入力（例: C123456）
   - 検索結果をダブルクリックでLCSCページを開く
5. **Save** で保存

### CLIツール

```bash
source venv/bin/activate
python lcsc_linker.py path/to/schematic.kicad_sch
```

#### CLIオプション

| オプション | 説明 |
|-----------|------|
| `-o FILE` | 出力ファイルを指定（デフォルト: 入力ファイルを上書き） |
| `--overwrite` | 既存のLCSCフィールドを上書き |
| `--dry-run` | 変更を保存せずに動作確認 |

#### CLI対話モード

各部品に対して検索結果が表示され、以下の操作が可能です：

- `[1-N]` - 番号で部品を選択
- `[s]` - カスタム検索クエリで再検索
- `[m]` - LCSC IDを手動入力（例: C123456）
- `[k]` - スキップ
- `[q]` - 終了

## 注意事項

### バックアップについて

**重要**: このツールは回路図ファイルを直接編集します。使用前に必ずバックアップを取ってください。KiCadの自動バックアップ機能（プロジェクトフォルダ内の `*-backups/` フォルダ）も活用してください。

### 非公式APIについて

このツールはJLCPCBの**非公式な内部API**を使用して部品検索を行っています。

- 公式にサポートされたAPIではありません
- 予告なく変更・停止される可能性があります
- 過度な使用はレート制限（403エラー）を受ける可能性があります
- **個人利用・教育目的のみ**を想定しています
- 商用利用は推奨しません

公式APIを利用したい場合は [LCSC Open API](https://www.lcsc.com/docs/openapi/index.html) または [JLCPCB API](https://api.jlcpcb.com/) に申請してください。

## トラブルシューティング

### `ModuleNotFoundError: No module named 'requests'` または `No module named 'wx'`

venvが有効化されていません。以下を実行してください：

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### `Rate limited` または `403 Forbidden`

APIのレート制限に達しました。数分待ってから再実行してください。

### 検索結果が0件

- 検索クエリが特殊文字を含む場合、別のクエリを試してください
- LCSC IDを直接入力することもできます

## ファイル構成

```
lcsc_linker.py      # CLI版メインスクリプト
lcsc_linker_gui.py  # GUI版アプリケーション（wxPython）
kicad_parser.py     # KiCad .kicad_sch パーサー
lcsc_api.py         # JLCPCB API クライアント
fix_lcsc.py         # バッチ処理用スクリプト
requirements.txt    # 依存関係（requests, wxPython）
```

## ライセンス

MIT License

## 免責事項

本ソフトウェアは「現状のまま」提供され、明示または黙示を問わず、いかなる保証もありません。作者は、本ソフトウェアの使用によって生じたいかなる損害についても責任を負いません。

ファイルの破損や予期しない動作が発生する可能性があります。重要なデータは必ずバックアップしてください。

非公式APIの使用は利用規約のグレーゾーンに該当する可能性があります。自己責任でご利用ください。
