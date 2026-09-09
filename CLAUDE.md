# CLAUDE.md — Physics Analysis Agent instructions

学部学生向け B → D\*τν 感度スタディのリポジトリ。エージェントは以下の規約に従うこと。

## ワークフロー(必須)

1. **Plan**: 解析タスクを受けたら、まず計画(生成するサンプル、選択、評価する量)を短くまとめてユーザーに提示し、承認を得る。
2. **Execute**: 承認後に実行。MC 生成・解析コードの変更は必ず再実行して確認する。
3. **Report**: 結果はプロット + 短い Markdown サマリで報告。数値は表に。

## 環境

- conda 環境 `physagent`(/opt/anaconda3/envs/physagent)。実行前に `source scripts/env.sh`。
- EvtGen 2.2.3(conda-forge, osx-arm64)。DECAY.DEC / evt.pdl は `$CONDA_PREFIX/share/EvtGen/`。
- フル検出器シミュレーションは使わない。検出器効果は `fastsim/` のスメアリングで模擬する。

## 物理コンベンション

- 崩壊モード表記は B0 基準: signal = B0 → D\*⁻ τ⁺ ν_τ(CC 含む)。
- Belle II 相当のブースト: Υ(4S) に pz ≈ +3 GeV(HER − LER)。C++ ドライバ内で設定済み。
- 単位は GeV(natural units)。m²_miss は GeV²。
- form factor: v1 は ISGW2。BGL/CLN へ更新する際は dec ファイルと README を同時に更新。
- 乱数 seed はコマンドライン引数で固定し、再現性を保つ。

## コード規約

- 生成物(data/*.hepmc, plots/*.png)はコミットしない(.gitignore 済み)。ただし報告用の最終プロットは docs/figures/ にコピーしてよい。
- dec ファイルを追加したら README の生成コマンド一覧を更新。
- Python は pyhepmc + numpy + matplotlib。ROOT は使わない(学生の環境依存を減らすため)。

## 学生対応

- 説明は日本語または英語(学生に合わせる)。物理の説明は学部レベルで、ヘリシティ抑制や missing mass の直感を式より先に。
