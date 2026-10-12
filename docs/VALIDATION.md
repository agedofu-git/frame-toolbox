# v0.1 検証記録

検証環境はWindows x64、Python 3.14.3、PySide6-Essentials / Shiboken 6.11.2、pytest 9.1.1です。Qtのoffscreen pluginを使用しました。Windowsのoffscreenでフォントを列挙できないため、検証スクリプトとfixtureだけがシステムの既存Segoe UIを読み込みます。フォントは本プロジェクトへ再配布していません。

初回の結果はpytest **71 passed**、Ruff **All checks passed**です。全6タブのPNGとMock診断ZIPを生成し、画面のテキスト表示も確認しました。2026-10-12の配布機能追加後は、インストーラーの検証を含めWindowsで **75 passed**、Ruff **All checks passed**を確認しています。

確認対象:

- Linux情報源を一時ディレクトリやFakeRunnerへ差し替えた各サービス。
- コマンド成功・欠落・timeout・不正引数・shellメタ文字のリテラル処理。
- OS / IP / nmcli / iw / process / OpenXR / audio解析と情報不足。
- 原子的な設定保存、不正設定の保持、IPと閾値の検証。
- レポートとZIP、JSONを壊さない秘匿化、journalのopt-inと収集制限。
- 通常ログレベル、ログ回転、プログラム先頭の責務コメント。
- 全6画面、設定・Refresh・Collectの操作、再起動の確認ダイアログ。
- 遅いバックエンド中のGUIタイマー応答、重複操作防止、処理中の終了。
- CLIのGUI起動経路、headless表示、Mock診断ZIP生成。
- wheel / sdistのビルドと、wheel内コードからのMock診断ZIP生成。

```bash
python -m pytest -q
ruff check .
python scripts/smoke_ui.py
python -m build --no-isolation
```

GitHub Actions設定は用意していますが、このローカル作業ではGitHub上のCIを実行していません。

実機で確認する項目はPython / glibc / wheel / Qt platform pluginの互換性、各ツールの有無とユーザー権限、default routeとDNSの取得、バッテリー選択、実際のVRプロセス名、OpenXR manifest、音声デバイス、ping許可とGUIの表示・応答です。正式なSteamVR再起動方法が確認できるまで通常モードの再起動は無効です。

## Steam Frame実機検証（2026-10-05 JST）

SSHで実機へ接続し、`steamos`ユーザーの専用テストディレクトリとvenv内で実行しました。root権限、OS設定変更、root filesystemの書き換えは行っていません。

| 項目 | 確認した実機 |
| --- | --- |
| OS | SteamOS 0.4.3 / BUILD_ID 20260930.6234839 / VARIANT_ID vr |
| CPU | aarch64 |
| Kernel | 6.18.0-ge66bc2ca6f8c |
| Python / glibc | 3.12.3 / 2.39 |
| Qt binding | PySide6-Essentials / Shiboken 6.11.2、manylinux_2_39_aarch64 wheel |
| 表示 | X11、実機セッションのDISPLAY=:0、QT_QPA_PLATFORM=xcb |
| 音声サーバー | PulseAudio互換 / PipeWire 1.6.8 |

結果:

- 実機上のpytest: **71 passed in 1.95s**。Qtテストのskipなし。
- 実機の通常GUIでOverview / Network / VR / Audio / Diagnostics / Settingsの6画面を表示・PNG保存・画像確認。検証終了時にツールのウィンドウを閉じました。
- OS、uptime、メモリ、root filesystem使用量、バッテリー、充電状態を取得。初回のBatteryは98% / Discharging。
- Wi-Fi、gateway、DNS、SSID、信号、周波数、channel、TX bitrateを取得。5 GHz / 5180 MHz / channel 36、信号-38 dBm、TX bitrate 1080.6 Mbpsは初回観測値で、固定の仕様ではありません。
- gatewayと同一LAN上のテストPCへのpingが成功。PCの初回latencyは4.239 ms。単発測定であり、継続的な品質を保証しません。
- steam / vrserver / vrcompositorを検出。vrmonitorはNot detected。OpenXR manifestからSteamVRを検出。
- Built-in Audio Playback / Capture、mic mute、設定volumeを取得。録音は行っていません。
- 隔離した設定ファイルの保存・読み込み、debugを含む設定検証が成功。
- 実機値で診断ZIP生成。ZIP整合性OK、summaryのmock=false / errors=[]、ZIPの権限0600を確認。選択した関連user journalは200行でした。
- 子プロセス内だけPATHを空にした実機テストで、コマンド不足時にnetwork UNKNOWN / process Unavailableを返し、アプリのクラッシュなし。
- 検証後もsteam / vrserver / vrcompositorが稼働していることを確認。

証拠となるPNG、live-status.jsonと診断ZIPはローカル作業用の`artifacts/steam-frame-20261005/`へ回収しました。このディレクトリはGit管理から除外されており、IPやSSIDを含む実機レポートは公開パッケージへ含めません。

再実行する画面検証の例（DISPLAYは実際のセッションで確認する）:

```bash
DISPLAY=:0 QT_QPA_PLATFORM=xcb python scripts/smoke_ui.py --live --pc-ip 192.168.1.20 --output-dir artifacts/live-ui
python -m pytest -q
```

今回の1台・OS版・表示セッションでの確認です。SteamOSアップデート耐性、実機のSteamVR再起動、リアルタイムマイク入力level、VR Overlayは未検証・未実装のままです。

## オフライン導入ZIPの実機検証（2026-10-12 JST）

- PySide6-Essentials / Shiboken 6.11.2のARM64 wheelとアプリwheelを含む約78.5 MBの配布ZIPを作成し、ZIP整合性と全同梱ファイルのSHA-256を検証しました。
- Steam FrameへZIPを転送し、`python3 install.py --desktop`を通常ユーザーで実行。`--no-index --only-binary=:all:`により外部パッケージサービスを使わず専用venvへ導入できました。
- `pip check`、Qt Widgetsとアプリのimportが成功。ユーザーのアプリメニュー登録とデスクトップショートカットを確認しました。
- インストールした`~/.local/bin/frame-toolbox`から通常モードの状態取得が成功。
- 新しくインストールしたvenvとwheelのコードから、X11の実機値GUIで全6タブを表示・PNG保存・正常終了しました。
- root権限、OSパッケージ、SteamVRプロセスへの操作は行っていません。既存のテスト環境は保持しています。

この追加検証はインストール経路・ランチャー・GUIが対象です。実機上の71件のpytestは2026-10-05の記録であり、今回の75件はWindows上の記録です。
