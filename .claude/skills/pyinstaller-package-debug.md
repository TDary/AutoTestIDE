---
name: pyinstaller-package-debug
description: AutoTestIDE PyInstaller 打包排错套路
metadata: 
  node_type: memory
  type: reference
  originSessionId: 4e0d1cb5-fe0f-4f90-89b6-fe79ed121e7e
---

# 打包排错

## 常见问题

### 1. 运行时 ImportError
**症状**：打包后启动报 `ModuleNotFoundError: autotest_ide.core.code_gen`
**原因**：PyInstaller 静态分析漏掉动态 import 的模块
**修复**：在 `autotest-ide.spec` 的 `hiddenimports` 列表中补上

```python
hiddenimports=[
    # ... 已有的 ...
    "autotest_ide.core.code_gen",      # 新增
    "autotest_ide.ui.record_controller",  # 新增
],
```

**排查命令**：
```bash
# 在 dist 目录中搜索模块是否存在
find dist/AutoTestIDE/ -name "code_gen*"
# 搜索 .pyc 不存在 → 说明没打包进去
```

### 2. 数据文件找不到（Jinja2 模板、runtest.py）
**症状**：运行时报 `template.html not found` 或子进程找不到 `runtest.py`
**原因**：`datas` 列表遗漏或目标路径不对
**修复**：在 spec 文件 `datas` 中补条目

```python
datas=[
    # 报告模板
    ("src/autotest_ide/report/template.html", "autotest_ide/report"),
    ("src/autotest_ide/report/report.css", "autotest_ide/report"),
    ("src/autotest_ide/report/report.js", "autotest_ide/report"),
    # Runner 脚本
    ("src/autotest_ide/runner/runtest.py", "scripts"),
    # SDK 包 __init__.py
    ("src/autotest_ide/sdks", "autotest_ide/sdks"),
    ("src/autotest_ide/sdks/jx4", "autotest_ide/sdks/jx4"),
],
```

**排查**：
```bash
# 检查数据文件是否在产物中
ls dist/AutoTestIDE/autotest_ide/report/
ls dist/AutoTestIDE/scripts/
```

### 3. 运行时弹黑窗后闪退
**症状**：双击 exe 后窗口一闪而过
**原因**：未捕获的异常在 `console=False` 模式下无输出
**修复**：临时改 `console=True` 看错误输出

```python
exe = EXE(
    ...
    console=True,  # 临时改为 True 排错
    ...
)
```

排完再改回 `False`。

### 4. 打包体积过大
**修复**：在 spec 的 `excludes` 中排除不需要的大包

```python
excludes=[
    "tkinter", "matplotlib", "numpy", "cv2",
    "pytest", "unittest",
    "distutils", "setuptools", "pip",
    "email", "html", "xml.etree", "xml.dom",
    "pygments",
],
```

### 5. 增量打包不生效
**原因**：PyInstaller 缓存了旧的 build 目录
**修复**：
```bash
python -m PyInstaller autotest-ide.spec --noconfirm
```

## Checklist（每次改代码后打包前）

- [ ] 新增模块 → 检查 `hiddenimports`
- [ ] 新增数据文件 → 检查 `datas`
- [ ] 删除模块 → 从 `hiddenimports` 移除
- [ ] `python -m pytest tests/ -v` 全部通过
- [ ] `python -m PyInstaller autotest-ide.spec --noconfirm`
- [ ] 运行 `dist/AutoTestIDE/AutoTestIDE.exe` 手动验证

[[pyinstaller-package-debug]]
