# qc-hub · 质控通管理系统

产线巡检 · 客诉跟进 · 产品抽检

| 项 | 值 |
|----|-----|
| 目录 | `E:\JMCL_WORK\2026_09_01\qc-hub` |
| 数据库 | MySQL `qc_hub` |
| 后端端口 | `8001` |
| 前端端口 | `8088`（局域网 `http://172.16.122.175:8088`） |

---

## CMD 启动（推荐）

**首次安装依赖：**

```cmd
cd /d E:\JMCL_WORK\2026_09_01\qc-hub
setup.bat
```

**日常启动：**

```cmd
cd /d E:\JMCL_WORK\2026_09_01\qc-hub
start.bat
```

本机或局域网浏览器打开 http://172.16.122.175:8088 ，登录 `admin` / `admin123`。本机也可以用 http://127.0.0.1:8088 。

---

## CMD 手动分窗启动

**窗口 1 — 后端：**

```cmd
cd /d E:\JMCL_WORK\2026_09_01\qc-hub\backend
call conda activate excel-to-web
set PYTHONUNBUFFERED=1
python -u -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

**窗口 2 — 前端：**

```cmd
cd /d E:\JMCL_WORK\2026_09_01\qc-hub\frontend
nvm use 20.19.0
set VITE_DEV_BACKEND=http://127.0.0.1:8001
npm run dev -- --host 0.0.0.0 --port 8088
```

---

## PowerShell 启动（可选）

```powershell
cd E:\JMCL_WORK\2026_09_01\qc-hub
.\start.ps1
```

---

## Docker 部署

见 [deploy/README.md](deploy/README.md)

---

## 说明

- 界面系统名称仍为 **质控通管理系统**
- 与母系统 `ExcelToWeb`（8000/5173）互不冲突
- 旧中文目录 `质控通管理系统` 可手动删除（若仍存在）
