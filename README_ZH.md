<!-- <div align="center">
  <img src="web/static/logos/memos_logo_512.png" width="250"/>
</div> -->

[English](README.md) | 简体中文 | [日本語](README_JP.md)

![pensieve-search](docs/images/pensieve-search-en.gif)

[![哔哩哔哩](https://img.shields.io/badge/Bilibili-哔哩哔哩-%23fb7299)](https://www.bilibili.com/video/BV16XUkY7EJm) [![YouTube](https://img.shields.io/badge/YouTube-YouTube-%23ff0000)](https://www.youtube.com/watch?v=tAnYkeKTFUc)


> 我对名字进行了调整，因为 Memos 这个名字已经被其他人注册了，所以改成了 Pensieve。

# Pensieve（原 Memos）

Pensieve 是一个专注于隐私的被动记录项目。它可以自动记录屏幕内容，构建智能索引，并提供便捷的 web 界面来检索历史记录。

这个项目主要参考了另外两个项目，一个叫做 [Rewind](https://www.rewind.ai/)，另一个叫做 [Windows Recall](https://support.microsoft.com/en-us/windows/retrace-your-steps-with-recall-aa03f8a0-a78b-4b3e-b0a1-2eb8ac48701c)。不过，与它们不同的是 Pensieve 让你可以完全管控自己的数据，避免将数据传递到不信任的数据中心。

## 功能特性

- 🚀 安装简单，只需要通过 pip 安装依赖就可以开始使用了
- 🔒 数据全掌控，所有数据都存储在本地，可以完全本地化运行，数据处理完全由自己控制
- 🔍 支持全文检索和向量检索
- 📊 交互式实体详情视图，支持时间序列上下文导航
- 🌐 智能元数据捕获，包括网页活动的浏览器 URL 获取
- 🤖 支持和 Ollama 一起工作，让 Ollama 作为 Pensieve 的机器学习引擎
- 🌐 支持任何 OpenAI API 兼容的模型（比如 OpenAI, Azure OpenAI，vLLM 等）
- 💻 支持 Mac 和 Windows 系统（Linux 支持正在开发中）
- 🔌 支持通过插件扩展出更多数据处理能力

## 📰 最新动态

- **增强的实体详情视图**: 从 `v0.29.0` 版本开始，Pensieve 引入了全新的实体详情页面，支持交互式上下文导航，让您可以按时间顺序浏览截图，提供更好的视觉上下文和元数据显示。
- **OCR 处理升级**: 更新 RapidOCR 版本，采用默认模型，减少约 15MB 的包大小。
- **配置管理界面**: 从 `v0.27.0` 版本开始，Pensieve 引入了直观的配置管理界面，可通过 Web 端轻松配置所有 Pensieve 设置。
- **API 结构优化**: 所有 API 端点现在使用标准的 `/api` 前缀，提高了一致性和可维护性。
- **智能空闲处理策略**: 从 `v0.26.0` 版本开始，Pensieve 引入了智能空闲处理策略，可以在系统空闲时自动处理未处理的文件。这项功能可以尽量多的处理截图，同时最小化对系统活跃使用时的性能影响。详细信息请参阅[空闲处理策略](#空闲处理策略)部分。
- **PostgreSQL 支持**: 从 `v0.25.4` 版本开始，Pensieve 现在完全支持使用 PostgreSQL 作为后端数据库。此增强功能允许在大数据量的情况下提高检索性能。如果您的截图数据量大或需要高速检索，我们强烈建议使用 PostgreSQL。有关设置 PostgreSQL 的更多详细信息，请参阅[使用 PostgreSQL 数据库](#-使用-postgresql-数据库)部分。

## 快速开始

![memos-installation](docs/images/memos-installation.gif)

> [!IMPORTANT]  
> 似乎不是所有版本的 Python 的 sqlite3 库都支持 `enable_load_extension`。不过，我不确定哪些环境或 Python 版本会遇到这个问题。我使用 `conda` 来管理 Python，通过 `conda` 安装的 Python macOS、Windows x86 和 Ubuntu 22.04 上都可以正常工作。
>
> 请确认以下命令在你的 Python 环境中是否正常工作：
>
> ```python
> import sqlite3
> 
> # Check sqlite version
> print(f"SQLite version: {sqlite3.sqlite_version}")
> 
> # Test if enable_load_extension is supported
> try:
>     conn = sqlite3.connect(':memory:')
>     conn.enable_load_extension(True)
>     print("enable_load_extension is supported")
> except AttributeError:
>     print("enable_load_extension is not supported")
> finally:
>     conn.close()
> ```
>
> 如果你发现这样无法正常工作，那么可以安装 [miniconda](https://docs.conda.io/en/latest/miniconda.html) 来管理 Python 环境。或者查看目前的 issue 列表，看看是否有其他人遇到同样的问题。

### 1. 安装 Pensieve

```sh
pip install -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple memos
```

### 2. 初始化

初始化 pensieve 的配置文件和 sqlite 数据库：

```sh
memos init
```

数据将存放在 `~/.memos` 目录中。

### 3. 启动服务

```sh
memos enable
memos start
```

这个命令会：

- 开始对所有屏幕进行记录
- 启动 Web 服务
- 将服务设置为开机启动

### 4. 访问 Web 界面

打开浏览器，访问 `http://localhost:8839`

![init page](docs/images/init-page-en.png)

### Mac 下的权限问题

在 Mac 下，Pensieve 需要获取截图权限，程序启动的时候，Mac 就会提示需要录屏的权限，请允许即可。

![mac permission](docs/images/mac-security-permission.jpg)

## 🚀 使用 PostgreSQL 数据库

要在 Pensieve 中使用 PostgreSQL，您需要安装支持 PostgreSQL 的软件包：

```sh
pip install memos[postgresql]
```

从 `v0.25.4` 版本开始，Pensieve 开始完整支持使用 PostgreSQL 作为后端数据库。相比 SQLite，PostgreSQL 在数据规模较大时依然可以获取非常好的检索性能。

如果你的截图数据规模较大，或者对检索响应速度有较高要求，强烈建议使用 PostgreSQL 作为后端数据库。

### 1. 使用 Docker 启动 PostgreSQL

由于 Pensieve 使用了向量检索功能，因此需要使用带有 pgvector 扩展的 PostgreSQL。我们推荐使用官方的 pgvector 镜像：

在 Linux/macOS 下：

```sh
docker run -d \
    --name pensieve-pgvector \
    --restart always \
    -p 5432:5432 \
    -e POSTGRES_PASSWORD=mysecretpassword \
    -v pensieve-pgdata:/var/lib/postgresql/data \
    pgvector/pgvector:pg17
```

在 Windows PowerShell 下：

```powershell
docker run -d `
    --name pensieve-pgvector `
    --restart always `
    -p 5432:5432 `
    -e POSTGRES_PASSWORD=mysecretpassword `
    -v pensieve-pgdata:/var/lib/postgresql/data `
    pgvector/pgvector:pg17
```

在 Windows 传统命令提示符下：

```cmd
docker run -d ^
    --name pensieve-pgvector ^
    --restart always ^
    -p 5432:5432 ^
    -e POSTGRES_PASSWORD=mysecretpassword ^
    -v pensieve-pgdata:/var/lib/postgresql/data ^
    pgvector/pgvector:pg17
```

这个命令会：

- 创建一个名为 `pensieve-pgvector` 的容器
- 设置 PostgreSQL 的密码为 `mysecretpassword`
- 将容器的 5432 端口映射到主机的 5432 端口
- 使用支持向量检索的 PostgreSQL 17 版本
- 创建一个名为 `pensieve-pgdata` 的数据卷来持久化存储数据
- 设置容器在 Docker 重启后自动启动

> 注意：如果你使用的是 Windows，需要先确保 Docker Desktop 已经安装并运行。你可以从 [Docker 官网](https://www.docker.com/products/docker-desktop/) 下载并安装 Docker Desktop。

### 2. 配置 Pensieve 使用 PostgreSQL

修改 `~/.memos/config.yaml` 文件中的数据库配置：

```yaml
# 将原来的 SQLite 配置：
database_path: database.db

# 改为 PostgreSQL 配置：
database_path: postgresql://postgres:mysecretpassword@localhost:5432/postgres
```

配置说明：

- `postgres:mysecretpassword`：数据库用户名和密码
- `localhost:5432`：PostgreSQL 服务器地址和端口
- `postgres`：数据库名称

### 3. 从 SQLite 迁移到 PostgreSQL

如果你之前使用的是 SQLite，想要迁移到 PostgreSQL，Pensieve 提供了专门的迁移命令：

```sh
# 停止 Pensieve 服务
memos stop

# 执行迁移
memos migrate \
  --sqlite-url "sqlite:///absolute/path/to/your/database.db" \
  --pg-url "postgresql://postgres:mysecretpassword@localhost:5432/postgres"

# 修改配置文件指向 PostgreSQL
# 编辑 ~/.memos/config.yaml，更新 database_path

# 重新启动服务
memos start
```

注意事项：

1. 迁移前请确保 PostgreSQL 服务正常运行
2. 迁移过程会完全清空目标 PostgreSQL 数据库，请确保数据库中没有重要数据
3. 迁移不会影响原有的 SQLite 数据库
4. 迁移过程可能需要一些时间，取决于数据量的大小
5. 迁移完成后，你可以选择备份并删除原来的 SQLite 数据库文件

下面分别是 Mac 和 Windows 的迁移命令：

```sh
# Mac
memos migrate \
  --sqlite-url "sqlite:///~/memos/database.db" \
  --pg-url "postgresql://postgres:mysecretpassword@localhost:5432/postgres"
```

```powershell
# Windows PowerShell
memos migrate `
  --sqlite-url "sqlite:///$env:USERPROFILE/.memos/database.db" `
  --pg-url "postgresql://postgres:mysecretpassword@localhost:5432/postgres"
```

```cmd
# Windows Command Line
memos migrate ^
  --sqlite-url "sqlite:///%USERPROFILE%/.memos/database.db" ^
  --pg-url "postgresql://postgres:mysecretpassword@localhost:5432/postgres"
```

## 使用指南

### 增强的实体详情视图

Pensieve v0.29.0 引入了全面的实体详情视图，为您的截图提供更深入的洞察：

1. **交互式上下文导航**：点击任何搜索结果即可打开详细的实体视图，支持时间序列上下文导航
2. **上下文导航栏**：使用底部的水平上下文导航栏浏览截图，按时间顺序显示前后截图
3. **丰富的元数据显示**：查看全面的元数据，包括浏览器 URL、应用程序名称、时间戳和提取的文本
4. **增强的视觉上下文**：通过改进的元数据捕获，更好地了解您的数字活动

新的实体视图让您更容易重建数字时间线，并找到特定时刻周围的相关内容。

### 使用配置管理界面

Pensieve v0.27.0 版本引入了全新的配置管理界面，让您可以更方便地管理系统设置：

1. 在浏览器中访问 `http://localhost:8839/config`
2. 界面分为几个主要部分：通用配置、服务器配置、记录配置、监控配置等
3. 修改相关设置后点击"保存更改"按钮
4. 对于需要重启服务的更改，系统会自动提示并提供服务重启选项

通过配置界面，您可以轻松调整各种设置，如 OCR 和 VLM 选项、空闲处理策略、数据库配置等，无需手动编辑配置文件。

### 使用合适的 embedding 模型

#### 1. 模型选择

Pensieve 通过 embedding 模型来提取语义信息，并构建向量索引。因此，选择一个合适的 embedding 模型非常重要。针对使用者的主语言，需要选择不同的 embedding 模型。

- 对于中文场景，可以使用 [jinaai/jina-embeddings-v2-base-zh](https://huggingface.co/jinaai/jina-embeddings-v2-base-zh) 模型。
- 对于英文场景，可以使用 [jinaai/jina-embeddings-v2-base-en](https://huggingface.co/jinaai/jina-embeddings-v2-base-en) 模型。

#### 2. 调整 Pensieve 配置

使用你喜欢的文本编辑器打开 `~/.memos/config.yaml` 文件，并修改 `embedding` 配置：

```yaml
embedding:
  use_local: true
  model: arkohut/jina-embeddings-v2-base-zh  # 使用的模型名称
  num_dim: 768                               # 模型的维度             
  use_modelscope: false                      # 是否使用魔搭（ModelScope）的模型
```

- 配置这里我使用的模型名称为 `arkohut/jina-embeddings-v2-base-zh`，这是我对原始的模型仓库做了裁剪，删除了一些用不到的模型文件，加速下载的速度。
- 如果你无法访问 Hugging Face 的模型仓库，可以设置 `use_modelscope` 为 `true`，通过魔搭（ModelScope）模型仓库下载模型。

#### 3. 重启 Pensieve 服务

```sh
memos stop
memos start
```

第一次使用 embedding 模型时，Pensieve 会自动下载模型并加载模型。

#### 4. 重新构建索引

如果你是在使用过程中切换了 embedding 模型，也就是说你之前已经索引过截图，那么你需要重新构建索引：

```sh
memos reindex --force
```

`--force` 参数表示重新构建索引表，并删除之前索引的截图数据。

### 使用 Ollama 支持视觉检索

默认情况下，Pensieve 仅启用 OCR 插件来提取截图中的文字并建立索引。然而，对于不包含文字的图像，这种方式会大大限制检索效果。

为了实现更全面的视觉检索功能，我们需要一个兼容 OpenAI API 的多模态图像理解服务。Ollama 正好可以完美胜任这项工作。

#### 使用前的重要说明

在决定是否启用 VLM 功能前，请注意以下几点：

1. **硬件要求**

   - 推荐配置：至少 8GB 显存的 NVIDIA 显卡或 M 系列芯片的 Mac
   - minicpm-v 模型将占用约 5.5GB 存储空间
   - 不建议使用 CPU 模式，会导致系统严重卡顿

2. **性能和功耗影响**

   - 启用 VLM 后会显著增加系统功耗
   - 可以考虑使用其他设备提供 OpenAI API 兼容的模型服务

#### 1. 安装 Ollama

请访问 [Ollama 官方文档](https://ollama.com) 获取详细的安装和配置指南。

#### 2. 准备多模态模型

使用以下命令下载并运行多模态模型 `minicpm-v`：

```sh
ollama run minicpm-v "描述一下这是什么服务"
```

这条命令会下载并运行 minicpm-v 模型，如果发现运行速度太慢的话，不推荐使用这部分功能。

#### 3. 配置 Pensieve 使用 Ollama

使用你喜欢的文本编辑器打开 `~/.memos/config.yaml` 文件，并修改 `vlm` 配置：

```yaml
vlm:
  endpoint: http://localhost:11434  # Ollama 服务地址
  modelname: minicpm-v              # 使用的模型名称
  force_jpeg: true                  # 将图片转换为 JPEG 格式以确保兼容性
  prompt: 请帮描述这个图片中的内容，包括画面格局、出现的视觉元素等  # 发送给模型的提示词
```

使用上述配置覆盖 `~/.memos/config.yaml` 文件中的 `vlm` 配置。

同时还要修改 `~/.memos/plugins/vlm/config.yaml` 文件中的 `default_plugins` 配置：

```yaml
default_plugins:
- builtin_ocr
- builtin_vlm
```

这里就是将 `builtin_vlm` 插件添加到默认的插件列表中。

#### 4. 重启 Pensieve 服务

```sh
memos stop
memos start
```

重启 Pensieve 服务之后，稍等片刻，就可以在 Pensieve 的 Web 界面中最新的截图里看到通过 VLM 所提取的数据了：

![image](./docs/images/single-screenshot-view-with-minicpm-result.png)

如果没有看到 VLM 的结果，可以：

- 使用命令 `memos ps` 查看 Pensieve 进程是否正常运行
- 检查 `~/.memos/logs/memos.log` 中是否有错误信息
- 确认 Ollama 模型是否正确加载（`ollama ps`）

### 全量索引

Pensieve 是一个计算密集型的应用，Pensieve 的索引过程会需要 OCR、VLM 以及 embedding 模型协同工作。为了尽量减少对用户电脑的影响，Pensieve 会计算每个截图的平均处理时间，并依据这个时间来调整索引的频率。因此，默认情况下并不是所有的截图都会被立即索引。

如果希望对所有截图进行索引，可以使用以下命令进行全量索引：

```sh
memos scan
```

该命令会扫描并索引所有已记录的截图。请注意，根据截图数量和系统配置的不同，这个过程可能会持续一段时间，并且会占用较多系统资源。索引的构建是幂等的，多次运行该命令不会对已索引的数据进行重复索引。

### 调整索引频率

Pensieve 在运行时，会根据截图生成的频率和单个截图的处理速度动态调整图像处理的间隔。对于没有 NVIDIA GPU 的情况，很难保证单个图像的处理速度比截图生成速度快，因此截图处理是抽样执行的。为了避免电脑负载过高，Pensieve 默认的抽样策略非常保守，这可能会导致有充足算力的设备无法充分发挥其性能。因此，在 `config.yaml` 中增加了更多的控制选项，允许用户选择更保守或更激进的策略。

```yaml
watch:
  # 统计处理速率的窗口大小
  rate_window_size: 10
  # 文件处理的稀疏因子
  # 值越高，处理频率越低
  # 1.0 表示处理每个文件，不能小于 1.0
  sparsity_factor: 3.0
  # 文件处理的初始间隔，表示每 N 个文件处理一个文件
  # 但会根据处理速率自动调整
  # 12 表示一开始每 12 个文件处理一个文件
  processing_interval: 12
```

如果希望每个截图文件都被处理，可以这么配置：

```yaml
# 这样的监控配置意味着一开始会处理每个文件
# 但如果处理速度比文件生成速度慢，处理间隔将会自动增加
watch:
  rate_window_size: 10
  sparsity_factor: 1.0
  processing_interval: 1
```

### 空闲处理策略

Pensieve 实现了智能的空闲处理策略，以在系统空闲时处理未处理的文件。这有助于确保所有截图最终都能被处理，同时最小化对系统活跃使用时的性能影响。

#### 空闲检测和处理

- 系统在 5 分钟没有新的截图活动后进入空闲状态
- 在空闲状态下，Pensieve 会尝试处理之前未处理的文件，前提是：
  - 系统不在使用电池供电
  - 当前时间在配置的处理时间窗口内
  - 有待处理的文件

#### 配置说明

空闲处理行为可以在 `~/.memos/config.yaml` 中自定义：

```yaml
watch:
  # 进入空闲状态前等待的秒数
  idle_timeout: 300
  # 处理未处理文件的时间窗口
  # 格式：["HH:MM", "HH:MM"]
  idle_process_interval: ["00:00", "07:00"]
```

- `idle_timeout`：系统在多少秒没有活动后进入空闲状态
- `idle_process_interval`：可以处理未处理文件的时间窗口
  - 格式为 ["HH:MM", "HH:MM"]，使用 24 小时制
  - 时间窗口可以跨越午夜（例如 ["23:00", "07:00"] 是有效的）
  - 对于跨越午夜的时间窗口，开始时间必须在 12:00 之后以避免歧义

这个策略确保：

1. 系统资源在工作时间主要用于活跃使用
2. 后台处理在非工作时间进行
3. 通过避免在电池供电时处理来延长电池寿命

记得执行 `memos stop && memos start` 使任何配置更改生效。

## 隐私安全

在开发 Pensieve 的过程中，我一直密切关注类似产品的进展，特别是 [Rewind](https://www.rewind.ai/) 和 [Windows Recall](https://support.microsoft.com/en-us/windows/retrace-your-steps-with-recall-aa03f8a0-a78b-4b3e-b0a1-2eb8ac48701c)。我非常欣赏它们的产品理念，但它们在隐私保护方面做得不够，这也是许多用户（或潜在用户）所担心的问题。记录个人电脑的屏幕可能会暴露极为敏感的隐私数据，如银行账户、密码、聊天记录等。因此，确保数据的存储和处理完全由用户掌控，防止数据泄露，变得尤为重要。

Pensieve 的优势在于：

1. 代码完全开源，并且是易于理解的 Python 代码，任何人都可以审查代码，确保没有后门。
2. 数据完全本地化，所有数据都存储在本地，数据处理完全由用户控制，数据将被存储在用户的 `~/.memos` 目录中。
3. 易于卸载，如果不再使用 Pensieve，通过 `memos stop && memos disable` 即可关闭程序，然后通过 `pip uninstall memos` 即可卸载，最后删除 `~/.memos` 目录即可清理所有的数据库和截图数据。
4. 数据处理完全由用户控制，Pensieve 是一个独立项目，所使用的机器学习模型（包括 VLM 以及 embedding 模型）都由用户自己选择，并且由于 Pensieve 的运作模式，使用较小的模型也可以达到不错的效果。

当然 Pensieve 肯定在隐私方面依然有可以改进的地方，欢迎大家贡献代码，一起让 Pensieve 变得更好。

## 其他值得注意的内容

### 有关存储空间

Pensieve 每 5 秒会记录一次屏幕，并将原始截图保存到 `~/.memos/screenshots` 目录中。存储空间占用主要取决于以下因素：

1. **截图数据**：

   - 单张截图大小：约 40-400KB（取决于屏幕分辨率以及显示的复杂程度）
   - 日均数据量：约 400MB（基于 10 小时使用时长，单屏幕 2560x1440 分辨率）
   - 多屏幕使用：数据量会随屏幕数量增加
   - 月度估算：按 20 个工作日计算，约 8GB

   截图会进行去重，如果连续截图内容变化不大，那么只会保留一张截图，去重机制可以在内容变化不频繁时（如阅读、文档编辑等场景）显著减少存储占用。

2. **数据库空间**：

   - SQLite 数据库大小取决于索引的截图数量
   - 参考值：10 万张截图索引后约占用 2.2GB 存储空间

### 有关功耗

Pensieve 默认需要两个计算密集型的任务：

- 一个是 OCR 任务，用于提取截图中的文字
- 一个是 embedding 任务，用于提取语义信息构建向量索引

#### 资源使用情况

- **OCR 任务**：使用 CPU 执行，并根据不同操作系统优化选择 OCR 引擎，以最小化 CPU 占用
- **Embedding 任务**：智能选择计算设备

  - NVIDIA GPU 设备优先使用 GPU
  - Mac 设备优先使用 Metal GPU
  - 其他设备使用 CPU

#### 性能优化策略

为了避免影响用户日常使用，Pensieve 采取了以下优化措施：

- 动态调整索引频率，根据系统处理速度自适应
- 电池供电时自动降低处理频率，最大程度节省电量

## 开发指南

### 拨开第一层洋葱

事实上，Pensieve 启动之后，会运行三个程序：

1. `memos serve` 启动 Web 服务
2. `memos record` 启动截图记录程序
3. `memos watch` 监听 `memos record` 所生成的图像事件，并结合实际的处理速度动态的向服务器提交索引请求

所以，如果你是开发者，或者希望更清晰的看到整个项目运行的日志，你完全可以使用这三个命令让每个部分在前台运行，去替代 `memos enable && memos start` 命令。
