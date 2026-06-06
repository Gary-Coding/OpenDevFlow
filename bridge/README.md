# @opendevflow/bridge

OpenDevFlow Bridge 用于把用户本机代码上下文和本地命令执行能力接入 OpenDevFlow 平台。

Bridge 会在本机运行，扫描指定代码根目录下的项目结构，生成代码上下文快照并上传到平台。后续平台下发的构建、测试、Git 等命令也会由 Bridge 在用户本机执行。

Bridge 是一个本地长连接进程。启动后需要保持终端窗口运行；关闭终端窗口后，平台将无法继续扫描代码上下文或执行本地命令。

## 使用方式

```bash
npx --registry https://registry.npmjs.org/ @opendevflow/bridge --server http://localhost:8765 --client-key <客户端标识> --root <本地代码根目录>
```

示例：

```bash
npx --registry https://registry.npmjs.org/ @opendevflow/bridge --server http://localhost:8765 --client-key muke-mac --root /Users/muke/projects
```

## 参数

- `--server`：OpenDevFlow 后端地址，默认 `http://localhost:8765`。
- `--client-key`：平台中登记的 Bridge 客户端标识，也可以使用环境变量 `OPENDEVFLOW_CLIENT_KEY`。
- `--root`：本地代码根目录，默认当前目录，也可以使用环境变量 `OPENDEVFLOW_ROOT`。
- `--help`：查看帮助。

## 安全说明

- Bridge 只上传项目结构、Git 状态和构建标记摘要，不上传完整源码。
- 本地命令执行前会进行基础危险命令拦截。
- 当前版本是 MVP，后续建议增加客户端密钥、命令白名单、本地二次确认和更完整的审计能力。
