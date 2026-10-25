# 图书情报检索与统计平台｜网页公开演示版

基于 Python、Streamlit、Plotly 开发的课程实训 Web 界面。包含数据总览、图书管理、读者管理、借阅管理、统计分析和系统信息六个页面。

> 此仓库是**在线 Demo 展示版**，使用 `data/` 中的合成示例数据；可交互体验新增、编辑、借阅、归还等操作，但修改仅保存在浏览器对应的 Streamlit 会话中，刷新、重新连接或应用重启后可能恢复初始状态。**不连接 MongoDB，也不持久保存修改。**

## 用 Streamlit Community Cloud 发布成网页

1. 在 GitHub 新建一个仓库（例如 `library-intelligence-demo`）。
2. 将**本部署包解压后的文件**上传到仓库根目录：根目录应能直接看到 `web/`、`data/`、`python/`、`requirements.txt`、`README.md`。
3. 打开 https://share.streamlit.io/ ，登录并连接 GitHub。
4. 点击 **Create app** → **Yup, I have an app**；选择上述 GitHub 仓库和 `main` 分支。
5. 将 **Main file path / Entrypoint** 设置为 `web/app.py`，选择兼容 Python 版本（建议 3.12）。
6. 点击 **Deploy**。平台成功运行后会提供 `https://<你选择的子域名>.streamlit.app` 形式的网址。

不需要在云端设置 `.env` 或 MongoDB 账号。请**不要**将密码、`.env`、历史实训报告或含个人信息的原始数据上传到公开仓库。

## 本地运行

```bash
python -m pip install -r requirements.txt
python -m streamlit run web/app.py
```

## 页面与数据

- `web/app.py`：Streamlit 入口，固定在线 Demo 模式
- `web/views/`：六个功能页面
- `web/components/`：布局、图表和 UI
- `web/services/demo_repository.py`：演示数据读写（仅会话内存）
- `data/`：演示数据，含 20 种图书、16 位读者及 66 条初始借阅事件
- `python/`：完整项目中的辅助业务代码；在线演示版不执行 CLI

## 注意

本部署包**不是**替代原实训项目的完整 MongoDB 交付文件。用于课程验收时仍需提交原 MongoDB 脚本、报告和相应截图。

如需公开网站对 MongoDB 执行真实且持久的写入，需要另建安全的云数据库或部署云端数据库服务器，并实现账号权限与访问隔离，不能把本 Demo 的会话内存存储当作数据库。
