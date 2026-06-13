# Cancan Microstack 原理说明（core / runtime / cli）

本文解释 `cancan_microstack` 这个库的抽象“到底在做什么、怎么做、为什么这样做”。重点覆盖三块：

- **core**：核心能力（资产、compose 合成、服务启动）
- **runtime**：运行时“适配/覆盖”机制（workspace 探测、覆盖目录、资源回退）
- **cli**：命令行如何把这些能力串起来

> 说明：本文内容基于 `cancan_microstack` 包的实现（`core/`, `runtime/`, `cli/` 目录）。

---

## 1. Cancan Microstack 解决的问题是什么

在一个“业务仓库”里，通常会重复做很多基础设施相关的事情：

- 拷贝一份 infra 的 `docker-compose.infra.yml`、DDL、启动脚本
- 业务自己维护/合并多个 compose 文件（容易漂移、版本不一致）
- 需要快速拉起 `controllersrv / infrasrv / opsbffsrv` 来配合业务服务

`cancan_microstack` 的目标是：

- 把**基础设施微服务栈**（controllersrv、infrasrv、opsbffsrv）及其必要资产（compose/DDL/脚本）作为**一个 Python 库**打包
- 通过 **AssetManager** 导出/读取资产，避免在业务仓复制模板
- 通过 **ComposeBuilder** 把“库内置的 infra compose”与“业务仓的 services compose”做合并，生成一个可运行的完整栈
- 通过 **ServiceRunner** 直接运行内置服务入口（cmd）
- 通过 **CLI** 把上述能力变成统一命令 `cancan ...`

你可以把它理解为一个“可嵌入（embedded）的 microstack 工具箱”：

- 资产（assets）+ 合成（compose build）+ 运行（services run）

---

## 2. 总体架构：Facade + 三个子系统

库里有一个很薄的门面（Facade）：`core/microstack.py` 的 `CancanMicrostack`。

它把三类核心能力组合在一起：

- `AssetManager`：管理包内静态文件（compose/DDL/scripts…）
- `ComposeBuilder`：合并 compose 生成最终栈文件
- `ServiceRunner`：启动内置服务（controllersrv/infrasrv/opsbffsrv）

对应源码结构：

- `core/`：上述三类能力的实现
- `runtime/`：运行时“工作区/覆盖/资源选择”的策略
- `cli/`：命令行入口，把用户输入映射到 `CancanMicrostack` 的方法

---

## 3. core：核心模块的具体原理

### 3.1 `CancanMicrostack`（Facade / 门面模式）

位置：`core/microstack.py`

核心思想：

- 对外暴露“少量、高层”的 API（build_compose/export_asset/run_service）
- 内部把细节委托给 `AssetManager/ComposeBuilder/ServiceRunner`

它的关键方法：

- `build_compose(workspace, service_file, overrides, output)`
  - 只是记录日志并调用 `ComposeBuilder.build(...)`
- `export_asset(logical_name, destination, overwrite)`
  - 调用 `AssetManager.export_asset(...)`
- `run_service(service_name, host, port, workspace)`
  - 调用 `ServiceRunner.run(...)`

这种封装的价值：

- CLI 和代码调用方都只要认识一个对象 `CancanMicrostack`，不用理解内部对象怎么拼起来

### 3.2 `AssetManager`（资产导出与读取）

位置：`core/assets.py`

`AssetManager` 的“资产”指 `cancan_microstack/assets/` 目录里随 Python 包一起发布的静态文件，例如：

- docker compose 模板
- DDL SQL
- 脚本

实现原理：

- 使用标准库 `importlib.resources` 来访问包内文件：
  - `resources.files(self._package)` 获取“可遍历的资源树”
  - `resources.as_file(traversable)` 将资源“物化”为真实文件路径（即使是 zip 包资源也能用）

关键能力：

- `list_assets(subdir=None)`
  - 遍历 `assets/`，返回 `AssetRecord(logical_name, path, is_dir)` 列表
  - `logical_name` 类似 `docker/docker-compose.infra.yml`，是对外稳定的“逻辑路径”
- `export_asset(logical_name, destination, overwrite=False)`
  - 把某个资产复制到工作区目录
  - 目录资产用 `shutil.copytree`，文件资产用 `shutil.copy2`
- `read_text(logical_name)`
  - 读取文本内容
- `resolve_path(logical_name)`
  - 把资产解析成一个真实 Path（用于后续读取/解析 YAML）

为什么要这样做：

- 业务仓不需要拷贝模板文件；资产版本随库升级而升级
- “逻辑名”让调用方稳定，不需要知道库内部真实文件在什么路径

### 3.3 `ComposeBuilder`（合成 compose 栈）

位置：`core/compose_builder.py`

`ComposeBuilder` 的目标：

- 以“库内置 infra compose”为 base
- 再叠加“业务仓 services compose”（可选）
- 再叠加多份 override（可选）
- 输出一个最终 compose 文件（默认 `compose.cancan.yml`）

实现步骤（与代码一致）：

1. 解析路径
   - `workspace`、`output_path` 都会 `.resolve()`
   - `output_file` 为空时默认：`workspace / "compose.cancan.yml"`

2. 加载 base compose
   - `base_model = _load_asset_yaml(self.base_asset)`
   - 默认 `base_asset = "docker/docker-compose.infra.yml"`
   - 底层通过 `AssetManager.resolve_path()` 找到资产文件，再 `yaml.safe_load()`

3. 合并业务 compose（可选）
   - 如果 `service_file` 存在：`merged = deep_merge(merged, load_yaml(service_file))`

4. 合并 overrides（可选、多份）
   - 逐个存在就合并：`merged = deep_merge(merged, load_yaml(override))`

5. 写出最终文件
   - `yaml.safe_dump(merged, sort_keys=False)`

核心算法：`_deep_merge(base: dict, override: dict)`

- 若 key 不存在：直接拷贝 override
- 若两边都是 dict：递归 deep merge
- 否则：override 覆盖 base

这意味着：

- 你的业务 compose 可以覆盖 infra 的同名字段（例如某个 service 的 env、ports 等）
- override 是“更高优先级”，最后应用

### 3.4 `ServiceRunner`（启动内置服务）

位置：`core/runner.py`

`ServiceRunner` 的职责：

- 把一个服务名（controllersrv/infrasrv/opsbffsrv）映射到一个“入口点字符串”
- 动态 import 对应模块并调用入口函数 `main(host, port)`
- 同时在启动前做 runtime bootstrap（workspace + overrides）

入口点映射（代码内固定字典 `_ENTRYPOINTS`）：

- `controllersrv` -> `cancan_microstack.cmd.controllersrv.run:main`
- `infrasrv` -> `cancan_microstack.cmd.infrasrv.run:main`
- `opsbffsrv` -> `cancan_microstack.cmd.opsbffsrv.run:main`

调用链：

- `run(...)` 是同步入口：内部 `asyncio.run(self.run_async(...))`
- `run_async(...)`：
  1) 计算 `workspace_path`（如果传了 workspace）
  2) `bootstrap_from_workspace(workspace_path)`（runtime 逻辑，下面会讲）
  3) `import_module(module_name)` 动态导入
  4) `func = getattr(module, func_name)`
  5) `result = func(host=host, port=port)`
  6) 如果 `result` 是 awaitable，则 await

为什么这样做：

- `cmd/` 下服务入口可以是同步或异步；runner 用 `inspect.isawaitable` 兼容两种
- 启动前统一把工作区与覆盖配置好，避免服务内部自己做一堆路径探测

---

## 4. runtime：运行时机制的具体原理

`runtime/` 解决的是“库被嵌入到某个业务工作区以后，如何识别工作区、如何支持覆盖、如何在工作区优先使用本地文件”的问题。

### 4.1 workspace 探测与标准目录

位置：`runtime/workspace.py`

#### 4.1.1 工作区根目录的概念

库把“当前业务仓根目录”称为 workspace root。它影响：

- 日志目录（`server_log_data/`）应该创建在哪里
- 当用户传入相对路径时，应该相对哪个根目录
- overrides 自动发现从哪里开始向上搜索

#### 4.1.2 探测规则（优先级）

- 优先环境变量：`CANCAN_WORKSPACE_ROOT`
- 否则从 `start`（默认 `Path.cwd()`）开始向上遍历，遇到任意“标记文件/目录”就认为是 workspace

标记（`_MARKERS`，任意一个存在即命中）：

- `server_log_data`
- `cmd`
- `docker-compose.infra.yml`
- `docker-compose.services.yml`
- `pyproject.toml`
- `requirements.txt`

这就是为什么它能在一个典型业务仓里“自动找根目录”。

#### 4.1.3 配置与使用

- `configure_workspace(root=None)`
  - 若传入 root：用它
  - 若 root 为 None：调用 `detect_workspace_root()` 自动探测
  - 保存到模块级变量 `_workspace_root`，并写入环境变量 `CANCAN_WORKSPACE_ROOT`

- `get_workspace_root()`
  - 懒加载：如果没配置过，就用环境变量或自动探测

- `ensure_server_log_dir()`
  - 在 workspace 下创建 `server_log_data/`

- `ensure_subdir(relative_path)`
  - 在 workspace 下创建任意子目录

### 4.2 overrides：不 fork 也能局部覆盖

位置：`runtime/overrides.py`

核心目标（文件头注释已经说明）：

- 允许业务仓通过 `cancan_overrides/` 注入 controllersrv/infrasrv/opsbffsrv 的自定义配置或实现
- 不需要 fork `cancan_microstack` 主库

#### 4.2.1 override root 的发现

- 环境变量：`CANCAN_OVERRIDE_ROOT`
- 否则从 workspace root 向上寻找名为 `cancan_overrides/` 的目录

相关函数：

- `discover_override_root(start=None)`
- `configure_overrides(root=None)`
- `get_override_root()`

`configure_overrides` 会把最终路径写入环境变量 `CANCAN_OVERRIDE_ROOT`。

#### 4.2.2 “覆盖”的实现方式：扩展 package search path

函数：`extend_service_package(service_name, package_name, package_path)`

逻辑：

1. 找到 override root（例如 `<workspace>/cancan_overrides`）
2. 如果存在 `<override_root>/<service_name>` 目录（例如 `cancan_overrides/infrasrv`）
3. 把该目录插入到 package 的搜索路径最前面

它通过 `pkgutil.extend_path` 构造 combined path：

- `combined_paths = [str(service_override), *package_path]`

这样当 Python import `cancan_microstack.services.<service_name>...` 时：

- 会优先在工作区 `cancan_overrides/<service_name>/` 下找模块
- 找不到才回退到库自带 `cancan_microstack/services/<service_name>/`

这是一种典型的“插件/覆盖”机制：

- 覆盖目录只需放你想替换的那几个文件
- 未覆盖的部分仍然复用库本身实现

#### 4.2.3 bootstrap：把 workspace 与 overrides 串起来

函数：`bootstrap_from_workspace(workspace)`

- 先 `configure_workspace(workspace)`
- 再基于该 root 去 `discover_override_root(...)` 并 `configure_overrides(...)`

`ServiceRunner.run_async` 在启动服务前会调用它，所以 “服务启动”天然具备 workspace + overrides 能力。

### 4.3 resources：工作区优先，资产兜底

位置：`runtime/resources.py`

函数：`resolve_workspace_or_asset(relative_path, asset_logical)`

规则非常直接：

- 先看 `<workspace_root>/<relative_path>` 是否存在
- 存在就用工作区文件
- 不存在就回退到包内资产：`AssetManager.resolve_path(asset_logical)`

这个机制常用于：

- 允许业务仓“放一个同名配置文件”来覆盖默认资产
- 不需要修改库代码

---

## 5. cli：命令行如何把能力串起来

位置：`cli/main.py`

CLI 是基于 `argparse` 的三段式子命令：

- `assets`：查看/导出资产
- `compose`：生成合并后的 compose
- `services`：运行内置服务

### 5.1 CLI 入口与解析

- `build_parser()` 构造 `argparse.ArgumentParser`
- `main(argv=None)` 解析参数并执行

CLI 每次运行都会实例化：

- `stack = CancanMicrostack()`

然后根据 subcommand 执行对应的 `stack.xxx`。

### 5.2 `assets` 子命令

- `cancan assets list [subdir]`
  - `stack.assets.list_assets(subdir)`
- `cancan assets export <logical_name> <destination> [--overwrite]`
  - `stack.export_asset(...)`

本质就是把 `AssetManager` 的能力暴露给用户。

### 5.3 `compose build` 子命令

- `cancan compose build --workspace . --service-file ... --override ... --output ...`

执行：

- 解析 workspace/service_file/overrides/output 为 Path
- 调用 `stack.build_compose(...)`

输出默认是 `<workspace>/compose.cancan.yml`（除非你显式 `--output`）。

### 5.4 `services run` 子命令

- `cancan services run <controllersrv|infrasrv|opsbffsrv> --host ... --port ... --workspace ...`

执行：

- `stack.run_service(...)`

而 `stack.run_service` 内部会走 `ServiceRunner.run -> run_async -> bootstrap_from_workspace`，所以 CLI 启动服务也自动带上 workspace + overrides 逻辑。

---

## 6. 一条“从命令到服务启动”的完整链路（串起来看）

以 `cancan services run infrasrv --workspace . --port 8080` 为例：

1. `cli/main.py:main()` 解析参数
2. 构造 `stack = CancanMicrostack()`
3. 调用 `stack.run_service("infrasrv", host, port, workspace)`
4. `core/microstack.py` 委托给 `self.runner.run(...)`
5. `core/runner.py:run()` -> `asyncio.run(run_async(...))`
6. `run_async()` 中：
   - `bootstrap_from_workspace(workspace_path)`
   - 根据 `_ENTRYPOINTS` 得到 `cancan_microstack.cmd.infrasrv.run:main`
   - `import_module(...)` + `getattr(...)
   - 调用 `main(host, port)`，如返回 awaitable 则 await

到这里，服务入口（`cmd/infrasrv/run.py`）接管后续：初始化 web server、路由、配置等。

---

## 7. 你之前“没太看懂”的点：它抽象的关键其实是两件事

1) **把静态资产当作 Python 包资源管理**

- 资产（compose/DDL/scripts）跟代码一起发布
- 通过 `AssetManager` 统一“列出/导出/读取/解析路径”

2) **把“工作区”和“覆盖”当作运行时策略统一注入**

- `runtime/workspace.py` 负责找到“你到底在哪个业务仓里跑”
- `runtime/overrides.py` 负责让业务仓用 `cancan_overrides/` 覆盖部分实现
- `ServiceRunner` 在启动服务前做 bootstrap，保证一致性

理解了这两个点，你会发现：

- `core` 提供能力
- `runtime` 提供“在业务仓里怎么落地”的策略
- `cli` 把能力做成统一工具链

---

## 8. 与你当前项目的 import 规范的关系（重要）

你当前项目有一个强约束：

- `__init__.py` 尽量保持空/不做 re-export
- 业务代码必须从“真实定义符号的模块文件”直接 import

`cancan_microstack` 的设计其实与这个原则兼容：

- 资产访问不依赖 `__init__.py` re-export（走 `importlib.resources`）
- 服务启动通过“明确入口点字符串”定位模块
- 覆盖机制通过扩展 package path，而不是在 `__init__` 里拼装导出

---

## 9. 实用建议（怎么用/怎么扩展）

- 想要在业务仓自定义某个服务的实现：
  - 创建 `cancan_overrides/<service_name>/...`，只放你要替换的文件
  - 运行时会自动优先加载覆盖目录（或用 `CANCAN_OVERRIDE_ROOT` 指定）

- 想要覆盖某个默认配置文件/资产：
  - 在 workspace 放置 `relative_path` 对应的文件
  - 使用 `resolve_workspace_or_asset` 的地方会优先选择工作区文件

- 想要生成完整栈 compose：
  - 用 `cancan compose build`，让 infra + services + overrides 统一合成到 `compose.cancan.yml`

### 9.1 关于 Docker 访问包内资产的正确姿势

`export_asset` 的设计目标就是“先把包内文件复制到你的工作区，再让 Docker 通过挂载访问”。

- Docker 只看到挂载进容器的工作区路径，不会直接去 venv 的 site-packages 查找
- 所以需要先在宿主机执行 `cancan assets export ... <workspace_path>`
- 然后在 compose 中挂载/引用 `<workspace_path>` 下的文件（而不是引用 venv 内路径）
- 这样既符合安全权限（容器只读工作区卷），也符合“包可分发”原则

