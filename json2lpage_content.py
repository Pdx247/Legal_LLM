import json
from pathlib import Path


INPUT_DIR = Path("./output")
OUTPUT_DIR = Path("./page_content")
LOG_PATH = OUTPUT_DIR / "page_content_log.jsonl"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_done_files(log_path: Path) -> set:
    done = set()
    if not log_path.exists():
        return done

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    name = obj.get("source_json")
                    if name:
                        done.add(name)
                except Exception:
                    continue
    except Exception:
        pass

    return done


def append_log(log_path: Path, source_json: str, output_txt: str) -> None:
    record = {
        "source_json": source_json,
        "output_txt": output_txt,
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def normalize_value(v) -> str:
    """把 value 统一转成字符串，并过滤无效值。"""
    if v is None:
        return ""
    s = str(v).strip()
    if not s or s == "原文未提及":
        return ""
    return s


def dict_to_line(d: dict) -> str:
    """
    按 dict 的 value 顺序拼接。
    第一个 value（法律名）加书名号。
    """
    values = list(d.values())
    parts = []

    for i, v in enumerate(values):
        s = normalize_value(v)
        if not s:
            continue

        if i == 0:
            s = f"《{s}》"

        parts.append(s)

    return " ".join(parts)


def process_one_json(json_path: Path, output_dir: Path) -> Path | None:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print(f"[SKIP] {json_path.name}: 顶层不是 list")
        return None

    lines = []
    for idx, item in enumerate(data, 1):
        if not isinstance(item, dict):
            print(f"[SKIP] {json_path.name}: 第 {idx} 项不是 dict")
            continue

        line = dict_to_line(item)
        if line:
            lines.append(line)

    out_path = output_dir / f"{json_path.stem}.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))

    return out_path


def main():
    ensure_dir(OUTPUT_DIR)

    done_files = load_done_files(LOG_PATH)

    json_files = sorted(INPUT_DIR.glob("*.json"))
    if not json_files:
        print(f"[WARN] 未找到 json 文件：{INPUT_DIR.resolve()}")
        return

    print(f"[FOUND] {len(json_files)} files in {INPUT_DIR.resolve()}")

    for json_file in json_files:
        # 判重：日志里有 or txt 已存在 都跳过
        out_path = OUTPUT_DIR / f"{json_file.stem}.txt"
        if json_file.name in done_files or out_path.exists():
            print(f"[SKIP] already processed => {json_file.name}")
            continue

        try:
            result_path = process_one_json(json_file, OUTPUT_DIR)
            if result_path is not None:
                append_log(LOG_PATH, json_file.name, result_path.name)
                print(f"[OK] {json_file.name} -> {result_path}")
        except Exception as e:
            print(f"[ERROR] {json_file.name}: {repr(e)}")


if __name__ == "__main__":
    main()