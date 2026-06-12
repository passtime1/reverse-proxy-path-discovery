# Reverse Proxy Path Discovery

基于搜索引擎 `site:` 语法的反向代理隐藏路径自动发现工具

## 📖 项目简介

本项目用于解决以下安全测试场景：

> **问题**: 访问 `http://xxx.com/` 返回 403/503 错误，看似无业务功能
> **实际**: 该站点配置了反向代理，通过二级路径 `/abc/`、`/bbb/` 映射到不同后端系统
> **目标**: 自动发现这些被搜索引擎收录的隐藏路径

## 🎯 核心思想

```
传统扫描                本项目方法
    │                       │
    ▼                       ▼
┌─────────┐           ┌─────────────┐
│ Fuzz    │           │ site:xxx.com │
│ /admin  │           │ 获取收录URL │
│ /api    │           └──────┬──────┘
│ ...     │                  │
└─────────┘                  ▼
                        ┌──────────┐
                        │ 提取      │
                        │ /abc/    │
                        │ /bbb/    │
                        └──────────┘
```

**优势**: 不依赖字典爆破，利用搜索引擎已收录的真实路径，发现未知系统

## 🏗️ 项目结构

```
reverse-proxy-path-discovery/
├── skill.yaml              # Skill 定义文件
├── proxy_detector.py       # 反向代理检测脚本 ⭐
├── path_analyzer.py        # 路径分析脚本 ⭐
├── README.md               # 本文件
└── .gitignore              # Git 忽略文件
```

## 🔧 核心组件

### 1. proxy_detector.py - 代理检测器

**功能**: 识别目标是否为反向代理服务器

**检测特征**:
- Server 头 (`nginx`, `apache`)
- CDN 标识 (`CF-Ray`, `cloudflare`)
- 代理头 (`Via`, `X-Forwarded-*`, `X-Cache`)
- 错误页面特征 (403/503 + Nginx 默认页面)

**输出示例**:
```json
{
  "domain": "xxx.com",
  "proxy_type": "Nginx",
  "root_status": 403,
  "is_path_mapped": true,
  "evidence": ["Server: nginx/1.18.0", "根路径403"]
}
```

### 2. path_analyzer.py - 路径分析器

**功能**: 从 URL 列表提取二级路径并分类

**分析能力**:
- 提取二级路径 (`/abc/`, `/bbb/`)
- 统计路径出现频率
- 自动分类系统类型
- 标注优先级

**输出示例**:
```json
{
  "path_mappings": [
    {
      "path": "/admin/",
      "frequency": 45,
      "system_type": "管理系统",
      "priority": "高",
      "stars": "⭐⭐⭐"
    },
    {
      "path": "/api/",
      "frequency": 120,
      "system_type": "API接口",
      "priority": "高",
      "stars": "⭐⭐"
    }
  ]
}
```

## 🚀 使用方法

### 方式一：Skill 调用 (推荐)

```bash
# 在 Claude Code 中使用
找反向代理后面的二级路径 http://xxx.com

# 或指定多个目标
找 nginx 代理的路径映射 http://target1.com, http://target2.com

# 使用 Bing 搜索
site:xxx.com 找隐藏路径
```

### 方式二：直接运行 Python 脚本

**检测反向代理**:
```bash
python proxy_detector.py --urls "http://xxx.com" --output json
```

**分析路径** (从 site: 搜索结果):
```bash
python path_analyzer.py --urls '["http://xxx.com/abc/", "http://xxx.com/bbb/"]' --output table
```

### 方式三：管道使用

```bash
# 从文件读取
python proxy_detector.py --input-file targets.txt --proxy_only

# 结合使用
cat urls.txt | python path_analyzer.py --min-frequency 3
```

## 📊 完整工作流程

```
Step 1: 环境检查
    ├── Python 可用性
    ├── requests 库安装
    └── 搜索引擎 MCP 可用性

Step 2: 反向代理识别 (proxy_detector.py)
    ├── 访问目标根路径
    ├── 分析响应头特征
    ├── 判断代理类型 (Nginx/Apache/Cloudflare)
    └── 确认路径映射可能性

Step 3: Site 搜索
    ├── 执行 site:xxx.com
    ├── 提取所有收录的 URL
    └── 获取页面标题和内容

Step 4: 路径分析 (path_analyzer.py)
    ├── 提取二级路径 (/xxx/)
    ├── 统计路径出现频率
    ├── 判断系统类型
    └── 标注优先级 (高/中/低)

Step 5: 生成报告
    ├── 反向代理资产列表
    ├── 路径映射关系图
    ├── 高价值目标 (管理系统/测试环境)
    └── 验证建议
```

## 🎨 路径类型自动识别

| 关键词 | 系统类型 | 优先级 | 标记 |
|--------|---------|--------|------|
| admin, manage, console, dashboard | 管理系统 | 高 | ⭐⭐⭐ |
| api, v1, v2, swagger, openapi | API接口 | 高 | ⭐⭐ |
| test, dev, staging, uat, demo | 测试环境 | 高 | ⭐⭐⭐ |
| app, mobile, h5, web, www | 前端应用 | 中 | ⭐⭐ |
| portal, gateway, entry, center | 门户系统 | 中 | ⭐⭐ |
| user, account, auth, login, sso | 用户系统 | 中 | ⭐⭐ |
| static, assets, cdn, dist, build | 静态资源 | 低 | ⭐ |
| backup, old, legacy, archive | 备份系统 | 高 | ⭐⭐⭐ |

## 📈 输出示例

### 控制台输出

```
================================================================================
反向代理路径映射发现报告
================================================================================

[+] 发现的反向代理资产 (2个):

  域名: xxx.com
  类型: Nginx (置信度: 高)
  根路径状态: 403 Forbidden
  可能存在路径映射: True
  证据:
    - Server: nginx/1.18.0
    - X-Cache: MISS

================================================================================
路径映射发现 (xxx.com)
================================================================================

统计信息:
  提取的URL数: 156
  唯一路径: 12
  过滤后路径: 8
  高优先级: 4
  中优先级: 3

发现的路径映射:

路径           次数   优先级  类型
--------------------------------------------------------------------------------
/admin/        45     高     ⭐⭐⭐ 管理系统
/api/          120    高     ⭐⭐   API接口
/test/         8      高     ⭐⭐⭐ 测试环境
/backup/       2      高     ⭐⭐⭐ 备份系统
/app/          30     中     ⭐⭐   前端应用
/portal/       15     中     ⭐⭐   门户系统
/static/       50     低     ⭐     静态资源
/user/         25     中     ⭐⭐   用户系统

================================================================================
高价值目标 🔥
================================================================================

[管理系统] http://xxx.com/admin/
[测试环境] http://xxx.com/test/
[备份系统] http://xxx.com/backup/

================================================================================
验证建议
================================================================================

1. 管理后台 (/admin/)
   - 尝试访问登录页面
   - 检查是否存在弱口令
   - 确认是否需要认证

2. 测试环境 (/test/)
   - 可能未受 WAF 保护
   - 可能存在调试信息泄露
   - 建议重点测试

3. API 接口 (/api/)
   - 检查文档是否暴露
   - 测试未授权访问
   - 查找敏感接口

================================================================================
```

## ⚙️ 配置参数

### proxy_detector.py

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--urls` | 目标 URL 列表 | 必填 |
| `--max_workers` | 并发线程数 | 10 |
| `--timeout` | 请求超时(秒) | 10 |
| `--output` | 输出格式(json/table/simple) | table |
| `--proxy_only` | 只输出代理结果 | False |

### path_analyzer.py

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--urls` | URL 列表(JSON) | 必填 |
| `--min-frequency` | 最小出现频率 | 2 |
| `--top` | 显示前 N 个路径 | 20 |
| `--output` | 输出格式 | table |

## 🛡️ 安全声明

**本工具仅用于合法授权的安全测试**

1. 仅对拥有测试权限的目标使用
2. 遵守目标站点的 robots.txt
3. 不要过于频繁地进行搜索请求
4. 发现敏感路径后应验证访问权限
5. 遵守相关法律法规

## 📝 技术细节

### 反向代理检测算法

```python
检测评分系统:
- Server: nginx → +3分
- X-Nginx-Cache → +2分
- Nginx 403页面 → +2分
- Via 头 → +2分
- X-Forwarded-* → +2分
- CF-Ray → +2分

置信度:
- 5分以上 → 高
- 3-4分 → 中
- 3分以下 → 低
```

### 路径提取算法

```python
URL: https://xxx.com/abc/index.html
↓
提取路径: /abc/

分类规则:
if 'admin' in path.lower():
    return '管理系统', '高', '⭐⭐⭐'
elif 'api' in path.lower():
    return 'API接口', '高', '⭐⭐'
...
```

## 🤝 贡献

欢迎提交 Issue 和 PR！

## 📄 许可证

MIT License

## 👨‍💻 作者

fly

---

**核心能力**: 发现根路径403但子路径是管理后台的隐藏资产
