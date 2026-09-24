"""Audit a committed package; optionally exercise native CLI installation only.

No model turn is sent. Native checks use a new CODEX_HOME, no credentials, and
an owned local bare Git origin. Keep --work-dir outside the source repository.
This is an explicit integration command, not part of unittest discovery.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tomllib
import zipfile


PLUGIN = "plugins/evrik/"
# Historical identity is used only to verify explicit uninstall/reinstall migration.
LEGACY_NAME = "research-lab"
LEGACY_ID = f"{LEGACY_NAME}@{LEGACY_NAME}"
PLUGIN_ID = "evrik@evrik"
VERSION = "1.0.0"
PLUGIN_FILES = {
    ".codex-plugin/plugin.json", "LICENSE", "skills/research/SKILL.md",
    "skills/research/agents/openai.yaml", "skills/research/scripts/research.py",
    "skills/research/references/literature.md",
    "skills/research/references/experiments.md",
    "skills/research/references/evidence.md",
    "hooks/hooks.json", "skills/research/references/parallelism.md",
}
HOOK_COMMAND = 'python3 -X utf8 -B "${CLAUDE_PLUGIN_ROOT}/skills/research/scripts/research.py" evidence hook'
HOOK_COMMAND_WINDOWS = 'python -X utf8 -B "${CLAUDE_PLUGIN_ROOT}/skills/research/scripts/research.py" evidence hook'
BASELINE = "d27a243e52effcdee344a5adb03f614554bee608"
MARKETPLACE = ".agents/plugins/marketplace.json"
REPO_FILES = {PLUGIN + name for name in PLUGIN_FILES} | {
    MARKETPLACE, ".gitattributes", ".gitignore", ".github/workflows/ci.yml",
    "README.md", "BEHAVIOR.md", "MATURITY.md", "LICENSE", "examples/run_demo.py",
    "examples/small-regression/.gitignore", "examples/small-regression/data.json",
    "examples/small-regression/evaluate.py", "examples/small-regression/model.json",
    "tests/test_research.py", "tests/check_distribution.py", "tests/fault_driver.py",
    "tests/test_fault_boundaries.py", "tests/test_input_boundaries.py",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(args, *, cwd=None, env=None, check=True, timeout=90):
    result = subprocess.run(
        [str(arg) for arg in args], cwd=cwd, env=env, capture_output=True,
        timeout=timeout, check=False,
    )
    if check:
        require(result.returncode == 0, f"Command failed: {args}\n{result.stderr.decode('utf-8', 'replace')}")
    return result


def git(repo, *args):
    return run(["git", "--no-optional-locks", "-C", repo, *args]).stdout


def committed_files(repo, revision):
    """Read blobs independently of the archive used for the package check."""
    commit = git(repo, "rev-parse", "--verify", f"{revision}^{{commit}}").decode().strip()
    files = {}
    for line in git(repo, "ls-tree", "-rz", commit).split(b"\0"):
        if not line:
            continue
        metadata, raw_name = line.split(b"\t", 1)
        mode, kind, blob = metadata.decode().split()
        name = raw_name.decode("utf-8")
        require(kind == "blob" and mode in {"100644", "100755"}, f"Unsupported package entry: {name}")
        files[name] = git(repo, "cat-file", "blob", blob)
    return commit, files


def payload(files, prefix=PLUGIN):
    values = {name[len(prefix):]: content for name, content in files.items() if name.startswith(prefix)}
    require(set(values) == PLUGIN_FILES, f"Unexpected plugin inventory: {sorted(set(values) ^ PLUGIN_FILES)}")
    return values


def hashes(files):
    return {name: sha(content) for name, content in sorted(files.items())}


def validate_hooks(content):
    expected = {"hooks": {event: [{"matcher": "*", "hooks": [{
        "type": "command", "command": HOOK_COMMAND,
        "commandWindows": HOOK_COMMAND_WINDOWS, "async": False, "timeout": 5,
    }]}] for event in ("PreToolUse", "PostToolUse")}}
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"Duplicate hook definition key: {key}")
            result[key] = value
        return result
    # Serialized comparison also rejects bool/int and int/float substitutions.
    actual = json.loads(content, object_pairs_hook=unique)
    require(json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True),
            "Unexpected hook definition; only the reviewed synchronous Pre/Post commands are allowed")


def audit_package(repo, revision, report, work):
    require(not git(repo, "status", "--porcelain", "--untracked-files=all").strip(), "A clean committed candidate is required")
    commit, files = committed_files(repo, revision)
    require(commit == git(repo, "rev-parse", "HEAD").decode().strip(), "Check out the candidate commit before auditing")
    require(REPO_FILES <= set(files) <= REPO_FILES | {"MATURITY.md"},
            f"Package inventory changed; review intended files: {sorted(set(files) ^ REPO_FILES)}")
    checkout = {name: (repo / name).read_bytes() for name in files}
    require(hashes(checkout) == hashes(files), "Checkout bytes differ from committed Git blobs")
    archive_bytes = git(repo, "archive", "--format=zip", commit)
    archive_path = work / "candidate.zip"
    archive_path.write_bytes(archive_bytes)
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        archived = {item.filename: archive.read(item) for item in archive.infolist() if not item.is_dir()}
    require(hashes(archived) == hashes(files), "Archive does not match committed Git blobs")
    plugin = payload(files)
    manifest = json.loads(plugin[".codex-plugin/plugin.json"])
    marketplace = json.loads(files[MARKETPLACE])
    require(manifest["name"] == marketplace["name"] == "evrik", "Product name mismatch")
    require(manifest["version"] == VERSION, f"Plugin version must be {VERSION}")
    require(manifest["repository"] == "https://github.com/kageyoru08/evrik" and
            manifest["interface"]["displayName"] == marketplace["interface"]["displayName"] == "Evrik",
            "Public repository or display identity differs")
    require(manifest["skills"] == "./skills/" and manifest["license"] == "MIT", "Invalid plugin paths/license")
    require(not (set(manifest) & {"mcpServers", "apps", "commands"}), "Unexpected runtime integration")
    require(manifest.get("hooks") == "./hooks/hooks.json", "Invalid native hook path")
    validate_hooks(plugin["hooks/hooks.json"])
    require(manifest["interface"]["capabilities"] == [], "Unexpected declared capability")
    require(len(marketplace["plugins"]) == 1 and marketplace["plugins"][0]["name"] == "evrik", "Expected one plugin")
    require(marketplace["plugins"][0]["source"] == {"source": "local", "path": "./plugins/evrik"}, "Invalid marketplace source")
    require(plugin["LICENSE"] == files["LICENSE"], "Packaged license differs")
    runner_ast = ast.parse(plugin["skills/research/scripts/research.py"].decode())
    imports = set()
    for node in ast.walk(runner_ast):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
    require(imports <= sys.stdlib_module_names | {"__future__"}, f"Unexpected runner dependencies: {imports - sys.stdlib_module_names}")
    skill = plugin["skills/research/SKILL.md"].decode()
    require(skill.startswith("---\nname: research\n") and "\ndescription: " in skill, "Invalid research skill frontmatter")
    checked_links = []
    for name, content in files.items():
        if not name.endswith(".md"):
            continue
        for target in re.findall(r"\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)", content.decode()):
            if target.startswith("#") or re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            path = target.split("#", 1)[0]
            resolved = (repo / PurePosixPath(name).parent / path).resolve()
            require(resolved.is_relative_to(repo), f"Link escapes package: {name}: {target}")
            relative = resolved.relative_to(repo).as_posix()
            require(relative in files or any(item.startswith(relative.rstrip("/") + "/") for item in files),
                    f"Broken relative link: {name}: {target}")
            checked_links.append({"source": name, "target": target})
    report["package"] = {
        "commit": commit, "clean_checkout": True, "archive": str(archive_path),
        "archive_sha256": sha(archive_bytes), "git_blob_sha256": hashes(files),
        "plugin_git_blob_sha256": hashes(plugin), "relative_links": checked_links,
        "metadata_checks": "passed", "version": manifest["version"], "runner_imports": sorted(imports),
        "hook_definition_sha256": sha(plugin["hooks/hooks.json"]),
    }
    return commit, files


def codex_binary(requested):
    executable = Path(requested or shutil.which("codex") or "")
    require(executable.is_file(), "Install official @openai/codex@latest or pass --codex")
    if executable.suffix.lower() == ".exe":
        return str(executable.resolve())
    # npm's shim starts a child process. Use its installed native binary so the
    # app-server process handle also owns the process we close on failure.
    roots = [executable.parent / "node_modules/@openai/codex", executable.resolve().parent.parent]
    filename = "codex.exe" if os.name == "nt" else "codex"
    candidates = {path.resolve() for root in roots if root.is_dir()
                  for path in root.glob(f"node_modules/@openai/codex-*/vendor/*/bin/{filename}")}
    if len(candidates) == 1:
        return str(candidates.pop())
    require(executable.suffix.lower() not in {".cmd", ".ps1", ".js"}, "Pass the installed native Codex executable with --codex")
    return str(executable.resolve())


def disk_hashes(directory):
    return {path.relative_to(directory).as_posix(): sha(path.read_bytes())
            for path in sorted(directory.rglob("*")) if path.is_file()}


def hook_inventory(response, project, installed, expect_hooks, plugin_id=PLUGIN_ID):
    require(len(response["data"]) == 1, "Unexpected hook response scope")
    entry = response["data"][0]
    require(Path(entry["cwd"]).resolve() == project, "Hook listing cwd differs")
    require(not entry["errors"], f"Hook loader errors: {entry['errors']}")
    found = [hook for hook in entry["hooks"] if hook.get("pluginId") == plugin_id]
    require(len(found) == (2 if expect_hooks else 0), "Unexpected research hook count")
    if expect_hooks:
        require({hook["eventName"] for hook in found} == {"preToolUse", "postToolUse"}, "Unexpected research hook events")
        for hook in found:
            require(hook["source"] == "plugin" and Path(hook["sourcePath"]).resolve() == installed / "hooks/hooks.json",
                    "Loader used a different hook source")
            require(hook["handlerType"] == "command" and hook["async"] is False and
                    hook["matcher"] == "*" and hook["timeoutSec"] == 5 and hook["enabled"] is True,
                    "Loaded hook behavior differs from the package")
            require(hook["trustStatus"] == "untrusted" and hook["isManaged"] is False,
                    "Discovery check must not grant hook trust")
            require(re.fullmatch(r"sha256:[0-9a-f]{64}", hook["currentHash"]) is not None, "Missing hook definition identity")
    other = [hook for hook in entry["hooks"] if hook.get("pluginId") != plugin_id]
    canary = [hook for hook in other if hook.get("pluginId") == "distribution-canary@distribution-canary"]
    require(len(canary) == 1 and canary[0]["enabled"] is True and canary[0]["trustStatus"] == "untrusted",
            "Unrelated canary hook disappeared or acquired trust")
    # New definitions may change UI order; all other unrelated metadata must stay identical.
    preserved = sorted(({key: value for key, value in hook.items() if key != "displayOrder"}
                        for hook in other), key=lambda hook: hook["key"])
    return {"research": found, "other": preserved, "errors": entry["errors"], "warnings": entry["warnings"],
            "scope": "discovery only; hook execution is not tested or qualified", "expected_research_hooks": 2 if expect_hooks else 0}


def loader(cli, env, project, installed, work, label, *, research_installed=True, expect_hooks=True,
           plugin_id=PLUGIN_ID):
    """Fresh native task + forced skill reload, with no turn/start or model call."""
    events = []
    closure = {"termination": "not_closed", "exit_code": None}
    messages = queue.Queue()
    stderr_path = work / f"{label}-app-server.stderr.txt"
    with stderr_path.open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen([cli, "app-server", "--stdio"], cwd=project, env=env,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
                                   text=True, encoding="utf-8")
        def read_output():
            for line in process.stdout:
                messages.put(line)
            messages.put(None)
        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        def send(method, params=None, request_id=None):
            packet = {"method": method}
            if params is not None:
                packet["params"] = params
            if request_id is not None:
                packet["id"] = request_id
            events.append({"sent": packet})
            process.stdin.write(json.dumps(packet) + "\n")
            process.stdin.flush()
        def request(request_id, method, params):
            send(method, params, request_id)
            deadline = time.monotonic() + 45
            while True:
                remaining = deadline - time.monotonic()
                require(remaining > 0, f"App-server timeout: {method}")
                try:
                    line = messages.get(timeout=remaining)
                except queue.Empty:
                    raise RuntimeError(f"App-server timeout: {method}") from None
                require(line is not None, f"App-server ended during {method}")
                message = json.loads(line)
                events.append({"received": message})
                require(not ("method" in message and "id" in message), "Unexpected server request; no approvals or input are supplied")
                if message.get("id") == request_id:
                    require("error" not in message, f"App-server error: {message}")
                    return message["result"]
        try:
            request(1, "initialize", {"clientInfo": {"name": "evrik_distribution", "version": VERSION},
                                     "capabilities": {"experimentalApi": True}})
            send("initialized")
            started = request(2, "thread/start", {"cwd": str(project), "ephemeral": True})
            require(started["thread"]["ephemeral"] is True, "Thread is not ephemeral")
            require(Path(started["thread"]["cwd"]).resolve() == project, "Thread cwd differs")
            skills = request(3, "skills/list", {"cwds": [str(project)], "forceReload": True})
            require(len(skills["data"]) == 1, "Unexpected skill response scope")
            entry = skills["data"][0]
            require(not entry["errors"], f"Skill loader errors: {entry['errors']}")
            found = [skill for skill in entry["skills"] if skill.get("pluginId") == plugin_id]
            require(len(found) == (1 if research_installed else 0), "Unexpected research skill count")
            if research_installed:
                require(found[0]["name"] == f"{plugin_id.split('@')[0]}:research" and found[0]["enabled"],
                        "Installed research skill not enabled")
                require(Path(found[0]["path"]).resolve() == installed / "skills/research/SKILL.md", "Loader used a different skill path")
            require(any(skill.get("pluginId") == "distribution-canary@distribution-canary" and skill["enabled"]
                        for skill in entry["skills"]), "Canary skill disappeared")
            hooks = hook_inventory(request(4, "hooks/list", {"cwds": [str(project)]}), project,
                                   installed, expect_hooks, plugin_id)
            request(5, "thread/unsubscribe", {"threadId": started["thread"]["id"]})
            return {"thread_id": started["thread"]["id"], "ephemeral": True,
                    "skill": found[0] if found else None, "loader_errors": entry["errors"],
                    "hooks": hooks, "model_turns": 0, "process": closure}
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=10)
                closure["termination"] = "stdin_eof"
            except subprocess.TimeoutExpired:
                closure["termination"] = "terminate"
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    closure["termination"] = "kill"
                    process.kill()
                    process.wait(timeout=5)
            reader.join(timeout=2)
            process.stdout.close()
            closure["exit_code"] = process.returncode
            events.append({"process": dict(closure)})
            (work / f"{label}-app-server.json").write_text(json.dumps(events, indent=2) + "\n", encoding="utf-8")


def native_checks(repo, commit, files, args, report, work):
    cli = codex_binary(args.codex)
    home = work / "codex-home"
    home.mkdir()
    project = work / "project"
    project.mkdir()
    (project / ".research/runs/retained").mkdir(parents=True)
    (project / ".research/protocol.json").write_text('{"sentinel":"retained protocol"}\n', encoding="utf-8")
    (project / ".research/runs/retained/result.json").write_text('{"sentinel":"retained evidence"}\n', encoding="utf-8")
    (home / "unrelated-canary.txt").write_text("Retain unrelated user file\n", encoding="utf-8")
    (home / "config.toml").write_text('[analytics]\nenabled = false\n', encoding="utf-8")
    # Only the subprocesses receive this isolated environment; no real user
    # config, credential store, marketplace, or installed cache is changed.
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "PATHEXT", "COMSPEC", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL"}
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    env.update(CODEX_HOME=str(home), HOME=str(home), USERPROFILE=str(home),
               GIT_CONFIG_GLOBAL=str(work / "gitconfig"), GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
    version = run([cli, "--version"], env=env).stdout.decode().strip()
    require(bool(version), "Codex --version returned no version")
    with Path(cli).open("rb") as binary:
        binary_sha256 = hashlib.file_digest(binary, "sha256").hexdigest()
    native = report["native"] = {"cli_version": version, "cli_binary": cli,
                                  "cli_binary_sha256": binary_sha256,
                                  "scope": "plugin management and loader only; no authenticated model execution",
                                  "isolated_codex_home": str(home), "commands": [], "states": {}}
    python_command = "python" if os.name == "nt" else "python3"
    python_args = [python_command, "-X", "utf8", "-B", "-c",
                   "import json,sys; print(json.dumps({'version':list(sys.version_info[:3]),'executable':sys.executable}))"]
    hook_python = json.loads(run(python_args, cwd=project, env=env, timeout=20).stdout)
    require(tuple(hook_python["version"]) >= (3, 11), "Native hook command requires Python 3.11+")
    native["hook_python"] = {"argv": python_args, **hook_python,
                             "scope": "platform command availability only; native hook execution is not exercised"}
    def command(*parts, expected_success=True):
        result = run([cli, *parts, "--json"], cwd=project, env=env, check=False)
        stdout = result.stdout.decode("utf-8", "replace")
        stderr = result.stderr.decode("utf-8", "replace")
        entry = {"args": list(parts), "returncode": result.returncode, "stdout": stdout, "stderr": stderr}
        native["commands"].append(entry)
        try:
            response = json.loads(stdout)
        except json.JSONDecodeError:
            response = None
        def errors(value):
            if isinstance(value, dict):
                return bool(value.get("errors") or value.get("error")) or any(errors(item) for item in value.values())
            return isinstance(value, list) and any(errors(item) for item in value)
        succeeded = result.returncode == 0 and response is not None and not errors(response)
        require(succeeded == expected_success, f"Unexpected native command outcome: {entry}")
        return response
    canary = work / "canary-marketplace"
    (canary / ".agents/plugins").mkdir(parents=True)
    (canary / "plugin/.codex-plugin").mkdir(parents=True)
    (canary / "plugin/hooks").mkdir(parents=True)
    (canary / "plugin/skills/distribution-canary").mkdir(parents=True)
    (canary / ".agents/plugins/marketplace.json").write_text(json.dumps({
        "name": "distribution-canary", "plugins": [{"name": "distribution-canary",
        "source": {"source": "local", "path": "./plugin"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}}]}), encoding="utf-8")
    (canary / "plugin/.codex-plugin/plugin.json").write_text(json.dumps({
        "name": "distribution-canary", "version": "1.0.0", "description": "Distribution test canary",
        "skills": "./skills/", "hooks": "./hooks/hooks.json"}), encoding="utf-8")
    (canary / "plugin/hooks/hooks.json").write_text(json.dumps({"hooks": {"PreToolUse": [{
        "matcher": "distribution_canary_never_called", "hooks": [{"type": "command",
        "command": 'python3 -X utf8 -B -c "pass"', "commandWindows": 'python -X utf8 -B -c "pass"',
        "async": False, "timeout": 5}]}]}}), encoding="utf-8")
    (canary / "plugin/skills/distribution-canary/SKILL.md").write_text(
        "---\nname: distribution-canary\ndescription: Test fixture for native plugin preservation.\n---\n\nRead-only test canary.\n", encoding="utf-8")
    command("plugin", "marketplace", "add", str(canary))
    command("plugin", "add", "distribution-canary@distribution-canary")
    canary_cache = home / "plugins/cache/distribution-canary"
    preserved_canary = disk_hashes(canary_cache)
    require(preserved_canary, "Canary plugin was not cached")
    preserved_project = disk_hashes(project)
    before_config = tomllib.loads((home / "config.toml").read_text(encoding="utf-8"))
    native["config_before"] = before_config
    installed = home / f"plugins/cache/evrik/evrik/{VERSION}"
    native["before_loader"] = loader(cli, env, project, installed, work, "before-research",
                                     research_installed=False, expect_hooks=False)
    preserved_hooks = native["before_loader"]["hooks"]["other"]
    def load_at(label, expected, cache=installed, plugin_id=PLUGIN_ID):
        observed = loader(cli, env, project, cache, work, label, research_installed=bool(expected),
                          expect_hooks="hooks/hooks.json" in expected, plugin_id=plugin_id)
        require(observed["hooks"]["other"] == preserved_hooks, f"Unrelated hook metadata changed at {label}")
        native.setdefault("hook_loaders", {})[label] = observed
        return observed
    def state(label, expected, expected_revision=commit, cache=installed):
        observed = disk_hashes(cache)
        require(observed == hashes(expected), f"Installed payload mismatch at {label}: {observed}")
        require(marketplace_root.is_relative_to(home), "Git marketplace snapshot is outside isolated CODEX_HOME")
        snapshot_commit = git(marketplace_root, "rev-parse", "HEAD").decode().strip()
        require(snapshot_commit == expected_revision, f"Marketplace resolved a different commit at {label}: {snapshot_commit}")
        require(disk_hashes(canary_cache) == preserved_canary, f"Unrelated plugin changed at {label}")
        require(disk_hashes(project) == preserved_project, f"Project research records changed at {label}")
        require((home / "unrelated-canary.txt").read_text(encoding="utf-8") == "Retain unrelated user file\n", "Unrelated file changed")
        config = tomllib.loads((home / "config.toml").read_text(encoding="utf-8"))
        projected = json.loads(json.dumps(config))
        for section in ("plugins", "marketplaces"):
            if section in projected:
                for key in list(projected[section]):
                    if key in {"evrik", PLUGIN_ID, LEGACY_NAME, LEGACY_ID}:
                        del projected[section][key]
                if not projected[section]:
                    del projected[section]
        require(projected == before_config, f"Unrelated config changed at {label}: {config}")
        native["states"][label] = {"installed_sha256": observed, "config": config,
                                    "marketplace_root": str(marketplace_root), "marketplace_commit": snapshot_commit,
                                    "canary_sha256": preserved_canary, "project_sha256": preserved_project}
    if args.public_source:
        added = command("plugin", "marketplace", "add", args.public_source, "--ref", commit)
        marketplace_root = Path(added["installedRoot"]).resolve()
        command("plugin", "add", "evrik@evrik")
        state("public-installed-B", payload(files))
        native["loader"] = load_at("public-B", payload(files))
        state("public-loaded-B", payload(files))
        return
    baseline, old_files = committed_files(repo, args.baseline)
    old = payload(old_files, f"plugins/{LEGACY_NAME}/")
    new = payload(files)
    require(json.loads(old[".codex-plugin/plugin.json"])["version"] == "1.0.0", "Baseline version differs")
    require(json.loads(old[".codex-plugin/plugin.json"])["name"] == LEGACY_NAME, "Baseline identity differs")
    require(baseline != commit and hashes(old) != hashes(new), "Legacy and renamed packages must differ")
    changed = [name for name in sorted(set(old) | set(new)) if old.get(name) != new.get(name)]
    origin = work / "origin.git"
    run(["git", "clone", "--bare", "--no-hardlinks", repo, origin], env=env)
    run(["git", "--git-dir", origin, "symbolic-ref", "HEAD", "refs/heads/main"], env=env)
    run(["git", "--git-dir", origin, "update-ref", "refs/heads/main", baseline], env=env)
    source = "https://distribution.invalid/evrik.git"
    run(["git", "config", "--file", work / "gitconfig", f"url.{origin.as_uri()}.insteadOf", source], env=env)
    native.update(baseline_commit=baseline, candidate_commit=commit, changed_plugin_files=changed,
                  added_plugin_files=sorted(set(new) - set(old)), removed_plugin_files=sorted(set(old) - set(new)),
                  baseline_plugin_files=sorted(old), candidate_plugin_files=sorted(new),
                  local_origin=str(origin), source_transport="child-only Git URL rewrite to owned bare file origin")
    added = command("plugin", "marketplace", "add", source)
    marketplace_root = Path(added["installedRoot"]).resolve()
    legacy_cache = home / f"plugins/cache/{LEGACY_NAME}/{LEGACY_NAME}/1.0.0"
    legacy_marketplace = marketplace_root
    command("plugin", "add", LEGACY_ID)
    state("legacy-installed", old, baseline, legacy_cache)
    load_at("legacy-installed", old, legacy_cache, LEGACY_ID)
    command("plugin", "remove", LEGACY_ID)
    require(not legacy_cache.exists(), "Legacy plugin cache remains after uninstall")
    load_at("legacy-removed", {})
    command("plugin", "marketplace", "remove", LEGACY_NAME)
    require(not legacy_marketplace.exists(), "Legacy marketplace checkout remains")
    run(["git", "--git-dir", origin, "update-ref", "refs/heads/main", commit], env=env)
    added = command("plugin", "marketplace", "add", source)
    marketplace_root = Path(added["installedRoot"]).resolve()
    command("plugin", "add", PLUGIN_ID)
    migrated_config = tomllib.loads((home / "config.toml").read_text(encoding="utf-8"))
    require(LEGACY_ID not in migrated_config.get("plugins", {}) and
            LEGACY_NAME not in migrated_config.get("marketplaces", {}), "Legacy configuration remains")
    state("migrated-B", new)
    load_at("migrated-B", new)
    command("plugin", "marketplace", "upgrade", "evrik")
    state("refreshed-B", new)
    native["loader"] = load_at("refreshed-B", new)
    state("loaded-B", new)
    unavailable = work / "origin-unavailable.git"
    require(origin.resolve().is_relative_to(work) and unavailable.resolve().is_relative_to(work), "Origin move escaped work directory")
    origin.rename(unavailable)
    try:
        command("plugin", "marketplace", "upgrade", "evrik", expected_success=False)
        state("failed-refresh-retained-B", new)
        load_at("failed-refresh-retained-B", new)
    finally:
        unavailable.rename(origin)
    command("plugin", "remove", "evrik@evrik")
    state("removed", {})
    require(not installed.exists(), "Removed plugin cache directory remains")
    load_at("removed", {})
    command("plugin", "add", "evrik@evrik")
    state("reinstalled-B", new)
    native["reinstalled_loader"] = load_at("reinstalled-B", new)
    state("reinstalled-loaded-B", new)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--work-dir", type=Path, required=True, help="New evidence/scratch directory outside the source repo")
    parser.add_argument("--native", action="store_true", help="Exercise official CLI plugin management and loader, without model turns")
    parser.add_argument("--baseline", default=BASELINE)
    parser.add_argument("--codex", help="Installed native Codex executable (default: resolve official npm installation)")
    parser.add_argument("--public-source", help="Optional public marketplace install check instead of the local lifecycle; use only after publication")
    args = parser.parse_args()
    repo, work = args.repo.resolve(), args.work_dir.resolve()
    require(not work.is_relative_to(repo), "Evidence/scratch directory must be outside the source repository")
    work.mkdir(parents=True, exist_ok=False)
    report = {"status": "running", "host": platform.platform(), "python": sys.version,
              "git": run(["git", "--version"]).stdout.decode().strip()}
    try:
        commit, files = audit_package(repo, args.revision, report, work)
        if args.native:
            native_checks(repo, commit, files, args, report, work)
        require(not args.public_source or args.native, "--public-source requires --native")
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        output = work / "report.json"
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": report["status"], "report": str(output)}))


if __name__ == "__main__":
    main()
