# cpp_parser 运行说明补充

可通过以下环境变量控制数据库连接模式与调试日志：

- DP_DB_PER_THREAD
  - 值："1"/"true"/"yes" 开启每线程一连接；"0"/"false"/"no" 使用单连接模式。
  - 默认：开启（每线程一连接）。
  - 作用：在高并发时减少锁竞争；若需要灰度或排查问题，可切换为单连接模式。

- DP_DB_DEBUG
  - 值："1"/"true"/"yes" 开启 DB 调试日志；其他值关闭。
  - 默认：关闭。
  - 作用：打印连接建立与关键查询的调试信息，便于定位问题。

在 Windows PowerShell 下运行时，可临时设置环境变量后启动程序：

```powershell
$env:DP_DB_PER_THREAD = "1"; $env:DP_DB_DEBUG = "0"; ./build/bin/cpp_parser -c config/parser_config.json --threads 1&
```

若使用 Linux shell：

```bash
DP_DB_PER_THREAD=1 DP_DB_DEBUG=0 
./build/bin/cpp_parser -c config/parser_config.json --threads 1&
```

注意：开启调试日志会增加输出，请仅在需要时打开。