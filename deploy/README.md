# XXX 管理系统 — 独立部署指南

从 ExcelToWeb **母系统** fork 出定制品（三业务模块：巡检 / 客诉 / 抽检），并 Docker 部署到他人电脑。

---

## 架构说明

| 组件 | 说明 |
|------|------|
| **母系统 (ExcelToWeb)** | 继续上传 Excel、试验 AI、多项目平台 |
| **新产品 (XXX管理系统)** | 独立 git 仓库 + 独立 MySQL + 固定 3 模块 |
| **数据** | `sheet_data.row_data` JSON 行存储，无需拆表 |

产品模式通过环境变量 `APP_MODE=product` + `product.modules.json` 启用。

---

## 第一步：在母系统导出三个项目

1. 查看当前项目 wid：

```powershell
cd E:\JMCL_WORK\2026_09_01\ExcelToWeb\backend
conda activate excel-to-web
python view_db.py
```

记下三个项目的 `project_id`（12 位 hex）。

2. 导出 bundle：

```powershell
python scripts/export_bundle.py --wids wid1,wid2,wid3 -o ..\deploy\data\bundle.json
```

3. 更新 `deploy/product.modules.json`，把三个 `project_id` 填进去（**必须与 bundle 里一致**）。

---

## 第二步：Fork 独立 git 仓库

```powershell
# 在母系统目录
cd E:\JMCL_WORK\2026_09_01
git clone ExcelToWeb XXX管理系统
cd XXX管理系统

# 可选：删除 git 历史，全新仓库
# Remove-Item -Recurse -Force .git
# git init
```

在新仓库根目录创建 `product.modules.json`（可从 `deploy/product.modules.json` 复制到根目录，本地开发用）：

```powershell
Copy-Item deploy\product.modules.json product.modules.json
```

---

## 第三步 A：本地开发（产品模式）

`backend/.env` 增加：

```env
APP_MODE=product
SYSTEM_NAME=XXX管理系统
SYSTEM_SUBTITLE=产线巡检 · 客诉跟进 · 产品抽检
ALLOW_UPLOAD=false
ALLOW_REGISTER=false
ENABLE_AI=false
PRODUCT_MODULES_FILE=../product.modules.json
```

导入数据（新库或空库）：

```powershell
cd backend
python scripts/import_bundle.py ..\deploy\data\bundle.json
python seed.py
```

启动（与母系统相同）：

```powershell
cd ..
.\start.ps1
```

登录后应看到 **三模块首页**，而非项目列表。

---

## 第三步 B：Docker 部署（给他人电脑）

**前提：** 已安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)。

1. 准备文件（在 fork 后的仓库 `deploy/` 目录）：

```
deploy/
  .env                    ← 从 .env.example 复制并修改密码
  product.modules.json    ← 填好三个 wid
  data/bundle.json        ← 母系统导出的数据包
```

2. 启动：

```powershell
cd deploy
Copy-Item .env.example .env
# 编辑 .env、product.modules.json

docker compose up -d --build
```

3. 浏览器打开：`http://localhost:8080`

4. 默认账号：`admin` / `admin123`（首次登录后请改密码）

5. 停止：

```powershell
docker compose down
```

**数据持久化：** MySQL 数据在 Docker volume `mysql_data`。备份可：

```powershell
docker compose exec mysql mysqldump -uroot -p$env:DB_PASSWORD xxx_management > backup.sql
```

---

## 权限说明

- **超级管理员** (`super_admin`)：用户管理 + 三模块全部访问 + 项目设置
- **模块级权限**：在「项目设置」为每个模块分配 admin / entry / read
- 产品模式下普通用户 **不能上传/删除模块**（仅 super_admin 可删）

---

## 与母系统的关系

- 新产品 **独立数据库**，不会自动同步母系统后续改动
- 母系统继续开发新功能；需要时可 cherry-pick 提交到新仓库
- 需要刷新数据时：重新 `export_bundle.py` → `import_bundle.py --reset`（会清空目标库）

---

## 文件清单

| 文件 | 作用 |
|------|------|
| `backend/app/config.py` | 产品/平台模式配置 |
| `backend/scripts/export_bundle.py` | 导出项目数据包 |
| `backend/scripts/import_bundle.py` | 导入数据包 |
| `frontend/src/ModuleHome.vue` | 三模块首页 |
| `product.modules.json` | 模块定义（wid、名称） |
| `deploy/docker-compose.yml` | Docker 一键部署 |
