# Frame Toolbox

SteamOS / Linuxの状態表示、簡単な診断、ログ収集を1つのデスクトップUIから行うオープンソースツールです。v0.1は読み取り中心で、Steam Frame実機（SteamOS 0.4.3 / ARM64）で状態取得、X11 GUI、診断ZIP生成と71件のテストを確認しています。未確認の機種固有コマンドやパスは実装していません。実機検証の詳細は[検証記録](docs/VALIDATION.md)を参照してください。

## 現在できること

- **Overview**: hostname、OS、SteamOSバージョン、kernel、CPU architecture、uptime、メモリ、ディスク、バッテリー、充電状態と主要な診断値。
- **Network**: default routeのインターフェース、Wi-Fi / Ethernet、IP、gateway、DNS、SSID、信号、周波数帯、channel、TX bitrate、Ethernet link speed、gateway / 設定したPCへのpingとlatency。
- **VR**: 設定可能なプロセス名の存在とPID、Linux OpenXR runtime manifestの検出。未検出は`Not detected`で表示。
- **Audio**: default input / output、音声サーバー、mic mute、設定されたmic volume。`pactl`から取得し、不足部分を`wpctl`で補完。
- **Diagnostics**: 新しい状態を取得し、限定した項目のディレクトリとZIPを作成。関連user journalは任意選択。
- **Settings**: PC IP、auto refresh、debug logging、プロセス名、診断閾値をユーザー領域へ保存。
- **Refresh**: Qt workerで取得し、GUIをブロックしない。取得中の重複操作を防止。
- **Mock Mode**: 実機コマンドを実行せず、Windows / Linuxで全6画面と設定、ZIP、再起動の確認UIを検証。

色だけに依存せず、`OK (GOOD)`、`WARNING`、`ERROR (BAD)`、`UNKNOWN`を表示します。情報がない場合は`Unknown` / `Unavailable`です。

## v0.1でできないこと

実機のSteamVR再起動は無効です。正式な方法が未確認のため、`RestartBackend`で抽象化したデフォルト実装は安全に失敗し、UIのボタンも無効にしています。Mock Modeでは確認後に操作をシミュレーションします。実機用バックエンドを追加する場合、実行計画の表示、確認、期限付き`CommandRunner`、結果とログの記録が必要です。

本体のreboot、kill、root取得、sudo、system configuration変更、root filesystemの書き換え、音声の自動修復は行いません。VR Overlay、PC Agent、プレイスペース保存、コントローラー設定も未実装です。

## 技術構成とGUIの選択

Python 3.10以上と**PySide6 / Qt Widgets**を使用します。Qtの公式Python binding、WindowsでのMock開発、Qtのworker / signal機構、将来の表示層の分離を重視して選択しました。Qt Widgetsは今回の通常GUIに適しており、QMLやブラウザーを必要としません。`PySide6-Essentials`だけを依存に指定し、Qt Addonsの導入を避けています。バックエンドはPython標準ライブラリだけで利用できます。

2026-10-05の実機検証ではPython 3.12.3 / glibc 2.39で、PySide6-Essentials 6.11.2の`manylinux_2_39_aarch64` wheelをユーザー領域のvenvへ導入できました。別のOS版ではPython ABI、CPU architecture、glibc、Qt platform pluginとディスプレイ環境の適合を確認してください。依存のソースビルドを実機で自動開始しないよう、以下ではbinary wheelのみに限定します。PySide6のライセンスは本ツールのMIT Licenseとは別で、再配布時はQt / PySide6 / Shibokenのライセンス条件も確認してください。

参照: [Qt for Pythonの導入](https://doc.qt.io/qtforpython-6/gettingstarted.html)、[パッケージ構成](https://doc.qt.io/qtforpython-6/gettingstarted/package_details.html)、[Qt for Linux](https://doc.qt.io/qtforpython-6/overviews/qtdoc-linux.html)。

## Installation

**Steam Frameでの簡単導入:** [最新版のリリース](https://github.com/agedofu-git/frame-toolbox/releases/latest)から`frame-toolbox-0.1.0-steamos-arm64.zip`をダウンロードして展開し、そのフォルダーで`python3 install.py --desktop`を実行してください。検証済みのARM64用Qt依存を同梱し、ZIP取得後はオフラインでユーザー領域へ導入できます。以降はアプリメニューの **Frame Toolbox** から起動します。[詳しい導入・更新・削除手順](docs/INSTALL_STEAM_FRAME.md)と[第三者パッケージの案内](docs/THIRD_PARTY_NOTICES.md)を参照してください。

以下はソースからの開発用導入手順です。

プロジェクトをユーザーディレクトリへ配置してください。既にPythonとvenvが利用できるLinux環境で実行します。root filesystemのロック解除やsystem packageの更新は必要ありません。

```bash
cd ~/frame-toolbox
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --only-binary=:all: -r requirements.txt
python -m pip install --no-deps -e .
python -m frame_toolbox
```

利用可能なbinary wheelがない場合はインストールを止め、対象のPython / glibcに適合するPySide6バージョンやユーザー領域の配布方式を検討してください。root filesystemを変更して依存を揃える手順は提供しません。wheelにQt本体が含まれていても、Linuxのディスプレイ関連ライブラリまで全て提供されるとは限りません。

wheel / sdistを利用する場合:

```bash
python -m pip install --only-binary=:all: -r requirements.txt
python -m pip install --no-deps ./dist/frame_toolbox-0.1.0-py3-none-any.whl
frame-toolbox
```

`ip`、`iw`、`nmcli`、`ping`、`ps`、`pactl`、`wpctl`、`journalctl`は任意の外部ツールです。存在や権限を確認し、失敗は取得不能として扱います。不足したツールをアプリが自動インストールすることはありません。

## Development setup

Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m frame_toolbox --mock
python -m pytest -q
ruff check .
python -m build
```

Windows PowerShell:

```powershell
cd frame-toolbox
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m frame_toolbox --mock
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
```

GUIテストはQtのoffscreen pluginを使います。GUI依存がない環境ではサービスのテストを実行し、GUIテストはskipされます。全UIを検証するには開発依存を導入してください。

## Mock Mode

```bash
python -m frame_toolbox --mock
```

6 GHz、-48 dBm、1921 Mbps、Battery 72%、VRプロセスRunningを表示します。SteamOSバージョンとkernelのmock文字列は実機仕様を表しません。PC IPを設定するとmockのlatencyを表示します。Mock Modeではjournalを選択しても実行しません。設定とアプリログ、レポートの保存は行います。

環境を分けたい場合:

```bash
python -m frame_toolbox --mock --config-dir ./artifacts/config --state-dir ./artifacts/state
python -m frame_toolbox --mock --headless --config-dir ./artifacts/config --state-dir ./artifacts/state
python -m frame_toolbox --mock --collect --output-dir ./artifacts/reports --state-dir ./artifacts/state
python scripts/smoke_ui.py --output-dir ./artifacts/ui
```

最後のコマンドは全6画面をPNGとして保存し、終了します。

Linux実機の値で画面を検証する場合は`--live`を指定できます。`--pc-ip`は任意です。

```bash
python scripts/smoke_ui.py --live --pc-ip 192.168.1.20 --output-dir ./artifacts/live-ui
```

検証スクリプトは既定でoffscreen描画です。実機のX11画面へ表示する場合は、そのセッションで確認した`DISPLAY`を使い、`QT_QPA_PLATFORM=xcb`を指定してください。今回の実機では`DISPLAY=:0`で確認しました。この値を全Steam Frameの仕様として仮定しません。

## Steam Frameでの起動方法

実機でPythonと依存が利用可能か確認し、上記Installationでユーザー領域へ導入した後、通常のSteamOSデスクトップセッションから起動してください。

```bash
cd ~/frame-toolbox
source .venv/bin/activate
python -m frame_toolbox
```

Python / glibc / platform pluginの確認例:

```bash
python3 --version
uname -m
ldd --version
python -m pip debug --verbose
```

GUIが起動できない環境でも、標準ライブラリだけの状態取得や収集を利用できます。

```bash
python3 -m frame_toolbox --headless
python3 -m frame_toolbox --collect
python3 -m frame_toolbox --collect --include-journal
```

Linux以外の通常モードはエラーで終了し、`--mock`の利用を案内します。

## 設定とログ

標準保存先:

| データ | 保存先 |
| --- | --- |
| 設定 | `~/.config/frame-toolbox/config.json` |
| アプリログ | `~/.local/state/frame-toolbox/toolbox.log` |
| レポート | `~/.local/state/frame-toolbox/reports/` |

絶対パスの`XDG_CONFIG_HOME` / `XDG_STATE_HOME`にも対応します。`--config-dir` / `--state-dir` / `--output-dir`で上書きできます。レポート保存先はDiagnostics画面でも選択できます。Linuxでは新しく作るアプリ専用ディレクトリに0700、設定・レポート・ZIP・現在のログに0600を使用します。既存の親ディレクトリの権限は変更しません。WindowsではユーザーディレクトリのACLを継承します。

PC IPはIPv4 / IPv6のunicast IPとして検証し、shellへ渡しません。hostnameとscoped IPv6のPC設定はv0.1では非対応です。IPv6のlink-local gatewayはインターフェースを指定してpingします。Auto refreshは0で無効、5–3600秒です。無効なJSONや設定値は元ファイルを保持し、警告とデフォルト設定で起動します。保存は一時ファイルと原子的な置換を使います。

閾値の初期値は-75 dBm未満、NetworkManagerの信号割合30%未満、Wi-Fi TX bitrate 50 Mbps未満です。汎用的な目安であり、Steam Frameの最適値を示すものではありません。

アプリログはINFO / WARNING / ERROR、設定時のみDEBUGを使用します。256 KBで回転し、バックアップ2件を保持します。コマンドの生出力・環境変数・プロセスの実行引数はログへ記録しません。

## Diagnostics reportに含まれる情報

`frame-toolbox-report-YYYYMMDD-HHMMSS/`と同名のZIPを作成します。同一時刻に重複した場合は数値suffixを付けて既存レポートを保持します。

| ファイル | 内容 |
| --- | --- |
| `system.txt` | OS、kernel、uptime、architecture、使用量、バッテリー、hostname |
| `network.txt` | default interface、IP、DNS、gateway、Wi-Fi情報、ping、警告 |
| `processes.txt` | 設定したプロセス名とPID、OpenXR選択manifestとruntime名 |
| `audio.txt` | 音声サーバー、input / output、mute、設定音量 |
| `toolbox.log` | 現在のアプリログ末尾、最大128 KB |
| `summary.json` | schema version、アプリversion、取得時刻、Mock表示、全ステータス |
| `related-journal.txt` | 任意選択時のみ。現在bootの関連user journal、最大200行・128 KB |

テキストファイルもJSON形式で、未取得の値は`null`です。全インターフェース・全routing tableの生出力は収集しません。default routeを選択したインターフェースの解析値に絞ります。

journalは`--user --boot=0 --lines 200 --grep`でSteam / VR / NetworkManager / Wi-Fi関連に限定します。システムjournalの権限取得は行わないため、Wi-Fiのログなどがuser journalに存在しない場合があります。全boot、全journal、Steamの不明なログディレクトリを探索する収集はしません。

## Privacy considerations

レポートにはIPアドレス、SSID、hostname、デバイス名、PID、OpenXR manifestのパスが含まれます。パスにユーザー名が含まれる場合もあります。レポートはローカルに保存し、自動アップロードや送信は行いません。

SSH private key、browser cookies、passwordファイル、authentication tokenを探索・収集しません。ホーム全体の走査、プロセスcommand lineの取得、設定JSONのレポートへのコピーも行いません。OpenXRは標準のJSON manifestの選択情報だけを読み、runtimeライブラリをロードしません。

任意のjournalには想定外の個人情報が含まれる可能性があります。一般的なpassword / token / secret / cookie / Authorizationや秘密鍵のテキストパターンは秘匿化しますが、未知の書式や自由文を完全に除去する保証はありません。journalは既定で無効です。共有前に展開されたレポートを確認してください。

## Project structure

```text
frame-toolbox/
├── README.md, LICENSE, pyproject.toml, requirements.txt
├── frame_toolbox/
│   ├── __main__.py, main.py, config.py
│   ├── models/status.py          # Qt非依存の共通Snapshot
│   ├── utils/                   # コマンド実行、限定ファイルI/O、ログ
│   ├── services/                # System / Network / VR / Audio / Diagnostics / Restart
│   ├── backends/                # StatusBackend、LinuxBackend、MockBackend
│   └── ui/                      # MainWindow、Worker、表示整形、widgets
├── tests/                       # 実機I/Oを置換したpytestとQtテスト
└── scripts/smoke_ui.py           # 全6タブの起動検証とPNG保存
```

UIコードにはsubprocessを置きません。`StatusBackend`、`RestartBackend`、`ReachabilityProbe`が差し替え境界です。過剰なplugin APIやPC Agentプロトコルは導入していません。全てのPythonファイルの先頭に責務・役割コメントを置きます。

## Known limitations

- Steam FrameのSteamOS 0.4.3 / ARM64実機で検証済みです。SteamOSアップデート前後、別OS版、別の表示セッションでは未検証です。一般的なLinux情報源を使う設計であり、全環境の情報取得を保証しません。
- Linuxサービスは標準のproc/sys、NetworkManager、iproute2、iwなどが利用できる範囲を取得します。旧バージョンのJSON出力非対応や権限不足は取得不能です。
- 多数のバッテリーがある場合は本体用を推測で選びません。バッテリー情報はUnavailableになります。
- default routeのmetricが最小のインターフェースを選び、IPv4がなければIPv6を調べます。VPN・policy routing・複数経路の厳密な分析は未対応です。
- NetworkManagerの信号割合をdBmへ換算しません。AP advertised rateとiwのTX link bitrateは分けて表示します。TX bitrateは実際の転送速度やVRストリームbitrateを表しません。
- gateway無応答はERROR (BAD)ですが、ICMPフィルタリングでも起きます。PCのpingもfirewallで拒否される場合があります。情報不足はUNKNOWNです。
- OpenXRはmanifestに設定されたruntimeを表示するだけで、ロード成功やアクティブセッションは検証しません。探索順は`XR_RUNTIME_JSON`、XDG user / system設定、`/etc`で、architecture別JSONを優先します。
- プロセスの存在はSteamVRの正常動作を証明しません。`ps comm`は環境によって長い名前を短縮する場合があります。プロセス名はSettingsで変更できます。
- mic volumeは設定gainで、リアルタイム入力levelはUnavailableです。マイクの録音や権限要求は行いません。
- 取得の間隔はSnapshot全体で完全に同時ではありません。閉じる操作は進行中の期限付き処理が終わるまで待ち、スレッドを強制停止しません。
- 再起動の実機実装とFlatpakは未対応です。ARM64配布ZIPは専用venv方式で、Qtのディスプレイ関連system libraryまでは同梱しません。root filesystemを変更しない方針は維持します。

参照: [NetworkManager nmcli](https://www.networkmanager.dev/docs/api/latest/nmcli.html)、[OpenXR loader runtime discovery](https://registry.khronos.org/OpenXR/specs/1.1/loader.html)、[WirePlumber wpctl](https://pipewire.pages.freedesktop.org/wireplumber/man/wpctl.html)。

## Tests / 検証

```bash
python -m pytest -q
ruff check .
python scripts/smoke_ui.py
python -m frame_toolbox --mock --collect --output-dir ./artifacts/reports --state-dir ./artifacts/state
```

コマンド成功 / 欠落 / timeout、shellメタ文字の扱い、OS / ip / iw / nmcli解析、情報不足、process detection、audio fallback、設定load / save、ZIP生成と秘匿化、障害分離、GUI操作とイベントループの応答性を検証します。Qtなしの場合のskipを全UI検証成功とは扱わないでください。

## 配布ZIPの作成

開発環境で次を実行します。ARM64依存の取得は配布を作る側だけで必要です。

```bash
python -m build
python -m pip download --only-binary=:all: --platform manylinux_2_39_aarch64 --python-version 312 --implementation cp --abi cp312 --dest artifacts/wheelhouse-arm64 'PySide6-Essentials==6.11.2'
python scripts/package_release.py
```

`dist/`に公開ソースZIP、SteamOS ARM64オフラインZIP、wheel、sdistと`SHA256SUMS`を生成します。公開ソースは`docs/FILES.md`の許可リストに限定し、実機診断、設定、秘密鍵、仮想環境は含めません。オフラインZIPには未改変のQt依存wheelと各wheel内のライセンス文書を含めます。チェックサムは破損確認用で、署名ではありません。

## Roadmap

v0.2候補は、実機から確認した情報源のadapter、配布の対応OS拡大と更新UI、正式な安全なSteamVR再起動バックエンド、診断の詳細とプライバシー選択です。

以降にFrame Overlay、WebSocket PC Agent、Playspace Profiles、Audio Doctor、Input Manager、必要な範囲のPlugin Systemを検討します。共通モデルとサービスを再利用し、UIや機種固有処理の変更が診断全体へ波及しない構成を維持します。

## License

Frame Toolboxは[MIT License](LICENSE)です。依存ライブラリのライセンスは各配布元を参照してください。Valveの公式ツールではありません。
