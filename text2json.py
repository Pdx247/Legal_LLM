import os
import json
import re
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.prompts import FewShotPromptTemplate, PromptTemplate


class Text2Json:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        prompt_input_path: str,
        prompt_output_path: str,
        prompt_prefix_path: str,
        out_dir: str = "output",                   # 输出目录
        log_file: str = "convert_log.jsonl",       # 转换日志
    ):
        # ==============
        # 代理隔离
        # ==============
        for k in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
            os.environ.pop(k, None)
        os.environ["NO_PROXY"] = "127.0.0.1,localhost,api.siliconflow.cn"

        self.base_url = base_url
        self.api_key = api_key
        self.model_name = model

        self.prompt_input_path = prompt_input_path
        self.prompt_output_path = prompt_output_path
        self.prompt_prefix_path = prompt_prefix_path

        self.out_dir = Path(out_dir)
        self.log_path = self.out_dir / log_file  # 日志路径

        if not self.api_key:
            raise RuntimeError("API_KEY 为空，请检查你的配置。")

        # model：开启 streaming=True stream()
        self.chunk_model = ChatOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model_name,
            streaming=True,
        )

        # prompt pieces
        self.chunk_template = PromptTemplate.from_template("原文:\n{law_text}\n\n整理成json格式:\n{law_json}")

        with open(self.prompt_input_path, "r", encoding="utf-8") as f:
            self.prompt_chunk_input = f.read()
        with open(self.prompt_output_path, "r", encoding="utf-8") as f:
            self.prompt_chunk_output = f.read()
        with open(self.prompt_prefix_path, "r", encoding="utf-8") as f:
            self.prompt_chunk_prefix = f.read()

        # few-shot template
        self.chunk_data = [{"law_text": self.prompt_chunk_input, "law_json": self.prompt_chunk_output}]
        self.chunk_few_shot_template = FewShotPromptTemplate(
            example_prompt=self.chunk_template,
            examples=self.chunk_data,
            prefix=self.prompt_chunk_prefix,
            suffix="基于我的示例，告诉我{input_law}的json格式是什么，仅输出json格式的数据(将示例中的‘$’看作大括号)，不要有多余输出",
            input_variables=["input_law"],
        )

        # 启动时读取日志，形成已转换集合
        self.ensure_parent_dir(self.log_path)
        self.done_names = self._load_done_names()

    # =========================
    # helpers
    # =========================
    def ensure_parent_dir(self, p: Path) -> None:
        p.parent.mkdir(parents=True, exist_ok=True)

    def safe_stem(self, name: str) -> str:
        stem = Path(name).stem
        return re.sub(r'[\\/:*?"<>|]+', "_", stem).strip() or "law"

    def extract_json_str(self, text: str) -> str:
        text = (text or "").strip()

        if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
            return text

        first_obj = text.find("{")
        first_arr = text.find("[")
        candidates = []

        if first_obj != -1:
            last_obj = text.rfind("}")
            if last_obj != -1 and last_obj > first_obj:
                candidates.append(text[first_obj:last_obj + 1])

        if first_arr != -1:
            last_arr = text.rfind("]")
            if last_arr != -1 and last_arr > first_arr:
                candidates.append(text[first_arr:last_arr + 1])

        if candidates:
            return max(candidates, key=len)

        raise ValueError("未能从模型输出中提取出 JSON，请检查模型返回内容。")

    def count_tokens_fallback(self, prompt_text: str, model_name: str = "") -> int:
        try:
            import tiktoken  # pip install tiktoken
            try:
                enc = tiktoken.encoding_for_model(model_name)
            except Exception:
                enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(prompt_text))
        except Exception:
            return max(1, len(prompt_text) // 4)

    def approx_tokens(self, text: str) -> int:
        try:
            return self.chunk_model.get_num_tokens(text)
        except Exception:
            return self.count_tokens_fallback(text, self.model_name)

    def clean_text(self, text: str) -> str:
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def stream_and_collect(self, prompt: str) -> str:
        collected = []
        print("\n[Model Output - streaming]\n")
        for chunk in self.chunk_model.stream(prompt):
            delta = getattr(chunk, "content", "") or ""
            if delta:
                print(delta, end="", flush=True)
                collected.append(delta)
        print("\n\n[Streaming Done]\n")
        return "".join(collected)

    # 读日志
    def _load_done_names(self) -> set:
        done = set()
        if not self.log_path.exists():
            return done
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        name = obj.get("law_name")
                        if name:
                            done.add(name)
                    except Exception:
                        continue
        except Exception:
            return done
        return done

    # 写日志
    def _append_log(self, law_name: str, json_path: Path, raw_path: Path) -> None:
        record = {
            "law_name": law_name,
            "json_path": str(json_path.as_posix()),
            "raw_path": str(raw_path.as_posix()),
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # =========================
    # core API
    # =========================
    def text_to_json_file(self, input_text: str, law_name: str) -> Path | None:
        law_name = self.safe_stem(law_name)

        out_path = Path(f"{self.out_dir.as_posix()}/chunk_output_{law_name}.json")
        raw_out_path = Path(f"{self.out_dir.as_posix()}/chunk_output_{law_name}.txt")

        # ✅ 更稳：日志里有，或者 json 文件已经存在，都跳过
        if law_name in self.done_names or out_path.exists():
            print(f"[SKIP] already converted => {law_name}")
            if law_name not in self.done_names:
                self.done_names.add(law_name)
            return None

        self.ensure_parent_dir(out_path)

        input_text = self.clean_text(input_text)

        # build prompt
        prompts = self.chunk_few_shot_template.format(input_law=input_text)

        # token count (估算)
        prompt_tokens = self.approx_tokens(prompts)
        print(f"[Token Count] prompts tokens ≈ {prompt_tokens}")

        # stream once (替代 invoke)
        raw_text = self.stream_and_collect(prompts)

        # save raw output for debugging (always)
        with open(raw_out_path, "w", encoding="utf-8") as f:
            f.write(raw_text)
        print(f"[OK] raw output saved => {raw_out_path.resolve()}")

        # extract json and save
        try:
            json_str = self.extract_json_str(raw_text)
            data = json.loads(json_str)

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            print(f"[OK] JSON saved => {out_path.resolve()}")

            # 成功后写日志 & 更新集合
            self._append_log(law_name, out_path, raw_out_path)
            self.done_names.add(law_name)

            return out_path

        except Exception as e:
            print(f"[WARN] JSON parse failed: {repr(e)}")
            print(f" 已保存原始输出到: {raw_out_path.resolve()}")
            raise


if __name__ == "__main__":
    BASE_URL = "https://api.siliconflow.cn/v1"
    MODEL_CHUNK = "Pro/moonshotai/Kimi-K2.5"

    # ✅ 每次执行前要求用户输入 API_KEY（不回显）
    import getpass
    API_KEY = getpass.getpass("请输入 API_KEY（输入时不显示）：").strip()
    if not API_KEY:
        raise RuntimeError("未输入 API_KEY，程序已退出。")

    PROMPT_INPUT_PATH = "./prompts/prompts_chunk_input_text.txt"
    PROMPT_OUTPUT_PATH = "./prompts/prompts_chunk_output_json.json"
    PROMPT_PREFIX_PATH = "./prompts/prompts_chunk_prefix.txt"

    # ✅ 弹出 ./law 目录，让你点选一个 txt 文件
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()

    law_dir = (Path(__file__).resolve().parent / "law").resolve()
    file_path = filedialog.askopenfilename(
        title="选择一个法律 txt 文件",
        initialdir=str(law_dir),
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
    )

    if not file_path:
        raise RuntimeError("未选择文件，程序已退出。")

    LAW_PATH = Path(file_path)
    with open(LAW_PATH, "r", encoding="utf-8") as f:
        input_text = f.read()

    t2j = Text2Json(
        base_url=BASE_URL,
        api_key=API_KEY,
        model=MODEL_CHUNK,
        prompt_input_path=PROMPT_INPUT_PATH,
        prompt_output_path=PROMPT_OUTPUT_PATH,
        prompt_prefix_path=PROMPT_PREFIX_PATH,
        out_dir="output",
    )

    t2j.text_to_json_file(input_text=input_text, law_name=LAW_PATH.stem)