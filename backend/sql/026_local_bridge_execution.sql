-- 本地 Bridge 命令执行日志。

ALTER TABLE local_bridge_commands
  ADD COLUMN IF NOT EXISTS logs TEXT;
