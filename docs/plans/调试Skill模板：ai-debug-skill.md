# 调试Skill模板：`ai-debug-skill`

***

### 一、Skill基础信息

```
名称: ai-debug-skill
版本: 1.0
用途: 对AICoding生成的项目代码进行高效调试，支持语法检查、逻辑验证、集成调试、性能分析四层调用
Token优化策略: 按需加载，只传入被调试代码片段，不加载项目全局上下文
```

***

### 二、输入格式（严格按照此结构传入）

```
{
  "layer": "L1|L2|L3|L4",          // 调试层级
  "code": "string",                 // 被调试的代码片段（必填）
  "function_signature": "string",   // 函数签名（L2、L3选填）
  "input_example": "string",        // 输入示例（L2选填）
  "expected_output": "string",      // 预期输出（L2、L3选填）
  "error_log": "string",            // 错误日志/异常信息（L3必填，其他层级选填）
  "runtime_data": "string",         // 运行时数据（L4选填）
  "language": "string"              // 编程语言（必填，如Python/JavaScript/Go等）
}
```

***

### 三、调试层级定义与输出格式

#### **L1 语法检查**

```
用途: 检查当前代码片段是否有语法错误、类型错误、未定义变量
输入重点: 完整代码片段
输出格式:
{
  "status": "pass|error|warning",
  "issues": [
    {
      "line": 行号,
      "type": "syntax|type|undefined",
      "description": "问题描述",
      "suggestion": "修复建议"
    }
  ]
}
```

#### **L2 逻辑验证**

```
用途: 验证函数逻辑是否符合预期，检查边界条件、空值处理
输入重点: 函数签名 + 完整函数代码 + 输入示例 + 预期输出
输出格式:
{
  "status": "pass|fail|inconclusive",
  "logic_issues": [
    {
      "condition": "触发条件描述",
      "expected": "预期行为",
      "actual": "实际行为（推测）",
      "fix": "修复建议"
    }
  ],
  "edge_cases": ["未处理的边界情况列表"]
}
```

#### **L3 集成调试**

```
用途: 根据错误日志，定位问题根源，给出修复建议
输入重点: 完整代码片段 + 错误日志/异常信息
输出格式:
{
  "root_cause": "问题根因",
  "location": "代码位置（文件名+行号）",
  "error_chain": "错误调用链（如有）",
  "unexpected_behavior": "非预期行为描述",
  "fix": "修复建议代码或步骤",
  "risk": "修复后可能引入的风险（如有）"
}
```

#### **L4 性能/安全分析**

```
用途: 检查代码性能瓶颈或安全漏洞
输入重点: 完整代码片段 + 运行时数据（可选）
输出格式:
{
  "category": "performance|security|both",
  "findings": [
    {
      "severity": "high|medium|low",
      "location": "代码位置",
      "description": "问题描述",
      "impact": "潜在影响",
      "recommendation": "优化/修复建议"
    }
  ]
}
```

***

### 四、Skill完整Prompt（可直接复制使用）

> 你是一个专业的调试工程师，请根据以下输入进行调试分析。
>
> **调试层级**: \{layer}
>
> **语言**: \{language}
>
> **传入代码**:
>
> ```language
> {code}
> ```
>
> **补充信息**:
>
> * 函数签名: \{function\_signature}
> * 输入示例: \{input\_example}
> * 预期输出: \{expected\_output}
> * 错误日志: \{error\_log}
> * 运行时数据: \{runtime\_data}
>
> **输出要求**:
>
> 1. 严格按照对应层级的输出格式返回结果
> 2. 只输出JSON格式，不要添加额外解释
> 3. 如果缺少必要字段，请在description中说明
> 4. 修复建议尽量具体，包含代码示例
> 5. 如果无法定位，请返回status为"inconclusive"

***

### 五、在AICoding中的使用示例

#### 场景1：执行L1语法检查

```
// 输入
{
  "layer": "L1",
  "code": "def add(a, b):\n    return a + b\n\nresult = add(1, '2')",
  "language": "Python"
}

// 输出示例
{
  "status": "warning",
  "issues": [
    {
      "line": 4,
      "type": "type",
      "description": "int类型与str类型相加，可能导致类型错误",
      "suggestion": "添加类型检查或强制转换：return int(a) + int(b)"
    }
  ]
}
```

#### 场景2：执行L3集成调试（根据错误日志）

```
// 输入
{
  "layer": "L3",
  "code": "def fetch_data(url):\n    response = requests.get(url)\n    return response.json()",
  "error_log": "Traceback (most recent call last):\n  File \"test.py\", line 3, in fetch_data\n    return response.json()\nAttributeError: 'NoneType' object has no attribute 'json'",
  "language": "Python"
}

// 输出示例
{
  "root_cause": "requests.get()返回了None，可能因为网络异常或URL无效",
  "location": "test.py:2",
  "error_chain": "fetch_data → requests.get → response.json (None)",
  "unexpected_behavior": "未处理请求失败的情况，直接调用json()导致报错",
  "fix": "添加异常处理：\n    try:\n        response = requests.get(url, timeout=5)\n        response.raise_for_status()\n        return response.json()\n    except (requests.RequestException, ValueError) as e:\n        return {'error': str(e)}",
  "risk": "可能会吞掉某些需要特别处理的异常，建议根据具体情况细化异常类型"
}
```

***

### 六、Token优化建议

使用时遵循以下原则，进一步降低Token消耗：

1. **只传相关代码片段**：不要传整个文件，只传被调试的函数或代码块
2. **补充信息尽量精简**：错误日志只保留关键的最后几行，输入示例只写出典型值
3. **优先使用L1/L2**：能通过语法检查或逻辑验证解决的问题，不要调用L3/L4
4. **缓存重复调用**：如果同一个函数被多次调试，可以考虑缓存上一次的L1/L2结果

***

### 七、扩展建议

您可以根据项目特点，对这个基础模板进行扩展：

* 对于**Web项目**：增加“L5 前端渲染调试” / “L6 API接口调试”
* 对于**多语言项目**：在输入中增加`target_file`字段，指定具体文件
* 对于**AI项目**：增加“L7 模型输出验证”，检查模型输出是否符合预期格式

***

这个模板可以直接复制到您的AICoding项目中作为Skill使用。如果您需要针对某个特定语言（如Python、JavaScript、Go）或特定框架（如React、Flask、Spring Boot）进行定制，可以进行随时调整
