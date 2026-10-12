# python -m frame_toolbox の起動入口。
# CLIの引数処理をmainへ委譲する。
from frame_toolbox.main import main

raise SystemExit(main())
