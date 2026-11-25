# 安装指南 (INSTALL.md) — P032 AcceptTwin，T012

## 已验证的安装环境（实测）

| 项目 | 实测值 |
| --- | --- |
| 操作系统 | Linux（`Linux htch-runtime 7.0.0-44-generic x86_64`） |
| Python | 3.12.3 |
| Node.js | 24.22.1（独立 Oracle 与报告界面构建用） |
| npm | 10.9.4 |
| pytest | 9.2.0（dev 依赖） |
| TypeScript | 5.9.3（`report-ui`，已冻结于 `report-ui/package-lock.json`） |

其他操作系统、Python/Node 版本一律 `NOT_TESTED`（见 `docs/LIMITATIONS.md`）。

## 安装步骤

```bash
git clone <repo>              # 或解包源码
cd p032-accepttwin

python3.12 -m venv .venv
.venv/bin/python -m pip install -e .            # 生产包：零运行时依赖
.venv/bin/python -m pip install -e ".[dev]"     # 测试：pytest==9.2.0
```

`pip install -e .` 会按 `pyproject.toml` 安装可编辑包并注册
`accepttwin` 控制台命令（`accepttwin = "accepttwin.cli:main"`）。
不安装也可以运行：pytest 通过 `pyproject.toml` 的
`pythonpath = ["src"]` 直接用源码；`python -m accepttwin` 在已安装
包时无需额外 `PYTHONPATH`。

## 报告界面构建

```bash
cd report-ui
npm run build    # tsc -p tsconfig.json，用已冻结的 package-lock.json
```

构建只用本地 `report-ui/node_modules/` 中的 TypeScript 5.9.3，
不访问网络。`npm ci`（全新安装依赖）需要访问 npm registry，
**不是**离线步骤；离线复现只需已存在的 `node_modules/`（见
`docs/LIMITATIONS.md` 与 `evidence/Performance/OFFLINE_LOG.txt`）。

冻结重建路径（T014，T013-F03，见 `00_control/ADR-007.md` 决定 8）：
干净检出后 `npm run build` 会失败（`tsc: not found`，
`node_modules/` 未提交）；重建有两条路——(a) 能访问 registry 时
`npm ci`（`package-lock.json` 已锁定 TypeScript 5.9.3）再
`npm run build`；(b) 离线时复用已装 `node_modules/`（钉死 tsc
5.9.3）再 `npm run build`，T013 已验证该重建与已提交
`report-ui.js` 字节一致（SHA-256 `784e3106…`）。已提交的
`report-ui.js` 本身就是冻结产物；无法访问 registry 的干净检出
不能从零重建它，该限制如实记录，不隐藏。

## 离线安装说明

- 生产包 `accepttwin` 本身零运行时依赖（`pyproject.toml` 的
  `dependencies = []`），安装不需要网络下载任何运行库。
- 构建后端为 `setuptools>=69`：`pip install -e .` 默认用构建隔离，
  首次构建会从 PyPI 下载 setuptools；若构建机完全离线，需事先
  在环境中备好 `setuptools>=69` 再用
  `pip install --no-build-isolation --no-index -e .`
  （离线验证实录见 `evidence/Performance/OFFLINE_LOG.txt`）。
- 测试依赖只有 `pytest==9.2.0`（及传递依赖），须事先装好；
  离线时无法现场下载。
- 安装后验证：

```bash
.venv/bin/python -m accepttwin --help
.venv/bin/python -m accepttwin --version   # accepttwin 1.0.0
.venv/bin/python -m accepttwin demo        # 健康 + 故意串版，各跑一次并导出 HTML
.venv/bin/python -m pytest -q
```

`demo` 是最快的端到端自检：两次真实运行（各 8 个真实 HTTP
请求）+ 两次 Oracle 对账 + 两份正式报告 + 两页 HTML，全部在
`output/runs/demo-healthy/` 与 `output/runs/demo-bleed/`。运行
输出（`output/`）是生成文件，已加入 `.gitignore`，不提交。

## 常见问题

- `No module named accepttwin`：包未安装进当前 Python 环境。
  在仓库根目录执行 `.venv/bin/python -m pip install -e .`，
  或用 `PYTHONPATH=src .venv/bin/python -m accepttwin …` 临时运行。
- `node: command not found`：Oracle 对账与 `npm run build` 需要
  Node.js ≥ 24；只跑 Python 单元测试不需要 Node。
- 端口冲突：源站与代理均用 OS 分配的临时回环端口（`port=0`），
  不占用固定端口；报告哈希已把临时端口归一化为 0（ADR-003）。
