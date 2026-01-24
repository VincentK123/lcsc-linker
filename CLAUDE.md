# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 言語設定

ユーザーとのやり取りは日本語で行う

## プロジェクト概要

KiCadの回路図ファイル（.kicad_sch）を読み込み、各部品に対してLCSCから候補部品を検索し、LCSCフィールド（部品番号とURL）を自動記入するPythonツール。

## 開発コマンド

```bash
# venv作成・有効化
python3 -m venv venv
source venv/bin/activate

# 依存関係インストール
pip install -r requirements.txt

# 実行
python lcsc_linker.py path/to/project.kicad_sch
```

## アーキテクチャ

```
lcsc_linker.py      # メインエントリーポイント・CLI・対話的選択UI
kicad_parser.py     # .kicad_sch S式パーサー/ライター
lcsc_api.py         # LCSC検索APIクライアント（JLCPCB非公式API使用）
fix_lcsc.py         # 手動LCSC情報注入スクリプト（バッチ処理用）
```

## KiCad 9.0 .kicad_schファイル形式

S式（S-expression）テキスト形式。部品は以下の構造：

```lisp
(symbol (lib_id "Device:C")
  (property "Reference" "C1" ...)
  (property "Value" "100nF" ...)
  (property "Footprint" "Capacitor_SMD:C_0402_1005Metric" ...)
  (property "LCSC" "" ...)  ← 部品番号を記入
  (property "URL" "" ...)   ← LCSCページURLを記入
)
```

## LCSC検索（重要）

- **非公式API使用**: JLCPCB SMT部品検索API（公式サポートなし）
- APIエンドポイント: `jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList`
- 検索クエリ: Value + パッケージサイズ（Footprintから抽出）
- パッケージサイズ抽出: `C_0402_1005Metric` -> `0402`
- レート制限あり（連続リクエストで403エラー）

## CLIオプション

```bash
python lcsc_linker.py schematic.kicad_sch           # 通常実行
python lcsc_linker.py schematic.kicad_sch -o out.kicad_sch  # 出力先指定
python lcsc_linker.py schematic.kicad_sch --overwrite       # 既存LCSC上書き
python lcsc_linker.py schematic.kicad_sch --dry-run         # 変更保存しない
```

## 注意事項

- 使用前に必ずバックアップを取ること
- 非公式APIは予告なく変更される可能性あり
