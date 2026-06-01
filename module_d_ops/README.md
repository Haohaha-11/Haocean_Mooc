# Module D Ops

模块 D 负责一键验收、联调入口和异常验证脚本。

## 常用命令

在项目根目录执行：

```bash
make test
```

运行 A/B/C 单模块测试。

```bash
make verify
```

启动模块 B 临时服务，执行模块 B smoke test，并用模块 A 完成一次真实 A -> B 提交流程。

## 覆盖范围

- 模块 A 单元测试
- 模块 B 单元测试
- 模块 C 单元测试
- 模块 B smoke test
- A 查询开放作业
- A 打包、MD5、上传到 B
- B pending 列表确认 A 的提交

当前模块 C 的 HTTP TUI 需要人工终端交互，自动脚本只覆盖其 HTTP 数据访问层单元测试。
