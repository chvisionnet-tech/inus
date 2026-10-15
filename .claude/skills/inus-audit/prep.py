#!/usr/bin/env python3
"""INUS 점검 사전준비 (읽기 전용: 원본 소스는 수정하지 않는다).

하는 일: 소스 인코딩 변환(CP949 -> UTF-8), 함수 색인, 대형 파일 분할 계획,
키 노출 1차 스캔, git 상태 확인. 결과는 <저장소>/audit_work/ 에만 쓴다.
사용: python3 prep.py [--root 저장소경로] [--no-fetch]   (Windows: py 또는 python)
주의: audit_work 는 일부러 숨김/ignore 로 만들지 않는다. 검색 도구가 숨김/ignore 폴더를 건너뛰기 때문이다.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SRC_DIRS = ["src/vba", "src/gas-main", "src/gas-sales", "src/worker", "site"]
EXTS = {".bas", ".cls", ".frm", ".gs", ".js", ".html", ".htm", ".json"}
VBA_EXTS = {".bas", ".cls", ".frm"}
CHUNK = 3000
PROC_VBA = re.compile(
    r"^\s*(?:Public\s+|Private\s+|Friend\s+)?(?:Static\s+)?(Sub|Function|Property\s+(?:Get|Let|Set))\s+(\w+)", re.I)
PROC_JS = re.compile(r"^\s*(?:async\s+)?function\s+(\w+)")
KEYPAT = [
    ("OpenAI형 키", re.compile(r"sk-[A-Za-z0-9_\-]{20,}")),
    ("Google API 키", re.compile(r"AIza[0-9A-Za-z_\-]{30,}")),
    ("GAS 배포 주소 직접 기재", re.compile(r"AKfycb[A-Za-z0-9_\-]{20,}")),
    ("AWS형 키", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("키/토큰 대입", re.compile(r"(?i)(?:api[_-]?key|secret|token|passwd|password)\s*[:=]\s*[\"'][^\"']{12,}[\"']")),
]


def decode(raw):
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8"), "utf-8-bom"
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        return raw.decode("cp949"), "cp949"
    except UnicodeDecodeError:
        return raw.decode("cp949", errors="replace"), "cp949(깨짐 있음)"


def find_procs(lines, ext):
    out = []
    for i, ln in enumerate(lines, 1):
        if ext in VBA_EXTS:
            m = PROC_VBA.match(ln)
            if m:
                out.append((i, m.group(1).split()[0], m.group(2)))
        else:
            m = PROC_JS.match(ln)
            if m:
                out.append((i, "function", m.group(1)))
    return out


def plan_chunks(total, procs):
    """프로시저 시작 줄에서만 자른다. 한 프로시저가 한도보다 길면 중간에서 자르고 표시한다."""
    if total <= CHUNK:
        return [{"from": 1, "to": total, "midcut": False}]
    starts = sorted(p[0] for p in procs)
    chunks, begin = [], 1
    while total - begin + 1 > CHUNK:
        limit = begin + CHUNK
        cands = [s for s in starts if begin < s <= limit]
        cut = max(cands) if cands else limit
        chunks.append({"from": begin, "to": cut - 1, "midcut": not cands})
        begin = cut
    chunks.append({"from": begin, "to": total, "midcut": False})
    return chunks


def git(root, *args, timeout=30):
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[3]))
    ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    out_dir = root / "audit_work"

    print("[사전점검] 저장소: %s" % root)
    branch = git(root, "branch", "--show-current")
    if branch:
        if not a.no_fetch:
            git(root, "fetch", "--quiet", timeout=25)
        dirty = [l for l in git(root, "status", "--porcelain").splitlines() if not l.endswith("audit_work/")]
        behind = git(root, "rev-list", "--count", "HEAD..@{u}") or "확인불가"
        print("[git] 브랜치 %s | 미커밋 변경 %d개 | 원격보다 뒤처진 커밋 %s" % (branch, len(dirty), behind))
        if dirty:
            print("[경고] 미커밋 변경이 있다. 점검 중 에이전트의 파일 수정 감지가 흐려지므로 정리 후 진행 권장.")
        if behind not in ("0", "확인불가"):
            print("[경고] 원격에 새 커밋이 있다. git pull 후 진행 권장.")
        if git(root, "ls-files", "audit_work"):
            print("[경고] audit_work 가 git 에 추적되고 있다. 커밋하지 말고 git rm --cached 로 빼야 한다.")
    else:
        print("[git] 저장소 정보를 읽지 못함(확인불가)")

    found = [d for d in SRC_DIRS if (root / d).is_dir()]
    if not found:
        print("[중단] 점검 대상 소스가 없다. 폴더 규칙과 내보내기 방법은 src/README.md 참고: %s" % ", ".join(SRC_DIRS))
        return 2

    if out_dir.exists():
        for sub in ("converted", "index"):
            shutil.rmtree(out_dir / sub, ignore_errors=True)
    (out_dir / "converted").mkdir(parents=True, exist_ok=True)
    (out_dir / "index").mkdir(parents=True, exist_ok=True)

    plan, keyhits = [], []
    for d in SRC_DIRS:
        base = root / d
        if not base.is_dir():
            print("[소스] %-14s 없음" % d)
            continue
        files = sorted(p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in EXTS)
        total = 0
        for p in files:
            rel = p.relative_to(root).as_posix()
            text, enc = decode(p.read_bytes())
            text = text.replace("\r\n", "\n")  # 줄 수는 그대로 유지된다
            lines = text.split("\n")
            if lines and lines[-1] == "":
                lines.pop()  # 끝 개행이 만드는 빈 조각 제거: 줄 수가 편집기/wc 와 같아진다
            dst = out_dir / "converted" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(text, encoding="utf-8", newline="\n")
            procs = find_procs(lines, p.suffix.lower())
            (out_dir / "index" / (rel.replace("/", "__") + ".idx.txt")).write_text(
                "\n".join("%d\t%s\t%s" % x for x in procs) + "\n", encoding="utf-8", newline="\n")
            chunks = plan_chunks(len(lines), procs)
            total += len(lines)
            plan.append({"file": rel, "work": "audit_work/converted/" + rel, "encoding": enc,
                         "lines": len(lines), "procs": len(procs), "chunks": chunks})
            for kind, pat in KEYPAT:
                for n, ln in enumerate(lines, 1):
                    m = pat.search(ln)
                    if m:
                        s = m.group(0)
                        keyhits.append((rel, n, kind, s[:4] + "***(%d자)" % len(s)))
        print("[소스] %-14s 파일 %d개, 줄 %s" % (d, len(files), format(total, ",")))

    (out_dir / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n[파일 상위 30] (줄 수 기준)  경로 | 인코딩 | 줄 | 프로시저 | 분할")
    for e in sorted(plan, key=lambda x: -x["lines"])[:30]:
        print("  %s | %s | %s | %d | %d조각%s" % (
            e["file"], e["encoding"], format(e["lines"], ","), e["procs"], len(e["chunks"]),
            " (중간분할 있음)" if any(c["midcut"] for c in e["chunks"]) else ""))
    big = [e for e in plan if len(e["chunks"]) > 1]
    print("[대형] %d개 파일이 %d줄 초과 -> 조각으로 나눠 에이전트에 배정 (audit_work/plan.json)" % (len(big), CHUNK))
    bad = [e["file"] for e in plan if "깨짐" in e["encoding"]]
    if bad:
        print("[경고] 인코딩이 깨진 파일: %s" % ", ".join(bad))
    if keyhits:
        print("\n[키 노출 의심] %d건 (값은 마스킹, 위치만 표시)" % len(keyhits))
        for rel, n, kind, mv in keyhits[:40]:
            print("  %s:%d | %s | %s" % (rel, n, kind, mv))
        if len(keyhits) > 40:
            print("  ... 외 %d건" % (len(keyhits) - 40))
    else:
        print("[키 노출 의심] 1차 스캔 0건 (패턴 기반이라 완전하지 않다)")
    print("\n[완료] 변환본: audit_work/converted/ | 색인: audit_work/index/ | 계획: audit_work/plan.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
