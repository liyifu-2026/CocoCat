import subprocess
import os


class GitStore:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        if not os.path.isdir(os.path.join(repo_path, ".git")):
            subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "config", "user.name", "cococat-memory"],
                           cwd=repo_path, capture_output=True)
            subprocess.run(["git", "config", "user.email", "memory@cococat.local"],
                           cwd=repo_path, capture_output=True)

    def commit(self, message: str) -> bool:
        subprocess.run(["git", "add", "-A"], cwd=self.repo_path, capture_output=True)
        result = subprocess.run(["git", "commit", "-m", message],
                                cwd=self.repo_path, capture_output=True, text=True)
        return result.returncode == 0

    def log(self, max_count: int = 10) -> list[str]:
        result = subprocess.run(
            ["git", "log", f"--max-count={max_count}", "--oneline"],
            cwd=self.repo_path, capture_output=True, text=True
        )
        return [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]

    def revert(self) -> bool:
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=self.repo_path, capture_output=True, text=True
        )
        if result.stdout.strip() == "0":
            return False
        count = int(result.stdout.strip())
        if count < 2:
            return False
        result = subprocess.run(
            ["git", "reset", "--hard", "HEAD~1"],
            cwd=self.repo_path, capture_output=True, text=True
        )
        return result.returncode == 0

    def last_commit_message(self) -> str:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=self.repo_path, capture_output=True, text=True
        )
        return result.stdout.strip()
