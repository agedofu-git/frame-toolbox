# Steam Frameへの簡単インストール

1. SteamOSのデスクトップで[最新版のダウンロードページ](https://github.com/agedofu-git/frame-toolbox/releases/latest)を開き、`frame-toolbox-0.1.0-steamos-arm64.zip`をダウンロードします。
2. ファイルマネージャーでZIPをユーザーフォルダーへ展開し、展開した`frame-toolbox-0.1.0`フォルダーで端末を開きます。
3. 次のコマンドを1回実行します。

```bash
python3 install.py --desktop
```

終了後、アプリメニューの **Frame Toolbox** から起動できます。デスクトップの場所が取得できればショートカットも作成します。KDEが確認を表示した場合は、内容を確認してショートカットの起動を許可してください。ゲームモードやVR空間のオーバーレイではなく、通常のデスクトップGUIです。

このZIPにはアプリwheel、検証したPySide6-Essentials 6.11.2とShiboken 6.11.2のARM64 wheel、ライセンス、チェックサムを含みます。ZIPダウンロード後の導入はオフラインです。sudo、OSパッケージの更新、SteamOSのroot filesystemの変更は行いません。

対象はARM64 Linux、Python 3.10以上、glibc 2.39以上です。Steam FrameのSteamOS 0.4.3 / Python 3.12.3 / glibc 2.39でアプリを検証しました。他のOS版ではQtのディスプレイ用ライブラリやvenvが利用できない場合があります。適合しない場合はインストールを停止します。システム環境を変更して回避する処理はありません。

インストール先は`~/.local/share/frame-toolbox/installs/`、起動ファイルは`~/.local/bin/frame-toolbox`、アプリメニュー登録は`$XDG_DATA_HOME/applications/frame-toolbox.desktop`（既定`~/.local/share/applications/`）です。更新は同じ手順です。新しい専用venvで導入が成功した後にランチャーを切り替え、前の環境は保持します。失敗時に作られたフォルダーも、確認できるよう保持します。

端末から起動する場合:

```bash
~/.local/bin/frame-toolbox
~/.local/bin/frame-toolbox --mock
~/.local/bin/frame-toolbox --headless
```

削除する場合はアプリを閉じ、上記の専用インストールフォルダー、起動ファイル、メニューとデスクトップのショートカットだけを削除してください。設定`~/.config/frame-toolbox/`とログ・診断`~/.local/state/frame-toolbox/`は別で、引き継ぎに利用できます。

チェックサムは破損確認用で、署名ではありません。[GitHubリリース](https://github.com/agedofu-git/frame-toolbox/releases/latest)の配布物を使用してください。詳細・制限・診断レポートの個人情報は[プロジェクトREADME](https://github.com/agedofu-git/frame-toolbox#readme)を参照してください。
