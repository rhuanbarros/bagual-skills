# Setup — Sistema de Skills BMad + Bagual

> Guia de reinstalação após formatação ou novo PC.
> Tempo estimado: 30–45 minutos.

---

## O que está salvo aqui

```
skills/
├── SETUP.md                          ← este arquivo
├── bagual-skills/                    ← skills customizadas (fonte principal)
│   ├── bagual-bmad-implement-quick-epic/   ← pipeline de epic (fast mode, time tracking)
│   ├── bagual-bmad-implement-epic/
│   ├── bagual-bmad-worktree-setup/
│   ├── bagual-test-pipeline/               ← com Step 3.5 startup smoke test
│   └── bagual-ai-evals-*/                  ← 10+ skills de AI evals
└── project-templates/                ← arquivos para copiar em cada novo projeto
    ├── _bmad/custom/
    │   ├── bmad-dev-story.toml       ← carrega 4 knowledge files + time tracking
    │   └── bmad-quick-dev.toml       ← carrega 4 knowledge files
    ├── CLAUDE.md                     ← template (preencher para cada projeto)
    └── AGENTS.md                     ← template (preencher para cada projeto)
```

**O que NÃO está aqui** (não precisa de backup):
- `bmad-*` skills (53+) — vêm do instalador BMad, reinstalar conforme Passo 3
- Arquivos de conhecimento dos projetos (`_bmad-output/*.md`) — ficam nos repos git

---

## Passo 1 — Instalar Claude Code

```powershell
# Via npm
npm install -g @anthropic-ai/claude-code

# Verificar
claude --version
```

Ou baixar o instalador em: https://claude.ai/download

---

## Passo 2 — Restaurar as bagual-skills

Copiar a pasta `bagual-skills/` deste backup para `Downloads`:

```powershell
Copy-Item -Recurse "D:\Meu Drive\skills\bagual-skills" "C:\Users\{SEU_USUARIO}\Downloads\bagual-skills"
```

Resultado esperado: `C:\Users\{SEU_USUARIO}\Downloads\bagual-skills\` com todas as subpastas.

---

## Passo 3 — Instalar o BMad (skills bmad-*)

O BMad instala as ~53 skills padrão (`bmad-quick-dev`, `bmad-dev-story`, `bmad-workflow-builder`, etc.).

```powershell
# Abrir Claude Code em qualquer projeto e rodar:
/bmad-bmb-setup
```

Ou instalar via npm se disponível:
```powershell
npm install -g @bagual/bmad
```

> Consulte a documentação atual do BMad em https://github.com/bmad-ai/bmad para o método de instalação correto na versão do momento.

---

## Passo 4 — Configurar um projeto existente

Para cada projeto clonado do git:

### 4a. Instalar bmad-* no projeto (se não estiver no repo)

```powershell
cd C:\projetos\meu-projeto
# Abrir Claude Code e rodar /bmad-bmb-setup
```

### 4b. Instalar as bagual-* skills

**Opção A — Symlinks** (recomendado — atualiza todos os projetos ao mesmo tempo):

```
create a synlink of these skills here in this project.

bagual-bmad-implement-quick-epic
bagual-test-pipeline

they are on the path /home/rhuan/2_temporario/bagual-skills/*.*

create the synlink here on the path /home/rhuan/2_temporario/autoshow/.claude/skills
```

```powershell
cd C:\projetos\meu-projeto\.claude\skills

# Criar symlinks para cada bagual-skill
New-Item -ItemType SymbolicLink -Path "bagual-bmad-implement-quick-epic" -Target "C:\Users\{SEU_USUARIO}\Downloads\bagual-skills\bagual-bmad-implement-quick-epic"
New-Item -ItemType SymbolicLink -Path "bagual-bmad-implement-epic"       -Target "C:\Users\{SEU_USUARIO}\Downloads\bagual-skills\bagual-bmad-implement-epic"
New-Item -ItemType SymbolicLink -Path "bagual-bmad-worktree-setup"       -Target "C:\Users\{SEU_USUARIO}\Downloads\bagual-skills\bagual-bmad-worktree-setup"
New-Item -ItemType SymbolicLink -Path "bagual-test-pipeline"             -Target "C:\Users\{SEU_USUARIO}\Downloads\bagual-skills\bagual-test-pipeline"
```

> ⚠️ Criar symlinks no Windows requer modo administrador ou Developer Mode ativado.
> Ativar: Configurações → Privacidade e Segurança → Para Desenvolvedores → Modo de Desenvolvedor.

**Opção B — Cópia física** (mais simples, mas cada projeto fica independente):

```powershell
Copy-Item -Recurse "C:\Users\{SEU_USUARIO}\Downloads\bagual-skills\bagual-bmad-implement-quick-epic" ".claude\skills\"
Copy-Item -Recurse "C:\Users\{SEU_USUARIO}\Downloads\bagual-skills\bagual-test-pipeline"             ".claude\skills\"
# ... repetir para cada skill
```

### 4c. Copiar os arquivos de customização do BMad

```powershell
# Criar a pasta custom se não existir
New-Item -ItemType Directory -Force "_bmad\custom"

# Copiar os TOMLs do backup
Copy-Item "D:\Meu Drive\skills\project-templates\_bmad\custom\bmad-dev-story.toml" "_bmad\custom\"
Copy-Item "D:\Meu Drive\skills\project-templates\_bmad\custom\bmad-quick-dev.toml" "_bmad\custom\"
```

### 4d. Verificar `_bmad/bmm/config.yaml`

O arquivo deve existir com nome do projeto e idioma. Se não existir ou estiver desconfigurado:

```yaml
# _bmad/bmm/config.yaml
project_name: NOME_DO_PROJETO
communication_language: "brazilian Portuguese"
document_output_language: Brazilian Portuguese
user_name: Bagual
user_skill_level: intermediate
planning_artifacts: "{project-root}/_bmad-output/planning-artifacts"
implementation_artifacts: "{project-root}/_bmad-output/implementation-artifacts"
output_folder: "{project-root}/_bmad-output"
```

---

## Passo 5 — Configurar um projeto NOVO do zero

```powershell
# 1. Criar o projeto e entrar nele
mkdir C:\projetos\novo-projeto
cd C:\projetos\novo-projeto
git init

# 2. Instalar BMad (Passo 3)
# 3. Instalar bagual-skills (Passo 4b ou 4b)

# 4. Criar AGENTS.md e CLAUDE.md a partir dos templates
Copy-Item "D:\Meu Drive\skills\project-templates\AGENTS.md" "."
Copy-Item "D:\Meu Drive\skills\project-templates\CLAUDE.md" "."
# Editar ambos: substituir todos os {CAMPOS_ENTRE_CHAVES}

# 5. Copiar TOMLs
New-Item -ItemType Directory -Force "_bmad\custom"
Copy-Item "D:\Meu Drive\skills\project-templates\_bmad\custom\*" "_bmad\custom\"

# 6. Criar _bmad/bmm/config.yaml (ver Passo 4d)

# 7. Criar _bmad-output/ com os 5 arquivos de memória
New-Item -ItemType Directory -Force "_bmad-output"
# Criar manualmente: anti-patterns.md, decisions.md, notes.md,
#                   product-decisions.md, projects-history.md
# (Ou usar /bmad-quick-dev para que a skill os crie automaticamente na primeira sessão)
```

---

## Estrutura mínima de um projeto configurado

```
meu-projeto/
├── CLAUDE.md                    ← importa AGENTS.md + regras Claude Code
├── AGENTS.md                    ← contexto para qualquer AI (stack, regras, skills)
├── .claude/
│   └── skills/
│       ├── bagual-bmad-implement-quick-epic/  (symlink ou cópia)
│       ├── bagual-test-pipeline/              (symlink ou cópia)
│       ├── bmad-quick-dev/                    (instalado pelo BMad)
│       ├── bmad-dev-story/                    (instalado pelo BMad)
│       └── ... (outras bmad-* skills)
├── _bmad/
│   ├── bmm/config.yaml          ← nome do projeto, idioma, paths
│   └── custom/
│       ├── bmad-dev-story.toml  ← carrega knowledge files + time tracking
│       └── bmad-quick-dev.toml  ← carrega knowledge files
└── _bmad-output/
    ├── anti-patterns.md         ← padrões a evitar (auto-memory)
    ├── decisions.md             ← decisões técnicas (auto-memory)
    ├── product-decisions.md     ← decisões de produto (auto-memory)
    ├── notes.md                 ← conhecimento operacional (auto-memory)
    └── projects-history.md      ← timeline de stories
```

---

## Verificação rápida após setup

Abrir Claude Code no projeto e rodar:

```
/bmad-help
```

→ Deve listar as skills disponíveis sem erros.

```
/bmad-quick-dev
```

→ Deve ativar, carregar os 4 arquivos de conhecimento, e cumprimentar em português.

---

## Troubleshooting

**"skill not found" ao rodar /bagual-***  
→ Verificar se a pasta existe em `.claude/skills/` (symlink ou cópia)  
→ Em Windows, symlinks precisam de Developer Mode ou modo admin

**"_bmad/custom/*.toml não está sendo lido"**  
→ Verificar se `_bmad/bmm/config.yaml` existe  
→ Verificar se o nome do arquivo é exatamente `bmad-dev-story.toml` (sem espaços)

**"persistent_facts não carrega os arquivos"**  
→ Verificar se os 4 arquivos `.md` existem em `_bmad-output/`  
→ Caminhos são relativos ao `{project-root}` — verificar se o projeto foi aberto na pasta certa

**Symlinks não funcionam (acesso negado)**  
→ Ativar Developer Mode: Configurações → Privacidade → Para Desenvolvedores → Modo de Desenvolvedor  
→ Ou usar Opção B (cópia física) como alternativa
