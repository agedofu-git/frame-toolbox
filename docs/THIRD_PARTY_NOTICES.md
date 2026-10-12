# 同梱する第三者パッケージ

Frame Toolbox自体はMIT Licenseです。SteamOS ARM64用オフラインZIPには、PyPIから取得した以下のwheelを変更せず同梱します。

| パッケージ | バージョン | 配布元 |
| --- | --- | --- |
| PySide6-Essentials | 6.11.2 | https://pypi.org/project/PySide6-Essentials/6.11.2/ |
| Shiboken6 | 6.11.2 | https://pypi.org/project/shiboken6/6.11.2/ |

各wheel内に含まれるライセンス文書と著作権表示が適用されます。Qt / PySide6 / ShibokenはFrame ToolboxのMIT Licenseで再ライセンスされません。wheelはZIPとして開いて各ライセンス文書を確認でき、インストール後は専用venvのsite-packages内に残ります。Pythonの動的なbindingを利用し、Qt本体の改変や静的リンクを行いません。

プロジェクト: https://code.qt.io/cgit/pyside/pyside-setup.git/ 、https://www.qt.io/ 。ライセンス文書とソースへの案内も配布元を参照してください。
