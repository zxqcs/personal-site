# 发布指南

## 写作与发布的关系

在 Obsidian 中打开 `~/Documents/PublicVault`，所有公开文章都在这里编辑。它是文章的唯一原稿。网站工程位于本仓库；其中的 `content/` 是发布时生成的副本，不要直接编辑。

发布路径为：PublicVault → 安全检查与单向复制 → `content/` → GitHub 仓库 → GitHub Actions 运行 Quartz → GitHub Pages。

Private Vault 不属于这条路径，也不能填入发布配置。发布前仍需亲自检查文章是否适合公开；自动扫描只能拦截部分常见敏感内容。

## 首次准备

本项目使用 Node.js 24 和 npm 10.9.2 或更新版本。运行 `node --version`，应显示 `v24.x`。如果不是，请先用你安装的 Node 版本管理器切换到 24；发布脚本会阻止其他主版本。

如果当前终端只有 Node 25，也可以为单次命令临时使用 Node 24，无需改动系统默认版本。例如：

```bash
npm_config_cache=/tmp/personal-site-npm-cache npm exec --yes --package=node@24.21.0 -- sh -c 'python3 scripts/release.py --dry-run'
```

正式发布时，把末尾的 `--dry-run` 改为 `--release --push`。首次运行需要从 npm 下载 Node 24；之后会复用缓存。

从网站工程目录操作：

```bash
cd /path/to/personal-site
npm ci
```

将 `/path/to/personal-site` 换成网站工程在本机的实际路径。本机的 `config/publish.local.toml` 已指向 `~/Documents/PublicVault` 对应的绝对路径。这个文件被 Git 忽略，不会上传。换电脑时，复制 `config/publish.example.toml` 为 `config/publish.local.toml`，再填入新电脑上 PublicVault 的绝对路径。不要填 Private Vault。

GitHub 仓库、Pages 发布源和站点地址已经配置完成；日常发文无需重复设置。

## 每次发布

1. 在 PublicVault 中写好文章，检查标题、链接、图片和任何可能涉及隐私的内容。当前发布白名单包括根目录 `index.md`，以及 `about/`、`thoughts/`、`essays/`、`projects/`、`fiction/`、`assets/` 中允许类型的文件。
2. 在网站工程目录预览将新增、修改和删除的文件。这一步不改动文件或远端：

   ```bash
   python3 scripts/publish.py --dry-run
   ```

3. 核对预览后，复制到网站工程。脚本会再次询问；只有输入 `y` 才会更新 `content/` 和发布清单。此时还没有提交或上传：

   ```bash
   python3 scripts/publish.py --publish
   ```

4. 先运行完整发布检查，包括配置、安全扫描、自动化测试、依赖审计和 Quartz 构建。这一步不会提交或上传：

   ```bash
   python3 scripts/release.py --dry-run
   ```

5. 检查通过后发布。脚本先询问是否创建本地提交，再询问是否推送到公开仓库；推送后 GitHub Actions 自动部署网站：

   ```bash
   python3 scripts/release.py --release --push
   ```

如果预览显示没有变化，就不需要继续发布。如果在第二次确认时选择不推送，本地提交会保留；确认提交内容后，可用 `git push origin main` 完成推送。

## 上线验收

在 [GitHub Actions](https://github.com/zxqcs/personal-site/actions) 确认最新的构建和部署都成功，再打开 [网站首页](https://zxqcs.github.io/personal-site/)与新文章检查。必要时再核对搜索、WikiLink、RSS（`index.xml`）、站点地图（`sitemap.xml`）和不存在页面的 404 响应。GitHub Pages 更新可能有短暂缓存延迟。

若检查失败或部署失败，先看命令输出或对应的 Actions 日志。`config/publish.local.toml`、`.obsidian/`、Private Vault 文件和凭据都不应进入公开 Git 历史。

## 回滚已发布内容

先从 `git log --oneline` 找到确认正常的旧提交。回滚要求网站工程的 Git 工作区完全干净；先预览目标与当前发布副本的差异：

```bash
python3 scripts/rollback.py --to 旧提交ID
```

确认后执行：

```bash
python3 scripts/rollback.py --to 旧提交ID --apply --push
```

脚本会分别询问是否创建回滚提交、是否推送。它只恢复网站的 `content/` 和发布清单，随后由 GitHub Actions 重新部署；PublicVault 原稿不会改变，Git 历史也不会被改写。以后再次从 PublicVault 正常发布，会重新带入原稿中的最新内容。
