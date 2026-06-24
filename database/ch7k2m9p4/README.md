# Chronicle 静态搜索页 — 数据更新说明

隐蔽入口（勿公开链接）：

```
https://fengweidiezhen.com/database/ch7k2m9p4/
```

## 目录结构（遵循 格式.md）

```
database/ch7k2m9p4/
├── index.html           # 搜索界面
├── chronicle.js
├── id_list.json         # 用户列表
├── search-meta.json         # 轻量索引元数据（页面首先加载）
├── search-index/            # 按用户分片的索引
│   └── {user_id}.json
└── data/
    ├── records/{user_id}/{YYYY-MM-DD}.json
    └── summaries/{user_id}/{YYYY-MM-DD}.json
```

## 更新流程

1. 从 Chronicle 项目复制或导出 `id_list.json` 与 `data/` 到本目录
2. 在项目根目录运行：

   ```bash
   python scripts/build_chronicle_index.py
   ```

3. `git add` → `commit` → `push`，GitHub Pages 自动部署

## 注意事项

- 全站导航**未**链接此页；仅通过完整 URL 访问
- `robots.txt` 已禁止 `/database/` 爬取
- 页面含 `noindex`，降低被搜索引擎收录概率
- 公开 GitHub 仓库中数据文件可见；敏感内容勿上传
