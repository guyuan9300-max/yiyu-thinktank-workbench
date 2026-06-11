# PR4A DoD

`Attachment / Voice Skeleton` only closes when all five checks below are green.

| Check | Pass Condition |
| --- | --- |
| 旧上传失败可见 | 旧上传链失败项能在 health advanced diagnostics 中看到 pseudo-op |
| 可重试 | 支持单条重试和全部重试，失败原因可解释 |
| 录音原件可恢复 | 杀进程后录音原件仍能从 app 私有持久目录找回 |
| `local_id` 绑定稳定 | 本地 task 与本地 voice draft 在没有 `remote_id` 时也能稳定绑定 |
| `interactive` 不被堵塞 | 大文件失败或 transfer 堵塞时，任务完成、改期等交互链仍可立即响应 |
