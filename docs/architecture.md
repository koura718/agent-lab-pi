# Architecture

## Next Steps 3–6 の具体化

[詳細設計](next-steps-3-6.md) に、Function Tool / MCP Server / MCP Client / Integration Testsの実装計画を定義しました。Step 3のFunction Tool・Agent factory・CLI・API不要テストは実装済みです。Step 4のMCP stdio Serverと実プロセステストも実装済みです。Step 5の診断Client・Agent側MCP接続・TOML設定も実装済みです。

- 初回MCP ServerはPython / stdioを採用し、Function Toolとcompare_listsのドメイン関数を共有します。
- 下記のNode.js MCP構成は将来候補です。
- テストはunit / ローカルintegration / 外部APIを呼ぶliveへ分離します。ローカルintegrationはネットワーク・課金不要です。
- GitHub Actionsのvalidate.ymlはすでに存在し、下記CI構成の基盤を実装済みです。
- 今回対象の3–6については詳細設計を参照してください。

Step 3の実装仕様は[Tool契約](tool-contract.md)、操作手順は[運用手順](runbook.md)を参照してください。

Step 4の公開契約と終了処理は[MCP Server仕様](mcp-server.md)を参照してください。

Step 5の接続管理と設定は[MCP Client仕様](mcp-client.md)を参照してください。

## 1. Overview

`agent-lab` は、OpenAI Codex、Claude Code、OpenAI Agents SDK、MCP を利用した  
AI Agent 開発・検証用の再利用可能なスターターテンプレートです。

このリポジトリでは、以下を重視します。

- 再現可能な開発環境
- 小さくレビュー可能な変更
- 安全な秘密情報管理
- Codex / Claude Code の併用
- Python / Node.js の役割分離
- Test / Lint / Validation の標準化
- GitHub Template Repository としての再利用性
- 将来的な MCP / Tool / 外部 API 連携

---

## 2. Design Principles

基本設計方針は以下です。

### 2.1 README as Source of Truth

プロジェクト全体の仕様・運用方針は `README.md` を基準とします。

```text
README.md
   |
   +-- AGENTS.md
   |    └-- Codex 向けルール
   |
   +-- CLAUDE.md
        └-- Claude Code 向けルール
```

AI Agent がリポジトリを操作する場合も、まず README を確認することを前提とします。

---

### 2.2 Reproducible Environment

ランタイムは `mise.toml` で固定します。

```text
mise
├── Python
├── uv
├── Node.js
└── pnpm
```

現在の基準バージョン:

```text
Python   3.14.7
uv       0.12.12
Node.js  24.21.0
pnpm     12.3.4
```

システム標準の Python や Node.js を直接置き換えない方針とします。

---

### 2.3 Local Dependency Management

Python:

```text
uv
```

Node.js:

```text
pnpm
```

を使用します。

グローバルインストールは原則避け、プロジェクト単位で依存関係を管理します。

---

### 2.4 Security First

秘密情報はソースコードと分離します。

```text
.env.example     Git 管理対象
.env             Git 管理対象外
API Keys         Git 管理対象外
OAuth Tokens     Git 管理対象外
SSH Private Key  Git 管理対象外
CLI Credentials  各ツールの認証ストア
```

秘密情報はログにも出力しません。

---

## 3. System Architecture

全体構成は以下です。

```text
Developer
   |
   +----------------------+
   |                      |
   v                      v
OpenAI Codex          Claude Code
   |                      |
   | AGENTS.md            | CLAUDE.md
   |                      |
   +----------+-----------+
              |
              v
        Git Repository
              |
      +-------+--------+
      |                |
      v                v
   Python            Node.js
      |                |
      v                v
     uv               pnpm
      |                |
      v                v
OpenAI Agents SDK     MCP Tools
      |
      v
     Agent
      |
      +-- Model
      +-- Function Tools
      +-- MCP Servers
      +-- External APIs
      +-- Data Stores
```

---

## 4. Repository Architecture

標準ディレクトリ構成:

```text
agent-lab/
├── .github/
│   └── workflows/
├── docs/
│   └── architecture.md
├── scripts/
│   ├── setup.sh
│   └── validate.sh
├── src/
│   └── agent_lab/
│       ├── __init__.py
│       └── main.py
├── tests/
│   └── test_smoke.py
├── .env.example
├── .gitignore
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── mise.toml
├── pyproject.toml
└── uv.lock
```

---

## 5. Runtime Architecture

### 5.1 mise

`mise` をランタイムバージョン管理の基盤とします。

```text
mise.toml
   |
   +-- python
   +-- uv
   +-- node
   +-- pnpm
```

目的:

- 開発環境の再現
- 新規環境セットアップの簡素化
- 開発者間のバージョン差異削減
- CI との整合性確保

---

### 5.2 Python

Python 側は OpenAI Agents SDK を中心に利用します。

```text
Python
   |
   v
uv
   |
   v
OpenAI Agents SDK
   |
   v
Agent Application
```

主な用途:

- Agent 実装
- Function Tool
- API Client
- MCP Client
- Test
- CLI
- Data Processing

---

### 5.3 Node.js

Node.js 側は主に MCP や JavaScript / TypeScript 系 Tool の実装に利用します。

```text
Node.js
   |
   v
pnpm
   |
   +-- MCP Server
   +-- MCP Tool
   +-- Utility
```

Node.js 側の依存関係は `pnpm` で管理します。

---

## 6. Agent Architecture

基本的な Agent 構成:

```text
User
  |
  v
Agent
  |
  +-------------------+
  |                   |
  v                   v
Model             Tool Layer
                      |
          +-----------+-----------+
          |           |           |
          v           v           v
     Function Tool   MCP       External API
```

---

### 6.1 Agent

Agent は以下を保持します。

- 名前
- Instructions
- Model
- Tools
- Output Policy
- Error Handling

基本的には OpenAI Agents SDK の `Agent` を使用します。

---

### 6.2 Runner

Agent の実行は Runner を介します。

```text
Input
  |
  v
Runner
  |
  v
Agent
  |
  v
Model / Tool
  |
  v
Final Output
```

Runner 層では将来的に以下を扱います。

- Timeout
- Retry
- Tracing
- Usage Monitoring
- Error Handling

---

## 7. Tool Architecture

Tool は段階的に追加します。

### Phase 1

```text
Function Tool
```

Python 関数を Tool として利用します。

目的:

- Agent Tool Calling の基本理解
- ローカルロジックとの連携
- Unit Test 容易性

---

### Phase 2

```text
MCP Server
```

Tool 実装を MCP Server として分離します。

```text
Agent
  |
  v
MCP Client
  |
  v
MCP Server
  |
  +-- File
  +-- API
  +-- Database
  +-- External Tool
```

---

### Phase 3

複数 MCP Server を利用します。

```text
Agent
  |
  +-- Filesystem MCP
  +-- Database MCP
  +-- API MCP
  +-- Search MCP
```

必要最小限の MCP のみ接続する方針とします。

---

## 8. MCP Architecture

MCP は Agent と外部機能の境界として利用します。

```text
Agent
  |
  v
MCP Client
  |
  v
MCP Protocol
  |
  v
MCP Server
  |
  +-- Resource
  +-- Tool
  +-- Prompt
```

MCP Server では以下を意識します。

- 最小権限
- 入力検証
- Timeout
- Error Handling
- Logging
- Secrets Separation

---

## 9. AI Development Tools

### 9.1 OpenAI Codex

Codex は主に以下に利用します。

- コード生成
- コードレビュー
- テスト生成
- リファクタリング
- ドキュメント整備
- Repository Analysis

設定方針:

```text
README.md
   |
   v
AGENTS.md
   |
   v
Codex
```

Codex は `AGENTS.md` のルールに従います。

---

### 9.2 Claude Code

Claude Code は主に以下に利用します。

- Repository Analysis
- 設計レビュー
- 大規模コード理解
- 実装支援
- ドキュメント生成
- 比較レビュー

設定方針:

```text
README.md
   |
   v
CLAUDE.md
   |
   v
Claude Code
```

Claude Code は sandbox / permissions を安全側で運用します。

---

## 10. Security Architecture

### 10.1 Secrets

秘密情報は `.env` に保存します。

```text
.env.example
   |
   v
.env
   |
   +-- OPENAI_API_KEY
   +-- ANTHROPIC_API_KEY
```

`.env` は Git 管理対象外です。

---

### 10.2 Git Security

以下はコミットしません。

```text
.env
API Keys
OAuth Tokens
SSH Private Keys
GitHub Tokens
Claude Credentials
Codex Credentials
```

`.gitignore` により除外します。

---

### 10.3 Privileged Operations

以下の操作は自動実行しない方針です。

- `sudo`
- OS 設定変更
- AppArmor 設定変更
- SSH 設定変更
- Firewall 設定変更
- User / Group 変更
- System-wide package install
- recursive delete
- destructive Git command

必要な場合は、影響範囲を確認してから明示的に実行します。

---

## 11. Sandbox Architecture

Codex / Claude Code は可能な限り sandbox を利用します。

```text
AI Tool
   |
   v
Sandbox
   |
   +-- Repository Read
   +-- Repository Write
   +-- Controlled Shell
   +-- Restricted Network
```

基本方針:

- リポジトリ外は原則変更しない
- 必要最小限の権限
- 未知の操作は Ask
- destructive command は明示承認

Ubuntu 24.04 では AppArmor / user namespace 制限の影響を受ける可能性があるため、OS 全体の保護を無効化するのではなく、必要最小限の調整を優先します。

---

## 12. Test Architecture

テストは大きく分けて以下に分類します。

```text
Tests
├── Unit Tests
├── Integration Tests
└── Smoke Tests
```

---

### 12.1 Unit Test

外部サービスを利用しないテストです。

対象:

- Agent object
- Tool logic
- Utility
- Data conversion
- Validation

```text
Network Access: No
API Cost: No
```

---

### 12.2 Integration Test

実際の外部 API や MCP Server を利用します。

```text
Network Access: Yes
API Cost: Possible
```

Unit Test とは明確に分離します。

---

### 12.3 Smoke Test

最小構成が動作するかを確認します。

現在は OpenAI Agents SDK の Agent 生成確認を実施しています。

---

## 13. Validation Architecture

開発時の validation フロー:

```text
Source Change
   |
   v
git diff --check
   |
   v
Ruff Lint
   |
   v
Ruff Format Check
   |
   v
pytest
   |
   v
Python Compile Check
   |
   v
Success
```

標準実行:

```bash
./scripts/validate.sh
```

---

## 14. Setup Architecture

新しい開発環境では以下の流れで構築します。

```text
Git Clone / Template
        |
        v
scripts/setup.sh
        |
        +-- prerequisite check
        |
        +-- mise install
        |
        +-- uv sync
        |
        +-- .env creation
        |
        v
scripts/validate.sh
```

`setup.sh` は OS 設定変更を行わず、プロジェクト環境の再構築に限定します。

---

## 15. Logging Architecture

アプリケーションログを導入する場合は、以下のレベルを基本とします。

```text
INFO
WARN
ERROR
```

推奨:

```text
logs/
├── agent.log
└── tool.log
```

`logs/` は Git 管理対象外とします。

秘密情報はログに出力しません。

---

## 16. Error Handling

エラー処理では以下を明確にします。

- どこで失敗したか
- なぜ失敗したか
- 再試行可能か
- ユーザー操作が必要か
- 外部サービス障害か
- 設定ミスか

例:

```text
INFO  Starting agent
INFO  Calling tool
WARN  Retry requested
ERROR External API unavailable
```

---

## 17. Configuration Architecture

設定はソースコードから分離します。

```text
Configuration
├── mise.toml
├── pyproject.toml
├── .env
└── MCP config
```

優先順位:

```text
Runtime Config
   |
   +-- Environment Variables
   +-- Project Config
   +-- Defaults
```

秘密情報を設定ファイルへ直接ハードコードしない方針です。

---

## 18. Git Architecture

基本ブランチ:

```text
main
```

通常の開発フロー:

```text
main
  |
  +-- feature/*
  |
  +-- fix/*
  |
  +-- docs/*
```

小規模な個人検証では `main` へ直接コミットする運用も許容しますが、重要な変更では branch / pull request を使用します。

---

## 19. GitHub Template Architecture

`agent-lab` 自体は Template Repository とします。

```text
agent-lab
   |
   +-- project-a
   +-- project-b
   +-- project-c
```

各プロジェクトは独立した Git 履歴を持ちます。

テンプレートでは以下を提供します。

- Runtime configuration
- Dependency management
- Agent skeleton
- Test structure
- Validation scripts
- AI coding instructions
- Security policy
- Documentation skeleton

---

## 20. Template Boundary

テンプレートに含めるもの:

```text
README.md
AGENTS.md
CLAUDE.md
mise.toml
pyproject.toml
uv.lock
.env.example
src/
tests/
scripts/
docs/
```

含めないもの:

```text
.env
.venv/
node_modules/
logs/
credentials
API Keys
temporary files
```

---

## 21. Backup Architecture

GitHub Repository を正本として利用します。

```text
Working Repository
      |
      v
GitHub
      |
      +-- Primary Source
      |
      v
git bundle
      |
      +-- Offline Backup
```

Git bundle により、GitHub 障害時やオフライン環境でも履歴を復元可能にします。

---

## 22. CI Architecture

将来的に GitHub Actions を追加します。

```text
Push / Pull Request
        |
        v
GitHub Actions
        |
        +-- mise setup
        +-- uv sync
        +-- Ruff
        +-- pytest
        +-- compile check
        |
        v
Pass / Fail
```

実 API を利用する Integration Test は通常 CI とは分離します。

---

## 23. Planned Architecture Evolution

### Phase 1

現在:

```text
Agent
  |
  v
OpenAI Model
```

---

### Phase 2

```text
Agent
  |
  v
Function Tool
```

---

### Phase 3

```text
Agent
  |
  v
MCP Server
```

---

### Phase 4

```text
Agent
  |
  +-- MCP Server A
  +-- MCP Server B
  +-- External API
```

---

### Phase 5

```text
Multi Agent
   |
   +-- Coordinator
   +-- Research Agent
   +-- Coding Agent
   +-- Review Agent
```

---

## 24. Future Extensions

今後の拡張候補:

- Function Tool
- MCP Server
- MCP Client
- Structured Output
- Agent Handoff
- Multi Agent
- Tracing
- Retry
- Timeout
- Rate Limit Handling
- Persistent Memory
- SQLite
- PostgreSQL / MySQL
- Vector Search
- Web Search
- External API
- GitHub Integration
- File Processing
- Background Jobs
- Observability
- GitHub Actions
- Docker
- Deployment

---

## 25. Current Status

現在、以下まで確認済みです。

```text
Ubuntu 24.04                OK
mise                        OK
Python 3.14.7              OK
uv 0.12.12                 OK
Node.js 24.21.0            OK
pnpm 12.3.4                OK

OpenAI Agents SDK          OK
OpenAI API Communication  OK

pytest                     OK
Ruff                       OK

OpenAI Codex CLI           OK
Codex Sandbox              OK

Claude Code                OK
Claude Permissions         OK
Claude Sandbox             OK

GitHub CLI                 OK
GitHub SSH                 OK

Docker                     OK
```

---

## 26. Architecture Decision Summary

現時点の主要判断:

| Area | Decision |
|---|---|
| Runtime Management | mise |
| Python | Python 3.14 |
| Python Dependency | uv |
| Node.js | Node.js 24 |
| Node Dependency | pnpm |
| Agent Framework | OpenAI Agents SDK |
| Test | pytest |
| Lint / Format | Ruff |
| AI Coding Tool | Codex + Claude Code |
| Tool Integration | Function Tool → MCP |
| Secrets | `.env` |
| Template | GitHub Template Repository |
| Validation | `scripts/validate.sh` |
| Setup | `scripts/setup.sh` |
| Main Documentation | README.md |

---

## 27. Guiding Principle

このプロジェクトでは、機能追加よりも以下を優先します。

```text
Reproducibility
Security
Maintainability
Testability
Observability
Simplicity
```

特に AI Agent は外部 API、Tool、MCP、ファイルシステム、ネットワークへアクセスする可能性があるため、

> 必要最小限の権限で、小さく実装し、検証してから拡張する

ことを基本原則とします。

