# Legal_LLM

RAG 法律大模型项目：用于将法律/法规等资料做结构化处理，便于后续检索与问答（RAG）。

目前包含两个主要工具：

- `docx2txt.py`：批量把 `.docx` 转换为 `.txt (UTF-8)`[1]
- `text2json.py`：将法律 `.txt` 输入给大模型，输出结构化 `json`

[1]：因为法律文件的下载地址是[国家法律法规数据库](https://flk.npc.gov.cn/index)，批量下载是用docx导出的

---

## 目录结构（约定）

```

Legal_LLM/
law/                 # 放法律原始 txt（text2json 输入）
prompts/             # 放 few-shot / prefix 提示词文件
output/              # text2json 输出 json / 日志
docx2txt.py
text2json.py

````

---

## 1) docx2txt：批量导入 docx，批量导出 txt（UTF-8）

### 功能
- 选择一个或多个 `.docx` 文件
- 将内容导出为同名 `.txt`（UTF-8）
- 可用于把 Word 法律文件转成纯文本，后续给 `text2json` 使用

### 使用方法（示例）
在项目根目录运行：

```bash
python docx2txt.py
````

运行后会弹出文件选择窗口，选择多个 `.docx` 即可。

> 输出位置与文件命名以脚本内逻辑为准（通常是同目录或指定输出目录）。
> 建议最终把转换得到的 `.txt` 放到 `law/` 目录，便于后续批量处理。

---

## 2) text2json：法律 txt -> 结构化 json（大模型输出）

### 功能

* 从 `law/` 目录选择一个法律 `.txt`
* 读取 `prompts/` 下的 few-shot 示例与 prefix
* 调用模型（SiliconFlow OpenAI 兼容接口）
* 输出：

  * `output/chunk_output_<法律名>.json`
  * `output/convert_log.jsonl`（记录已转换文件，重复会跳过）

### 准备

确保 `prompts/` 目录存在以下文件（你的提示词/示例）：

* `./prompts/prompts_chunk_input_text.txt`
* `./prompts/prompts_chunk_output_json.json`
* `./prompts/prompts_chunk_prefix.txt`

并把待处理法律文本放入 `./law/*.txt`

### 运行

在项目根目录运行：

```bash
python text2json.py
```

运行时会：

1. 提示输入 `API_KEY`
2. 弹窗选择 `law/` 下的 `.txt`
3. 控制台 streaming 打印模型输出
4. 生成 `output/chunk_output_<法律名>.json`

### 输出文件

* `output/chunk_output_<法律名>.json`：最终结构化结果
* `output/convert_log.jsonl`：转换日志（用于跳过重复转换）

---

## 说明

* 若模型输出不是严格 JSON，会在控制台提示 `JSON parse failed`，并保留 raw 输出供排查。

