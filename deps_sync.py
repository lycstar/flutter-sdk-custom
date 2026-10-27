#!/usr/bin/env python3
"""直接解析 flutter DEPS 并拉取 git 依赖, 绕过 gclient(Termux 下死锁).
用法: python3 deps_sync.py <flutter_root> [jobs]
- 浅拉取 (git init + fetch --depth=1 <rev> + checkout FETCH_HEAD)
- 断点续传: 已 checkout 到目标 rev 的条目跳过
- cipd / download_* / fuchsia / mac 相关条目跳过
"""
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SKIP_PAT = re.compile(
    r"download_|setup_githooks|run_fuchsia_emu|host_os == |host_cpu == ")


def load_deps(root: Path):
    src = (root / 'DEPS').read_text()
    env = {'vars': {}}

    builtin_vars = {'host_os': 'linux', 'host_cpu': 'arm64',
                    'host_arch': 'arm64'}  # gclient 内置, 按本机取值

    def Var(key):
        return env['vars'][key] if key in env['vars'] else builtin_vars[key]

    env['Var'] = Var
    exec(src, env)  # DEPS 是受控上游文件
    deps, hooks = env.get('deps', {}), env.get('hooks', [])
    print(f"DEPS: {len(deps)} deps, {len(hooks)} hooks (全部 hooks 跳过)")
    return deps


def entry_url_rev(key, val):
    if isinstance(val, str):
        if '@' not in val:
            return None, None, f"skip(no-rev): {key}"
        url, rev = val.rsplit('@', 1)
        return url, rev, None
    if isinstance(val, dict):
        if val.get('dep_type') == 'cipd':
            return None, None, f"skip(cipd): {key}"
        url = val.get('url', '')
        rev = val.get('rev') or val.get('revision')
        if not url or not rev:
            return None, None, f"skip(unknown-type): {key}"
        return url, rev, None
    return None, None, f"skip(bad-entry): {key}"


def current_rev(repo: Path):
    try:
        return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repo,
                              capture_output=True, text=True,
                              timeout=30).stdout.strip()
    except Exception:
        return None


def shallow_fetch(repo: Path, url: str, rev: str):
    if not (repo / '.git').exists():
        repo.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'init', '-q'], cwd=repo, check=True)
        subprocess.run(['git', 'remote', 'add', 'origin', url],
                       cwd=repo, check=True)
    else:
        remotes = subprocess.run(['git', 'remote', 'get-url', 'origin'],
                                 cwd=repo, capture_output=True, text=True)
        if remotes.stdout.strip() != url:
            subprocess.run(['git', 'remote', 'set-url', 'origin', url],
                           cwd=repo, check=True)
    subprocess.run(['git', 'fetch', '-q', '--depth=1', '--no-tags',
                    'origin', rev], cwd=repo, check=True, timeout=1800)
    subprocess.run(['git', 'checkout', '-q', '--detach', 'FETCH_HEAD'],
                   cwd=repo, check=True, timeout=600)


def sync_one(key, url, rev, root: Path):
    repo = root / key
    if current_rev(repo) == rev:
        return key, 'cached', None
    last_err = None
    for attempt in range(3):
        try:
            shallow_fetch(repo, url, rev)
            if current_rev(repo) != rev:
                raise RuntimeError(f"rev mismatch after checkout: {key}")
            return key, 'done', None
        except Exception as e:
            last_err = str(e)[:200]
            time.sleep(5 * (attempt + 1))
    return key, 'failed', last_err


def main():
    root = Path(sys.argv[1]).resolve()
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    deps = load_deps(root)
    state_file = root / '.deps_sync_state.json'
    state = json.loads(state_file.read_text()) if state_file.exists() else {}

    tasks, skipped = [], []
    for key, val in deps.items():
        url, rev, skip = entry_url_rev(key, val)
        if skip:
            skipped.append(skip)
            continue
        cond = None
        if isinstance(val, dict):
            cond = val.get('condition')
        if cond and SKIP_PAT.search(cond):
            skipped.append(f"skip(cond): {key} [{cond[:50]}]")
            continue
        if state.get(key) == rev:
            continue
        tasks.append((key, url, rev))

    print(f"待拉取 {len(tasks)}, 跳过 {len(skipped)}, 已缓存 {len(state)}")
    for s in skipped:
        print(" ", s)

    results = []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futs = {pool.submit(sync_one, k, u, r, root): k
                for k, u, r in tasks}
        for fut in as_completed(futs):
            key, status, err = fut.result()
            print(f"[{status}] {key}" + (f" — {err}" if err else ""), flush=True)
            if status != 'failed':
                rev = next(r for kk, _, r in tasks if kk == key)
                state[key] = rev
                state_file.write_text(json.dumps(state))
            results.append((key, status, err))

    failed = [r for r in results if r[1] == 'failed']
    print(f"\n完成. 成功/缓存 {len(results)-len(failed)}, 失败 {len(failed)}")
    if failed:
        for k, _, e in failed:
            print(f"FAILED: {k}: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
