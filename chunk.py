import getpass
import sys
import time
from pathlib import Path

from text2json import Text2Json  # 你的类所在文件名：text2json.py


def prompt_go_on(timeout_sec: int = 30) -> bool:
    """
    Windows 稳定版：
    - Y/y/回车：继续
    - n/N：停止
    - timeout_sec 秒无输入：自动继续
    """
    try:
        import msvcrt
    except ImportError:
        # 非 Windows 兜底：直接继续
        print(f"[INFO] Current platform does not support timed console input, continue by default.")
        return True

    print(f"Go on next file [Y/n] (default: continue in {timeout_sec}s): ", end="", flush=True)

    chars = []
    start = time.time()

    while True:
        # 超时：自动继续
        if time.time() - start >= timeout_sec:
            print("\n[INFO] No input in 30s, continue...\n")
            return True

        if msvcrt.kbhit():
            ch = msvcrt.getwch()

            # 回车：继续
            if ch in ("\r", "\n"):
                print()
                text = "".join(chars).strip().lower()
                if text in ("n", "no"):
                    print("[INFO] Stop requested. Exiting.\n")
                    return False
                return True

            # Ctrl+C
            if ch == "\x03":
                raise KeyboardInterrupt

            # 退格
            if ch == "\b":
                if chars:
                    chars.pop()
                    print("\b \b", end="", flush=True)
                continue

            # 普通字符
            chars.append(ch)
            print(ch, end="", flush=True)

        time.sleep(0.05)


def main():
    BASE_URL = "https://api.siliconflow.cn/v1"
    MODEL_CHUNK = "Pro/zai-org/GLM-5"

    PROMPT_INPUT_PATH = "./prompts/prompts_chunk_input_text.txt"
    PROMPT_OUTPUT_PATH = "./prompts/prompts_chunk_output_json.json"
    PROMPT_PREFIX_PATH = "./prompts/prompts_chunk_prefix.txt"

    LAW_DIR = Path("./law")
    if not LAW_DIR.exists():
        raise RuntimeError(f"law 目录不存在：{LAW_DIR.resolve()}")

    # 每次执行前要求输入 API_KEY（不回显）
    api_key = getpass.getpass("请输入 API_KEY（输入时不显示）：").strip()
    if not api_key:
        raise RuntimeError("未输入 API_KEY，程序已退出。")

    t2j = Text2Json(
        base_url=BASE_URL,
        api_key=api_key,
        model=MODEL_CHUNK,
        prompt_input_path=PROMPT_INPUT_PATH,
        prompt_output_path=PROMPT_OUTPUT_PATH,
        prompt_prefix_path=PROMPT_PREFIX_PATH,
        out_dir="output",
        log_file="convert_log.jsonl",
    )

    law_files = sorted(LAW_DIR.glob("*.txt"))
    if not law_files:
        raise RuntimeError(f"law 目录下没有找到 txt 文件：{LAW_DIR.resolve()}")

    print(f"[FOUND] {len(law_files)} law txt files.")

    for i, law_path in enumerate(law_files, 1):
        print(f"\n========== [{i}/{len(law_files)}] {law_path.name} ==========")

        try:
            try:
                input_text = law_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                input_text = law_path.read_text(encoding="utf-8", errors="replace")

            result = t2j.text_to_json_file(input_text=input_text, law_name=law_path.stem)

            if result is None:
                print(f"[INFO] skipped => {law_path.name}")

        except Exception as e:
            print(f"[ERROR] Failed on {law_path.name}: {repr(e)}")

        # 每处理完一个文件都询问是否继续
        if i < len(law_files):
            go_on = prompt_go_on(timeout_sec=30)
            if not go_on:
                sys.exit(0)

    print("\n[DONE] all law files processed.")


if __name__ == "__main__":
    main()