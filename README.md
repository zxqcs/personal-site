# 公开思考空间

这是一个以独立 Obsidian PublicVault 为唯一内容源、以 Quartz 5 生成静态网站、并通过 GitHub Actions 发布到 GitHub Pages 的本地项目。

先阅读 [ARCHITECTURE.md](ARCHITECTURE.md)、[SECURITY.md](SECURITY.md) 和 [PUBLISHING.md](PUBLISHING.md)。日常入口是：

```bash
python3 scripts/publish.py --dry-run
```

不要在 `content/` 中编辑文章，不要把任何 Private Vault 配置到本项目。

Quartz 上游：<https://github.com/jackyzha0/quartz/tree/v5>
