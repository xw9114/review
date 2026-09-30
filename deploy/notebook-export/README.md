# 日序内部导出接口

此目录包含知识系统所需的日序扩展。它只导出 `kind=note` 的文字笔记，并使用独立的
`NOTEBOOK_EXPORT_TOKEN` Bearer Token；不会复用网页管理员密码。

部署步骤由运维流程执行：

1. 将 `notebook_export.py` 复制到日序项目根目录。
2. 对日序的 `app.py`、`Dockerfile` 和 `tests/test_app.py` 应用对应补丁。
3. 在日序 `notebook.env` 添加 `NOTEBOOK_EXPORT_TOKEN=<随机值>`。
4. 在知识系统 `.env` 添加相同值到 `NOTEBOOK_API_TOKEN`，并设置 `NOTEBOOK_API_URL`。
5. 先构建并运行日序测试，再重建日序 web 容器和知识系统 backend/frontend。

接口：

```text
GET /internal/v1/entries?kind=note
Authorization: Bearer <token>
```

错误令牌返回 `401`；任何非 `note` 类型返回 `400`。
