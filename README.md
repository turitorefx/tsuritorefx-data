# 釣りトレFX釣果MAP 更新データ専用リポジトリ

このリポジトリにはアプリ本体を置きません。公開されるのは更新用JSONと低頻度の更新スクリプトだけです。

## GitHubにアップロードするもの
- `version.json`
- `data/`
- `scripts/`
- `.github/workflows/update-data.yml`

## ローカルアプリ側の設定
GitHubでこのリポジトリを **Public** にし、例としてユーザー名が `wakai`、リポジトリ名が `tsuritorefx-data` の場合、RawベースURLは：

`https://raw.githubusercontent.com/wakai/tsuritorefx-data/main`

これをローカルアプリの「☁ 更新データ設定」に貼り付けます。

## 公開範囲
公開JSONには公開釣果・公開施設情報のみを保存します。ユーザー補正座標、個人釣果、写真、Firebase個人データは入れません。

## 注意
外部サイトのレイアウト変更やアクセス制限で自動取得が失敗することがあります。その場合も直前の正常データを残す設計です。各項目には出典URLを保持してください。
